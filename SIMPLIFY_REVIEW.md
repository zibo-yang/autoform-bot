# Simplification and optimization advice — AutoformBot

Date: 2026-10-03

This is advice only. No source file has been changed. It complements `CODE_REVIEW.md`, which lists correctness bugs; this document covers code that works but is duplicated, dead, slow, or fixed at the wrong depth.

## Scope

Four reviews of every Python file under `autoform_cli/` and `servers/` (about 16,000 lines), one each for reuse, simplification, efficiency, and altitude (whether a fix sits at the right depth).

Not covered in depth: `coverage.py`, `claims.py`, `scaffold.py`, `doctor.py`, `mermaid.py`, `status.py`, the second half of `skeleton.py` (output staging and install), `servers/lean_client.py`, the internals of `ProjectResourceCache._acquire`, and `autoform_cli/probes/skeleton_probe.lean`.

## Recommended order

1. Fix the render link map (A1). It is the largest win and does not change output.
2. Do the other safe cleanups in part A. They are small and independent.
3. Make `markdown.content()` the single Markdown parser (B1). This is the most valuable structural change, and it also fixes finding 3 in `CODE_REVIEW.md`.
4. Take the remaining items in part B one at a time; each needs a decision.

## Part A — Safe changes (output stays identical)

Items A1 to A4 were tried in a working copy and then reverted. With them applied, lint and the test suite passed (757 passed, 32 skipped), `make check-example` passed, and the rendered site and audit output were byte-identical to the current code on the example blueprint and on two synthetic blueprints. Items A5 to A9 are from reading the code and were not tried.

### A1. `autoform render` rebuilds a full link map for every page

- Location: `_anchored_links` at `autoform_cli/render.py:1309`, called from `_rewrite_links` (`render.py:1365`) and, per focus page, from `autoform_cli/graph_pages.py:186` and `:198`.
- Problem: for each page, the function computes a link for every node in the graph, and each link resolves paths on disk. Work grows with the square of the node count. A profile at 107 nodes showed 1.5 million `lstat` calls.
- Advice:
  - In `_anchored_links`, compute the href once per target page; many nodes share one chapter page.
  - In `_rewrite_links`, compute the link only for the node a link actually points at, instead of building the whole map first.
  - In `graph_pages.py`, call `node_links(focus_page)` once per focus page, not twice.
- Measured effect on a synthetic blueprint (the example plus chained theorem leaves):

  | Blueprint | Current | With the change |
  | --- | --- | --- |
  | about 200 nodes | 27 s | 1 s |
  | about 500 nodes | 161 s | 3 s |

### A2. `Graph.children` is a linear scan called once per node

- Location: `autoform_cli/graph.py:110`. Call sites: `audit.py:143`, `graph_pages.py:51`, `render.py:309`, `:334`, `:622`, `:646`, `:822`, `:1131`.
- Problem: each call scans every node, so each pass is quadratic. Measured cost of one pass: 0.03 s at 1,000 nodes, 0.39 s at 4,000, 1.75 s at 8,400. It only matters above a few thousand nodes.
- Advice: compute the set of parent ids once and test membership, as `runtime.py:504` already does. `audit.py` needs the count, so use a `Counter` of parents there.
- Constraint: do not cache inside `Graph`. `tests/test_graph_scale.py` requires `children()` to reflect later changes to the caller's dict and pins the two-field shape of the class. A method that computes the set on demand is fine.
- This is finding 10 in `CODE_REVIEW.md`.

### A3. Dead code

- `autoform_cli/render.py`: `_inject_after_title` (`:754`), `_status_phrase` (`:1251`), `_markdown_table_cell` (`:1258`) and `_shift_headings` (`:1291`) have no callers. Two of them are near-copies of live functions (`_inject_after_lead`, `_demote_headings`), so a reader has to work out which is real. There are also six stray blank lines at `:691-697` and a stray `f""` at `:1245`.
- `servers/repl/core.py:334`: `mem_interval_check` is never read (finding 11 in `CODE_REVIEW.md`). All `LeanReplConfig(...)` constructions use keywords, so removing it shifts nothing.
- `autoform_cli/claims.py:346`: `gc()` is a compatibility alias for `cleanup()` with no caller.
- `servers/repl/pool.py:16`: `DEFAULT_PORT = 8990` has no reader.

Checked and not dead: `ClaimBoard.holds`, `ClaimBoard.heartbeat` and `Heartbeat` are used by tests, by the `execution` branch, and documented in `autoform_cli/README.md`.

### A4. Copies of helpers that `markdown.py` already provides

- Regexes: `graph.py:19-23` and `render.py:28-29` re-declare `HEADING`, `FENCE`, `LINK`, `HTML_COMMENT` and `INLINE_CODE` character for character. `audit.py:20-23` already imports them.
- Link extraction: `graph.py:393-397` re-implements `markdown.link_targets()` (`markdown.py:181`).
- `_is_within` is defined identically in `graph.py:688`, `render.py:1408` and `markdown.py:569`. Keep one and make it public. `scaffold.py:287` `_within` is deliberately different and should stay.

### A5. Parameters in `render.py` that never vary

