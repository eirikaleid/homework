<div align="center">

# homework

**Don't let the agent grade its own homework.**

A verification pipeline for code written by AI coding agents. It catches what slips past "all tests green" and hands the agent a structured fix round.

![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-alpha-orange)
![Tests](https://img.shields.io/badge/tests-305%20passing-brightgreen)
![Typed](https://img.shields.io/badge/mypy-strict-blue)

</div>

---

## The problem

When one model writes the code and also judges it, it skips the checks that would have caught its own mistakes. On real tasks we watched an agent:

- report a feature as done when the send step was never written,
- add a UI button the spec never asked for,
- "pass" lint, test and build from a stale Turborepo cache,
- write an end-to-end test that rendered a fake page with `setContent` instead of the real app,
- inject a `window.__testHook` global into production code so that test would pass.

Telling the agent "don't do that" in the prompt does not stop it. A machine has to check.

## Features

| | |
|---|---|
| **Task contract** | A small TOML file states which paths a task may touch, which must change, which dependencies it may add and which commands prove it works. |
| **Deterministic layer** | `homework check` runs in seconds and spends zero tokens: scope diff, dependency diff, test tampering, an ast-grep rule pack, and acceptance commands re-run with every cache disabled. |
| **Independent reviewers** | `homework review` sends only the spec and the diff to fresh model sessions. They never see the agent's own report, and must answer in a strict JSON schema with `file:line` evidence per acceptance criterion. |
| **Tamper-resistant** | The contract is read from the base commit, not from the working tree the agent controls. Edits to `.gitattributes`, hidden index flags and nested repos are findings. |
| **Fail-closed** | A malformed reviewer answer, a reviewer that used tools or a skipped acceptance run never counts as a pass. |
| **Machine-readable output** | `report.json` (JSON Schema validated), `review.json` and a `fix-round.md` ready to hand back to the agent. |

## How it works

```text
task.md + contract.toml     what the task may touch, and how to prove it works
        │
        ▼
   agent writes code
        │
        ▼
Layer 1 · homework check     deterministic · no tokens · seconds
   scope · dependencies · test protection · ast-grep rules
   · acceptance commands re-run with caches disabled
        │
        ▼
Layer 2 · homework review    independent reviewers see spec + diff only
   strict JSON verdict per acceptance criterion
        │
        ├── pass → commit
        └── fail → fix-round.md → back to the agent
```

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- git
- For layer 2: [Codex CLI](https://github.com/openai/codex) (default reviewer) and optionally the Antigravity CLI `agy`

All Python dependencies, including a pinned `ast-grep` 0.51.0, install into the project's `.venv`. Nothing is installed globally.

## Quick start

```bash
git clone https://github.com/eirikaleid/homework.git
cd homework
uv sync
```

Pin the base commit **before** the agent starts. A branch name or `HEAD~1` is resolved at check time, and an agent that commits or rebases can move it.

```bash
BASE=$(git -C ../my-project rev-parse HEAD)

# ... the agent runs ...

uv run homework check  --repo ../my-project --base "$BASE" --require-acceptance
uv run homework review --repo ../my-project --base "$BASE" --task task.md
```

A minimal contract (`<repo>/.homework.toml`, or pass `--contract`):

```toml
version = 1
allowed_paths        = ["apps/web/src/**", "apps/web/package.json"]
required_paths       = ["apps/web/src/features/chat/Composer.tsx"]
allowed_dependencies = ["@floating-ui/react"]
acceptance           = ["pnpm lint && pnpm test"]

[forbidden]
paths = ["apps/web/e2e/**"]
```

The full schema (forbidden patterns, test exemptions, rule toggles, generated files, environment passthrough) is in the [reference](docs/reference.md#homework-check-layer-1).

## Exit codes

Both commands use the same contract, so a pipeline script needs one rule:

| Exit | Status | Pipeline action |
|---|---|---|
| `0` | pass | Continue. |
| `1` | fail | Hand `fix-round.md` back to the agent. |
| `2` | error | Stop: bad input, tool error, or a file in the diff that looks like a secret. |
| `3` | pass-partial | A human must approve. Never auto-pass: nothing proved the change works. |

## What gets checked

**Layer 1 (`check`)**

- **Scope:** allowed, forbidden and required paths; symlinks; forbidden regex patterns.
- **Dependencies:** `package.json`, `go.mod`, `go.work` additions, removals and git/URL/file sources; new `replace` / `use` directives.
- **Test protection:** deleted tests, `.skip` / `.only` / `.fail` (aliases included), constant assertions, fewer assertions.
- **Rule pack:** ast-grep rules for TS/TSX/JS, e.g. `setContent` fake pages, `window.__*` test hooks, DOM injection in e2e tests.
- **Acceptance:** commands re-run with caches off (`turbo --force`, `MOON_CACHE=off`, `go test -count=1`), in an allow-listed environment, optionally with an empty `HOME` (`--isolate-home`).

**Layer 2 (`review`)**

- Reviewers run in parallel, each in an empty temporary directory with a timeout.
- Codex runs with its shell tool and every other tool disabled, under a read-only permission profile.
- The diff is fenced with a random per-run nonce and treated as untrusted data.
- Reviewer text is redacted (paths, keys, tokens) before it reaches `fix-round.md`.

> [!IMPORTANT]
> `homework review` sends the task, the contract and the full diff to third-party model providers (OpenAI for Codex, Google for agy). Do not review code you are not allowed to share with them. Files that look like secrets stop the run unless you pass `--allow-secrets-risk`.

The full trust boundary, threat model and reviewer confinement are documented in [docs/reference.md](docs/reference.md).

## Roadmap

**Done**

- [x] Layer 1: `homework check`
- [x] Layer 2: `homework review` with Codex and optional agy reviewers
- [x] Regression corpus with real agent failures and clean control runs

**Planned**

- [ ] `homework loop`: write → check → review → fix round, at most 3 rounds
- [ ] Mutation testing on changed files in the final round
- [ ] `homework hook install`: a pre-tool hook that blocks out-of-scope writes before they happen
- [ ] CI for lint, type check and tests
- [ ] Packaged release on PyPI
- [ ] Demo recording and an end-to-end example task
- [ ] `CONTRIBUTING.md`

**Non-goals**

- **Not a sandbox.** homework detects; it does not contain a malicious agent. Run untrusted agents in an isolated environment.
- **Not a replacement for human review** of security-critical code. `pass-partial` exists so a human stays in the loop where proof is missing.
- **No hosted service.** Everything runs locally; the only network calls are the reviewer CLIs you choose.
- **No automatic commits or pushes.** homework reports; your pipeline decides.
- **No guarantee against unknown secret formats.** Redaction and secret detection are pattern based.

## Known limitations

- agy cannot disable its tools; tool use is detected after the fact and fails the run, which is why the agy reviewer is opt-in.
- Dependency checks cover the npm, Go and Python ecosystems only.
- Forbidden-pattern regexes use Python `re` without a timeout; very long lines are windowed and flagged.

## Development

```bash
uv run pytest            # unit and fixture tests
uv run pytest --live -m live   # calls the real reviewer CLIs (uses quota)
uv run ruff check
uv run mypy
```

## Built on

[ast-grep](https://ast-grep.github.io/), [agentdiff](https://pypi.org/project/agentdiff-cli/) (optional signal), [Codex CLI](https://github.com/openai/codex), Gemini CLI [hooks](https://geminicli.com/docs/hooks/). Background reading: [EvilGenie: A Reward Hacking Benchmark](https://arxiv.org/abs/2511.21654).

## Developer

<table>
  <tr>
    <td align="center" width="140">
      <a href="https://github.com/eirikaleid">
        <img src="https://github.com/eirikaleid.png?size=120" width="96" height="96" alt="eirikaleid"><br>
        <sub><b>eirikaleid</b></sub>
      </a>
    </td>
    <td>
      Designed and built by <a href="https://github.com/eirikaleid"><b>@eirikaleid</b></a>.<br>
      Bug reports and ideas are welcome in <a href="https://github.com/eirikaleid/homework/issues">Issues</a>.
    </td>
  </tr>
</table>

## License

[MIT](LICENSE)
