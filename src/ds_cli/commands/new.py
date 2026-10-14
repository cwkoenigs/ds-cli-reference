"""
DS CLI - ``ds new`` and ``ds migrate``: the interview.

``ds new NAME`` gives a repository its curated docs, manifest, pre-push hook, and agent config.
It asks eight questions with inferred defaults, or takes them from ``--answers FILE``. It does
not scaffold code; ``ds create`` still does that, and ``ds new .`` can follow it.
``ds migrate`` is ``ds new`` on an existing repository: old docs are kept under .ds/legacy/.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import typer

from ..config import CANON_PATH, PROJECTS_DIR, app, console
from ..canon import reconcile as reconcile_mod
from ..canon.client import Canon, CanonError
from ..interview import questions as q_mod, render as r_mod
from .. import hooks as hooks_mod


def _canon(explicit: Optional[Path], repo: Path) -> Canon:
    try:
        return Canon.locate(explicit or CANON_PATH, Path(repo).resolve())
    except CanonError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2)


def _interview(repo: Path, answers_file: Optional[Path]) -> tuple[q_mod.Answers, list[q_mod.Question]]:
    qs = q_mod.questions(repo)
    if answers_file:
        a = q_mod.fill_defaults(q_mod.answers_from_file(answers_file), repo)
    else:
        console.print("[dim]ds: a few questions. Defaults are in brackets; Enter accepts.[/dim]")
        raw: dict[str, str] = {}
        for q in qs:
            raw[q.key] = typer.prompt(f"  {q.text}", default=q.default, show_default=bool(q.default)) if q.default or q.key in ("purpose",) \
                else (typer.prompt(f"  {q.text}", default="", show_default=False) or "")
        a = q_mod.Answers(purpose=raw["purpose"], owner=raw["owner"], test_cmd=raw["test_cmd"], lint_cmd=raw["lint_cmd"],
                          tags=[t.strip() for t in raw["tags"].split(",") if t.strip()], snowflake=raw["snowflake"],
                          notes=raw["notes"], declines=q_mod.parse_declines(raw["declines"]))
    if not a.purpose:
        console.print("[red]A one-line purpose is required.[/red]")
        raise typer.Exit(2)
    return a, qs


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _run(repo: Path, name: str, canon: Canon, answers_file: Optional[Path], force: bool, git: bool) -> None:
    a, qs = _interview(repo, answers_file)
    try:
        written = r_mod.write_all(repo, name, a, canon, qs, force=force)
    except FileExistsError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    for p in written:
        console.print(f"[green]✓[/green] {p.relative_to(repo)}")
    if git:
        if not (repo / ".git").exists():
            _git(repo, "init", "-q")
        hooks_mod.install(repo, canon.root)
        console.print("[green]✓[/green] pre-push hook installed")
    from .agent import write_project_config
    if write_project_config(repo):
        console.print("[green]✓[/green] agent config (.mcp.json, .ds/agent.toml)")
    if git:
        _git(repo, "add", "-A")
        if _git(repo, "diff", "--cached", "--quiet").returncode != 0:
            r = _git(repo, "-c", "user.name=ds", "-c", "user.email=ds@local", "commit", "-qm", f"ds new: {name}")
            console.print("[green]✓[/green] committed" if r.returncode == 0 else f"[yellow]commit skipped: {r.stderr.strip()}[/yellow]")
    r = reconcile_mod.check(repo, canon)
    applicable = canon.applicable(a.tags)
    declined = sum(1 for s in applicable if s.id in a.declines)
    typer.echo(f"ds: {len(applicable)} standards apply; {len(applicable) - declined} adopted at current versions"
               + (f", {declined} declined" if declined else "") + f"; check: {len(r.errors)} errors, {len(r.pending)} pending.")
    raise typer.Exit(r.exit_code)


@app.command()
def new(
    name: str = typer.Argument(help="Project name; also the directory under ~/code unless --dir is given"),
    dir: Optional[Path] = typer.Option(None, "--dir", help="Directory to create or use (default: ~/code/NAME; '.' for the current one)"),
    answers: Optional[Path] = typer.Option(None, "--answers", help="TOML answers file (non-interactive)"),
    canon: Optional[Path] = typer.Option(None, "--canon", help="Canon checkout (default: $DS_CANON, then ../canon)"),
    force: bool = typer.Option(False, "--force", help="Keep existing README/AGENTS/DECISIONS under .ds/legacy/ and write new ones"),
    git: bool = typer.Option(True, "--git/--no-git", help="git init if needed, install the hook, commit"),
):
    """Interview, then write README.md, AGENTS.md, DECISIONS.md, .ds/manifest.toml, .ds/interview.md,
    .ds/agent.toml; install the pre-push hook; commit. Every applicable standard is adopted
    at its current version unless declined in the interview."""
    repo = (Path(dir) if dir else PROJECTS_DIR / name).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    c = _canon(canon, repo)
    _run(repo, name if name != "." else repo.name, c, answers, force, git)


@app.command()
def migrate(
    repo: Path = typer.Argument(Path("."), help="Existing repository (default: current directory)"),
    answers: Optional[Path] = typer.Option(None, "--answers"),
    canon: Optional[Path] = typer.Option(None, "--canon"),
    git: bool = typer.Option(True, "--git/--no-git"),
):
    """`ds new` for a repository that already exists: defaults are detected from its files,
    old docs are kept under .ds/legacy/, nothing else is touched."""
    repo = Path(repo).resolve()
    c = _canon(canon, repo)
    _run(repo, repo.name, c, answers, force=True, git=git)
