"""Single committed hierarchy, revision guards, subprocesses and durable transactions."""

import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import RLock

from legoworld.backend import uid
from legoworld.document import empty, entries


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uid() + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class Project:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.outputs = self.workspace / "outputs"
        self.state_path = self.outputs / "project.json"
        self.document = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.is_file() else empty()
        self.lock = RLock()
        self.reports, self.images = {}, {}
        self.worker_calls = 0

    @property
    def revision(self):
        return self.document["revision"]

    def stale(self, expected):
        if type(expected) is not int or expected != self.revision:
            return {"ok": False, "error": {"type": "stale_revision", "expected": expected,
                                          "current_revision": self.revision}, "revision": self.revision}
        return None

    def create(self, name, expected_revision):
        with self.lock:
            conflict = self.stale(expected_revision)
            if conflict:
                return conflict
            doc = empty(name)
            doc["revision"] = self.revision + 1
            self.commit(doc, {"action": "create_model"})
            return {"ok": True, "revision": self.revision, "root_id": "root", "name": name}

    def worker(self, action, document=None, timeout_seconds=120, **kwargs):
        self.worker_calls += 1
        self.outputs.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="worker-", dir=self.outputs) as folder:
            root = Path(folder)
            request_path, response_path, log_path = root / "request.json", root / "response.json", root / "worker.log"
            write_json(request_path, {"action": action, "document": document if document is not None else self.document,
                                      "workspace": str(self.workspace), **kwargs})
            env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1")
            env.setdefault("OPENBLAS_NUM_THREADS", "1")
            try:
                with log_path.open("wb") as log:
                    process = subprocess.run([sys.executable, "-X", "utf8", "-m", "legoworld.worker",
                        str(request_path), str(response_path)], cwd=self.workspace, env=env,
                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=timeout_seconds,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if process.returncode != 0 or not response_path.is_file():
                    result = {"ok": False, "error": {"type": "worker_exit", "exit_code": process.returncode}}
                else:
                    result = json.loads(response_path.read_text(encoding="utf-8"))
            except subprocess.TimeoutExpired:
                result = {"ok": False, "error": {"type": "worker_timeout", "seconds": timeout_seconds}}
            with log_path.open("rb") as log:
                log.seek(max(0, log_path.stat().st_size - 65536))
                result["log"] = log.read().decode("utf-8", errors="replace")
            return result

    def commit(self, document, event, report=None):
        revision_dir = self.outputs / "projects" / document["model_id"] / "revisions" / str(document["revision"])
        write_json(revision_dir / "project.json", document)
        write_json(revision_dir / "event.json", event)
        if report is not None:
            write_json(revision_dir / "validation.json", report)
        # The active snapshot is the commit point; failed writes never replace in-memory state.
        write_json(self.state_path, document)
        self.document = document
        self.reports.clear()
        self.images.clear()
        if report is not None:
            self.reports[False] = deepcopy(report)

    def mutate(self, action, expected_revision, timeout_seconds=120, **kwargs):
        with self.lock:
            conflict = self.stale(expected_revision)
            if conflict:
                return conflict
            if not 0 < timeout_seconds <= 600:
                raise ValueError("timeout_seconds must be in (0, 600]")
            if "path" in kwargs:
                source = Path(kwargs["path"])
                source = (self.workspace / source).resolve() if not source.is_absolute() else source.resolve()
                if action == "build" and not source.is_relative_to(self.workspace):
                    raise ValueError("Build scripts must be inside this workspace")
                kwargs["path"] = str(source)
            result = self.worker(action, timeout_seconds=timeout_seconds, **kwargs)
            doc = result.pop("document", None)
            if result["ok"]:
                self.commit(doc, {"action": action, "arguments": kwargs, "log": result.get("log", "")}, result["validation"])
            else:
                candidate_id = uid()
                write_json(self.outputs / "candidates" / (candidate_id + ".json"),
                           {"document": doc, "result": result, "base_revision": self.revision})
                result["candidate_id"] = candidate_id
            result["revision"] = self.revision
            return result

    def selected_document(self, candidate_id=None):
        if candidate_id is None:
            return deepcopy(self.document)
        if not re.fullmatch(r"[0-9a-f]{32}", candidate_id):
            raise ValueError("Invalid candidate ID")
        record = json.loads((self.outputs / "candidates" / (candidate_id + ".json")).read_text(encoding="utf-8"))
        if record["document"] is None:
            raise ValueError("This attempt failed before producing a candidate model")
        return record["document"]

    def validate(self, stability=False, candidate_id=None):
        with self.lock:
            if candidate_id is None and stability in self.reports:
                return deepcopy(self.reports[stability])
            result = self.worker("validate", self.selected_document(candidate_id), stability=stability)
            if not result["ok"]:
                raise ValueError(result)
            if candidate_id is None:
                self.reports[stability] = result["validation"]
            return deepcopy(result["validation"])

    def render(self, candidate_id=None, **options):
        with self.lock:
            key = json.dumps([candidate_id, options], sort_keys=True)
            if key not in self.images:
                result = self.worker("render", self.selected_document(candidate_id), **options)
                if not result["ok"]:
                    raise ValueError(result)
                self.images[key] = base64.b64decode(result["png"])
            return self.images[key]

    def tree(self, target_id="root", depth=1, offset=0, limit=100):
        with self.lock:
            if not 0 <= depth <= 20 or not 1 <= limit <= 500 or offset < 0:
                raise ValueError("Use depth 0..20, limit 1..500 and nonnegative offset")
            nodes = entries(self.document)
            if target_id not in nodes:
                raise KeyError(target_id)
            selected = [v for k, v in nodes.items() if (k == target_id or k.startswith(target_id + "/"))
                        and k.count("/") - target_id.count("/") <= depth]
            for item in selected:
                if item["assembly"]:
                    item["ports"] = list(self.document["definitions"][item["definition"]]["ports"])
            return {"revision": self.revision, "root_id": "root", "nodes": selected[offset:offset+limit],
                    "total": len(selected), "has_more": offset+limit < len(selected)}

    def save_checkpoint(self):
        with self.lock:
            checkpoint = uid()
            write_json(self.outputs / "checkpoints" / (checkpoint + ".json"), self.document)
            return {"checkpoint_id": checkpoint, "revision": self.revision}

    def restore_checkpoint(self, checkpoint_id, expected_revision):
        if not re.fullmatch(r"[0-9a-f]{32}", checkpoint_id):
            raise ValueError("Invalid checkpoint ID")
        return self.mutate("import", expected_revision,
                           path=str(self.outputs / "checkpoints" / (checkpoint_id + ".json")))

    def export(self):
        with self.lock:
            result = self.worker("export")
            if not result["ok"]:
                return {**result, "revision": self.revision}
            self.reports[True] = result["validation"]
            from legoworld.studio_io import write_io
            name = re.sub(r"[^\w-]+", "_", self.document["name"]).strip("_") or "model"
            directory = self.outputs / name
            directory.mkdir(parents=True, exist_ok=True)
            text = result.pop("mpd_text")
            (directory / "model.mpd").write_text(text, encoding="utf-8")
            write_io(directory / "model.io", text)
            write_json(directory / "project.json", self.document)
            write_json(directory / "validation.json", result["validation"])
            (directory / "preview.png").write_bytes(self.render(four_views=True))
            return {"ok": True, "revision": self.revision, "parts": result["validation"]["parts"],
                    **{k: str(directory / f) for k, f in (("mpd", "model.mpd"), ("io", "model.io"),
                         ("project", "project.json"), ("preview", "preview.png"), ("validation", "validation.json"))}}
