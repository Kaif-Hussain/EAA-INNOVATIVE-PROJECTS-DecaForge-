🏠 Smart Home Controller 🚀
​Version 1.0 | April 2026
Gesture 🖐️ · Voice 🎤 · Temperature 🌡️ · People Counter 👥 · Air Quality 💨 · Web Dashboard 💻  
​1. Project Overview 📝
​The Smart Home Controller is a real-time IoT system integrating computer vision, voice recognition, sensor automation, and a live web dashboard. It utilizes an ESP32 microcontroller communicating with a Python 🐍 application on a PC. 
 <p align="center">
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" alt="python" width="100" height="100"/>
</p>

​Key Features ✨
​Hand Gesture Control 🖐️: Adjust LED brightness in real time by pinching or spreading your thumb and index finger via webcam.  
​Voice Commands 🗣️: Control lights using phrases like "light on," "light 70," or "dim to fifty".  
​Automated Fan Speed ❄️: A DHT11 sensor monitors temperature; the ESP32 automatically calculates fan speed.  
​People Counter 👥: Dual IR sensors detect entry and exit to maintain a live room occupancy count.  
​Security & Energy Savings 🔒: A magnetic Hall sensor detects door states, and a relay automatically activates if someone is inside.  
​Air Quality Monitoring 🍃: An MQ135 sensor tracks air quality (categorized as GOOD, MODERATE, or POOR).  
​Real-Time Dashboard 🌐: A web-based dashboard using Server-Sent Events (SSE) provides instant updates without page refreshes.  
​2. Hardware Requirements 🛠️
​Main Components
Component Purpose
ESP32 Dev Board 🧠 Main microcontroller (WiFi, Dual-core, PWM, ADC, I2C)
DHT11 🌡️ Temperature and Humidity sensor
MQ135 💨 Gas/Air Quality sensor
Hall Effect Sensor 🧲 Door open/close detection
IR Obstacle Sensor (x2) 🔦 Infrared beam break for people counting
OLED Display (x2) 📺 Two 0.96" SSD1306 displays for data visualization
N-MOSFET ⚡ Switches fan motor (IRLZ44N or 2N7000)
Relay Module 🔌 Controls high-current 
PC Requirements 💻
​Webcam 📷: For hand gesture detection via MediaPipe AI.  
​Microphone 🎙️: For voice commands via Google Speech API.  
​Python 3.9+ 🐍: To run the gesture and voice processing application.  
3. Wiring & Pin Connections 📍
ESP32 Pin Component Connection Details
GPIO 18 LED 💡 PWM output via 220Ω resistor
GPIO 5 Fan (MOSFET) 🌀 PWM gate signal to MOSFET
GPIO 4 DHT11 🌡️ Data pin with 10kΩ pull-up
GPIO 34 MQ135 💨 Analog input (ADC1)
GPIO 2 Hall Sensor 🧲 Digital input for door state
GPIO 16/15 IR Sensors 📶 IR1 (Entry) and IR2 (Exit)
GPIO 17 Relay ⚡ Digital output for load control
GPIO 21/22 OLED 1 📟 I2C Data/Clock (Sensor Display)
GPIO 32/33 OLED 2 📟 I2C Data/Clock (People Display)
​⚠️ Warning: Never connect a DC motor directly to ESP32 pins. Use the MOSFET circuit with a 1N4007 flyback diode to prevent chip damage.  
​4. Software Installation 💾
​Arduino Libraries 🛠️
​Install these via the Arduino Library Manager:  
​Adafruit SSD1306 & Adafruit GFX  
​DHT sensor library (Adafruit)  
​Python Environment 
​Install necessary packages using:  
pip install opencv-python mediapipe pyserial speechrecognition pyaudio
​5. How It Works ⚙️
​Serial Protocol 📡
​The ESP32 and Python app communicate at 9600 baud.  
​ESP32 → Python 🐍: Sends a string every 2 seconds (e.g., T28.5,H62,A410,F128,D1,P3,R1).  
​Python 🐍 → ESP32: Sends brightness commands (e.g., B180\n for 70% brightness).  
​Control Logic 🧠
​Gestures 🖐️: The system calculates the Euclidean distance between the thumb tip and index tip. This distance is mapped to a PWM value between 0–255.  
​Fan Speed 🌀: Automatically calculated based on temperature:  
​\le 30^{\circ}C: Fan OFF.  
​\ge 40^{\circ}C: Fan FULL (255).  
​Air Quality 💨:
​< 800: GOOD ✅.  
​800 – 1500: MODERATE ⚠️.  
​> 1500: POOR ❌.  
6. Troubleshooting 🔍
​Access Denied 🚫: Ensure the Arduino Serial Monitor is closed before running the Python script.  
​OLED Failure 🌑: Check that Wire.begin(21,22) is called and the I2C address is 0x3C.  
​Voice Not Working 🔇: Ensure an active internet connection for the Google Speech API.  🏠 Smart Home Controller 🚀
​Version 1.0 | April 2026
Gesture 🖐️ · Voice 🎤 · Temperature 🌡️ · People Counter 👥 · Air Quality 💨 · Web Dashboard 💻  
​1. Project Overview 📝
​The Smart Home Controller is a real-time IoT system integrating computer vision, voice recognition, sensor automation, and a live web dashboard. It utilizes an ESP32 microcontroller communicating with a Python 🐍 application on a PC. 
 <p align="center">
  <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" alt="python" width="100" height="100"/>
