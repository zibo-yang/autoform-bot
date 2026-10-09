# Statement Text Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `autoform audit` reports a formalizable article whose statement shows a reader nothing
(`empty-statement-text`) or only announces that it is not written yet (`placeholder-statement-text`).

**Architecture:** The placeholder rule that `coverage.py` applies to evidence cells moves to `markdown.py` as
public helpers and coverage imports it. `markdown.py` also gains `visible_prose`, which renders Markdown as the
site does and returns the text a reader sees outside headings, code blocks and diagrams. `audit.py` applies both to
the statement that PR 1's `article_parts` returns. At most one statement finding fires per article.

**Tech Stack:** Python 3.10+, `uv`, pytest, ruff. No new dependency.

**Spec:** `/workspaces/autoform-bot/docs/superpowers/specs/2026-10-06-blueprint-search-design.md`, section
"PR 2: a contract on the statement text". This is PR 2 of five for
[#143](https://github.com/facebookresearch/autoform-bot/issues/143).

**Where to work:** worktree `/workspaces/autoform-bot/.claude/worktrees/statement-span`, branch
`feat/issue-143-statement-span`, on top of PR 1's commit. Run every command from that directory. The five PR
commits stack on this one local branch and are split into branches at submission.

## Global Constraints

- Python 3.10+, run through `uv`. No new dependency.
- Markdown under `blueprint/` stays the only authored state. The audit writes nothing.
- Public CLI and JSON shapes are contracts. This PR adds two finding codes and changes no JSON shape.
- `autoform_cli/README.md` is the single source of command-line truth.
- The PR passes `make lint`, `make test` and `make check-example`.
- Line length 120. No formatter runs in CI: match the surrounding code and do not reformat unrelated lines.
- Tests and docs change in the same commit as the behaviour they describe.
- **One commit for this PR.** Tasks 1 and 2 make working commits; Task 3 squashes them into a single commit on top
  of PR 1's commit. The message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Never push and never open a pull request.** The user approves all five PRs first.
- Never `git add` anything under `docs/superpowers/`; those files live only in the main checkout.
- Never use bare `git stash` in this worktree.
- Known baseline: `tests/test_project_create.py::test_file_swapped_in_before_open_is_not_called_a_link[parent]` and
  `[ancestor]` fail on untouched `main` on this machine. Every other test must pass.

## Decisions that differ from the spec

1. **The audit judges the statement as the site renders it, not a re-render of masked lines.** The first draft
   masked the statement, deleted heading lines and rendered what was left. Review showed that this differs from the
   published page: a setext or quoted heading was not dropped, a `#` line inside display mathematics was deleted,
   `<!--` inside inline code hid the rest, and text indented inside a `<div>` was lost. `visible_prose` renders the
   statement unchanged and leaves out heading, `pre` and diagram elements while walking the result.
2. **`visible_text` is replaced by `visible_prose`.** Same purpose, added here because the audit is its first
   caller. PR 3 may use it or `rendered_visible_text` for search fields. The spec is updated in Task 3.
3. **Heading text is not judged.** PR 1 settled that a subheading alone is not statement text, so `### Setting`
   over `TODO` is a placeholder, not a pass.
4. **The marker rule is tightened, for coverage too.** `TODO-lists form a monoid.` and
   `Unknown-variance case: ...` were read as placeholder markers because a hyphen counted with nothing after it.
   A hyphen or dash now marks a placeholder only when whitespace or the end of the text follows. Every placeholder
   case in `tests/test_coverage.py` still holds. This is a small behaviour change to coverage evidence, stated in
   the PR description.
5. **The tree walk becomes iterative.** `<span>` nested about 1,000 deep raised an uncaught `RecursionError` that
   ended the whole audit. That is reachable today from a coverage cell; this PR would extend it to every
   statement, so it is fixed here.
6. **Rendering runs only for formalizable articles.** It costs about 1 ms per article.

## Behaviour (measured on a scratch prototype; every row is a test below)

| Statement | Finding |
| --- | --- |
| `TODO`, `**TBD.**`, `TODO: state it`, `- TODO`, `TBD - pick one` | `placeholder-statement-text` |
| `### Setting` then `TODO`; setext `Setting` / `=======` then `TODO`; `> ### Setting` / `> TODO` | `placeholder-statement-text` |
| A fenced Lean block or Mermaid diagram, then `TODO` | `placeholder-statement-text` |
| `TODO: tighten the bound.` then a real statement | `placeholder-statement-text` (opens with a marker) |
| `Unknown: whether $P = NP$.` | `placeholder-statement-text` (documented limit) |
| `<span hidden>…</span>`, `---`, `[ ](missing.md)`, `![diagram](d.png)`, `...`, `⊥ ≠ ⊤` | `empty-statement-text` |
| `Pending Mathlib PR 1234 …`, `TODO state it`, `TODO-lists form a monoid.` | none |
| `$$ n + 0 = n $$`, `` `Nat.add_zero` ``, ``TODO `<!--` real statement``, text indented inside `<div>` | none |
| empty, a comment only, a fence only, a heading only | `missing-statement-text`, as today |

The prototype broke no existing test and added no finding to the bundled example.

## Review Focus

Each line has a test in Task 1 or Task 2.

1. A real statement that opens with `TODO:` and a note. Expected: `placeholder-statement-text`, so the marker is
   not shipped unnoticed.
2. A placeholder under any published heading form (ATX, setext, quoted). Expected: `placeholder-statement-text`.
3. A real statement that begins with a hyphenated word such as `Unknown-variance`. Expected: no finding.
4. A placeholder in an article that is not formalizable. Expected: no finding.
5. Markup nested thousands of elements deep. Expected: the audit finishes; it does not crash.

## Known limits (for the README and the PR description, not fixed here)

- `Unknown: …` and `Pending — …` at the start of a real statement are reported. The author rewords.
- A statement with no letter or digit (`⊥ ≠ ⊤`) is `empty-statement-text`.
- `To be written`, `N/A`, `FIXME`, `TODO state it` pass. They are left to review.
- Only the `hidden` attribute counts as hiding; `style="display:none"` does not.
- Rendering cost is the site renderer's own and is superlinear on pathological input (4,000 inline formulas in one
  statement take about 23 s). `autoform render` pays the same cost for the same article.
