import cv2
import numpy as np
import json
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

cap = cv2.VideoCapture(0)

with open('../config/config.json', 'r', encoding='utf-8') as config:
    face_data = config["file_paths"]["face_tracking"]
    body_data = config["file_paths"]["body_tracking"]

if not cap.isOpened():
    print("Cannot open camera")
    exit()

while True: 
    (ret, frame) = cap.read()
    

    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break

    cv2.imshow('frame', frame)

    if cv2.waitKey(1) == ord('q'):
        break


