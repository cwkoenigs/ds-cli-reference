"""Page writers for the browser view and the team portal: every page is built from the three
kinds of line (inherited pointers, local text, derived facts). Nothing here is written into the
repo; the staged tree is build input for the docs shell (see ``docusaurus.py``)."""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..canon import derived, manifest as manifest_mod, reconcile
from ..canon.client import Canon, Standard
from .render import label, resolve_text

# The extension set the browser view uses. Tuned by fidelity/run_fidelity.py against cmark-gfm:
#   superfences  fences inside list items (fenced_code cannot)
#   escapeall    backslash hard breaks and CommonMark-style escapes
#   tilde        ~~strikethrough~~;  tasklist  - [ ] items;  magiclink  bare URLs
#   emoji        :shortcodes: with GitLab's (gemoji) index, emitted as the character itself
#   footnotes, tables, attr_list, md_in_html, toc
# sane_lists is deliberately absent: it broke two-space nested ordered lists and gained nothing.
STANDARDS_DIR = "standards"


@dataclass
class Staged:
    stage: Path
    docs: Path
    nav: list


# -- git facts (derived) -------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def git_facts(repo: Path) -> dict[str, str]:
    return {
        "branch": _git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "unknown",
        "head": _git(repo, "rev-parse", "--short", "HEAD") or "unknown",
        "last_commit": _git(repo, "log", "-1", "--format=%cs") or "unknown",
        "dirty": "yes" if _git(repo, "status", "--porcelain") else "no",
        "remote": _git(repo, "remote", "get-url", "origin") or "none",
    }


# -- page writers --------------------------------------------------------------------------

def _rel_link(from_page: Path, to_page: Path) -> str:
    return Path(os.path.relpath(to_page, from_page.parent)).as_posix()


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def write_standard_pages(canon: Canon, docs: Path) -> list[Standard]:
    """One generated page per standard: header facts, then the canon's text verbatim."""
    out = []
    for std in sorted(canon.standards.values(), key=lambda s: s.id):
        body = canon.body(std)
        head = (f"# {std.title}\n\n<!-- ds:inherited [[{std.id}@{std.version}]] -->\n"
                f"| | |\n|---|---|\n| **ID** | `{std.id}` |\n| **Version** | {std.version} |\n"
                f"| **Applies to** | {', '.join(f'`{a}`' for a in std.applies_to)} |\n| **Owner** | {std.owner} |\n"
                f"| **Source** | `{std.path}` |\n\n---\n\n")
        # the canon file starts with its own H1; demote it so the page has one title
        lines = body.splitlines()
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        _write(docs / STANDARDS_DIR / f"{std.id}.md", head + "\n".join(lines).strip("\n") + "\n")
        out.append(std)
    return out


def in_force_table(repo: Path, canon: Canon, page: Path, docs: Path) -> str:
    """Standards in force for a repo, from the manifest plus the check's pending view."""
    result = reconcile.check(repo, canon, regen=False)
    pending = {f.where.split("@")[0]: f for f in result.pending}
    try:
        m = manifest_mod.for_repo(repo)
    except manifest_mod.ManifestError as e:
        return f"**Manifest error:** {e}\n"
    rows = ["| Standard | Canon | Manifest | Status | By | On | Note |", "|---|---|---|---|---|---|---|"]
    for std in canon.applicable(m.tags):
        e = m.entries.get(std.id)
        link = _rel_link(page, docs / STANDARDS_DIR / f"{std.id}.md")
        if std.id in pending:
            status, by, on, note = "**pending**", e.by if e else "", e.on if e else "", pending[std.id].message.split(" — ", 1)[-1]
            mv = str(e.version) if e else "—"
        else:
            status, by, on, mv = e.status, e.by or "", e.on or "", str(e.version)
            note = f"{e.reason} (revisit {e.revisit})" if e.status == "declined" else ""
        rows.append(f"| [{std.title}]({link}) `{std.id}` | v{std.version} | v{mv} | {status} | {by} | {on} | {note} |")
    summary = f"{len(result.pending)} pending, {len(result.errors)} errors"
    return "\n".join(rows) + f"\n\n*Checked {date.today().isoformat()}: {summary}.*\n"


