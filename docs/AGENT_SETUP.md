# AGENT SETUP — register `ds serve-mcp` with the runtimes on this machine

Make the repository's standards reachable by every agent runtime on this machine. `ds serve-mcp`
exposes four tools over stdio: `read_standard`, `manifest_status`, `canon_list`, `graph_symbols`.
`ds agent config` already writes the registrations whose format is fixed. This skill handles the
one that is not — Cortex Code — and verifies all of them.

Nothing here is a guess. The Cortex Code settings location is read from the installed tool on this
machine; if it cannot be determined, the skill says so and stops rather than writing a file the
runtime never reads (the failure mode `ds agent config` avoids by marking its file unverified).

## Prerequisites

- `ds` with `ds serve-mcp` and `ds agent config` on the PATH.
- The repository has `.ds/manifest.toml` (born or migrated through `ds`). If not, run `ds migrate .`.
- A canon checkout reachable from the repository (`$DS_CANON` or `../canon`).

## Workflow

### Step 1 — Fixed-format registrations

Run `ds agent config` in the repository. It writes:

- `.mcp.json` — Claude Code reads project-scoped servers from here. Committed, so every clone gets it.
- `.ds/agent.toml` — tier and budget defaults for the dispatcher.
- `.ds/coco-settings.json` — a best guess for Cortex Code, marked `_unverified`. Step 3 replaces it.

Add `--codex` when Codex is installed on this machine; it appends `[mcp_servers.ds]` to
`~/.codex/config.toml` once.

### Step 2 — Prove the server before registering it anywhere else

Run `ds serve-mcp --repo .` through a stdio client and call `manifest_status`. The fastest check
is the repository's own test: `python -m pytest tests/unit/test_mcp.py -q` in ds-cli, or a
20-line client using the `mcp` package. A server that does not answer here will not answer inside
a runtime; stop and report the error.

### Step 3 — Cortex Code (discover, never assume)

1. Confirm Cortex Code is installed: `cortex --version`.
2. Find where it reads MCP server registrations and per-repo settings. In order:
   `cortex --help` and `cortex mcp --help` (or the nearest subcommand), the local docs it ships,
   then its config directory under `$HOME`. Record the exact path and format you found.
3. Register the server there: command `ds`, args `["serve-mcp"]`, transport stdio, scoped to this
   repository if the format supports scoping, otherwise user-level with a comment naming the repo.
   Set the default mode to `code` if the settings file carries a mode.
4. Replace `.ds/coco-settings.json` with the real content (or delete it and note the real location
   in `.ds/agent.toml` under `[runtimes] cortex = "<path>"`). Remove the `_unverified` key.

**⚠️ STOP** before writing to any file outside the repository: show the path and the exact
addition, and ask once.

### Step 4 — Verify in each runtime

For each runtime that is installed, start it in the repository and ask it to call
`manifest_status`. The answer must name this repository and list its adopted standards. Record
the result per runtime: `verified`, `not installed`, or `failed: <reason>`.

## Output

A short report: which runtimes are registered and verified, the Cortex Code settings path that was
discovered (or "could not determine" with what was tried), and the files written. No file outside
the repository is changed without the Step 3 confirmation.

## Notes

- `graph_symbols` is an AST stand-in. If a code-graph MCP (for example codebase-memory-mcp) is
  installed, register it alongside and prefer it for callers and blast radius; say so in the report.
- Re-run this skill whenever the canon moves, `ds` is upgraded, or a runtime is (re)installed.
  Everything it writes is idempotent.
- `ds new` calls `ds agent config` automatically. This skill is the per-machine half.
