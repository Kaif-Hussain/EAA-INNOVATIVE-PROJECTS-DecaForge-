import serial
import speech_recognition as sr
import time

# Change 'COM18' to your ESP32's port
try:
    ser = serial.Serial('COM18', 115200, timeout=1)
    print("Serial connection established on COM18")
except serial.SerialException as e:
    print(f"Error: Could not connect to COM18. {e}")
    print("Please check your COM port and try again.")
    exit()

def listen_voice():
    try:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("Say something...")
            audio = r.listen(source, timeout=5)
        try:
            command = r.recognize_google(audio).lower()
            print(f"You said: {command}")
            if "light on" in command:
                ser.write(b'L1') # Send 'L1' to ESP32
                print("Sent: L1 (Light ON)")
            elif "light off" in command:
                ser.write(b'L0')
                print("Sent: L0 (Light OFF)")
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Error with Google API: {e}")
    except Exception as e:
        print(f"Error: {e}")

try:
    while True:
        listen_voice()
except KeyboardInterrupt:
    print("\nExiting...")
    ser.close()
    print("Serial connection closed.")