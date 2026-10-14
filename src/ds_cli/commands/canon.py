"""
DS CLI - knowledge-system verbs: ``ds canon``, ``ds reconcile``, ``ds docs``, ``ds hooks``.

See docs/KNOWLEDGE_SYSTEM.md. Every verb here is offline and deterministic; the only writes
are the manifest (adopt/decline), the derived block, docs/rendered/, and the git hook.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from ..config import CANON_PATH, app, console
from ..canon import manifest as manifest_mod
from ..canon import reconcile as reconcile_mod
from ..canon.client import Canon, CanonError
from ..docs import docusaurus as site_mod
from ..docs import render as render_mod
from .. import hooks as hooks_mod

canon_app = typer.Typer(help="Read the canon: the standards that apply to a repository.")
docs_app = typer.Typer(invoke_without_command=True, help="View a repository's docs with pointers resolved.")
hooks_app = typer.Typer(help="Git hooks for the knowledge system.")
app.add_typer(canon_app, name="canon")
app.add_typer(docs_app, name="docs")
app.add_typer(hooks_app, name="hooks")

RepoArg = typer.Argument(Path("."), help="Repository root (default: current directory)")
CanonOpt = typer.Option(None, "--canon", help="Canon checkout (default: $DS_CANON, then ../canon)")


def _canon(explicit: Optional[Path], repo: Path) -> Canon:
    try:
        return Canon.locate(explicit or CANON_PATH, Path(repo).resolve())
    except CanonError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2)


def _git_user() -> str:
    try:
        return subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip() or os.environ.get("USER", "unknown")
    except Exception:
        return os.environ.get("USER", "unknown")


# -- ds reconcile -------------------------------------------------------------------------

@app.command()
def reconcile(
    repo: Path = RepoArg,
    canon: Optional[Path] = CanonOpt,
    check: bool = typer.Option(True, "--check", help="Offline check (the default): manifest, pointers, derived block, pending"),
    adopt: Optional[str] = typer.Option(None, "--adopt", metavar="ID", help="Record a standard as adopted at the canon's current version"),
    decline: Optional[str] = typer.Option(None, "--decline", metavar="ID", help="Record a decline; requires --reason and --revisit"),
    reason: Optional[str] = typer.Option(None, "--reason"),
    revisit: Optional[str] = typer.Option(None, "--revisit", help="YYYY-MM-DD"),
    by: Optional[str] = typer.Option(None, "--by", help="Who decided (default: git user.name)"),
    interactive: bool = typer.Option(False, "--interactive", help="Decide each pending item (not in this version)"),
    apply: bool = typer.Option(False, "--apply", help="Unattended, model-driven (not in this version)"),
    regen: bool = typer.Option(True, "--regen/--no-regen", help="Regenerate the derived block"),
    quiet: bool = typer.Option(False, "--quiet", help="Hook mode: one line per pending item; errors only otherwise"),
    timing: bool = typer.Option(False, "--timing"),
):
    """Keep the repository in step with the canon. Pending standards are information;
    only a broken pointer or a malformed manifest fails (exit 1)."""
    c = _canon(canon, repo)
    if interactive or apply:
        console.print("[yellow]--interactive and --apply are not in this version. Use --adopt ID or --decline ID --reason ... --revisit ...[/yellow]")
        raise typer.Exit(2)
    if adopt:
        e = reconcile_mod.adopt(repo, c, adopt, by or _git_user())
        typer.echo(f"adopted {adopt}@{e.version} by {e.by} on {e.on}")
    if decline:
        if not reason or not revisit:
            console.print("[red]--decline requires --reason and --revisit[/red]")
            raise typer.Exit(2)
        e = reconcile_mod.decline(repo, c, decline, by or _git_user(), reason, revisit)
        typer.echo(f"declined {decline}@{e.version} by {e.by}: {e.reason} (revisit {e.revisit})")
    r = reconcile_mod.check(repo, c, regen=regen)
    if quiet:
        for f in r.errors:
            typer.echo(f"ds: error in {f.where}: {f.message}", err=True)
        if r.pending:
            names = ", ".join(f"{f.where.split('@')[0]} ({f.message.split(' — ')[1].split(' (')[0]})" for f in r.pending)
            plural = "s" if len(r.pending) != 1 else ""
            typer.echo(f"ds: {len(r.pending)} standard{plural} pending — {names}. Run `ds reconcile`.", err=True)
    else:
        for f in r.findings:
            typer.echo(f"{f.level:7} {f.where:28} {f.message}")
        suffix = f" ({r.duration_s * 1000:.0f} ms)" if timing else ""
        typer.echo(f"{len(r.errors)} errors, {len(r.pending)} pending, {len(r.info)} notes{suffix}")
    raise typer.Exit(r.exit_code)


# -- ds canon -----------------------------------------------------------------------------

@canon_app.command("list")
def canon_list(repo: Path = RepoArg, canon: Optional[Path] = CanonOpt):
    """Standards that apply to this repository, with their status in the manifest."""
    c = _canon(canon, repo)
    r = reconcile_mod.check(repo, c, regen=False)
    pending = {f.where.split("@")[0]: f.message for f in r.pending}
    try:
        m = manifest_mod.for_repo(repo)
    except manifest_mod.ManifestError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    for std in c.applicable(m.tags):
        e = m.entries.get(std.id)
        if std.id in pending:
            status = "pending  " + (f"(manifest v{e.version} {e.status})" if e else "(new)")
        else:
            note = f": {e.reason} (revisit {e.revisit})" if e.status == "declined" else ""
            status = f"{e.status}{note} by {e.by} on {e.on}"
        typer.echo(f"{std.id:10} v{std.version:<3} {std.title:45} {status}")


@canon_app.command("read")
def canon_read(std_id: str, canon: Optional[Path] = CanonOpt, repo: Path = typer.Option(Path("."), "--repo")):
    """Print a standard."""
    c = _canon(canon, repo)
    try:
        res = c.resolve(std_id)
    except CanonError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    typer.echo(f"{render_mod.label(res.standard)}  applies_to={list(res.standard.applies_to)}  owner={res.standard.owner}\n")
    typer.echo(res.text)


# -- ds docs ------------------------------------------------------------------------------

@docs_app.callback()
def docs(ctx: typer.Context, canon: Optional[Path] = CanonOpt,
         inline: bool = typer.Option(False, "--inline", help="Append the text of every referenced standard")):
    """With no subcommand: print this repository's README and AGENTS.md with pointers resolved."""
    if ctx.invoked_subcommand is None:
        c = _canon(canon, Path("."))
        typer.echo(render_mod.print_docs(Path("."), c, inline=inline))


