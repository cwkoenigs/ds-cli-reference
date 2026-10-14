"""`ds new` and `ds migrate`: detection, rendering, manifest, hook, and the acceptance check
from BUILD.md D3: a fresh repo passes `ds reconcile --check` with 0 pending, AGENTS.md under 40 lines."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import write_canon, write_repo
from ds_cli.canon import manifest as manifest_mod, reconcile
from ds_cli.canon.client import Canon
from ds_cli.interview import questions as q_mod, render as r_mod

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "answers.toml"


def test_detection_from_files(tmp_path):
    repo = tmp_path / "r"
    (repo / "src" / "pkg").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname="pkg"\n[tool.ruff]\n[tool.uv]\n')
    (repo / "dbt_project.yml").write_text("name: x\n")
    (repo / "Dockerfile").write_text("FROM scratch\n")
    (repo / "dock.yaml").write_text("snowflake:\n  database: ANALYTICS_DB\n  schema: CLAIMS\n")
    assert q_mod.detect_tags(repo) == ["python", "package", "dbt", "service", "snowflake"]
    assert q_mod.detect_test_cmd(repo) == ("uv run pytest -q", "uv project")
    assert q_mod.detect_lint_cmd(repo)[0] == "uv run ruff check ."
    assert q_mod.detect_snowflake(repo) == ("ANALYTICS_DB.CLAIMS", "dock.yaml")
    (repo / "Makefile").write_text("test:\n\tpytest\n")
    assert q_mod.detect_test_cmd(repo) == ("make test", "Makefile has a test target")


def test_answers_file_partial_takes_defaults(tmp_path):
    f = tmp_path / "a.toml"
    f.write_text('purpose = "x"\ntags = "python, dbt"\n')
    a = q_mod.fill_defaults(q_mod.answers_from_file(f), tmp_path)
    assert a.tags == ["python", "dbt"] and a.test_cmd and a.lint_cmd and a.purpose == "x"
    assert q_mod.parse_declines("adr-014: pixi for now; layout") == {"adr-014": "pixi for now", "layout": "declined at interview"}


def test_new_writes_curated_set_and_passes_check(tmp_path):
    canon = Canon(write_canon(tmp_path))
    repo = tmp_path / "demo"
    repo.mkdir()
    a = q_mod.fill_defaults(q_mod.answers_from_file(FIXTURE), repo)
    written = r_mod.write_all(repo, "demo", a, canon, q_mod.questions(repo), today="2026-10-14")
    names = {p.relative_to(repo).as_posix() for p in written}
    assert names == {"README.md", "AGENTS.md", "DECISIONS.md", ".ds/manifest.toml", ".ds/interview.md", ".ds/agent.toml"}
    readme = (repo / "README.md").read_text()
    assert readme.startswith("# demo\n\n<!-- ds:local interview 2026-10-14 -->\nFeature store for claims models. Owner: ckoenigs.")
    assert "Snowflake: `ANALYTICS_DB.CLAIMS`" in readme and "adjudication table" in readme
    assert "Team standards in force are listed in AGENTS.md" in readme and "[[layout]]" not in readme
    agents = (repo / "AGENTS.md").read_text()
    assert len(agents.splitlines()) < 40
    assert "Standards in force: [[adr-000]] [[adr-014]] [[layout]]" in agents and "<!-- ds:derived" in agents
    m = manifest_mod.for_repo(repo, canon)
    assert m.entries["adr-014"].status == "declined" and m.entries["adr-014"].revisit == "2027-01-12"
    assert m.entries["layout"].status == "adopted" and m.repo_extra["created"] == "2026-10-14"
    r = reconcile.check(repo, canon)
    assert r.exit_code == 0 and r.pending == []
    transcript = (repo / ".ds/interview.md").read_text()
    assert "| What does this repo do, in one line? |" in transcript and "adr-014: Pinned to pixi" in transcript


def test_new_refuses_existing_docs_unless_force(tmp_path):
    canon = Canon(write_canon(tmp_path))
    repo = write_repo(tmp_path)                       # has README/AGENTS/DECISIONS and a manifest
    a = q_mod.fill_defaults(q_mod.answers_from_file(FIXTURE), repo)
    with pytest.raises(FileExistsError):
        r_mod.write_all(repo, "claims-features", a, canon, q_mod.questions(repo))
    old = (repo / "README.md").read_text()
    r_mod.write_all(repo, "claims-features", a, canon, q_mod.questions(repo), force=True)
    assert (repo / ".ds/legacy/README.md").read_text() == old
    assert "Feature store for claims models" in (repo / "README.md").read_text()


def test_cli_new_and_migrate(tmp_path, monkeypatch):
    from ds_cli.main import app
    canon_dir = write_canon(tmp_path)
    runner = CliRunner()
    r = runner.invoke(app, ["new", "demo", "--dir", str(tmp_path / "demo"), "--answers", str(FIXTURE), "--canon", str(canon_dir)])
    assert r.exit_code == 0, r.output
    assert "3 standards apply; 2 adopted at current versions, 1 declined; check: 0 errors, 0 pending" in r.output
    repo = tmp_path / "demo"
    assert (repo / ".git/hooks/pre-push").exists()
    log = subprocess.run(["git", "-C", str(repo), "log", "--oneline"], capture_output=True, text=True).stdout
    assert "ds new: demo" in log
    r = runner.invoke(app, ["reconcile", str(repo), "--canon", str(canon_dir)])
    assert r.exit_code == 0 and "0 pending" in r.output
    # migrate an existing repo: old docs preserved, new ones written, hook installed
    existing = write_repo(tmp_path, "legacy-repo")
    r = runner.invoke(app, ["migrate", str(existing), "--answers", str(FIXTURE), "--canon", str(canon_dir)])
    assert r.exit_code == 0, r.output
    assert (existing / ".ds/legacy/AGENTS.md").exists() and (existing / ".git/hooks/pre-push").exists()
    # a second `new` without --force refuses
    r = runner.invoke(app, ["new", "demo", "--dir", str(repo), "--answers", str(FIXTURE), "--canon", str(canon_dir)])
    assert r.exit_code == 1 and "already exist" in r.output
