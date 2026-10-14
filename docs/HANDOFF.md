# HANDOFF — the work machine

You are the agent on Clark's work machine (Cortex Code, or Claude Code). Everything below was
built and verified on Clark's personal Mac on 2026-10-13 and 2026-10-14. Your job is the half
that needs this machine: GitLab, Snowflake, Cortex Code, and the real repositories. Work in
order. Verify every step by a command before calling it done; anything you could not verify
goes in the report as "unverified", never as "done".

## Read first, in this order

1. This file.
2. `docs/KNOWLEDGE_SYSTEM.md` in this repository: the verbs as they exist.
3. In the canon repository: `README.md`, `adr/adr-000-knowledge-system.md`, then
   `docs/design/knowledge-system.md` and `docs/design/agent-system.md`.
4. `docs/PORT.md` in this repository.

Do not redesign. Decisions already made, with evidence, and not to be reopened:

- Documentation lives in every repository; standards live once in the canon; repos point with `[[id]]`.
- Docusaurus (the docs-ds shell) is the renderer behind `ds docs`. It matched GitLab's rendering on 45 of 46
  constructs; MkDocs matched 32. The MkDocs, Zensical, and report builds in ds-operations were experiments.
- There is no local model tier. Cortex (Sonnet-class) is the floor, Opus plans and reviews.
- `ds new` sits beside `ds create`; `ds migrate` is `ds new` for an existing repository.
- Cortex Code's settings location is discovered on the machine that has it, never guessed.

## State of the world

| Repository | Where it is | Status |
|---|---|---|
| ds-cli | GitHub `cwkoenigs/ds-cli`, `main` | knowledge-system verbs, 27 tests; pushed 2026-10-14 |
| canon | GitHub `cwkoenigs/canon` (private), `main` | 18 standards split from the skills-os guidebook, all `proposed`; index builder; CI with `check_index` and `portal` jobs |
| skills-os | GitHub `cwkoenigs/skills-os`, `main` | so-init, so-changes, so-capture, so-best-practice-audit retargeted; so-agent-setup added; pushed |
| docs-ds | GitHub `cwkoenigs/docs-ds`, `main` | the renderer shell only; wiki, skills, templates, sync and lint removed; pushed |
| agent-system | GitHub `cwkoenigs/agent-system` (private), `main` | dispatcher skeleton with a dry tier; GitLab queue, MR, Slack, Snowflake load are stubs |
| platform-test | GitHub `cwkoenigs/platform-test` (private), `main` | the end-to-end test, including `bench/` for S8 |

Verified on the Mac: `ds reconcile` in about 1 ms; the pre-push hook blocks only on a broken pointer or a
malformed manifest; `ds docs` renders one repo and the portal; `ds serve-mcp` answers a real stdio client;
`ds new` and `ds migrate` produce a repo that passes the check with 0 pending; `ds migrate` on a copy of
ds-cli itself: 18 standards apply, 0 errors.

## Prerequisites on this machine

**Do not merge or install this branch over the team's ds-cli.** The GitLab ds-cli has diverged from this
reference; the feature is ported into it by following `docs/PORT.md` from this reference checkout, which reads the
real codebase, writes a plan, stops for Clark's approval, ports on a local branch, and never pushes.
skills-os is not installed on the work machine.

1. Clone this reference next to the real ds-cli: `~/Developer/ds-cli-reference`.
2. In the real ds-cli (`~/code/ds-cli`, origin GitLab), follow `~/Developer/ds-cli-reference/docs/PORT.md`, including Clark's approval.
3. Reinstall `ds` from that checkout (`pipx install --force -e .`) only after Clark approves the port.
4. `ds setup` clones canon and docs-ds into `~/.ds/`. docs-ds stays its own repository; rendering happens there, never in the documented repo.

The steps below assume `ds` has the ported verbs. Use whatever command names the port settled on.

## Steps, in order

### S1. Canon to GitLab (30 min)

1. Create the project in the team's GitLab group; push `main`.
2. Fill `repos.txt` with the GitLab paths of ds-operations and ds-cli (the two acceptance repos).
3. Set the runner tag in `.gitlab-ci.yml`. Open a merge request that touches one standard, and
   confirm `check_index` runs and passes.

Verify: the `check_index` job is green on main.

### S2. ds-operations, the first acceptance repo (1 h)

1. In the checkout: `ds migrate . --answers answers.toml` with a file like:

       purpose = "<one line, from docs/index.md>"
       tags = ["python", "service", "snowflake"]
       notes = "<the one thing future-you should know>"

   Old README, AGENTS.md, DECISIONS.md are kept under `.ds/legacy/`; the six canonical pages under
   `docs/` stay as local docs.
