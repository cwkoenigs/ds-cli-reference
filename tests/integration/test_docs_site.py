"""`ds docs build` and `ds docs portal` through the docs shell. Needs the shell checkout and Node."""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from ds_cli.canon.client import Canon
from ds_cli.config import docs_shell
from ds_cli.docs import docusaurus as site
from conftest import write_canon, write_repo

try:
    SHELL = docs_shell()
except FileNotFoundError:
    SHELL = None

pytestmark = pytest.mark.skipif(SHELL is None or shutil.which("npx") is None, reason="docs shell or npx not available")


def test_single_site_and_portal(tmp_path: Path):
    canon = Canon(write_canon(tmp_path))
    repo = write_repo(tmp_path)
    staged = site.stage_single(repo, canon, tmp_path / "stage")
    r = site.build(staged.stage, tmp_path / "site")
    assert r.returncode == 0, r.stdout + r.stderr
    html = (tmp_path / "site/index.html").read_text()
    assert "Repository layout (layout v1)" in html and (tmp_path / "site/standards/adr-014/index.html").exists()
    staged = site.stage_portal(tmp_path, canon, tmp_path / "pstage")
    r = site.build(staged.stage, tmp_path / "portal")
    assert r.returncode == 0, r.stdout + r.stderr
    rows = list(csv.DictReader((tmp_path / "portal/adoption.csv").open()))
    assert len(rows) == 3 and all(x["status"] == "adopted" for x in rows)
