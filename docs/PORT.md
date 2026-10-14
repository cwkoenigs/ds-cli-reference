# PORT — bring the knowledge system into the real ds-cli

Give this file to the agent on the work machine. It needs nothing else installed.

The knowledge-system verbs were built in a reference copy of ds-cli
(`github.com/cwkoenigs/ds-cli-reference`). The team's real ds-cli
lives on GitLab and has diverged far enough that a git merge is meaningless. This skill reads the
real codebase, decides where each piece belongs in *its* structure, and ports the feature by hand.

**Hard rules.**
- Never `git merge`, `git rebase`, or `git pull` the reference into the real ds-cli.
- Never push, never open a merge request, never change the real ds-cli's default branch. All work
  happens on a new local branch; publishing is Clark's call.
- Never modify existing commands' behaviour. The feature is additive; if a name collides, rename the
  new command and say so.
- docs-ds stays its own repository. `ds docs` calls it as an external renderer; it is never copied
  into ds-cli. Rendering output goes outside the documented repository (`~/.ds/`), never into it.

## The feature, as a list of parts

Read these from the reference checkout. Each part's dependency on ds-cli internals is listed, because
that is all the port has to adapt.

| Part | Reference path | Depends on ds-cli internals |
|---|---|---|
| Canon client | `src/ds_cli/canon/client.py` | none |
| Manifest | `src/ds_cli/canon/manifest.py` | none (`tomli`/`tomli-w`) |
| Derived block | `src/ds_cli/canon/derived.py` | none |
| Reconcile | `src/ds_cli/canon/reconcile.py` | none |
| Rendering | `src/ds_cli/docs/{render,pages,docusaurus}.py` | `config.docs_shell()` |
| Hook installer | `src/ds_cli/hooks.py` | the module path of the CLI entry (`python -m ds_cli.main`) |
| Interview | `src/ds_cli/interview/{questions,render}.py` | `__version__` |
| MCP server | `src/ds_cli/mcp/server.py` | none (`mcp>=2`) |
| Commands | `src/ds_cli/commands/{canon,new,agent,setup}.py` | `config.app`, `config.console`, `PROJECTS_DIR`, `CANON_PATH`, `DS_HOME`, URLs |
| Config additions | `src/ds_cli/config.py` (the knowledge-system block) | — |
| Tests | `tests/unit/test_{canon,new,mcp,setup}.py`, `tests/integration/test_docs_site.py`, fixtures in `tests/conftest.py` and `tests/fixtures/answers.toml` | the fixtures |
| Docs | `docs/KNOWLEDGE_SYSTEM.md` | — |

The first four parts and the MCP server are self-contained: they move as packages with only an
import-path change. All adaptation is in the commands, config, hook, and tests.

## Workflow

### Step 0 — Two checkouts, side by side

1. The real ds-cli: the current directory, origin on GitLab. Confirm with `git remote -v`. Check the
   working tree is clean; if not, stop and say so.
2. The reference: this checkout (where this file lives), cloned next to the real one, never into it,
   for example `~/Developer/ds-cli-reference`. Read from it only.
3. Record the real ds-cli's current branch and commit.

### Step 1 — Read the real codebase (read-only, before planning)

Answer each from the files, not from memory of the reference:

- **Layout**: package name and path; is it still `src/ds_cli/`, or restructured (the rewrite in
  `docs/DESIGN.md` may have changed it)?
- **CLI framework and registration**: Typer? How are commands registered (import side effects in
  `main.py`, an explicit registry, entry points)? Where do shared objects (`app`, `console`) live?
- **Configuration**: how constants and paths are defined (a `config.py`, a manifest like
  `ds-manifest.yaml`, env vars, a settings class). The knowledge-system's `DS_HOME`, `CANON_PATH`,
  `CANON_URL`, `DOCS_SHELL_URL`, and `docs_shell()` must go *there*, in that style.
- **Packaging**: pixi or uv, `pyproject.toml` dependencies, Python floor. The feature needs
  `tomli-w`, `mcp>=2`, and `tomli` below 3.11; the MCP SDK needs Python 3.10+.
- **Tests**: runner, layout, fixtures, how the suite is invoked (pixi task, Makefile, CI).
- **Name collisions**: does the real CLI already have `reconcile`, `canon`, `docs`, `hooks`, `new`,
  `migrate`, `serve-mcp`, `agent`, or `setup`? Does it already use `.ds/` in projects (for example
  `.ds/status.yaml` from VISIBILITY.md) or a `ds.yaml`? List every overlap.
- **Baseline**: run the real test suite now and save the list of failures.

### Step 2 — Plan, then stop

Write the plan to `docs/decisions/<date>-knowledge-system-port.md` in the real ds-cli (§3 decision
log format if the guidebook is in use): for every part in the table, where it lands, what changes in
it, and why. Include:

- the command names, with any renames forced by collisions;
- where the config additions go and in what form;
- overlaps with existing concepts, decided explicitly. `ds.yaml` (owner, type) and `.ds/manifest.toml`
  (tags, standards) overlap: propose whether the interview reads defaults from `ds.yaml`, writes into
  it, or keeps them separate; do not merge the formats silently;
- dependencies to add and to which file;
- what is deliberately not ported, with a reason.

**⚠️ STOP.** Show the plan and wait for Clark's approval. Change nothing else until then.

### Step 3 — Port on a local branch

`git checkout -b knowledge-system` from the real ds-cli's current branch. Then, in this order, running
the knowledge-system tests after each step:

1. Copy the self-contained packages (canon, mcp, interview, docs) to their planned location and fix
   import paths only.
2. Add the config block in the real codebase's style.
3. Add the commands, rewritten to the real CLI's registration pattern and output conventions
   (its console, its error style, its exit codes). Keep the behaviour identical to the reference:
   `reconcile` exits 1 only on a broken pointer or a malformed manifest.
4. Point the hook at the real CLI's entry module.
5. Add the dependencies.
6. Port the tests and fixtures to the real test layout.
7. Add `docs/KNOWLEDGE_SYSTEM.md`, rewritten for the real command names.

Commit after each numbered step with a message naming it. Do not push.

### Step 4 — Prove it

- The knowledge-system tests pass.
- The real suite's failures are **identical** to the Step 1 baseline. Any new failure is a port bug;
  fix it or stop and report.
- `ds setup`, then in a scratch repository: `ds new` with an answers file → `ds reconcile` exits 0
  with 0 pending → `ds docs serve` renders through docs-ds → `ds serve-mcp` answers `manifest_status`.

### Step 5 — Report and stop

Report: the branch name and commits, the plan file, every rename and why, the overlap decisions,
baseline vs final test failures, and the scratch-repo proof. Then stop. Pushing the branch and opening
a merge request are Clark's decisions.

## Stopping points

- ✋ Step 0: dirty working tree in the real ds-cli.
- ✋ Step 2: always, after the plan.
- ✋ Step 4: any test that passed at baseline and fails after the port.
