# XIAO RP2040 firmware

## Wiring

| Component | XIAO pad | RP2040 GPIO |
|---|---:|---:|
| OLED D0/SCK | D7 | 1 |
| OLED D1/MOSI | D6 | 0 |
| OLED RES | D4 | 6 |
| OLED DC | D2 | 28 |
| OLED CS | D0 | 26 |
| OLED VCC | 3V3 | — |
| OLED GND | GND | — |
| TTP223 OUT | D9 | 4 |
| TTP223 VCC | 3V3 | — |
| TTP223 GND | GND | — |

## Flashing with Arduino IDE

1. Install the **Raspberry Pi Pico/RP2040** board package by Earle F. Philhower.
2. Install the **Adafruit GFX Library** and **Adafruit SSD1306** libraries.
3. Open `xiao_rp2040_lyrics/xiao_rp2040_lyrics.ino`.
4. Select **Seeed XIAO RP2040** and its COM port.
5. Upload the sketch.

After flashing, run `run-device.ps1` on the computer. The host automatically
detects the XIAO's USB serial port. If detection fails, set `SERIAL_PORT=COM3`
(using the actual port shown by Arduino IDE) in `.env`.
