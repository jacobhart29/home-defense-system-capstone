import cv2
import numpy as np
import json
import mediapipe.tasks as tasks
from mediapipe.tasks.python.vision.core import image as mp_image
from pathlib import Path

cap = cv2.VideoCapture(0)

config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
with config_path.open('r', encoding='utf-8') as config_file:
    config = json.load(config_file)
    face_data = config["file_paths"]["face_tracking"]
    body_data = config["file_paths"]["body_tracking"]

def draw_detection(frame, detection, color=(0, 255, 0), thickness=2):
    bbox = detection.bounding_box
    start = (int(bbox.origin_x), int(bbox.origin_y))
    end = (int(bbox.origin_x + bbox.width), int(bbox.origin_y + bbox.height))
    cv2.rectangle(frame, start, end, color, thickness)
    keypoints = getattr(detection, 'keypoints', None)
    if keypoints:
        for kp in keypoints:
            if kp.x is None or kp.y is None:
                continue
            x = int(np.clip(kp.x, 0.0, 1.0) * frame.shape[1])
            y = int(np.clip(kp.y, 0.0, 1.0) * frame.shape[0])
            cv2.circle(frame, (x, y), 3, color, -1)


def draw_pose_landmarks(frame, landmarks, color=(0, 255, 0), point_radius=3, thickness=2):
    height, width = frame.shape[:2]
    for landmark in landmarks:
        if landmark.x is None or landmark.y is None:
            continue
        x = int(np.clip(landmark.x, 0.0, 1.0) * width)
        y = int(np.clip(landmark.y, 0.0, 1.0) * height)
        cv2.circle(frame, (x, y), point_radius, color, -1)

    for connection in vision.PoseLandmarksConnections.POSE_LANDMARKS:
        start = landmarks[connection.start]
        end = landmarks[connection.end]
        if start.x is None or start.y is None or end.x is None or end.y is None:
            continue
        x1 = int(np.clip(start.x, 0.0, 1.0) * width)
        y1 = int(np.clip(start.y, 0.0, 1.0) * height)
        x2 = int(np.clip(end.x, 0.0, 1.0) * width)
        y2 = int(np.clip(end.y, 0.0, 1.0) * height)
        cv2.line(frame, (x1, y1), (x2, y2), color, thickness)

config_dir = config_path.parent
face_model_path = Path(face_data)
body_model_path = Path(body_data)
if not face_model_path.is_absolute():
    face_model_path = (config_dir / face_model_path).resolve()
if not body_model_path.is_absolute():
    body_model_path = (config_dir / body_model_path).resolve()

if not face_model_path.exists():
    raise FileNotFoundError(f"Face model not found: {face_model_path}")
if not body_model_path.exists():
    raise FileNotFoundError(f"Body model not found: {body_model_path}")

vision = tasks.vision
face_detector = vision.FaceDetector.create_from_model_path(str(face_model_path))
pose_landmarker = vision.PoseLandmarker.create_from_model_path(str(body_model_path))

if not cap.isOpened():
    print("Cannot open camera")
    exit()

while True: 
    (ret, frame) = cap.read()

    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_input = mp_image.Image(image_format=mp_image.ImageFormat.SRGB, data=rgb_frame)

    face_result = face_detector.detect(mp_input)
    pose_result = pose_landmarker.detect(mp_input)

    if face_result and getattr(face_result, 'detections', None):
        for detection in face_result.detections:
            draw_detection(frame, detection, color=(0, 255, 255), thickness=2)

    if pose_result and getattr(pose_result, 'pose_landmarks', None):
        for landmarks in pose_result.pose_landmarks:
            draw_pose_landmarks(frame, landmarks, color=(0, 255, 0), point_radius=3, thickness=2)

    overlay_text = []
    if face_result and getattr(face_result, 'detections', None):
        overlay_text.append(f"Faces: {len(face_result.detections)}")
    if pose_result and getattr(pose_result, 'pose_landmarks', None):
        overlay_text.append("Pose detected")

    if overlay_text:
        cv2.putText(frame, ' | '.join(overlay_text), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow('frame', frame)

    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()


