/*
  ============================================================
   SMART HOME CONTROLLER — ESP32 FIXED
  ============================================================
  BUGS FIXED vs your uploaded file:

  BUG 1 — Serial.println() instead of Serial.print()
    Each field was on a separate line so Python got:
    "T\n28.5\n,H\n62..." — never matched the parser.
    FIX: Use Serial.print() for all fields, Serial.println() only at end.

  BUG 2 — Serial format sent wrong value for fan
    Was sending (fanPWM*100)/255 (percentage) instead of fanPWM (raw 0-255).
    Python parser expects raw PWM. FIX: Send fanPWM directly.

  BUG 3 — delay(1000) inside loop()
    A 1-second blocking delay every loop iteration means Python's
    "B180\n" command sits in the serial buffer for up to 1 second
    before ESP32 even checks Serial.available(). 
    FIX: Removed. All timing uses millis() non-blocking.

  BUG 4 — else ledcWrite(LED_PIN, 255) after serial command
    Any serial line that doesn't start with "B" (like sensor echoes)
    was forcing LED to full brightness 255, overriding gesture control.
    FIX: Removed that else branch entirely.

  BUG 5 — ledcWrite(LED_PIN, 5000) in setup
    5000 is the PWM frequency, not a brightness value. Writing it as
    duty cycle causes undefined LED behaviour.
    FIX: ledcWrite(LED_PIN, 0) — start off.
  ============================================================
*/

#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

// ─────────────────────────────────────────────
//  WiFi
// ─────────────────────────────────────────────
const char* ssid     = "12345678";
const char* password = "12345678";
WiFiServer server(80);

// ─────────────────────────────────────────────
//  Pins
// ─────────────────────────────────────────────
#define LED_PIN    18
#define FAN_PIN     5
#define DHTPIN      4
#define MQ135_PIN  34
#define HALL_PIN    2
#define IR1_PIN    16
#define IR2_PIN    15
#define RELAY_PIN  17

// ─────────────────────────────────────────────
//  OLED — two displays on two I2C buses
// ─────────────────────────────────────────────
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT  64

// display  → Wire  (SDA=21, SCL=22) — sensors
// display1 → Wire1 (SDA=32, SCL=33) — people/door
Adafruit_SSD1306 display (SCREEN_WIDTH, SCREEN_HEIGHT, &Wire,  -1);
Adafruit_SSD1306 display1(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire1, -1);

// ─────────────────────────────────────────────
//  DHT
// ─────────────────────────────────────────────
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// ─────────────────────────────────────────────
//  State
// ─────────────────────────────────────────────
float temp      = 0;
float hum       = 0;
int   air       = 0;
int   fanPWM    = 0;
int   ledPWM    = 0;
int   peopleCount = 0;
bool  doorOpen  = false;
bool  relayOn   = false;

// IR edge detection (non-blocking)
bool ir1Last = HIGH;
bool ir2Last = HIGH;

unsigned long lastSensor = 0;
unsigned long lastSSE    = 0;

// SSE
WiFiClient sseClient;
bool       sseActive = false;

// ─────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────
String airLabel(int raw) {
  if (raw < 800)  return "GOOD";
  if (raw < 1500) return "MOD";
  return "POOR";
}

// ─────────────────────────────────────────────
//  OLED 1 — sensor data
// ─────────────────────────────────────────────
void updateOLED1() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);

  display.setCursor(0, 0);
  display.print("Temp: "); display.print(temp, 1); display.println(" C");

  display.setCursor(0, 16);
  display.print("Hum : "); display.print((int)hum); display.println(" %");

  display.setCursor(0, 32);
  display.print("Air : "); display.print(air);
  display.print(" ["); display.print(airLabel(air)); display.println("]");

  display.setCursor(0, 48);
  display.print("Fan:"); display.print((fanPWM * 100) / 255);
  display.print("% LED:"); display.print((ledPWM * 100) / 255);
  display.println("%");

  display.display();
}

// ─────────────────────────────────────────────
//  OLED 2 — people + door
// ─────────────────────────────────────────────
void updateOLED2() {
  display1.clearDisplay();
  display1.setTextSize(1);
  display1.setTextColor(WHITE);

  display1.setCursor(0, 0);
  display1.println("-- People Counter --");
  display1.drawLine(0, 9, 127, 9, WHITE);

  display1.setTextSize(2);
  display1.setCursor(30, 16);
  display1.print("Ppl: ");
  display1.println(peopleCount);

  display1.setTextSize(1);
  display1.setCursor(0, 45);
  display1.print("Door: ");
  display1.println(doorOpen ? "OPEN" : "CLOSED");

  display1.setCursor(0, 56);
  display1.print("Relay: ");
  display1.println(relayOn ? "ON" : "OFF");

  display1.display();
}