- `published_tables` still walks recursively. Only coverage reaches it, and it is unchanged.

## Upstream coordination

`main` is still `7fa6d1d`. The maintainer asked for #143 after #90, so #90 probably lands first and this commit
will need a rebase.

| Open PR | Overlap | What this plan does about it |
| --- | --- | --- |
| #165 | `coverage.py` call sites and import block; `markdown.py` `__all__` | Coverage imports the helpers under their old private names, so its call sites do not change |
| #124, #90 | `audit.py` around `_read_article` and `if not article.statement_text:` | `_ArticleShape` is built with keyword arguments; expect a manual rebase |
| #90 | README hunk near `overfull-container` | The new subsection goes at the end of "Audit contract", away from that hunk |
| #141, #166, #156, #157, #140, #145 | README hunks elsewhere | None needed |

## File Structure

| File | Change | Responsibility |
| --- | --- | --- |
| `autoform_cli/markdown.py` | Modify | Gains `PLACEHOLDER_WORDS`, `has_substance`, `is_placeholder`, `visible_prose`; `_visible_parts` becomes iterative |
| `autoform_cli/coverage.py` | Modify | Imports the two functions; its own copies and constants are deleted |
| `autoform_cli/audit.py` | Modify | `_statement_fault` picks at most one statement finding |
| `autoform_cli/README.md` | Modify | "Audit contract" gains a "Statement text" subsection |
| `skills/agent-review/references/roadmap-quality.md` | Modify | One usability bullet for what the audit cannot judge |
| `tests/test_markdown.py` | Modify | Tests for the helpers, `visible_prose` and deep nesting |
| `tests/test_audit.py` | Modify | Tests for the two findings |
| `tests/test_coverage.py` | Untouched | Must pass unchanged |

---

### Task 1: Shared helpers in `markdown.py`

**Files:**
- Modify: `autoform_cli/markdown.py` (constants near line 95; after `rendered_visible_text`; `_visible_parts`;
  `__all__`)
- Modify: `autoform_cli/coverage.py:19-43` and `:528-561`
- Test: `tests/test_markdown.py`

**Interfaces:**
- Consumes: nothing from this plan.
- Produces, in `autoform_cli.markdown`:
  - `PLACEHOLDER_WORDS: frozenset[str]`
  - `has_substance(visible: str) -> bool`
  - `is_placeholder(visible: str) -> bool`
  - `visible_prose(value: str) -> str`: Markdown in, the reader-visible text outside headings, code blocks and
    diagrams out, whitespace collapsed.

