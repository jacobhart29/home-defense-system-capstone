import os

from deepface import DeepFace
import cv2
import numpy as np
import time
import threading
import datetime


rtsp_url = url here bum
Db = "path to database"
model_name = "Archface" 
detectoor = "opencv"
dist_m = "cosine"
dist_threshold = 0.4
skip_frames = 5
detect_width = 960
display = True
log_unknowns = True


class rtspstream:
    def __init__(self, rtsp_url):
        self.cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer size to minimize latency
        self.frame= None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self.update, daemon=True)
        print("Starting RTSP stream thread...")

    def _reader(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to read frame from RTSP stream.")
                continue
            with self.lock:
                self.frame = frame
        else:
            time.sleep(0.1)  # Sleep briefly to avoid busy-waiting

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
            
    def reconnect(self):
        print("Attempting to reconnect to RTSP stream...")
        self.cap.release()
        self.cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        print("Reconnection attempt finished.")

    def stop(self):
        self.running = False
        self.cap.release()

#Recognition now
def identity(face_crop):
    #return name distance or unknown
    try:
        result = DeepFace.find(face_crop, db_path=Db, model_name=model_name, detector_backend=detector, distance_metric=dist_m)
        if len(result) > 0 and result[0].shape[0] > 0 and result[0]['cosine'][0] < dist_threshold:
            return result[0]['identity'][0]
    except Exception:
        return "Unknown,None"
def _draw(
    frame, 
    face_crop, 
    identity, 
    display=display, 
    log_unknowns=log_unknowns
):
    if display:
        cv2.putText(frame, identity, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Face Recognition", frame)
        cv2.waitKey(1)
    if log_unknowns and identity == "Unknown,None":
        with open("unknown_log.txt", "a") as f:
            f.write(f"{datetime.datetime.now()}: Unknown face detected\n")
def main():

    os.makedirs(".logs/unkowns", exist_ok=True)


    stream = rtspstream(rtsp_url)
    frame_count = 0
    time.sleep(2) 
    lastresults = []
    no_frame_count = 0
    while True:
        frame = stream.read()
        if frame is None:
            no_frame_count += 1
            if no_frame_count > 10:  # If we haven't received a frame for a while, try reconnecting
                stream.reconnect()
                no_frame_count = 0
            continue
        no_frame_count = 0
        frame_count += 1
        display_frame = frame.copy()
        if frame_count % skip_frames == 0:
            h_orig, w_orig = frame.shape[:2]
            scalle = detect_width / w_orig
            detect_height = int(h_orig * scalle)
            sMALL_frame = cv2.resize(frame, (detect_width, detect_height))
            try:
                faces = DeepFace.extract_faces(img_path=sMALL_frame, detector_backend=detector, enforce_detection=False, align=True)
                lastresults = []
                for face_obj in faces:
                    conf = face_obj.get("confidence", 1.0)
                    if conf < 0.75:  # Filter out low-confidence detections
                        continue
                    r = face_obj["region"]
                    x = int(r["x"] / scalle)
                    y = int(r["y"] / scalle)
                    w = int(r["w"] / scalle)
                    h = int(r["h"] / scalle)

                    x1 = max(0, x); y1 = max(0, y)
                    x2 = min(w_orig, x + w); y2 = min(h_orig, y + h)
                    
                    if face_crop.size == 0 or w< 60 or h < 60: 
                        continue
                    name, dist = identity(face_crop)

                    if LOG_UNKNOWN and name == "Unknown,None":
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        cv2.imwrite(f".logs/unkowns/unknown_{timestamp}.jpg", face_crop)
                    
                    lastresults.append((x, y, w, h, name, dist))

            except Exception as e:
                pass
        for (x, y, w, h, name, dist) in lastresults:
            _draw(display_frame, face_crop, name, display=display, log_unknowns=log_unknowns)

            cv2.putText(display_frame, {frame_count}, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            cv2.imshow("Face Recognition", display_frame)

            if DISPLAY:
                cv2.imshow("DeepFace - Live", display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        stream.stop()
        if DISPLAY:
            cv2.destroyAllWindows()
            print("Exiting...")
