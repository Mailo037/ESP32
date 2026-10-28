# Nachbau von "espnow": Pakete gehen an die anderen Boards im Simulator.
import simhw as hw
import uctypes
import _sim_time as time

MAX_DATA_LEN = 250
KEY_LEN = 16
ADDR_LEN = 6
BROADCAST = b"\xff" * 6


class ESPNow:
    def __init__(self):
        self._an = False
        self._peers = []
        self._mac = bytearray(6)
        self._puffer = bytearray(MAX_DATA_LEN)
        self.peers_table = {}

    def active(self, a=None):
        if a is None:
            return self._an
        self._an = bool(a)
        hw.en_active(1 if a else 0)

    def config(self, *a, **k):
        return 0

    def add_peer(self, mac, *a, **k):
        mac = bytes(mac)
        if len(mac) != 6:
            raise ValueError("invalid peer")
        if mac in self._peers:
            raise OSError(-12395, "ESP_ERR_ESPNOW_EXIST")
        if len(self._peers) >= 20:
            raise OSError(-12394, "ESP_ERR_ESPNOW_FULL")
        self._peers.append(mac)

    def del_peer(self, mac):
        mac = bytes(mac)
        if mac not in self._peers:
            raise OSError(-12393, "ESP_ERR_ESPNOW_NOT_FOUND")
        self._peers.remove(mac)

    def get_peers(self):
        return tuple((p, 0, 0, False) for p in self._peers)

    def send(self, mac, msg=None, sync=True):
        if msg is None:
            msg = mac
            ziele = self._peers
        else:
            mac = bytes(mac)
            if mac not in self._peers:
                raise OSError(-12393, "ESP_ERR_ESPNOW_NOT_FOUND")
            ziele = (mac,)
        if not self._an:
            raise OSError(-12396, "ESP_ERR_ESPNOW_NOT_INIT")
        if isinstance(msg, str):
            msg = msg.encode()
        msg = bytes(msg)
        if len(msg) > MAX_DATA_LEN:
            raise ValueError("msg too long")
        ok = True
        for z in ziele:
            if not hw.en_send(uctypes.addressof(z), uctypes.addressof(msg), len(msg)):
                ok = False
        return ok

    def any(self):
        return bool(hw.en_any())

    def irecv(self, timeout_ms=None):
        n = hw.en_recv(uctypes.addressof(self._mac), uctypes.addressof(self._puffer),
                       -1 if timeout_ms is None else int(timeout_ms))
        if n < 0:
            return (None, None)
        mac = bytes(self._mac)
        self.peers_table[mac] = [int(hw.en_rssi()), time.ticks_ms()]
        return (mac, self._puffer[:n])

    def recv(self, timeout_ms=None):
        mac, msg = self.irecv(timeout_ms)
        if mac is None:
            return [None, None]
        return [mac, bytes(msg)]

    def __iter__(self):
        return self

    def __next__(self):
        return self.irecv()

    def stats(self):
        return (0, 0, 0, 0, 0)