- [ ] **Step 1: Write the failing tests**

In `tests/test_markdown.py`, add `PLACEHOLDER_WORDS`, `has_substance`, `is_placeholder` and `visible_prose` to the
existing `from autoform_cli.markdown import (...)` block, then append at the end of the file:

```python
@pytest.mark.parametrize(
    "visible",
    ["TODO", "tbd.", "**TODO.**", "todo tbd", "TODO: state it", "TBD - pick one", "Pending – later", "TODO -"],
)
def test_is_placeholder_accepts_bare_and_marker_placeholders(visible: str) -> None:
    assert is_placeholder(visible)


@pytest.mark.parametrize(
    "visible",
    [
        "",
        "Pending Mathlib PR 1234",
        "TODO state it",
        "Let x be a todo list.",
        "TODO-lists form a monoid.",
        "Unknown-variance case: the sample mean is normal.",
    ],
)
def test_is_placeholder_leaves_sentences_alone(visible: str) -> None:
    assert not is_placeholder(visible)


@pytest.mark.parametrize(("visible", "expected"), [("", False), ("...", False), ("**_~", False), ("x", True)])
def test_has_substance_needs_a_word_character(visible: str, expected: bool) -> None:
    assert has_substance(visible) is expected


def test_placeholder_words_are_the_coverage_contract_words() -> None:
    assert PLACEHOLDER_WORDS == {"pending", "placeholder", "todo", "tbd", "unknown"}


@pytest.mark.parametrize(
    "source",
    [
        "### Setting\n\nLet x.",
        "Setting\n=======\n\nLet x.",
        "> ### Quoted\n> Let x.",
        "```lean\ntheorem t : True\n```\n\nLet x.",
        "```mermaid\ngraph TD\n```\n\nLet x.",
        "    indented code\n\nLet x.",
        "<!-- note -->Let x.",
    ],
)
def test_visible_prose_leaves_out_headings_code_blocks_and_diagrams(source: str) -> None:
    assert visible_prose(source) == "Let x."


def test_visible_prose_keeps_inline_code_and_drops_hidden_text() -> None:
    assert visible_prose("Use `Nat.add_zero`.") == "Use Nat.add_zero."
    assert visible_prose("<span hidden>secret</span> shown") == "shown"


@pytest.mark.parametrize("tag", ["span", "div", "b"])
def test_visible_text_survives_markup_nested_thousands_deep(tag: str) -> None:
    source = f"<{tag}>" * 3000 + "x"

    assert rendered_visible_text(source) == "x"
    assert visible_prose(source) == "x"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_markdown.py -q 2>&1 | tail -5`
Expected: collection error, `ImportError: cannot import name 'PLACEHOLDER_WORDS' from 'autoform_cli.markdown'`.

- [ ] **Step 3: Add the constants and the three functions to `markdown.py`**

After the `_WHITESPACE = re.compile(r"\s+")` line, add:

```python
#: Words that name the absence of a decision.
PLACEHOLDER_WORDS = frozenset({"pending", "placeholder", "todo", "tbd", "unknown"})
#: Punctuation that turns a leading placeholder into a marker, as in ``TODO:``.
#: A hyphen or dash needs space after it, so ``Unknown-variance`` stays a word.
_MARKER_PUNCTUATION = re.compile(r"^\s*(?::|[-–—](?=\s|$))")
#: Elements that label or illustrate prose without being prose.
_ASIDE_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "pre"})
```

Directly after the `rendered_visible_text` function, add:

