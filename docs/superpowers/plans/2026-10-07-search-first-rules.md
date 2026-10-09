# Search-First Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tell the Roadmap, Formalize and Agent Review skills to run `autoform search` before a result is added a
second time, so the command from PR 3 is used.

**Architecture:** Three insertions of prose, each a new paragraph or list item, placed where upstream PR #172 does
not edit. Each names `autoform search` and links to the "Search contract" section of `autoform_cli/README.md`; none
restates a flag. Two tests in `tests/test_skill_examples.py` pin the rules and check that every skill link into the
reference lands on a real section.

**Tech Stack:** Markdown skills, pytest. No Python under `autoform_cli/` changes.

**Spec:** `/workspaces/autoform-bot/docs/superpowers/specs/2026-10-06-blueprint-search-design.md`, section
"PR 5: search-first rules".

## Global Constraints

- Work only in the worktree `/workspaces/autoform-bot/.claude/worktrees/statement-span`, on branch
  `feat/issue-143-statement-span`, whose tip is `6d95a6b` (PR 3).
- The result is exactly one new commit on that branch. Do not push, and do not open or update a pull request.
- Never `git add` anything under `docs/superpowers/`. Never run bare `git stash`.
- `autoform_cli/README.md` is the single source of command-line truth: a skill names a command and links to the
  reference, and never restates an invocation or a flag.
- Skill prose wraps at 80 columns. Python line length is 120.
- Insert new lines only. Do not rewrap, move or edit an existing line of any skill; that is what keeps this
  mergeable with upstream PR #172 in either order.
- The new text must not contain `Execution notes` or `` `agents.md` ``: PR #172 adds a test that forbids both in
  the Roadmap and Formalize skills.
- Known baseline: `tests/test_project_create.py::test_file_swapped_in_before_open_is_not_called_a_link[parent]` and
  `[ancestor]` fail locally on untouched `main`. Any other failure is yours.

## Risks found while planning, and how the plan removes each

| # | Risk | Evidence | What the plan does |
|---|------|----------|--------------------|
| 1 | Textual conflict with PR #172, which rewrites parts of both skills and adds a test to the same file. | #172 edits `formalize/SKILL.md` lines 62–66 and 114–121, inserts after `roadmap/SKILL.md` line 70 and edits 89–95, and adds a test after line 89 of the test file. | Each insertion sits at least four unchanged lines from every #172 hunk: Roadmap after line 55, Formalize after line 78, tests after line 830. A prototype of these exact edits merged cleanly with #172 in both orders, and the merged tree passed all 28 skill tests. Task 2 repeats that check. |
| 2 | An agent searches once with a full sentence, gets nothing, and adds the duplicate anyway. | On the bundled example, `infimum losses consistent` returns no hit and `infimum loss` returns nine. One absent word means no hit. | Both skills say an empty result counts only after a retry with fewer words is also empty. The test pins that sentence in both. |
| 3 | An agent reads a refusal as "no hits". | Search exits 2 on an invalid blueprint (`dependency target does not exist`), and on an article that changed during the search. A Roadmap pass is often invalid mid-edit. | Both skills say a refusal is not an empty result. Roadmap is told to search before adding the article, and to repair what the refusal reports. |
| 4 | A hit is treated as the same result when it only shares words, and two different results are merged. | Matching is by substring; milestone pages are hits too (`Infimum Loss milestone` matched by title). | Roadmap must read each hit's statement, link only when another article already states the result, and is told that resemblance is no reason to merge. |
| 5 | Formalize uses a found declaration its article does not depend on, which silently changes the DAG and, under the open policy, fails CI. | Formalize already says a missing prerequisite returns to Roadmap, and that an undeclared open statement fails CI. | Formalize may use a hit's declaration only when the claimed article depends on that article, directly or through its dependencies; any other hit is a missing prerequisite, which the existing sentence already routes to Roadmap. |
| 6 | Formalize believes search covers all Lean code. | Search reads only `lean:` and `mathlib_declaration` names recorded in articles. | Formalize is told search finds only declarations an article records, and to look through the project's Lean files as well. |
| 7 | Parallel Roadmap agents each add the same result; neither search sees the other's worktree. | Roadmap already divides sections among agents with one owner for global consistency. | Roadmap says search reads only the checkout it runs in, and that owner repeats it for what parallel agents added. |
| 8 | A reviewer calls a roadmap duplicate-free because search found nothing. | Agent Review forbids claims without shown evidence. | The rubric says a second article stating the same result is a duplicate and that finding none does not prove there is none. |
| 9 | The "Search contract" heading is renamed during review of #171 and the three links break silently. | No test checks skill links into the reference today. | A new test resolves every `autoform_cli/README.md#fragment` link in the skills against the reference's headings. |
| 10 | The tests only restate the plan. `AGENTS.md` warns against tests that validate their own planning state. | Wording pins are this file's convention, but each must name the failure it prevents. | Two tests only. One checks real link targets. The other pins the fewest sentences that carry risks 2, 3, 5 and 8, and its docstring names the failure. |

