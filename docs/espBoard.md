# Das BZTG espBoard – Bauteile, Pinbelegung, Messprotokoll

Das *espBoard* (BZTG Oldenburg, Version „August 26“) ist ein Lernboard rund um einen
ESP32. Alle Programme in diesem Repository laufen darauf mit **MicroPython**.

## Bauteile (Arbeitsblatt „Kennenlernen des espBoards“)

Die Nummern entsprechen den Nummern auf dem Foto im Arbeitsblatt.

| Nr. | Bauteil | Beschriftung auf dem Board | Aufgabe |
|---|---|---|---|
| 1 | **ESP32-DevKit** (ESP-32D „HW-394“, USB-C) | – | Mikrocontroller: 2 Kerne, 240 MHz, WLAN + Bluetooth, 3,3-V-Logik |
| 2 | **8 LEDs** (rot/gelb abwechselnd) mit Widerstandsnetzwerk 8 × 220 Ω | `RN220`, `P7` (links) … `P0` (rechts) | Einfache Ausgaben, z. B. Punktestand oder Munition |
| 3 | **4 Taster** als Kreuz: S17 oben, S4 links, S5 rechts, S16 unten | `S4`, `S5`, `S16`, `S17` | Eingaben, active-high (gedrückt = 3,3 V) |
| 4 | **2 Potentiometer** (Drehwiderstände) | `RP0`, `RP3` | Analoge Eingabe 0 … 3,3 V |
| 5 | **Analog-Joystick** mit Taster | `RJ6`, `RJ7`, Taster `S2` | Zwei Potis (X/Y) + Druckknopf |
| 6 | **RGB-LED** mit Vorwiderständen | `P8`, `R18`, `R19`, `R23` | Farbige Statusanzeige (PWM) |
| 7 | **OLED-Display** SSD1306, 128 × 64 Pixel | – | Grafikausgabe über I²C |
| 8 | **BMP280** (steckbar, 6-polige Buchse `3V3 GND SCL SDA …`) | `BMP280` | Temperatur- und Luftdrucksensor (I²C) – bei manchen Boards ist die Buchse leer |

Außerdem auf dem Board: ein **Piezo-Summer** an GPIO 15 mit Transistor `T3`
(Steckbrücke `XJ15` muss gesteckt sein, sonst bleibt der Summer stumm), die
Stiftleiste `X51…X53`, die I²C-Messpunkte `MCL`/`MDA` und die Messpunkte
`MP0`, `MP3`, `MP4`, `MP6`, `MP7`, `MP26` sowie `GND`.

```
 ┌──────────────────────────────────────────────────────────────┐
 │ X51  P7 P6 P5 P4 P3 P2 P1 P0     (RP3)   (RP0)               │
 │      rt ge rt ge rt ge rt ge      MP3     MP0    [BMP280]    │
 │ ┌───────────────────────────┐                                │
 │ │  ESP32-DevKit (USB-C)     │   MP6   ┌──────────┐           │
 │ │                           │   MP7   │   OLED   │           │
 │ └───────────────────────────┘         │ 128 × 64 │           │
 │ XJ15 T3         R19 R18  R23  MCL MDA └──────────┘           │
 │  MP4      S17                              ┌─────────┐       │
 │       S4        S5          P8 (RGB)       │Joystick │ RJ6   │
 │           S16                         RJ7  │  (S2)   │       │
 │                 BZTG Oldenburg / August 26 └─────────┘ GND   │
 └──────────────────────────────────────────────────────────────┘
```

## Pinbelegung

Die Zahl im Namen der Bauteile verrät oft schon den Anschluss: `S4` hängt an GPIO 4,
`R19` gehört zur roten LED an GPIO 19. Bei den analogen Bauteilen steht die Zahl
für den **ADC1-Kanal**: `RP0` → Kanal 0 (GPIO 36), `RJ7` → Kanal 7 (GPIO 35).

