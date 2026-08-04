#include <Adafruit_NeoPixel.h>
#include <U8g2lib.h>

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
constexpr uint8_t MAX_TEXT_ROWS = 6;
constexpr uint8_t HORIZONTAL_MARGIN = 2;
constexpr unsigned long DEBOUNCE_MS = 80;
constexpr unsigned long WHITE_FLASH_MS = 160;
constexpr uint16_t GOLDEN_ANGLE_HUE_STEP = 25033;

U8G2_SSD1306_128X64_NONAME_F_4W_SW_SPI display(
  U8G2_R0,
  OLED_SCK,
  OLED_MOSI,
  OLED_CS,
  OLED_DC,
  OLED_RESET
);
Adafruit_NeoPixel rgb(1, RGB_DATA, NEO_GRB + NEO_KHZ800);

const uint8_t *const LYRIC_FONTS[] = {
  u8g2_font_helvB14_tr,
  u8g2_font_helvB12_tr,
  u8g2_font_helvB10_tr,
  u8g2_font_6x12_tr,
};

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

void advanceLyricColor() {
  lyricHue += GOLDEN_ANGLE_HUE_STEP;
  if (!whiteFlashUntil) showLyricColor();
}

void drawMusicIcon() {
  display.clearBuffer();
  display.setDrawColor(1);
  display.drawDisc(51, 45, 7);
  display.drawDisc(55, 42, 7);
  display.drawBox(60, 15, 4, 29);
  display.drawBox(64, 15, 12, 4);
  display.drawBox(72, 18, 8, 4);
  display.drawBox(77, 21, 5, 8);
  display.drawBox(74, 27, 5, 5);
  display.sendBuffer();
}

bool wrapText(const String &text, String rows[], uint8_t &rowCount, uint8_t maxRows) {
  rowCount = 0;
  int position = 0;

  while (position < text.length()) {
    while (position < text.length() && text[position] == ' ') position++;
    if (position >= text.length()) break;
    if (rowCount >= maxRows) return false;

    String row;
    while (position < text.length()) {
      int nextSpace = text.indexOf(' ', position);
      if (nextSpace < 0) nextSpace = text.length();
      String word = text.substring(position, nextSpace);
      String candidate = row.length() ? row + " " + word : word;

      if (display.getUTF8Width(candidate.c_str()) <= SCREEN_WIDTH - 2 * HORIZONTAL_MARGIN) {
        row = candidate;
        position = nextSpace;
        while (position < text.length() && text[position] == ' ') position++;
      } else if (row.length()) {
        break;
      } else {
        int characters = 1;
        while (
          characters < word.length()
          && display.getUTF8Width(word.substring(0, characters + 1).c_str())
            <= SCREEN_WIDTH - 2 * HORIZONTAL_MARGIN
        ) {
          characters++;
        }
        row = word.substring(0, characters);
        position += characters;
        break;
      }
    }
    rows[rowCount++] = row;
  }

  return true;
}

void drawCentered(const String &text) {
  display.clearBuffer();
  display.setDrawColor(1);
  if (!text.length()) {
    display.sendBuffer();
    return;
  }

  String rows[MAX_TEXT_ROWS];
  uint8_t rowCount = 0;
  int lineHeight = 0;
  bool fitted = false;

  for (const uint8_t *font : LYRIC_FONTS) {
    display.setFont(font);
    lineHeight = display.getAscent() - display.getDescent() + 2;
    uint8_t maxRows = min<uint8_t>(MAX_TEXT_ROWS, SCREEN_HEIGHT / lineHeight);
    if (wrapText(text, rows, rowCount, maxRows)) {
      fitted = true;
      break;
    }
  }

  if (!fitted) {
    display.setFont(u8g2_font_6x12_tr);
    lineHeight = display.getAscent() - display.getDescent() + 1;
    wrapText(text, rows, rowCount, MAX_TEXT_ROWS);
  }

  int blockHeight = rowCount * lineHeight - 2;
  int baseline = (SCREEN_HEIGHT - blockHeight) / 2 + display.getAscent();
  for (uint8_t row = 0; row < rowCount; row++) {
    int width = display.getUTF8Width(rows[row].c_str());
    int x = max<int>(HORIZONTAL_MARGIN, (SCREEN_WIDTH - width) / 2);
    display.drawUTF8(x, baseline + row * lineHeight, rows[row].c_str());
  }
  display.sendBuffer();
}

void setup() {
  pinMode(TOUCH_OUT, INPUT);
  pinMode(RGB_POWER, OUTPUT);
  digitalWrite(RGB_POWER, HIGH);

  rgb.begin();
  rgb.setBrightness(255);
  showLyricColor();

  Serial.begin(115200);
  display.begin();
  display.enableUTF8Print();

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
          advanceLyricColor();
        }
        drawCentered(newText);
      } else if (inputLine == "ICON\tMUSIC") {
        if (displayedText != "<MUSIC>") {
          displayedText = "<MUSIC>";
          advanceLyricColor();
        }
        drawMusicIcon();
      } else if (inputLine == "BOOTSEL") {
        rp2040.rebootToBootloader();
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
