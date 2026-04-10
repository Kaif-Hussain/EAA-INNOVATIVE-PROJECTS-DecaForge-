"""
=============================================================
  SMART HOME CONTROLLER — Python Final
=============================================================
  Matches: smart_home_FINAL.ino

  Serial format  ESP32 → Python:
    "T28.5,H62,A410,F128,D1,P3,R1"
     T=Temp  H=Humidity  A=Air  F=FanPWM
     D=Door(0/1)  P=PeopleCount  R=Relay(0/1)

  Serial command Python → ESP32:
    "B180\n"  → LED brightness 0-255

  Controls:
    GESTURE  → LED brightness (thumb-index pinch/spread)
    VOICE    → LED brightness ("light on/off/70/fifty")
    FAN      → Auto on ESP32 by temperature
    RELAY    → Auto on ESP32 (door open OR people inside)
    HUD      → Shows all sensor + people + door + relay data

  Press Q to quit.
=============================================================
  pip install opencv-python mediapipe pyserial
            speechrecognition pyaudio
=============================================================
"""

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

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────
FALLBACK_PORT = "COM3"
BAUD_RATE     = 9600

MODEL_PATH = "hand_landmarker.task"
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)

MIN_DIST = 0.03
MAX_DIST = 0.25

TEMP_MIN = 20.0
TEMP_MAX = 40.0

AIR_GOOD     = 800
AIR_MODERATE = 1500

WORD_TO_NUM = {
    "zero": 0,    "one": 1,    "two": 2,    "three": 3,   "four": 4,
    "five": 5,    "six": 6,    "seven": 7,  "eight": 8,   "nine": 9,
    "ten": 10,    "twenty": 20,"thirty": 30,"forty": 40,
    "fifty": 50,  "sixty": 60, "seventy": 70,"eighty": 80,
    "ninety": 90, "hundred": 100,
}

# ─────────────────────────────────────────────────────────────
#  SHARED STATE
# ─────────────────────────────────────────────────────────────
state = {
    "temp":     0.0,
    "humidity": 0.0,
    "air":      0,
    "fan_pwm":  0,
    "led_pwm":  0,
    "door":     0,    # 0=closed  1=open
    "people":   0,    # count
    "relay":    0,    # 0=off  1=on
}
state_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────
#  SERIAL — auto-detect ESP32
# ─────────────────────────────────────────────────────────────
def find_port() -> str:
    keywords = ["CP210", "CH340", "USB Serial", "UART", "Silicon Labs", "FTDI"]
    for p in serial.tools.list_ports.comports():
        if any(k in p.description for k in keywords):
            print(f"[Serial] Found → {p.device}  ({p.description})")
            return p.device
    print(f"[Serial] Auto-detect failed. Using fallback: {FALLBACK_PORT}")
    return FALLBACK_PORT

try:
    esp32 = serial.Serial(find_port(), baudrate=BAUD_RATE, timeout=1)
    time.sleep(2)
    esp32.reset_input_buffer()
    esp32.reset_output_buffer()
    print("[Serial] Connected.\n")
except serial.SerialException as e:
    print(f"[Serial] ERROR: {e}")
    raise SystemExit(1)

serial_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────
#  SERIAL READER THREAD
#  Parses: "T28.5,H62,A410,F128,D1,P3,R1"
# ─────────────────────────────────────────────────────────────
def serial_reader():
    while True:
        try:
            line = esp32.readline().decode(errors="ignore").strip()
            if not line:
                continue

            # Sensor data line — must have T and all fields
            if (line.startswith("T") and ",H" in line
                    and ",A" in line and ",F" in line
                    and ",D" in line and ",P" in line and ",R" in line):

                # Parse: T28.5,H62,A410,F128,D1,P3,R1
                t_s, rest = line.split(",H", 1)
                h_s, rest = rest.split(",A", 1)
                a_s, rest = rest.split(",F", 1)
                f_s, rest = rest.split(",D", 1)
                d_s, rest = rest.split(",P", 1)
                p_s, r_s  = rest.split(",R", 1)

                temp   = float(t_s[1:])
                hum    = float(h_s)
                air    = int(a_s)
                fan    = int(f_s)
                door   = int(d_s)
                people = int(p_s)
                relay  = int(r_s)

                with state_lock:
                    state["temp"]     = temp
                    state["humidity"] = hum
                    state["air"]      = air
                    state["fan_pwm"]  = fan
                    state["door"]     = door
                    state["people"]   = people
                    state["relay"]    = relay

                print(f"[ESP32] T={temp:.1f}°C H={hum:.0f}% "
                      f"Air={air}[{air_label(air)}] "
                      f"Fan={int(fan/255*100)}% "
                      f"Door={'OPEN' if door else 'SHUT'} "
                      f"Ppl={people} Relay={'ON' if relay else 'OFF'}")

            elif line.startswith("LED_OK:"):
                print(f"[ESP32] LED confirmed: {line.split(':')[1]} PWM")

            else:
                print(f"[ESP32] {line}")

        except (ValueError, AttributeError):
            pass
        except Exception:
            time.sleep(0.05)

