"""`ds setup` clones the canon and the shell into DS_HOME, and the verbs find them there."""
from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from conftest import write_canon, write_repo


def _bare_from(src: Path, tmp_path: Path, name: str) -> Path:
    subprocess.run(["git", "-C", str(src), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@l", "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@l", "commit", "-qm", "init"], check=True)
    bare = tmp_path / f"{name}.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(bare)], check=True)
    return bare


def test_setup_fetches_canon_and_shell(tmp_path, monkeypatch):
    from ds_cli.main import app
    canon_src = write_canon(tmp_path / "src")
    shell_src = tmp_path / "src" / "shell"
    shell_src.mkdir()
    (shell_src / "docusaurus.config.ts").write_text("export default {};\n")
    canon_url = _bare_from(canon_src, tmp_path, "canon")
    shell_url = _bare_from(shell_src, tmp_path, "shell")
    home = tmp_path / "home"
    monkeypatch.setenv("DS_HOME", str(home))
    monkeypatch.delenv("DS_CANON", raising=False)
    r = CliRunner().invoke(app, ["setup", "--canon-url", str(canon_url), "--shell-url", str(shell_url), "--home", str(home), "--no-npm"])
    assert r.exit_code == 0, r.output
    assert "canon  cloned" in r.output and "shell  cloned" in r.output and "3 standards" in r.output
    r = CliRunner().invoke(app, ["setup", "--canon-url", str(canon_url), "--shell-url", str(shell_url), "--home", str(home), "--no-npm"])
    assert "canon  updated" in r.output
    # a repo far from the clone finds the canon through DS_HOME
    repo = write_repo(tmp_path / "elsewhere")
    r = CliRunner().invoke(app, ["reconcile", str(repo)])
    assert r.exit_code == 0 and "0 pending" in r.output, r.output
    from ds_cli.config import docs_shell
    monkeypatch.setattr("ds_cli.config.DS_HOME", home)
    assert docs_shell() == home / "shell"