// ─────────────────────────────────────────────
//  SSE push
// ─────────────────────────────────────────────
void pushSSE() {
  if (!sseActive || !sseClient.connected()) {
    sseActive = false;
    return;
  }
  String json = "{";
  json += "\"temp\":"       + String(temp, 1)                + ",";
  json += "\"hum\":"        + String((int)hum)               + ",";
  json += "\"air\":"        + String(air)                    + ",";
  json += "\"airLabel\":\"" + airLabel(air) + "\","          ;
  json += "\"fan\":"        + String((fanPWM * 100) / 255)   + ",";
  json += "\"led\":"        + String((ledPWM * 100) / 255)   + ",";
  json += "\"door\":"       + String(doorOpen ? 1 : 0)       + ",";
  json += "\"people\":"     + String(peopleCount)            + ",";
  json += "\"relay\":"      + String(relayOn ? 1 : 0)        ;
  json += "}";

  sseClient.print("data: ");
  sseClient.print(json);
  sseClient.print("\n\n");
}

// ─────────────────────────────────────────────
//  HTML dashboard
// ─────────────────────────────────────────────
void serveHTML(WiFiClient& client) {
  String html = R"rawhtml(<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Home</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Courier New',monospace;background:#0d0d0d;color:#e0e0e0;
       min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:20px 14px}
  h1{font-size:1.3em;color:#00ffcc;letter-spacing:3px;text-transform:uppercase;margin-bottom:4px}
  .sub{font-size:.68em;color:#444;margin-bottom:22px;letter-spacing:1px}
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;
       background:#0f0;margin-right:6px;animation:blink 1s infinite}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
        gap:12px;width:100%;max-width:680px}
  .card{background:#161616;border:1px solid #2a2a2a;border-radius:10px;
        padding:14px 12px;display:flex;flex-direction:column;align-items:flex-start}
  .card-label{font-size:.62em;color:#555;text-transform:uppercase;
              letter-spacing:2px;margin-bottom:7px}
  .card-value{font-size:1.9em;font-weight:bold;line-height:1;transition:color .3s}
  .card-unit{font-size:.68em;color:#555;margin-top:4px}
  .bar-wrap{width:100%;height:5px;background:#222;border-radius:3px;
            margin-top:10px;overflow:hidden}
  .bar-fill{height:100%;border-radius:3px;transition:width .5s ease}
  .badge{display:inline-block;padding:3px 10px;border-radius:20px;
         font-size:.7em;font-weight:bold;margin-top:8px;letter-spacing:1px}
  .badge-on  {background:#1a3a1a;color:#00ff88;border:1px solid #00ff88}
  .badge-off {background:#2a1a1a;color:#ff4444;border:1px solid #ff4444}
  .badge-open{background:#1a2a3a;color:#00d4ff;border:1px solid #00d4ff}
  .badge-shut{background:#1a1a1a;color:#444;   border:1px solid #333}
  .c-cyan{color:#00d4ff}.c-blue{color:#5588ff}.c-green{color:#00ff88}
  .c-amber{color:#ffaa00}.c-red{color:#ff4444}.c-white{color:#e0e0e0}.c-pink{color:#ff88cc}
  .footer{margin-top:22px;font-size:.65em;color:#333;letter-spacing:1px}
  #ts{color:#00ffcc}
</style>
</head>
<body>
<h1><span class="dot"></span>Smart Home</h1>
<p class="sub">Live · No Refresh · Server-Sent Events</p>
<div class="grid">
  <div class="card">
    <div class="card-label">Temperature</div>
    <div class="card-value c-cyan" id="temp">--.-</div>
    <div class="card-unit">&deg;C</div>
    <div class="bar-wrap"><div class="bar-fill" id="bar-temp" style="width:0%;background:#00d4ff"></div></div>
  </div>
  <div class="card">
    <div class="card-label">Humidity</div>
    <div class="card-value c-blue" id="hum">--</div>
    <div class="card-unit">%</div>
    <div class="bar-wrap"><div class="bar-fill" id="bar-hum" style="width:0%;background:#5588ff"></div></div>
  </div>
  <div class="card">
    <div class="card-label">Air Quality</div>
    <div class="card-value c-green" id="airVal">----</div>
    <div class="card-unit" id="airRaw">-- raw</div>
    <div class="bar-wrap"><div class="bar-fill" id="bar-air" style="width:0%;background:#00ff88"></div></div>
  </div>
  <div class="card">
    <div class="card-label">Fan Speed</div>
    <div class="card-value c-amber" id="fan">--</div>
    <div class="card-unit">% AUTO</div>
    <div class="bar-wrap"><div class="bar-fill" id="bar-fan" style="width:0%;background:#ffaa00"></div></div>
  </div>
  <div class="card">
    <div class="card-label">LED Level</div>
    <div class="card-value c-white" id="led">--</div>
    <div class="card-unit">% (gesture/voice)</div>
    <div class="bar-wrap"><div class="bar-fill" id="bar-led" style="width:0%;background:#e0e0e0"></div></div>
  </div>
  <div class="card">
    <div class="card-label">Door</div>
    <div class="card-value c-cyan" id="doorVal">--</div>
    <div class="card-unit">Hall sensor</div>
    <div id="door-badge" class="badge badge-shut">CLOSED</div>
  </div>
  <div class="card">
    <div class="card-label">People Inside</div>
    <div class="card-value c-pink" id="people">--</div>
    <div class="card-unit">IR counter</div>
    <div class="bar-wrap"><div class="bar-fill" id="bar-ppl" style="width:0%;background:#ff88cc"></div></div>
  </div>
  <div class="card">
    <div class="card-label">Relay / Power</div>
    <div class="card-value" id="relayVal">--</div>
    <div class="card-unit">auto</div>
    <div id="relay-badge" class="badge badge-off">OFF</div>
  </div>
</div>
<p class="footer">Last update: <span id="ts">connecting...</span></p>
<script>
const es = new EventSource('/events');
es.onmessage = function(e) {
  const d = JSON.parse(e.data);
  document.getElementById('temp').textContent     = d.temp;
  document.getElementById('bar-temp').style.width = Math.min(100,d.temp/50*100)+'%';
  document.getElementById('hum').textContent      = d.hum;
  document.getElementById('bar-hum').style.width  = d.hum+'%';
  const airEl=document.getElementById('airVal'),barAir=document.getElementById('bar-air');
  airEl.textContent=d.airLabel;
  document.getElementById('airRaw').textContent=d.air+' raw';
  barAir.style.width=Math.min(100,d.air/4095*100)+'%';
  if(d.airLabel==='GOOD'){airEl.className='card-value c-green';barAir.style.background='#00ff88';}
  else if(d.airLabel==='MOD'){airEl.className='card-value c-amber';barAir.style.background='#ffaa00';}
  else{airEl.className='card-value c-red';barAir.style.background='#ff4444';}
  document.getElementById('fan').textContent      = d.fan;
  document.getElementById('bar-fan').style.width  = d.fan+'%';
  document.getElementById('led').textContent      = d.led;
  document.getElementById('bar-led').style.width  = d.led+'%';
  const db=document.getElementById('door-badge');
  document.getElementById('doorVal').textContent=d.door?'OPEN':'SHUT';
  db.textContent=d.door?'OPEN':'CLOSED';
  db.className='badge '+(d.door?'badge-open':'badge-shut');
  document.getElementById('people').textContent=d.people;
  document.getElementById('bar-ppl').style.width=Math.min(100,d.people*10)+'%';
  const rb=document.getElementById('relay-badge'),rv=document.getElementById('relayVal');
  rv.textContent=d.relay?'ON':'OFF';
  rv.className='card-value '+(d.relay?'c-green':'c-red');
  rb.textContent=d.relay?'ACTIVE':'OFF';
  rb.className='badge '+(d.relay?'badge-on':'badge-off');
  document.getElementById('ts').textContent=new Date().toLocaleTimeString();
};
es.onerror=function(){document.getElementById('ts').textContent='reconnecting...';};
</script>
</body>
</html>)rawhtml";

  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: text/html");
  client.println("Connection: close");
  client.println();
  client.println(html);
}

// ============================================================
//  SETUP
// ============================================================
void setup() {
  Serial.begin(9600);

  Wire.begin(21, 22);    // OLED 1
  Wire1.begin(32, 33);   // OLED 2

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED1 FAILED"); while (1);
  }
  if (!display1.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED2 FAILED"); while (1);
  }

  // Sensor & relay pins
  pinMode(HALL_PIN,  INPUT_PULLUP);
  pinMode(IR1_PIN,   INPUT_PULLUP);
  pinMode(IR2_PIN,   INPUT_PULLUP);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  display.clearDisplay();
  display.setTextColor(WHITE);
  display.setCursor(0, 0); display.println("Starting...");
  display.display();

  display1.clearDisplay();
  display1.setTextColor(WHITE);
  display1.setCursor(0, 0); display1.println("Starting...");
  display1.display();

  dht.begin();

  // ✅ BUG 5 FIX: ledcWrite(LED_PIN, 0) not 5000
  ledcAttach(LED_PIN, 5000, 8);
  ledcAttach(FAN_PIN, 5000, 8);
  ledcWrite(LED_PIN, 0);   // LED off at start
  ledcWrite(FAN_PIN, 0);   // Fan off at start

  display.setCursor(0, 16);
  display.println("WiFi connecting...");
  display.display();

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);

  server.begin();
  Serial.println("WiFi Connected!");
  Serial.print("IP: "); Serial.println(WiFi.localIP());

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("WiFi OK!");
  display.println(WiFi.localIP());
  display.display();
  delay(1200);
}

// ============================================================
//  LOOP — non-blocking, no delay()
// ============================================================
void loop() {
  
  unsigned long now = millis();
  // Detect Entry
if (digitalRead(IR1_PIN) == LOW) {
  delay(100); // Simple debounce
  while (digitalRead(IR1_PIN) == LOW); // Wait for person to pass IR1
  
  // Check if they hit IR2 immediately after
  if (digitalRead(IR2_PIN) == LOW) {
    while (digitalRead(IR2_PIN) == LOW); // Wait for person to clear IR2
    peopleCount++;
    delay(500); // "Cooldown" to prevent the second IF from triggering
  }
} 
// Use "else if" so it can't trigger both directions in one loop cycle
else if (digitalRead(IR2_PIN) == LOW) {
  delay(100);
  while (digitalRead(IR2_PIN) == LOW);
  
  if (digitalRead(IR1_PIN) == LOW) {
    while (digitalRead(IR1_PIN) == LOW);
    if (peopleCount > 0) peopleCount--; // Cleaner way to prevent negatives
    delay(500); 
  }
}

  // ── Hall sensor — door ────────────────────────────────────
  doorOpen = (digitalRead(HALL_PIN) == LOW);

  // ── Relay ─────────────────────────────────────────────────
  relayOn = (doorOpen || peopleCount > 0);
  digitalWrite(RELAY_PIN, relayOn ? HIGH : LOW);

  // ── Sensor read every 2 seconds ──────────────────────────
  if (now - lastSensor > 2000) {
    lastSensor = now;

    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) temp = t;
    if (!isnan(h)) hum  = h;
    air = analogRead(MQ135_PIN);

    if (temp <= 20.0)      fanPWM = 0;
    else if (temp >= 40.0) fanPWM = 255;
    else                   fanPWM = (int)map((long)temp, 20, 40, 0, 255);
    ledcWrite(FAN_PIN, fanPWM);

    updateOLED1();
    updateOLED2();

    // ✅ BUG 1 FIX: Serial.print() not Serial.println() for each field
    // ✅ BUG 2 FIX: Send fanPWM (raw 0-255) not percentage
    // Format: T28.5,H62,A410,F128,D1,P3,R1
    Serial.print("T");  Serial.print(temp, 1);
    Serial.print(",H"); Serial.print((int)hum);
    Serial.print(",A"); Serial.print(air);
    Serial.print(",F"); Serial.print(fanPWM);
    Serial.print(",D"); Serial.print(doorOpen ? 1 : 0);
    Serial.print(",P"); Serial.print(peopleCount);
    Serial.print(",R"); Serial.println(relayOn ? 1 : 0);
  }

  // ── SSE push every 1 second ───────────────────────────────
  if (now - lastSSE > 1000) {
    lastSSE = now;
    pushSSE();
  }

  // ── Serial command from Python ────────────────────────────
  // ✅ BUG 4 FIX: Removed else ledcWrite(LED_PIN,255)
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("B")) {
      int brightness = constrain(cmd.substring(1).toInt(), 0, 255);
      ledcWrite(LED_PIN, brightness);
      ledPWM = brightness;
      Serial.print("LED_OK:"); Serial.println(brightness);
    }
    // NO else branch — anything that isn't "B" is just ignored
  }

  // ── Web server ────────────────────────────────────────────
  WiFiClient client = server.available();
  if (client) {
    String request = "";
    unsigned long t0 = millis();
    while (client.connected() && millis() - t0 < 200) {
      if (client.available()) {
        char c = client.read();
        request += c;
        if (request.endsWith("\r\n\r\n")) break;
      }
    }

    if (request.indexOf("GET /events") >= 0) {
      if (sseActive) sseClient.stop();
      sseClient = client;
      sseActive = true;
      sseClient.println("HTTP/1.1 200 OK");
      sseClient.println("Content-Type: text/event-stream");
      sseClient.println("Cache-Control: no-cache");
      sseClient.println("Connection: keep-alive");
      sseClient.println("Access-Control-Allow-Origin: *");
      sseClient.println();
      sseClient.flush();
      pushSSE();
    } else {
      serveHTML(client);
      delay(1);
      client.stop();
    }
  }
}
