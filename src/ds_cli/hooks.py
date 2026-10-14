"""``ds hooks install``: a pre-push hook that runs ``ds reconcile --check``. Idempotent.
Pending standards never block a push; a broken pointer or a malformed manifest does."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

MARKER = "# ds:pre-push"
TEMPLATE = """#!/bin/sh
{marker} — runs `ds reconcile --check`. Pending standards are printed and never block.
# A broken pointer or a malformed manifest blocks the push. Reinstall with `ds hooks install`.
exec "{python}" -m ds_cli.main reconcile --check --quiet{canon} "$(git rev-parse --show-toplevel)"
"""


def install(repo: Path, canon_root: Path | None = None) -> Path:
    hooks = Path(repo) / ".git" / "hooks"
    if not hooks.is_dir():
        raise FileNotFoundError(f"{repo} is not a git repository")
    hook = hooks / "pre-push"
    canon = f' --canon "{Path(canon_root).resolve()}"' if canon_root else ""
    content = TEMPLATE.format(marker=MARKER, python=sys.executable, canon=canon)
    if hook.exists() and hook.read_text() == content:
        return hook
    if hook.exists() and MARKER not in hook.read_text():
        hook.rename(hooks / "pre-push.before-ds")
    hook.write_text(content)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook
