import os
from deepface import DeepFace
import cv2
import numpy as np
import time
import threading
import datetime
from pathlib import Path
import audio

audio.init_audio(str(Path(__file__).resolve().parent.parent / 'sounds'))

# --- CONFIGURATION ---
rtsp_url_1 = "rtsp://root:defense@192.168.0.90:554/axis-media/media.amp?videocodec=h264&camera=1"
rtsp_url_2 = "rtsp://root:defense@192.168.0.91:554/axis-media/media.amp?videocodec=h264&camera=2"
Db = "/home/pi/defese/deepface pics-20260603T190838Z-3-001.zip"  # Path to your DeepFace database
model_name = "ArcFace"  
detector = "opencv"     
dist_m = "cosine"
dist_threshold = 0.4
skip_frames = 5
detect_width = 1280      
display = True
log_unknowns = True

class rtspstream:
    def __init__(self, url):
        self.url = url
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
        self.frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()
        print(f"Starting RTSP stream thread for {self.url}...")

    def _reader(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(1)
                continue
            with self.lock:
                self.frame = frame
            time.sleep(0.01)  # Prevent CPU pinning

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def reconnect(self):
        print(f"Attempting to reconnect to {self.url}...")
        self.cap.release()
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        print(f"Reconnection attempt finished for {self.url}.")

    def stop(self):
        self.running = False
        self.cap.release()


def identity(face_crop):
    """Returns name and distance, or 'Unknown, None'."""
    try:
        result = DeepFace.find(
            face_crop, 
            db_path=Db, 
            model_name=model_name, 
            detector_backend=detector, 
            distance_metric=dist_m,
            enforce_detection=False
        )
        if len(result) > 0 and not result[0].empty:
            # Get the top match distance from the first results dataframe
            df = result[0]
            distance = df[dist_m].values[0]
            if distance  30:
                stream1.reconnect()
                no_frame_1 = 0
            time.sleep(0.05)
            continue
        if frame2 is None:
            no_frame_2 += 1
            if no_frame_2 > 30:
                stream2.reconnect()
                no_frame_2 = 0
            time.sleep(0.05)
            continue
        
        no_frame_1 = 0
        no_frame_2 = 0
        frame_count += 1

        # Match dimensions before stitching (Normalize Cam 2 height to Cam 1 height)
        h1, w1 = frame1.shape[:2]
        h2, w2 = frame2.shape[:2]
        if h1 != h2:
            new_w2 = int(w2 * (h1 / h2))
            frame2 = cv2.resize(frame2, (new_w2, h1))
        
        # Merge streams side-by-side horizontally
        merged_frame = cv2.hconcat([frame1, frame2])
        display_frame = merged_frame.copy()

        # Update detections on target intervals
        if frame_count % skip_frames == 0:
            h_orig, w_orig = merged_frame.shape[:2]
            scale = detect_width / w_orig
            detect_height = int(h_orig * scale)
            small_frame = cv2.resize(merged_frame, (detect_width, detect_height))
            
            try:
                faces = DeepFace.extract_faces(
                    img_path=small_frame, 
                    detector_backend=detector, 
                    enforce_detection=False, 
                    align=True
                )
                lastresults = []
                
                for face_obj in faces:
                    conf = face_obj.get("confidence", 1.0)
                    if conf < 0.75:
                        continue
                        
                    r = face_obj["region"]
                    # Scale coordinates back up to native merged resolution
                    x = int(r["x"] / scale)
                    y = int(r["y"] / scale)
                    w = int(r["w"] / scale)
                    h = int(r["h"] / scale)
                    
                    x1, y1 = max(0, x), max(0, y)
                    x2, y2 = min(w_orig, x + w), min(h_orig, y + h)
                    
                    face_crop = merged_frame[y1:y2, x1:x2]
                    if face_crop.size == 0 or w < 60 or h < 60:
                        continue
                        
                    name, dist = identity(face_crop)
                    
                    if log_unknowns and name == "Unknown":
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        cv2.imwrite(f".logs/unknowns/unknown_{timestamp}.jpg", face_crop)
                        with open("unknown_log.txt", "a") as f:
                            f.write(f"{datetime.datetime.now()}: Unknown face detected\n")
                            audio.play("I SEE YOU Scary Voice Effect.ogg")
                            
                    lastresults.append((x1, y1, x2, y2, name, dist))
            except Exception as e:
                pass

        # Draw overlays across the merged space
        for (x1, y1, x2, y2, name, dist) in lastresults:
            color = (0, 0, 255) if name == "Unknown" else (0, 255, 0)
            label = f"{name}" if dist is None else f"{name} ({dist:.2f})"
            
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(display_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        if display:
            # Diagnostic telemetry overlay
            cv2.putText(display_frame, f"Frame: {frame_count}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            cv2.imshow("DeepFace - Merged Dual Live", display_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    stream1.stop()
    stream2.stop()
    if display:
        cv2.destroyAllWindows()
    print("Exiting...")

if __name__ == "__main__":
    main()
