import cv2
import mediapipe as mp
import urllib.request
import os
import math
import re
import serial
import serial.tools.list_ports
import speech_recognition as sr
import threading

# --- Config ---
FALLBACK_PORT = "COM8"
MODEL_PATH = "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"

MIN_DIST = 0.03
MAX_DIST = 0.25

# Map spoken words to numbers
WORD_TO_NUM = {
    "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,
    "six":6,"seven":7,"eight":8,"nine":9,"ten":10,
    "twenty":20,"thirty":30,"forty":40,"fifty":50,
    "sixty":60,"seventy":70,"eighty":80,"ninety":90,"hundred":100
}

# --- Auto-detect port ---
def find_port():
    for p in serial.tools.list_ports.comports():
        if any(k in p.description for k in ["CP210", "CH340", "USB Serial", "UART", "Silicon Labs", "FTDI"]):
            return p.device
    return FALLBACK_PORT

esp32 = serial.Serial(find_port(), baudrate=9600, timeout=1)
serial_lock = threading.Lock()

# --- Send brightness (0-255) to ESP32 ---
def send_brightness(value):
    value = max(0, min(255, value))
    cmd = f"B{value:03d}".encode()
    with serial_lock:
        esp32.write(cmd)
    print(f"Brightness: {value} ({int(value/255*100)}%)")

def percent_to_pwm(percent):
    """Convert 0-100% to 0-255 PWM."""
    return int(max(0, min(100, percent)) / 100 * 255)

# --- Extract percentage from voice command ---
def extract_percent(command):
    """
    Tries to find a number in the command.
    Handles digits ('set light 75') and words ('set light seventy five').
    Returns 0-100 int or None if not found.
    """
    # 1. Try plain digits first e.g. "light 75" or "brightness 50 percent"
    match = re.search(r'\b(\d{1,3})\b', command)
    if match:
        val = int(match.group(1))
        if 0 <= val <= 100:
            return val

    # 2. Try spoken words e.g. "seventy five", "fifty"
    words = command.split()
    total = 0
    found = False
    for word in words:
        if word in WORD_TO_NUM:
            total += WORD_TO_NUM[word]
            found = True
    if found and 0 <= total <= 100:
        return total

    return None

# --- Download model if missing ---
if not os.path.exists(MODEL_PATH):
    print("Downloading model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

# ============================================================
# VOICE THREAD
# ============================================================
def voice_worker():
    r = sr.Recognizer()
    print("Voice ready.")
    print("  Say 'light on'        -> full brightness")
    print("  Say 'light off'       -> off")
    print("  Say 'light 50'        -> 50% brightness")
    print("  Say 'light seventy'   -> 70% brightness")

    while True:
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=3)
            command = r.recognize_google(audio).lower()
            print("Voice:", command)

            if "light off" in command or "turn off" in command:
                send_brightness(0)

            elif "light on" in command or "turn on" in command:
                # Check if a number follows e.g. "light on 80"
                percent = extract_percent(command)
                if percent is not None:
                    send_brightness(percent_to_pwm(percent))
                else:
                    send_brightness(255)  # no number = full brightness

            elif any(w in command for w in ["brightness", "set", "light", "dim"]):
                # e.g. "set brightness 40" / "dim to fifty"
                percent = extract_percent(command)
                if percent is not None:
                    send_brightness(percent_to_pwm(percent))
                else:
                    print("No percentage found in command.")

        except sr.UnknownValueError:
            pass
        except Exception as e:
            print("Voice error:", e)

threading.Thread(target=voice_worker, daemon=True).start()

# ============================================================
# GESTURE - thumb-index distance controls brightness
# ============================================================
THUMB_TIP = 4
INDEX_TIP = 8

def get_distance(lm):
    dx = lm[THUMB_TIP].x - lm[INDEX_TIP].x
    dy = lm[THUMB_TIP].y - lm[INDEX_TIP].y
    return math.sqrt(dx*dx + dy*dy)

def dist_to_brightness(dist):
    clamped = max(MIN_DIST, min(MAX_DIST, dist))
    ratio = (clamped - MIN_DIST) / (MAX_DIST - MIN_DIST)
    return int(ratio * 255)

# --- MediaPipe setup ---
options = mp.tasks.vision.HandLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,
    num_hands=1,
)

cap = cv2.VideoCapture(0)
last_brightness = -1
ts = 0

print("\nPinch -> dim  |  Spread thumb & index -> bright  |  Q -> quit\n")

with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        h, w, _ = frame.shape
        results = detector.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB,
                     data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), ts
        )
        ts += 33

        if results.hand_landmarks:
            lm = results.hand_landmarks[0]

            thumb = (int(lm[THUMB_TIP].x * w), int(lm[THUMB_TIP].y * h))
            index = (int(lm[INDEX_TIP].x * w), int(lm[INDEX_TIP].y * h))

            cv2.line(frame, thumb, index, (255, 200, 0), 2)
            cv2.circle(frame, thumb, 8, (0, 200, 255), -1)
            cv2.circle(frame, index, 8, (0, 200, 255), -1)

            dist = get_distance(lm)
            brightness = dist_to_brightness(dist)

            if abs(brightness - last_brightness) > 5:
                send_brightness(brightness)
                last_brightness = brightness

            # Brightness bar
            bar_height = int((brightness / 255) * 200)
            cv2.rectangle(frame, (w - 50, h - 220), (w - 20, h - 20), (50, 50, 50), -1)
            cv2.rectangle(frame, (w - 50, h - 20 - bar_height), (w - 20, h - 20), (0, 255, 180), -1)
            cv2.putText(frame, f"{int(brightness/255*100)}%", (w - 60, h - 230),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 180), 2)

            cv2.putText(frame, f"Dist: {dist:.2f}", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2)

        else:
            cv2.putText(frame, "No hand detected", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)

        cv2.imshow("Gesture + Voice LED Control", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
esp32.close()