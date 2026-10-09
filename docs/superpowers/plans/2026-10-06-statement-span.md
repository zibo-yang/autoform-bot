# One Definition of the Statement (PR 1 of #143) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `autoform audit` and the published theorem box one shared definition of where an article's statement
ends, in `autoform_cli/markdown.py`, so that `autoform search` (PR 3) can use the same one.

**Architecture:** A new `article_parts(text)` in `markdown.py` splits an article body at its published H2 headings,
using the masking `markdown.py` already has for fences, indented code and HTML comments. `audit._read_article` and
`render._split_body` drop their private fence-and-heading loops and call it. A small `visible_text(markdown)` helper
is added for the later PRs.

**Tech Stack:** Python 3.10+, `uv`, pytest, ruff. No new dependency.

**Spec:** `docs/superpowers/specs/2026-10-06-blueprint-search-design.md`, section "PR 1: one definition of the
statement".

## Global Constraints

- Python 3.10+, run through `uv`. No new dependency.
- Markdown under `blueprint/` stays the only authored state. Nothing in this work writes a file, an index or a cache.
- Public CLI and JSON shapes are contracts. This PR changes none.
- `autoform_cli/README.md` is the single source of command-line truth.
- The PR passes `make lint`, `make test` and `make check-example`.
- Line length 120. No formatter runs in CI, so match the surrounding code and do not reformat unrelated lines.
- Tests and docs change in the same PR as the behaviour they describe.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Pushing the branch and opening the PR need the user's go-ahead. Do neither as part of this plan.
- `docs/superpowers/` is local working material. Never `git add` anything under it.

## Before you start

- Work on branch `feat/issue-143-statement-span`, created from `main` at `7fa6d1d`, in its own worktree.
- Run tests with `uv run pytest`. The full suite takes about a minute.
- **Known baseline failures on this machine, unrelated to this work:** the two parameters of
  `tests/test_project_create.py::test_file_swapped_in_before_open_is_not_called_a_link` fail on untouched `main`.
  Expect exactly those two failures in a full run and no others.
- The code in this plan was run as a prototype: with it, the full suite passes apart from those two tests, ruff is
  clean, and the bundled example's rendered site is byte-identical to the one `main` produces.

## File structure

| File | Change | Responsibility |
| --- | --- | --- |
| `autoform_cli/markdown.py` | add | `ArticleSection`, `ArticleParts`, `article_parts`, `visible_text` |
| `autoform_cli/audit.py` | modify | `_read_article` calls `article_parts` |
| `autoform_cli/render.py` | modify | `_split_body` calls `article_parts`; `_body_without_dependencies` is deleted |
| `autoform_cli/README.md` | modify | one paragraph defining the statement |
| `tests/test_markdown.py` | add tests | the rule itself |
| `tests/test_audit.py` | add tests | the rule through `autoform audit` |
| `tests/test_render.py` | add tests | the rule through `autoform render` |

`graph.py` keeps its own loop in `_parse_node`. It decides edges, not statements, and is out of scope.

## Behaviour this PR changes

Each row has a test in the task named.

| Case | Before | After | Task |
| --- | --- | --- | --- |
| H3 before the first H2, on the site | statement box cut at the H3 | box runs to the first H2, with the H3 demoted to H6 | 3 |
| A heading inside an HTML comment, on the site | cut the statement there | ends nothing | 3 |
| Prose above the H1, in the audit | not counted as statement text | counted | 2 |
| A statement that is only an indented code block, in the audit | counted as statement text | `missing-statement-text` | 2 |

## Review Focus

Inputs the spec does not spell out that are most likely to bite. Each is pinned by a test in the task named.

1. **A statement whose first line is indented four spaces.** It is a code block on the site, so trimming must remove
   blank lines only, never leading spaces. Task 1, `test_a_statement_keeps_the_indentation_that_makes_it_code`.
2. **An H3 inside a statement.** Many statements share one chapter page, so it must be demoted like every other node
   heading or it joins the chapter's table of contents. Task 3,
   `test_a_statement_keeps_its_subheadings_inside_the_theorem`.
3. **CRLF line endings, and a section heading with a trailing comment or closing hashes.** The section title must
   still read `Depends on`, or the audit reports a section that exists as missing. Task 1,
   `test_a_section_title_is_read_as_published`.
4. **A fence that is never closed.** The site publishes the rest of the page as code, so no section starts after
   it. Task 1, `test_an_unclosed_fence_hides_every_heading_after_it`.