```python
def visible_prose(value: str) -> str:
    """Return the prose a reader sees once ``value`` is published.

    Headings, code blocks and diagrams are left out: a heading names what
    follows and a block of code illustrates it, but neither says it. Inline
    code stays, because a sentence may name a declaration.
    """

    tree = render_tree(value)
    if tree is None:
        return ""
    return _collapse("".join(_visible_parts(tree, hidden=False, aside=True)))


def has_substance(visible: str) -> bool:
    """Whether anything a reader could act on survives emphasis and punctuation."""

    return bool(re.search(r"\w", re.sub(r"[*_~\\]", "", visible)))


def is_placeholder(visible: str) -> bool:
    """Whether the text only announces that a decision is still outstanding.

    Two shapes are rejected. Text whose every word is a placeholder, however
    decorated -- ``TBD``, ``**TODO.**`` -- and text that opens with one used as
    a marker, where punctuation separates it from the rest: ``TODO: choose a
    milestone``.

    A status word that merely begins a sentence is left alone, because it is
    usually carrying real information: "Pending Mathlib PR 1234" and "Unknown
    provenance, excluded by agreement" both name something a reader can check.
    Rejecting those pushed authors toward vaguer wording to satisfy the checker.

    The gap this leaves is a marker written without punctuation, as in "TODO
    choose a milestone". That reads as prose to any rule cheap enough to trust,
    so it is left to human review rather than guessed at.
    """

    stripped = re.sub(r"[*_~\\]", "", visible)
    words = re.findall(r"\w+", stripped.casefold())
    if not words:
        return False
    if all(word in PLACEHOLDER_WORDS for word in words):
        return True
    if words[0] not in PLACEHOLDER_WORDS:
        return False
    _, _, remainder = stripped.casefold().partition(words[0])
    return _MARKER_PUNCTUATION.match(remainder) is not None
```

In `__all__`, add `"PLACEHOLDER_WORDS",` after `"LINK",`; `"has_substance",` and `"is_placeholder",` after
`"frontmatter_end",`; `"visible_prose",` after `"strip_line_comments",`.

- [ ] **Step 4: Make the tree walk iterative and able to skip asides**

Replace the whole `_visible_parts` function with:

```python
def _visible_parts(element: object, hidden: bool, aside: bool = False) -> list[str]:
    """Walk a parsed tree, collecting only the text a browser would draw.

    With ``aside``, headings, code blocks and diagrams are left out as well.
    """

    parts: list[str] = []
    # An explicit stack, so markup nested a thousand elements deep cannot
    # exhaust the interpreter's own.
    pending: list[tuple[object, bool]] = [(element, hidden)]
    while pending:
        item, inherited = pending.pop()
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item.tag, str):
            # A comment or processing instruction. Its text is markup, not
            # content, and a reader never sees it. Any tail text belongs to the
            # parent, which queued it below.
            continue
        concealed = _conceals(item, inherited) or (aside and _is_aside(item))
        if not concealed and item.text:
            parts.append(item.text)
        for child in reversed(item):
            # Tail text sits in this element, not the child, so it is hidden
            # only when this element is.
            if not concealed and child.tail:
                pending.append((child.tail, False))
            pending.append((child, concealed))
    return parts


def _is_aside(element: object) -> bool:
    return _local_name(element) in _ASIDE_TAGS or "mermaid" in element.attrib.get("class", "").split()
```

- [ ] **Step 5: Make `coverage.py` import the helpers**

Directly after the parenthesised `from .markdown import (...)` block, add two lines. The private aliases keep
`_validate_evidence` untouched, which keeps this change clear of open PR #165:

```python
from .markdown import has_substance as _has_substance
from .markdown import is_placeholder as _is_placeholder
```

Delete the two constants and their comments (`_PLACEHOLDER_EVIDENCE` and `_MARKER_PUNCTUATION`, four lines), and
delete the whole `_has_substance` and `_is_placeholder` function definitions. `import re` stays: `_SEPARATOR` uses
it. Nothing else in `coverage.py` changes.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_markdown.py tests/test_coverage.py tests/test_audit.py tests/test_render.py -q 2>&1 | tail -3 && make lint`
Expected: all pass, lint clean.

Run: `git diff --stat -- tests/test_coverage.py`
Expected: no output.

- [ ] **Step 7: Commit (working commit, squashed in Task 3)**

```bash
git add autoform_cli/markdown.py autoform_cli/coverage.py tests/test_markdown.py
git commit -m "wip: share the placeholder rule and visible prose"
```

---

### Task 2: Report empty and placeholder statements

**Files:**
- Modify: `autoform_cli/audit.py:29-33` (imports), `:178-185` (the finding), `:250-269` (`_ArticleShape`,
  `_read_article`)
- Modify: `autoform_cli/README.md` (end of "Audit contract")
- Modify: `skills/agent-review/references/roadmap-quality.md` ("Usability and status discipline")
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes from Task 1: `has_substance(visible: str) -> bool`, `is_placeholder(visible: str) -> bool`,
  `visible_prose(value: str) -> str`.
- Consumes from PR 1: `article_parts(text).statement`, `content_lines`, `HEADING`.
- Produces: finding codes `empty-statement-text` and `placeholder-statement-text`. Nothing later imports from here.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_audit.py`. `_article`, `_coverage`, `_finding_map` and `audit_blueprint` already exist in
that file.