threading.Thread(target=serial_reader, daemon=True).start()

# ─────────────────────────────────────────────────────────────
#  SEND LED BRIGHTNESS
# ─────────────────────────────────────────────────────────────
def send_brightness(value: int):
    value = max(0, min(255, int(value)))
    cmd   = f"B{value:03d}\n".encode()
    with serial_lock:
        esp32.write(cmd)
        esp32.flush()
    with state_lock:
        state["led_pwm"] = value
    print(f"[LED] Sent {cmd}  ({int(value/255*100)}%)")

def percent_to_pwm(pct) -> int:
    return int(max(0.0, min(100.0, float(pct))) / 100.0 * 255)

# ─────────────────────────────────────────────────────────────
#  AIR QUALITY
# ─────────────────────────────────────────────────────────────
def air_label(raw: int) -> str:
    if raw < AIR_GOOD:      return "GOOD"
    if raw < AIR_MODERATE:  return "MOD"
    return "POOR"

def air_color(raw: int):
    if raw < AIR_GOOD:      return (80, 220, 80)
    if raw < AIR_MODERATE:  return (0, 190, 255)
    return (50, 50, 240)

# ─────────────────────────────────────────────────────────────
#  VOICE
# ─────────────────────────────────────────────────────────────
def extract_percent(command: str):
    m = re.search(r'\b(\d{1,3})\b', command)
    if m:
        v = int(m.group(1))
        if 0 <= v <= 100:
            return v
    total, found = 0, False
    for word in command.split():
        if word in WORD_TO_NUM:
            total += WORD_TO_NUM[word]
            found  = True
    if found and 0 <= total <= 100:
        return total
    return None

def voice_worker():
    r = sr.Recognizer()
    print("[Voice] Ready. Say: 'light on/off', 'light 70', 'dim to fifty'\n")
    while True:
        try:
            with sr.Microphone() as src:
                r.adjust_for_ambient_noise(src, duration=0.4)
                audio = r.listen(src, timeout=4, phrase_time_limit=5)
            cmd = r.recognize_google(audio).lower()
            print(f"[Voice] '{cmd}'")

            if any(w in cmd for w in ["light off","turn off","switch off"]):
                send_brightness(0)
            elif any(w in cmd for w in ["light on","turn on","switch on"]):
                pct = extract_percent(cmd)
                send_brightness(percent_to_pwm(pct) if pct is not None else 255)
            elif any(w in cmd for w in ["brightness","set","light","dim","percent"]):
                pct = extract_percent(cmd)
                if pct is not None:
                    send_brightness(percent_to_pwm(pct))
                else:
                    print("[Voice] No percentage found.")
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            print(f"[Voice] API error: {e}")
        except Exception as e:
            print(f"[Voice] Error: {e}")

threading.Thread(target=voice_worker, daemon=True).start()

# ─────────────────────────────────────────────────────────────
#  MEDIAPIPE
# ─────────────────────────────────────────────────────────────
if not os.path.exists(MODEL_PATH):
    print("[MediaPipe] Downloading model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("[MediaPipe] Done.")

THUMB_TIP = 4
INDEX_TIP = 8

def get_distance(lm) -> float:
    dx = lm[THUMB_TIP].x - lm[INDEX_TIP].x
    dy = lm[THUMB_TIP].y - lm[INDEX_TIP].y
    return math.sqrt(dx * dx + dy * dy)

def dist_to_brightness(dist: float) -> int:
    clamped = max(MIN_DIST, min(MAX_DIST, dist))
    return int((clamped - MIN_DIST) / (MAX_DIST - MIN_DIST) * 255)

mp_options = mp.tasks.vision.HandLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,
    num_hands=1,
)

# ─────────────────────────────────────────────────────────────
#  HUD DRAWING
# ─────────────────────────────────────────────────────────────
FONT = cv2.FONT_HERSHEY_SIMPLEX

