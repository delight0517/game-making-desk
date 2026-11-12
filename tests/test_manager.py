"""Synthetic controller tests, with no live Codex or gameplay execution."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desk"))
from production_manager import ProductionManager, CANDIDATE


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        def read(path, default):
            return json.loads(path.read_text()) if path.exists() else default
        def write(path, value):
            path.write_text(json.dumps(value))
        self.manager = ProductionManager(self.root, read, write)

    def tearDown(self):
        self.manager.stop()
        self.temp.cleanup()

    def test_stop_before_any_job_is_safe(self):
        self.assertEqual(self.manager.stop()["status"], "stopped")

    def test_deadline_anchored_and_repeated_start_does_not_extend(self):
        target = time.time() + 400
        first = self.manager.start(deadline=target)
        second = self.manager.start(minutes=20)
        self.assertEqual(first["deadline"], target)
        self.assertEqual(second["deadline"], target)

    def test_existing_writer_blocks_dispatch(self):
        self.manager.start()
        with self.assertRaisesRegex(ValueError, "인계"):
            self.manager.run_candidate()
        self.assertFalse(self.manager.snapshot()["candidateWriteReady"])

    def test_bad_handoff_hash_does_not_grant_write(self):
        path = self.root / CANDIDATE
        path.parent.mkdir(parents=True)
        path.write_text("return {}")
        with self.assertRaises(ValueError):
            self.manager.release_candidate("0" * 64)
        self.assertFalse(self.manager.snapshot()["candidateWriteReady"])

    def test_explicit_handoff_auto_dispatches_once(self):
        path = self.root / CANDIDATE
        path.parent.mkdir(parents=True)
        path.write_text("return {}")
        calls = []
        ready = threading.Event()
        def fake_run():
            calls.append(1)
            ready.set()
        self.manager.run_candidate = fake_run
        self.manager.start(deadline=time.time() + 400)
        self.manager.release_candidate(hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertTrue(ready.wait(3))
        self.manager._wake.set()
        time.sleep(.05)
        self.assertEqual(len(calls), 1)

    def test_completion_worker_requires_real_handoff_file(self):
        with self.assertRaises(ValueError):
            self.manager.record_worker("fixture", "completed", "test invocation")
        path = self.root / "handoff.md"
        path.write_text("synthetic")
        state = self.manager.record_worker("fixture", "completed", "test invocation", ["handoff.md"])
        self.assertEqual(state["workers"][0]["evidence"][0]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_two_module_cap_and_no_duplicate_dispatch(self):
        for name in ["submission/Game-Project-Updated-Planning.html",CANDIDATE]:
            path = self.root / name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("synthetic")
        gate=threading.Event()
        calls=[]
        def fake(module_id,token,data):
            calls.append(module_id)
            gate.wait(3)
        self.manager._run_module=fake
        # Keep background loop dormant during deterministic dispatch checks.
        self.manager.state.update(status="running",deadline=time.time()+300)
        self.manager.run_module("document-consistency")
        self.manager.run_module("game-semantic-review")
        duplicate=self.manager.run_module("document-consistency")
        self.assertEqual(len(calls),2)
        self.assertEqual(len(duplicate["moduleJobs"]),2)
        source=self.root/CANDIDATE
        self.manager.handoff_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,"두 모듈"):
            self.manager.run_candidate()
        gate.set()

    def test_stop_kills_every_owned_parallel_process(self):
        first,second=Mock(),Mock()
        first.pid,second.pid=101,202
        first.poll.return_value=second.poll.return_value=None
        self.manager.processes={"a":first,"b":second}
        self.manager.state["moduleJobs"]={"a":{"status":"running"},"b":{"status":"queued"}}
        with patch("production_manager.subprocess.run") as kill:
            result=self.manager.stop()
            self.assertEqual(kill.call_count,2)
        self.assertEqual({j["status"] for j in result["moduleJobs"].values()},{"cancelled"})
        self.manager.processes={}


if __name__ == "__main__":
    unittest.main()