5. **A setext heading (`Proof` over `-----`).** The graph loader reads only ATX headings, so this must not start a
   section here either. Task 1, `test_only_atx_headings_end_a_statement`.

---

### Task 1: `article_parts` and `visible_text` in `markdown.py`

**Files:**
- Modify: `autoform_cli/markdown.py` (add after `frontmatter_end`, before `site_converter`; extend `__all__`)
- Test: `tests/test_markdown.py`

**Interfaces:**
- Consumes: existing `frontmatter_end(lines: list[str]) -> int`, `HEADING`, `content_lines(text: str) -> list[str]`,
  `rendered_visible_text(value: str) -> str`, and the private `_mask_fences_and_comments(lines, hidden)` and
  `_mask_indented_code(lines, hidden)`, all already in `markdown.py`.
- Produces:
  - `ArticleSection(title: str, heading: str, body: str)`: `title` is the H2 text as published, `heading` the raw
    heading line, `body` the raw Markdown up to the next H2 without surrounding blank lines.
  - `ArticleParts(statement: str, remainder: str, sections: tuple[ArticleSection, ...])`.
  - `article_parts(text: str) -> ArticleParts`.
  - `visible_text(value: str) -> str`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_markdown.py`, extend the existing import block so it reads:

```python
from autoform_cli.markdown import (
    SITE_EXTENSION_CONFIGS,
    SITE_EXTENSIONS,
    ArticleSection,
    article_parts,
    content,
    content_lines,
    link_targets,
    local_target_issue,
    markdown_anchors,
    markdown_links,
    PublishedTable,
    published_tables,
    rendered_visible_text,
    visible_text,
)
```

Append to the end of the file:

```python
def test_a_statement_runs_from_the_title_to_the_first_h2() -> None:
    parts = article_parts(
        "---\ndeclaration: theorem\n---\n\n# Title\n\nThe statement.\n\n"
        "## Depends on\n\n- [Base](base.md)\n\n## Sources\n\n- [Paper](paper.md)\n"
    )

    assert parts.statement == "The statement."
    assert parts.remainder == "## Depends on\n\n- [Base](base.md)\n\n## Sources\n\n- [Paper](paper.md)"
    assert parts.sections == (
        ArticleSection("Depends on", "## Depends on", "- [Base](base.md)"),
        ArticleSection("Sources", "## Sources", "- [Paper](paper.md)"),
    )


def test_a_deeper_heading_does_not_end_the_statement() -> None:
    parts = article_parts("# Title\n\nFirst part.\n\n### Remark\n\nSecond part.\n\n## Sources\n")

    assert parts.statement == "First part.\n\n### Remark\n\nSecond part."
    assert [section.title for section in parts.sections] == ["Sources"]


def test_prose_before_the_title_belongs_to_the_statement() -> None:
    assert article_parts("Lead-in.\n\n# Title\n\nBody.\n").statement == "Lead-in.\n\n\nBody."


@pytest.mark.parametrize(
    "hidden",
    [
        "```\n## Not a section\n```",
        "~~~~\n## Not a section\n~~~~",
        "<!--\n## Not a section\n-->",
        "    ## Not a section",
    ],
)
def test_a_heading_that_is_not_published_ends_nothing(hidden: str) -> None:
    parts = article_parts(f"# Title\n\nBefore.\n\n{hidden}\n\nAfter.\n\n## Sources\n")

    assert parts.statement == f"Before.\n\n{hidden}\n\nAfter."
    assert [section.title for section in parts.sections] == ["Sources"]


def test_an_article_without_sections_is_all_statement() -> None:
    parts = article_parts("# Title\n\nOnly a statement.\n")

    assert (parts.statement, parts.remainder, parts.sections) == ("Only a statement.", "", ())


@pytest.mark.parametrize(
    "text",
    ["", "# Title\n", "---\ndeclaration: theorem\n---\n", "---\nnever closed\n# Title\n\nBody.\n"],
)
def test_an_article_with_no_body_has_an_empty_statement(text: str) -> None:
    parts = article_parts(text)

    assert (parts.statement, parts.remainder, parts.sections) == ("", "", ())


