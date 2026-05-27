import cv2
import numpy as np
import json
import threading
import time
import mediapipe.tasks as tasks
from mediapipe.tasks.python.vision.core import image as mp_image
from pathlib import Path

# --- 1. NON-BLOCKING RTSP THREADED STREAM READER ---
class RTSPStreamReader:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
        self.grabbed, self.frame = self.cap.read()
        self.started = False
        self.read_lock = threading.Lock()

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
                with self.read_lock:
                    self.grabbed = grabbed
                    self.frame = frame
            else:
                time.sleep(1)
                self.cap.open(self.rtsp_url, cv2.CAP_FFMPEG)

    def read(self):
        with self.read_lock:
            frame_copy = self.frame.copy() if self.frame is not None else None
            return self.grabbed, frame_copy

    def stop(self):
        self.started = False
        if self.thread.is_alive():
            self.thread.join()
        self.cap.release()

# --- 2. CONFIGURATION & MODELS ENVIRONMENT SETUP ---
config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
with config_path.open('r', encoding='utf-8') as config_file:
    config = json.load(config_file)

face_data = config["file_paths"]["face_tracking"]
body_data = config["file_paths"]["body_tracking"]

config_dir = config_path.parent
face_model_path = Path(face_data) if Path(face_data).is_absolute() else (config_dir / face_data).resolve()
body_model_path = Path(body_data) if Path(body_data).is_absolute() else (config_dir / body_data).resolve()

if not face_model_path.exists(): raise FileNotFoundError(f"Face model not found: {face_model_path}")
if not body_model_path.exists(): raise FileNotFoundError(f"Body model not found: {body_model_path}")

vision = tasks.vision
face_detector = vision.FaceDetector.create_from_model_path(str(face_model_path))
pose_landmarker = vision.PoseLandmarker.create_from_model_path(str(body_model_path))

# --- 3. RENDERING UTILITIES ---
def draw_detection(frame, detection, color=(0, 255, 255), thickness=2):
    bbox = detection.bounding_box
    start = (int(bbox.origin_x), int(bbox.origin_y))
    end = (int(bbox.origin_x + bbox.width), int(bbox.origin_y + bbox.height))
    cv2.rectangle(frame, start, end, color, thickness)
    
    keypoints = getattr(detection, 'keypoints', None)
    if keypoints:
        for kp in keypoints:
            if kp.x is None or kp.y is None: continue
            # Landmarks from Tasks API on stitched frames are already absolute pixels relative to the input image size
            x = int(kp.x)
            y = int(kp.y)
            cv2.circle(frame, (x, y), 3, color, -1)

def draw_pose_landmarks(frame, landmarks, color=(0, 255, 0), point_radius=3, thickness=2):
    # Tasks API returns normalized coordinates (0.0 to 1.0) relative to the final stitched image size
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

# --- 4. START RTSP LENSES ---
# Removed < > tags from string structure
rtsp_url1 = "rtsp://root:defense@192.168.0.90:554/axis-media/media.amp?videocodec=h264&camera=1"
rtsp_url2 = "rtsp://root:defense@192.168.0.90:554/axis-media/media.amp?videocodec=h264&camera=2"

cam1 = RTSPStreamReader(rtsp_url1).start()
cam2 = RTSPStreamReader(rtsp_url2).start()

print("Connecting to AXIS Dual Lenses...")

# --- 5. APPLICATION PROCESSING LOOP ---
while True:
    ret1, frame1 = cam1.read()
    ret2, frame2 = cam2.read()

    # Fallback to webcam if network stream fails to initialize
    if not ret1 or not ret2 or frame1 is None or frame2 is None:
        continue

    # Ensure symmetric vertical alignment before horizontal stitching
    h1, w1, _ = frame1.shape
    h2, w2, _ = frame2.shape
    if h1 != h2:
        new_width = int(w2 * (h1 / h2))
        frame2 = cv2.resize(frame2, (new_width, h1))

    # Stitch Axis streams side-by-side
    merged_frame = cv2.hconcat([frame1, frame2])

    # Convert stitched layout to MediaPipe frame tracking requirements
    rgb_frame = cv2.cvtColor(merged_frame, cv2.COLOR_BGR2RGB)
    mp_input = mp_image.Image(image_format=mp_image.ImageFormat.SRGB, data=rgb_frame)

    # Process unified image canvas
    face_result = face_detector.detect(mp_input)
    pose_result = pose_landmarker.detect(mp_input)

    # Render overlays directly onto stitched canvas
    if face_result and getattr(face_result, 'detections', None):
        for detection in face_result.detections:
            draw_detection(merged_frame, detection, color=(0, 255, 255), thickness=2)

    if pose_result and getattr(pose_result, 'pose_landmarks', None):
        for landmarks in pose_result.pose_landmarks:
            draw_pose_landmarks(merged_frame, landmarks, color=(0, 255, 0), point_radius=3, thickness=2)

    # Calculate real-time analytic telemetry overlays
    overlay_text = []
    if face_result and getattr(face_result, 'detections', None):
        overlay_text.append(f"Faces: {len(face_result.detections)}")
    if pose_result and getattr(pose_result, 'pose_landmarks', None):
        overlay_text.append("Pose detected")

    if overlay_text:
        cv2.putText(merged_frame, ' | '.join(overlay_text), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    # Display continuous merged panorama canvas
    cv2.imshow('AXIS P4705 Panoramic MediaPipe Track', merged_frame)

    if cv2.waitKey(1) == ord('q'):
        break

# Clean up environment variables
cam1.stop()
cam2.stop()
cv2.destroyAllWindows()