## Review Focus

- A skill link whose fragment contains characters GitHub strips from a heading (for example a backtick or a
  colon): the link check must compute the same fragment GitHub does. Covered in Task 1 by the assertion that
  the four fragments already in use resolve.
- A `# comment` line inside a `bash` fence in the reference must not count as a heading. Covered in Task 1: the
  test skips fenced lines, and the reference has 16 `bash` fences with such lines.
- The merged result with PR #172, not only a clean textual merge: #172's own new test must pass on it. Covered
  in Task 2, Step 2.
- A hit that is the article being revised itself. Not tested; the Roadmap text says "another article".
- An agent on a host that installed the plugin before `search` existed. Not tested; skills and CLI ship in one
  plugin, so they cannot disagree.

---

### Task 1: The three rules and their tests

**Files:**
- Modify: `tests/test_skill_examples.py` (insert after line 830, the end of
  `test_skills_delegate_the_command_line_to_the_reference`)
- Modify: `skills/roadmap/SKILL.md` (insert after line 55)
- Modify: `skills/formalize/SKILL.md` (insert after line 78)
- Modify: `skills/agent-review/references/roadmap-quality.md` (insert after line 13)

**Interfaces:**
- Consumes: the heading `## Search contract` in `autoform_cli/README.md` (added by PR 3), whose GitHub fragment is
  `search-contract`.
- Produces: nothing a later task imports.

- [ ] **Step 1: Write the failing tests**

In `tests/test_skill_examples.py`, find the last line of `test_skills_delegate_the_command_line_to_the_reference`:

```python
    assert citing >= 3
```

Directly after it, before `def test_roadmap_reconciles_the_pages_setup_wrote`, insert:

```python


def test_skill_links_into_the_cli_reference_land_on_a_section(repo_root: Path) -> None:
    """A skill that cites a reference section must not point at a renamed one.

    Skills hold no command line of their own, so a link whose fragment no
    longer matches a heading leaves the agent at the top of a long file with no
    contract to read.
    """
    reference = (repo_root / "autoform_cli/README.md").read_text(encoding="utf-8")
    sections: set[str] = set()
    fenced = False
    for line in reference.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and (heading := re.fullmatch(r"#{1,6} +(.+?) *", line)):
            sections.add(re.sub(r"[^a-z0-9 -]", "", heading[1].lower()).replace(" ", "-"))

    cited: set[str] = set()
    for page in sorted((repo_root / "skills").glob("*/**/*.md")):
        if "assets" in page.relative_to(repo_root).parts:
            continue
        for fragment in re.findall(r"autoform_cli/README\.md#([^)\s]+)", page.read_text(encoding="utf-8")):
            assert fragment in sections, f"{page.relative_to(repo_root)} links to a missing section: #{fragment}"
            cited.add(fragment)
    assert {"commands", "search-contract"} <= cited


def test_skills_search_the_blueprint_before_adding_a_result(repo_root: Path) -> None:
    """`autoform search` prevents a duplicate only if an agent runs it first.

    Matching is literal, so the rule that matters most is that an empty result
    is not yet an answer: without it an agent searches once with a full
    sentence, finds nothing, and adds the result a second time.
    """

    def read(relative: str) -> str:
        return " ".join((repo_root / relative).read_text(encoding="utf-8").split())

    roadmap = read("skills/roadmap/SKILL.md")
    formalize = read("skills/formalize/SKILL.md")
    rubric = read("skills/agent-review/references/roadmap-quality.md")

    assert "Before adding a formalizable article, run `autoform search`" in roadmap
    assert "instead of adding a node" in roadmap
    assert "Before adding a helper, also run `autoform search`" in formalize
    assert "any other hit is a missing prerequisite" in formalize
    for skill in (roadmap, formalize):
        assert "An empty result counts only after a retry with fewer words is also empty" in skill
        assert "a refusal is not an empty result" in skill
    assert "Run `autoform search`" in rubric
    assert "Finding none does not prove there is none" in rubric
    for text in (roadmap, formalize, rubric):
        assert "README.md#search-contract)" in text
        assert "autoform search ." not in text and "--lean-root ." not in text
```

