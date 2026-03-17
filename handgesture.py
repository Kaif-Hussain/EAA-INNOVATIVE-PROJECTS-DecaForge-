import cv2
import mediapipe as mp
import urllib.request
import os
import serial
import serial.tools.list_ports

# --- Find ESP32 Port Automatically ---
def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if any(k in p.description for k in ["CP210", "CH340", "USB Serial", "UART"]):
            return p.device
    return None

ESP32_PORT = find_esp32_port()
if ESP32_PORT is None:
    ESP32_PORT = "COM3"  # <-- change this manually if auto-detect fails
    print(f"ESP32 not found automatically. Trying {ESP32_PORT}")
else:
    print(f"ESP32 found on {ESP32_PORT}")

esp32 = serial.Serial(ESP32_PORT, baudrate=9600, timeout=1)

# --- Send Command to ESP32 ---
def set_brightness(level: int):
    if level < 50:
        esp32.write(b"DIM\n")
        print("Sent: DIM")
    else:
        esp32.write(b"BRIGHT\n")
        print("Sent: BRIGHT")

# --- Gesture Detection ---
def count_extended_fingers(hand_landmarks):
    tips = [4, 8, 12, 16, 20]
    pips = [3, 6, 10, 14, 18]
    extended = 0

    # Thumb
    if hand_landmarks[tips[0]].x < hand_landmarks[pips[0]].x:
        extended += 1

    # Other 4 fingers
    for i in range(1, 5):
        if hand_landmarks[tips[i]].y < hand_landmarks[pips[i]].y:
            extended += 1

    return extended

def classify_gesture(hand_landmarks):
    fingers_up = count_extended_fingers(hand_landmarks)
    if fingers_up <= 1:
        return "fist"
    elif fingers_up >= 4:
        return "palm"
    return "other"

# --- Model Setup ---
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"

if not os.path.exists(MODEL_PATH):
    print("Downloading model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Download complete.")

# --- MediaPipe Setup ---
BaseOptions           = mp.tasks.BaseOptions
HandLandmarker        = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
VisionRunningMode     = mp.tasks.vision.RunningMode

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]

def draw_hand_landmarks(frame, hand_landmarks, width, height):
    for start_idx, end_idx in HAND_CONNECTIONS:
        s = hand_landmarks[start_idx]
        e = hand_landmarks[end_idx]
        cv2.line(frame,
                 (int(s.x * width), int(s.y * height)),
                 (int(e.x * width), int(e.y * height)),
                 (0, 255, 0), 2)
    for lm in hand_landmarks:
        cv2.circle(frame, (int(lm.x * width), int(lm.y * height)), 5, (0, 0, 255), -1)

# --- Brightness Settings ---
BRIGHTNESS_DIM    = 20
BRIGHTNESS_BRIGHT = 100

last_gesture = None

# --- Main Loop ---
options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=1,
)

cap = cv2.VideoCapture(0)
print("Press 'q' to quit.")
print("Fist  --> LED dims")
print("Palm  --> LED brightens")

with HandLandmarker.create_from_options(options) as landmarker:
    frame_timestamp_ms = 0

    while True:
        success, frame = cap.read()
        if not success:
            print("Failed to access camera.")
            break

        img_rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        results  = landmarker.detect_for_video(mp_image, frame_timestamp_ms)
        frame_timestamp_ms += 33

        h, w, _ = frame.shape
        gesture  = "none"

        if results.hand_landmarks:
            for hand_landmarks in results.hand_landmarks:
                draw_hand_landmarks(frame, hand_landmarks, w, h)
                gesture = classify_gesture(hand_landmarks)

        # Only send to ESP32 when gesture changes
        if gesture != last_gesture:
            if gesture == "fist":
                set_brightness(BRIGHTNESS_DIM)
            elif gesture == "palm":
                set_brightness(BRIGHTNESS_BRIGHT)
            last_gesture = gesture

        # Show gesture on screen
        color = (0, 100, 255) if gesture == "fist" else (0, 255, 100) if gesture == "palm" else (200, 200, 200)
        cv2.putText(frame, f"Gesture: {gesture.upper()}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 2)

        cv2.imshow("Gesture LED Control", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
esp32.close()