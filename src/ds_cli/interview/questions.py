"""The eight questions, with defaults inferred from the repository and the environment.
Nothing here is hard-coded as a fact about the repo; a default is a guess the person confirms."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class Answers:
    purpose: str = ""
    owner: str = ""
    test_cmd: str = ""
    lint_cmd: str = ""
    tags: list[str] = field(default_factory=list)
    snowflake: str = ""                      # "database.schema" or ""
    notes: str = ""
    declines: dict[str, str] = field(default_factory=dict)   # id -> reason


@dataclass
class Question:
    key: str
    text: str
    default: str
    how: str          # where the default came from


def _git_user() -> str:
    try:
        return subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def _read(p: Path) -> str:
    try:
        return p.read_text()
    except Exception:
        return ""


def _pyproject(repo: Path) -> dict:
    p = repo / "pyproject.toml"
    if not p.exists():
        return {}
    try:
        return tomllib.loads(p.read_text())
    except Exception:
        return {}


def detect_tags(repo: Path) -> list[str]:
    tags: list[str] = []
    py = _pyproject(repo)
    has_py = bool(py) or (repo / "pixi.toml").exists() or any(repo.rglob("*.py"))
    if has_py:
        tags.append("python")
    if py.get("project") and (repo / "src").is_dir():
        tags.append("package")
    if (repo / "dbt_project.yml").exists():
        tags.append("dbt")
    if (repo / "Dockerfile").exists() or (repo / "dock.yaml").exists():
        tags.append("service")
    if any(repo.rglob("*.ipynb")):
        tags.append("notebook")
    blob = (_read(repo / "pyproject.toml") + _read(repo / "pixi.toml") + _read(repo / "dock.yaml")).lower()
    if "snowflake" in blob or "snowpark" in blob:
        tags.append("snowflake")
    if "streamlit" in blob:
        tags.append("streamlit")
    return tags


def detect_test_cmd(repo: Path) -> tuple[str, str]:
    mk = _read(repo / "Makefile")
    if re.search(r"^test:", mk, re.M):
        return "make test", "Makefile has a test target"
    pixi = _read(repo / "pixi.toml")
    if re.search(r"^test\s*=", pixi, re.M):
        return "pixi run test", "pixi.toml has a test task"
    py = _pyproject(repo)
    if (repo / "uv.lock").exists() or "uv" in py.get("tool", {}):
        return "uv run pytest -q", "uv project"
    if py:
        return "python -m pytest -q", "pyproject.toml present"
    return "uv run pytest -q", "default"


def detect_lint_cmd(repo: Path) -> tuple[str, str]:
    mk = _read(repo / "Makefile")
    if re.search(r"^lint:", mk, re.M):
        return "make lint", "Makefile has a lint target"
    py = _pyproject(repo)
    tool = py.get("tool", {})
    parts = []
    if "ruff" in tool or (repo / "ruff.toml").exists():
        parts.append("uv run ruff check .")
    if "mypy" in tool or (repo / "mypy.ini").exists():
        parts.append("uv run mypy .")
    if parts:
        return " && ".join(parts), "pyproject.toml tool sections"
    return "uv run ruff check . && uv run mypy .", "default"


def detect_snowflake(repo: Path) -> tuple[str, str]:
    db, schema = os.environ.get("SNOWFLAKE_DATABASE", ""), os.environ.get("SNOWFLAKE_SCHEMA", "")
    if db and schema:
        return f"{db}.{schema}", "environment"
    dock = _read(repo / "dock.yaml")
    m_db = re.search(r"^\s*database:\s*(\S+)", dock, re.M)
    m_sc = re.search(r"^\s*schema:\s*(\S+)", dock, re.M)
    if m_db and m_sc:
        return f"{m_db.group(1)}.{m_sc.group(1)}", "dock.yaml"
    return "", "not detected"


def questions(repo: Path, canon_tags: list[str] | None = None) -> list[Question]:
    test_cmd, test_how = detect_test_cmd(repo)
    lint_cmd, lint_how = detect_lint_cmd(repo)
    sf, sf_how = detect_snowflake(repo)
    tags = detect_tags(repo)
    return [
        Question("purpose", "What does this repo do, in one line?", "", "no default"),
        Question("owner", "Who owns it?", _git_user() or os.environ.get("USER", ""), "git user.name"),
        Question("test_cmd", "Test command?", test_cmd, test_how),
        Question("lint_cmd", "Lint/type command?", lint_cmd, lint_how),
        Question("tags", "Which canon tags apply? (comma-separated)", ", ".join(tags), "inferred from files"),
        Question("snowflake", "Does it talk to Snowflake? Which database.schema? (empty for no)", sf, sf_how),
        Question("notes", "Anything future-you would want to know?", "", "no default"),
        Question("declines", "Any standard you already know you'll decline? (id: reason; id: reason)", "", "no default"),
    ]


def parse_declines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in text.split(";"))):
        sid, _, reason = part.partition(":")
        if sid.strip():
            out[sid.strip()] = reason.strip() or "declined at interview"
    return out


def answers_from_file(path: Path) -> Answers:
    data = tomllib.loads(Path(path).read_text())
    declines = data.get("declines", {})
    if isinstance(declines, list):
        declines = {d: "declined at interview" for d in declines}
    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return Answers(purpose=data.get("purpose", ""), owner=data.get("owner", ""), test_cmd=data.get("test_cmd", ""),
                   lint_cmd=data.get("lint_cmd", ""), tags=list(tags), snowflake=data.get("snowflake", ""),
                   notes=data.get("notes", ""), declines=dict(declines))


def fill_defaults(answers: Answers, repo: Path) -> Answers:
    """Every empty answer takes its inferred default, so an answers file can be partial."""
    qs = {q.key: q for q in questions(repo)}
    if not answers.owner:
        answers.owner = qs["owner"].default
    if not answers.test_cmd:
        answers.test_cmd = qs["test_cmd"].default
    if not answers.lint_cmd:
        answers.lint_cmd = qs["lint_cmd"].default
    if not answers.tags:
        answers.tags = [t.strip() for t in qs["tags"].default.split(",") if t.strip()]
    if not answers.snowflake:
        answers.snowflake = qs["snowflake"].default
    return answers
