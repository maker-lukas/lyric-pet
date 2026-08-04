#include <Adafruit_GFX.h>
#include <Adafruit_NeoPixel.h>
#include <Adafruit_SSD1306.h>
#include <SPI.h>

constexpr uint8_t OLED_MOSI = 0;   // XIAO D6
constexpr uint8_t OLED_SCK = 1;    // XIAO D7
constexpr uint8_t OLED_RESET = 6;  // XIAO D4
constexpr uint8_t OLED_DC = 28;    // XIAO D2
constexpr uint8_t OLED_CS = 26;    // XIAO D0
constexpr uint8_t TOUCH_OUT = 4;   // XIAO D9
constexpr uint8_t RGB_POWER = 11;
constexpr uint8_t RGB_DATA = 12;

constexpr uint8_t SCREEN_WIDTH = 128;
constexpr uint8_t SCREEN_HEIGHT = 64;
constexpr uint8_t TEXT_SIZE = 2;
constexpr uint8_t MAX_COLUMNS = 10;
constexpr uint8_t MAX_ROWS = 4;
constexpr unsigned long DEBOUNCE_MS = 300;
constexpr unsigned long WHITE_FLASH_MS = 160;
constexpr uint16_t GOLDEN_ANGLE_HUE_STEP = 25033;

Adafruit_SSD1306 display(
  SCREEN_WIDTH,
  SCREEN_HEIGHT,
  OLED_MOSI,
  OLED_SCK,
  OLED_DC,
  OLED_RESET,
  OLED_CS
);
Adafruit_NeoPixel rgb(1, RGB_DATA, NEO_GRB + NEO_KHZ800);

String inputLine;
String displayedText;
bool lastTouchState = false;
unsigned long lastTouchAt = 0;
unsigned long whiteFlashUntil = 0;
uint16_t lyricHue = 0;

void showLyricColor() {
  rgb.setPixelColor(0, rgb.gamma32(rgb.ColorHSV(lyricHue)));
  rgb.show();
}

void drawCentered(const String &text) {
  String rows[MAX_ROWS];
  uint8_t rowCount = 0;
  int position = 0;

  while (position < text.length() && rowCount < MAX_ROWS) {
    while (position < text.length() && text[position] == ' ') position++;
    String row;
    while (position < text.length()) {
      int nextSpace = text.indexOf(' ', position);
      if (nextSpace < 0) nextSpace = text.length();
      String word = text.substring(position, nextSpace);
      if (row.length() && row.length() + 1 + word.length() > MAX_COLUMNS) break;
      if (row.length()) row += ' ';
      row += word;
      position = nextSpace;
      while (position < text.length() && text[position] == ' ') position++;
    }
    if (!row.length() && position < text.length()) {
      row = text.substring(position, min(position + MAX_COLUMNS, static_cast<int>(text.length())));
      position += row.length();
    }
    rows[rowCount++] = row;
  }

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(TEXT_SIZE);
  display.setTextWrap(false);

  const int lineHeight = 8 * TEXT_SIZE;
  int y = (SCREEN_HEIGHT - rowCount * lineHeight) / 2;
  for (uint8_t row = 0; row < rowCount; row++) {
    int width = rows[row].length() * 6 * TEXT_SIZE;
    display.setCursor(max(0, (SCREEN_WIDTH - width) / 2), y + row * lineHeight);
    display.print(rows[row]);
  }
  display.display();
}

void setup() {
  pinMode(TOUCH_OUT, INPUT);
  pinMode(RGB_POWER, OUTPUT);
  digitalWrite(RGB_POWER, HIGH);
  rgb.begin();
  rgb.setBrightness(255);
  showLyricColor();
  Serial.begin(115200);

  if (!display.begin(SSD1306_SWITCHCAPVCC)) {
    while (true) delay(1000);
  }
  lastTouchState = digitalRead(TOUCH_OUT) == HIGH;
  drawCentered("Waiting");
  Serial.println("READY");
}

void loop() {
  unsigned long now = millis();
  if (whiteFlashUntil && static_cast<long>(now - whiteFlashUntil) >= 0) {
    whiteFlashUntil = 0;
    showLyricColor();
  }

  while (Serial.available()) {
    char character = Serial.read();
    if (character == '\n') {
      if (inputLine.startsWith("TEXT\t")) {
        String newText = inputLine.substring(5);
        if (newText != displayedText) {
          displayedText = newText;
          lyricHue += GOLDEN_ANGLE_HUE_STEP;
          if (!whiteFlashUntil) showLyricColor();
        }
        drawCentered(newText);
      }
      inputLine = "";
    } else if (character != '\r') {
      inputLine += character;
    }
  }

  bool touchState = digitalRead(TOUCH_OUT) == HIGH;
  if (touchState && !lastTouchState && now - lastTouchAt >= DEBOUNCE_MS) {
    whiteFlashUntil = now + WHITE_FLASH_MS;
    rgb.setPixelColor(0, rgb.Color(255, 255, 255));
    rgb.show();
    Serial.println("TOGGLE");
    lastTouchAt = now;
  }
  lastTouchState = touchState;
}
