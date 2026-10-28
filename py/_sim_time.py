# Nachbau von "time": Warten blockiert den Browser nicht, weil jedes Board
# in einem eigenen Web Worker laeuft.
import simhw as hw
import time as _t

ticks_ms = _t.ticks_ms
ticks_diff = _t.ticks_diff
ticks_add = _t.ticks_add
time = _t.time
ticks_us = getattr(_t, "ticks_us", lambda: _t.ticks_ms() * 1000)
ticks_cpu = getattr(_t, "ticks_cpu", ticks_us)
for _name in ("time_ns", "localtime", "gmtime", "mktime"):
    try:
        globals()[_name] = getattr(_t, _name)
    except AttributeError:
        pass


def sleep_ms(ms):
    if ms > 0:
        hw.sleep(ms)


def sleep_us(us):
    if us > 0:
        hw.sleep(us / 1000)


def sleep(s):
    if s > 0:
        hw.sleep(s * 1000)