def test_a_section_title_is_read_as_published() -> None:
    parts = article_parts("# Title\r\n\r\nBody.\r\n\r\n## Depends on <!-- edges --> ##\r\n\r\nNone.\r\n")

    assert parts.statement == "Body."
    assert parts.sections == (ArticleSection("Depends on", "## Depends on <!-- edges --> ##", "None."),)


def test_only_atx_headings_end_a_statement() -> None:
    # The graph loader reads only ATX headings, so a setext underline is prose
    # here too; one rule for where a section starts, whatever reads the article.
    parts = article_parts("# Title\n\nBody.\n\nProof\n-----\n\nSteps.\n")

    assert parts.statement == "Body.\n\nProof\n-----\n\nSteps."
    assert parts.sections == ()


def test_a_horizontal_rule_after_the_frontmatter_is_statement_text() -> None:
    assert article_parts("---\nlean: A.b\n---\n\n# Title\n\nAbove.\n\n---\n\nBelow.\n").statement == (
        "Above.\n\n---\n\nBelow."
    )


def test_a_statement_keeps_the_indentation_that_makes_it_code() -> None:
    parts = article_parts("# Title\n\n    theorem draft : True := trivial\n\n## Sources\n\n    cited\n")

    assert parts.statement == "    theorem draft : True := trivial"
    assert parts.sections == (ArticleSection("Sources", "## Sources", "    cited"),)
    assert visible_text(parts.statement) == ""


def test_an_unclosed_fence_hides_every_heading_after_it() -> None:
    # The site publishes the rest of the page as code, so no section starts there.
    parts = article_parts("# Title\n\nBefore.\n\n```\ncode\n\n## Depends on\n\n- [Base](base.md)\n")

    assert parts.statement == "Before.\n\n```\ncode\n\n## Depends on\n\n- [Base](base.md)"
    assert parts.sections == ()


def test_visible_text_drops_code_and_comments_before_rendering() -> None:
    assert visible_text("A **bold**\nclaim.\n\n```lean\ntheorem hidden\n```\n\n<!-- aside -->\n") == "A bold claim."
    assert visible_text("```\nonly code\n```\n") == ""
    assert visible_text("Uses `Nat.succ` inline.") == "Uses Nat.succ inline."
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_markdown.py -q`
Expected: collection error, `ImportError: cannot import name 'ArticleSection' from 'autoform_cli.markdown'`.

- [ ] **Step 3: Implement**

In `autoform_cli/markdown.py`, insert this block between the end of `frontmatter_end` and `def site_converter`:

```python
@dataclass(frozen=True, slots=True)
class ArticleSection:
    """One H2 section of an article, in the author's own Markdown."""

    title: str
    heading: str
    body: str


@dataclass(frozen=True, slots=True)
class ArticleParts:
    """An article body split at its published H2 headings.

    ``statement`` is everything between the frontmatter and the first H2, with
    the H1 title line removed. ``remainder`` is the rest. Both are the author's
    Markdown, untouched apart from surrounding blank lines, so a caller that
    publishes them publishes what was written and indentation keeps its meaning.
    """

    statement: str
    remainder: str
    sections: tuple[ArticleSection, ...]


def article_parts(text: str) -> ArticleParts:
    """Split an article into its statement and its H2 sections.

    This is the one definition of where a statement ends. A heading counts only
    where it is published, so ``## Proof`` inside a fenced block, an indented
    code block, or an HTML comment ends nothing, and a heading below level two
    belongs to whatever it sits in.
    """

    lines = text.splitlines()
    body = lines[frontmatter_end(lines) :]
    hidden: set[int] = set()
    masked = _mask_indented_code(_mask_fences_and_comments(body, hidden), hidden)

    title = next((index for index, line in enumerate(masked) if _heading_level(line) == 1), None)
    if title is not None:
        del body[title], masked[title]

    starts = [index for index, line in enumerate(masked) if _heading_level(line) == 2]
    end = starts[0] if starts else len(body)
    sections = tuple(
        ArticleSection(
            title=HEADING.match(masked[start]).group(2).strip(),
            heading=body[start],
            body=_trim(body[start + 1 : stop]),
        )
        for start, stop in zip(starts, [*starts[1:], len(body)])
    )
    return ArticleParts(
        statement=_trim(body[:end]),
        remainder=_trim(body[end:]),
        sections=sections,
    )


def visible_text(value: str) -> str:
    """Return the text a reader sees once the Markdown ``value`` is published.

    Code blocks and HTML comments are masked before rendering, so an example or
    an aside never reads as prose.
    """

    return rendered_visible_text("\n".join(content_lines(value)))


