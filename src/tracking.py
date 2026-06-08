import sys
sys.modules['tensorflow'] = None
sys.modules['tensorflow.tools'] = None
sys.modules['tensorflow.tools.docs'] = None

import cv2
import numpy as np
import json
import threading
import time
from flask import Flask, Response
import mediapipe as mp
import mediapipe.tasks as tasks
from pathlib import Path
import audio

# --- Global Shared State ---
latest_merged_frame = None
frame_lock = threading.Lock()
system_error_msg = None  # Holds background crash logs

try:
    audio.init_audio(str(Path(__file__).resolve().parent.parent / 'sounds'))
    sounds = audio.list_sounds()
    print(f"Available sounds: {sounds}")
except Exception as e:
    print(f"[AUDIO WARN] Audio failed to init: {e}")

app = Flask(__name__)

class RTSPStreamReader:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
        self.grabbed, self.frame = self.cap.read()
        self.started = False
        self.read_lock = threading.Lock()
        self.fps = 0.0
        self.prev_time = time.time()

    def start(self):
        if self.started: return self
        self.started = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()
        return self

    def update(self):
        while self.started:
            grabbed, frame = self.cap.read()
            if grabbed:
                current_time = time.time()
                time_delta = current_time - self.prev_time
                self.prev_time = current_time
                
                with self.read_lock:
                    self.grabbed = grabbed
                    self.frame = frame
                    if time_delta > 0:
                        instant_fps = 1.0 / time_delta
                        self.fps = (self.fps * 0.9) + (instant_fps * 0.1)
            else:
                time.sleep(1)
                self.cap.open(self.rtsp_url, cv2.CAP_FFMPEG)

    def read(self):
        with self.read_lock:
            frame_copy = self.frame.copy() if self.frame is not None else None
            return self.grabbed, frame_copy, round(self.fps, 1)

