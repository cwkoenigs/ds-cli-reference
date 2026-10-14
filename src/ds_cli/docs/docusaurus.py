"""The browser view and the team portal, rendered by the docs shell (the Docusaurus site in
the docs-ds repository). The shell is pointed at the staged tree with environment variables
and never modified. Strictness is ``reconcile --check``'s job, so staged builds downgrade
broken links to warnings."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..canon.client import Canon
from ..config import docs_shell
from . import pages as site
from .pages import Staged, STANDARDS_DIR


def _front_matter(path: Path, title: str, position: int | None = None, slug: str | None = None,
                  label: str | None = None) -> None:
    text = path.read_text()
    if text.startswith("---\n"):                      # generated pages never carry their own; repo docs may
        text = text.split("\n---\n", 1)[1].lstrip("\n")
    fm = {"title": title}
    if slug:
        fm["slug"] = slug
    if position is not None:
        fm["sidebar_position"] = position
    if label:
        fm["sidebar_label"] = label
    head = "---\n" + "".join(f"{k}: {json.dumps(v)}\n" for k, v in fm.items()) + "---\n\n"
    path.write_text(head + text)


def _category(d: Path, label: str, position: int, link_doc: str | None = None, collapsed: bool = False) -> None:
    d.mkdir(parents=True, exist_ok=True)
    cat: dict = {"label": label, "position": position, "collapsed": collapsed}
    if link_doc:
        cat["link"] = {"type": "doc", "id": link_doc}
    (d / "_category_.json").write_text(json.dumps(cat, indent=2) + "\n")


def _decorate_repo_pages(base: Path, docs: Path, name: str, root_slug: str | None) -> None:
    """Front matter and categories for one repo's pages (written by site.stage_repo_pages)."""
    order = [("index.md", "Overview", 1), ("agents.md", "Agents", 2), ("decisions.md", "Decisions", 3),
             ("standards-in-force.md", "Standards in force", 5), ("status.md", "Status", 6)]
    for fname, label, pos in order:
        p = base / fname
        if p.exists():
            _front_matter(p, name if fname == "index.md" else label, pos, root_slug if fname == "index.md" else None, label)
    local = base / "local"
    if local.is_dir():
        _category(local, "Local docs", 4)
        for p in sorted(local.rglob("*.md")):
            _front_matter(p, p.stem.replace("-", " ").capitalize())


def _decorate_standards(docs: Path, position: int) -> None:
    _category(docs / STANDARDS_DIR, "Standards", position, collapsed=True)
    for p in sorted((docs / STANDARDS_DIR).glob("*.md")):
        title = p.read_text().split("\n", 1)[0].lstrip("# ").strip()
        _front_matter(p, title, label=f"{title} ({p.stem})")


def stage_single(repo: Path, canon: Canon, stage: Path) -> Staged:
    stage = Path(stage)
    docs = stage / "docs"
    if docs.exists():
        shutil.rmtree(docs)
    docs.mkdir(parents=True)
    nav = site.stage_repo_pages(repo, canon, docs, docs)
    site.write_standard_pages(canon, docs)
    _decorate_repo_pages(docs, docs, Path(repo).resolve().name, "/")
    _decorate_standards(docs, 7)
    (stage / "site.json").write_text(json.dumps({"title": Path(repo).resolve().name, "nav_label": "This repo"}))
    return Staged(stage, docs, nav)


def stage_portal(root: Path, canon: Canon, stage: Path, site_name: str = "Team portal") -> Staged:
    stage = Path(stage)
    staged = site.stage_portal(root, canon, stage, site_name)      # writes the pages
    docs = staged.docs
    # static assets: the CSV is served from the site root
    static = stage / "static"
    shutil.rmtree(static, ignore_errors=True)
    static.mkdir()
    shutil.move(str(docs / "adoption.csv"), str(static / "adoption.csv"))
    adoption = docs / "adoption.md"
    adoption.write_text(adoption.read_text().replace("[adoption.csv](adoption.csv)", "[adoption.csv](pathname:///adoption.csv)"))
    _front_matter(docs / "index.md", site_name, 1, "/", "Home")
    _front_matter(adoption, "Adoption", 2)
    repos_dir = docs / "repos"
    if repos_dir.is_dir():
        _category(repos_dir, "Repositories", 3)
        for base in sorted(p for p in repos_dir.iterdir() if p.is_dir()):
            _category(base, base.name, 1, link_doc=f"repos/{base.name}/index", collapsed=True)
            _decorate_repo_pages(base, docs, base.name, None)
    _decorate_standards(docs, 4)
    (stage / "site.json").write_text(json.dumps({"title": site_name, "nav_label": "Portal"}))
    return Staged(stage, docs, staged.nav)


def _env(stage: Path, strict: bool) -> dict[str, str]:
    meta = json.loads((Path(stage) / "site.json").read_text()) if (Path(stage) / "site.json").exists() else {}
    env = {**os.environ,
           "DOCS_CONTENT_PATH": str(Path(stage).resolve() / "docs"),
           "SITE_BASE_URL": "/", "SITE_URL": os.environ.get("SITE_URL", "https://example.com"),
           "SITE_TITLE": meta.get("title", "Docs"), "SITE_NAV_LABEL": meta.get("nav_label", "Docs"),
           "SITE_TAGLINE": "rendered by ds docs",
           "DOCS_STRICT": "1" if strict else "0"}
    static = Path(stage).resolve() / "static"
    if static.is_dir():
        env["DOCS_STATIC_PATH"] = str(static)
    return env


def build(stage: Path, out: Path, strict: bool = False) -> subprocess.CompletedProcess:
    shell = docs_shell()
    cmd = ["npx", "docusaurus", "build", "--out-dir", str(Path(out).resolve())]
    return subprocess.run(cmd, cwd=shell, env=_env(stage, strict), capture_output=True, text=True)


def serve_cmd(stage: Path, port: int, out: Path | None = None) -> list[str]:
    """Build, then serve the static site: the dev server renders client-side, which is useless
    to anything that is not a browser, and the build takes seconds."""
    out = Path(out) if out else Path(stage) / "site"
    r = build(stage, out)
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    return [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(out.resolve())]
