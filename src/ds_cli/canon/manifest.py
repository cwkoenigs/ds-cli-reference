"""``.ds/manifest.toml``: load, validate, write.

Mirrors ``ds/canon/manifest.py`` in docs/ds-cli-updates.md. A malformed manifest is an error
that fails ``reconcile --check``; a pending standard never is.
"""
from __future__ import annotations

import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

from .client import Canon

STATUSES = ("adopted", "declined", "pending")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MANIFEST_REL = Path(".ds/manifest.toml")


class ManifestError(Exception):
    """The manifest is missing, not TOML, or violates the schema."""


@dataclass
class Entry:
    id: str
    status: str
    version: int
    by: str | None = None
    on: str | None = None
    reason: str | None = None
    revisit: str | None = None

    def to_toml(self) -> dict:
        d: dict = {"status": self.status, "version": self.version}
        for k in ("by", "on", "reason", "revisit"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


@dataclass
class Manifest:
    path: Path
    name: str
    tags: list[str]
    repo_extra: dict = field(default_factory=dict)   # created, interview, ds_version, ...
    entries: dict[str, Entry] = field(default_factory=dict)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dump(self))


def _err(path: Path, msg: str) -> ManifestError:
    return ManifestError(f"{path}: {msg}")


def load(path: Path, canon: Canon | None = None) -> Manifest:
    path = Path(path)
    if not path.exists():
        raise _err(path, "missing")
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise _err(path, f"not valid TOML: {e}") from None
    repo = raw.get("repo")
    if not isinstance(repo, dict):
        raise _err(path, "missing [repo] table")
    name = repo.get("name")
    tags = repo.get("tags")
    if not isinstance(name, str) or not name:
        raise _err(path, "[repo].name must be a non-empty string")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise _err(path, "[repo].tags must be a list of strings")
    extra = {k: v for k, v in repo.items() if k not in ("name", "tags")}
    entries: dict[str, Entry] = {}
    stds = raw.get("standards", {})
    if not isinstance(stds, dict):
        raise _err(path, "[standards] must be a table")
    for sid, ent in stds.items():
        if not isinstance(ent, dict):
            raise _err(path, f"[standards.{sid}] must be a table")
        status = ent.get("status")
        if status not in STATUSES:
            raise _err(path, f"[standards.{sid}].status must be one of {', '.join(STATUSES)}")
        version = ent.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise _err(path, f"[standards.{sid}].version must be an integer >= 1")
        e = Entry(sid, status, version, ent.get("by"), ent.get("on"), ent.get("reason"), ent.get("revisit"))
        if status in ("adopted", "declined"):
            if not e.by:
                raise _err(path, f"[standards.{sid}] {status} requires `by`")
            if not e.on or not DATE_RE.match(e.on):
                raise _err(path, f"[standards.{sid}] {status} requires `on` as YYYY-MM-DD")
        if status == "declined":
            if not e.reason:
                raise _err(path, f"[standards.{sid}] declined requires `reason`")
            if not e.revisit or not DATE_RE.match(e.revisit):
                raise _err(path, f"[standards.{sid}] declined requires `revisit` as YYYY-MM-DD")
        if canon is not None and sid not in canon.standards:
            raise _err(path, f"[standards.{sid}] is not a standard in the canon")
        entries[sid] = e
    return Manifest(path, name, tags, extra, entries)


def dump(m: Manifest) -> str:
    doc: dict = {"repo": {"name": m.name, "tags": m.tags, **m.repo_extra},
                 "standards": {sid: e.to_toml() for sid, e in sorted(m.entries.items())}}
    return tomli_w.dumps(doc)


def for_repo(repo: Path, canon: Canon | None = None) -> Manifest:
    return load(Path(repo) / MANIFEST_REL, canon)
