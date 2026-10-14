# ds-cli-reference

Reference implementation of the knowledge-system verbs: canon, manifest, `reconcile`, `ds docs`,
the pre-push hook, the `ds new` / `ds migrate` interview, the MCP server, and `ds setup`. It is
written as part of a ds-cli so it can be **ported** into the team's real ds-cli. It is not a fork
of that ds-cli and is never merged into it.

## Start here on the work machine

> **Received earlier instructions?** Read [docs/UPDATE.md](docs/UPDATE.md) first: it lists what was
> wrong and the next steps for skills-os and agent-system.

```bash
git clone https://github.com/cwkoenigs/ds-cli-reference.git ~/Developer/ds-cli-reference
git clone https://github.com/cwkoenigs/canon.git ~/Developer/canon
git clone https://github.com/cwkoenigs/docs-ds.git ~/Developer/docs-ds
```

Then open Cortex Code (or Claude Code) in your real ds-cli and say:

```
Read ~/Developer/ds-cli-reference/docs/PORT.md and follow it to port the knowledge system into this repository.
```

It reads your ds-cli, writes a port plan, and **stops for your approval** before porting on a local
branch. It never pushes or merges. After the port, [docs/HANDOFF.md](docs/HANDOFF.md) has the remaining steps.

## Contents

| Path | What |
|---|---|
| `src/ds_cli/canon/` | canon client, manifest, derived block, reconcile |
| `src/ds_cli/docs/` | terminal, GitLab copy, and browser views (through docs-ds) |
| `src/ds_cli/interview/` | `ds new` / `ds migrate` |
| `src/ds_cli/mcp/` | `ds serve-mcp` |
| `src/ds_cli/commands/` | `canon.py`, `new.py`, `agent.py`, `setup.py` |
| `src/ds_cli/config.py` | the few names the commands need; in the real ds-cli they go in its own config |
| `docs/PORT.md` | the port procedure |
| `docs/KNOWLEDGE_SYSTEM.md` | the verbs |
| `docs/AGENT_SETUP.md` | registering `ds serve-mcp` with Cortex Code |
| `docs/HANDOFF.md` | everything after the port |

## Run it standalone

```bash
python -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/pytest -q
.venv/bin/ds-ref --help
```