def _trim(lines: list[str]) -> str:
    """Join ``lines`` without the blank ones at either end."""

    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def _heading_level(line: str) -> int:
    heading = HEADING.match(line)
    return len(heading.group(1)) if heading else 0
```

Then extend `__all__` at the bottom of the file. It keeps its existing order; add four names:

```python
__all__ = [
    "ArticleParts",
    "ArticleSection",
    "EXTERNAL_SCHEMES",
```

```python
    "PublishedTable",
    "article_parts",
    "markdown_links",
```

```python
    "strip_line_comments",
    "visible_text",
]
```

Why `_trim` and not `str.strip()`: `strip()` would remove the four leading spaces that make a first line a code
block, and the audit would then read that code as prose.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_markdown.py -q`
Expected: all pass, no failures.

Run: `uv run ruff check autoform_cli tests`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add autoform_cli/markdown.py tests/test_markdown.py
git commit -m "$(cat <<'EOF'
Define an article's statement once in the Markdown primitives

The audit and the renderer each decide where a statement ends, and they
disagree. article_parts splits an article at its published H2 headings so
both can read one rule.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: The audit reads the shared statement

**Files:**
- Modify: `autoform_cli/audit.py` (imports near line 29; `_read_article` near line 257)
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: from Task 1, `article_parts(text: str) -> ArticleParts` with `.statement: str` and
  `.sections: tuple[ArticleSection, ...]`, each section having `.title: str`; and the existing
  `content_lines(text: str) -> list[str]`.
- Produces: nothing new. `_read_article(path: Path) -> _ArticleShape` keeps its signature and `_ArticleShape` keeps
  its two boolean fields.

- [ ] **Step 1: Write the failing tests**

Append to the end of `tests/test_audit.py`. `_coverage`, `_article` and `_finding_map` are helpers already defined
at the top of that file:

```python
@pytest.mark.parametrize(
    "prose",
    [
        "",
        "<!-- the statement goes here -->",
        "```lean\ntheorem draft : True := trivial\n```",
        "    theorem draft : True := trivial",
    ],
)
def test_audit_requires_statement_text_a_reader_can_see(tmp_path: Path, prose: str) -> None:
    blueprint = tmp_path / "blueprint"
    _coverage(blueprint)
    _article(blueprint, "chapter/result.md", prose=prose, declaration="theorem")

    codes = {code for code, _reason in _finding_map(blueprint)["roadmap/chapter/result.md"]}

    assert codes == {"missing-statement-text"}


@pytest.mark.parametrize(
    "prose",
    [
        "### Setting\n\nLet $X$ be a set.",
        "Let $X$ be a set.\n\n```lean\ntheorem draft : True := trivial\n```",
    ],
)
def test_audit_accepts_a_statement_with_subheadings_or_code(tmp_path: Path, prose: str) -> None:
    blueprint = tmp_path / "blueprint"
    _coverage(blueprint)
    _article(blueprint, "chapter/result.md", prose=prose, declaration="theorem")

    assert audit_blueprint(blueprint).clean


def test_audit_counts_statement_prose_written_above_the_title(tmp_path: Path) -> None:
    blueprint = tmp_path / "blueprint"
    _coverage(blueprint)
    path = _article(blueprint, "chapter/result.md", prose="", declaration="theorem")
    path.write_text(
        "---\ndeclaration: theorem\n---\n\nLet $X$ be a set.\n\n# Result\n\n## Depends on\n\nNone.\n",
        encoding="utf-8",
    )

    assert audit_blueprint(blueprint).clean


def test_audit_ignores_a_depends_heading_that_is_not_published(tmp_path: Path) -> None:
    blueprint = tmp_path / "blueprint"
    _coverage(blueprint)
    _article(
        blueprint,
        "chapter/result.md",
        prose="A statement.\n\n```\n## Depends on\n```",
        depends=False,
        declaration="theorem",
    )

    codes = {code for code, _reason in _finding_map(blueprint)["roadmap/chapter/result.md"]}

    assert codes == {"missing-depends-section"}
