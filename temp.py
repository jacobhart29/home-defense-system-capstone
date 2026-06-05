import os
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"

import sys
sys.modules['tensorflow'] = None
sys.modules['tensorflow.tools'] = None
sys.modules['tensorflow.tools.docs'] = None

import cv2
import numpy as np
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from flask import Flask, Response
import mediapipe as mp
import mediapipe.tasks as tasks
from pathlib import Path

app = Flask(__name__)

# ── Config & model loading ────────────────────────────────────────────────────

config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
with config_path.open('r', encoding='utf-8') as f:
    config = json.load(f)

body_data = config["file_paths"]["body_tracking"]
config_dir = config_path.parent
body_model_path = (
    Path(body_data) if Path(body_data).is_absolute()
    else (config_dir / body_data).resolve()
)
if not body_model_path.exists():
    raise FileNotFoundError(f"Body model not found: {body_model_path}")

vision = tasks.vision
pose_landmarker = vision.PoseLandmarker.create_from_model_path(str(body_model_path))
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

# ── Camera config ─────────────────────────────────────────────────────────────

CAMERA_IP   = "192.168.0.90"
CAMERA_USER = "root"
CAMERA_PASS = "defense"
TARGET_W, TARGET_H = 480, 270
INFERENCE_EVERY_N = 3  # run pose+face every N frames, reuse result in between

def make_rtsp_url(camera_index):
    return (
        f"rtsp://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:554"
        f"/axis-media/media.amp"
        f"?videocodec=h264"
        f"&camera={camera_index}"
        f"&resolution=640x360"
        f"&fps=15"
        f"&compression=50"
    )

# ── Threaded camera reader ────────────────────────────────────────────────────

class CameraReader:
    def __init__(self, camera_index):
        self.index = camera_index
        self.frame = None
        self.lock = threading.Lock()
        self.fps = 0.0
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _open(self):
        url = make_rtsp_url(self.index)
        while True:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if cap.isOpened():
                for _ in range(3):
                    cap.read()
                print(f"[CAM{self.index}] ready")
                return cap
            print(f"[CAM{self.index}] failed to open, retrying in 2s...")
            cap.release()
            time.sleep(2)

    def _run(self):
        cap = self._open()
        t_last = time.time()
        while not self._stop:
            ret, frame = cap.read()
            if not ret or frame is None:
                print(f"[CAM{self.index}] lost frame, reconnecting...")
                cap.release()
                cap = self._open()
                continue
            now = time.time()
            d = now - t_last
            t_last = now
            fps = 1.0 / d if d > 0 else 0.0
            with self.lock:
                self.frame = frame
                self.fps = self.fps * 0.9 + fps * 0.1

    def read(self):
        with self.lock:
            return (self.frame is not None), (
                self.frame.copy() if self.frame is not None else None
            ), self.fps

    def stop(self):
        self._stop = True

# ── Drawing helpers ───────────────────────────────────────────────────────────

