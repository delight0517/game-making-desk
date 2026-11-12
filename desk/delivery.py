"""Read-only assignment delivery gates. User answers are never completion evidence.

Call evaluate_delivery(desk_root) on each /api/desk request. Evidence is an
explicit operator record, not a claim that this module observed gameplay or an
upload. Every referenced local artifact is checked against its recorded SHA256.
See EVIDENCE_SCHEMA below for the intentionally small receipt interface.
"""
from pathlib import Path
import hashlib
import json
import zipfile

EVIDENCE_SCHEMA = {
    "baseline": {"sources": [{"path": "path/to/file", "sha256": "64 hex"}]},
    "requirements": {"studioAlternativeAccepted": False, "acceptanceEvidence": ""},
    "document": {"reviewed": False, "files": [{"path": "submission/plan.docx", "sha256": "64 hex"}],
                 "comparison": {"path": "submission/comparison.md", "sha256": "64 hex"}},
    "game": {"candidateFiles": [], "runtime": {"kind": "actual-gameplay", "checks": {
        "intro": False, "transition": False, "interaction": False, "outcome": False}, "evidence": []}},
    "video": {"file": {"path": "submission/update.mp4", "sha256": "64 hex"},
              "probe": {"path": "submission/video-probe.json", "sha256": "64 hex"},
              "contentVerified": False, "includesUpdatedGameplay": False},
    "upload": {"verifiedAt": "", "destination": "", "items": [
        {"kind": "document", "sha256": "64 hex", "remoteId": "", "url": ""},
        {"kind": "video", "sha256": "64 hex", "remoteId": "", "url": ""}]}}


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _path(root, name):
    path = Path(name)
    if path.is_absolute():
        return path
    # Earlier Codex receipts stored a workspace-relative path rather than a
    # desk-relative one. Support that exact format without guessing filenames.
    if name.replace("\\", "/").startswith("outputs/game-making-desk/"):
        return root.parent.parent / Path(name.replace("\\", "/"))
    return root / path


def _artifact(root, record):
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        return None
    expected = record.get("sha256", "")
    if not isinstance(expected, str) or len(expected) != 64:
        return None
    try:
        path = _path(root, record["path"])
        if not path.is_file() or not path.stat().st_size:
            return None
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected.lower():
            return None
        return {"path": str(path), "sha256": expected.lower(), "bytes": path.stat().st_size}
    except (OSError, ValueError):
        return None


def _artifacts(root, records):
    if not isinstance(records, list) or not records:
        return []
    results = [_artifact(root, record) for record in records]
    return results if all(results) else []


def _document_valid(artifact):
    if not artifact:
        return False
    path = Path(artifact["path"])
    try:
        if path.suffix.lower() == ".pdf":
            return path.read_bytes().startswith(b"%PDF-")
        if path.suffix.lower() == ".docx":
            with zipfile.ZipFile(path) as document:
                return "word/document.xml" in document.namelist() and document.testzip() is None
        return False
    except (OSError, zipfile.BadZipFile):
        return False


