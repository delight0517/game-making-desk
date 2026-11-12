"""Local modular worker registry. No external OnlyChat/BodyMod integration."""
from pathlib import Path
import hashlib

MODULES = {
    "document-consistency": {
        "label": "기획서 일관성 검토", "mode": "read-only", "version": 1,
        "inputs": ["submission/Game-Project-Updated-Planning.html", "submission/comparison.md",
                   "submission/implementation-status.json", "answers.json"],
        "goal": "Compare final planning and comparison against original user answers and implementation status. Identify contradictions, invented canon, or claims that exceed evidence. Do not ask new cosmetic questions."},
    "game-semantic-review": {
        "label": "인트로 동작 의미 검토", "mode": "read-only", "version": 1,
        "inputs": ["game-candidate/lava_fortress_demo/prologue.lua", "game-candidate/lava_fortress_demo/init.lua",
                   "game-runtime/NATIVE-LOAD-CHECK.json", "game-candidate/OFFLINE-CHECKS.json"],
        "goal": "Review Luanti prologue callback semantics, next/previous/skip, battle transition and repeat entry. Distinguish source review/server load from actual rendered gameplay. Do not propose cosmetic changes."},
}


def inputs(root, module_id):
    module = MODULES[module_id]
    found = []
    for name in module["inputs"]:
        path = Path(root) / name
        if path.is_file():
            raw = path.read_bytes()
            found.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                          "content": raw.decode("utf-8", errors="replace")[:35000]})
    return found


CONTRACT = {"version": 1, "maxParallel": 2, "writePolicy": "Only candidate-review may write its explicitly handed-off single file. Registry audit modules are read-only; reports go to manager-runs only.",
            "externalIntegration": "None. This is a local modular scheduler inspired by the user's BodyMod request."}
