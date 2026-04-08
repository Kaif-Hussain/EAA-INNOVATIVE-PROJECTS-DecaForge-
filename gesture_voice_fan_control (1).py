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
import time

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
FALLBACK_PORT = "COM3"
MODEL_PATH    = "hand_landmarker.task"
MODEL_URL     = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)

MIN_DIST = 0.03
MAX_DIST = 0.25

TEMP_MIN = 20.0   # °C — fan threshold
TEMP_MAX = 40.0   # °C — fan at 100%

WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}

# ─────────────────────────────────────────────
# SHARED STATE  (thread-safe primitives)
# ─────────────────────────────────────────────
current_temp   = 0.0
current_fan_pwm = 0
state_lock     = threading.Lock()

# ─────────────────────────────────────────────
# SERIAL
# ─────────────────────────────────────────────
def find_port():
    for p in serial.tools.list_ports.comports():
        if any(k in p.description for k in
               ["CP210", "CH340", "USB Serial", "UART", "Silicon Labs", "FTDI"]):
            return p.device
    return FALLBACK_PORT

esp32       = serial.Serial(find_port(), baudrate=9600, timeout=1)
serial_lock = threading.Lock()

# ─────────────────────────────────────────────
# SERIAL READER THREAD  — parses "T25.3,F128" lines from ESP32
# ─────────────────────────────────────────────
def serial_reader():
    global current_temp, current_fan_pwm
    while True:
        try:
            line = esp32.readline().decode(errors="ignore").strip()
            if line.startswith("T") and ",F" in line:
                # Format: T25.3,F128
                t_part, f_part = line.split(",F")
                temp = float(t_part[1:])
                fan  = int(f_part)
                with state_lock:
                    current_temp    = temp
                    current_fan_pwm = fan
                print(f"[Sensor] Temp: {temp:.1f}°C  Fan PWM: {fan} ({int(fan/255*100)}%)")
        except Exception:
            time.sleep(0.1)

threading.Thread(target=serial_reader, daemon=True).start()

# ─────────────────────────────────────────────
# SEND BRIGHTNESS
# ─────────────────────────────────────────────
def send_brightness(value: int):
    value = max(0, min(255, value))
    cmd = f"B{value:03d}\n".encode()
    with serial_lock:
        esp32.write(cmd)
    print(f"[LED] Brightness: {value} ({int(value / 255 * 100)}%)")

def percent_to_pwm(percent: float) -> int:
    return int(max(0, min(100, percent)) / 100 * 255)

# ─────────────────────────────────────────────
# VOICE HELPERS
# ─────────────────────────────────────────────
def extract_percent(command: str):
    match = re.search(r'\b(\d{1,3})\b', command)
    if match:
        val = int(match.group(1))
        if 0 <= val <= 100:
            return val
    words = command.split()
    total, found = 0, False
    for word in words:
        if word in WORD_TO_NUM:
            total += WORD_TO_NUM[word]
            found = True
    if found and 0 <= total <= 100:
        return total
    return None

# ─────────────────────────────────────────────
# VOICE THREAD
# ─────────────────────────────────────────────
def voice_worker():
    r = sr.Recognizer()
    print("\n[Voice] Ready.")
    print("  'light on/off'         -> LED full / off")
    print("  'light 70'             -> LED 70%")
    print("  'set brightness fifty' -> LED 50%\n")

    while True:
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=3)
            command = r.recognize_google(audio).lower()
            print(f"[Voice] Heard: {command}")

            if "light off" in command or "turn off" in command:
                send_brightness(0)
            elif "light on" in command or "turn on" in command:
                pct = extract_percent(command)
                send_brightness(percent_to_pwm(pct) if pct is not None else 255)
            elif any(w in command for w in ["brightness", "set", "light", "dim"]):
                pct = extract_percent(command)
                if pct is not None:
                    send_brightness(percent_to_pwm(pct))
                else:
                    print("[Voice] No percentage found.")
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"[Voice] Error: {e}")

threading.Thread(target=voice_worker, daemon=True).start()

