# Blueprint search and reuse: phase 1 design

Implements phase 1 of [facebookresearch/autoform-bot#143](https://github.com/facebookresearch/autoform-bot/issues/143)
against `main` at `7fa6d1d`. This file is a local working document and is not part of any pull request.

## Goal

Before adding a roadmap node or a Lean helper, an agent can ask in one deterministic, local, read-only call whether
the blueprint already contains that result, see enough to decide whether to reuse it, and record the reuse as an
ordinary dependency link.

## Scope

In scope, as five pull requests to `facebookresearch/autoform-bot`:

| PR | Branch | Delivers | Depends on |
| --- | --- | --- | --- |
| 1 | `feat/issue-143-statement-span` | One shared definition of an article's statement | `main` |
| 2 | `feat/issue-143-statement-audit` | `placeholder-statement-text` and `empty-statement-text` audit findings | PR 1 |
| 3 | `feat/issue-143-search` | `autoform search` and the `autoform-search/v1` contract | PR 1 |
| 4 | `feat/issue-143-search-skeleton` | `autoform search --skeleton REPORT` | PR 3 |
| 5 | `docs/issue-143-search-first` | Search-first rules in Roadmap, Formalize and Agent Review | PR 3 |

Out of scope:

- `duplicate-lean-target`. The maintainer tied it to #90 and #119, and the `catalog: module` concept it needs is not
  on `main`.
- Phase 2 (search across projects), blocked on #20, #18, #17.
- An `aliases` frontmatter key, `--similar-to`, and statement text in `autoform work context` (open questions 2, 4
  and 5 of the issue). Each is left out; none is needed for the goal.
- Changing `graph.py`'s own Markdown loop in `_parse_node`. It decides edges, not statements.
- Any change to `autoform-runtime/v3` or `autoform-work/v2`.

## Global constraints

- Python 3.10+, run through `uv`. No new dependency.
- Markdown under `blueprint/` stays the only authored state. Nothing in this work writes a file, an index or a cache.
- Search runs no subprocess, no network call and no Lean process.
- Public CLI and JSON shapes are contracts: new JSON is versioned, sorted by key, compact
  (`sort_keys=True, separators=(",", ":")`), and free of timestamps and absolute paths.
- `autoform_cli/README.md` is the single source of command-line truth. Skills link to it and never restate an
  invocation; `tests/test_skill_examples.py` enforces both.
- Every PR passes `make lint`, `make test` and `make check-example`.
- Line length 120. No formatter runs in CI, so match the surrounding code and do not reformat unrelated lines.
- Tests and docs change in the same PR as the behaviour they describe.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Pushing a branch and opening a PR need the user's go-ahead each time.

## PR 1: one definition of the statement

### Problem

`audit._read_article` ends the statement at the first H2 and returns a boolean. `render._split_body` ends it at the
first heading of any level, keeps fences and comments, and includes prose before the H1. An article with an H3
before its first H2 has statement text for audit and a truncated statement box on the site.

### Rule

The statement is the article body after the frontmatter and before the first H2, with the H1 line removed.

- A heading counts only when it is published: not inside a fenced block, an indented code block or an HTML comment.
  `markdown.content()` already computes that view line by line.
- Headings of level 3 and deeper do not end the statement.
- Unterminated frontmatter makes the whole document frontmatter, so the statement is empty. `load_graph` already
  rejects such an article.

### Interface

Added to `autoform_cli/markdown.py` and exported in `__all__`:

```python
@dataclass(frozen=True, slots=True)
class ArticleSection:
    title: str     # the H2 text as published
    heading: str   # the raw heading line
    body: str      # raw Markdown up to the next H2, without surrounding blank lines

@dataclass(frozen=True, slots=True)
class ArticleParts:
    statement: str                         # raw Markdown of the statement
    remainder: str                         # raw Markdown from the first H2 to the end
    sections: tuple[ArticleSection, ...]   # in document order

def article_parts(text: str) -> ArticleParts: ...

def visible_text(markdown: str) -> str: ...
```

PR 1 ships `article_parts`, `ArticleParts(statement, sections)` and `ArticleSection` only. Upstream removes API
with no caller, so `ArticleParts.remainder` was dropped and `visible_text` was never added.

PR 2 ships `visible_prose(value)` in its place. It renders the Markdown unchanged, as the site does, and returns
the visible text outside heading, `pre` and diagram elements. Masking the source first and re-rendering it was
tried and rejected: it disagreed with the published page on setext headings, comment openers in inline code and
text indented inside HTML blocks.

Only blank lines are trimmed from the ends of each part. Leading spaces stay, because four of them make a line a
code block.

### Consumers

- `audit._read_article` is replaced by `article_parts`. `missing-statement-text` fires when the masked statement has
  no non-blank line; `missing-depends-section` fires when no section title case-folds to `depends on`.
- `render._split_body` returns `parts.statement` and the sections other than the two dependency sections, both
  with headings demoted as node headings already are. `render._body_without_dependencies` is deleted.

### Behaviour changes

| Case | Audit before | Audit after | Render before | Render after |
| --- | --- | --- | --- | --- |
| H3 before the first H2 | whole span counts | same | statement cut at the H3 | statement runs to the first H2, the H3 demoted to H6 |
| Prose before the H1 | not counted | counted | in the statement | same |
| Fence only | no statement text | same | fence shown | same |
| HTML comment only | no statement text | same | comment kept in source | same |
| Indented code only | counts as statement text | no statement text | code shown | same |
| Heading inside an HTML comment | ends nothing | same | cuts the statement | ends nothing |

The bundled example has no article in any of these rows: a prototype of this PR renders it byte-identically to
`main`. No existing test pins render's cut at any heading. The PR description states the render change so the
maintainer decides it at review.

### Tests

`tests/test_markdown.py`: one test per table row, plus unterminated frontmatter, a heading inside a fence, a heading
inside a comment, an article with no H2, `sections` order and titles, CRLF input, a setext heading, an unclosed
fence, and an indented first line. `tests/test_audit.py` and
`tests/test_render.py`: the H3 and pre-H1 rows through the real commands.

### Docs

`autoform_cli/README.md`, "Articles and containment": one sentence defining the statement by the rule above.

## PR 2: a contract on the statement text

### Shared helpers

Move from `coverage.py` to `markdown.py`, made public, with coverage importing them and behaving exactly as before:

```python
PLACEHOLDER_WORDS: frozenset[str]            # was _PLACEHOLDER_EVIDENCE
def has_substance(visible: str) -> bool: ... # was _has_substance
def is_placeholder(visible: str) -> bool: ...# was _is_placeholder
def visible_prose(value: str) -> str: ...
```

As built (commit `b8cc564`): a single hyphen marks a placeholder only when space follows it, so
`Unknown-variance` is a word; this applies to coverage evidence too. The rendered-tree walk is iterative, and a
failed conversion discards the shared converter.

### Findings

For a formalizable article, exactly one of these may fire, checked in this order:

| Code | Condition |
| --- | --- |
| `missing-statement-text` (existing) | the masked statement has no non-blank line |
| `empty-statement-text` | `has_substance(visible_prose(statement))` is false |
| `placeholder-statement-text` | `is_placeholder(visible_prose(statement))` is true |

Inline code stays visible for statements. Coverage strips it because a code span is not evidence; a statement may
legitimately name a Lean identifier.

### Rubric

`skills/agent-review/references/roadmap-quality.md`, under usability: the statement uses standard notation, gives
context for each symbol, says what the result is for, and contains no proof steps. These need judgment and stay out
of the audit.

### Tests

`tests/test_audit.py`: `TODO`, `**TBD.**`, `TODO: state it` are placeholders; `Pending Mathlib PR 1234` is not;
`<span hidden>x</span>`, a lone horizontal rule and an empty link are empty; a display-math-only statement is
neither. One test asserts the bundled example produces no finding with either new code, because
`make check-example` does not run the audit. `tests/test_coverage.py` keeps passing untouched.

### Docs

`autoform_cli/README.md`, "Audit contract": the two codes and the placeholder rule.

## PR 3: `autoform search`

### Command

```bash
autoform search blueprint "separating hyperplane" --lean-root .
autoform search blueprint "non-ambiguous" --lean-root . --json --limit 20
autoform search blueprint "interlacing" --state proved --state fully_proved --declaration theorem
```

| Argument | Meaning |
| --- | --- |
| `target` | project root or blueprint directory, required, as `autoform work` resolves it |
| `query` | one string; split on whitespace into terms. One query per call, a decision recorded in [the cost note](2026-10-06-search-cost.md) |
| `--lean-root PATH` | resolve `lean:` names to a source file and line |
| `--state KEY` | keep hits whose derived state is `KEY`; repeatable; choices are the keys of `status.STATES` |
| `--declaration KIND` | keep hits whose `declaration` case-folds to `KIND`; repeatable |
| `--limit N` | positive integer, default 20 |
| `--json` | emit `autoform-search/v1` |

Exit codes: 0 with or without hits; 2 for a query with no terms, an unreadable or invalid blueprint, or an invalid
Lean root, with the message on standard error. This matches `autoform work`.

### Module

New file `autoform_cli/search.py`:

```python
SEARCH_SCHEMA = "autoform-search/v1"
USED_BY_LIMIT = 10

class SearchError(ValueError): ...

@dataclass(frozen=True, slots=True)
class SearchLeanTarget:
    declaration: str
    source_file: str | None
    line: int | None

@dataclass(frozen=True, slots=True)
class SearchHit:
    node_id: str
    article_id: str | None
    article_path: str
    title: str
    declaration: str | None
    state: str
    statement_text: str
    lean_targets: tuple[SearchLeanTarget, ...]
    mathlib: bool
    mathlib_declarations: tuple[str, ...]
    source_targets: tuple[str, ...]
    used_by: tuple[str, ...]
    used_by_count: int
    matched_fields: tuple[str, ...]
    shared_title: bool

@dataclass(frozen=True, slots=True)
class SearchResult:
    source_revision: str
    query: str
    terms: tuple[str, ...]
    states: tuple[str, ...]
    declarations: tuple[str, ...]
    limit: int
    total_matches: int
    hits: tuple[SearchHit, ...]
    def as_dict(self) -> dict[str, object]: ...
    def to_json(self) -> str: ...

def search_blueprint(
    project_or_blueprint: str | Path,
    query: str,
    *,
    lean_root: str | Path | None = None,
    states: Sequence[str] = (),
    declarations: Sequence[str] = (),
    limit: int = 20,
) -> SearchResult: ...
```

### Loading

1. `resolve_runtime_paths`, `load_graph`, `build_runtime_graph` with no Lean root. A symlinked roadmap entry or an
   escaping source target is refused exactly as for `autoform work`.
2. Each article is read once more from disk. If the SHA-256 of its bytes differs from the node's `source_sha256`,
   search raises `SearchError`. Every hit is therefore bound to the reported `source_revision`.
3. With `--lean-root`, `lean.index_project` is called once. Each `lean:` name is looked up for its file and line.
   The runtime schema is not changed to carry the line.
4. Reverse dependency edges are built once for the whole graph.

### Matching

- Normalization: Unicode NFKC, then `casefold()`, then runs of whitespace collapsed to one space. Applied to terms
  and to every field.
- A node matches when every term is a substring of at least one of its fields. Different terms may match in
  different fields.
- Fields, in rank order, with the name each takes in `matched_fields`:

  | Rank | Name | Content |
  | --- | --- | --- |
  | 0 | `title` | the H1 |
  | 1 | `lean` | `lean:` names and `mathlib_declaration` names |
  | 2 | `node_id` | the path-derived ID |
  | 3 | `statement_text` | `visible_text` of the statement |
  | 4 | `execution_notes` | `visible_text` of the `## Execution notes` section, if any |
  | 5 | `ancestors` | titles of the containing articles |

- Frontmatter other than the two name keys, fenced blocks, indented code and HTML comments are never indexed.
- Every article is searchable, including containers and prose-only pages. `--declaration` excludes articles with no
  `declaration`.

### Ordering

Hits sort by: the lowest rank among their matched fields; then `used_by_count`, larger first; then `node_id`.
`total_matches` counts hits after the filters and before `--limit`.

### Output

`statement_text` in a hit is the raw statement Markdown, so an agent gets the LaTeX as authored. `used_by` holds the
first `USED_BY_LIMIT` dependents in sorted order and `used_by_count` the full number. `shared_title` is true when
another article in the blueprint has the same title after normalization; it is advisory and never an error.

JSON document:

```json
{"schema":"autoform-search/v1","source_revision":"…","query":"…","terms":["…"],
 "filters":{"declarations":[],"states":[]},"limit":20,"total_matches":1,"hits":[{…}]}
```

Each hit serializes every `SearchHit` field; `lean_targets` entries carry `declaration`, `source_file` and `line`.

Human-readable output, every line passed through `_human_text`:

```
Non-ambiguity (infimum-loss/definitions/non-ambiguity) [af_fb4bc2e0d1d9b34cfcc377b4]
  def · fully proved · used by 2
  Lean: CabannesThesis.NonAmbiguous (src/CabannesThesis/Basic.lean:11)
  Statement: A weak observation S : Y → Prop is non-ambiguous when …
  Matched: statement_text
1 of 1 matching article(s) shown.
```

The `Statement:` line is the visible text, truncated to 200 characters. With no hits the command prints
`No matching articles.`

### Tests

New file `tests/test_search.py`:

- a hit by a word found only in the statement, only in the title, only in a `lean:` name;
- two terms matching in two different fields; a term that matches nowhere yields no hit;
- text in frontmatter, a fenced block, indented code and an HTML comment yields no hit;
- matching across case, across NFKC-equivalent forms, and across a Markdown line wrap or emphasis marker;
- ordering by field rank, then dependents, then ID;
- `--state`, `--declaration` and `--limit`, with `total_matches` unaffected by the limit;
- `used_by` capped at 10 with the full count; `shared_title` set for two articles with one title;
- JSON bytes identical across two runs, containing `source_revision` and neither the temporary directory path nor
  a timestamp;
- a symlinked roadmap entry is refused with exit 2; an article edited between load and read is refused;
- human output escapes a control character placed in a title;
- `subprocess.run` and `subprocess.Popen` are patched to fail and the command still succeeds;
- with a counter, each article is read once by search and reverse edges are built once, on a 300-article blueprint;
- an empty query exits 2; an unknown `--state` is rejected by the parser.

### Docs

`autoform_cli/README.md`: the command under "Commands" and a new "Search contract" section covering matching,
ordering, the schema and the integrity check.

## PR 4: `--skeleton REPORT`

- New flag `--skeleton PATH` naming an existing `autoform-skeleton/v4` report. Search loads it with
  `load_skeleton_report` and never runs Lean.
- `skeleton.py` exposes its blueprint fingerprint as a public `blueprint_hash(graph)`. Search refuses, with exit 2,
  a report whose `blueprint_hash` differs from that of the blueprint being searched.
- Every Lean target in a hit gains a `signature` key: the report's elaborated signature for that article and
  declaration, or `null` when no report is given or the report has no such declaration. Adding the key is additive
  within `autoform-search/v1`.
- Tests: a matching report attaches signatures; a report for another blueprint is refused; a filtered report yields
  `null` for unselected articles; a malformed report exits 2.
- Docs: the flag and the refusal in the "Search contract" section.

## PR 5: search-first rules

- `skills/roadmap/SKILL.md`, "Ground and decompose": before creating a formalizable leaf, search the blueprint for
  the result; when it exists, link to it under `## Depends on` or `## Proof depends on` instead of adding a node.
- `skills/formalize/SKILL.md`: when a proof needs a helper, search the blueprint first, then the pinned Mathlib
  checkout. A hit that is not a declared dependency of the claimed article returns to Roadmap, as a missing
  prerequisite already does.
- `skills/agent-review/references/roadmap-quality.md`: the duplicate check under "Pull-request units and DAG" names
  the search command as its evidence.
- Each skill names `autoform search` and links to the CLI reference; none restates flags.
- `tests/test_skill_examples.py`: one assertion per rule above, and `("search",)` added to the commands the
  reference must document.

## Sequencing and parallel work

PR 1 is built first. PRs 2 and 3 touch different files apart from importing from `markdown.py`, so they are built
in parallel in separate worktrees, each branched from PR 1. PRs 4 and 5 are built in parallel after PR 3. Each PR
gets its own implementation plan under `docs/superpowers/plans/`.

## Risks

- **The render boundary change is undecided upstream.** If the maintainer prefers "any heading", the rule is one
  condition in `article_parts`, and audit follows render.
- **Open PRs overlap.** #90 reworks runtime and render, #124 enforces the execution-notes contract, #141 binds
  statements to a hash. Search reads through public functions and changes no existing schema, which keeps rebases
  small. PR 1 touches `render._split_body`, the likeliest conflict with #90.
- **Search cost is linear.** Each query loads the blueprint and renders the statement of every article once: about
  1.7 s at 1,000 articles and 5 s at 3,000. See [the cost note](2026-10-06-search-cost.md) for measurements and
  options. The test asserts the read-once bound, not a time limit.