- `_render_landing_page(targets=None)` (`:1029`) forwards to `_next_target` (`:808`), but no caller passes it, so `(targets or {}).get(node_id)` is always `None`. Its type hint is also wrong.
- `group_pages` (`:807`) and `node_ids` in `_render_overview_summary` (`:1214`) are typed optional but always supplied.
- `sources_base=None` defaults on `_rewrite_links`, `_render_chapter` and `_render_environment` are always passed.
- `_source_href` (`:556`) is a one-line wrapper with one caller.

### A6. The cycle finder is written twice in `graph.py`

- Location: `_find_cycles` (`graph.py:515-553`) and again inside `_find_rollup_cycles` (about `:647-690`).
- Advice: one `_cycles(adjacency)` helper; each caller formats its own message and keeps its own neighbour order. `_find_rollup_cycles` drops from nesting depth 6 to 3.

### A7. `autoform doctor --lean-root` indexes the Lean tree twice

- Location: `doctor.py:112` and `:154`. `build_runtime_graph` calls `index_project` (`runtime.py:309`), then `audit_graph` calls it again (`audit.py:366`), and `_source_spans` reads every Lean file a third time for line counts (`audit.py:441`).
- Cost: `index_project` measured at 5.65 s for 1,341 Lean files, so a project that size pays about 6 s extra.
- Advice: give `audit_graph` an optional `index` parameter and record line counts while indexing.
- Related: `extract_skeletons` (`skeleton.py:2005`, `:2014`) runs the full indexer a second time only to compare a digest; a digest-only helper would do.

### A8. Smaller duplicates

- `_git` helper: `scaffold.py:55-69` and `lean.py:321-333` do the same thing. `claims.py:109` is different and should stay.
- `_atomic_write`: `visualize.py:32-50` repeats `scaffold._atomic_write` (`scaffold.py:265`). Check the `_replace` test seam at `visualize.py:28` first.
- Frontmatter skipping: `render.py:1273-1278` and `:1847-1853` scan for the closing `---` by hand; `markdown.frontmatter_end()` exists. Note one difference: on unterminated frontmatter `render.py` publishes the whole file, while `frontmatter_end` yields an empty body.
- The "is this file published" filter is written three times in `render.py` (`:317-325`, `:565-568`, `:903-908`).
- The Lake project marker list appears in `servers/__init__.py:11`, `servers/lean_runtime.py:278` and `skeleton.py:87`.
- `servers/lsp/server.py:64-65` re-inlines `_inherit_clean_env()` from `servers/repl/core.py:168`.

### A9. Long functions with separable jobs

- `extract_graph_skeletons` (`skeleton.py:2040`, 155 lines): target collection and `node_ids` selection are pure and lift out cleanly.
- `_validate_probe_record` (`skeleton.py:1671`) and `_validate_trusted_record` (`:1710`) run the same seven checks.
- `LeanRuntimeServices.dispatch` (`servers/lean_runtime.py:735-776`): the two LSP arms repeat the same lease and error-handling block.
- `_adjust_line_numbers` (`servers/repl/core.py:354-371`): the `pos`/`endPos` shift is written four times.
- `skeleton.py:580`: an `isinstance` check that is always false. `skeleton.py:2107-2108`: a `None` guard followed by the same test on the next line.

## Part B — Changes that need a decision

Each of these changes behaviour in some case, removes a public name, or touches process-lifecycle code.

### B1. Make `markdown.content()` the only Markdown parser

- Problem: there are 10 hand-written code-fence scanners outside `markdown.py` — one in `graph.py:368`, one in `audit.py:250`, and eight in `render.py` (`:757`, `:777`, `:1418`, `:1538`, `:1811`, `:1857`, plus the fence-blind `_first_h1` at `:1262` and `_document_body` at `:1270`). `markdown.content()` (`markdown.py:160`) is used only by `coverage.py`.
- The scanners disagree with `content()`, so `check`, `audit` and `render` can read a different title or dependency list from the same article:

  | Input | Hand-written scanners | `markdown.content()` |
  | --- | --- | --- |
  | Closing fence with trailing text | closes the fence | stays fenced (matches the published site) |
  | `<!--` inside a fence (graph, audit) | swallows the closing fence and what follows | literal text |
  | 4-space indented code block | visible, links count | hidden |
  | Multi-line comment (graph, audit) | lines joined, line numbers shift | line count preserved |

- Why it needs a decision: in every case `content()` matches what the site publishes, so switching is a contract change. A dependency link inside an indented block or after a fence with trailing text would start or stop counting as an edge. It needs new tests.
- What `content()` would need: keep raw lines beside the masked ones with a per-line kind (code, comment, visible), own the frontmatter boundary, a `headings()` iterator, and a way to transform only visible lines for the rewriters in `render.py`.
- Intermediate step with no behaviour change: collapse the eight loops in `render.py` onto one local fence iterator.
- Size: large (four modules), mostly mechanical.

### B2. Remove the old per-project routers