def dark_panel(frame, x, y, w, h, alpha=0.62):
    ov = frame.copy()
    cv2.rectangle(ov, (x, y), (x + w, y + h), (10, 10, 10), -1)
    cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0, frame)

def vbar(frame, x, y_top, bar_h, val255, color, label):
    bw     = 26
    fill_h = int((val255 / 255) * bar_h)
    cv2.rectangle(frame, (x, y_top), (x + bw, y_top + bar_h), (35,35,35), -1)
    cv2.rectangle(frame, (x, y_top), (x + bw, y_top + bar_h), (70,70,70),  1)
    if fill_h > 0:
        cv2.rectangle(frame,
                      (x, y_top + bar_h - fill_h),
                      (x + bw, y_top + bar_h), color, -1)
    pct = int(val255 / 255 * 100)
    cv2.putText(frame, f"{pct}%",
                (x - 2, y_top - 6), FONT, 0.40, color, 1, cv2.LINE_AA)
    cv2.putText(frame, label,
                (x, y_top + bar_h + 13), FONT, 0.38,
                (170,170,170), 1, cv2.LINE_AA)

def draw_status_panel(frame, s):
    """Top-left panel — all sensor + people + door + relay."""
    px, py, pw, ph = 10, 10, 300, 175
    dark_panel(frame, px, py, pw, ph)

    # Temperature colour
    temp = s["temp"]
    tc   = ((255,210,60) if temp <= TEMP_MIN else
            (0,210,255)  if temp <= 28 else
            (0,150,255)  if temp <= 34 else
            (40,60,255))

    fp  = int(s["fan_pwm"] / 255 * 100)
    fst = ("OFF" if fp==0 else "LOW" if fp<40 else "MED" if fp<75 else "HIGH")
    lp  = int(s["led_pwm"] / 255 * 100)
    alb = air_label(s["air"])
    alc = air_color(s["air"])

    # Door + relay colours
    door_col  = (0, 200, 255) if s["door"]  else (80, 80, 80)
    relay_col = (0, 255, 120) if s["relay"] else (60, 60, 200)
    door_txt  = "OPEN"        if s["door"]  else "SHUT"
    relay_txt = "ON"          if s["relay"] else "OFF"

    rows = [
        (f"Temp     : {temp:.1f} C",                      tc),
        (f"Humidity : {s['humidity']:.0f} %",              (150,150,150)),
        (f"Air MQ135: {s['air']}  [{alb}]",                alc),
        (f"Fan      : {fp:3d}%  [{fst}]  [AUTO]",          (0,200,255)),
        (f"LED      : {lp:3d}%  [gesture/voice]",           (0,255,160)),
        (f"Door     : {door_txt}",                          door_col),
        (f"People   : {s['people']}",                       (255,140,220)),
        (f"Relay    : {relay_txt}  [auto]",                 relay_col),
    ]
    for i, (txt, col) in enumerate(rows):
        cv2.putText(frame, txt, (px + 10, py + 24 + i * 20),
                    FONT, 0.50, col, 1, cv2.LINE_AA)

def draw_air_bar(frame, air_raw, fw, fh):
    pct = min(100, int(air_raw / 4095 * 100))
    col = air_color(air_raw)
    lbl = air_label(air_raw)
    bx  = fw // 2 - 70
    cv2.rectangle(frame, (bx, fh-38), (bx+140, fh-28), (35,35,35), -1)
    cv2.rectangle(frame, (bx, fh-38), (bx + int(pct*1.4), fh-28), col, -1)
    cv2.putText(frame, f"AIR: {lbl}  ({air_raw})",
                (bx-5, fh-43), FONT, 0.40, col, 1, cv2.LINE_AA)

def draw_door_relay_badge(frame, door, relay, fw):
    """Top-right corner badges for door and relay."""
    # Door badge
    d_txt = "DOOR: OPEN" if door  else "DOOR: SHUT"
    d_col = (0,200,255)  if door  else (70,70,70)
    cv2.rectangle(frame, (fw-160, 14), (fw-10, 36), (20,20,20), -1)
    cv2.rectangle(frame, (fw-160, 14), (fw-10, 36), d_col, 1)
    cv2.putText(frame, d_txt, (fw-153, 29), FONT, 0.48, d_col, 1, cv2.LINE_AA)

    # Relay badge
    r_txt = "RELAY: ON " if relay else "RELAY: OFF"
    r_col = (0,255,120)  if relay else (60,60,200)
    cv2.rectangle(frame, (fw-160, 42), (fw-10, 64), (20,20,20), -1)
    cv2.rectangle(frame, (fw-160, 42), (fw-10, 64), r_col, 1)
    cv2.putText(frame, r_txt, (fw-153, 57), FONT, 0.48, r_col, 1, cv2.LINE_AA)

