"""
DS CLI - ``ds serve-mcp`` and ``ds agent config``.

``serve-mcp`` exposes the canon and the manifest to agents over stdio. ``agent config`` writes the
registrations ds can know without asking: a project-level ``.mcp.json`` (Claude Code reads it
from the repo root), a best-guess Cortex Code file marked unverified, and ``.ds/agent.toml``.
Registering with Cortex Code for real is the ``so-agent-setup`` skill's job, on a machine that
has it: the settings location is discovered there, never guessed here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from ..config import CANON_PATH, app, console
from ..canon.client import Canon, CanonError

agent_app = typer.Typer(help="Agent runtime configuration for this repository.")
app.add_typer(agent_app, name="agent")

SERVER_ENTRY = {"type": "stdio", "command": "ds", "args": ["serve-mcp"]}


def _canon(explicit: Optional[Path], repo: Path) -> Canon:
    try:
        return Canon.locate(explicit or CANON_PATH, Path(repo).resolve())
    except CanonError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2)


@app.command("serve-mcp")
def serve_mcp(repo: Path = typer.Option(Path("."), "--repo", help="Repository root (default: current directory)"),
              canon: Optional[Path] = typer.Option(None, "--canon")):
    """Serve read_standard, manifest_status, canon_list, and graph_symbols over stdio."""
    from ..mcp.server import serve
    serve(Path(repo).resolve(), _canon(canon, repo))


def write_project_config(repo: Path) -> list[Path]:
    """The registrations that are the same on every machine. Returns the files written."""
    repo = Path(repo)
    written: list[Path] = []

    # Claude Code: project-scoped MCP servers live in .mcp.json at the repo root.
    mcp_json = repo / ".mcp.json"
    data = {}
    if mcp_json.exists():
        try:
            data = json.loads(mcp_json.read_text())
        except json.JSONDecodeError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    if servers.get("ds") != SERVER_ENTRY:
        servers["ds"] = SERVER_ENTRY
        mcp_json.write_text(json.dumps(data, indent=2) + "\n")
        written.append(mcp_json)

    # Cortex Code: format not verified on this machine; so-agent-setup replaces this.
    coco = repo / ".ds" / "coco-settings.json"
    if not coco.exists():
        coco.parent.mkdir(exist_ok=True)
        coco.write_text(json.dumps({
            "_unverified": "Best guess written by `ds agent config`. Run /so-agent-setup on a machine with Cortex Code to "
                           "discover the real settings location and format; it replaces this file.",
            "mode": "code",
            "mcpServers": {"ds": SERVER_ENTRY},
        }, indent=2) + "\n")
        written.append(coco)

    agent_toml = repo / ".ds" / "agent.toml"
    if not agent_toml.exists():
        from ..interview.render import agent_config
        from datetime import date
        agent_toml.parent.mkdir(exist_ok=True)
        agent_toml.write_text(agent_config(date.today().isoformat()))
        written.append(agent_toml)
    return written


def codex_snippet() -> str:
    return '[mcp_servers.ds]\ncommand = "ds"\nargs = ["serve-mcp"]\n'


@agent_app.command("config")
def agent_config(repo: Path = typer.Argument(Path("."), help="Repository root"),
                 codex: bool = typer.Option(False, "--codex", help="Also register in ~/.codex/config.toml (user-level)")):
    """Write .mcp.json (Claude Code), .ds/agent.toml, and a best-guess Cortex Code file."""
    repo = Path(repo).resolve()
    written = write_project_config(repo)
    for p in written:
        typer.echo(f"wrote {p.relative_to(repo)}")
    if not written:
        typer.echo("already configured")
    if codex:
        cfg = Path.home() / ".codex" / "config.toml"
        text = cfg.read_text() if cfg.exists() else ""
        if "[mcp_servers.ds]" in text:
            typer.echo(f"codex: already registered in {cfg}")
        else:
            cfg.parent.mkdir(exist_ok=True)
            cfg.write_text(text.rstrip("\n") + ("\n\n" if text else "") + codex_snippet())
            typer.echo(f"codex: registered in {cfg}")
    typer.echo("cortex code: see .ds/coco-settings.json (unverified); run /so-agent-setup where Cortex Code is installed")