def status_page(repo: Path, canon: Canon) -> str:
    g = git_facts(repo)
    try:
        m = manifest_mod.for_repo(repo)
        extra = m.repo_extra
        tags = ", ".join(f"`{t}`" for t in m.tags)
    except manifest_mod.ManifestError:
        extra, tags = {}, "(manifest error)"
    agents = (repo / "AGENTS.md").read_text() if (repo / "AGENTS.md").exists() else ""
    test_cmd = (re.search(r"Test command: `([^`]+)`", agents) or [None, "not declared"])[1]
    lines = ["# Status", "", "<!-- ds:derived git -->", "| | |", "|---|---|",
             f"| **Branch** | `{g['branch']}` |", f"| **Commit** | `{g['head']}` ({g['last_commit']}) |",
             f"| **Uncommitted changes** | {g['dirty']} |", f"| **Remote** | `{g['remote']}` |",
             f"| **Tags** | {tags} |", f"| **Test command** | `{test_cmd}` |"]
    for k, v in extra.items():
        lines.append(f"| **{k}** | `{v}` |")
    sy = repo / ".ds/status.yaml"
    if sy.exists():
        lines += ["", "## Platform status (`.ds/status.yaml`)", "", "```yaml", sy.read_text().rstrip(), "```"]
    lines += ["", derived.derived_block(repo).replace("## Public surface (derived)", "## Public surface (derived from the code)")]
    return "\n".join(lines)


def remote_web(remote: str) -> str | None:
    """``https://host/g/p.git`` or ``git@host:g/p.git`` -> ``https://host/g/p``."""
    m = re.match(r"^git@([^:]+):(.+?)(?:\.git)?$", remote) or re.match(r"^https?://(?:[^@/]+@)?([^/]+)/(.+?)(?:\.git)?/?$", remote)
    return f"https://{m.group(1)}/{m.group(2)}" if m else None


def rewrite_repo_links(text: str, src: Path, repo: Path, staged_of: dict[Path, Path], page: Path, g: dict[str, str]) -> str:
    """Relative links between repo files keep working in the browser view: links to staged
    docs become links to their staged pages; links to other repo files go to the remote's
    blob URL when there is one; anything else is left alone for ``check`` to report."""
    web = remote_web(g.get("remote", "")) if g.get("remote") not in (None, "", "none") else None

    def sub(m: re.Match) -> str:
        label, target, title = m.group(1), m.group(2), m.group(3) or ""
        path, _, anchor = target.partition("#")
        if not path or "://" in path or path.startswith(("mailto:", "/", "[[")):
            return m.group(0)
        abs_target = (src.parent / path).resolve()
        if abs_target in staged_of:
            new = _rel_link(page, staged_of[abs_target])
        elif abs_target.exists() and web:
            rel = abs_target.relative_to(repo).as_posix()
            blob = "blob" if "github" in web else "-/blob"
            new = f"{web}/{blob}/{g.get('branch', 'main')}/{rel}"
        else:
            return m.group(0)
        return f"[{label}]({new}{'#' + anchor if anchor else ''}{title})"

    return re.sub(r"(?<!\!)\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)", sub, text)