2. `ds reconcile --timing` → `0 errors`. Fix any `error` line it prints; a pending standard is fine.
3. `ds docs serve --port 8000` and open it. Every `[[id]]` resolves; the standards pages carry the
   guidebook text.
4. **STOP and show Clark a diff** before removing the in-repo site configs: `mkdocs.yml`,
   `zensical.yml`, `scripts/build_report.py` and `scripts/report/`, the `docs` and `docs-zensical`
   dependency groups, the docs CI jobs, and `scripts/check_docs.py` (its link checking is now
   `ds reconcile`). Remove only on his word. Keep `docs/*.md` and `docs/archive/`.
5. Commit: `knowledge system: migrate; render through ds docs`.

Verify: `ds reconcile` exit 0; a push prints the pending nudge and goes through.

### S3. ds-cli, the second acceptance repo (20 min)

`ds migrate .` with purpose "Scaffold and deploy data science projects to Snowflake, and keep every
repository in step with the canon". Expected: 18 standards apply, 0 errors. Review the generated
README; the old one is in `.ds/legacy/`. Commit.

### S4. Cortex Code (45 min)

In ds-operations, follow `~/Developer/ds-cli-reference/docs/AGENT_SETUP.md`. It runs `ds agent config`, proves the server with a stdio
call, then discovers where Cortex Code reads MCP registrations on this machine from `cortex --help`
and its docs, writes the registration, and replaces `.ds/coco-settings.json`. **It asks before writing
outside the repository.** Then start Cortex Code in the repo and ask it to call `manifest_status`.

Verify: the answer names ds-operations and lists its adopted standards. Record the settings path you
found in the report; Clark needs it for the installer.

### S5. (skipped) so-capture

so-capture lives in skills-os, which is not installed on the work machine. Skip.

### S6. The portal pipeline (1 h, partly unverified)

1. Set `DOCS_SHELL_PATH` (the docs-ds GitLab path) as a CI variable on the canon project.
2. Run the `portal` job. Verify: the `site/` artifact exists and `site/index.html` lists both repos.
3. Publish: build `docs-ds/Dockerfile.static` with `SITE_DIR=site`, push to the Snowflake image
   repository, and deploy as a service with `ds deploy service` (reuse its spec; do not write a
   bespoke `ALTER SERVICE`). Uncomment and fix the job's publish lines with what actually worked.

If the runner lacks docker or snow, stop at the artifact and say so.

### S7. The dispatcher, one real task (1 h)

In agent-system: implement `GitLabQueue.pop_all` (issues labeled `agent`, token from the environment)
and the MR step in `run.py` (push the task branch, open an MR with `summary.md` as the description).
Then, in ds-operations, create one small test-gated issue labeled `agent` and run
`python -m dispatcher.run --once --tasks <from the queue> --tier cortex:sonnet`. Verify: one metrics
row, one MR with a summary a person can read in ten seconds. If `cortex --print --mode code` does not
exist in that shape, find the right invocation, fix `ladder.run_tier`, and record it.

### S8. The benchmark with real runners (as long as it takes; last)

The bench is `bench/` in the platform-test repository (`cwkoenigs/platform-test`); its README is also at
`canon/docs/design/standards-bench-README.md`. Clone it, `uv sync`, then: `bench run` for `mash` and `system` with
`--runner coco`, then `bench drift`, `bench reconcile`, `bench score`. This answers the only question
that justifies the platform: whether curated docs plus a cheap model beats raw repos plus Opus.

## Ground rules

- Commit after each step with a message naming it. Never force-push. Never push to a repo you
  did not clone in this session.
- No hostnames, tokens, account locators, or key paths in any file you write. Tokens come from the
  environment; the only place a host appears is where it already does.
- Ask once before any delete in ds-operations and before any write outside a repository.
- If a step takes more than 90 minutes, stop, write what you have and what blocked you, move on.

## Definition of done

- Canon on GitLab with `check_index` green and both acceptance repos in `repos.txt`.
- ds-operations and ds-cli pass `ds reconcile` and push through the hook.
- Cortex Code answers `manifest_status` in ds-operations, and the settings path is recorded.
- The portal artifact renders both repos; publish state recorded honestly.
- One dispatcher task closed as an MR, or the exact reason it was not.

## Report

Write `HANDOFF-REPORT.md` in ds-operations, under two screens: done and verified (command and its
last line per step), done but unverified and why, not done and where you stopped, decisions you made
where this file was silent, the Cortex Code settings path, and three things Clark should look at first.