def draw_target_crosshair(frame, cx, cy, radius=15, color=(0, 0, 255), thickness=2):
    cv2.circle(frame, (cx, cy), radius, color, thickness)
    cv2.circle(frame, (cx, cy), 2, color, -1)
    cv2.line(frame, (cx, cy - radius - 5), (cx, cy - radius + 3), color, thickness)
    cv2.line(frame, (cx, cy + radius + 5), (cx, cy + radius - 3), color, thickness)
    cv2.line(frame, (cx - radius - 5, cy), (cx - radius + 3, cy), color, thickness)
    cv2.line(frame, (cx + radius + 5, cy), (cx + radius - 3, cy), color, thickness)
    cv2.putText(frame, "LOCK", (cx + radius + 8, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

def draw_pose_landmarks(frame, landmarks, color=(0, 255, 0), point_radius=3, thickness=2):
    height, width = frame.shape[:2]
    for landmark in landmarks:
        if landmark.x is None or landmark.y is None: continue
        x = int(np.clip(landmark.x, 0.0, 1.0) * width)
        y = int(np.clip(landmark.y, 0.0, 1.0) * height)
        cv2.circle(frame, (x, y), point_radius, color, -1)
        
    for connection in tasks.vision.PoseLandmarksConnections.POSE_LANDMARKS:
        start = landmarks[connection.start]
        end = landmarks[connection.end]
        if start.x is None or start.y is None or end.x is None or end.y is None: continue
        x1 = int(np.clip(start.x, 0.0, 1.0) * width)
        y1 = int(np.clip(start.y, 0.0, 1.0) * height)
        x2 = int(np.clip(end.x, 0.0, 1.0) * width)
        y2 = int(np.clip(end.y, 0.0, 1.0) * height)
        cv2.line(frame, (x1, y1), (x2, y2), color, thickness)

def trigger_audio_async(sound_file):
    def play():
        try: audio.play(sound_file)
        except: pass
    t = threading.Thread(target=play)
    t.daemon = True
    t.start()

# --- Processing Loop ---
def update_processing_loop():
    global latest_merged_frame, system_error_msg
    
    try:
        config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
        with config_path.open('r', encoding='utf-8') as config_file:
            config = json.load(config_file)

        body_data = config["file_paths"]["body_tracking"]
        config_dir = config_path.parent
        body_model_path = Path(body_data) if Path(body_data).is_absolute() else (config_dir / body_data).resolve()

        if not body_model_path.exists(): 
            raise FileNotFoundError(f"Body model not found at path: {body_model_path}")

        vision = tasks.vision
        options = vision.PoseLandmarkerOptions(
            base_options=tasks.BaseOptions(model_asset_path=str(body_model_path)),
            running_mode=vision.RunningMode.VIDEO
        )
        pose_landmarker = vision.PoseLandmarker.create_from_options(options)
        
        # Explicitly call objdetect to bypass headless OpenCV bugs
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml') #FIXED STUPID LINE NOW WE GET 25 FPS GOOD ENOUGHT

        rtsp_url1 = "rtsp://root:defense@192.168.0.90:554/axis-media/media.amp?videocodec=h264&camera=2"
        rtsp_url2 = "rtsp://root:defense@192.168.0.90:554/axis-media/media.amp?videocodec=h264&camera=1"

        cam1 = RTSPStreamReader(rtsp_url1).start()
        cam2 = RTSPStreamReader(rtsp_url2).start()
        print("[CAM1] ready\n[CAM2] ready\n[STARTUP] both cameras ready")

    except Exception as initialization_error:
        system_error_msg = f"CRITICAL PIPELINE FAILURE: {str(initialization_error)}"
        print(f"\n!!! {system_error_msg} !!!\n")
        return

    while True:
        ret1, frame1, fps1 = cam1.read()
        ret2, frame2, fps2 = cam2.read()

        if not ret1 or not ret2 or frame1 is None or frame2 is None:
            time.sleep(0.01)
            continue

        frame1 = cv2.resize(frame1, (480, 270))
        frame2 = cv2.resize(frame2, (480, 270))

        for f_idx, frame in enumerate([frame1, frame2]):
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            
            if len(faces) > 0:
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 0), 2)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_input = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            try:
                timestamp_ms = int(time.time() * 1000)
                pose_result = pose_landmarker.detect(mp_input, timestamp_ms)
                
                if pose_result and getattr(pose_result, 'pose_landmarks', None):
                    for landmarks in pose_result.pose_landmarks:
                        draw_pose_landmarks(frame, landmarks)
                        ls, rs, lh, rh = landmarks[11], landmarks[12], landmarks[23], landmarks[24]
                        if all(pt.x is not None and pt.y is not None for pt in [ls, rs, lh, rh]):
                            avg_x = (ls.x + rs.x + lh.x + rh.x) / 4.0
                            avg_y = (ls.y + rs.y + lh.y + rh.y) / 4.0
                            tx = int(np.clip(avg_x, 0.0, 1.0) * frame.shape[1])
                            ty = int(np.clip(avg_y, 0.0, 1.0) * frame.shape[0])
                            draw_target_crosshair(frame, tx, ty, radius=14, color=(0, 0, 255), thickness=2)
            except Exception as mp_err:
                pass

        cv2.putText(frame1, f"CAM 1: {fps1} FPS", (340, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        cv2.putText(frame2, f"CAM 2: {fps2} FPS", (340, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        merged = cv2.hconcat([frame1, frame2])
        ret, buffer = cv2.imencode('.jpg', merged, [cv2.IMWRITE_JPEG_QUALITY, 50])
        if ret:
            with frame_lock:
                latest_merged_frame = buffer.tobytes()
        time.sleep(0.01)

# --- Flask Server ---
def generate_tracking_frames():
    while True:
        with frame_lock:
            if latest_merged_frame is None:
                blank = np.zeros((270, 960, 3), dtype=np.uint8)
                if system_error_msg:
                    cv2.putText(blank, system_error_msg, (30, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                else:
                    cv2.putText(blank, "CONNECTING TO LENSES...", (360, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                _, buffer = cv2.imencode('.jpg', blank)
                frame_data = buffer.tobytes()
            else:
                frame_data = latest_merged_frame
                
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        time.sleep(0.03)

@app.route('/video_feed')
def video_feed():
    return Response(generate_tracking_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    status = f"<div style='color:red;'>{system_error_msg}</div>" if system_error_msg else "<div style='color:#00ff00;'>STATUS: ACTIVE</div>"
    return f'''
    <html>
    <head><title>Tracking Dashboard</title></head>
    <body style="background:#111; color:white; font-family:sans-serif; text-align:center; margin:0; padding:20px;">
        <h2>Tracking Stream</h2>
        <div style="margin-top: 15px; font-weight: bold; letter-spacing: 1px;">{status}</div>
        <img src="/video_feed" style="border:3px solid #222; width:960px; height:270px; background:#000; margin-top:20px;"/>
    </body>
    </html>
    '''

if __name__ == '__main__':
    proc_thread = threading.Thread(target=update_processing_loop)
    proc_thread.daemon = True
    proc_thread.start()
    
    # FORCED OVERRIDE: Listen globally on port 5000 to overwrite the old 42069 configuration
    app.run(host='0.0.0.0', port=5000, threaded=True, use_reloader=False)
