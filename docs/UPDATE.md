# UPDATE — corrections to earlier instructions, and next steps for skills-os and agent-system

Read this before HANDOFF.md if you received earlier instructions. Written 2026-10-14.

## What was wrong

Earlier versions of the instructions, including HANDOFF.md before this date, had these errors:

1. **They told you to merge or install a GitHub ds-cli branch into the team ds-cli.** Wrong. The team
   ds-cli on GitLab has diverged; nothing is merged into it and nothing is pushed to it. The feature is
   **ported** by following `docs/PORT.md`, which plans first and stops for Clark's approval.
2. **They pointed at `github.com/cwkoenigs/ds-cli`.** That repository is private and contains company
   details. Do not use it. The code to port is this repository, `ds-cli-reference`.
3. **They listed five or six repositories to clone.** Only three are needed for the core:

       git clone https://github.com/cwkoenigs/ds-cli-reference.git ~/Developer/ds-cli-reference
       git clone https://github.com/cwkoenigs/canon.git ~/Developer/canon
       git clone https://github.com/cwkoenigs/docs-ds.git ~/Developer/docs-ds

4. **They referred to skills (`/so-ds-port`, `/so-agent-setup`, `/so-capture`) as if skills-os were
   installed.** It is not. Use `docs/PORT.md` and `docs/AGENT_SETUP.md` in this repository instead.
5. **They used paths under `~/code` and step numbers S1 to S8.** Clones live under `~/Developer`, and
   HANDOFF.md now has S1 to S7, with S6 (dispatcher) and S7 (benchmark) optional.
6. **They said canon was private.** canon and docs-ds are public.

If you already acted on any of the above, stop and tell Clark exactly what you did before continuing.

## The order of work

1. **Core.** Clone the three repositories above, port with `docs/PORT.md`, then follow HANDOFF.md S1 to S5.
2. **skills-os** (below), once the core is ported. Interactive: used by people in their Cortex Code sessions.
3. **agent-system** (below), last. Unattended: runs on a schedule with nobody watching.

The two share nothing directly. Both read and write the canon, each repository's manifest, and GitLab,
so a decision recorded with skills-os in the afternoon is visible to the dispatcher overnight.

## Next steps: skills-os

What it adds: workflows people run in their sessions on top of the `ds` commands.

| Skill | Does |
|---|---|
| `so-capture` | turns a gotcha or discovery from a session into a draft, then flushes it to the canon as a merge request |
| `so-changes` | records repository decisions in `DECISIONS.md`; proposes team-wide ones to the canon as standards |
| `so-best-practice-audit` | audits a repository against the standards that apply to it (`ds canon list`) |
| `so-init` | runs `ds new` or `ds migrate`, then the platform interview |
| `so-agent-setup`, `so-ds-port` | the same procedures as `docs/AGENT_SETUP.md` and `docs/PORT.md`, as skills |

Steps, after the core port is approved and `ds` has the new commands:

1. **Get access.** `github.com/cwkoenigs/skills-os` is private until Clark publishes it. Stop if you cannot
   clone it.
2. `git clone https://github.com/cwkoenigs/skills-os.git ~/Developer/skills-os`, then
   `cd ~/Developer/skills-os && ./install.sh`. This links the skills into `~/.claude/skills` and
   `~/.codex/skills`. Find where Cortex Code loads skills on this machine (as AGENT_SETUP.md does for MCP)
   and link them there too; ask before writing outside the repository.
3. Check: `./tests/verify.sh` prints `7/7 passed`.
4. Configure `so-capture`: `~/.config/so-capture/config.toml` with `knowledge_repo` set to the canon's
   GitLab path (after HANDOFF S1), `captures_dir = "captures"`, `token_env = "GITLAB_TOKEN"`.
5. Prove it in ds-operations: run `/so-capture` on one real thing from the session and flush it. A merge
   request appears on the canon. Run `/so-best-practice-audit` and confirm it cites standards by id.

Done when: one capture merged into the canon, and one audit report that reads `ds canon list`.

## Next steps: agent-system

What it adds: hand-off. A GitLab issue labeled `agent` becomes a merge request overnight, or a specific
question when the agent cannot finish. Every task is measured. Its README explains the whole flow.

It is a skeleton today: the loop works with a `dry` tier that makes no edits. Four connections are not
built, and they need this machine.

Steps, after the core is done and at least one repository is migrated (the dispatcher reads the test
command from `AGENTS.md` and the tiers from `.ds/agent.toml`, which `ds migrate` writes):

1. **Get access.** `github.com/cwkoenigs/agent-system` is private until Clark publishes it. Stop if you
   cannot clone it.
2. `git clone https://github.com/cwkoenigs/agent-system.git ~/Developer/agent-system`, `uv sync`,
   `uv run pytest` (1 passes). Read its README.
3. **Cortex.** Find the headless invocation of Cortex Code on this machine and how it reports tokens; fix
   `ladder.run_tier` to match. The design's guess is `cortex --print --mode code`.
4. **GitLab queue.** Implement `GitLabQueue.pop_all`: open issues labeled `agent` in a project, token from
   `GITLAB_TOKEN`, acceptance command from the issue body or the repository's `AGENTS.md`.
5. **Merge request.** In `run.process`, push the `agent/<task-id>` branch and open an MR with `summary.md`
   as the description; comment the MR link, or the "needs you" text, on the issue.
6. **Prove it.** In ds-operations, create one small issue labeled `agent` whose acceptance is a test
   command. Run `uv run python -m dispatcher.run --once` against it. One metrics row, one MR with a summary
   a person can read in ten seconds.
7. **Later:** the Slack digest (`digest.post_slack`, webhook in `SLACK_WEBHOOK`), the nightly schedule, the
   Snowflake mirror, and a `ds task` command that creates the issue.

Done when: one real issue closed as an MR by the dispatcher.

## Ground rules (unchanged)

Never merge into or push to the team ds-cli without Clark. Ask before any delete and before any write
outside a repository. Commit after each step. Report what is verified, what is not, and why.
