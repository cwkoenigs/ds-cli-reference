"""Fixtures for the knowledge-system tests: a three-standard canon and one repository."""
from pathlib import Path

import pytest

# ---- knowledge-system fixtures: a three-standard canon and one repository ----
import json
import subprocess

STANDARDS = {
    "adr-000": ("Repo knowledge system", ["*"], "Every fact exists once.\n\n## Apply\n- Keep a manifest.\n"),
    "layout": ("Repository layout", ["*"], "src/<package>/ for code, tests/ for tests.\n"),
    "adr-014": ("uv, not pixi", ["python", "package"], "All Python repos use uv.\n\n## Apply\n- Replace pixi.toml.\n"),
}


def write_canon(root: Path, versions: dict | None = None) -> Path:
    canon = root / "canon"
    (canon / "adr").mkdir(parents=True, exist_ok=True)
    index = []
    for sid, (title, applies, body) in STANDARDS.items():
        v = (versions or {}).get(sid, 1)
        rel = f"adr/{sid}.md" if sid.startswith("adr-") else f"{sid}.md"
        (canon / rel).write_text(f"---\nid: {sid}\nversion: {v}\ntitle: {title}\n---\n\n# {title}\n\n{body}")
        index.append({"id": sid, "version": v, "title": title, "applies_to": applies, "owner": "ck", "hash": "x", "path": rel})
    (canon / "index.json").write_text(json.dumps({"generated": "2026-10-14", "standards": index}))
    return canon


def write_repo(root: Path, name: str = "claims-features") -> Path:
    repo = root / name
    (repo / "src/pkg").mkdir(parents=True)
    (repo / ".ds").mkdir()
    (repo / "src/pkg/mod.py").write_text("def load_claims():\n    return []\n")
    (repo / "README.md").write_text("# claims-features\n\n<!-- ds:local interview 2026-10-14 -->\nFeature store. Follows [[layout]] and [[adr-014]].\n")
    (repo / "AGENTS.md").write_text("# AGENTS.md\n\n- Test command: `python -c pass`\n\nStandards: [[adr-000]] [[layout]] [[adr-014]]\n")
    (repo / "DECISIONS.md").write_text("# Local decisions\n\nNone yet.\n")
    (repo / ".ds/manifest.toml").write_text(
        '[repo]\nname = "claims-features"\ntags = ["python", "package"]\n\n' +
        "".join(f'[standards.{sid}]\nstatus = "adopted"\nversion = 1\nby = "ck"\non = "2026-10-14"\n\n' for sid in STANDARDS))
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    return repo


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@local", *args],
                          capture_output=True, text=True, check=check)