def evaluate_delivery(root):
    """Return factual stage evidence and nextAction; never mutate any file.

    DELIVERY-EVIDENCE.json is maintained by the integrating worker after real
    checks. Missing or stale receipts fail closed, while candidate outputs remain
    visible. This is evidence validation, not an OS-enforced writer gate.
    """
    root = Path(root).resolve()
    evidence = _read(root / "DELIVERY-EVIDENCE.json")
    stages = []

    def add(label, complete, next_action, found, missing, **extra):
        stages.append({"label": label, "complete": bool(complete), "status": "complete" if complete else "pending",
                       "nextAction": next_action, "evidence": found, "missing": missing, **extra})

    sources = _artifacts(root, evidence.get("baseline", {}).get("sources"))
    # Existing document image provenance is a concrete discovery receipt, but
    # cannot itself establish that game/video sources were inspected.
    provenance = _read(root / "IMAGE-SOURCES.json")
    add("자료 확인", bool(sources), "기존 기획서·게임 원본 경로와 확인한 파일을 기록",
        sources or ([{"documentId": provenance["documentId"], "scope": "기존 문서 이미지 출처"}] if provenance.get("documentId") else []),
        [] if sources else ["기획·게임 원본 확인 파일과 SHA256 기록"])

    codex = _read(root / "CODEX-STUDIO-RECEIPT.json")
    codex_file = _artifact(root, {"path": codex.get("resultFile"), "sha256": codex.get("resultSha256")})
    result = _read(codex_file["path"]) if codex_file else {}
    codex_ok = (codex.get("provider") == "codex" and codex.get("status") == "completed"
                and bool(codex.get("sourceCommit")) and bool(codex.get("template"))
                and isinstance(result.get("draft"), str) and bool(result.get("draft", "").strip()))
    claude = _read(root / "CLAUDE-STUDIO-REVIEW.json")
    claude_ok = bool(claude and claude.get("is_error") is False and claude.get("subtype") == "success"
                     and claude.get("terminal_reason") != "api_error" and claude.get("result"))
    requirements = evidence.get("requirements", {})
    alternative_accepted = (requirements.get("studioAlternativeAccepted") is True
                            and bool(requirements.get("acceptanceEvidence")))
    add("Studio 양식 · 실행", codex_ok or claude_ok, "Studio 양식을 기존 기획과 대조",
        ([{"executor": "Codex", "jobId": codex.get("jobId"), **codex_file}] if codex_ok else [])
        + ([{"executor": "Claude", "file": "CLAUDE-STUDIO-REVIEW.json"}] if claude_ok else []),
        [] if codex_ok or claude_ok else ["성공한 실행 응답과 검증 가능한 원본 결과"],
        alternateExecution=bool(codex_ok and not claude_ok),
        originalRequirementSatisfied=bool(claude_ok or (codex_ok and alternative_accepted)),
        caveat="Codex 대체 경로. 과제의 Claude 사용 조건 충족 여부는 별도 확인 필요." if codex_ok and not claude_ok and not alternative_accepted else "")

    document = evidence.get("document", {})
    docs = _artifacts(root, document.get("files"))
    comparison = _artifact(root, document.get("comparison"))
    doc_ok = bool(docs and all(_document_valid(x) for x in docs) and comparison and document.get("reviewed") is True)
    add("기획서 업데이트", doc_ok, "제출용 기획서와 기존/개선 대조표를 열어 검수",
        docs + ([comparison] if comparison else []),
        [] if doc_ok else ["검수된 DOCX/PDF 최종본", "기존/개선 내용 대조표 및 파일 해시"])

    game = evidence.get("game", {})
    candidates = _artifacts(root, game.get("candidateFiles"))
    runtime = game.get("runtime", {})
    runtime_files = _artifacts(root, runtime.get("evidence"))
    checks = runtime.get("checks", {})
    gameplay_ok = bool(candidates and runtime_files and runtime.get("kind") == "actual-gameplay"
                       and all(checks.get(k) is True for k in ("intro", "transition", "interaction", "outcome")))
    add("실제 게임 개선", gameplay_ok, "변경한 인트로·게임 진입·조작·결과를 실제 게임에서 확인",
        candidates + runtime_files, [] if gameplay_ok else ["실제 게임 플레이 확인: 인트로·전환·조작·결과"],
        candidateReady=bool(candidates), runtimeVerified=gameplay_ok)

    video = evidence.get("video", {})
    video_file = _artifact(root, video.get("file"))
    probe_file = _artifact(root, video.get("probe"))
    probe = _read(probe_file["path"]) if probe_file else {}
    streams = probe.get("streams", [])
    try:
        duration = float(probe.get("format", {}).get("duration", 0))
    except (ValueError, TypeError):
        duration = 0
    probe_ok = bool(duration > 0 and any(x.get("codec_type") == "video" for x in streams))
    video_ok = bool(video_file and probe_ok and video.get("contentVerified") is True
                    and video.get("includesUpdatedGameplay") is True and gameplay_ok)
    add("영상 업데이트", video_ok, "재생 가능한 영상에서 인트로와 변경된 실제 플레이 확인",
        ([video_file] if video_file else []) + ([probe_file] if probe_file else []),
        [] if video_ok else ["재생 검사한 영상", "개선된 실제 게임 플레이가 포함된 내용 확인"],
        videoFileReady=bool(video_file and probe_ok), actualGameplayIncluded=bool(video.get("includesUpdatedGameplay") is True and gameplay_ok))

    upload = evidence.get("upload", {})
    uploaded = upload.get("items", [])
    doc_hashes = {x["sha256"] for x in docs}
    def uploaded_item(kind, hashes):
        return any(isinstance(item, dict) and item.get("kind") == kind
                   and item.get("sha256") in hashes and (item.get("remoteId") or item.get("url")) for item in uploaded) if isinstance(uploaded, list) else False
    upload_ok = bool(doc_ok and video_ok and upload.get("destination") and upload.get("verifiedAt")
                     and uploaded_item("document", doc_hashes)
                     and uploaded_item("video", {video_file["sha256"]} if video_file else set()))
    add("제출", upload_ok, "지정된 과제 제출 위치에 최종 기획서·영상을 업로드하고 확인",
        uploaded if upload_ok else [], [] if upload_ok else ["제출 위치", "최종 파일 해시와 일치하는 실제 업로드 확인 기록"])

    current = next((i for i, stage in enumerate(stages) if not stage["complete"]), None)
    if current is not None:
        stages[current]["status"] = "current"
    all_artifacts_complete = all(stage["complete"] for stage in stages)
    assignment_ok = all_artifacts_complete and stages[1]["originalRequirementSatisfied"]
    return {"schemaVersion": 1, "complete": assignment_ok,
            "artifactsComplete": all_artifacts_complete, "currentWaypoint": None if current is None else current + 1,
            "nextAction": stages[current]["nextAction"] if current is not None else
                          ("제출 완료 확인" if assignment_ok else "Codex 대체가 원래 과제 조건을 충족하는지 확인"),
            "stages": stages,
            "scope": "로컬 증거 파일 검증. 실제 플레이·업로드는 기록된 관찰 증거 범위에서만 판정하며 이 모듈이 직접 수행하지 않습니다."}
