"""Hardware-free integration checks with an isolated emulated board filesystem."""
import ast
import builtins
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
import os as host_os
import io

ROOT = Path(__file__).resolve().parents[1]


class PowerCut(BaseException):
    pass


class Board:
    def __init__(self, directory):
        self.root = Path(directory)
        self.modules = {}
        self.cut = None
        self.renames = 0
        self.os = types.SimpleNamespace(stat=lambda p: self.path(p).stat(),
            listdir=lambda p="/": host_os.listdir(self.path(p)),
            mkdir=lambda p: self.path(p).mkdir(), remove=lambda p: self.path(p).unlink(),
            rmdir=lambda p: self.path(p).rmdir(), rename=self.rename, sync=lambda: None,
            statvfs=lambda p: (4096, 4096, 0, 1024))
        self.modules.update(os=self.os, sys=types.SimpleNamespace(modules={}, path=[]),
            machine=types.SimpleNamespace(Pin=lambda *a, **k: None, ADC=lambda *a, **k: None,
                PWM=lambda *a, **k: None, reset=self.reset, unique_id=lambda: b"\x01\x02\x03\x04\x05\x06"),
            time=types.SimpleNamespace(sleep_ms=lambda ms: None))
        self.resets = 0

    def path(self, p):
        result = self.root / str(p).lstrip("/")
        if not result.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Escaped test filesystem")
        return result

    def open(self, p, *a, **k):
        return builtins.open(self.path(p), *a, **k)

    def rename(self, a, b):
        self.renames += 1
        if self.cut == self.renames:
            raise PowerCut()
        host_os.replace(self.path(a), self.path(b))

    def reset(self):
        self.resets += 1

    def load(self, name):
        source = (ROOT / (name + ".py")).read_text(encoding="utf-8")
        env = dict(vars(builtins))
        def importing(n, *args, **kwargs):
            return self.modules[n] if n in self.modules else builtins.__import__(n, *args, **kwargs)
        env.update(open=self.open, __import__=importing)
        module = types.ModuleType(name)
        module.__dict__["__builtins__"] = env
        exec(compile(source, name + ".py", "exec"), module.__dict__)
        self.modules[name] = module
        return module

    def write(self, name, value):
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value.encode() if isinstance(value, str) else value)

    def hub(self):
        self.write("hub_version.json", '{"version":"2.1.0"}')
        ha = self.load("hub_apps")
        ha.meldung = lambda *args: None
        ha.balken = lambda *args: None
        return ha