```

- [ ] **Step 2: Run the tests to verify the two behaviour changes fail**

Run: `uv run pytest tests/test_audit.py -q`
Expected: exactly two failures, and every other test passes:

- `test_audit_requires_statement_text_a_reader_can_see[    theorem draft : True := trivial]`, because the old loop
  counts indented code as statement text;
- `test_audit_counts_statement_prose_written_above_the_title`, because the old loop ignores prose above the H1.

The other new tests pass already. They pin behaviour the rewrite must keep.

- [ ] **Step 3: Implement**

In `autoform_cli/audit.py`, replace these four import lines:

```python
from .markdown import FENCE as _FENCE
from .markdown import frontmatter_end as _frontmatter_end
from .markdown import HEADING as _HEADING
from .markdown import HTML_COMMENT as _HTML_COMMENT
```

with:

```python
from .markdown import article_parts as _article_parts
from .markdown import content_lines as _content_lines
```

Replace the whole body of `_read_article` so the function reads:

```python
def _read_article(path: Path) -> _ArticleShape:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return _ArticleShape(False, False)

    parts = _article_parts(text)
    return _ArticleShape(
        statement_text=any(line.strip() for line in _content_lines(parts.statement)),
        has_depends_section=any(section.title.casefold() == "depends on" for section in parts.sections),
    )
```

Leave `_ArticleShape` and every caller unchanged.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_audit.py tests/test_graph_scale.py -q`
Expected: all pass. `tests/test_graph_scale.py` holds `test_audit_does_not_scan_for_children_per_node`, which
exercises the audit loop this task edits.

Run: `uv run ruff check autoform_cli tests`
Expected: `All checks passed!` If ruff reports an unused import in `audit.py`, one of the four old import lines was
left behind.

- [ ] **Step 5: Commit**

```bash
git add autoform_cli/audit.py tests/test_audit.py
git commit -m "$(cat <<'EOF'
Read the audit's statement through the shared definition

Prose above the title now counts as statement text, and a statement that
is only an indented code block no longer does.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: The renderer reads the shared statement

**Files:**
- Modify: `autoform_cli/render.py` (import near line 26; `_split_body` near line 1883; delete
  `_body_without_dependencies` near line 1921)
- Modify: `autoform_cli/README.md` (section "Articles and containment")
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: from Task 1, `article_parts(text: str) -> ArticleParts` with `.statement: str` and `.sections`, each
  section having `.title: str`, `.heading: str` and `.body: str`. Existing in `render.py`:
  `_DEPENDENCY_SECTIONS = frozenset({"depends on", "proof depends on"})` and `_demote_headings(text: str) -> str`,
  which raises every heading outside a fence by four levels, capped at H6.
- Produces: nothing new. `_split_body(text: str) -> tuple[str, str]` keeps its signature and its one caller.

- [ ] **Step 1: Write the failing tests**

Append to the end of `tests/test_render.py`. `_project` is the fixture helper at the top of that file; it writes a
two-node blueprint whose `top.md` these tests overwrite:

```python
def _statement_box(page: str, node_id: str) -> str:
    start = page.index('<div class="bp-thmcontent"', page.index(f'id="{node_id}"'))
    return page[start : page.index("</div>", start)]


def test_a_statement_keeps_its_subheadings_inside_the_theorem(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "blueprint/roadmap/top.md").write_text(
        "---\ndeclaration: theorem\nlean: Project.top\n---\n\n"
        "# Top\n\nThe main result.\n\n### Setting\n\nThe hypotheses.\n\n"
        "## Sources\n\nA citation.\n\n## Depends on\n\n- [Base](base.md)\n",
        encoding="utf-8",
    )
    render_site(project / "blueprint", tmp_path / "out", lean_root=project)
    page = (tmp_path / "out/roadmap/README.md").read_text(encoding="utf-8")
    box = _statement_box(page, "top")

    assert "The main result." in box and "The hypotheses." in box
    # Demoted like every other heading a node brings onto the chapter page.
    assert "###### Setting" in box
    assert "\n### Setting" not in page
    assert "A citation." not in box
    assert page.index("###### Setting") < page.index("###### Sources")
    assert "## Depends on" not in page


def test_a_hidden_heading_does_not_cut_a_statement_short(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "blueprint/roadmap/top.md").write_text(
        "---\ndeclaration: theorem\nlean: Project.top\n---\n\n"
        "# Top\n\nThe main result.\n\n<!--\n## Draft\n-->\n\nIts second sentence.\n\n"
        "## Depends on\n\n- [Base](base.md)\n",
        encoding="utf-8",
    )
    render_site(project / "blueprint", tmp_path / "out", lean_root=project)
    box = _statement_box((tmp_path / "out/roadmap/README.md").read_text(encoding="utf-8"), "top")

    assert "The main result." in box and "Its second sentence." in box
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_render.py -q -k "subheadings_inside_the_theorem or hidden_heading_does_not_cut"`
Expected: both fail on their first assertion. The old `_split_body` ends the statement at the `### Setting` line in
the first test and at the commented `## Draft` line in the second.

