"""Derived doc lines: what the code says, regenerated and never hand-edited.

Mirrors ``ds/canon/derived.py``. This prototype uses an AST walk as the stand-in for the code
graph, in the exact block format the bench scores, so the two agree on drift.
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

MARKER = "<!-- ds:derived"
MAX_LINES = 12                       # beyond this, AGENTS.md gets a per-directory summary
FULL_REL = Path(".ds/derived.md")


def public_symbols(repo: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in sorted(Path(repo).glob("src/**/*.py")):
        if p.name == "__init__.py":
            continue
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:
            continue
        names = [n.name for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_")]
        if names:
            out[str(p.relative_to(repo))] = names
    for p in sorted(Path(repo).glob("models/*.sql")):
        out.setdefault("models", []).append(p.stem)
    return out


def full_listing(symbols: dict[str, list[str]]) -> list[str]:
    return [f"- `{mod}`: " + ", ".join(f"`{n}`" for n in names) for mod, names in symbols.items()]


def summary_listing(symbols: dict[str, list[str]]) -> list[str]:
    by_dir: dict[str, list[int]] = {}
    for mod, names in symbols.items():
        d = mod.rsplit("/", 1)[0] + "/" if "/" in mod else mod
        by_dir.setdefault(d, []).append(len(names))
    return [f"- `{d}`: {len(counts)} module{'s' if len(counts) != 1 else ''}, {sum(counts)} public symbols" for d, counts in by_dir.items()]


def derived_block(repo: Path, today: str | None = None, symbols: dict[str, list[str]] | None = None) -> str:
    """The block for AGENTS.md: every public symbol when the repo is small, a per-directory
    summary pointing at ``.ds/derived.md`` when it is not."""
    symbols = public_symbols(repo) if symbols is None else symbols
    stamp = today or date.today().isoformat()
    full = full_listing(symbols)
    lines = [f"{MARKER} graph {stamp} -->", "## Public surface (derived)"]
    if len(full) > MAX_LINES:
        lines += summary_listing(symbols) + [f"Full listing: `{FULL_REL.as_posix()}`"]
    else:
        lines += full
    return "\n".join(lines) + "\n"


def full_block(repo: Path, today: str | None = None, symbols: dict[str, list[str]] | None = None) -> str:
    symbols = public_symbols(repo) if symbols is None else symbols
    return "\n".join([f"{MARKER} graph {today or date.today().isoformat()} -->", "# Public surface (derived)", "",
                       *full_listing(symbols)]) + "\n"


def _strip_date(block: str) -> str:
    return "\n".join(l for l in block.splitlines() if not l.startswith(MARKER))


def regenerate(repo: Path, file: str = "AGENTS.md") -> bool:
    """Replace the derived block in ``file``. Returns True when the file changed. The date
    line is kept when the content is unchanged, so repeated runs produce no diff."""
    p = Path(repo) / file
    if not p.exists():
        return False
    text = p.read_text()
    symbols = public_symbols(repo)
    new_block = derived_block(repo, symbols=symbols)
    full = Path(repo) / FULL_REL
    if len(full_listing(symbols)) > MAX_LINES:
        new_full = full_block(repo, symbols=symbols)
        if not full.exists() or _strip_date(full.read_text()).strip() != _strip_date(new_full).strip():
            full.parent.mkdir(exist_ok=True)
            full.write_text(new_full)
    elif full.exists():
        full.unlink()
    if MARKER in text:
        head, _, old = text.partition(MARKER)
        old_block = MARKER + old
        if _strip_date(old_block).strip() == _strip_date(new_block).strip():
            return False
        p.write_text(head + new_block)
        return True
    p.write_text(text.rstrip("\n") + "\n\n" + new_block)
    return True
