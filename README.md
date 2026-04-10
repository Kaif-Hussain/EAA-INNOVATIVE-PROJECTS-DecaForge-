## 🏠 **SMART HOME CONTROLLER** 🚀  
### **Version 1.0**  |  **April 2026**  
**Gesture 🖐️  •  Voice 🎤  •  Temperature 🌡️  •  People Counter 👥  •  Air Quality 💨  •  Web Dashboard 💻**

---

## 📝 **1) PROJECT OVERVIEW**  
**Smart Home Controller** is a **real-time IoT system** that combines:  
✅ **Computer Vision** (gesture control)  
✅ **Voice Recognition** (speech commands)  
✅ **Sensor Automation** (temperature + air quality + door + people count)  
✅ **Live Web Dashboard** (instant updates)

It uses an **ESP32** to communicate with a **Python application**, powering automation + monitoring in one complete setup.

---

## ✨ **KEY FEATURES**  

### 🖐️ **Hand Gesture Control**  
➤ Control **LED brightness in real-time** using a webcam by **pinching/spreading** your thumb and index finger.

### 🗣️ **Voice Commands**  
➤ Control lights using commands like:  
**“light on”** • **“light 70”** • **“dim to fifty”**

### ❄️ **Automated Fan Speed (Temperature Based)**  
➤ A **DHT11 sensor** measures temperature and the **ESP32 auto-adjusts fan speed**.

### 👥 **People Counter**  
➤ **Two IR sensors** detect **entry/exit** and keep a **live occupancy count**.

### 🔒 **Security + Energy Saving**  
➤ A **Hall sensor** detects door open/close state.  
➤ A **relay** can automatically activate when someone is inside.

### 🍃 **Air Quality Monitoring**  
➤ An **MQ135 sensor** checks air quality and labels it as:  
✅ **GOOD** • ⚠️ **MODERATE** • ❌ **POOR**

### 🌐 **Real-Time Web Dashboard (SSE)**  
➤ Live updates using **Server-Sent Events (SSE)** → **no refresh needed**.

---

## 🛠️ **2) HARDWARE REQUIREMENTS**  

### 🔩 **Main Components**  
| **Component** | **Purpose** |
|---|---|
| **ESP32 Dev Board 🧠** | Main controller (WiFi, Dual-core, PWM, ADC, I2C) |
| **DHT11 🌡️** | Temperature + Humidity sensor |
| **MQ135 💨** | Gas / Air Quality sensor |
| **Hall Effect Sensor 🧲** | Door open/close detection |
| **IR Obstacle Sensor (x2) 🔦** | People entry/exit counting |
| **OLED Display (x2) 📺** | Two 0.96” SSD1306 displays |
| **N-MOSFET ⚡** | Fan motor switching (IRLZ44N / 2N7000) |
| **Relay Module 🔌** | Controls high-current load |

### 💻 **PC Requirements**  
🎥 **Webcam**: For gesture detection (MediaPipe)  
🎙️ **Microphone**: For voice commands (Google Speech API)  
🐍 **Python 3.9+**: Runs gesture + voice processing

---

## 📍 **3) WIRING & PIN CONNECTIONS**  

| **ESP32 Pin** | **Component** | **Connection Details** |
|---|---|---|
| **GPIO 18** | LED 💡 | PWM output via **220Ω resistor** |
| **GPIO 5** | Fan (MOSFET) 🌀 | PWM gate signal to MOSFET |
| **GPIO 4** | DHT11 🌡️ | Data pin + **10kΩ pull-up** |
| **GPIO 34** | MQ135 💨 | Analog input (ADC1) |
| **GPIO 2** | Hall Sensor 🧲 | Digital input for door state |
| **GPIO 16 / 15** | IR Sensors 📶 | IR1 (Entry) + IR2 (Exit) |
| **GPIO 17** | Relay ⚡ | Digital output for load control |
| **GPIO 21 / 22** | OLED 1 📟 | I2C Data/Clock (Sensor Display) |
| **GPIO 32 / 33** | OLED 2 📟 | I2C Data/Clock (People Display) |

### ⚠️ **IMPORTANT WARNING**  
❗ **Never connect a DC motor directly to ESP32 pins.**  
Use a **MOSFET circuit** + **1N4007 flyback diode** to prevent damage.

---

## 💾 **4) SOFTWARE INSTALLATION**  

### 🛠️ **Arduino Libraries (Install via Library Manager)**  
✅ **Adafruit SSD1306**  
✅ **Adafruit GFX**  
✅ **DHT sensor library (Adafruit)**

### 🐍 **Python Environment (Install Packages)**  
```bash
pip install opencv-python mediapipe pyserial speechrecognition pyaudio
```

---

## ⚙️ **5) HOW IT WORKS**  

### 📡 **Serial Protocol**  
**Baud Rate:** **9600**  

➡️ **ESP32 → Python** (every 2 seconds):  
Example: `T28.5,H62,A410,F128,D1,P3,R1`

⬅️ **Python → ESP32** (brightness command):  
Example: `B180\n` (70% brightness)

---

## 🧠 **CONTROL LOGIC**  

### 🖐️ **Gestures**  
➤ Calculates distance between **thumb tip** and **index tip**  
➤ Maps it to PWM range: **0 → 255**

### 🌀 **Fan Speed Rule**  
- **≤ 30°C** → Fan **OFF**  
- **≥ 40°C** → Fan **FULL (255)**

### 💨 **Air Quality Rule**  
- **< 800** → ✅ **GOOD**  
- **800 – 1500** → ⚠️ **MODERATE**  
- **> 1500** → ❌ **POOR**

---

## 🔍 **6) TROUBLESHOOTING**  

🚫 **Access Denied:** Close **Arduino Serial Monitor** before running Python.  
🌑 **OLED Not Working:** Ensure `Wire.begin(21,22)` and confirm I2C address **0x3C**.  
🔇 **Voice Not Working:** Google Speech API needs **active internet**.