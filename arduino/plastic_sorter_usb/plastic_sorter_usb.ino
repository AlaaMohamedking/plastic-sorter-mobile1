/*
  plastic_sorter_usb.ino
  Arduino Mega 2560 + 8 ريليهات Active-LOW
  اتصال USB مباشر (كابل OTG من الموبايل، أو سلك USB عادى من الكمبيوتر) — بدون بلوتوث خالص.

  البروتوكول (نفس بروتوكول نسخة الكمبيوتر ونسخة الموبايل بالظبط):
    R:<idx>:<0/1>   تشغيل/إيقاف الريليه رقم idx (0-7)
    P:<idx>:<ms>    نبضة على الريليه رقم idx لمدة ms مللى ثانية
    A               إيقاف كل الريليهات فوراً
*/

const int RELAY_COUNT = 8;
const int RELAY_PINS[RELAY_COUNT] = {22, 24, 26, 28, 30, 32, 34, 36};
const bool ACTIVE_LOW = true;
const long BAUD_RATE = 115200;   // لازم يطابق BAUD_RATE فى usb_serial_link.py بتاع تطبيق الموبايل

String buffer = "";

void setRelay(int idx, bool on) {
  if (idx < 0 || idx >= RELAY_COUNT) return;
  int level = ACTIVE_LOW ? (on ? LOW : HIGH) : (on ? HIGH : LOW);
  digitalWrite(RELAY_PINS[idx], level);
}

void allStop() {
  for (int i = 0; i < RELAY_COUNT; i++) setRelay(i, false);
}

void handleCommand(String line) {
  line.trim();
  if (line.length() == 0) return;

  if (line == "A") {
    allStop();
    return;
  }

  int firstColon = line.indexOf(':');
  if (firstColon < 0) return;
  String cmd = line.substring(0, firstColon);
  String rest = line.substring(firstColon + 1);
  int secondColon = rest.indexOf(':');
  if (secondColon < 0) return;
  int idx = rest.substring(0, secondColon).toInt();
  int value = rest.substring(secondColon + 1).toInt();

  if (cmd == "R") {
    setRelay(idx, value == 1);
  } else if (cmd == "P") {
    setRelay(idx, true);
    delay(value);   // بسيط ومباشر؛ لمشروع فيه أكتر من نبضة فى نفس الوقت استخدم millis() بدل delay()
    setRelay(idx, false);
  }
}

void setup() {
  for (int i = 0; i < RELAY_COUNT; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
  }
  allStop();
  Serial.begin(BAUD_RATE);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handleCommand(buffer);
      buffer = "";
    } else {
      buffer += c;
    }
  }
}
