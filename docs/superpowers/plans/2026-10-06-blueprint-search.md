# Blueprint Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `autoform search TARGET QUERY` tells an agent, in one local read-only call, whether the blueprint already
holds a result, with enough in each hit to decide on reuse.

**Architecture:** A new module `autoform_cli/search.py` loads the graph and runtime projection exactly as
`autoform doctor` does, rereads each article under a hash check, folds six prose and name fields plus one
full-name field for matching, and returns immutable dataclasses that serialize to `autoform-search/v1`.
`__main__.py` gains the parser and a printer in the style of `_work`. Nothing is cached or written.

**Tech Stack:** Python 3.10+, `uv`, pytest, ruff. No new dependency.

**Spec:** `/workspaces/autoform-bot/docs/superpowers/specs/2026-10-06-blueprint-search-design.md`, section
"PR 3: `autoform search`". This is PR 3 of five for
[#143](https://github.com/facebookresearch/autoform-bot/issues/143). Where this plan and the spec differ, the
section "Decisions that differ from the spec" governs; the spec is updated in Task 3.

**Where to work:** worktree `/workspaces/autoform-bot/.claude/worktrees/statement-span`, branch
`feat/issue-143-statement-span`, on top of PR 2's commit `b8cc564`. Run every command from that directory.

**Verified prototype:** every code block below was run in a scratch copy of `b8cc564`: 29 search tests pass, the
full suite is unchanged, `ruff` is clean. Two fresh reviewers attacked that prototype before this plan was written;
their findings are already applied. The scratch copy is not the implementation: write the tests first and watch
them fail.

## Global Constraints

- Python 3.10+, run through `uv`. No new dependency.
- Markdown under `blueprint/` stays the only authored state. Search writes no file, index or cache.
- Search runs no subprocess, no network call and no Lean process.
- Public CLI and JSON shapes are contracts: the JSON is versioned, sorted by key, compact
  (`sort_keys=True, separators=(",", ":")`), and free of timestamps and absolute paths.
- `autoform_cli/README.md` is the single source of command-line truth. Every line inside one of its `bash` fences
  that contains the word `autoform` is run with `--help` by `tests/test_skill_examples.py`, so keep prose out of
  fences.
- The PR passes `make lint`, `make test` and `make check-example`.
- Line length 120. No formatter runs in CI: match the surrounding code and do not reformat unrelated lines.
- Do not edit `autoform_cli/runtime.py`, `graph.py`, `lean.py`, `markdown.py`, `work.py` or any existing schema.
- **One commit for this PR.** Tasks make working commits; Task 3 squashes them into a single commit on top of
  PR 2's commit. The message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Never push and never open a pull request.** The user approves all five PRs first.
- Never `git add` anything under `docs/superpowers/`; those files live only in the main checkout.
- Never use bare `git stash` in this worktree.
- Known baseline: `tests/test_project_create.py::test_file_swapped_in_before_open_is_not_called_a_link[parent]` and
  `[ancestor]` fail on untouched `main` on this machine. Every other test must pass.

## Decisions that differ from the spec

Each was forced by evidence from the prototype review. Each goes in the PR description.

1. **A seventh field, `qualified_names`, and last-component matching for `lean` and `node_id`.** With the spec's
   fields, every article in chapter `measure-theory` matched "measure" through its path ID, and every article
   matched a word inside the project's Lean namespace. On a 2,031-article blueprint the one article whose statement
   was about a probability measure ranked 102 of 102. `lean` and `node_id` now hold only the last component of each
   name, and the full names live in a lowest-ranked field. The same article ranks 2. A full name such as
   `Project.Measure.law` or `measure/law` still finds its article.
2. **Ordering gains one tie-break.** The issue says "best matching field, then more dependents first, then node
   ID". That stays the primary key. Between hits with the same best field, the one whose worst-placed term sits in
   a better field comes first, so a title holding every term beats a title holding one common word.
3. **Matching folds more than case and width.** `hahn-banach` did not find "Hahn–Banach", `holder` did not find
   "Hölder", and a soft hyphen pasted from a PDF hid a word. The command exists to prevent duplicates, and each
   miss creates one. Accents, typographic dashes and quotes, and invisible format characters now fold away.
4. **A term loses its surrounding `$`.** The site delimits mathematics as `\(...\)`, so a formula pasted from a
   hit's `statement_text` matched nothing.
5. **`--declaration def` also keeps `noncomputable def`.** The filter compares the kind after any leading
   modifiers, as `status.is_definition` does. `def` and `definition` stay distinct.
6. **Schema additions: `article_revision` and `mathlib_file` per hit, `open_statements` at the top.** Sibling
   schemas carry them, and upstream bumps a schema version for every key added later. `filters` uses the flag
   names: `{"declaration": [...], "state": [...]}`.
7. **`visible_prose`, not `visible_text`.** Prose fields use the function PR 2 added. Subheadings and code blocks
   inside a statement are not searched, the same definition of statement prose the audit uses.
8. **Human output prints the state key.** `can_prove`, not "ready to prove", because `--state` takes the key.
9. **Loading follows `autoform doctor`.** `resolve_runtime_paths`, `load_graph`, `build_runtime_graph`, then
   `graph.nodes[id].path` for the reread. No path is resolved twice.
10. **No `signature` key yet.** See "Open decision" below.

## Risks and what the design does about them

| Risk | Outcome |
| --- | --- |
| A hit shows text the reported revision does not contain | Each article is reread and refused unless its SHA-256 is the one the graph parsed |
| Article text forges lines in terminal output | Every line built from project text passes through `_human_text`; tested with ESC and BEL |
| Search writes, caches or starts a process | None of these exist in the module; a test patches `subprocess` to fail and compares every file before and after |
| Output differs between runs or hosts | JSON is sorted and compact; tested byte-identical across runs and across project-root and blueprint-directory targets |
| One statement the renderer gives up on breaks the run | `visible_prose` returns no text for it (PR 2); the article is still found by title, and later articles are unaffected |
| Chapter slug or Lean namespace buries real matches | Decision 1 |
| Typographic variants miss an existing article | Decision 3 |
| A filter silently matches nothing | `--state` is checked by the parser; `--declaration` help names the frontmatter key and tolerates modifiers |
| Thousands of terms make the scan quadratic | The scan stops at an article's first missing term |
| A query that is not text (lone surrogate from bad `argv`) | Refused with exit 2 |
| Two Lean scans disagree | One scan, taken by search; the runtime is built without the Lean root |
| Parity with `autoform work` | Same loaders, so the same refusals: symlinked entry, escaping source target, ambiguous or escaping directory. Verified equal `source_file` on two real projects |

## Known limits (for the README or the PR description, not fixed here)

- **Cost is linear.** About 2 ms per article per call: 1.8 s at 1,000 articles. Decided in
  `docs/superpowers/specs/2026-10-06-search-cost.md` (option A).
- **Rendering is superlinear on pathological input.** A statement with 1,500 inline formulas adds about 4 s to
  every search. The cost is the site renderer's; `autoform audit` and `autoform render` pay it for the same
  article. A size cap would not bound it (a 700-deep list of 1,400 characters takes 2.6 s), so none is added.
- **`source_revision` can describe a different read.** Upstream reads each article twice, in `load_graph` and in
  `build_runtime_graph`, without comparing them. Search's hash check binds its own read to the first. Only an edit
  that is reverted between those reads, within one command, slips through. The two-line fix belongs in
  `runtime.py` and is a separate upstream change.
- **Substring matching is literal.** `map` matches `roadmap`; there is no stemming or phrase search.
- **Human output can raise `UnicodeEncodeError` on an ASCII-only terminal** for a title such as `√7`, exactly as
  `autoform work list` does. `--json` is unaffected.
- **A `declaration:` value can imitate the summary line's fields** (`theorem, proved, used by 9`). It cannot
  start a new line. `autoform work` prints frontmatter the same way.

## Open decision (does not block this plan)

PR 4 adds a `signature` key to each Lean target. Upstream bumps a schema version whenever a key is added (work v1
to v2, runtime v2 to v3). Because all five PRs are held back until approved, PR 4 can still add the key to
`autoform-search/v1` before anything ships. If PR 3 is ever submitted alone, PR 4 must ship `autoform-search/v2`.
This plan does not emit a placeholder `signature: null`.

## Review Focus

Each line has a test in Task 1 or Task 2.

1. A word that is also a chapter directory or a namespace. Expected: an article whose statement uses the word
   ranks above the chapter's other members.
2. A query typed on a plain keyboard for a title with an en dash, an accent or a soft hyphen. Expected: found.
3. An article edited while the search runs. Expected: exit 2, no partial output.
4. Control characters in a title or statement. Expected: escaped in human output, never a forged line.
5. The project root and its `blueprint` directory as target. Expected: byte-identical JSON.

## Upstream coordination

`main` is still `7fa6d1d`.

| Open PR | Overlap | What this plan does about it |
| --- | --- | --- |
| #90 | `runtime.py`, a new `catalog: module` page with a long `lean:` list, runtime v4 | Search does not touch `runtime.py`; `lean_targets` is documented as complete, not capped |
| #124 | Execution notes become one final H2 | Compatible: notes are read by section title |
| #141 (draft) | Adds its own `article_statement` and a skeleton `statement_text` | `statement_text` here is `article_parts(...).statement`; raise the shared definition on that PR |
| #165, #140, #157 | Import lines and distant hunks in `__main__.py` | None needed |

No manifest, skill tool list or bundled-example file enumerates commands. Only `autoform_cli/README.md` and
`tests/test_skill_examples.py` change besides the code.

## File Structure

| File | Change | Responsibility |
| --- | --- | --- |
| `autoform_cli/search.py` | Create | Loading, folding, matching, ordering, and the `autoform-search/v1` shape |
| `autoform_cli/__main__.py` | Modify | The `search` parser, `_search` printer, `_positive_count` |
| `autoform_cli/README.md` | Modify | The command under "Commands"; a new "Search contract" section |
| `tests/test_search.py` | Create | Library tests (Task 1) and CLI tests (Task 2) |
| `tests/test_skill_examples.py` | Modify | `("search",)` joins the commands the reference must document |

---

### Task 1: The search module

**Files:**
- Create: `autoform_cli/search.py`
- Create: `tests/test_search.py`

**Interfaces:**
- Consumes (existing): `runtime.resolve_runtime_paths`, `runtime.build_runtime_graph`, `graph.load_graph`,
  `lean.index_project`, `lean.index_failure_message`, `markdown.article_parts`, `markdown.visible_prose`.
- Produces, in `autoform_cli.search`:
  - `SEARCH_SCHEMA = "autoform-search/v1"`, `USED_BY_LIMIT = 10`
  - `class SearchError(ValueError)`
  - `SearchLeanTarget(declaration: str, source_file: str | None, line: int | None)` with `as_dict()`
  - `SearchHit` with the fields in the code below and `as_dict()`
  - `SearchResult(source_revision, open_statements, query, terms, states, declarations, limit, total_matches,
    hits)` with `as_dict()` and `to_json()`
  - `search_blueprint(project_or_blueprint, query, *, lean_root=None, states=(), declarations=(), limit=20)
    -> SearchResult`
  - `statement_preview(hit: SearchHit, width: int = 200) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_search.py` with this content:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from autoform_cli import search as search_module
from autoform_cli.runtime import RuntimeProjectionError, load_runtime_graph
from autoform_cli.search import USED_BY_LIMIT, SearchError, search_blueprint


_LEAN_SOURCE = "namespace Project\n\ntheorem separation : True := trivial\n\nend Project\n"


def _article(
    project: Path,
    relative: str,
    *,
    title: str,
    body: str = "A precise statement.",
    metadata: tuple[str, ...] = (),
    depends: tuple[str, ...] = (),
) -> Path:
    path = project / "blueprint/roadmap" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", *metadata, "---", "", f"# {title}", "", body]
    if depends:
        lines.extend(["", "## Depends on", "", *(f"- [dependency]({target})" for target in depends)])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    _article(project, "README.md", title="Book")
    _article(project, "convexity/README.md", title="Convex analysis")
    _article(
        project,
        "convexity/hyperplane.md",
        title="Separating hyperplane",
        body="Two disjoint convex sets are separated by an affine functional.",
        metadata=("declaration: theorem", "statement: formalized", "lean: Project.separation"),
    )
    _article(
        project,
        "convexity/support.md",
        title="Supporting functional",
        body="A closed convex set is the intersection of its supporting half-spaces.",
        metadata=("declaration: lemma",),
        depends=("hyperplane.md",),
    )
    return project


def _ids(project: Path, query: str, **options: object) -> list[str]:
    return [hit.node_id for hit in search_blueprint(project, query, **options).hits]


def _matched(project: Path, query: str) -> dict[str, tuple[str, ...]]:
    return {hit.node_id: hit.matched_fields for hit in search_blueprint(project, query).hits}


def test_finds_an_article_by_a_word_in_its_statement_title_or_lean_name(tmp_path: Path) -> None:
    project = _project(tmp_path)

    assert _matched(project, "affine") == {"convexity/hyperplane": ("statement_text",)}
    assert _matched(project, "separating") == {"convexity/hyperplane": ("title",)}
    assert _matched(project, "separation") == {"convexity/hyperplane": ("lean", "qualified_names")}


def test_every_term_must_occur_but_terms_may_sit_in_different_fields(tmp_path: Path) -> None:
    project = _project(tmp_path)

    assert _matched(project, "separating affine") == {"convexity/hyperplane": ("title", "statement_text")}
    assert _ids(project, "separating nowhere") == []
    assert search_blueprint(project, "Affine  affine AFFINE").terms == ("affine",)


def test_finds_an_article_by_its_mathlib_name_file_name_and_containing_titles(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(project, "convexity/duality/README.md", title="Duality")
    _article(
        project,
        "convexity/duality/hahn.md",
        title="Extension",
        metadata=("declaration: theorem", "mathlib: true", "mathlib_declaration: exists_extension_norm_eq"),
    )

    assert _ids(project, "exists_extension_norm_eq") == ["convexity/duality/hahn"]
    assert _matched(project, "hahn") == {"convexity/duality/hahn": ("node_id", "qualified_names")}
    assert _matched(project, "analysis")["convexity/duality/hahn"] == ("ancestors",)
    assert _matched(project, "duality analysis")["convexity/duality/hahn"] == ("ancestors", "qualified_names")


def test_a_directory_or_namespace_is_the_weakest_match(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(project, "measure/README.md", title="Integration")
    _article(project, "measure/law.md", title="Law", metadata=("declaration: def", "lean: Project.Measure.law"))
    _article(project, "convexity/prob.md", title="Probability", body="A probability measure has mass one.")

    assert _matched(project, "measure") == {
        "convexity/prob": ("statement_text",),
        "measure": ("node_id", "qualified_names"),
        "measure/law": ("qualified_names",),
    }
    assert _ids(project, "measure") == ["measure", "convexity/prob", "measure/law"]
    assert _ids(project, "Project.Measure.law") == ["measure/law"]
    assert _ids(project, "measure/law") == ["measure/law"]


def test_unpublished_text_is_not_searched(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(
        project,
        "convexity/quiet.md",
        title="Quiet",
        metadata=("declaration: theorem", "origin: background"),
        body=(
            "Shown text.\n\n<!-- commentword -->\n\n```lean\nfencedword\n```\n\n"
            "    indentedword\n\n<span hidden>hiddenword</span>\n\n### headingword"
        ),
    )

    assert _ids(project, "shown") == ["convexity/quiet"]
    for word in ("commentword", "fencedword", "indentedword", "hiddenword", "headingword", "background", "declaration"):
        assert _ids(project, word) == [], word


def test_matching_ignores_case_width_emphasis_and_line_wraps(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(
        project,
        "convexity/spelled.md",
        title="Spelled",
        body="A non-**ambiguous** label over ℝ is\nﬁnite, by Straße.",
        metadata=("declaration: def",),
    )

    for query in ("NON-AMBIGUOUS", "non-ambiguous label", "is finite", "over r", "Ｓpelled", "STRASSE"):
        assert _ids(project, query) == ["convexity/spelled"], query


def test_matching_ignores_accents_typographic_punctuation_and_invisible_characters(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(
        project,
        "convexity/names.md",
        title="Hahn–Banach",
        body="Hölder and Poincaré use Zorn’s lemma on semi­continuous non​negative maps.",
    )

    for query in ("hahn-banach", "holder", "poincare", "zorn's", "semicontinuous", "nonnegative", "HÖLDER"):
        assert _ids(project, query) == ["convexity/names"], query
    with pytest.raises(SearchError, match="no terms"):
        search_blueprint(project, "​ ­")


def test_a_formula_pasted_with_its_dollar_signs_matches_on_its_content(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(project, "convexity/formula.md", title="Formula", body="Let $S : Y \\to \\mathrm{Prop}$ be given.")

    assert _ids(project, "$\\mathrm{Prop}$") == ["convexity/formula"]
    assert search_blueprint(project, "$S : Y$ $$").terms == ("s", ":", "y")


def test_execution_notes_are_searched_as_published_and_rank_below_statements(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(
        project,
        "convexity/tried.md",
        title="Tried",
        body=(
            "A statement.\n\n## Execution notes\n\nThe com**pact**ness route failed.\n\n"
            "```\nnotefence\n```\n\n## Sources\n\nsourceword"
        ),
        metadata=("declaration: theorem",),
    )
    _article(project, "convexity/states.md", title="States", body="A compactness statement.")

    hits = search_blueprint(project, "compactness").hits

    assert [(hit.node_id, hit.matched_fields) for hit in hits] == [
        ("convexity/states", ("statement_text",)),
        ("convexity/tried", ("execution_notes",)),
    ]
    assert _ids(project, "sourceword") == []
    assert _ids(project, "notefence") == []


def test_hits_sort_by_best_field_then_worst_placed_term_then_dependents_then_id(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _article(project, "README.md", title="Book")
    _article(project, "c/README.md", title="Chapter")
    _article(project, "c/both.md", title="Compact operator")
    _article(project, "c/a-split.md", title="Operator", body="A compact map.")
    _article(project, "c/used.md", title="Spectrum", body="Of a compact operator.")
    _article(project, "c/alone.md", title="Resolvent", body="Of a compact operator.")
    _article(project, "c/again.md", title="Adjoint", body="Of a compact operator.")
    _article(project, "c/uses.md", title="Consumer", body="Uses it.", depends=("used.md",))

    assert _ids(project, "compact operator") == ["c/both", "c/a-split", "c/used", "c/again", "c/alone"]


def test_a_term_found_only_in_a_containing_title_does_not_demote_a_title_match(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(
        project,
        "convexity/noted.md",
        title="Unrelated",
        body="A statement.\n\n## Execution notes\n\nTried a convex separating argument.",
    )

    assert _ids(project, "convex separating")[0] == "convexity/hyperplane"


def test_fields_rank_in_the_documented_order(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _article(project, "README.md", title="Book")
    _article(project, "zeta/README.md", title="Holds the marker word")
    _article(project, "zeta/f-ancestor.md", title="Under")
    _article(project, "zeta/e-notes.md", title="Notes", body="A statement.\n\n## Execution notes\n\nmarker")
    _article(project, "zeta/d-statement.md", title="Statement", body="The marker.")
    _article(project, "zeta/marker.md", title="Path")
    _article(project, "zeta/b-lean.md", title="Lean", metadata=("declaration: def", "lean: Project.marker"))
    _article(project, "zeta/a-title.md", title="Marker")
    _article(project, "zeta/g-full.md", title="Full", metadata=("declaration: def", "lean: Marker.other"))

    assert _ids(project, "marker") == [
        "zeta",
        "zeta/a-title",
        "zeta/b-lean",
        "zeta/marker",
        "zeta/d-statement",
        "zeta/e-notes",
        "zeta/f-ancestor",
        "zeta/g-full",
    ]


def test_filters_and_limit_narrow_the_hits_but_not_the_count(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(project, "convexity/hull.md", title="Convex hull", metadata=("declaration: noncomputable DEF",))

    assert _ids(project, "convex") == [
        "convexity",
        "convexity/hull",
        "convexity/hyperplane",
        "convexity/support",
    ]
    assert _ids(project, "convex", declarations=["Theorem"]) == ["convexity/hyperplane"]
    assert _ids(project, "convex", declarations=["theorem", "lemma"]) == [
        "convexity/hyperplane",
        "convexity/support",
    ]
    assert _ids(project, "convex", declarations=["def"]) == ["convexity/hull"]
    assert _ids(project, "convex", states=["can_prove"]) == ["convexity/hyperplane"]
    limited = search_blueprint(project, "convex", limit=1)
    assert [hit.node_id for hit in limited.hits] == ["convexity"]
    assert limited.total_matches == 4
    with pytest.raises(SearchError, match="positive integer"):
        search_blueprint(project, "convex", limit=0)


def test_a_hit_names_at_most_ten_dependents_and_counts_them_all(tmp_path: Path) -> None:
    project = _project(tmp_path)
    for index in range(USED_BY_LIMIT + 2):
        _article(project, f"convexity/use{index:02d}.md", title=f"Use {index}", depends=("hyperplane.md",))

    hit = search_blueprint(project, "separating").hits[0]

    assert hit.used_by_count == USED_BY_LIMIT + 3
    assert hit.used_by == ("convexity/support", *(f"convexity/use{index:02d}" for index in range(9)))


def test_a_title_shared_with_another_article_is_marked(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(project, "convexity/again.md", title="separating  HYPERPLANE")

    assert [hit.shared_title for hit in search_blueprint(project, "separating").hits] == [True, True]
    assert [hit.shared_title for hit in search_blueprint(project, "supporting").hits] == [False]


def test_a_lean_target_reports_its_file_and_line(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "Project.lean").write_text(_LEAN_SOURCE, encoding="utf-8")

    located = search_blueprint(project, "separating", lean_root=project).hits[0].lean_targets[0]
    unlocated = search_blueprint(project, "separating").hits[0].lean_targets[0]

    assert located.as_dict() == {"declaration": "Project.separation", "line": 3, "source_file": "Project.lean"}
    assert unlocated.as_dict() == {"declaration": "Project.separation", "line": None, "source_file": None}
    with pytest.raises(SearchError, match="Lean root does not exist"):
        search_blueprint(project, "separating", lean_root=tmp_path / "missing")


def test_a_project_and_its_blueprint_directory_give_the_same_result(tmp_path: Path) -> None:
    project = _project(tmp_path)

    assert search_blueprint(project / "blueprint", "convex").to_json() == search_blueprint(project, "convex").to_json()


def test_a_symlinked_roadmap_entry_is_refused(tmp_path: Path) -> None:
    project = _project(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("---\n---\n\n# Outside\n\nconvex\n", encoding="utf-8")
    (project / "blueprint/roadmap/convexity/linked.md").symlink_to(outside)

    with pytest.raises(RuntimeProjectionError):
        search_blueprint(project, "convex")


def test_an_article_edited_while_the_blueprint_is_searched_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    build = search_module.build_runtime_graph

    def edit_after_building(*args: object, **kwargs: object):
        runtime = build(*args, **kwargs)
        (project / "blueprint/roadmap/convexity/support.md").write_text("# Rewritten\n", encoding="utf-8")
        return runtime

    monkeypatch.setattr(search_module, "build_runtime_graph", edit_after_building)

    with pytest.raises(SearchError, match="convexity/support: the article changed while"):
        search_blueprint(project, "convex")


def test_a_query_that_is_not_text_is_refused(tmp_path: Path) -> None:
    project = _project(tmp_path)

    for query in ("", "   ", "$"):
        with pytest.raises(SearchError, match="no terms"):
            search_blueprint(project, query)
    with pytest.raises(SearchError, match="not valid Unicode"):
        search_blueprint(project, "convex\udcff")


def test_search_writes_nothing_and_starts_no_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    (project / "Project.lean").write_text(_LEAN_SOURCE, encoding="utf-8")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("search must not start a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    before = {path: path.read_bytes() for path in sorted(project.rglob("*")) if path.is_file()}

    assert search_blueprint(project, "convex", lean_root=project).total_matches == 3

    assert {path: path.read_bytes() for path in sorted(project.rglob("*")) if path.is_file()} == before


def test_each_article_is_read_once_and_rendered_at_most_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    _article(project, "README.md", title="Book")
    _article(project, "c/README.md", title="Chapter")
    for index in range(300):
        _article(
            project,
            f"c/a{index:03d}.md",
            title=f"Result {index}",
            depends=(f"a{index - 1:03d}.md",) if index else (),
        )
    reads: list[str] = []
    renders: list[str] = []
    read, prose = search_module._article, search_module.visible_prose
    monkeypatch.setattr(search_module, "_article", lambda path, node: reads.append(node.id) or read(path, node))
    monkeypatch.setattr(search_module, "visible_prose", lambda value: renders.append(value) or prose(value))

    result = search_blueprint(project, "result precise", limit=5)

    assert result.total_matches == 300
    assert sorted(reads) == sorted(node.id for node in load_runtime_graph(project).nodes)
    assert len(renders) == len(reads)


def test_a_statement_the_renderer_gives_up_on_is_still_found_by_its_title(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(project, "convexity/deep.md", title="Deeply nested", body="- " * 500 + "x")

    assert _ids(project, "nested") == ["convexity/deep"]
    assert _ids(project, "affine") == ["convexity/hyperplane"]


def test_the_bundled_example_answers_a_reuse_question(repo_root: Path) -> None:
    project = repo_root / "skills/setup/assets/cabannes-thesis-project"

    hit = search_blueprint(project, "NonAmbiguous at most one eligible", lean_root=project).hits[0]

    assert hit.node_id == "infimum-loss/definitions/non-ambiguity"
    assert hit.state == "fully_proved"
    assert [target.as_dict() for target in hit.lean_targets] == [
        {"declaration": "CabannesThesis.NonAmbiguous", "line": 11, "source_file": "src/CabannesThesis/Basic.lean"}
    ]
    assert hit.used_by_count == 2
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_search.py -q 2>&1 | tail -5`
Expected: collection error, `ImportError: cannot import name 'search' from 'autoform_cli'`.

- [ ] **Step 3: Write the module**

Create `autoform_cli/search.py` with this content:

```python
"""Read-only search over the articles of one Markdown blueprint."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .graph import load_graph
from .lean import SourceIndex, index_failure_message, index_project
from .markdown import ArticleParts, article_parts, visible_prose
from .runtime import RuntimeNode, build_runtime_graph, resolve_runtime_paths


SEARCH_SCHEMA = "autoform-search/v1"
#: How many dependents a hit names; ``used_by_count`` is never capped.
USED_BY_LIMIT = 10
#: Indexed fields, best first. A field's position is the rank its matches sort by.
#: ``lean`` and ``node_id`` hold only the last component of each name, so a
#: chapter's directory or a project's namespace does not make every article
#: beneath it a strong match; ``qualified_names`` holds the names in full.
_FIELDS = ("title", "lean", "node_id", "statement_text", "execution_notes", "ancestors", "qualified_names")
#: Dashes and quotation marks a typist replaces with the keyboard's own.
_PLAIN_PUNCTUATION = str.maketrans(
    {
        **dict.fromkeys("\u2010\u2011\u2012\u2013\u2014\u2015\u2212", "-"),
        **dict.fromkeys("\u2018\u2019", "'"),
        **dict.fromkeys("\u201c\u201d", '"'),
    }
)


class SearchError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SearchLeanTarget:
    declaration: str
    source_file: str | None
    line: int | None

    def as_dict(self) -> dict[str, int | str | None]:
        return {
            "declaration": self.declaration,
            "line": self.line,
            "source_file": self.source_file,
        }


@dataclass(frozen=True, slots=True)
class SearchHit:
    node_id: str
    article_id: str | None
    article_path: str
    #: SHA-256 of the article's bytes, which is unchanged by an edit elsewhere.
    article_revision: str
    title: str
    declaration: str | None
    state: str
    #: The statement as authored, so mathematics arrives as the LaTeX it was written in.
    statement_text: str
    lean_targets: tuple[SearchLeanTarget, ...]
    mathlib: bool
    mathlib_declarations: tuple[str, ...]
    mathlib_file: str | None
    source_targets: tuple[str, ...]
    used_by: tuple[str, ...]
    used_by_count: int
    matched_fields: tuple[str, ...]
    #: Another article has this title. Advisory: two chapters may each have a "Main theorem".
    shared_title: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "article_id": self.article_id,
            "article_path": self.article_path,
            "article_revision": self.article_revision,
            "declaration": self.declaration,
            "lean_targets": [target.as_dict() for target in self.lean_targets],
            "matched_fields": list(self.matched_fields),
            "mathlib": self.mathlib,
            "mathlib_declarations": list(self.mathlib_declarations),
            "mathlib_file": self.mathlib_file,
            "node_id": self.node_id,
            "shared_title": self.shared_title,
            "source_targets": list(self.source_targets),
            "state": self.state,
            "statement_text": self.statement_text,
            "title": self.title,
            "used_by": list(self.used_by),
            "used_by_count": self.used_by_count,
        }


@dataclass(frozen=True, slots=True)
class SearchResult:
    source_revision: str
    open_statements: bool
    query: str
    terms: tuple[str, ...]
    states: tuple[str, ...]
    declarations: tuple[str, ...]
    limit: int
    total_matches: int
    hits: tuple[SearchHit, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": SEARCH_SCHEMA,
            "source_revision": self.source_revision,
            "open_statements": self.open_statements,
            "query": self.query,
            "terms": list(self.terms),
            "filters": {"declaration": list(self.declarations), "state": list(self.states)},
            "limit": self.limit,
            "total_matches": self.total_matches,
            "hits": [hit.as_dict() for hit in self.hits],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


def search_blueprint(
    project_or_blueprint: str | Path,
    query: str,
    *,
    lean_root: str | Path | None = None,
    states: Sequence[str] = (),
    declarations: Sequence[str] = (),
    limit: int = 20,
) -> SearchResult:
    """Return the articles in which every term of ``query`` occurs.

    Nothing is written and nothing is kept between calls: each one reads the
    blueprint again, so a hit describes the Markdown as it is now.
    """

    terms = _terms(query)
    if not terms:
        raise SearchError("search query has no terms")
    if limit < 1:
        raise SearchError("search limit must be a positive integer")
    wanted_states = tuple(sorted(set(states)))
    wanted_declarations = tuple(sorted({_normalize(declaration) for declaration in declarations} - {""}))

    paths = resolve_runtime_paths(project_or_blueprint)
    graph = load_graph(paths.blueprint_dir)
    # The runtime is built without the Lean root and the sources are indexed
    # here, once, because a hit reports a declaration's line as well as its file.
    runtime = build_runtime_graph(graph, project_root=paths.project_root)
    lean_index = _lean_index(lean_root)
    nodes = {node.id: node for node in runtime.nodes}

    used_by: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    title_count: dict[str, int] = {}
    for node in runtime.nodes:
        for dependency in node.dependencies:
            used_by[dependency].append(node.id)
        title = _normalize(node.title)
        title_count[title] = title_count.get(title, 0) + 1

    matches: list[tuple[int, int, SearchHit]] = []
    for node in runtime.nodes:
        if wanted_states and node.status.state not in wanted_states:
            continue
        if wanted_declarations and not _declares(node, wanted_declarations):
            continue
        revision, text = _article(graph.nodes[node.id].path, node)
        parts = article_parts(text)
        fields = _fields(node, nodes, parts)
        # Each term's best field. A term found nowhere rules the article out.
        ranks: list[int] = []
        for term in terms:
            rank = next((rank for rank, name in enumerate(_FIELDS) if term in fields[name]), None)
            if rank is None:
                break
            ranks.append(rank)
        else:
            dependents = sorted(used_by[node.id])
            hit = SearchHit(
                node_id=node.id,
                article_id=node.article_id,
                article_path=node.article_path,
                article_revision=revision,
                title=node.title,
                declaration=node.declaration,
                state=node.status.state,
                statement_text=parts.statement,
                lean_targets=tuple(_lean_target(target.declaration, lean_index) for target in node.lean_targets),
                mathlib=node.mathlib,
                mathlib_declarations=node.mathlib_declarations,
                mathlib_file=node.mathlib_file,
                source_targets=node.source_targets,
                used_by=tuple(dependents[:USED_BY_LIMIT]),
                used_by_count=len(dependents),
                matched_fields=tuple(name for name in _FIELDS if any(term in fields[name] for term in terms)),
                shared_title=title_count[_normalize(node.title)] > 1,
            )
            matches.append((min(ranks), max(ranks), hit))

    # Best field first. Among equals, the article whose worst-placed term sits
    # in a better field, then the one more articles depend on.
    matches.sort(key=lambda match: (match[0], match[1], -match[2].used_by_count, match[2].node_id))
    return SearchResult(
        source_revision=runtime.source_revision,
        open_statements=runtime.open_statements,
        query=query,
        terms=terms,
        states=wanted_states,
        declarations=wanted_declarations,
        limit=limit,
        total_matches=len(matches),
        hits=tuple(hit for _best, _worst, hit in matches[:limit]),
    )


def statement_preview(hit: SearchHit, width: int = 200) -> str:
    """Return the start of a hit's statement as a reader sees it, on one line."""

    prose = visible_prose(hit.statement_text)
    return prose if len(prose) <= width else prose[: width - 3].rstrip() + "..."


def _normalize(text: str) -> str:
    """Fold ``text`` so spellings a reader takes for the same string compare equal.

    Case, width, ligatures, accents, typographic dashes and quotes, and
    invisible characters such as a soft hyphen all fold away, because the
    person searching types none of them the way a source happened to.
    """

    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(
        character for character in decomposed if unicodedata.category(character) not in ("Mn", "Cf")
    ).translate(_PLAIN_PUNCTUATION)
    return " ".join(unicodedata.normalize("NFKC", plain).casefold().split())


def _terms(query: str) -> tuple[str, ...]:
    """Split a query into the distinct terms an article must contain."""

    if any(unicodedata.category(character) == "Cs" for character in query):
        raise SearchError("search query is not valid Unicode text")
    # A formula pasted with its dollar signs is matched on its content, since
    # the published text delimits mathematics differently.
    return tuple(dict.fromkeys(term for word in _normalize(query).split() if (term := word.strip("$"))))


def _declares(node: RuntimeNode, kinds: tuple[str, ...]) -> bool:
    """Whether ``node`` declares one of ``kinds``, with or without leading modifiers."""

    declaration = _normalize(node.declaration or "")
    return any(declaration == kind or declaration.endswith(f" {kind}") for kind in kinds)


def _article(path: Path, node: RuntimeNode) -> tuple[str, str]:
    """Return an article's revision and text, refusing bytes the graph was not built from."""

    if node.source_sha256 is None:
        raise SearchError(f"{node.id}: the article has no recorded revision")
    try:
        content = path.read_bytes()
    except OSError:
        raise SearchError(f"{node.id}: article cannot be read") from None
    if hashlib.sha256(content).hexdigest() != node.source_sha256:
        raise SearchError(
            f"{node.id}: the article changed while the blueprint was being searched; retry after the project is idle"
        )
    return node.source_sha256, content.decode("utf-8")


def _fields(node: RuntimeNode, nodes: dict[str, RuntimeNode], parts: ArticleParts) -> dict[str, str]:
    """Return what each indexed field of ``node`` holds, folded for matching."""

    # The heading goes with the notes so a comment it opens still hides them;
    # ``visible_prose`` leaves the heading's own text out.
    notes = "\n\n".join(
        f"{section.heading}\n\n{section.body}"
        for section in parts.sections
        if section.title.casefold() == "execution notes"
    )
    ancestors: list[str] = []
    parent = node.parent
    while parent is not None:
        ancestors.append(nodes[parent].title)
        parent = nodes[parent].parent
    names = [*(target.declaration for target in node.lean_targets), *node.mathlib_declarations]
    return {
        "title": _normalize(node.title),
        "lean": _normalize("\n".join(name.rpartition(".")[2] for name in names)),
        "node_id": _normalize(node.id.rpartition("/")[2]),
        "statement_text": _normalize(visible_prose(parts.statement)),
        "execution_notes": _normalize(visible_prose(notes)) if notes else "",
        "ancestors": _normalize("\n".join(ancestors)),
        "qualified_names": _normalize("\n".join([node.id, *names])),
    }


def _lean_index(lean_root: str | Path | None) -> SourceIndex | None:
    if lean_root is None:
        return None
    root = Path(lean_root).expanduser().resolve()
    if not root.is_dir():
        raise SearchError("Lean root does not exist or is not a directory")
    try:
        return index_project(root)
    except OSError as error:
        raise SearchError(index_failure_message(error)) from error


def _lean_target(name: str, index: SourceIndex | None) -> SearchLeanTarget:
    declaration = index.find(name) if index is not None else None
    if declaration is None:
        return SearchLeanTarget(name, None, None)
    return SearchLeanTarget(name, declaration.path.as_posix(), declaration.line)


__all__ = [
    "SEARCH_SCHEMA",
    "USED_BY_LIMIT",
    "SearchError",
    "SearchHit",
    "SearchLeanTarget",
    "SearchResult",
    "search_blueprint",
    "statement_preview",
]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_search.py -q 2>&1 | tail -3 && make lint`
Expected: `24 passed`, lint clean.

- [ ] **Step 5: Commit (working commit, squashed in Task 3)**

```bash
git add autoform_cli/search.py tests/test_search.py
git commit -m "wip: search module"
```

---

### Task 2: The command

**Files:**
- Modify: `autoform_cli/__main__.py` (imports near line 29; parser before the `claim` parser near line 207;
  dispatch near line 308; `_search` before `_work_assumptions`; `_positive_count` before `_positive_seconds`)
- Modify: `tests/test_search.py`

**Interfaces:**
- Consumes from Task 1: `SearchError`, `search_blueprint`, `statement_preview`, `SearchResult.to_json()`,
  and the `SearchHit` fields `title`, `node_id`, `article_id`, `declaration`, `state`, `used_by_count`,
  `shared_title`, `lean_targets`, `mathlib_declarations`, `matched_fields`.
- Produces: the `autoform search` command. Exit 0 with or without hits; exit 2 with the message on standard error.

- [ ] **Step 1: Write the failing tests**

In `tests/test_search.py`, replace the import block at the top (everything above `_LEAN_SOURCE`) with:

```python
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from autoform_cli import __main__ as cli, search as search_module
from autoform_cli.runtime import RuntimeProjectionError, load_runtime_graph
from autoform_cli.search import SEARCH_SCHEMA, USED_BY_LIMIT, SearchError, search_blueprint
```

Then append to the end of the file:

```python
def test_search_cli_emits_stable_json(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path)
    command = ["search", str(project), "Separating  AFFINE", "--json", "--state", "can_prove", "--limit", "5"]

    assert cli.main(command) == 0
    first = capsys.readouterr().out
    assert cli.main(command) == 0
    assert capsys.readouterr().out == first

    assert str(tmp_path) not in first
    document = json.loads(first)
    assert first == json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    hit = document.pop("hits")[0]
    assert document == {
        "filters": {"declaration": [], "state": ["can_prove"]},
        "limit": 5,
        "open_statements": False,
        "query": "Separating  AFFINE",
        "schema": SEARCH_SCHEMA,
        "source_revision": load_runtime_graph(project).source_revision,
        "terms": ["separating", "affine"],
        "total_matches": 1,
    }
    assert len(hit.pop("article_revision")) == 64
    assert hit == {
        "article_id": None,
        "article_path": "blueprint/roadmap/convexity/hyperplane.md",
        "declaration": "theorem",
        "lean_targets": [{"declaration": "Project.separation", "line": None, "source_file": None}],
        "matched_fields": ["title", "statement_text"],
        "mathlib": False,
        "mathlib_declarations": [],
        "mathlib_file": None,
        "node_id": "convexity/hyperplane",
        "shared_title": False,
        "source_targets": [],
        "state": "can_prove",
        "statement_text": "Two disjoint convex sets are separated by an affine functional.",
        "title": "Separating hyperplane",
        "used_by": ["convexity/support"],
        "used_by_count": 1,
    }


def test_search_cli_human_output_escapes_project_text(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path)
    (project / "Project.lean").write_text(_LEAN_SOURCE, encoding="utf-8")
    path = project / "blueprint/roadmap/convexity/hyperplane.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("# Separating hyperplane", "# Separating hyperplane\x1b[2J").replace("affine", "affine\x07")
    path.write_text(text, encoding="utf-8")

    assert cli.main(["search", str(project), "separating", "--lean-root", str(project)]) == 0
    output = capsys.readouterr().out
    assert "\x1b" not in output and "\x07" not in output
    lines = output.splitlines()
    assert "Separating hyperplane\\x1b[2J (convexity/hyperplane)" in lines
    assert "  theorem, can_prove, used by 1" in lines
    assert "  Lean: Project.separation (Project.lean:3)" in lines
    assert "  Statement: Two disjoint convex sets are separated by an affine\\x07 functional." in lines
    assert "  Matched: title" in lines
    assert lines[-1] == "1 of 1 matching article(s) shown."

    assert cli.main(["search", str(project), "nowhere"]) == 0
    assert capsys.readouterr().out == "No matching articles.\n"


def test_search_cli_cuts_a_long_statement_and_counts_what_the_limit_hides(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path)
    _article(project, "convexity/long.md", title="Longwinded", body="convex " * 100 + "\n\nSecond paragraph.")

    assert cli.main(["search", str(project), "convex", "--declaration", "lemma", "--limit", "1"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "Supporting functional (convexity/support)"

    assert cli.main(["search", str(project), "convex", "--limit", "1"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "1 of 4 matching article(s) shown."

    assert cli.main(["search", str(project), "longwinded"]) == 0
    statement = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("  Statement: "))
    assert len(statement) == len("  Statement: ") + 200
    assert statement.endswith("...")


def test_search_cli_reports_errors_on_stderr_with_exit_2(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)

    assert cli.main(["search", str(project), "  "]) == 2
    assert capsys.readouterr().err == "error: search query has no terms\n"

    assert cli.main(["search", str(project), "convex", "--lean-root", str(tmp_path / "missing")]) == 2
    assert capsys.readouterr().err == "error: Lean root does not exist or is not a directory\n"

    assert cli.main(["search", str(tmp_path / "missing"), "convex"]) == 2
    assert capsys.readouterr().err == "error: project or blueprint directory does not exist\n"

    for arguments in (["--state", "finished"], ["--limit", "0"], ["--limit", "many"]):
        with pytest.raises(SystemExit) as refused:
            cli.main(["search", str(project), "convex", *arguments])
        assert refused.value.code == 2
    capsys.readouterr()

    _article(project, "convexity/bad\x1b.md", title="Bad", metadata=("article_id: not-an-id",))
    assert cli.main(["search", str(project), "convex"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "\x1b" not in captured.err and "malformed article_id" in captured.err
    (project / "blueprint/roadmap/convexity/bad\x1b.md").unlink()

    def unreadable(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(13, "Permission denied", "/private/secret/blueprint")

    monkeypatch.setattr(cli, "search_blueprint", unreadable)
    assert cli.main(["search", str(project), "convex"]) == 2
    error = capsys.readouterr().err
    assert error.startswith("error: ") and "/private/secret" not in error


def test_search_cli_does_not_report_output_errors_as_unreadable_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)

    class ClosedPipe(io.StringIO):
        def write(self, text: str) -> int:
            raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(sys, "stdout", ClosedPipe())
    with pytest.raises(BrokenPipeError):
        cli.main(["search", str(project), "convex"])
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_search.py -q -k search_cli 2>&1 | tail -8`
Expected: 5 failed. Four fail with `SystemExit: 2` (argparse: `invalid choice: 'search'`); the output-error test
fails with `DID NOT RAISE` or the same `SystemExit`.

- [ ] **Step 3: Wire the parser**

In `autoform_cli/__main__.py`, after the line `from .scaffold import ScaffoldError, scaffold_project` add:

```python
from .search import SearchError, search_blueprint, statement_preview
```

Directly before the line `    claim = subparsers.add_parser("claim", help="coordinate temporary node ownership through Git refs")`
insert, followed by one blank line:

```python
    search = subparsers.add_parser(
        "search", help="find articles by title, Lean name, or statement text before adding one"
    )
    search.add_argument("target", help="project root or blueprint directory")
    search.add_argument("query", help="words that must all occur in an article; put -- before one starting with -")
    search.add_argument("--lean-root", type=Path, help="resolve local Lean declaration targets")
    search.add_argument(
        "--state",
        action="append",
        default=[],
        dest="states",
        choices=[state.key for state in status.STATES],
        metavar="KEY",
        help="keep articles in this derived state (repeatable): "
        + ", ".join(state.key for state in status.STATES),
    )
    search.add_argument(
        "--declaration",
        action="append",
        default=[],
        dest="declarations",
        metavar="KIND",
        help="keep articles whose frontmatter declaration is KIND: theorem, lemma, def, ... (repeatable)",
    )
    search.add_argument(
        "--limit", type=_positive_count, default=20, metavar="N", help="show at most N articles (default 20)"
    )
    search.add_argument("--json", action="store_true", help="write stable machine-readable output")
```

In the dispatch chain, directly before `    if args.command == "claim":` insert:

```python
    if args.command == "search":
        return _search(args)
```

- [ ] **Step 4: Add the printer and the argument type**

Directly before `def _work_assumptions(args: argparse.Namespace) -> int:` insert, followed by two blank lines:

```python
def _search(args: argparse.Namespace) -> int:
    # Only reading the blueprint can fail on the project's paths; printing the
    # result stays outside, so an output error is not reported as one.
    try:
        result = search_blueprint(
            args.target,
            args.query,
            lean_root=args.lean_root,
            states=args.states,
            declarations=args.declarations,
            limit=args.limit,
        )
    except (GraphValidationError, RuntimeProjectionError) as error:
        for issue in error.issues:
            print(f"error: {_human_text(issue)}", file=sys.stderr)
        return 2
    except SearchError as error:
        print(f"error: {_human_text(error)}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError):
        print("error: project, blueprint, or Lean root path cannot be read", file=sys.stderr)
        return 2

    if args.json:
        print(result.to_json())
        return 0
    if not result.hits:
        print("No matching articles.")
        return 0
    for hit in result.hits:
        durable = f" [{hit.article_id}]" if hit.article_id else ""
        print(_human_text(f"{hit.title} ({hit.node_id}){durable}"))
        summary = [
            hit.declaration or "no declaration",
            hit.state,
            f"used by {hit.used_by_count}",
        ]
        if hit.shared_title:
            summary.append("title shared with another article")
        print(_human_text("  " + ", ".join(summary)))
        for target in hit.lean_targets:
            location = f" ({target.source_file}:{target.line})" if target.source_file else ""
            print(_human_text(f"  Lean: {target.declaration}{location}"))
        if hit.mathlib_declarations:
            print(_human_text("  Mathlib: " + ", ".join(hit.mathlib_declarations)))
        preview = statement_preview(hit)
        if preview:
            print(_human_text(f"  Statement: {preview}"))
        print("  Matched: " + ", ".join(hit.matched_fields))
    print(f"{len(result.hits)} of {result.total_matches} matching article(s) shown.")
    return 0
```

Directly before `def _positive_seconds(value: str) -> float:` insert, followed by two blank lines:

```python
def _positive_count(value: str) -> int:
    try:
        count = int(value)
    except ValueError:
        count = 0
    if count < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}")
    return count
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_search.py tests/test_work.py tests/test_cli.py -q 2>&1 | tail -3 && make lint`
Expected: all pass (29 in `tests/test_search.py`), lint clean.

- [ ] **Step 6: Try the command on the bundled example**

Run: `uv run autoform search skills/setup/assets/cabannes-thesis-project "non-ambiguous" --lean-root skills/setup/assets/cabannes-thesis-project --limit 2`
Expected: two hits, the first `Full supervision is non-ambiguous (infimum-loss/theorems/supervision-non-ambiguous)`
with a `Lean: CabannesThesis.supervision_nonAmbiguous (src/CabannesThesis/Basic.lean:23)` line, then
`2 of 4 matching article(s) shown.`

Run: `uv run autoform search skills/setup/assets/cabannes-thesis-project "  "; echo "exit $?"`
Expected: `error: search query has no terms` and `exit 2`.

- [ ] **Step 7: Commit (working commit, squashed in Task 3)**

```bash
git add autoform_cli/__main__.py tests/test_search.py
git commit -m "wip: search command"
```

---

### Task 3: Document, verify, and make it one commit

**Files:**
- Modify: `autoform_cli/README.md`
- Modify: `tests/test_skill_examples.py:791`
- Modify (main checkout, never committed): `docs/superpowers/specs/2026-10-06-blueprint-search-design.md`

**Interfaces:**
- Consumes: the working commits from Tasks 1 and 2.
- Produces: exactly one commit on top of PR 2's commit.

- [ ] **Step 1: Make the docs test require the command**

In `tests/test_skill_examples.py`, change

```python
    assert {("check",), ("audit",), ("render",), ("claim", "acquire")} <= documented
```

to

```python
    assert {("check",), ("audit",), ("render",), ("search",), ("claim", "acquire")} <= documented
```

Run: `uv run pytest tests/test_skill_examples.py -q -k documents_only_commands 2>&1 | tail -3`
Expected: 1 failed, because the reference does not show `autoform search` yet.

- [ ] **Step 2: Document the command**

In `autoform_cli/README.md`, under "## Commands", insert the block below directly before the paragraph
`Plan durable article identity metadata without changing the blueprint:` and leave one blank line after it:

````markdown
Ask whether the blueprint already holds a result before adding an article or
a Lean helper:

```bash
autoform search . "separating hyperplane" --lean-root .
autoform search . "non-ambiguous" --lean-root . --json --limit 20
autoform search blueprint "interlacing" --state proved --declaration theorem
```

`search` takes the project or blueprint directory, then one quoted query; both
are required, and a query that starts with `-` goes after `--`. `--state` takes
derived state keys and `--declaration` frontmatter `declaration` kinds, each
repeatable; `--limit` defaults to 20. It exits 0 with or without hits. See the
[search contract](#search-contract).
````

Insert the section below directly before the heading `## Open statements` and leave one blank line after it:

````markdown
## Search contract

`autoform search` is a read-only projection of Markdown: it writes nothing,
keeps no index, and starts no process. The query splits on whitespace into
terms. An article is a hit when every term is a substring of one of its
fields; terms may sit in different fields. Both sides are folded first: case,
width, accents, typographic dashes and quotes, and invisible characters do not
matter, and a term loses its surrounding `$`. Fields, best first, as
`matched_fields` names them: `title`; `lean` (the last component of each
`lean:` and `mathlib_declaration` name); `node_id` (the last component of the
path ID); `statement_text`; `execution_notes`; `ancestors` (titles of
containing articles); `qualified_names` (the path ID and Lean names in full).
The statement and `## Execution notes` are matched as the site publishes them,
without headings, code blocks, diagrams, comments, and hidden elements; inline
code and mathematics count, and published mathematics is delimited `\(...\)`,
so search for a formula's content. Other frontmatter and sections are not
searched. Every article is searched, containers included.

Hits sort by the best field any term matched, then by the worst among the
terms' best fields, then more dependents first, then node ID. `--state` and
`--declaration` apply before `total_matches` is counted and `--limit` after.
`--declaration def` also keeps `noncomputable def`, but not `definition`.

`--json` writes `autoform-search/v1`: `source_revision`, `open_statements`,
`query`, `terms`, `filters`, `limit`, `total_matches`, and `hits`, with no
timestamp or absolute path. A hit carries `node_id`, `article_id`,
`article_path`, `article_revision`, `title`, `declaration`, `state`,
`statement_text` (the authored Markdown), `lean_targets` (all of them),
`mathlib`, `mathlib_declarations`, `mathlib_file`, `source_targets`, `used_by`,
`used_by_count`, `shared_title`, and `matched_fields`; `article_id`,
`declaration`, and `mathlib_file` may be null. A Lean target has `declaration`,
and `source_file` and `line`, relative to `--lean-root` and null without one or
when the lexical scan does not find the name. `used_by` holds the first ten
dependents by node ID, through statement or proof; `used_by_count` counts all.
`shared_title` marks a title another article repeats and is advisory.

Search rereads each article and refuses, with exit 2, bytes other than those
the graph was built from, as it refuses a symlinked roadmap entry. Each call
reads every article and renders its statement, about 2 ms per article (1.8 s
at 1,000 articles), so one precise query beats several broad ones.
````

- [ ] **Step 3: Run the docs tests**

Run: `uv run pytest tests/test_skill_examples.py tests/test_plugin_runtime.py -q 2>&1 | tail -3`
Expected: all pass.

- [ ] **Step 4: Check every README claim against the command**

Run each and compare with the README text just added:

```bash
EX=skills/setup/assets/cabannes-thesis-project
uv run autoform search "$EX" "non-ambiguous" --lean-root "$EX" --json --limit 20 | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted(d)); print(sorted(d['hits'][0])); print(sorted(d['hits'][0]['lean_targets'][0]))"
uv run autoform search "$EX" "NonAmbiguous" --state proved --declaration theorem; echo "exit $?"
uv run autoform search "$EX" -- "-x"; echo "exit $?"
```

Expected: the three printed key lists are exactly the keys the "Search contract" names (`schema` plus the 8 named top-level keys, 17 hit
keys, 3 Lean target keys); the second command prints `No matching articles.` and `exit 0`; the third prints
`No matching articles.` and `exit 0`.

- [ ] **Step 5: Commit (working commit)**

```bash
git add autoform_cli/README.md tests/test_skill_examples.py
git commit -m "wip: search docs"
git status --short
```

Expected: `git status --short` prints nothing.

- [ ] **Step 6: Prove the tests are live**

The tree is clean, so each mutation is undone with `git restore autoform_cli`. Apply one, run
`uv run pytest tests/test_search.py -q 2>&1 | tail -1`, confirm at least one failure, restore, repeat.

| File | Change | A test that must fail |
| --- | --- | --- |
| `search.py` | delete the `if hashlib.sha256(content).hexdigest() != node.source_sha256:` check and its `raise` | `test_an_article_edited_while_the_blueprint_is_searched_is_refused` |
| `search.py` | sort key without `match[1]` | `test_hits_sort_by_best_field_then_worst_placed_term_then_dependents_then_id` |
| `search.py` | `"lean": _normalize("\n".join(names)),` | `test_a_directory_or_namespace_is_the_weakest_match` |
| `search.py` | `_normalize(notes)` instead of `_normalize(visible_prose(notes))` | `test_execution_notes_are_searched_as_published_and_rank_below_statements` |
| `search.py` | drop `.translate(_PLAIN_PUNCTUATION)` | `test_matching_ignores_accents_typographic_punctuation_and_invisible_characters` |
| `__main__.py` | print the `Statement:` line without `_human_text` | `test_search_cli_human_output_escapes_project_text` |

Run: `git diff --exit-code && echo restored`
Expected: `restored`.

- [ ] **Step 7: Run the full gates**

Run: `make lint && make test 2>&1 | tail -4; make check-example; echo "exit $?"`
Expected: lint clean; only the two baseline failures named in Global Constraints; `make check-example` exit 0.

Run: `git diff HEAD~3 --stat -- autoform_cli/runtime.py autoform_cli/graph.py autoform_cli/lean.py autoform_cli/markdown.py autoform_cli/work.py`
Expected: no output.

- [ ] **Step 8: Measure the cost the README states**

```bash
SCRATCH=/tmp/claude-1000/-workspaces-autoform-bot/871c4e72-d376-4bd7-814d-6dc20396d6a6/scratchpad
uv run python /workspaces/autoform-bot/docs/superpowers/specs/search-bench.py "$SCRATCH/bench-search" 1000
```

Expected: the line names `n=1000` and a time near 1.8 s for each query (the prototype measured 1.81 to 1.86 s). If
the figure is far from the README's "about 2 ms per article (1.8 s at 1,000 articles)", correct the README, do not
leave the claim.

- [ ] **Step 9: Squash into one commit**

```bash
BASE=$(git rev-parse HEAD~3)
test "$(git log -1 --format=%s "$BASE")" = "Audit statements that are empty or only a placeholder" || { echo "BASE is not PR 2"; exit 1; }
test -z "$(git status --short)" || { echo "tree not clean"; exit 1; }
git reset --soft "$BASE"
git commit -F - <<'EOF'
Add autoform search for finding a result before adding it again

Nothing told an agent whether the blueprint already held a result, so a
Roadmap pass could add a second article for it and Formalize could prove
a helper twice. `autoform search TARGET QUERY` answers in one local,
read-only call, and each hit carries what a reuse decision needs: the
statement as authored, the derived state, the Lean targets with file and
line, the sources, and the articles that already depend on it.

An article is a hit when every term occurs in one of its fields, after
folding case, width, accents, typographic punctuation and invisible
characters. Fields rank title, Lean name, file name, statement,
execution notes, containing titles, then full names. Statement and notes
are matched as the site publishes them.

Search keeps no index: each call reads every article and renders its
statement, about 2 ms per article. It rereads each article and refuses
bytes other than those the graph was built from, so a hit belongs to the
reported source revision. `--json` writes `autoform-search/v1`.

Part of #143.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline -4
```

Expected: the new commit, then `Audit statements that are empty or only a placeholder`, then PR 1's commit, then
`7fa6d1d`. Nothing is pushed.

- [ ] **Step 10: Re-run the gates on the squashed commit**

Run: `git status --short && make lint && make test 2>&1 | tail -3`
Expected: clean tree, lint clean, the same two baseline failures only.

- [ ] **Step 11: Bring the spec in line**

In the spec's "PR 3" section, apply the ten decisions listed above: the field table (seven fields, last-component
`lean` and `node_id`, `visible_prose`), the ordering sentence, the folding rule, the `SearchHit` and `SearchResult`
fields, the `filters` key names, the loading steps, and the human-output sample. In "PR 4", record the open
decision about `signature` and the schema version. Do not `git add` the spec.

## Notes for the PR description (written at submission, not now)

- The ten "Decisions that differ from the spec", with the 102-to-2 ranking measurement for decision 1.
- The cost table from `docs/superpowers/specs/2026-10-06-search-cost.md`, so the maintainer can ask for several
  queries per call before the schema is fixed.
- The "Known limits" list, including the upstream double read behind `source_revision`.
- Stacked on PRs 1 and 2. The runtime schema is untouched.

## Outcome (2026-10-07)

Built as one local commit `2e0587a`. Nothing pushed for PR 3, no PR.

- **Base moved.** Upstream `main` advanced 58 commits to `cc7e3a8`. The local stack was rebased onto it before
  building: PR 1 is `a711d93`, PR 2 is `a95f5d5` locally. PR #171 still carries the pre-rebase `a07ed02` and
  `b8cc564` and still merges cleanly. Old tips are kept at `backup/pr3-base-before-rebase`.
- **Gates:** lint clean; `make test` 1,969 passed with the 2 baseline failures; `make check-example` exit 0;
  1,000 articles searched in 1.83 s.
- **Changed by the final review:**
  - `execution_notes` field cut. Upstream PR #172 (the maintainer's, open, mergeable) moves notes out of articles
    to `blueprint/.implementation-notes/<article_id>.md` and asserts the README no longer says "Execution notes".
    Six fields remain: `title`, `lean`, `node_id`, `statement_text`, `ancestors`, `qualified_names`.
  - `matched_fields` names each term's best field, not every field containing a term.
  - A mark is stripped as an accent only on a letter, and text is recomposed, so `≠` does not find `=`.
  - A blank `--declaration` is refused. The roadmap root's title is left out of `ancestors`.
  - `_positive_count` removed (`--limit` is `int`; the module refuses values below 1). `USED_BY_LIMIT` is private.
  - README: the cost figures moved out of the contract into the PR description; flag semantics stated once.
- **Deferred minors:** the `Lean:` line's escaping is untested; `query` and `limit` echoes are redundant; a BOM
  article is read as having no frontmatter (graph behaviour).
- **For the PR description:** upstream #183 inserts at the same spot in `__main__.py` (trivial rebase for whoever
  lands second); the read-once test does not check "reverse edges built once"; no skill mentions the command until
  PR 5.

## Third review round (2026-10-07)

Commit is now the tip of `feat/issue-143-statement-span` (see `git log`). Two fresh reviewers; no critical bug.
Fixed: a blueprint with no `roadmap/README.md` lost the chapter title from `ancestors` (the root is now found by
path); the README example used `--state proved` alone, which hides fully proved theorems; three contract sentences
had no failing test (statement above ancestors, authored `statement_text` and published preview, `def` not
`definition`); the symlink refusal is asserted through the CLI; the no-process guard also covers `os.system` and
sockets and snapshots the whole temp tree; `--help` and the README now say matching is substring, every word is
required, state keys are exact, `matched_fields` does not say which term, and human output is not a contract.
Gates: lint clean, `make test` 1,972 passed + 2 baseline, check-example exit 0.

Deferred: `_normalize` is not idempotent around U+0345 (no miss found in 300,000 trials); marks stripped on
letters conflate some words in Japanese, Devanagari and Thai (false positives only, stated in the README);
"reverse edges built once" is not asserted by a counter; `--limit` accepts what `int()` accepts.

For PR 5: zero hits is not proof of absence under all-words substring matching ("recovery of the ..." misses on
"of"; "unambiguous" misses "non-ambiguous"). The skill rule must say to retry with fewer, distinctive words.
A reviewer's PR description draft is in this session's transcript.

## Softer matching (2026-10-07, user decision)

The user chose "stop words + word endings". Query-side only, so recall only grows:
- Filler words (`a an and are as at be by for from in is it of on or that the to with`) are dropped unless the
  query has no other word.
- A plain alphabetic word loses a final `ing`, `ed`, `es` or `s` when four letters remain; not after `ss`, `us`,
  `is`. Names with a dot, underscore or digit are searched exactly.
- `terms` in the output shows the terms as searched (`separating` appears as `separat`).
On the bundled example, "recovery of the fully supervised solution" and "deterministic distribution recovered"
now find `supervision-recovery`. `unambiguous` still does not find `non-ambiguous`; the README says to retry with
fewer words. Gates: lint clean, 1,973 passed + 2 baseline, check-example exit 0, 1.88 s at 1,000 articles.

## Fourth review round: the softer matching (2026-10-07)

One fresh reviewer; no critical bug. The hit set was confirmed to only grow (60,000 random queries, 0 violations).
Fixed:
- **Shown hits could shrink.** `rings` became `ring`, 25 articles matched, and the one article that held "rings"
  fell outside `--limit 20`. Articles holding the words as typed now sort before stem-only matches.
- **`-ies`/`-ied` and doubled letters.** `topologies` was cut to `topologi`, which `topology` does not contain;
  7% of stemmed tokens in Mathlib docstrings missed their base form this way. Now `topolog`, `satisf`, `embed`,
  `control`.
- **Sentence punctuation** around a word of letters is shed (`recovered,` and `(solutions).`).
- **Filler list widened** with `can do does has have if its let such then there these this we when where which
  whose`; `not every all any some no exists` stay as terms.
- **README and help** restated to match the rule exactly.
Gates: lint clean, 1,976 passed + 2 baseline, check-example exit 0, 1.82 s at 1,000 articles.
Deferred: `mapping` stays `mapp` (four-letter minimum); `indices`/`matrices` do not reach `index`/`matrix`.