- [ ] **Step 3: Implement**

In `autoform_cli/render.py`, add one import after the `.lean` import line:

```python
from .lean import SourceLinker, build_linker, declaration_names, index_failure_message
from .markdown import article_parts
from .status import is_definition
```

Replace the whole of `_split_body` with:

```python
def _split_body(text: str) -> tuple[str, str]:
    """Return the node's statement and whatever trailing sections follow it.

    Only the statement belongs inside the theorem environment; ``## Sources``
    and friends are page material that sits after it, the way a blueprint sets
    a statement apart from the prose around it. The dependency sections are
    dropped: the DAG is re-presented in the metadata line, so repeating the raw
    link lists on the page would only duplicate it.
    """
    parts = article_parts(text)
    remainder = "\n\n".join(
        f"{section.heading}\n\n{section.body}".rstrip()
        for section in parts.sections
        if section.title.casefold() not in _DEPENDENCY_SECTIONS
    )
    # Many statements now share one chapter page, so a node's own
    # subheadings must not compete with the chapter's structure.
    return _demote_headings(parts.statement), _demote_headings(remainder)
```

Delete the function `_body_without_dependencies` entirely. It has no other caller. Leave `_demote_headings`,
`_outside_fences`, and the module-level `_HEADING` and `_FENCE` in place: other functions in `render.py` use them.

The statement goes through `_demote_headings` because it can now contain an H3. A statement with no heading is
returned unchanged.

- [ ] **Step 4: Document the rule**

In `autoform_cli/README.md`, section "Articles and containment", find the paragraph that begins:

```markdown
`## Depends on` lists what the article needs in order to be *stated*;
```

Insert this paragraph, followed by a blank line, immediately before it:

```markdown
An article's statement is its body from the end of the frontmatter to the first
`##` heading, without the H1 line. A deeper heading does not end it, and neither
does a `##` line inside a code block or an HTML comment. `autoform audit` and
the published theorem box both read that span.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_render.py tests/test_skill_examples.py -q`
Expected: all pass. `tests/test_skill_examples.py` reads `autoform_cli/README.md`, so it confirms the documentation
edit broke no assertion on that file.

Run: `grep -n "_body_without_dependencies" -r autoform_cli tests`
Expected: no output.

Run: `uv run ruff check autoform_cli tests`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add autoform_cli/render.py autoform_cli/README.md tests/test_render.py
git commit -m "$(cat <<'EOF'
Publish the statement the audit checks

The theorem box now runs to the first H2, as the audit already assumed,
instead of stopping at any heading. Subheadings inside it are demoted with
the rest of the node's headings, and a heading inside an HTML comment no
longer cuts the statement short.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Verify the branch

**Files:** none changed.

**Interfaces:**
- Consumes: the three commits from Tasks 1 to 3.
- Produces: evidence for the PR description. No code.

- [ ] **Step 1: Lint**

Run: `make lint`
Expected: `All checks passed!`

- [ ] **Step 2: Full test suite**

Run: `make test`
Expected: the only failures are the two parameters of
`tests/test_project_create.py::test_file_swapped_in_before_open_is_not_called_a_link`, which fail on untouched
`main` on this machine. Any other failure is a regression from this branch: stop and fix it.

To confirm the baseline, run the same test on `main`:
`git stash -u && git checkout -q main && uv run pytest -q tests/test_project_create.py -k swapped_in_before_open; git checkout -q - && git stash pop`
Skip the stash commands if the working tree is clean.

- [ ] **Step 3: Bundled example**

Run: `make check-example`
Expected: it validates, renders and builds the bundled example with exit status 0.

- [ ] **Step 4: Show the example site is unchanged**

The bundled example has no article in any row of the behaviour table, so its rendered site must not change. From
the branch worktree, with `<SCRATCH>` an empty temporary directory and `<MAIN>` a checkout of `main`:

```bash
cd skills/setup/assets/cabannes-thesis-project
uv run --project ../../../.. autoform render blueprint -o <SCRATCH>/new --lean-root .
(cd <MAIN>/skills/setup/assets/cabannes-thesis-project && \
  uv run --project ../../../.. autoform render blueprint -o <SCRATCH>/old --lean-root .)