def metadata(name, data):
    return {"name": name, "groesse": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class Updates(unittest.TestCase):
    def test_all_sources_parse(self):
        for p in ROOT.glob("*.py"):
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))

    def staged(self, board):
        update = board.load("hub_update")
        files = []
        for name in update.FILES:
            value = ('{"version":"2.2.0"}' if name.endswith(".json") else "# NEW " + name).encode()
            board.write("hubupdate/" + name, value)
            board.write(name, "# OLD " + name)
            files.append(metadata(name, value))
        board.write("hubupdate/pending.json", json.dumps({"dateien": files}))
        return files

    def test_boot_resumes_after_every_possible_file_replace_cut(self):
        for cut in range(1, 9):
            with self.subTest(cut=cut), tempfile.TemporaryDirectory() as tmp:
                board = Board(tmp)
                files = self.staged(board)
                board.cut = cut
                with self.assertRaises(PowerCut):
                    board.load("boot")
                self.assertTrue(board.path("hubupdate/pending.json").exists())
                board.cut = None
                board.load("boot")
                for f in files:
                    self.assertEqual(hashlib.sha256(board.path(f["name"]).read_bytes()).hexdigest(), f["sha256"])
                self.assertFalse(board.path("hubupdate/pending.json").exists())

    def test_corrupt_stage_never_changes_live_firmware(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Board(tmp)
            self.staged(board)
            board.write("hubupdate/bmp280.py", "corrupt")
            board.load("boot")
            self.assertTrue(board.modules["sys"]._hub_update_fehler)
            self.assertEqual(board.path("main.py").read_text(), "# OLD main.py")

    def test_firmware_download_error_never_marks_pending_or_changes_live_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Board(tmp)
            board.hub()
            update = board.load("hub_update")
            files = []
            for name in update.FILES:
                value = b'{"version":"2.2.0"}' if name.endswith(".json") else b"x=1\n"
                files.append(metadata(name, value))
            board.write("main.py", "# OLD")
            class Net:
                def datei_laden(self, *args):
                    raise OSError("offline")
            with self.assertRaises(OSError):
                update.installieren(Net(), {"id": "a" * 64, "version": "2.2.0", "dateien": files}, None)
            self.assertFalse(board.path("hubupdate/pending.json").exists())
            self.assertEqual(board.path("main.py").read_text(), "# OLD")
            self.assertEqual(board.resets, 0)

    def test_successful_firmware_download_commits_at_boot_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Board(tmp)
            board.hub()
            update = board.load("hub_update")
            values = {n: b'{"version":"2.2.0"}' if n.endswith(".json") else b"x=2\n" for n in update.FILES}
            class Net:
                def datei_laden(self, path, target, meta, progress):
                    board.write(target, values[meta["name"]])
            meta = {"id": "a" * 64, "version": "2.2.0", "dateien": [metadata(n, v) for n, v in values.items()]}
            update.installieren(Net(), meta, None)
            self.assertEqual(board.resets, 1)
            self.assertTrue(board.path("hubupdate/pending.json").exists())
            board.load("boot")
            self.assertEqual(json.loads(board.path("hub_version.json").read_text())["version"], "2.2.0")

    def test_offline_check_returns_without_blocking_gallery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Board(tmp)
            board.hub()
            class Net:
                def __init__(self, k): pass
                def verbinden(self): raise OSError("offline")
                def trennen(self): pass
            board.modules["hub_online"] = types.SimpleNamespace(konfig_lesen=lambda: {"url": "https://test"}, Netz=Net)
            board.load("hub_update").pruefen()
            self.assertEqual(board.resets, 0)

    def test_streaming_download_checks_hash_length_and_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Board(tmp)
            online = board.load("hub_online")
            net = online.Netz({"url": "https://firmware.test", "store": "https://apps.test"})
            raw = b"hello" * 1000
            urls = []
            class Response:
                status_code = 200
                def __init__(self, data): self.raw = io.BytesIO(data)
                def close(self): pass
            def request(method, url, **kwargs):
                urls.append(url)
                return Response(raw)
            net.req = types.SimpleNamespace(request=request)
            meta = metadata("main.py", raw)
            net.datei_laden("firmware/" + "a" * 64 + "/main.py", "/download", meta)
            self.assertTrue(urls[-1].startswith("https://firmware.test/firmware/"))
            self.assertEqual(board.path("download").read_bytes(), raw)
            net.datei_laden("apps/Game", "/app", meta, extra="&datei=helper.py&paket=test")
            self.assertIn("https://apps.test/apps/Game?", urls[-1])
            self.assertIn("&datei=helper.py&paket=test", urls[-1])
            with self.assertRaises(OSError): net.datei_laden("apps/Game", "/bad", {**meta, "sha256": "0" * 64})
            self.assertFalse(board.path("bad").exists())
            with self.assertRaises(OSError): net.datei_laden("apps/Game", "/short", {**meta, "groesse": len(raw) + 1})
            self.assertFalse(board.path("short").exists())

    def test_zip_project_installs_modules_assets_and_recovers_directory_swap(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = Board(tmp)
            ha = board.hub()
            board.modules["hub_online"] = types.SimpleNamespace()
            gallery = board.load("hub_galerie")
            values = {"main.py": b"# HUB-NAME: Game\nimport helper\n", "helper.py": b"x=1\n", "assets/a.bin": b"\x00\x01"}
            app = {"id": "Game", "paket": "a" * 64, "sha256": hashlib.sha256(values["main.py"]).hexdigest(), "dateien": [metadata(n,v) for n,v in values.items()]}
            class Net:
                def datei_laden(self, path, target, meta, progress, extra):
                    board.write(target, values[meta["name"]])
            gallery.paket_installieren(Net(), app, None)
            self.assertEqual(ha.datei("Game"), "/apps/Game/main.py")
            self.assertIn("Game", ha.apps())
            self.assertTrue(ha.vertraut("Game"))
            self.assertEqual(board.path("apps/Game/assets/a.bin").read_bytes(), b"\x00\x01")
            board.write("apps/Game/helper.py", "# modified")
            self.assertFalse(ha.vertraut("Game"))
            board.rename("/apps/Game", "/apps/.alt_Game")
            ha.pakete_retten()
            self.assertIn("Game", ha.apps())
            # Download failure during an update leaves the old project usable.
            class Offline:
                def datei_laden(self, *args): raise OSError("offline")
            with self.assertRaises(OSError): gallery.paket_installieren(Offline(), app, None)
            self.assertTrue(board.path("apps/Game/main.py").exists())
            bad = {**app, "dateien": [metadata("../main.py", b"bad")]}
            with self.assertRaises(ValueError): gallery.paket_installieren(Net(), bad, None)


if __name__ == "__main__":
    unittest.main()
