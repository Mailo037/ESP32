# Startet main.py wie auf dem echten ESP32 - nur mit nachgebauter Hardware.
import sys
import _sim_time
import _sim_machine
import _sim_network
import _sim_espnow

sys.modules["time"] = _sim_time
sys.modules["utime"] = _sim_time
sys.modules["machine"] = _sim_machine
sys.modules["network"] = _sim_network
sys.modules["espnow"] = _sim_espnow
if "" not in sys.path:
    sys.path.insert(0, "")
if "/" not in sys.path:
    sys.path.insert(0, "/")
if "/lib" not in sys.path:
    sys.path.insert(0, "/lib")


def _starten():
    try:
        with open("/boot.py") as f:
            boot = f.read()
    except OSError:
        boot = None
    if boot is not None:
        exec(boot, {"__name__": "__boot__"})
        if getattr(sys, "_hub_update_fehler", False):
            raise RuntimeError("Hub-Update muss fortgesetzt werden")
    with open("/main.py") as f:
        quelltext = f.read()
    g = {"__name__": "__main__", "__file__": "main.py"}
    try:
        exec(quelltext, g)
    except SystemExit:
        pass
    except BaseException as e:
        print("-" * 32)
        sys.print_exception(e)
        print("Programm beendet (Fehler).")
        return
    print("Programm beendet.")


_starten()
