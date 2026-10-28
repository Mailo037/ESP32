# Nachbau von "machine" fuer den espBoard-Simulator.
# Jeder Zugriff auf Pins, ADC, PWM und I2C geht an das Board im Browser.
import simhw as hw
import uctypes
import _sim_time as time


def _adr(b):
    return uctypes.addressof(b)


class Pin:
    IN = 1
    OUT = 3
    OPEN_DRAIN = 7
    PULL_UP = 2
    PULL_DOWN = 1
    IRQ_RISING = 1
    IRQ_FALLING = 2

    def __init__(self, id, mode=-1, pull=-1, *, value=None, **kw):
        self.id = int(id)
        if value is not None:
            self.value(value)

    def init(self, mode=-1, pull=-1, *, value=None, **kw):
        if value is not None:
            self.value(value)

    def value(self, v=None):
        if v is None:
            return int(hw.pin_get(self.id))
        hw.pin_set(self.id, 1 if v else 0)

    def __call__(self, v=None):
        return self.value(v)

    def on(self):
        self.value(1)

    def off(self):
        self.value(0)

    def irq(self, *a, **k):
        return None

    def __repr__(self):
        return "Pin(%d)" % self.id


def _pin_nr(p):
    return p.id if isinstance(p, Pin) else int(p)


class ADC:
    ATTN_0DB = 0
    ATTN_2_5DB = 1
    ATTN_6DB = 2
    ATTN_11DB = 3
    WIDTH_9BIT = 0
    WIDTH_10BIT = 1
    WIDTH_11BIT = 2
    WIDTH_12BIT = 3

    def __init__(self, pin, *, atten=None):
        self.id = _pin_nr(pin)

    def init(self, *a, **k):
        pass

    def atten(self, a):
        pass

    def width(self, w):
        pass

    def read_u16(self):
        return int(hw.adc(self.id))

    def read(self):
        return int(hw.adc(self.id)) >> 4

    def read_uv(self):
        return int(hw.adc(self.id)) * 3300 // 65535 * 1000


class PWM:
    def __init__(self, pin, freq=None, duty=None, *, duty_u16=None, duty_ns=None, **kw):
        self.id = _pin_nr(pin)
        self._f = 5000
        self._d = 32768
        self._setzen(freq, duty, duty_u16)

    def _setzen(self, freq=None, duty=None, duty_u16=None):
        if freq is not None:
            self._f = int(freq)
        if duty is not None:
            self._d = max(0, min(65535, int(duty) * 64))
        if duty_u16 is not None:
            self._d = max(0, min(65535, int(duty_u16)))
        hw.pwm(self.id, self._f, self._d)

    def init(self, freq=None, duty=None, *, duty_u16=None, **kw):
        self._setzen(freq, duty, duty_u16)

    def freq(self, f=None):
        if f is None:
            return self._f
        self._setzen(freq=f)

    def duty_u16(self, d=None):
        if d is None:
            return self._d
        self._setzen(duty_u16=d)

    def duty(self, d=None):
        if d is None:
            return self._d >> 6
        self._setzen(duty=d)

    def deinit(self):
        hw.pwm(self.id, 0, 0)


class I2C:
    """Am Bus haengt nur das OLED (0x3C). Der BMP280-Sockel ist leer -
    wie auf vielen echten Boards."""

    def __init__(self, id=0, *, scl=None, sda=None, freq=400000, **kw):
        self.freq = int(freq)

    def init(self, *a, freq=400000, **k):
        self.freq = int(freq)

    def scan(self):
        return [0x3C]

    def _pruefen(self, addr):
        if addr != 0x3C:
            raise OSError(19)   # ENODEV, wie beim echten ESP32

    def writeto(self, addr, buf, stop=True):
        self._pruefen(addr)
        hw.i2c_start(self.freq)
        hw.i2c_data(_adr(buf), len(buf))
        hw.i2c_end()
        return len(buf)

    def writevto(self, addr, bufs, stop=True):
        self._pruefen(addr)
        hw.i2c_start(self.freq)
        n = 0
        for b in bufs:
            hw.i2c_data(_adr(b), len(b))
            n += len(b)
        hw.i2c_end()
        return n

    def readfrom(self, addr, n, stop=True):
        raise OSError(19)

    def readfrom_into(self, addr, buf, stop=True):
        raise OSError(19)

    def readfrom_mem(self, addr, mem, n, **kw):
        raise OSError(19)

    def readfrom_mem_into(self, addr, mem, buf, **kw):
        raise OSError(19)

    def writeto_mem(self, addr, mem, buf, **kw):
        raise OSError(19)


SoftI2C = I2C


class SPI:
    def __init__(self, *a, **k):
        pass

    def init(self, *a, **k):
        pass

    def write(self, buf):
        pass


class Timer:
    ONE_SHOT = 0
    PERIODIC = 1

    def __init__(self, *a, **k):
        pass

    def init(self, *a, **k):
        print("Hinweis: machine.Timer wird im Simulator nicht unterstuetzt")

    def deinit(self):
        pass


def freq(f=None):
    return 240000000


def unique_id():
    return bytes(hw.mac(i) for i in range(6))


def reset():
    hw.reset()


soft_reset = reset


def idle():
    time.sleep_ms(1)


def lightsleep(ms=0):
    time.sleep_ms(ms)


deepsleep = lightsleep


def disable_irq():
    return 0


def enable_irq(state=0):
    pass
