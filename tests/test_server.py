"""Fresh-profile API checks; no AI, real project data or external account calls."""
from pathlib import Path
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import urllib.error


class FreshServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.temp.name)
        source = Path(__file__).resolve().parents[1] / "desk"
        for file in source.iterdir():
            if file.is_file() and file.suffix in (".py", ".js", ".html", ".json", ".png"):
                shutil.copy2(file, cls.data / file.name)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.url = f"http://127.0.0.1:{cls.port}"
        cls.process = subprocess.Popen([sys.executable, str(source / "server.py"),
                                        "--port", str(cls.port), "--data-dir", str(cls.data)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                urllib.request.urlopen(cls.url + "/api/desk", timeout=1).close()
                return
            except (OSError, urllib.error.URLError):
                time.sleep(.1)
        cls.process.terminate()
        raise RuntimeError("Fresh server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.temp.cleanup()

    def post(self, data, origin=None):
        request = urllib.request.Request(self.url + "/api/answer",
                    data=json.dumps(data).encode(), headers={"Content-Type": "application/json",
                    "Origin": origin or self.url}, method="POST")
        return urllib.request.urlopen(request, timeout=3)

    def test_fresh_utf8_save_and_stale_revision(self):
        with urllib.request.urlopen(self.url + "/api/desk") as response:
            before = json.load(response)
        data = {"questionId": "sample-1", "text": "새로운 장면", "status": "draft",
                "revision": before["answers"]["revision"]}
        with self.post(data) as response:
            saved = json.load(response)
        self.assertEqual(saved["items"]["sample-1"]["text"], "새로운 장면")
        self.assertTrue((self.data / "answers.json").is_file())
        self.assertTrue(list((self.data / "backups").glob("*-answers.json")))
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post(data)
        self.assertEqual(error.exception.code, 409)

    def test_foreign_origin_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post({"questionId": "sample-1", "text": "ignored", "status": "draft", "revision": 0},
                      "https://unrelated.example")
        self.assertEqual(error.exception.code, 403)

    def test_ui_and_storyboard_sample_available(self):
        with urllib.request.urlopen(self.url + "/") as response:
            self.assertIn("스토리보드", response.read().decode("utf-8"))
        with urllib.request.urlopen(self.url + "/doc-image-1.png") as response:
            self.assertEqual(response.read(8), b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
