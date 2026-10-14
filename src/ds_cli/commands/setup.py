"""
DS CLI - ``ds setup``: fetch what the knowledge-system verbs need and nothing else.

The canon (standards) and the docs shell (renderer) are git repositories. This clones or
updates them under ``DS_HOME`` (default ``~/.ds``) and installs the shell's Node dependencies.
Idempotent; run it again to update. A checkout beside the repository or an env var still wins.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer

from ..config import CANON_URL, DOCS_SHELL_URL, DS_HOME, app, console
from ..canon.client import Canon


def _sync_repo(url: str, dest: Path) -> str:
    if (dest / ".git").exists():
        r = subprocess.run(["git", "-C", str(dest), "pull", "-q", "--ff-only"], capture_output=True, text=True)
        return "updated" if r.returncode == 0 else f"pull failed: {r.stderr.strip()[:200]}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "clone", "-q", "--depth", "1", url, str(dest)], capture_output=True, text=True)
    return "cloned" if r.returncode == 0 else f"clone failed: {r.stderr.strip()[:200]}"


@app.command()
def setup(canon_url: Optional[str] = typer.Option(None, "--canon-url", help=f"default {CANON_URL} or $DS_CANON_URL"),
          shell_url: Optional[str] = typer.Option(None, "--shell-url", help=f"default {DOCS_SHELL_URL} or $DS_DOCS_SHELL_URL"),
          home: Optional[Path] = typer.Option(None, "--home", help=f"default {DS_HOME} or $DS_HOME"),
          npm: bool = typer.Option(True, "--npm/--no-npm", help="install the shell's Node dependencies")):
    """Fetch or update the canon and the docs shell under ~/.ds, so `ds reconcile`, `ds canon`,
    and `ds docs` work in any repository."""
    home = Path(home or DS_HOME)
    canon_dir, shell_dir = home / "canon", home / "shell"
    typer.echo(f"canon  {_sync_repo(canon_url or CANON_URL, canon_dir)}  -> {canon_dir}")
    typer.echo(f"shell  {_sync_repo(shell_url or DOCS_SHELL_URL, shell_dir)}  -> {shell_dir}")
    if (shell_dir / "package.json").exists() and npm:
        if shutil.which("npm"):
            r = subprocess.run(["npm", "ci", "--no-fund", "--no-audit"], cwd=shell_dir, capture_output=True, text=True)
            typer.echo("shell  npm ci " + ("ok" if r.returncode == 0 else f"failed: {r.stderr.strip()[-200:]}"))
        else:
            console.print("[yellow]npm not found; `ds docs` needs Node. Install it, then run `ds setup` again.[/yellow]")
    try:
        c = Canon(canon_dir)
        typer.echo(f"canon  {len(c.standards)} standards, index generated {c.generated}")
    except Exception as e:
        console.print(f"[red]canon unusable: {e}[/red]")
        raise typer.Exit(1)
    typer.echo("ready: `ds reconcile`, `ds canon list`, `ds docs serve` work in any repository")
