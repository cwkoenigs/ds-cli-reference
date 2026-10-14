# Knowledge system verbs

The deterministic core of the repo knowledge system (canon, pointers, manifest, reconcile),
as `ds` commands. The design is the `platform` documents (knowledge-system.md, ds-cli-updates.md,
adr-000); this page is what exists in this repository today.

## What a repository carries

- `README.md`, `AGENTS.md`, `DECISIONS.md`, and optional pages under `docs/`: plain Markdown.
  Org standards are referenced as `[[id]]` pointers, never copied.
- `.ds/manifest.toml`: for every applicable standard, `adopted`, `declined`, or `pending`,
  with who, when, and for declines a reason and a revisit date.
- A derived block in `AGENTS.md` (`<!-- ds:derived -->`), regenerated from the code.

## Commands

| Command | Does | Writes |
|---|---|---|
| `ds setup` | Clones or updates the canon and the docs shell into `~/.ds/` (`DS_HOME`) and installs the shell's Node dependencies; run once per machine, again to update | `~/.ds/canon`, `~/.ds/shell` |
| `ds new NAME [--dir D] [--answers FILE]` | The interview: eight questions with inferred defaults, or an answers file. Writes the curated docs and manifest, installs the hook, commits. Does not scaffold code; run `ds create` first, then `ds new . --dir .` | README.md, AGENTS.md, DECISIONS.md, .ds/manifest.toml, .ds/interview.md, .ds/agent.toml |
| `ds migrate [REPO]` | `ds new` on an existing repository: defaults detected from its files, old docs kept under .ds/legacy/ | the same |
| `ds reconcile` | Offline check: manifest well-formed, pointers resolve, derived block current, pending standards listed. Exit 1 only on a broken pointer or a malformed manifest. | the derived block |
| `ds reconcile --adopt ID` | Record a standard as adopted at the canon's current version | the manifest |
| `ds reconcile --decline ID --reason ... --revisit YYYY-MM-DD` | Record a decline | the manifest |
| `ds canon list` | Applicable standards with their status | nothing |
| `ds canon read ID` | A standard's text | nothing |
| `ds docs` | README and AGENTS.md in the terminal with pointers resolved (`--inline` appends the standards' text) | nothing |
| `ds docs render` | The committed copy for GitLab: `docs/rendered/` with pointers as links, never prose | `docs/rendered/` |
| `ds docs serve` / `ds docs build` | The browser view through the docs shell | a build directory |
| `ds docs portal ROOT` | Every repository under ROOT plus the canon and the adoption table | a build directory |
| `ds hooks install` | Pre-push hook running `ds reconcile --check --quiet`; pending never blocks | `.git/hooks/pre-push` |
| `ds serve-mcp` | MCP server over stdio: `read_standard`, `manifest_status`, `canon_list`, `graph_symbols` | nothing |
| `ds agent config [--codex]` | Registers the server where the format is known: `.mcp.json` (Claude Code), optionally `~/.codex/config.toml`; writes a best-guess Cortex Code file marked unverified, which `/so-agent-setup` replaces | `.mcp.json`, `.ds/agent.toml`, `.ds/coco-settings.json` |

## Where things are found

- The canon: `--canon`, then `$DS_CANON`, then `canon/` beside the repository or its parents, then `~/.ds/canon`.
- The docs shell: `$DS_DOCS_SHELL`, then `~/.ds/shell`, then `~/code/docs-ds`, then `~/Developer/docs-ds`.
- `ds setup` fills `~/.ds/` from `DS_CANON_URL` and `DS_DOCS_SHELL_URL` (defaults in `config.py`).

## Not in this version

`reconcile --interactive` and `--apply`, and the dispatcher. Cortex Code registration is done by the
`so-agent-setup` skill on a machine that has Cortex Code; `ds agent config` leaves it a marked best guess.