def stage_repo_pages(repo: Path, canon: Canon, docs: Path, base: Path, nav_title: str | None = None) -> list:
    """Write a repo's pages under ``base`` (inside ``docs``). Returns MkDocs nav entries."""
    repo = Path(repo).resolve()
    name = nav_title or repo.name
    pages: list[tuple[str, Path]] = []
    g = git_facts(repo)

    # where every repo doc lands in the stage, so relative links can be rewritten
    staged_of: dict[Path, Path] = {}
    for fname, out in (("README.md", "index.md"), ("AGENTS.md", "agents.md"), ("DECISIONS.md", "decisions.md")):
        if (repo / fname).exists():
            staged_of[(repo / fname).resolve()] = base / out
    local_dir = repo / "docs"
    if local_dir.is_dir():
        for p in local_dir.rglob("*.md"):
            if "rendered" not in p.relative_to(local_dir).parts:
                staged_of[p.resolve()] = base / "local" / p.relative_to(local_dir)

    def link_for_page(page: Path):
        return lambda std: _rel_link(page, docs / STANDARDS_DIR / f"{std.id}.md")

    def copy_doc(src: Path, dst: Path, title: str) -> None:
        text = rewrite_repo_links(src.read_text(), src.resolve(), repo, staged_of, dst, g)
        _write(dst, resolve_text(text, canon, link_for_page(dst)))
        pages.append((title, dst))

    for fname, title in (("README.md", "Overview"), ("AGENTS.md", "Agents"), ("DECISIONS.md", "Decisions")):
        src = repo / fname
        if src.exists():
            copy_doc(src, base / ("index.md" if fname == "README.md" else fname.lower()), title)
    local_nav = []
    local_dir = repo / "docs"
    if local_dir.is_dir():
        for src in sorted(p for p in local_dir.rglob("*.md") if "rendered" not in p.relative_to(local_dir).parts):
            rel = src.relative_to(local_dir)
            dst = base / "local" / rel
            copy_doc(src, dst, rel.as_posix())
            local_nav.append({rel.as_posix(): dst.relative_to(docs).as_posix()})
    in_force = base / "standards-in-force.md"
    _write(in_force, "# Standards in force\n\n<!-- ds:derived manifest -->\n" + in_force_table(repo, canon, in_force, docs))
    status = base / "status.md"
    _write(status, status_page(repo, canon))

    nav = [{t: p.relative_to(docs).as_posix()} for t, p in pages if "local" not in p.relative_to(docs).parts]
    if local_nav:
        nav.append({"Local docs": local_nav})
    nav += [{"Standards in force": in_force.relative_to(docs).as_posix()}, {"Status": status.relative_to(docs).as_posix()}]
    return nav


def stage_single(repo: Path, canon: Canon, stage: Path) -> Staged:
    """One repo: its docs, the standards it points at, standards in force, status."""
    stage = Path(stage)
    docs = stage / "docs"
    if docs.exists():
        shutil.rmtree(docs)
    docs.mkdir(parents=True)
    nav = stage_repo_pages(repo, canon, docs, docs)
    stds = write_standard_pages(canon, docs)
    nav.append({"Standards": [{f"{s.title} ({s.id})": f"{STANDARDS_DIR}/{s.id}.md"} for s in stds]})
    return Staged(stage, docs, nav)


def discover_repos(root: Path) -> tuple[list[Path], list[Path]]:
    """Directories under ``root`` (two levels) that carry ``.ds/manifest.toml``, and those
    with a README but no manifest (reported, not rendered)."""
    root = Path(root).resolve()
    with_manifest, without = [], []
    for d in sorted(p for p in root.glob("*") if p.is_dir()) + sorted(p for p in root.glob("*/*") if p.is_dir()):
        if d.name.startswith(".") or d.name in ("site", "stage", "work", "results"):
            continue
        if (d / manifest_mod.MANIFEST_REL).exists():
            with_manifest.append(d)
        elif (d / "README.md").exists() and (d / ".git").exists():
            without.append(d)
    return with_manifest, without


def adoption_rows(repos: list[Path], canon: Canon) -> list[dict]:
    rows = []
    for repo in repos:
        try:
            m = manifest_mod.for_repo(repo)
        except manifest_mod.ManifestError as e:
            rows.append({"repo": repo.name, "standard": "", "title": "", "canon_version": "", "manifest_version": "",
                         "status": "manifest-error", "by": "", "on": "", "reason": str(e), "revisit": ""})
            continue
        result = reconcile.check(repo, canon, regen=False)
        pending = {f.where.split("@")[0] for f in result.pending}
        for std in canon.applicable(m.tags):
            e = m.entries.get(std.id)
            rows.append({
                "repo": repo.name, "standard": std.id, "title": std.title, "canon_version": std.version,
                "manifest_version": e.version if e else "", "status": "pending" if std.id in pending else (e.status if e else "pending"),
                "by": (e.by or "") if e else "", "on": (e.on or "") if e else "",
                "reason": (e.reason or "") if e else "", "revisit": (e.revisit or "") if e else "",
            })
    return rows


