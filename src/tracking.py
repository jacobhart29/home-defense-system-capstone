import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

cap = cv2.VideoCapture(0)


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


