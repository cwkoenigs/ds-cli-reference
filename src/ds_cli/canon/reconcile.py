"""``reconcile``: the one verb. ``check`` is offline and deterministic; ``adopt`` and ``decline``
record a decision in the manifest.

Exit codes follow the design: pending standards are information; only a broken pointer or a
malformed manifest fails.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import derived, manifest as manifest_mod
from .client import BadPin, Canon, UnknownStandard

DOC_FILES = ("README.md", "AGENTS.md", "DECISIONS.md")
LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def relative_links(text: str) -> list[str]:
    """Targets of inline links that are relative paths (no scheme, no anchor-only, no pointer)."""
    out = []
    for m in LINK_RE.finditer(text):
        t = m.group(1).split("#")[0]
        if not t or "://" in t or t.startswith(("mailto:", "/", "[[")):
            continue
        out.append(t)
    return out


@dataclass
class Finding:
    level: str      # error | pending | info
    code: str       # manifest | pointer | pin-stale | derived | new | outdated | pending | revisit
    message: str
    where: str = ""


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)
    duration_s: float = 0.0

    def _of(self, level: str) -> list[Finding]:
        return [f for f in self.findings if f.level == level]

    @property
    def errors(self) -> list[Finding]:
        return self._of("error")

    @property
    def pending(self) -> list[Finding]:
        return self._of("pending")

    @property
    def info(self) -> list[Finding]:
        return self._of("info")

    @property
    def exit_code(self) -> int:
        return 1 if self.errors else 0

    def pending_ids(self) -> list[str]:
        return [f.where for f in self.pending]


def doc_files(repo: Path) -> list[Path]:
    repo = Path(repo)
    files = [repo / f for f in DOC_FILES if (repo / f).exists()]
    docs = repo / "docs"
    if docs.is_dir():
        files += sorted(p for p in docs.rglob("*.md") if "rendered" not in p.relative_to(docs).parts)
    return files


def check(repo: Path, canon: Canon, regen: bool = True) -> CheckResult:
    t0 = time.perf_counter()
    repo = Path(repo)
    r = CheckResult()

    # 1. manifest well-formed
    try:
        m = manifest_mod.for_repo(repo, canon)
    except manifest_mod.ManifestError as e:
        r.findings.append(Finding("error", "manifest", str(e), str(manifest_mod.MANIFEST_REL)))
        m = None

    # 2. every pointer resolves
    for f in doc_files(repo):
        rel = str(f.relative_to(repo))
        for ptr in canon.pointers(f.read_text()):
            try:
                res = canon.resolve(ptr.id, ptr.pinned)
            except UnknownStandard:
                r.findings.append(Finding("error", "pointer", f"{ptr.raw} does not resolve: unknown standard", rel))
                continue
            except BadPin as e:
                r.findings.append(Finding("error", "pointer", f"{ptr.raw} does not resolve: {e}", rel))
                continue
            if res.stale:
                r.findings.append(Finding("info", "pin-stale",
                                          f"{ptr.raw} is pinned below the current version {res.standard.version}", rel))

    # 2b. relative links between repo files resolve (reported, never blocking: the audit's job)
    for f in doc_files(repo):
        rel = str(f.relative_to(repo))
        for target in relative_links(f.read_text()):
            if not (f.parent / target).exists():
                r.findings.append(Finding("info", "link", f"link target `{target}` not found", rel))

    # 3. derived docs regenerated
    if regen and derived.regenerate(repo):
        r.findings.append(Finding("info", "derived", "derived block regenerated", "AGENTS.md"))

    # 4. pending standards
    if m is not None:
        today = date.today().isoformat()
        for std in canon.applicable(m.tags):
            e = m.entries.get(std.id)
            key = f"{std.id}@{std.version}"
            if e is None:
                r.findings.append(Finding("pending", "new", f"{key} — {std.title} (new; applies because tags match {list(std.applies_to)})", key))
            elif e.version != std.version:
                r.findings.append(Finding("pending", "outdated", f"{key} — {std.title} (manifest has v{e.version}, {e.status})", key))
            elif e.status == "pending":
                r.findings.append(Finding("pending", "pending", f"{key} — {std.title} (undecided)", key))
            elif e.status == "declined" and e.revisit and e.revisit <= today:
                r.findings.append(Finding("info", "revisit", f"{std.id} declined by {e.by}; revisit date {e.revisit} has passed", std.id))
    r.duration_s = time.perf_counter() - t0
    return r


def _record(repo: Path, canon: Canon, std_id: str, status: str, by: str, **extra: str | None) -> manifest_mod.Entry:
    m = manifest_mod.for_repo(repo, canon)
    std = canon.get(std_id)
    e = manifest_mod.Entry(std_id, status, std.version, by, date.today().isoformat(),
                           extra.get("reason"), extra.get("revisit"))
    m.entries[std_id] = e
    m.save()
    return e


def adopt(repo: Path, canon: Canon, std_id: str, by: str) -> manifest_mod.Entry:
    return _record(repo, canon, std_id, "adopted", by)


def decline(repo: Path, canon: Canon, std_id: str, by: str, reason: str, revisit: str) -> manifest_mod.Entry:
    if not reason:
        raise manifest_mod.ManifestError("decline requires a reason")
    return _record(repo, canon, std_id, "declined", by, reason=reason, revisit=revisit)
