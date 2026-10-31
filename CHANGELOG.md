# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `homework review` (layer 2): independent model reviewers (Codex by default, agy fresh headless
  session with `--reviewer agy`) that see only the trusted task/contract and the diff; fixed prompt
  with a nonce-fenced, untrusted diff; JSON schema `review.schema.json` with one retry; parallel runs
  with timeout and env allow-list; `review.json` + layer-2 section in `fix-round.md`; exit 0/1/2/3.
  Tests use fake reviewers; real calls are `@pytest.mark.live` (`--live`).
- `homework review` hardening against a hostile diff: reviewer text is redacted (home paths, keys,
  tokens, long hex/base64) before it reaches `fix-round.md` / `review.json`; Codex runs without a
  shell tool, under a permission profile that reads only the empty work dir and, file by file, the
  codex binary and its `codex-*` helpers (a binary in `/`, `$HOME` or a direct child of it is refused),
  with an empty `HOME`;
  agy gets the prompt on stdin (`stream-json`), and any agy tool use fails that reviewer
  (`suspicious`; only the measured plain step stream passes, an extra user turn beyond agy's own
  `--json-schema` follow-up or a stray `unknown` step does not); no schema-valid answer fails the run (`invalid`) while an infrastructure failure
  stays pass-partial; all-`unverifiable` answers are pass-partial; `items` needs at least one entry;
  reviewer process groups are killed on timeout; a pass lists its warnings; the files to be sent are
  printed to stderr and a secret in the diff (secret-like file name, untracked file content, added
  lines of tracked files) stops the run unless `--allow-secrets-risk`.
- `homework check` (layer 1): deterministic checks of an agent's change against a task contract
  (`contract.toml` / `.homework.toml`, optional task.md frontmatter).
  - scope: allowed/forbidden paths with own `**` glob matcher, symlink escapes, `required_paths`,
    forbidden regex patterns on added lines, contract self-modification;
  - dependencies: unlisted `package.json` / `go.mod` / `pyproject.toml` / `requirements.txt` additions,
    removals, version changes and key reordering;
  - test protection: deleted tests, skip/only markers, constant assertions, assertion-count drops;
  - ast-grep rule pack (pinned 0.51.0; ts/tsx separate): window `__*` hooks, e2e `setContent` /
    external URLs / DOM injection, static inline styles, `textTransform: uppercase`, commented-out code;
    regex rules for CSS `text-transform: uppercase` and duplicated numeric literals;
  - acceptance runner without build caches (moon/turbo `--force`, `go test -count=1`, env overrides),
    cache-hit detection, generator drift check; `--no-run` to skip;
  - optional `--with-agentdiff` signal;
  - `report.json` (JSON Schema `schemas/report.schema.json`) and `fix-round.md`; exit 0/1/2.
- Hardening against an agent that tries to evade the check:
  - contract and `--task` inside the repo are read from `--base`; edits are `contract-modified` /
    `task-modified` findings and block acceptance; missing from base is exit 2 unless
    `--trust-worktree-contract`;
  - acceptance env is allow-listed (`PATH`, `HOME`, `LANG`, `LC_*`, `TMPDIR`, `TERM`, `CI` +
    contract `env_passthrough`);
  - diff parsing no longer trusts patch header paths (quoted names, `"`, `\`, tab, unicode, non-UTF-8);
    `--text --no-textconv`; `.gitattributes` edits, assume-unchanged/skip-worktree flags and ignored
    files are reported;
  - `status: "pass-partial"` when acceptance is skipped, with its own exit code `3`; `--require-acceptance`
    (recommended in pipeline scripts) makes a skipped run a finding;
  - `report.json` records the resolved `base_sha`; README asks to pin `--base` to a commit id;
  - `--isolate-home` runs acceptance with an empty temporary `HOME`;
  - untracked nested git repositories (`nested-repo`) and submodule/gitlink changes (`submodule-changed`)
    are errors;
  - acceptance commands run in their own process group, timeouts kill the group and are findings,
    output kept to the last 1 MB, log and earlier findings survive errors;
  - non-registry dependency sources (git/http/file/link, `npm:` aliases, any protocol except
    `workspace:`) and new `go.mod` / `go.work` `replace` and `go.work` `use` are findings; go.mod
    blocks are parsed with any whitespace (`require\t(`) and only `\n` ends a line;
  - JavaScript/JSX rule variants (each rule/language pair has a test); aliased/bracketed/describe-level
    skip markers and `.fail`, `it.each(...).skip`, `describe.parallel.*`, `pytestmark = pytest.mark.skip`,
    `expect (true)`; `commented-out-code` no longer flags prose such as `// Retry (twice);`;
    ast-grep matches count when any added line is inside their range;
  - lines over 10 000 characters are checked by contract regexes in overlapping 4096-character windows
    and fail the run as a `line-too-long` warning; `expect(` in comments/strings
    is not counted as an assertion;
  - crashes exit 2 with a traceback, stale report files are removed, invalid globs and wrongly typed
    `package.json` sections are errors/findings instead of crashes, untracked files split on `\n` only.
- Regression tests over the measured corpus (`fixtures/`), with base snapshots extracted by
  `scripts/fixtures-snapshot.sh` so CI does not need the source repository.
