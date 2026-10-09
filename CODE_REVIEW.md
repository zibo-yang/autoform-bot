# Code review findings — AutoformBot

Date: 2026-10-03

## Scope

The review covered the whole source tree: the 65-commit range ahead of `origin/main`, plus the rest of `autoform_cli/` and `servers/`.

`make lint` and the test suite pass (757 passed, 32 skipped), so none of the findings below are caught by existing tests.

Not reviewed: `autoform_cli/probes/skeleton_probe.lean`.
Only skimmed: `coverage.py`, `mermaid.py`, `graph_views.py`, and most of `render.py`.

## How each finding was verified

| Verification | Findings |
| --- | --- |
| Reproduced by running the code | 2, 3, 4 |
| Confirmed from the lockfile and commit history | 5 |
| Confirmed by grep | 10, 11 |
| From reading the code only | 1, 6, 7, 8, 9, 12, 13, 14 |

Findings 1, 6 and 12 depend on runtime conditions that were not reproduced.

## Recommended order of work

1. Make `markdown.content()` the only Markdown parser. This fixes finding 3 and removes the duplicated fence/comment state machines in `graph.py`, `audit.py` and `render.py`.
2. Fix the LSP completion signal (finding 1).
3. Fix the lexical scanner's scope tracking (finding 2).

Findings 1 and 2 come first after the parser work because both produce wrong answers that look like success or failure of the user's Lean work.

## Findings, most severe first

### 1. Diagnostics treated as final after 1s of silence

- Location: `servers/lsp/server.py:473`
- Problem: the server treats diagnostics as complete once 1 second passes with no new message. A file with a slow failing tactic can be reported as "compiles cleanly".
- Status: not reproduced; depends on Lean's publication timing.

### 2. Lexical scanner loses namespace scope and misses some declarations

- Location: `autoform_cli/lean.py:24`
- Problem:
  - The scanner pops the enclosing namespace on `mutual … end` and `noncomputable section … end`, so `Foo.bar` is indexed as `bar`.
  - `public theorem` is not indexed at all.
  - `foo.{u}` is indexed as `foo.`.
- Status: reproduced.

### 3. `<!--` inside a code fence drops dependency links

- Location: `autoform_cli/graph.py:369`; same bug at `autoform_cli/audit.py:250`
- Problem: a literal `<!--` inside a code fence silently drops the dependency links below it, and `autoform check` still passes.
- Root cause: `graph.py`, `audit.py` and `render.py` each carry their own Markdown fence/comment parser instead of using `markdown.content()`.
- Status: reproduced.

### 4. Render deletes the old site before building the new one

- Location: `autoform_cli/render.py:278`
- Problem: the previous site is deleted before the new one is built. One non-UTF-8 `.md` file outside `roadmap/` then crashes with a traceback and leaves a partial tree.
- Status: reproduced.

### 5. Generated Pages workflow pins an old `pymdown-extensions`

- Location: `autoform_cli/templates/github/workflows/blueprint-pages.yml:66`
- Problem: the workflow template still pins `pymdown-extensions==10.21.3`, while the checker runs 11.0.1 after commit `13be889`. The checker and the published site no longer use the same renderer.
- Status: confirmed from the lockfile and commit history.

### 6. REPL restart must fit in the next request's 30s budget

- Location: `servers/repl/core.py:756`
- Problem: after a timed-out command, the REPL restart (including `import Mathlib`) has to complete within the next request's 30s budget. On a slow machine every later call fails with a startup timeout.
- Status: not reproduced.

### 7. `run_lean_code` cannot reference the project's own declarations

- Location: `servers/repl/core.py:734`
- Problem: `run_lean_code` rejects project-local imports and discards the allowed ones, so a snippet can never reference the project's own declarations. This is undocumented.

### 8. Source permalinks are relative to `--lean-root`, not the git root

- Location: `autoform_cli/lean.py:275`
- Problem: permalinks 404 when the Lake project sits in a subdirectory of the repository.

### 9. Every hover or diagnostics call forces a full re-elaboration

- Location: `servers/lsp/server.py:216`
- Problem: each hover or diagnostics call sends `didOpen` then `didClose`, forcing a full re-elaboration each time, serialized per project.

### 10. `Graph.children` is O(n) and called per node

- Location: `autoform_cli/graph.py:110`
- Problem: `Graph.children` is O(n) and is still called per node in `audit.py`, `graph_pages.py` and six places in `render.py`, so audit and render stay quadratic on large graphs.
- Status: call sites confirmed by grep.

### 11. `mem_interval_check` is never read

- Location: `servers/repl/core.py:334`
- Problem: the setting is never read. The memory limit is only checked between requests, not while a command runs.
- Status: confirmed by grep.

### 12. `_dependency_order` is recursive

- Location: `autoform_cli/skeleton.py:2380`
- Problem: a dependency chain about 1,000 deep ends in an uncaught `RecursionError`.
- Status: not reproduced.

### 13. Unreadable file reported as "0 error(s)"

- Location: `servers/lsp/server.py:152`
- Problem: an unreadable file is reported as "0 error(s)" with severity `unknown`. The file is also read with the locale encoding rather than UTF-8.

### 14. A malformed claim ref blocks its key permanently

- Location: `autoform_cli/claims.py:251`
- Problem: with a malformed claim ref, `acquire`, `renew` and `release` raise, and `cleanup` skips it, so the key stays blocked. The `acquire` docstring says malformed leases can be taken over, but the tests pin the opposite behavior.