def stage_portal(root: Path, canon: Canon, stage: Path, site_name: str = "Team portal") -> Staged:
    """Every repo under ``root`` plus the canon and the adoption table, as one site."""
    stage = Path(stage)
    docs = stage / "docs"
    if docs.exists():
        shutil.rmtree(docs)
    docs.mkdir(parents=True)
    repos, skipped = discover_repos(root)
    stds = write_standard_pages(canon, docs)
    rows = adoption_rows(repos, canon)

    # per-repo sections
    repo_nav = []
    index_rows = ["| Repository | Owner | Tags | Pending | Last commit | Uncommitted |", "|---|---|---|---|---|---|"]
    for repo in repos:
        base = docs / "repos" / repo.name
        nav = stage_repo_pages(repo, canon, docs, base, repo.name)
        repo_nav.append({repo.name: nav})
        m = manifest_mod.for_repo(repo)
        g = git_facts(repo)
        owner = next((e.by for e in m.entries.values() if e.by), "")
        pend = sum(1 for r in rows if r["repo"] == repo.name and r["status"] == "pending")
        index_rows.append(f"| [{repo.name}](repos/{repo.name}/index.md) | {owner} | {', '.join(f'`{t}`' for t in m.tags)} | {pend} | {g['last_commit']} | {g['dirty']} |")

    # adoption table + csv
    per_std: dict[str, dict[str, int]] = {}
    for r in rows:
        if r["standard"]:
            per_std.setdefault(r["standard"], {"adopted": 0, "declined": 0, "pending": 0})
            per_std[r["standard"]][r["status"]] = per_std[r["standard"]].get(r["status"], 0) + 1
    adoption = ["# Adoption", "", "<!-- ds:derived manifests -->",
                "One row per repository per applicable standard, from every `.ds/manifest.toml`. "
                "The same rows are in [adoption.csv](adoption.csv) for loading into the adoption table.", "",
                "## By standard", "", "| Standard | Adopted | Declined | Pending |", "|---|---|---|---|"]
    for sid, c in sorted(per_std.items()):
        adoption.append(f"| [{canon.get(sid).title}]({STANDARDS_DIR}/{sid}.md) `{sid}` | {c['adopted']} | {c['declined']} | {c['pending']} |")
    adoption += ["", "## By repository", "", "| Repository | Standard | Canon | Manifest | Status | By | On | Reason | Revisit |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        adoption.append(f"| {r['repo']} | `{r['standard']}` | {r['canon_version']} | {r['manifest_version']} | {r['status']} | {r['by']} | {r['on']} | {r['reason']} | {r['revisit']} |")
    _write(docs / "adoption.md", "\n".join(adoption) + "\n")
    with (docs / "adoption.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["repo"])
        w.writeheader()
        w.writerows(rows)

    home = ["# Team portal", "", "<!-- ds:derived registry -->",
            f"{len(repos)} repositories with a manifest, {len(canon.standards)} standards in the canon, "
            f"{sum(1 for r in rows if r['status'] == 'pending')} pending decisions. Generated {date.today().isoformat()}.", "",
            *index_rows, ""]
    if skipped:
        home += ["## Repositories without a manifest", "", "Not born through `ds new`; not rendered.", ""]
        home += [f"- `{s.name}`" for s in skipped]
    _write(docs / "index.md", "\n".join(home) + "\n")

    nav = [{"Home": "index.md"}, {"Adoption": "adoption.md"}, {"Repositories": repo_nav},
           {"Standards": [{f"{s.title} ({s.id})": f"{STANDARDS_DIR}/{s.id}.md"} for s in stds]}]
    return Staged(stage, docs, nav)
