# MicroPython SSD1306 OLED-Treiber (I2C und SPI)
#
# Kompatibel zum Original-Treiber aus micropython-lib, aber schneller:
#  - Adress-Befehle werden in EINER I2C-Uebertragung gesendet (statt 6 einzelnen)
#  - show_rect(x, y, w, h) uebertraegt nur einen Ausschnitt des Bildes.
#    Ein ganzes Bild (1024 Byte) braucht bei 400 kHz ca. 23 ms,
#    ein kleiner Ausschnitt (z. B. Ball 5x8 Pixel) unter 1 ms.

from micropython import const
import framebuf


# Register
SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xA0)
SET_MUX_RATIO = const(0xA8)
SET_COM_OUT_DIR = const(0xC0)
SET_DISP_OFFSET = const(0xD3)
SET_COM_PIN_CFG = const(0xDA)
SET_DISP_CLK_DIV = const(0xD5)
SET_PRECHARGE = const(0xD9)
SET_VCOM_DESEL = const(0xDB)
SET_CHARGE_PUMP = const(0x8D)


class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        self.mv = memoryview(self.buffer)
        # Fenster-Befehl: Spalte x0..x1, Seite p0..p1
        self.fenster = bytearray((SET_COL_ADDR, 0, 0, SET_PAGE_ADDR, 0, 0))
        self.x_offset = 32 if width == 64 else 0
        self.invertiert = -1
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP | 0x00,  # aus
            SET_MEM_ADDR,
            0x00,  # horizontal (Fenster wird zeilenweise gefuellt)
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,
            SET_MUX_RATIO,
            self.height - 1,
            SET_COM_OUT_DIR | 0x08,
            SET_DISP_OFFSET,
            0x00,
            SET_COM_PIN_CFG,
            0x02 if self.width > 2 * self.height else 0x12,
            SET_DISP_CLK_DIV,
            0x80,
            SET_PRECHARGE,
            0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL,
            0x30,
            SET_CONTRAST,
            0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP,
            0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01,  # an
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        # Nur senden, wenn sich etwas aendert (spart I2C-Zeit pro Bild)
        invert = 1 if invert else 0
        if invert != self.invertiert:
            self.write_cmd(SET_NORM_INV | invert)
            self.invertiert = invert

    def _fenster_setzen(self, x0, x1, p0, p1):
        f = self.fenster
        f[1] = x0 + self.x_offset
        f[2] = x1 + self.x_offset
        f[4] = p0
        f[5] = p1
        self.write_cmds(f)

    def show(self):
        """Ganzes Bild uebertragen."""
        self._fenster_setzen(0, self.width - 1, 0, self.pages - 1)
        self.write_data(self.buffer)

    def show_rect(self, x, y, w, h):
        """Nur den Ausschnitt (x, y, w, h) in Pixeln uebertragen.

        Senkrecht wird auf ganze 8-Pixel-Seiten aufgerundet.
        """
        x0 = x if x > 0 else 0
        x1 = x + w - 1
        if x1 >= self.width:
            x1 = self.width - 1
        y0 = y if y > 0 else 0
        y1 = y + h - 1
        if y1 >= self.height:
            y1 = self.height - 1
        if x1 < x0 or y1 < y0:
            return
        p0 = y0 >> 3
        p1 = y1 >> 3
        self._fenster_setzen(x0, x1, p0, p1)
        W = self.width
        if x0 == 0 and x1 == W - 1:
            self.write_data(self.mv[p0 * W:(p1 + 1) * W])
        else:
            teile = []
            for p in range(p0, p1 + 1):
                a = p * W
                teile.append(self.mv[a + x0:a + x1 + 1])
            self.write_data_list(teile)


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.cmd_list = [b"\x00", None]   # Co=0, D/C#=0: Befehlsfolge
        self.write_list = [b"\x40", None]  # Co=0, D/C#=1: Daten
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80  # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_cmds(self, cmds):
        self.cmd_list[1] = cmds
        self.i2c.writevto(self.addr, self.cmd_list)

    def write_data(self, buf):
        self.write_list[1] = buf
        self.i2c.writevto(self.addr, self.write_list)

    def write_data_list(self, teile):
        # Alle Teile in EINER Uebertragung, das Fenster bricht selbst um
        self.i2c.writevto(self.addr, [b"\x40"] + teile)


class SSD1306_SPI(SSD1306):
    def __init__(self, width, height, spi, dc, res, cs, external_vcc=False):
        self.rate = 10 * 1024 * 1024
        dc.init(dc.OUT, value=0)
        res.init(res.OUT, value=0)
        cs.init(cs.OUT, value=1)
        self.spi = spi
        self.dc = dc
        self.res = res
        self.cs = cs
        import time

        self.res(1)
        time.sleep_ms(1)
        self.res(0)
        time.sleep_ms(10)
        self.res(1)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.write_cmds(bytearray([cmd]))

    def write_cmds(self, cmds):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(cmds)
        self.cs(1)

    def write_data(self, buf):
        self.write_data_list((buf,))

    def write_data_list(self, teile):
        self.spi.init(baudrate=self.rate, polarity=0, phase=0)
        self.cs(1)
        self.dc(1)
        self.cs(0)
        for t in teile:
            self.spi.write(t)
        self.cs(1)