```python
def _statement_codes(tmp_path: Path, prose: str) -> set[str]:
    blueprint = tmp_path / "blueprint"
    _coverage(blueprint)
    _article(blueprint, "chapter/result.md", prose=prose, declaration="theorem")
    return {code for code, _reason in _finding_map(blueprint).get("roadmap/chapter/result.md", [])}


@pytest.mark.parametrize(
    "prose",
    [
        "TODO",
        "**TBD.**",
        "TODO: state it",
        "- TODO",
        "TBD - pick one",
        "### Setting\n\nTODO",
        "Setting\n=======\n\nTODO",
        "> ### Setting\n> TODO",
        "```lean\ntheorem draft : True := trivial\n```\n\nTODO",
        "```mermaid\ngraph TD\n```\n\nTODO",
        "TODO: tighten the bound.\n\nFor every $n$, $n + 0 = n$.",
        "<!-- For every $n$, $n + 0 = n$. -->\nTBD",
        "Unknown: whether $P = NP$.",
    ],
)
def test_audit_reports_a_placeholder_statement(tmp_path: Path, prose: str) -> None:
    assert _statement_codes(tmp_path, prose) == {"placeholder-statement-text"}


@pytest.mark.parametrize(
    "prose",
    [
        "<span hidden>For every $n$, $n + 0 = n$.</span>",
        "---",
        "[ ](missing.md)",
        "![diagram](diagram.png)",
        "...",
        "⊥ ≠ ⊤",
    ],
)
def test_audit_reports_a_statement_that_shows_a_reader_nothing(tmp_path: Path, prose: str) -> None:
    assert _statement_codes(tmp_path, prose) == {"empty-statement-text"}


@pytest.mark.parametrize(
    "prose",
    [
        "Pending Mathlib PR 1234, this is `Nat.add_zero`.",
        "TODO state it",
        "$$\nn + 0 = n\n$$",
        "$$\n# x = y\n$$",
        "`Nat.add_zero`",
        "TODO `<!--` real statement here",
        "<div>\n\n    For all n.\n\n</div>",
        "TODO-lists form a monoid.",
        "Unknown-variance case: the sample mean is normal.",
    ],
)
def test_audit_accepts_a_statement_that_says_something(tmp_path: Path, prose: str) -> None:
    assert _statement_codes(tmp_path, prose) == set()


def test_audit_reports_one_statement_finding_at_a_time(tmp_path: Path) -> None:
    # Nothing published at all is "missing", never also "empty".
    assert _statement_codes(tmp_path, "<!-- TODO -->") == {"missing-statement-text"}


def test_statement_findings_say_what_is_wrong(tmp_path: Path) -> None:
    blueprint = tmp_path / "blueprint"
    _coverage(blueprint)
    _article(blueprint, "chapter/todo.md", prose="TODO", declaration="theorem")
    _article(blueprint, "chapter/rule.md", prose="---", declaration="theorem")

    findings = _finding_map(blueprint)

    assert findings["roadmap/chapter/todo.md"] == [
        (
            "placeholder-statement-text",
            "formalizable article's statement is a placeholder, or opens with one used as a marker",
        )
    ]
    assert findings["roadmap/chapter/rule.md"] == [
        ("empty-statement-text", "formalizable article's statement shows a reader no text")
    ]


def test_audit_leaves_a_placeholder_alone_outside_formalizable_articles(tmp_path: Path) -> None:
    blueprint = tmp_path / "blueprint"
    _coverage(blueprint)
    _article(blueprint, "chapter/README.md", prose="TODO")
    _article(blueprint, "chapter/result.md", declaration="theorem")

    assert "roadmap/chapter/README.md" not in _finding_map(blueprint)


def test_audit_survives_a_statement_nested_thousands_deep(tmp_path: Path) -> None:
    assert _statement_codes(tmp_path, "<span>" * 3000 + "For all n.") == set()


def test_bundled_example_has_no_statement_text_finding(repo_root: Path) -> None:
    blueprint = repo_root / "skills" / "setup" / "assets" / "cabannes-thesis-project" / "blueprint"

    codes = {finding.code for finding in audit_blueprint(blueprint).findings}

    assert not codes & {"missing-statement-text", "empty-statement-text", "placeholder-statement-text"}
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_audit.py -q 2>&1 | tail -30`
Expected: `test_audit_reports_a_placeholder_statement` (13 cases),
`test_audit_reports_a_statement_that_shows_a_reader_nothing` (6 cases) and
`test_statement_findings_say_what_is_wrong` FAIL, each because the finding set is empty or the key is absent.
These pass already and are guards, proved live in Step 8:
`test_audit_accepts_a_statement_that_says_something`, `test_audit_reports_one_statement_finding_at_a_time`,
`test_audit_leaves_a_placeholder_alone_outside_formalizable_articles`,
`test_audit_survives_a_statement_nested_thousands_deep`, `test_bundled_example_has_no_statement_text_finding`.

