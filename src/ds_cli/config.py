"""Configuration the knowledge-system commands rely on. In the real ds-cli these names live in
its own configuration; see docs/PORT.md for where they go."""
import os
from pathlib import Path

import typer
from rich.console import Console

from . import __version__


def _version_callback(value: bool):
    if value:
        print(f"ds {__version__}")
        raise typer.Exit()


app = typer.Typer(name="ds", help="Knowledge-system verbs (reference implementation)", rich_markup_mode="rich")


@app.callback()
def _app_callback(version: bool = typer.Option(False, "--version", "-V", callback=_version_callback, is_eager=True)):
    """Knowledge-system verbs (reference implementation)."""


console = Console()

PROJECTS_DIR = Path(os.getenv("DS_PROJECTS_DIR", Path.home() / "code"))

# Knowledge system: the canon checkout and the docs shell.
# `ds setup` fetches both into DS_HOME; a checkout beside the repo or an env var wins over it.
DS_HOME = Path(os.getenv("DS_HOME", Path.home() / ".ds"))
CANON_PATH = os.getenv("DS_CANON")
CANON_URL = os.getenv("DS_CANON_URL", "https://github.com/cwkoenigs/canon.git")
DOCS_SHELL_URL = os.getenv("DS_DOCS_SHELL_URL", "https://github.com/cwkoenigs/docs-ds.git")


def docs_shell() -> Path:
    """The docs shell (the docs-ds Docusaurus site) that `ds docs` renders through."""
    candidates = [os.getenv("DS_DOCS_SHELL"), DS_HOME / "shell", PROJECTS_DIR / "docs-ds", Path.home() / "Developer" / "docs-ds"]
    for c in candidates:
        if c and (Path(c) / "docusaurus.config.ts").exists():
            return Path(c)
    raise FileNotFoundError("docs shell not found: run `ds setup`, or set DS_DOCS_SHELL to a docs-ds checkout")