def draw_people_counter(frame, people, fw, fh):
    """Bottom-right people count display."""
    col = (255,140,220)
    cv2.rectangle(frame, (fw-120, fh-70), (fw-10, fh-10), (18,18,18), -1)
    cv2.rectangle(frame, (fw-120, fh-70), (fw-10, fh-10), col, 1)
    cv2.putText(frame, "PEOPLE", (fw-113, fh-52), FONT, 0.40, col, 1, cv2.LINE_AA)
    cv2.putText(frame, str(people), (fw-100, fh-22), FONT, 1.20, col, 2, cv2.LINE_AA)

def draw_hint(frame, fh):
    cv2.putText(frame,
                "PINCH=dim  SPREAD=bright | Voice:'light on/off/N%' | Q=quit",
                (10, fh-10), FONT, 0.35, (100,100,100), 1, cv2.LINE_AA)

# ─────────────────────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────────────────────
cap             = cv2.VideoCapture(0)
last_brightness = -1
ts              = 0

print("=" * 60)
print("  Smart Home Controller — Final")
print("  Gesture+Voice → LED  |  Temp → Fan (auto)")
print("  Hall → Door state    |  IR × 2 → People counter")
print("  Relay auto (door OR people)  |  MQ135 → Air quality")
print("  Press Q to quit")
print("=" * 60 + "\n")

with mp.tasks.vision.HandLandmarker.create_from_options(mp_options) as detector:
    while True:
        ok, frame = cap.read()
        if not ok:
            print("[Camera] Frame read failed.")
            break

        # Mirror flip for natural gesture feel
        frame   = cv2.flip(frame, 1)
        fh, fw  = frame.shape[:2]

        # ── Gesture detection ──────────────────────────────
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = detector.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts
        )
        ts += 33

        if results.hand_landmarks:
            lm       = results.hand_landmarks[0]
            thumb_pt = (int(lm[THUMB_TIP].x * fw), int(lm[THUMB_TIP].y * fh))
            index_pt = (int(lm[INDEX_TIP].x  * fw), int(lm[INDEX_TIP].y  * fh))
            dist     = get_distance(lm)
            bright   = dist_to_brightness(dist)

            if abs(bright - last_brightness) > 3:
                send_brightness(bright)
                last_brightness = bright

            cv2.line(frame, thumb_pt, index_pt, (255,200,0), 2)
            cv2.circle(frame, thumb_pt, 10, (0,210,255), -1)
            cv2.circle(frame, index_pt, 10, (0,210,255), -1)

            mid = ((thumb_pt[0]+index_pt[0])//2,
                   (thumb_pt[1]+index_pt[1])//2)
            cv2.putText(frame, f"{dist:.2f}", mid, FONT, 0.42,
                        (255,255,255), 1, cv2.LINE_AA)

            cv2.putText(frame,
                        f"Gesture dist={dist:.3f}  LED={int(bright/255*100)}%",
                        (10, fh-28), FONT, 0.48, (255,200,0), 1, cv2.LINE_AA)

            # Right-side LED bar (above people counter)
            vbar(frame, fw-50, fh-240, 160, bright, (0,255,160), "LED")

        else:
            cv2.putText(frame, "Show hand to control LED",
                        (fw//2 - 150, fh//2),
                        FONT, 0.70, (70,70,70), 1, cv2.LINE_AA)

        # ── Snapshot shared state ──────────────────────────
        with state_lock:
            s = dict(state)

        # ── Left FAN bar ───────────────────────────────────
        vbar(frame, 10, fh-240, 160, s["fan_pwm"], (0,200,255), "FAN")

        # ── Overlays ───────────────────────────────────────
        draw_status_panel(frame, s)
        draw_door_relay_badge(frame, s["door"], s["relay"], fw)
        draw_people_counter(frame, s["people"], fw, fh)
        draw_air_bar(frame, s["air"], fw, fh)
        draw_hint(frame, fh)

        cv2.imshow("Smart Home Controller", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\n[Main] Quit.")
            break

# ── Cleanup ───────────────────────────────────────────────────
cap.release()
cv2.destroyAllWindows()
send_brightness(0)
esp32.close()
print("[Main] Shutdown complete.")