def draw_target_crosshair(frame, cx, cy, radius=15, color=(0, 0, 255), thickness=2):
    cv2.circle(frame, (cx, cy), radius, color, thickness)
    cv2.circle(frame, (cx, cy), 2, color, -1)
    cv2.line(frame, (cx, cy - radius - 5), (cx, cy - radius + 3), color, thickness)
    cv2.line(frame, (cx, cy + radius + 5), (cx, cy + radius - 3), color, thickness)
    cv2.line(frame, (cx - radius - 5, cy), (cx - radius + 3, cy), color, thickness)
    cv2.line(frame, (cx + radius + 5, cy), (cx + radius - 3, cy), color, thickness)
    cv2.putText(frame, "LOCK", (cx + radius + 8, cy + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

def draw_pose_landmarks(frame, landmarks, color=(0, 255, 0), point_radius=3, thickness=2):
    h, w = frame.shape[:2]
    for lm in landmarks:
        if lm.x is None or lm.y is None:
            continue
        x = int(np.clip(lm.x, 0.0, 1.0) * w)
        y = int(np.clip(lm.y, 0.0, 1.0) * h)
        cv2.circle(frame, (x, y), point_radius, color, -1)
    for conn in vision.PoseLandmarksConnections.POSE_LANDMARKS:
        s, e = landmarks[conn.start], landmarks[conn.end]
        if any(pt.x is None or pt.y is None for pt in [s, e]):
            continue
        x1 = int(np.clip(s.x, 0.0, 1.0) * w); y1 = int(np.clip(s.y, 0.0, 1.0) * h)
        x2 = int(np.clip(e.x, 0.0, 1.0) * w); y2 = int(np.clip(e.y, 0.0, 1.0) * h)
        cv2.line(frame, (x1, y1), (x2, y2), color, thickness)

# ── Per-frame processing ──────────────────────────────────────────────────────

# Per-camera inference state (no lock needed — each cam processed in its own executor slot)
_infer_counter = [0, 0]
_last_faces = [[], []]
_last_landmarks = [None, None]

def process_frame(frame, cam_slot):
    if frame is None:
        return frame, 0

    h, w = frame.shape[:2]
    _infer_counter[cam_slot] += 1
    run_infer = (_infer_counter[cam_slot] % INFERENCE_EVERY_N == 0)

    if run_infer:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _last_faces[cam_slot] = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_input = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        try:
            result = pose_landmarker.detect(mp_input)
            _last_landmarks[cam_slot] = (
                result.pose_landmarks
                if result and getattr(result, 'pose_landmarks', None)
                else None
            )
        except Exception:
            _last_landmarks[cam_slot] = None

    for (x, y, fw, fh) in _last_faces[cam_slot]:
        cv2.rectangle(frame, (x, y), (x + fw, y + fh), (255, 255, 0), 2)

    if _last_landmarks[cam_slot]:
        for landmarks in _last_landmarks[cam_slot]:
            draw_pose_landmarks(frame, landmarks)
            ls, rs = landmarks[11], landmarks[12]
            lh, rh = landmarks[23], landmarks[24]
            if all(pt.x is not None and pt.y is not None for pt in [ls, rs, lh, rh]):
                cx = int(np.clip((ls.x + rs.x + lh.x + rh.x) / 4, 0, 1) * w)
                cy = int(np.clip((ls.y + rs.y + lh.y + rh.y) / 4, 0, 1) * h)
                draw_target_crosshair(frame, cx, cy, radius=14, color=(0, 0, 255))

    return frame, len(_last_faces[cam_slot])

# ── Startup ───────────────────────────────────────────────────────────────────

_cam1 = CameraReader(1)
_cam2 = CameraReader(2)
_executor = ThreadPoolExecutor(max_workers=2)

# ── Frame generator ───────────────────────────────────────────────────────────

def generate_frames():
    while True:
        ok1, frame1, fps1 = _cam1.read()
        ok2, frame2, fps2 = _cam2.read()

        if not ok1 or not ok2:
            time.sleep(0.01)
            continue

        f1 = cv2.resize(frame1, (TARGET_W, TARGET_H))
        f2 = cv2.resize(frame2, (TARGET_W, TARGET_H))

        fut1 = _executor.submit(process_frame, f1, 0)
        fut2 = _executor.submit(process_frame, f2, 1)
        f1, faces1 = fut1.result()
        f2, faces2 = fut2.result()

        cv2.putText(f1, f"CAM 1 | {fps1:.1f} FPS", (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(f2, f"CAM 2 | {fps2:.1f} FPS", (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        merged = cv2.hconcat([f1, f2])

        total = faces1 + faces2
        if total > 0:
            cv2.putText(merged,
                        f"PANORAMIC LOCK: {total} TARGET{'S' if total > 1 else ''}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        ok, buf = cv2.imencode('.jpg', merged, [cv2.IMWRITE_JPEG_QUALITY, 55])
        if not ok:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return '''
    <html>
    <head><title>P4705-PLVE</title></head>
    <body style="background:#111;color:white;font-family:sans-serif;text-align:center;margin:0;padding:20px;">
        <h2>AXIS P4705-PLVE &mdash; Panoramic Tracking</h2>
        <div style="margin-top:10px;color:#00ff00;font-weight:bold;letter-spacing:1px;">STATUS: OPERATIONAL</div>
        <img src="/video_feed"
             style="border:3px solid #222;width:960px;height:270px;background:#000;margin-top:20px;box-shadow:0 0 20px #000;"/>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=42069, threaded=False, use_reloader=False)
