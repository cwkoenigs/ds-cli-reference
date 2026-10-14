"""Knowledge-system verbs: canon client, manifest, derived block, reconcile, render, hook, CLI.
Self-contained: a three-standard canon and one repository are written into a temp directory."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ds_cli.canon import derived, manifest as manifest_mod, reconcile
from ds_cli.canon.client import BadPin, Canon, CanonError, UnknownStandard
from ds_cli.docs import render
from ds_cli import hooks

from conftest import STANDARDS, git, write_canon, write_repo  # noqa: E402


@pytest.fixture
def world(tmp_path: Path):
    canon = write_canon(tmp_path)
    repo = write_repo(tmp_path)
    return tmp_path, Canon(canon), repo


def bump(root: Path, sid: str, version: int) -> Canon:
    current = json.loads((root / "canon/index.json").read_text())
    versions = {s["id"]: s["version"] for s in current["standards"]}
    versions[sid] = version
    return Canon(write_canon(root, versions))


# -- client ---------------------------------------------------------------------------------

def test_client_resolves_and_pins(world):
    _, canon, _ = world
    assert canon.resolve("layout").text.startswith("# Repository layout")
    with pytest.raises(BadPin):
        canon.resolve("layout", 2)
    with pytest.raises(UnknownStandard):
        canon.resolve("nope")
    assert [s.id for s in canon.applicable(["python"])] == ["adr-000", "adr-014", "layout"]
    assert [s.id for s in canon.applicable(["dbt"])] == ["adr-000", "layout"]


def test_client_locate_and_explicit_must_exist(world, tmp_path, monkeypatch):
    root, canon, repo = world
    monkeypatch.delenv("DS_CANON", raising=False)
    assert Canon.locate(None, repo).root == canon.root
    with pytest.raises(CanonError):
        Canon.locate(tmp_path / "missing", repo)


# -- manifest -------------------------------------------------------------------------------

@pytest.mark.parametrize("bad, msg", [
    ("not = [toml", "not valid TOML"),
    ("[repo]\nname='x'\ntags=['python']\n[standards.layout]\nstatus='maybe'\nversion=1\n", "status must be one of"),
    ("[repo]\nname='x'\ntags=['python']\n[standards.layout]\nstatus='declined'\nversion=1\nby='a'\non='2026-01-01'\n", "requires `reason`"),
    ("[repo]\nname='x'\ntags=['python']\n[standards.nope]\nstatus='pending'\nversion=1\n", "not a standard in the canon"),
])
def test_manifest_rejects(world, bad, msg):
    _, canon, repo = world
    (repo / ".ds/manifest.toml").write_text(bad)
    with pytest.raises(manifest_mod.ManifestError, match=msg):
        manifest_mod.for_repo(repo, canon)


def test_manifest_round_trip(world):
    _, canon, repo = world
    m = manifest_mod.for_repo(repo, canon)
    m.entries["adr-014"] = manifest_mod.Entry("adr-014", "declined", 1, "lada", "2026-10-14", "image build", "2027-01-12")
    m.save()
    assert manifest_mod.for_repo(repo, canon).entries["adr-014"].reason == "image build"


# -- derived --------------------------------------------------------------------------------

def test_derived_regenerate_tracks_code(world):
    _, _, repo = world
    assert derived.regenerate(repo) is True                       # no block yet: appended
    assert "`src/pkg/mod.py`: `load_claims`" in (repo / "AGENTS.md").read_text()
    assert derived.regenerate(repo) is False                      # idempotent
    (repo / "src/pkg/mod.py").write_text("def load_claims():\n    return []\n\ndef build_features():\n    return []\n")
    assert derived.regenerate(repo) is True
    assert "`build_features`" in (repo / "AGENTS.md").read_text()


# -- reconcile ------------------------------------------------------------------------------

def test_reconcile_clean_then_pending(world):
    root, canon, repo = world
    r = reconcile.check(repo, canon)
    assert r.exit_code == 0 and r.pending == [] and r.errors == []
    canon2 = bump(root, "adr-014", 2)
    r = reconcile.check(repo, canon2)
    assert r.exit_code == 0 and r.pending_ids() == ["adr-014@2"] and r.pending[0].code == "outdated"


def test_reconcile_errors(world):
    _, canon, repo = world
    (repo / "README.md").write_text("See [[ghost]] and [[layout@5]].\n")
    r = reconcile.check(repo, canon)
    assert r.exit_code == 1 and len(r.errors) == 2
    (repo / "README.md").write_text("fine\n")
    (repo / ".ds/manifest.toml").write_text("nope = [")
    assert reconcile.check(repo, canon).errors[0].code == "manifest"


def test_reconcile_is_fast(world):
    _, canon, repo = world
    t0 = time.perf_counter()
    for _ in range(5):
        reconcile.check(repo, canon)
    assert (time.perf_counter() - t0) / 5 < 1.0


def test_adopt_decline_round_trip(world):
    root, _, repo = world
    canon = bump(root, "adr-014", 2)
    reconcile.decline(repo, canon, "adr-014", by="ck", reason="image build", revisit="2027-01-12")
    r = reconcile.check(repo, canon)
    assert r.exit_code == 0 and r.pending == []
    canon3 = bump(root, "adr-014", 3)                              # a bumped decline is pending again
    assert reconcile.check(repo, canon3).pending_ids() == ["adr-014@3"]
    reconcile.adopt(repo, canon3, "adr-014", by="ck")
    assert reconcile.check(repo, canon3).pending == []


# -- render ---------------------------------------------------------------------------------

def test_render_links_not_prose_and_idempotent(world):
    _, canon, repo = world
    written = render.render_repo(repo, canon, canon_url="https://gitlab.example.com/ds/canon/-/blob/main")
    text = (repo / "docs/rendered/README.md").read_text()
    assert "[[" not in text and "[Repository layout (layout v1)](https://gitlab.example.com/ds/canon/-/blob/main/layout.md)" in text
    assert "src/<package>/ for code" not in text
    assert all(changed is False for _, changed in render.render_repo(repo, canon, canon_url="https://gitlab.example.com/ds/canon/-/blob/main"))


def test_print_inline(world):
    _, canon, repo = world
    out = render.print_docs(repo, canon, inline=True)
    assert "uv, not pixi (adr-014 v1)" in out and "All Python repos use uv." in out


# -- hook -----------------------------------------------------------------------------------

def test_hook_blocks_only_on_errors(world, tmp_path):
    root, canon, repo = world
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", str(bare))
    hooks.install(repo, canon.root)
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    assert git(repo, "push", "-u", "origin", branch, check=False).returncode == 0
    bump(root, "adr-014", 2)
    git(repo, "commit", "-qam", "noop", "--allow-empty")
    r = git(repo, "push", "origin", branch, check=False)
    assert r.returncode == 0 and "1 standard pending" in r.stderr and "adr-014" in r.stderr
    (repo / "README.md").write_text("See [[ghost]].\n")
    git(repo, "commit", "-qam", "break")
    r = git(repo, "push", "origin", branch, check=False)
    assert r.returncode != 0 and "ghost" in r.stderr


# -- CLI ------------------------------------------------------------------------------------

def test_cli_verbs(world):
    from ds_cli.main import app
    root, canon, repo = world
    runner = CliRunner()
    c = str(canon.root)
    r = runner.invoke(app, ["reconcile", str(repo), "--canon", c, "--timing"])
    assert r.exit_code == 0 and "0 errors, 0 pending" in r.output
    r = runner.invoke(app, ["canon", "list", str(repo), "--canon", c])
    assert r.exit_code == 0 and r.output.count("adopted by ck") == 3
    r = runner.invoke(app, ["canon", "read", "adr-014", "--canon", c, "--repo", str(repo)])
    assert r.exit_code == 0 and "All Python repos use uv." in r.output
    bump(root, "adr-014", 2)
    r = runner.invoke(app, ["reconcile", str(repo), "--canon", c, "--decline", "adr-014", "--reason", "image build", "--revisit", "2027-01-12", "--by", "ck"])
    assert r.exit_code == 0 and "declined adr-014@2" in r.output and "0 pending" in r.output
    r = runner.invoke(app, ["reconcile", str(repo), "--canon", c, "--interactive"])
    assert r.exit_code == 2
    r = runner.invoke(app, ["docs", "print", str(repo), "--canon", c])
    assert r.exit_code == 0 and "Repository layout (layout v1)" in r.output
    r = runner.invoke(app, ["docs", "render", str(repo), "--canon", c])
    assert r.exit_code == 0 and "3 changed of 3" in r.output
    (repo / "README.md").write_text("[[nope]]\n")
    assert runner.invoke(app, ["reconcile", str(repo), "--canon", c]).exit_code == 1


def test_pointers_in_code_are_not_claims(world):
    _, canon, repo = world
    (repo / "docs").mkdir()
    (repo / "docs/howto.md").write_text("Use `[[id]]` to point at a standard.\n\n```\n[[ghost]] inside a fence\n```\n\nReal: [[layout]].\n")
    r = reconcile.check(repo, canon)
    assert r.exit_code == 0 and r.errors == []
    out = render.resolve_text((repo / "docs/howto.md").read_text(), canon, lambda s: f"{s.id}.md")
    assert "`[[id]]`" in out and "[[ghost]] inside a fence" in out and "[Repository layout (layout v1)](layout.md)" in out


def test_large_surface_is_summarized(world):
    _, _, repo = world
    for i in range(15):
        (repo / f"src/pkg/m{i:02d}.py").write_text(f"def f{i}():\n    pass\n")
    assert derived.regenerate(repo) is True
    agents = (repo / "AGENTS.md").read_text()
    assert "- `src/pkg/`: 16 modules, 16 public symbols" in agents and "Full listing: `.ds/derived.md`" in agents
    assert "`f7`" in (repo / ".ds/derived.md").read_text()
    assert derived.regenerate(repo) is False