| Bauteil | GPIO | Hinweis |
|---|---|---|
| OLED + BMP280 (I²C) | SDA = 21, SCL = 22 | OLED-Adresse `0x3C`, BMP280 `0x76` |
| LEDs P7 … P0 (links → rechts) | 13, 12, 14, 27, 26, 25, 33, 32 | Ausgang, 1 = an. P7 rot, P6 gelb, … P0 gelb (abwechselnd) |
| Taster S4 / S5 / S16 / S17 | 4 / 5 / 16 / 17 | Eingang, 10 kΩ Pull-down → gedrückt = 1 |
| Joystick X (`RJ6`) | 34 | ADC1 Kanal 6, nur Eingang |
| Joystick Y (`RJ7`) | 35 | ADC1 Kanal 7, nur Eingang |
| Joystick-Taster | 2 | active-high |
| Poti `RP0` | 36 (VP) | ADC1 Kanal 0 – in Space Dodge „Poti rechts“ |
| Poti `RP3` | 39 (VN) | ADC1 Kanal 3 – in Space Dodge „Poti links“ |
| RGB-LED rot / grün / blau | 19 / 23 / 18 | PWM |
| Piezo-Summer | 15 | PWM |

In MicroPython liefert `ADC.read_u16()` Werte von 0 … 65535. Mit
`atten(ADC.ATTN_11DB)` deckt das den Bereich 0 … ca. 3,3 V ab; der Joystick steht
in Ruhe ungefähr in der Mitte (≈ 32 000).

## Messprotokoll

**Aufbau:** Digitales Multimeter auf Gleichspannung (DC, Bereich ≥ 5 V) stellen,
Board per USB versorgen, **schwarze** Messleitung an `GND`, mit der **roten**
an den Messpunkten messen.

> ⚠️ **Vorsicht:** Mit der Messspitze nie zwei Anschlüsse gleichzeitig berühren.
> Ein Kurzschluss kann Bauteile beschädigen.

Die Tabelle nennt die **Sollwerte**, die sich aus der Schaltung ergeben. Eure
gemessenen Werte tragt ihr in die rechte Spalte ein. Abweichungen von ein paar
Hundertstel Volt sind normal.

| Messpunkt | Sollwert | Warum? | Gemessen |
|---|---|---|---|
| MP4, S4 **nicht** gedrückt | **0 V** | Der 10-kΩ-Pull-down zieht den Eingang auf GND | |
| MP4, S4 gedrückt | **≈ 3,3 V** | Der Taster verbindet den Eingang mit 3,3 V | |
| MP0, RP0 drehen | **0 V … ≈ 3,3 V**, stufenlos | Poti als Spannungsteiler zwischen GND und 3,3 V | |
| MP3, RP3 drehen | **0 V … ≈ 3,3 V**, stufenlos | wie RP0 | |
| MP6, RJ6 (Joystick X) bewegen | Ruhe **≈ 1,65 V**, Anschlag 0 V bzw. ≈ 3,3 V | Joystick = zwei Potis mit Mittelstellung | |
| MP7, RJ7 (Joystick Y) bewegen | Ruhe **≈ 1,65 V**, Anschlag 0 V bzw. ≈ 3,3 V | wie RJ6 | |

**Auswertung:**

- Die Taster sind **digitale** Eingänge: es gibt nur „0 V“ (logisch 0) und
  „3,3 V“ (logisch 1). Das Programm liest das mit `Pin(4, Pin.IN).value()`.
- Potis und Joystick sind **analoge** Eingänge: jede Spannung dazwischen ist möglich.
  Der ADC des ESP32 wandelt sie in eine Zahl um (`read_u16()`).
- Am Board liegen nie mehr als 3,3 V an den GPIOs an – mehr verträgt der ESP32 nicht.
  Die 5 V vom USB werden auf dem DevKit auf 3,3 V heruntergeregelt.

**Mit dem Programm nachmessen:** Dieselben Werte könnt ihr in Thonny direkt
im ESP32 ablesen:

```python
from machine import Pin, ADC
for gpio, name in ((36, "MP0"), (39, "MP3"), (34, "MP6"), (35, "MP7")):
    a = ADC(Pin(gpio)); a.atten(ADC.ATTN_11DB)
    print(name, round(a.read_uv() / 1e6, 2), "V")
print("MP4 (S4):", Pin(4, Pin.IN).value())
```

## Stromversorgung und WLAN

WLAN bzw. ESP-NOW (für **ESP-Pong**) zieht kurzzeitig 200–300 mA. Reicht die
Versorgung nicht, startet das Board mit `Brownout detector was triggered` neu.
Dann:

1. Board über ein kräftiges USB-Netzteil, eine Powerbank oder einen direkten
   USB-Port am PC versorgen (keinen passiven USB-Hub, kein langes dünnes Kabel).
2. Wer über den 3,3-V-Pin versorgt: Netzteil mit mindestens 500 mA, besser 1 A.
3. Optional einen Elko mit 470–1000 µF zwischen 3,3 V und GND nahe am ESP32.