- [ ] **Step 3: Implement**

In `autoform_cli/audit.py`, the `markdown` imports become (existing one-per-line style):

```python
from .markdown import article_parts as _article_parts
from .markdown import content_lines as _content_lines
from .markdown import has_substance as _has_substance
from .markdown import HEADING as _HEADING
from .markdown import is_placeholder as _is_placeholder
from .markdown import local_target_issue as _local_target_issue
from .markdown import markdown_links as _markdown_links
from .markdown import visible_prose as _visible_prose
```

After the `_DEPRECATED_ATTRIBUTE` line, add:

```python
#: What can be wrong with a statement's text, in the order the audit checks it.
_STATEMENT_FAULTS = {
    "missing-statement-text": "formalizable article has no statement text before its first H2 section",
    "empty-statement-text": "formalizable article's statement shows a reader no text",
    "placeholder-statement-text": (
        "formalizable article's statement is a placeholder, or opens with one used as a marker"
    ),
}
```

In `audit_graph`, replace

```python
            if not article.statement_text:
                findings.append(
                    AuditFinding(
                        article_path,
                        "missing-statement-text",
                        "formalizable article has no statement text before its first H2 section",
                    )
                )
```

with

```python
            fault = _statement_fault(article.statement)
            if fault is not None:
                findings.append(AuditFinding(article_path, fault, _STATEMENT_FAULTS[fault]))
```

Replace `_ArticleShape` and `_read_article` with:

```python
@dataclass(frozen=True, slots=True)
class _ArticleShape:
    statement: str
    has_depends_section: bool


def _read_article(path: Path) -> _ArticleShape:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return _ArticleShape(statement="", has_depends_section=False)

    parts = _article_parts(text)
    return _ArticleShape(
        statement=parts.statement,
        has_depends_section=any(section.title.casefold() == "depends on" for section in parts.sections),
    )


def _statement_fault(statement: str) -> str | None:
    """Return the code of what is wrong with a statement's text, or ``None``.

    The text is judged as the site publishes it, so a hidden element, an image
    or a bare rule states nothing however much source it takes.
    """

    # A subheading names what follows; alone it states nothing.
    if not any(line.strip() and not _HEADING.match(line) for line in _content_lines(statement)):
        return "missing-statement-text"
    prose = _visible_prose(statement)
    if not _has_substance(prose):
        return "empty-statement-text"
    if _is_placeholder(prose):
        return "placeholder-statement-text"
    return None
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_audit.py tests/test_doctor.py tests/test_coverage.py -q 2>&1 | tail -3`
Expected: all pass. `tests/test_doctor.py` pins the bundled example at `5 finding(s): declared-coverage-gap`.

- [ ] **Step 5: Document the contract**

In `autoform_cli/README.md`, insert this subsection at the end of "Audit contract": after the paragraph that ends
"or creates another graph artifact." and before `## Open statements`.

```markdown
### Statement text

A formalizable article must state its result in prose a reader sees. At most
one of three findings reports a statement that does not, checked in this order:

- `missing-statement-text`: the statement has no prose outside code blocks, HTML
  comments, and headings.
- `empty-statement-text`: the published prose has no letter or digit, as with a
  hidden element, a horizontal rule, an image, or a link with no text.
- `placeholder-statement-text`: every word is one of `pending`, `placeholder`,
  `todo`, `tbd`, `unknown`, or the statement opens with one of them followed by
  a colon or a spaced dash, as in `TODO: state it`.

The prose is read as the site publishes it, without headings, code blocks, and
diagrams; inline code and mathematics count. A status word that begins a
sentence passes ("Pending Mathlib PR 1234 ..."), and so does a marker written
without punctuation; both are left to review. A real statement that opens
`Unknown: ...` is reported and needs rewording. Coverage evidence is held to the
same placeholder rule.
```

