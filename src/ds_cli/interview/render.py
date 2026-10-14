"""Answers -> README.md, AGENTS.md, DECISIONS.md, .ds/manifest.toml, .ds/interview.md,
.ds/agent.toml. Only sections the answers justify; every block carries provenance."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from .. import __version__
from ..canon import derived, manifest as manifest_mod
from ..canon.client import Canon
from .questions import Answers, Question

REVISIT_DAYS = 90
LEGACY_DIR = Path(".ds/legacy")


def _local(today: str) -> str:
    return f"<!-- ds:local interview {today} -->"


def readme(name: str, a: Answers, canon: Canon, today: str) -> str:
    applicable = canon.applicable(a.tags)
    glossary = any(s.id == "glossary" for s in applicable)
    lines = [f"# {name}", "", _local(today), f"{a.purpose.rstrip('.')}. Owner: {a.owner}.", "", f"Run tests: `{a.test_cmd}`"]
    if a.lint_cmd:
        lines.append(f"Lint and types: `{a.lint_cmd}`")
    if a.snowflake:
        lines.append(f"Snowflake: `{a.snowflake}`")
    if a.notes:
        lines += ["", a.notes.strip()]
    lines += ["", "<!-- ds:inherited -->",
              "Team standards in force are listed in AGENTS.md; `ds canon list` shows each one's status."
              + (" Domain terms: [[glossary]]." if glossary else "")]
    return "\n".join(lines) + "\n"


def agents(a: Answers, canon: Canon, repo: Path, today: str) -> str:
    applicable = canon.applicable(a.tags)
    gate = next((s for s in applicable if "acceptance" in s.title.lower() or "test" in s.title.lower()), None)
    lines = ["# AGENTS.md", "", _local(today),
             f"- Test command: `{a.test_cmd}` (exit code is the definition of done" + (f", per [[{gate.id}]])" if gate else ")"),
             f"- Lint/type: `{a.lint_cmd}`",
             f"- Tags: {', '.join(a.tags)}"]
    if a.snowflake:
        lines.append(f"- Snowflake: `{a.snowflake}`")
    pointers = " ".join(f"[[{s.id}]]" for s in applicable if s.id != "glossary")
    lines += ["", "<!-- ds:inherited -->", f"Standards in force: {pointers or 'none apply yet'}",
              "Read `manifest_status` first, then query the graph before reading any file.", "",
              derived.derived_block(repo, today).rstrip("\n")]
    return "\n".join(lines) + "\n"


def decisions(today: str) -> str:
    return f"# Local decisions\n\n{_local(today)}\nNone yet. Declined standards are recorded in `.ds/manifest.toml`.\n"


def manifest(name: str, a: Answers, canon: Canon, repo: Path, today: str) -> manifest_mod.Manifest:
    m = manifest_mod.Manifest(repo / manifest_mod.MANIFEST_REL, name, list(a.tags),
                              {"created": today, "interview": ".ds/interview.md", "ds_version": __version__})
    revisit = (date.fromisoformat(today) + timedelta(days=REVISIT_DAYS)).isoformat()
    for std in canon.applicable(a.tags):
        if std.id in a.declines:
            m.entries[std.id] = manifest_mod.Entry(std.id, "declined", std.version, a.owner, today, a.declines[std.id], revisit)
        else:
            m.entries[std.id] = manifest_mod.Entry(std.id, "adopted", std.version, a.owner, today)
    return m


def transcript(qs: list[Question], a: Answers, today: str) -> str:
    given = {"purpose": a.purpose, "owner": a.owner, "test_cmd": a.test_cmd, "lint_cmd": a.lint_cmd,
             "tags": ", ".join(a.tags), "snowflake": a.snowflake or "(none)", "notes": a.notes or "(none)",
             "declines": "; ".join(f"{k}: {v}" for k, v in a.declines.items()) or "(none)"}
    lines = [f"# Interview {today}", "", f"<!-- ds:local interview {today} -->", "",
             "| Question | Default (from) | Answer |", "|---|---|---|"]
    for q in qs:
        default = f"`{q.default}` ({q.how})" if q.default else f"({q.how})"
        lines.append(f"| {q.text} | {default} | {given[q.key]} |")
    return "\n".join(lines) + "\n"


def agent_config(today: str) -> str:
    return f"""# Written by `ds new` on {today}. Defaults for the agent system; no local model tier.
[tiers]
execute = "cortex:sonnet"      # first attempts and escalation
plan    = "cortex:opus"        # one call per task
review  = "cortex:opus"        # only when the gate asks for it

[limits]
max_attempts  = 3
context_window = 200000
token_budget  = 400000

[context]
read_manifest_first = true
graph_before_files  = true
"""


def write_all(repo: Path, name: str, a: Answers, canon: Canon, qs: list[Question], force: bool = False,
              today: str | None = None) -> list[Path]:
    """Write the curated set. Existing docs are refused unless ``force``, in which case they are
    kept under .ds/legacy/ (the migrate case) until the first successful audit."""
    today = today or date.today().isoformat()
    repo = Path(repo)
    targets = {"README.md": readme(name, a, canon, today), "AGENTS.md": None, "DECISIONS.md": decisions(today)}
    existing = [f for f in targets if (repo / f).exists()]
    if existing and not force:
        raise FileExistsError(f"{', '.join(existing)} already exist in {repo}; use --force to keep them under {LEGACY_DIR}/")
    if existing:
        (repo / LEGACY_DIR).mkdir(parents=True, exist_ok=True)
        for f in existing:
            (repo / f).rename(repo / LEGACY_DIR / f)
    (repo / ".ds").mkdir(exist_ok=True)
    written = []
    for f, content in targets.items():
        content = agents(a, canon, repo, today) if f == "AGENTS.md" else content
        (repo / f).write_text(content)
        written.append(repo / f)
    m = manifest(name, a, canon, repo, today)
    m.save()
    written.append(m.path)
    (repo / ".ds/interview.md").write_text(transcript(qs, a, today))
    written.append(repo / ".ds/interview.md")
    agent = repo / ".ds/agent.toml"
    if not agent.exists():
        agent.write_text(agent_config(today))
        written.append(agent)
    return written