diff -r <SCRATCH>/old <SCRATCH>/new && echo IDENTICAL
```

Expected: `IDENTICAL`.

- [ ] **Step 5: Report**

Report to the user: the three commit hashes, the lint, test and example results with their actual output, and the
`IDENTICAL` check. Do not push and do not open a pull request; the user decides that.

The PR description, when the user asks for it, must state the four rows of "Behaviour this PR changes" and say that
the first-H2 boundary is open question 1 of #143, offered for the maintainer's decision.

---

## Deviations from the spec

The spec was updated to match these while the plan was written:

- `ArticleParts.sections` holds `ArticleSection(title, heading, body)` objects, not `(title, body)` pairs. The
  renderer needs the author's raw heading line to republish a section.
- The renderer demotes headings inside the statement. The spec did not say what happens to an H3 that is now part
  of a statement.
- A statement that is only an indented code block is now `missing-statement-text`. The spec's table listed fences
  and comments but not indented code.

## State after two review rounds (2026-10-06)

The branch is one commit, per the one-commit-per-PR rule. Earlier histories are kept on the local branches
`backup/statement-span-three-commits` and `backup/statement-span-before-squash`.

Changes from the tasks above, made after review:

- `ArticleParts.remainder` and `visible_text` were removed. They return in the PRs that call them.
- The `literal_unclosed_comment` keyword was tried and withdrawn: it was quadratic, covered only part of the
  problem, and gave the audit and the site two readings. There is one strict rule.
- A statement that is only a subheading is `missing-statement-text`, as on `main`.
- The `missing-statement-text` reason reads "before its first H2 section".
- `__all__` order, field documentation, and several tests were tightened.

### Behaviour changes the PR description must list

| Case | Before | After |
| --- | --- | --- |
| Site: an H3 before the first H2 | statement box cut at the H3 | box runs to the first H2, the H3 demoted to H6 |
| Site: a heading inside a closed HTML comment | cut the statement there | ends nothing |
| Site: a fence opener inside an HTML comment | rest of the article treated as fenced | split correctly |
| Site: `## Depends on <!-- note -->` | section republished in the notes | dropped, as a dependency section |
| Site: a statement whose first line is indented | indent stripped, shown as prose | shown as written (a code block at four spaces) |
| Site: blank lines around section headings; trailing spaces at a section's end | as authored | one blank line; trailing spaces dropped |
| Audit: prose above the H1 | not counted as statement text | counted |
| Audit: a statement that is only an indented code block | counted | `missing-statement-text` |
| Audit: `missing-statement-text` reason string (appears in `--json`) | "...between its H1 and first H2 section" | "...before its first H2 section" |

### Known limits to disclose

- **An HTML comment or fence that never closes hides every heading after it.** That includes a mid-paragraph
  `<!--` paired with a later, unrelated `-->`. The site then shows the remaining sections inside the theorem box,
  where `main` split them. The audit reports `missing-depends-section` on the same article, so the author is told.
- **`graph.py` keeps its own reader.** On malformed fences the audit and the graph loader can disagree about
  whether `## Depends on` exists: a fence "closed" by a line carrying an info string, and a closed fence that
  contains `<!--`. In both the audit matches the published page. Aligning the loader is a separate change.
- **A section heading that opens a comment** (`## Sources <!--`) loses that opener from its section body.
- `<!-- a --> ## Sources` counts as a section although the site publishes it as a paragraph.

### Coordination with open upstream PRs

- **#124** edits the `_read_article` loop this branch deletes and gives the graph loader its own statement rule.
  Whichever lands second should read `article_parts(...).sections`.
- **#141** hashes the statement returned by `render._split_body`, which this branch changes (boundary, demoted
  headings, kept indentation). It should hash `article_parts(...).statement`.
- **#90** and **#165** conflict only in import lines.

### Third review round (`/code-review`)

Two regressions were found and fixed, each with a test that failed first:

- A comment opened on the H1 line and closed further down lost its opener when the title line was dropped, so the
  hidden text read as prose. The statement now keeps the open comment.
- An H1 written below an H2 no longer ended that section, so the statement under it vanished into the dropped
  dependency section. The title now ends the section, and the text under it is statement.