- Location: `servers/repl/projects.py` (`LeanReplProjects`, whole module) and `servers/lsp/server.py:495-533` (`LeanLspProjects`).
- Problem: production uses `ProjectResourceCache` (`servers/lean_runtime.py:299`). The two routers are referenced only by `tests/test_servers.py:109-184` and the `servers/repl/__init__.py` export. About 85 lines.
- Why it needs a decision: `LeanReplProjects` is in `__all__`, and two tests go with it.

### B3. LSP: every call re-elaborates the file

- Location: `servers/lsp/server.py:155/180` and `:217/242` send `didOpen` then `didClose` on every hover or diagnostics call (finding 9 in `CODE_REVIEW.md`). `_collect_diagnostics` (`:474`) also always waits a fixed 1 s of silence.
- Advice: keep a small table of open documents per session, send `didChange` only when the text differs, and use `textDocument/waitForDiagnostics` instead of the fixed wait.
- Why it needs a decision: each open file pins a Lean worker process in memory, and the daemon's memory budget only covers REPL workers. Not measured; no Lean was started.

### B4. REPL: retirement and error classification are decided at three levels

- Location: `servers/repl/core.py:716` (`run`), `:889` (`_run`), `:936` (`_run_io`).
- Problem: 20 `self.close(...)` calls, 11 `if stderr_poison_reason is not None` guards, 10 `if run_from_env` forks and 5 copies of the "cleanup also failed" message, spread across the three layers.
- Advice: `_run_io` only raises with facts, `_run` is the single owner that retires and classifies, and `run` maps the result to raise-or-dict in one place.
- Why it needs a decision: this is process-lifecycle code, and a 1,700-line protocol test pins its message wording.

### B5. Skeleton declaration rules live in two parallel validators

- Location: `autoform_cli/skeleton.py:1662-1850` and `:596-735`.
- Advice: put the invariants on `TrustedDeclaration` / `DeclarationSkeleton` and have both ingestion paths call one checked constructor.
- Related leftovers: `format_report(..., lean_root=None)` (`:2417`) is documented as never reread, and `source_excerpt` (`:2398`) and `DeclarationSkeleton.defines` (`:176`) have only test callers. Removing them changes a public signature and three tests.

### B6. The `lean:` target list is re-parsed by each consumer

- Location: `declaration_names(node.lean or "")` at `__main__.py:255`, `audit.py:372`, `runtime.py:323`, `render.py:1668`, `skeleton.py:2057`.
- Problem: only `skeleton.py` rejects an empty or duplicated list; the other four accept the same article silently.
- Advice: parse once into a `Node.lean_targets` tuple in `graph.py`.
- Why it needs a decision: moving the rejection into `load_graph` makes `autoform check` stricter.

### B7. Lean scope tracking in the lexical scanner

- Location: `autoform_cli/lean.py:116-155`.
- Problem: two parallel stacks kept in step by hand, and `end` pops whatever is on top. This is the mechanism behind finding 2 in `CODE_REVIEW.md`.
- Advice: one block stack of `(kind, name)` entries with one opener table (`namespace`, `section`, `mutual`, with shared modifiers), and derive the namespace prefix from the stack. Under 50 lines in one module.

### B8. Three implementations of child-process supervision

- Location: `autoform_cli/skeleton.py:879-1175` (about 300 lines), `servers/repl/core.py:63-165`, `servers/lsp/server.py:62-105`.
- Problem: three teardown policies with different guarantees; the LSP one kills only the direct child.
- Advice: one supervised-process primitive shared by all three.
- Why it needs a decision: it crosses both packages and needs a neutral home if `autoform_cli` must not import from `servers`.

### B9. Graph rules are re-checked, and extended, outside `load_graph`

- Location: `autoform_cli/runtime.py:254-300`, `:395`, `:445`; `graph_views.py:502`.
- Problem: `runtime.py` re-validates graph invariants and adds symlink and source-confinement rules that `check` does not apply, so a blueprint can pass `check` and fail the runtime export. Its `_article_id` also matches `readme.md` case-insensitively where `graph.py:321` does not.
- Advice: one `validate(graph)` in `graph.py`, and decide once whether the stricter rules belong in `check`.
- Partly verified: `_discover_nodes` was not read, so `load_graph` may already reject some of these.

### B10. Other performance items

- `graph_pages.py:99` and `:138`: every chapter and scope page rebuilds whole-graph indexes. Measured for all chapter views: 0.09 s at 1,000 nodes, 1.48 s at 4,200, 5.9 s at 8,400. A bulk builder like `focus_views` (`graph_views.py:286`) would fix it; the edge-projection logic is subtle.
- `servers/repl/pool.py:56-60`: pool workers start one after another with a 2 s stagger inside the first request. The stagger looks deliberate, so changing it alters startup behaviour.
- `skeleton.py:1139-1142`: the probe wait loop scans the process table every 50 ms. Polling every 0.25 to 0.5 s would cost less, at the risk of missing a very short-lived child.

## Checked and found fine

- `load_graph` is linear (0.54 s per 1,000 nodes).
- `lean_client.py` import-time hashing and its request path.
- The per-request REPL memory check (about 1 ms).
- `render._group_nodes` and `graph_views._group_nodes` share a name but group differently on purpose.
- `render._source_revision` and `runtime._source_revision` hash different inputs.
