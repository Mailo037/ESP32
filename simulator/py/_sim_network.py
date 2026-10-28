# Nachbau von "network": ESP-NOW und ein WLAN, dessen Internet der Browser
# stellt (fuer den Online-Speicher des ESP-Hubs).
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
        self._verbunden = False

    def active(self, a=None):
        if a is None:
            return self._an
        self._an = bool(a)

    def connect(self, ssid=None, *a, **k):
        # Jedes WLAN "klappt" - ins Internet geht es ueber den Browser
        self._verbunden = self._an

    def disconnect(self):
        self._verbunden = False

    def isconnected(self):
        return self._verbunden and self._an

    def status(self, *a):
        return 1010 if self.isconnected() else 0

    def scan(self):
        return []

    def ifconfig(self, *a):
        if self.isconnected():
            return ("192.168.4.%d" % (10 + hw.mac(5) % 200), "255.255.255.0", "192.168.4.1", "192.168.4.1")
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