@docs_app.command("print")
def docs_print(repo: Path = RepoArg, canon: Optional[Path] = CanonOpt,
               inline: bool = typer.Option(False, "--inline")):
    """Terminal view of a repository's docs."""
    c = _canon(canon, repo)
    typer.echo(render_mod.print_docs(repo, c, inline=inline))


@docs_app.command("render")
def docs_render(repo: Path = RepoArg, canon: Optional[Path] = CanonOpt,
                canon_url: Optional[str] = typer.Option(None, "--canon-url", envvar="DS_CANON_URL", help="Web root of the canon for GitLab links"),
                out: Optional[Path] = typer.Option(None, "--out", help="Default docs/rendered inside the repo")):
    """The committed copy for GitLab: every doc under docs/rendered with pointers as links, never prose."""
    c = _canon(canon, repo)
    written = render_mod.render_repo(repo, c, out, canon_url)
    for p, changed in written:
        typer.echo(f"{'wrote ' if changed else 'same  '} {p}")
    typer.echo(f"{sum(1 for _, ch in written if ch)} changed of {len(written)}")


@docs_app.command("build")
def docs_build(repo: Path = RepoArg, canon: Optional[Path] = CanonOpt,
               out: Path = typer.Option(Path("site"), "--out"), stage: Optional[Path] = typer.Option(None, "--stage")):
    """Browser view, built to a directory."""
    c = _canon(canon, repo)
    stage = stage or Path(out).resolve().parent / ".ds-stage"
    site_mod.stage_single(repo, c, stage)
    r = site_mod.build(stage, out)
    typer.echo(r.stdout + r.stderr)
    typer.echo(f"site: {Path(out).resolve()}")
    raise typer.Exit(r.returncode)


@docs_app.command("serve")
def docs_serve(repo: Path = RepoArg, canon: Optional[Path] = CanonOpt, port: int = typer.Option(8000, "--port"),
               stage: Optional[Path] = typer.Option(None, "--stage")):
    """Browser view: build, then serve on 127.0.0.1:PORT."""
    c = _canon(canon, repo)
    stage = stage or Path(repo).resolve() / ".ds" / "stage"
    site_mod.stage_single(repo, c, stage)
    cmd = site_mod.serve_cmd(stage, port)
    console.print(f"serving {Path(repo).resolve().name} at [cyan]http://127.0.0.1:{port}/[/cyan]")
    os.execv(cmd[0], cmd)


@docs_app.command("portal")
def docs_portal(root: Path = typer.Argument(..., help="Directory containing repositories"), canon: Optional[Path] = CanonOpt,
                out: Path = typer.Option(Path("portal-site"), "--out"), stage: Optional[Path] = typer.Option(None, "--stage"),
                name: str = typer.Option("Team portal", "--name")):
    """Team portal, built: every repository under ROOT, the canon, and the adoption table."""
    c = _canon(canon, root)
    stage = stage or Path(out).resolve().parent / ".ds-portal-stage"
    site_mod.stage_portal(root, c, stage, name)
    r = site_mod.build(stage, out)
    typer.echo(r.stdout + r.stderr)
    typer.echo(f"portal: {Path(out).resolve()}  (adoption.csv inside)")
    raise typer.Exit(r.returncode)


# -- ds hooks -----------------------------------------------------------------------------

@hooks_app.command("install")
def hooks_install(repo: Path = RepoArg, canon: Optional[Path] = CanonOpt):
    """Install the pre-push hook that runs `ds reconcile --check` (idempotent)."""
    c = _canon(canon, repo) if (canon or CANON_PATH) else None
    hook = hooks_mod.install(repo, c.root if c else None)
    typer.echo(f"installed {hook}")
