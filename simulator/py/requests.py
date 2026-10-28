# Nachbau von "requests" fuer den espBoard-Simulator: die Anfrage stellt
# der Browser (synchrones XMLHttpRequest im Web Worker).
import json as _json
import simhw as hw

SIMULATOR = True


class Response:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text
        self.content = text.encode()
        self.reason = b""

    def json(self):
        return _json.loads(self.text)

    def close(self):
        pass


def request(method, url, data=None, json=None, headers=None, timeout=None, **kw):
    if json is not None:
        data = _json.dumps(json)
    if isinstance(data, (bytes, bytearray)):
        data = data.decode()
    antwort = str(hw.http(method, url, "" if data is None else data, 0 if data is None else 1))
    status, _, text = antwort.partition("\n")
    status = int(status)
    if status == 0:
        raise OSError("keine Verbindung: " + text)
    return Response(status, text)


def get(url, **kw):
    return request("GET", url, **kw)


def post(url, **kw):
    return request("POST", url, **kw)


def put(url, **kw):
    return request("PUT", url, **kw)


def patch(url, **kw):
    return request("PATCH", url, **kw)


def delete(url, **kw):
    return request("DELETE", url, **kw)
