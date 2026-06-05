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

audio.init_audio(str(Path(__file__).resolve().parent.parent / 'sounds'))

sounds = audio.list_sounds()
print(f"Available sounds: {sounds}")

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

    def stop(self):
        self.started = False
        if self.thread.is_alive():
            self.thread.join()
        self.cap.release()

config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
with config_path.open('r', encoding='utf-8') as config_file:
    config = json.load(config_file)

body_data = config["file_paths"]["body_tracking"]
config_dir = config_path.parent
body_model_path = Path(body_data) if Path(body_data).is_absolute() else (config_dir / body_data).resolve()

if not body_model_path.exists(): raise FileNotFoundError(f"Body model not found: {body_model_path}")

vision = tasks.vision
pose_landmarker = vision.PoseLandmarker.create_from_model_path(str(body_model_path))
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

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
        
    for connection in vision.PoseLandmarksConnections.POSE_LANDMARKS:
        start = landmarks[connection.start]
        end = landmarks[connection.end]
        if start.x is None or start.y is None or end.x is None or end.y is None: continue
        x1 = int(np.clip(start.x, 0.0, 1.0) * width)
        y1 = int(np.clip(start.y, 0.0, 1.0) * height)
        x2 = int(np.clip(end.x, 0.0, 1.0) * width)
        y2 = int(np.clip(end.y, 0.0, 1.0) * height)
        cv2.line(frame, (x1, y1), (x2, y2), color, thickness)
        


rtsp_url1 = "rtsp://root:defense@192.168.0.90:554/axis-media/media.amp?videocodec=h264&camera=2"
rtsp_url2 = "rtsp://root:defense@192.168.0.90:554/axis-media/media.amp?videocodec=h264&camera=1"

cam1 = RTSPStreamReader(rtsp_url1).start()
cam2 = RTSPStreamReader(rtsp_url2).start()

print("AXIS Dual Lenses Connected. Targeting Pipeline Operational.")

def process_camera_lens(frame):
    if frame is None: return frame, 0
    height, width = frame.shape[:2]
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 0), 2)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_input = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    try:
        pose_result = pose_landmarker.detect(mp_input)
        if pose_result and getattr(pose_result, 'pose_landmarks', None):
            for landmarks in pose_result.pose_landmarks:
                draw_pose_landmarks(frame, landmarks)
                
                ls = landmarks[11]
                rs = landmarks[12]
                lh = landmarks[23]
                rh = landmarks[24]
                
                if all(pt.x is not None and pt.y is not None for pt in [ls, rs, lh, rh]):
                    avg_x = (ls.x + rs.x + lh.x + rh.x) / 4.0
                    avg_y = (ls.y + rs.y + lh.y + rh.y) / 4.0
                    
                    target_x = int(np.clip(avg_x, 0.0, 1.0) * width)
                    target_y = int(np.clip(avg_y, 0.0, 1.0) * height)
                    
                    draw_target_crosshair(frame, target_x, target_y, radius=14, color=(0, 0, 255), thickness=2)
                    
    except Exception:
        pass 
        
    return frame, len(faces)

def generate_tracking_frames():
    alert_played = False
    while True:
        ret1, frame1, fps1 = cam1.read()
        ret2, frame2, fps2 = cam2.read()

        if not ret1 or not ret2 or frame1 is None or frame2 is None:
            time.sleep(0.01)
            continue

        frame1 = cv2.resize(frame1, (480, 270))
        frame2 = cv2.resize(frame2, (480, 270))

        frame1, faces1 = process_camera_lens(frame1)
        frame2, faces2 = process_camera_lens(frame2)

        cv2.putText(frame1, f"CAM 1: {fps1} FPS", (340, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        cv2.putText(frame2, f"CAM 2: {fps2} FPS", (340, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        merged_frame = cv2.hconcat([frame1, frame2])

        total_targets = faces1 + faces2
        if total_targets > 0:
            cv2.putText(merged_frame, f"PANORAMIC LOCK: {total_targets} TARGETS", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            if not alert_played:
                audio.play("cave3.ogg")
                alert_played = True
        else:
            alert_played = False

        ret, buffer = cv2.imencode('.jpg', merged_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
        if not ret: continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_tracking_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return '''
    <html>
    <head><title>Untitled</title></head>
    <body style="background:#111; color:white; font-family:sans-serif; text-align:center; margin:0; padding:20px;">
        <h2>death stream</h2>
        <div style="margin-top: 15px; color: #00ff00; font-weight: bold; letter-spacing: 1px;">STATUS: WORKING</div>
        <img src="/video_feed" style="border:3px solid #222; width:960px; height:270px; background:#000; margin-top:20px; box-shadow: 0 0 20px #000;"/>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='100.86.238.4', port=42069, threaded=True, use_reloader=False)
