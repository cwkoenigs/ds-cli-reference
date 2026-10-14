"""Canon client: locate the canon, load index.json, resolve pointers, list applicable standards.

Mirrors ``ds/canon/client.py`` in docs/ds-cli-updates.md. Offline by design: the canon is a
local checkout (``DS_CANON`` or ``--canon``); ``index.json`` is the only thing read for lookups.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

POINTER_RE = re.compile(r"\[\[([a-z0-9-]+)(?:@(\d+))?\]\]")
CODE_RE = re.compile(r"```.*?```|~~~.*?~~~|`[^`\n]*`", re.S)
FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n?", re.S)


class CanonError(Exception):
    """The canon is missing, unreadable, or does not contain what was asked for."""


class UnknownStandard(CanonError):
    pass


class BadPin(CanonError):
    pass


@dataclass(frozen=True)
class Standard:
    id: str
    version: int
    title: str
    applies_to: tuple[str, ...]
    owner: str
    hash: str
    path: str
    supersedes: str | None = None


@dataclass(frozen=True)
class Pointer:
    id: str
    pinned: int | None
    raw: str
    start: int = 0
    end: int = 0


@dataclass(frozen=True)
class Resolved:
    standard: Standard
    text: str          # body with front matter stripped
    pinned: int | None
    stale: bool        # pinned to an older version than the canon's current one


class Canon:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        index_path = self.root / "index.json"
        if not index_path.exists():
            raise CanonError(f"no index.json in {self.root}")
        data = json.loads(index_path.read_text())
        self.generated: str | None = data.get("generated")
        self.standards: dict[str, Standard] = {}
        for s in data["standards"]:
            self.standards[s["id"]] = Standard(
                id=s["id"], version=int(s["version"]), title=s["title"],
                applies_to=tuple(s["applies_to"]), owner=s.get("owner", ""),
                hash=s.get("hash", ""), path=s["path"], supersedes=s.get("supersedes"),
            )

    # -- locating -------------------------------------------------------------------------

    @classmethod
    def locate(cls, explicit: Path | str | None = None, start: Path | None = None) -> "Canon":
        """Explicit path, then ``DS_CANON``, then ``canon/`` beside the repo or its parents."""
        candidates: list[Path] = []
        if explicit:
            if not (Path(explicit) / "index.json").exists():
                raise CanonError(f"no index.json in {Path(explicit)}")
            return cls(Path(explicit))
        if os.environ.get("DS_CANON"):
            candidates.append(Path(os.environ["DS_CANON"]))
        base = Path(start or Path.cwd()).resolve()
        for up in (base, base.parent, base.parent.parent, base.parent.parent.parent):
            candidates.append(up / "canon")
        candidates.append(Path(os.environ.get("DS_HOME", Path.home() / ".ds")) / "canon")
        for c in candidates:
            if (Path(c) / "index.json").exists():
                return cls(Path(c))
        raise CanonError("canon not found: run `ds setup`, pass --canon, or set DS_CANON")

    # -- lookups --------------------------------------------------------------------------

    def get(self, std_id: str) -> Standard:
        try:
            return self.standards[std_id]
        except KeyError:
            raise UnknownStandard(std_id) from None

    def body(self, std: Standard) -> str:
        text = (self.root / std.path).read_text()
        return FRONTMATTER_RE.sub("", text, count=1).strip("\n") + "\n"

    def resolve(self, std_id: str, version: int | None = None) -> Resolved:
        """Current text of a standard. A pin above the current version is a broken pointer;
        a pin below it resolves to the current text and is flagged stale (the index holds
        only current versions; history lives in the canon's git log)."""
        std = self.get(std_id)
        if version is not None and version > std.version:
            raise BadPin(f"{std_id}@{version}: canon is at version {std.version}")
        return Resolved(std, self.body(std), version, bool(version is not None and version < std.version))

    def applicable(self, tags: list[str] | tuple[str, ...] | set[str]) -> list[Standard]:
        """Standards whose ``applies_to`` matches the repo's tags. Entries are globs over
        tags; ``*`` matches every repo."""
        out = []
        for std in self.standards.values():
            if any(pat == "*" or any(fnmatch.fnmatchcase(t, pat) for t in tags) for pat in std.applies_to):
                out.append(std)
        return sorted(out, key=lambda s: s.id)

    @staticmethod
    def pointers(text: str) -> list[Pointer]:
        """Pointers in prose. Fenced blocks and code spans are skipped, so a document may talk
        about the ``[[id]]`` syntax without making a claim."""
        masked = CODE_RE.sub(lambda m: " " * len(m.group(0)), text)
        return [Pointer(m.group(1), int(m.group(2)) if m.group(2) else None, m.group(0), m.start(), m.end())
                for m in POINTER_RE.finditer(masked)]