# ─────────────────────────────────────────────
# MEDIAPIPE SETUP
# ─────────────────────────────────────────────
if not os.path.exists(MODEL_PATH):
    print("Downloading MediaPipe model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

THUMB_TIP = 4
INDEX_TIP = 8

def get_distance(lm):
    dx = lm[THUMB_TIP].x - lm[INDEX_TIP].x
    dy = lm[THUMB_TIP].y - lm[INDEX_TIP].y
    return math.sqrt(dx * dx + dy * dy)

def dist_to_brightness(dist: float) -> int:
    clamped = max(MIN_DIST, min(MAX_DIST, dist))
    ratio   = (clamped - MIN_DIST) / (MAX_DIST - MIN_DIST)
    return int(ratio * 255)

options = mp.tasks.vision.HandLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,
    num_hands=1,
)

# ─────────────────────────────────────────────
# DRAWING HELPERS
# ─────────────────────────────────────────────
def draw_brightness_bar(frame, brightness, x_right, bottom):
    bar_h = int((brightness / 255) * 180)
    cv2.rectangle(frame, (x_right - 50, bottom - 200),
                  (x_right - 20, bottom - 20), (40, 40, 40), -1)
    cv2.rectangle(frame, (x_right - 50, bottom - 20 - bar_h),
                  (x_right - 20, bottom - 20), (0, 255, 180), -1)
    cv2.putText(frame, f"{int(brightness / 255 * 100)}%",
                (x_right - 62, bottom - 208),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 180), 2)
    cv2.putText(frame, "LED", (x_right - 50, bottom - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)


def draw_fan_bar(frame, fan_pwm, temp, x_left, bottom):
    bar_h = int((fan_pwm / 255) * 180)
    cv2.rectangle(frame, (x_left, bottom - 200),
                  (x_left + 30, bottom - 20), (40, 40, 40), -1)
    # colour shifts red as temp rises
    green = max(0, 255 - int((fan_pwm / 255) * 255))
    cv2.rectangle(frame, (x_left, bottom - 20 - bar_h),
                  (x_left + 30, bottom - 20), (0, green, 255), -1)
    cv2.putText(frame, f"{int(fan_pwm / 255 * 100)}%",
                (x_left - 4, bottom - 208),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2)
    cv2.putText(frame, "FAN", (x_left, bottom - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)


def draw_temp_box(frame, temp, fan_pwm):
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (260, 100), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    temp_color = (0, 200, 255) if temp <= TEMP_MIN else (
        (0, 165, 255) if temp <= 30 else (0, 80, 255))
    cv2.putText(frame, f"Temp : {temp:.1f} C",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.75, temp_color, 2)
    cv2.putText(frame, f"Fan  : {int(fan_pwm / 255 * 100)}%  [auto]",
                (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 180, 180), 1)


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────
cap            = cv2.VideoCapture(0)
last_brightness = -1
ts             = 0

print("\n[Gesture] Pinch → dim | Spread → bright | Q → quit\n")

with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        h, w, _ = frame.shape

        # ── Gesture detection ──────────────────
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = detector.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts
        )
        ts += 33

        if results.hand_landmarks:
            lm    = results.hand_landmarks[0]
            thumb = (int(lm[THUMB_TIP].x * w), int(lm[THUMB_TIP].y * h))
            index = (int(lm[INDEX_TIP].x * w), int(lm[INDEX_TIP].y * h))

            cv2.line(frame, thumb, index, (255, 200, 0), 2)
            cv2.circle(frame, thumb, 8, (0, 200, 255), -1)
            cv2.circle(frame, index, 8, (0, 200, 255), -1)

            dist       = get_distance(lm)
            brightness = dist_to_brightness(dist)

            if abs(brightness - last_brightness) > 5:
                send_brightness(brightness)
                last_brightness = brightness

            cv2.putText(frame, f"Dist: {dist:.2f}", (20, 115),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)

            draw_brightness_bar(frame, brightness, w, h)
        else:
            cv2.putText(frame, "No hand detected", (20, 115),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (100, 100, 100), 2)

        # ── Read shared sensor state ───────────
        with state_lock:
            temp    = current_temp
            fan_pwm = current_fan_pwm

        # ── Overlay: temperature + fan bar ─────
        draw_temp_box(frame, temp, fan_pwm)
        draw_fan_bar(frame, fan_pwm, temp, 20, h)

        cv2.imshow("Gesture + Voice LED  |  Temp Fan Control", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
esp32.close()
