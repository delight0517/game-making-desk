"""Synthetic receipt tests; not real gameplay or upload acceptance."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / "desk/delivery.py"
spec = importlib.util.spec_from_file_location("delivery", SOURCE)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def file(self, name, content=b"fixture"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {"path": name, "sha256": hashlib.sha256(content).hexdigest()}

    def save(self, evidence):
        (self.root / "DELIVERY-EVIDENCE.json").write_text(json.dumps(evidence))

    def codex(self):
        result = self.file("result.json", b'{"draft":"synthetic template result"}')
        (self.root / "CODEX-STUDIO-RECEIPT.json").write_text(json.dumps({
            "provider":"codex", "status":"completed", "sourceCommit":"fixture", "template":"fixture.md",
            "resultFile":result["path"], "resultSha256":result["sha256"], "jobId":"fixture"}))

    def full_fixture(self):
        self.codex()
        doc_path = self.root / "plan.docx"
        with zipfile.ZipFile(doc_path, "w") as doc:
            doc.writestr("word/document.xml", "<document>synthetic</document>")
        doc = {"path":"plan.docx", "sha256":hashlib.sha256(doc_path.read_bytes()).hexdigest()}
        movie = self.file("movie.mp4")
        return {"baseline":{"sources":[self.file("old-plan.md"),self.file("logic.lua")]},
            "requirements":{"studioAlternativeAccepted":True,"acceptanceEvidence":"synthetic acceptance fixture"},
            "document":{"reviewed":True,"files":[doc],"comparison":self.file("comparison.md")},
            "game":{"candidateFiles":[self.file("intro.lua")],"runtime":{"kind":"actual-gameplay",
                    "checks":dict.fromkeys(["intro","transition","interaction","outcome"],True),"evidence":[self.file("observed.json")]}},
            "video":{"file":movie,"probe":self.file("probe.json",json.dumps({"format":{"duration":"12.4"},"streams":[{"codec_type":"video"}]}).encode()),
                     "contentVerified":True,"includesUpdatedGameplay":True},
            "upload":{"destination":"synthetic-only","verifiedAt":"fixture","items":[
                {"kind":"document","sha256":doc["sha256"],"remoteId":"fixture-doc"},
                {"kind":"video","sha256":movie["sha256"],"remoteId":"fixture-video"}]}}

    def test_answers_do_not_complete_anything(self):
        self.file("answers.json", b'{"items":{"q":{"status":"submitted"}}}')
        result = delivery.evaluate_delivery(self.root)
        self.assertFalse(result["complete"])
        self.assertFalse(any(s["complete"] for s in result["stages"]))

    def test_failed_claude_subtype_success_is_not_success(self):
        self.file("CLAUDE-STUDIO-REVIEW.json", b'{"subtype":"success","is_error":true,"terminal_reason":"api_error","result":"ConnectionRefused"}')
        self.assertFalse(delivery.evaluate_delivery(self.root)["stages"][1]["complete"])

    def test_codex_result_hash_must_match(self):
        self.codex()
        self.assertTrue(delivery.evaluate_delivery(self.root)["stages"][1]["complete"])
        self.file("result.json", b'{"draft":"tampered"}')
        self.assertFalse(delivery.evaluate_delivery(self.root)["stages"][1]["complete"])

    def test_candidates_and_storyboard_video_are_not_gameplay(self):
        evidence = self.full_fixture()
        evidence["game"]["runtime"]["kind"] = "offline-test"
        self.save(evidence)
        result = delivery.evaluate_delivery(self.root)
        self.assertTrue(result["stages"][3]["candidateReady"])
        self.assertFalse(result["stages"][3]["complete"])
        self.assertTrue(result["stages"][4]["videoFileReady"])
        self.assertFalse(result["stages"][4]["complete"])
        self.assertFalse(result["stages"][5]["complete"])

    def test_matched_receipts_pass_but_original_requirement_stays_separate(self):
        evidence = self.full_fixture()
        self.save(evidence)
        self.assertTrue(delivery.evaluate_delivery(self.root)["complete"])
        evidence["requirements"] = {}
        self.save(evidence)
        result = delivery.evaluate_delivery(self.root)
        self.assertTrue(result["artifactsComplete"])
        self.assertFalse(result["complete"])

    def test_upload_old_hash_cannot_complete(self):
        evidence = self.full_fixture()
        evidence["upload"]["items"][0]["sha256"] = "0" * 64
        self.save(evidence)
        self.assertFalse(delivery.evaluate_delivery(self.root)["stages"][5]["complete"])


if __name__ == "__main__":
    unittest.main()