The file must keep exactly two blank lines between top-level functions.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_skill_examples.py -q -k "land_on_a_section or before_adding_a_result"`

Expected: 2 failed. `test_skill_links_into_the_cli_reference_land_on_a_section` fails on its last line, with
`search-contract` missing from the cited set; it must NOT fail on "links to a missing section", which would mean
the heading rule is wrong for a link that already exists. `test_skills_search_the_blueprint_before_adding_a_result`
fails on its first assertion.

- [ ] **Step 3: Add the Roadmap rule**

In `skills/roadmap/SKILL.md`, the paragraph that begins "Work from exact source passages." ends with the line
`requested Zulip work.` followed by a blank line and `Enumerate the entire adopted boundary`. Insert this
paragraph and one blank line between them, changing no existing line:

```markdown
Before adding a formalizable article, run `autoform search` over the blueprint
for its result, by a few distinctive words of the statement and by a likely
Lean name; the [search contract](../../autoform_cli/README.md#search-contract)
says what is matched. An empty result counts only after a retry with fewer
words is also empty, and a refusal is not an empty result: repair what it
reports and search again. Read each hit's statement. When another article
already states the result, link to it under `## Depends on` or `## Proof
depends on` instead of adding a node; a hit that only resembles the result is
no reason to merge the two. Search reads only the checkout it runs in, so the
owner of global consistency repeats it for what parallel agents added.
```

- [ ] **Step 4: Add the Formalize rule**

In `skills/formalize/SKILL.md`, the paragraph that begins "Read the complete article" ends with the line
`open-statement policy below allows.` followed by a blank line and `` `roadmap/README.md` sets the project's
policy. `` Insert this paragraph and one blank line between them, changing no existing line:

```markdown
Before adding a helper, also run `autoform search` over the blueprint for it,
as the [search contract](../../autoform_cli/README.md#search-contract)
describes. An empty result counts only after a retry with fewer words is also
empty, and a refusal is not an empty result. Search finds only declarations an
article records, so look through the project's Lean files as well. Use a hit's
declaration only when the claimed article depends on that hit's article,
directly or through its dependencies; any other hit is a missing prerequisite.
```

Do not edit the later sentence "A missing prerequisite, ... returns to Roadmap"; it already says where such a hit
goes, and PR #172 rewrites the lines around it.

- [ ] **Step 5: Add the Agent Review evidence item**

In `skills/agent-review/references/roadmap-quality.md`, under `## Evidence`, directly after the line
`4. Distinguish statement prerequisites from proof-only prerequisites.`, insert:

```markdown
5. Run `autoform search`, described in the
   [search contract](../../../autoform_cli/README.md#search-contract), for each
   main result in scope, by a few distinctive words and by its Lean name. A
   second article stating the same result is a duplicate. Finding none does not
   prove there is none, because matching is literal.
```

The link has three `..` because the file is one directory deeper than a `SKILL.md`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_skill_examples.py -q`

Expected: `27 passed`.

- [ ] **Step 7: Check that only lines were added**

Run: `git diff --numstat -- skills`

Expected: three rows, each with `0` in the second (deleted) column: `5 0` for `roadmap-quality.md`, `8 0` for
`formalize/SKILL.md`, `11 0` for `roadmap/SKILL.md`.

Run: `git diff -- skills | grep '^+' | awk 'length > 81'`

Expected: no output (no added line is wider than 80 columns; the `+` adds one).

### Task 2: Prove it survives PR #172, run the gates, commit

**Files:**
- No file changes beyond Task 1.

**Interfaces:**
- Consumes: the working tree from Task 1.
- Produces: one commit on `feat/issue-143-statement-span`.

- [ ] **Step 1: Commit**

```bash
git add tests/test_skill_examples.py skills/roadmap/SKILL.md skills/formalize/SKILL.md \
  skills/agent-review/references/roadmap-quality.md
git status --short
```

Expected: exactly those four files staged, nothing else listed.

```bash
git commit -m "$(cat <<'EOF'
Tell the skills to search the blueprint before adding a result

`autoform search` prevents a duplicate only when an agent runs it first, and
no skill mentioned it. Roadmap now searches before adding a formalizable
article and links to an article that already states the result. Formalize
searches before adding a helper and may use a hit only when its article is a
dependency of the claimed one. The roadmap-quality rubric names the search as
evidence for its duplicate check.

Matching is literal, so each rule says an empty result counts only after a
retry with fewer words, and that a refusal is not an empty result.

A new test resolves every skill link into the CLI reference against its
headings, so renaming a section cannot strand a skill.

Refs #143.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Merge with PR #172 in both orders and test the merged tree**

```bash
SCRATCH=/tmp/claude-1000/-workspaces-autoform-bot/871c4e72-d376-4bd7-814d-6dc20396d6a6/scratchpad
git fetch upstream pull/172/head:refs/remotes/upstream/pr-172 --quiet
A=$(git merge-tree --write-tree HEAD upstream/pr-172) && echo "ours<-172 clean"
B=$(git merge-tree --write-tree upstream/pr-172 HEAD) && echo "172<-ours clean"
test "$A" = "$B" && echo "same tree"
rm -rf "$SCRATCH/merged" && mkdir -p "$SCRATCH/merged" && git archive "$A" | tar -x -C "$SCRATCH/merged"
(cd "$SCRATCH/merged" && "$OLDPWD/.venv/bin/python" -m pytest tests/test_skill_examples.py -q -p no:cacheprovider)
```

Expected: `ours<-172 clean`, `172<-ours clean`, `same tree`, then `28 passed` (27 plus #172's own test).
`git merge-tree` writes objects only; it does not touch the worktree or the branch.

If #172 has merged or changed since this plan was written and a merge reports a conflict, do not rewrap to fix
it: move the affected insertion to the nearest paragraph break that is four or more unchanged lines from the new
hunk, amend the commit, and repeat this step.

- [ ] **Step 3: Check the rule against real output**

```bash
EX=skills/setup/assets/cabannes-thesis-project
.venv/bin/autoform search $EX "infimum losses consistent"
.venv/bin/autoform search $EX "infimum loss" --limit 2
```

Expected: the first prints `No matching articles.`; the second prints two hits, the first titled `Infimum loss`,
and the footer `2 of 9 matching article(s) shown.` This is the case the retry rule exists for.

- [ ] **Step 4: Run the project gates**

```bash
make lint
make test 2>&1 | tail -5
make check-example; echo "exit=$?"
```

Expected: `make lint` clean. `make test` reports 1,978 passed and the 2 known baseline failures in
`tests/test_project_create.py` (1,976 before, plus the 2 new tests). `make check-example` prints `exit=0`.

- [ ] **Step 5: Confirm the branch state**

```bash
git log --oneline -5
git status --short
git diff --stat HEAD~1
```

Expected: four commits above `cc7e3a8` (PR 1, PR 2, PR 3, this one), a clean worktree, and four files changed
with insertions only. Do not push.

## Self-review

- **Spec coverage.** Roadmap rule: Task 1 Step 3. Formalize rule, including "returns to Roadmap": Step 4, relying
  on the existing sentence. Agent Review duplicate check: Step 5, placed under Evidence so the existing bullet is
  not edited. "Names `autoform search`, links to the reference, restates no flag": asserted in Step 1. One
  assertion per rule: Step 1. `("search",)` in the documented commands: already added by PR 3.
- **Departures from the spec.** The spec asks Formalize to search "the blueprint first, then the pinned Mathlib
  checkout"; the existing Mathlib sentence is left where it is and the new paragraph says "also", because editing
  that sentence would touch a paragraph #172 rewrites. The spec does not ask for the link-resolution test; it is
  added for risk 9 and can be dropped without affecting the rules.
- **Placeholders.** None.
- **Names.** The fragment `search-contract` and the two test names are used identically in every step.