</p>

​Key Features ✨
​Hand Gesture Control 🖐️: Adjust LED brightness in real time by pinching or spreading your thumb and index finger via webcam.  
​Voice Commands 🗣️: Control lights using phrases like "light on," "light 70," or "dim to fifty".  
​Automated Fan Speed ❄️: A DHT11 sensor monitors temperature; the ESP32 automatically calculates fan speed.  
​People Counter 👥: Dual IR sensors detect entry and exit to maintain a live room occupancy count.  
​Security & Energy Savings 🔒: A magnetic Hall sensor detects door states, and a relay automatically activates if someone is inside.  
​Air Quality Monitoring 🍃: An MQ135 sensor tracks air quality (categorized as GOOD, MODERATE, or POOR).  
​Real-Time Dashboard 🌐: A web-based dashboard using Server-Sent Events (SSE) provides instant updates without page refreshes.  
​2. Hardware Requirements 🛠️
​Main Components
Component Purpose
ESP32 Dev Board 🧠 Main microcontroller (WiFi, Dual-core, PWM, ADC, I2C)
DHT11 🌡️ Temperature and Humidity sensor
MQ135 💨 Gas/Air Quality sensor
Hall Effect Sensor 🧲 Door open/close detection
IR Obstacle Sensor (x2) 🔦 Infrared beam break for people counting
OLED Display (x2) 📺 Two 0.96" SSD1306 displays for data visualization
N-MOSFET ⚡ Switches fan motor (IRLZ44N or 2N7000)
Relay Module 🔌 Controls high-current 
PC Requirements 💻
​Webcam 📷: For hand gesture detection via MediaPipe AI.  
​Microphone 🎙️: For voice commands via Google Speech API.  
​Python 3.9+ 🐍: To run the gesture and voice processing application.  
3. Wiring & Pin Connections 📍
ESP32 Pin Component Connection Details
GPIO 18 LED 💡 PWM output via 220Ω resistor
GPIO 5 Fan (MOSFET) 🌀 PWM gate signal to MOSFET
GPIO 4 DHT11 🌡️ Data pin with 10kΩ pull-up
GPIO 34 MQ135 💨 Analog input (ADC1)
GPIO 2 Hall Sensor 🧲 Digital input for door state
GPIO 16/15 IR Sensors 📶 IR1 (Entry) and IR2 (Exit)
GPIO 17 Relay ⚡ Digital output for load control
GPIO 21/22 OLED 1 📟 I2C Data/Clock (Sensor Display)
GPIO 32/33 OLED 2 📟 I2C Data/Clock (People Display)
​⚠️ Warning: Never connect a DC motor directly to ESP32 pins. Use the MOSFET circuit with a 1N4007 flyback diode to prevent chip damage.  
​4. Software Installation 💾
​Arduino Libraries 🛠️
​Install these via the Arduino Library Manager:  
​Adafruit SSD1306 & Adafruit GFX  
​DHT sensor library (Adafruit)  
​Python Environment 
​Install necessary packages using:  
pip install opencv-python mediapipe pyserial speechrecognition pyaudio
​5. How It Works ⚙️
​Serial Protocol 📡
​The ESP32 and Python app communicate at 9600 baud.  
​ESP32 → Python 🐍: Sends a string every 2 seconds (e.g., T28.5,H62,A410,F128,D1,P3,R1).  
​Python 🐍 → ESP32: Sends brightness commands (e.g., B180\n for 70% brightness).  
​Control Logic 🧠
​Gestures 🖐️: The system calculates the Euclidean distance between the thumb tip and index tip. This distance is mapped to a PWM value between 0–255.  
​Fan Speed 🌀: Automatically calculated based on temperature:  
​\le 30^{\circ}C: Fan OFF.  
​\ge 40^{\circ}C: Fan FULL (255).  
​Air Quality 💨:
​< 800: GOOD ✅.  
​800 – 1500: MODERATE ⚠️.  
​> 1500: POOR ❌.  
6. Troubleshooting 🔍
​Access Denied 🚫: Ensure the Arduino Serial Monitor is closed before running the Python script.  
​OLED Failure 🌑: Check that Wire.begin(21,22) is called and the I2C address is 0x3C.  
​Voice Not Working 🔇: Ensure an active internet connection for the Google Speech API.  