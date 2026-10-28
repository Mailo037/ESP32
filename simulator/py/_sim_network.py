# Nachbau von "network": nur das, was fuer ESP-NOW gebraucht wird.
import simhw as hw

STA_IF = 0
AP_IF = 1


def _mac():
    return bytes(hw.mac(i) for i in range(6))


class WLAN:
    PM_NONE = 0
    PM_PERFORMANCE = 1
    PM_POWERSAVE = 2

    def __init__(self, interface=STA_IF):
        self._an = False
        self._kanal = 1

    def active(self, a=None):
        if a is None:
            return self._an
        self._an = bool(a)

    def connect(self, *a, **k):
        print("Hinweis: Im Simulator gibt es kein WLAN, nur ESP-NOW")

    def disconnect(self):
        pass

    def isconnected(self):
        return False

    def status(self, *a):
        return 0

    def scan(self):
        return []

    def ifconfig(self, *a):
        return ("0.0.0.0", "0.0.0.0", "0.0.0.0", "0.0.0.0")

    def config(self, *a, **k):
        if "channel" in k:
            self._kanal = k["channel"]
        if a:
            if a[0] == "mac":
                return _mac()
            if a[0] == "channel":
                return self._kanal
            return 0