In `skills/agent-review/references/roadmap-quality.md`, under "Usability and status discipline", add as the
second bullet (the wording is the issue's):

```markdown
- Each statement uses standard notation, gives context for each symbol, says
  what the result is for, and contains no proof steps.
```

- [ ] **Step 6: Run the docs and skill tests**

Run: `uv run pytest tests/test_skill_examples.py tests/test_plugin_runtime.py -q 2>&1 | tail -3 && make lint`
Expected: all pass, lint clean.

- [ ] **Step 7: Commit (working commit, squashed in Task 3)**

```bash
git add autoform_cli/audit.py autoform_cli/README.md skills/agent-review/references/roadmap-quality.md tests/test_audit.py
git commit -m "wip: audit empty and placeholder statements"
git status --short
```

Expected: `git status --short` prints nothing.

- [ ] **Step 8: Prove the guard tests can fail**

The tree is clean, so each mutation is undone with `git restore`.

Mutation A. Insert `return "empty-statement-text"` as the first body line of `_statement_fault` (after the
docstring). Run `uv run pytest tests/test_audit.py -q 2>&1 | grep FAILED`. Expected among the failures:
`test_audit_accepts_a_statement_that_says_something`, `test_audit_reports_one_statement_finding_at_a_time`,
`test_audit_survives_a_statement_nested_thousands_deep`, `test_bundled_example_has_no_statement_text_finding`.
Then `git restore autoform_cli/audit.py`.

Mutation B. In `audit_graph`, change `if node.formalizable:` to `if True:`. Run
`uv run pytest tests/test_audit.py -q -k leaves_a_placeholder_alone 2>&1 | tail -3`. Expected: 1 failed. Then
`git restore autoform_cli/audit.py`.

Run: `git diff --exit-code && echo restored`
Expected: `restored`.

---

### Task 3: Verify the whole PR and make it one commit

**Files:**
- Modify (main checkout, never committed): `docs/superpowers/specs/2026-10-06-blueprint-search-design.md`

**Interfaces:**
- Consumes: the two working commits from Tasks 1 and 2.
- Produces: exactly one commit on top of PR 1's commit.

- [ ] **Step 1: Run the full gates**

Run: `make lint && make test 2>&1 | tail -4; make check-example; echo "exit $?"`
Expected: lint clean; only the two baseline failures named in Global Constraints; `make check-example` exit 0.

- [ ] **Step 2: Confirm the example and the untouched files**

Run: `uv run autoform audit skills/setup/assets/cabannes-thesis-project/blueprint --json | python3 -c "import json,sys; print(sorted({f['code'] for f in json.load(sys.stdin)['findings']}))"`
Expected: `['declared-coverage-gap']`.

Run: `git diff HEAD~2 --stat -- autoform_cli/render.py autoform_cli/graph.py tests/test_coverage.py`
Expected: no output.

- [ ] **Step 3: Measure what the audit now costs**

```bash
SCRATCH=/tmp/claude-1000/-workspaces-autoform-bot/871c4e72-d376-4bd7-814d-6dc20396d6a6/scratchpad
BENCH=/workspaces/autoform-bot/docs/superpowers/specs/audit-cost-bench.py
uv run python "$BENCH" "$SCRATCH/bench-head" 1000
rm -rf "$SCRATCH/pr1" && mkdir "$SCRATCH/pr1" && git archive HEAD~2 autoform_cli | tar -x -C "$SCRATCH/pr1"
(cd "$SCRATCH/pr1" && PYTHONPATH=. "$OLDPWD/.venv/bin/python" "$BENCH" "$SCRATCH/bench-pr1" 1000)
```

Expected: each line names the `autoform_cli` it measured (the second must be under `pr1/`). Review measured
0.70 s before and about 1.8 s after at 1,000 articles, about 1.1 ms per article. Record both figures in this
plan's closing notes. A figure far above that is a finding to raise, not to hide.

- [ ] **Step 4: Squash into one commit**

The guards stop the squash from swallowing a changed PR 1 commit or stray work.

```bash
BASE=$(git rev-parse HEAD~2)
test "$(git log -1 --format=%s "$BASE")" = "Define an article's statement once for the audit and the site" || { echo "BASE is not PR 1"; exit 1; }
test -z "$(git status --short)" || { echo "tree not clean"; exit 1; }
git reset --soft "$BASE"
git commit -F - <<'EOF'
Audit statements that are empty or only a placeholder

A formalizable article could pass the audit with "TODO" as its statement,
or with markup that publishes nothing. Search and reuse depend on the
statement saying what the result is, so the audit now reports both.

At most one statement finding fires per article: missing-statement-text,
then empty-statement-text, then placeholder-statement-text. The prose is
judged as the site publishes it, without headings, code blocks and
diagrams.

The placeholder rule is the one coverage evidence follows. It moves to
markdown.py, and a hyphen or dash now marks a placeholder only when space
follows it, so "Unknown-variance" is a word in both places.

The rendered-tree walk is iterative, so deeply nested markup no longer
ends the audit with a RecursionError.

Part of #143.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline -3
```

Expected: the new commit, then PR 1's commit, then `7fa6d1d`. Nothing is pushed.

- [ ] **Step 5: Re-run the gates on the squashed commit**

Run: `git status --short && make lint && make test 2>&1 | tail -3`
Expected: clean tree, lint clean, the same two baseline failures only.

- [ ] **Step 6: Bring the spec in line**

In the spec's "PR 1 / Interface" section, replace the `visible_text` sentences with: PR 2 adds
`visible_prose(value)`, which renders the Markdown unchanged and leaves out heading, `pre` and diagram elements.
In "PR 2 / Shared helpers", add `visible_prose`, the tightened marker rule and the iterative walk. In
"PR 2 / Findings", replace `visible_text(statement)` in both rows with `visible_prose(statement)`. Do not
`git add` the spec.

## Notes for the PR description (written at submission, not now)

- Two new finding codes. A project whose articles carry `TODO` statements goes from a clean audit to findings, and
  `autoform audit` and `autoform doctor` then exit 1. No generated CI workflow runs either command.
- Coverage behaviour change: `TODO-later` style hyphenated text is no longer a placeholder marker.
- Carry the "Known limits" list and the Task 3 Step 3 timings.
- Stacked on PR 1; likely to need a rebase after #90 and #124.

## Outcome (2026-10-06)

Built as one local commit `0027a25` on top of `a07ed02`. Nothing pushed, no PR.

- Gates: `make lint` clean; `make test` 1,877 passed with the 2 baseline failures; `make check-example` exit 0;
  the bundled example still reports only `declared-coverage-gap`.
- Audit cost at 1,000 formalizable articles, best of 3: 0.64 s on PR 1, 1.68 s with this commit.
- Changed during execution: the `$$ / # x = y / $$` audit case was dropped (the loader rejects a second H1), and
  the inline-code `<!--` case expects `missing-depends-section` (PR 1's known limit).
- Added by the final review: the marker rule keeps `TODO—later` and `TODO -- later` as placeholders, and a
  conversion that fails midway no longer breaks rendering for later articles.
- Deferred minors: a non-ATX heading alone reports `empty-statement-text` rather than `missing-statement-text`;
  raw `<pre>` text is not counted as prose; two low-value tests; no coverage-level test for the marker change.

## Second review round (2026-10-06)

Commit is now `b8cc564`. Two fresh reviewers (correctness, maintainer's eye) found no critical or important bug.
Applied: `_PLACEHOLDER_WORDS` made private; the `aside` flag removed (`visible_prose` marks heading, `pre` and
diagram elements hidden, then reuses the ordinary walk); `_statement_finding` returns code and reason together;
the empty reason reads "has no prose with a letter or digit"; a coverage-level test for the hyphen change; an h5
heading case; `render_html` re-raise asserted; redundant tests and rows removed; README marker wording corrected
and the reference-link limit stated. Gates: lint clean, 1,869 passed + 2 baseline failures, check-example exit 0.

Not applied, with reasons: splitting the renderer fixes and the hyphen change into their own PRs (user's
one-commit-per-PR rule; user to decide); moving the README subsection (it would capture an unrelated paragraph or
collide with #90); unaliased coverage imports (aliases keep clear of #165); `except BaseException` (only one-shot
CLI paths render); wider punctuation and NFKC for markers (same accepted gap); resolving reference links defined
in later sections (false negative only, documented).
