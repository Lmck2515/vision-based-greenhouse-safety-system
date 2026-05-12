import cv2
import numpy as np
import requests
import threading
import time
import os
import customtkinter as ctk
from PIL import Image as PILImage
from io import BytesIO
from ultralytics import YOLO
import speech_recognition as sr

# CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

BOT_TOKEN = "8316113986:AAGUwVtUQUapE1DHnj4XY06JIKaroRvzCro"
CHAT_ID = "2118826051"
POSE_MODEL_PATH = "yolov8n-pose.pt"
TOOL_MODEL_PATH = "/Users/liammckenna/Desktop/499code/best.pt"

class GreenhouseSafetySystem(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.geometry("1400x1050") 
        self.configure(fg_color="#1a1a1a")

        print("System: Loading AI Models...")
        self.pose_model = YOLO(POSE_MODEL_PATH)
        self.tool_model = YOLO(TOOL_MODEL_PATH)
        
        # Initialize cameras
        self.cap1 = cv2.VideoCapture(0)
        self.cap2 = cv2.VideoCapture(1)
        
        self.running = False
        self.latest_frame = None
        self.last_fall_alert_time = 0 
        self.lying_frames = 0
        self.standing_grace = 0 
        self.alert_active = False 
        self.last_update_id = None

        # Tool Tracker
        self.tracked_tools = {} 

        # UI LAYOUT 
        self.header = ctk.CTkLabel(self, text="GREENHOUSE SAFETY SYSTEM", 
                                   font=ctk.CTkFont(family="Inter", size=28, weight="bold"))
        self.header.pack(pady=(15, 10))

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20)
        self.main_container.grid_rowconfigure(0, weight=1) 
        self.main_container.grid_columnconfigure(0, weight=1)

        self.monitor_card = ctk.CTkFrame(self.main_container, fg_color="#2d2d2d", corner_radius=15)
        self.monitor_card.grid(row=0, column=0, sticky="nsew", pady=5)

        self.video_display = ctk.CTkLabel(self.monitor_card, text="Cameras Offline")
        self.video_display.pack(pady=10, padx=10, fill="both", expand=True)

        self.status_bar = ctk.CTkLabel(self.monitor_card, text="SYSTEM READY", 
                                       font=ctk.CTkFont(size=18, weight="bold"),
                                       fg_color="#3d3d3d", height=45, corner_radius=10,
                                       text_color="#ffffff", width=400)
        self.status_bar.pack(pady=(0, 15))

        self.controls_card = ctk.CTkFrame(self.main_container, fg_color="#262626", corner_radius=15, border_width=1, border_color="#333333")
        self.controls_card.grid(row=1, column=0, sticky="ew", pady=10)

        self.sos_btn = ctk.CTkButton(self.controls_card, text="🆘 TRIGGER EMERGENCY ASSISTANCE (SOS)", 
                                     command=self.manual_sos,
                                     fg_color="#ffffff", text_color="#e74c3c",
                                     hover_color="#f2f2f2",
                                     font=ctk.CTkFont(size=20, weight="bold"),
                                     height=55)
        self.sos_btn.pack(fill="x", pady=(10, 5), padx=15)

        self.btn_row = ctk.CTkFrame(self.controls_card, fg_color="transparent")
        self.btn_row.pack(fill="x", pady=(0, 10), padx=15)

        self.start_btn = ctk.CTkButton(self.btn_row, text="▶ START MONITORING", command=self.start_system,
                                       fg_color="#2ecc71", text_color="#000", font=ctk.CTkFont(weight="bold"), height=45)
        self.start_btn.pack(side="left", padx=(0, 5), expand=True, fill="x")

        self.stop_btn = ctk.CTkButton(self.btn_row, text="⏹ STOP SYSTEM", command=self.stop_system,
                                      fg_color="#e74c3c", font=ctk.CTkFont(weight="bold"), height=45)
        self.stop_btn.pack(side="right", padx=(5, 0), expand=True, fill="x")

        self.log_panel = ctk.CTkFrame(self, fg_color="#1e1e1e", height=180, corner_radius=0, border_width=1, border_color="#333")
        self.log_panel.pack(side="bottom", fill="x", pady=(10, 0))
        self.log_panel.pack_propagate(False)

        ctk.CTkLabel(self.log_panel, text="SYSTEM ACTIVITY CONSOLE", font=ctk.CTkFont(size=12, weight="bold"), text_color="#888").pack(pady=(5, 0))
        
        self.log_box = ctk.CTkTextbox(self.log_panel, fg_color="#000", font=ctk.CTkFont(family="Consolas", size=13), text_color="#00FF00")
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(5, 15))
        self.log_box.configure(state="disabled")

        threading.Thread(target=self.telegram_listener, daemon=True).start()
        threading.Thread(target=self.voice_listener, daemon=True).start()
        self.add_log("System initialized and ready.")

    def add_log(self, message):
        ts = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {message}\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def voice_listener(self):
        recognizer = sr.Recognizer()
        keywords = ["emergency", "help", "danger", "alert"]
        while True:
            if self.running:
                try:
                    with sr.Microphone() as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        audio = recognizer.listen(source, phrase_time_limit=3)
                        text = recognizer.recognize_google(audio).lower()
                        if any(word in text for word in keywords):
                            self.after(0, lambda t=text: self.add_log(f"Voice Command: '{t}'"))
                            self.after(0, self.manual_sos)
                except: pass
            time.sleep(0.2)

    def play_voice(self, text):
        def task(): os.system(f'say "{text}" &')
        threading.Thread(target=task, daemon=True).start()

    def send_tg_photo(self, frame, caption):
        def task():
            try:
                success, buffer = cv2.imencode(".jpg", frame)
                if success:
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", 
                                  data={"chat_id": CHAT_ID, "caption": caption}, 
                                  files={"photo": ("image.jpg", BytesIO(buffer), "image/jpeg")}, timeout=15)
                    self.after(0, lambda: self.add_log("Telegram alert sent."))
            except Exception as e:
                self.after(0, lambda: self.add_log(f"TG Error: {e}"))
        threading.Thread(target=task, daemon=True).start()

    def telegram_listener(self):
        while True:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
                params = {"timeout": 10, "offset": (self.last_update_id + 1) if self.last_update_id else None}
                resp = requests.get(url, params=params).json()
                if "result" in resp:
                    for update in resp["result"]:
                        self.last_update_id = update["update_id"]
                        if "message" in update and "text" in update["message"]:
                            txt = update["message"]["text"].lower()
                            if "/status" in txt:
                                status = "Running ✅" if self.running else "Idle ❌"
                                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                              data={"chat_id": CHAT_ID, "text": f"System Status: {status}"})
                            elif "/photo" in txt:
                                if self.latest_frame is not None:
                                    self.send_tg_photo(self.latest_frame.copy(), "📸 Live Snapshot Request")
            except: pass
            time.sleep(1)

    def manual_sos(self):
        self.alert_active = True
        self.status_bar.configure(text="🆘 EMERGENCY REQUESTED", fg_color="#f1c40f", text_color="#000")
        self.add_log("SOS Triggered (Manual/Voice)")
        self.play_voice("Emergency alert triggered.")
        if self.latest_frame is not None: 
            self.send_tg_photo(self.latest_frame.copy(), "🚨 SOS: Manual Emergency Triggered!")

    def start_system(self):
        self.running = True
        self.alert_active = False
        self.lying_frames = 0
        self.status_bar.configure(text="MONITORING ACTIVE", fg_color="#2ecc71", text_color="#000")
        self.play_voice("System started.")
        self.add_log("System Monitoring: Started")
        self.update_loop()

    def stop_system(self):
        self.running = False
        self.status_bar.configure(text="SYSTEM READY", fg_color="#3d3d3d", text_color="#fff")
        self.play_voice("System stopped.")
        self.add_log("System Monitoring: Stopped")

    def update_loop(self):
        if not self.running: return
        ret1, frame1 = self.cap1.read()
        ret2, frame2 = self.cap2.read()
        if not ret1 or not ret2: 
            self.after(10, self.update_loop)
            return

        f1 = cv2.resize(frame1, (640, 480))
        f2 = cv2.resize(frame2, (640, 480))
        any_person_lying = False
        processed_frames = []

        for cam_idx, frame in enumerate([f1, f2]):
            # 1. Pose Detection
            pose_res = self.pose_model(frame, conf=0.5, verbose=False)[0]
            annotated = pose_res.plot()

            # 2. Tool Detection (best.pt)
            tool_res = self.tool_model(frame, conf=0.4, verbose=False)[0]
            for t_box in tool_res.boxes:
                tx1, ty1, tx2, ty2 = t_box.xyxy[0].cpu().numpy()
                t_conf = float(t_box.conf[0])
                t_label = self.tool_model.names[int(t_box.cls[0])]
                
                cv2.rectangle(annotated, (int(tx1), int(ty1)), (int(tx2), int(ty2)), (255, 128, 0), 2)
                cv2.putText(annotated, f"TOOL: {t_label} {t_conf:.2f}", (int(tx1), int(ty1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 128, 0), 2)

                # Path Hazard Logic 
                t_center = ((tx1 + tx2) / 2, (ty1 + ty2) / 2)
                is_on_path = (t_center[0] > 640 * 0.7)

                if is_on_path:
                    tool_key = (cam_idx, t_label)
                    now = time.time()
                    if tool_key not in self.tracked_tools:
                        self.tracked_tools[tool_key] = {'start': now, 'pos': t_center, 'alerted': False}
                    else:
                        dist = np.linalg.norm(np.array(t_center) - np.array(self.tracked_tools[tool_key]['pos']))
                        if dist > 30:
                            self.tracked_tools[tool_key] = {'start': now, 'pos': t_center, 'alerted': False}
                        elif now - self.tracked_tools[tool_key]['start'] > 5 and not self.tracked_tools[tool_key]['alerted']:
                            self.play_voice(f"Be careful of the {t_label} on the path")
                            self.add_log(f"Hazard: {t_label} stationary on path.")
                            self.tracked_tools[tool_key]['alerted'] = True

            # 3. Fall Detection
            if len(pose_res.boxes) > 0:
                for i in range(len(pose_res.boxes)):
                    pts = pose_res.keypoints.data[i].cpu().numpy() 
                    box = pose_res.boxes.xyxy[i].cpu().numpy()
                    
                    if len(pts) >= 17: 
                        has_feet = pts[15][2] > 0.35 or pts[16][2] > 0.35
                        has_shoulders = pts[5][2] > 0.35 or pts[6][2] > 0.35
                        is_whole_body_visible = has_feet and has_shoulders

                        if is_whole_body_visible:
                            x1, y1, x2, y2 = box
                            box_h, box_w = (y2 - y1), (x2 - x1)
                            sh_y = (pts[5][1] + pts[6][1]) / 2   
                            hip_y = (pts[11][1] + pts[12][1]) / 2 
                            
                            is_sideways = box_w > (box_h * 0.95)
                            torso_pixel_h = abs(sh_y - hip_y)
                            torso_ratio = torso_pixel_h / (box_h + 1e-6)
                            is_torso_collapsed = torso_ratio < 0.24
                            is_not_standing_shape = box_h < (box_w * 2.8)

                            if is_sideways or (is_torso_collapsed and is_not_standing_shape):
                                any_person_lying = True
                                cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 4)
                        else:
                            x1, y1, x2, y2 = box
                            cv2.putText(annotated, "PARTIAL BODY - IGNORING", (int(x1), int(y1) - 5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            processed_frames.append(annotated)

        # Alert Logic
        if any_person_lying:
            self.lying_frames += 1
            self.standing_grace = 0 
        else:
            self.standing_grace += 1
            if self.standing_grace > 5:
                self.lying_frames = 0

        combined_annotated = np.hstack((processed_frames[0], processed_frames[1]))
        
        if self.lying_frames >= 10: 
            cv2.putText(combined_annotated, "FALL VERIFIED", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
            current_time = time.time()
            if current_time - self.last_fall_alert_time > 60:
                self.last_fall_alert_time = current_time 
                self.alert_active = True
                self.add_log("🚨 ALERT: Automated Fall Detected.")
                self.send_tg_photo(combined_annotated.copy(), "🚨 FALL DETECTED: Automated alert from system.")
                self.play_voice("Fall detected.")

        self.latest_frame = combined_annotated.copy()

        if self.status_bar.cget("text") != "🆘 EMERGENCY REQUESTED":
            if self.lying_frames >= 10:
                self.status_bar.configure(text="🚨 FALL DETECTED", fg_color="#e74c3c", text_color="#fff")
            elif self.lying_frames > 0:
                self.status_bar.configure(text=f"ANALYZING... ({self.lying_frames})", fg_color="#f39c12", text_color="#000")
            else:
                self.status_bar.configure(text="MONITORING ACTIVE", fg_color="#2ecc71", text_color="#000")

        img_display = PILImage.fromarray(cv2.cvtColor(combined_annotated, cv2.COLOR_BGR2RGB))
        ctk_img = ctk.CTkImage(light_image=img_display, dark_image=img_display, size=(1280, 480))
        self.video_display.configure(image=ctk_img, text="")
        self.after(10, self.update_loop)

if __name__ == "__main__":
    app = GreenhouseSafetySystem()
    app.mainloop()