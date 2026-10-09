# Search `--skeleton REPORT` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `autoform search --skeleton REPORT` attaches to every Lean target of a hit the elaborated signature
that an existing skeleton report records for it, without running Lean, and keeps working after the blueprint
is edited.

**Architecture:** `search_blueprint` gains a `skeleton` path. It loads the report with the existing
`load_skeleton_report` and looks signatures up by declaration name. `SearchLeanTarget` gains a `signature`
field that is always present in JSON and is `null` when there is nothing to attach. A report extracted from an
earlier state of the blueprint is still used; the result says so in a new top-level
`skeleton_matches_blueprint` field, and the CLI prints a warning on stderr in human mode.

**Tech Stack:** Python 3 (`autoform_cli/`), pytest, ruff (line length 120), Markdown reference
(`autoform_cli/README.md`, wrapped at 80).

**Spec:** `/workspaces/autoform-bot/docs/superpowers/specs/2026-10-06-blueprint-search-design.md`, section
"PR 4: `--skeleton REPORT`". Two deviations, both approved or forced, are listed under "Deviations from the
spec" below.

## Global Constraints

- Work only in the worktree `/workspaces/autoform-bot/.claude/worktrees/statement-span`, on branch
  `feat/issue-143-statement-span`, on top of `0d566b1`. Run every command from that directory.
- One commit for the whole PR, made in Task 3. **Do not push and do not open or update any pull request.**
- Never `git add` anything under `docs/superpowers/`. Never use bare `git stash`.
- Use the worktree's interpreter: `.venv/bin/python -m pytest ...`.
- `autoform_cli/README.md` is the only place the command line is documented. No skill file changes in this PR.
- `autoform search` stays read-only: it writes nothing and starts no process, with or without `--skeleton`.
- The JSON schema stays `autoform-search/v1`; `signature` and `skeleton_matches_blueprint` are added keys.
  (`v1` is itself unmerged, in the same PR #171, so no consumer exists yet.)
- Known baseline: `tests/test_project_create.py::test_file_swapped_in_before_open_is_not_called_a_link[parent]`
  and `[ancestor]` fail on untouched `main` in this environment. Any other failure is yours.
- A verified prototype of the whole change is saved at
  `/tmp/claude-1000/-workspaces-autoform-bot/871c4e72-d376-4bd7-814d-6dc20396d6a6/scratchpad/pr4/pr4-proto.patch`.
  It is a reference for exact text only. Follow the steps in order; do not apply it wholesale, because each test
  must be watched failing first.

## Deviations from the spec

1. **A report of another blueprint state is used, not refused** (decided by the user on 2026-10-07). The spec
   says search refuses, with exit 2, a report whose `blueprint_hash` differs. That makes the flag unusable
   during roadmap work, where every added article changes the hash. A signature states a Lean declaration,
   whichever article names it, so signatures are attached by declaration name and the mismatch is reported in
   `skeleton_matches_blueprint` and a stderr warning.
2. **No public `blueprint_hash(graph)`.** Draft upstream PR #141 adds a new call to the private
   `_blueprint_hash(graph)` and would merge without a textual conflict, so a rename would break `main`. An
   insert-only method `SkeletonReport.describes(graph)` is added instead and `_blueprint_hash` is untouched.

## Risks found while planning, and how the plan removes them

| # | Risk | Evidence | What the plan does |
|---|------|----------|--------------------|
| 1 | A bad report is reported as "project, blueprint, or Lean root path cannot be read". | `SkeletonError` is a `RuntimeError`, and `_search` in `__main__.py` has a generic `except (OSError, RuntimeError, ValueError)`. | `search.py` converts `SkeletonError` to `SearchError`, which the CLI already prints verbatim. A test asserts the generic message never appears. |
| 2 | Deeply nested JSON raises `RecursionError`, which the loader does not catch. | `json.loads("[" * 100000)` raises `RecursionError` (a `RuntimeError`). | Caught in `search.py` and reported as "skeleton report is malformed". Tested. |
| 3 | A report path that is a pipe or device blocks or exhausts memory, since the loader calls `read_text`. | `load_skeleton_report` reads the file whole, with no type check. | `search.py` requires `Path.is_file()` first. Pinned by the directory case, whose exact message only the guard produces. No real-pipe test: if the guard were removed, that test would hang the suite instead of failing. |
| 4 | Draft PR #141 bumps the report schema to `autoform-skeleton/v5`. | `gh pr diff 141`. | Search never names a schema version: it goes through `load_skeleton_report`, the test uses the `SKELETON_SCHEMA` constant, and the README says "a report that `autoform skeleton --output` wrote". |
| 5 | The match flag is wrongly false when extraction and search spell the blueprint path differently. | Prototype: the hash is equal for `.`, `blueprint`, and absolute paths; a symlinked project is already refused by `resolve_runtime_paths`. | A test runs four spellings of the blueprint and two of the report path. |
| 6 | With no refusal, a reader may not notice the report is older than the blueprint. | Deviation 1. | `skeleton_matches_blueprint` is `false` in JSON, and human mode warns on stderr, also when there is no hit. Tested for both. |
| 7 | With no refusal, a report from a different project attaches that project's signature to any declaration of the same name. | Deviation 1 removes the only cross-project guard. | Not prevented. Such a report makes `skeleton_matches_blueprint` false and triggers the warning; the README states that signatures are matched by name alone. |
| 8 | A signature is as old as the report: Lean files edited after extraction are not detected, because search does not run Lean. | By design; freshness needs a build. | Documented in the README as a reading aid and not review evidence. A lexical check against the sources is a possible follow-up, not part of this PR. |
| 9 | Report text reaches a terminal. | Signatures are multi-line and come from a file. | Each line passes through `_human_text`. A test puts an escape sequence in a signature. JSON output is `json.dumps`. |
| 10 | Existing tests pin the exact JSON of a result and of a Lean target. | `test_search_cli_emits_stable_json`, `test_the_bundled_example_answers_a_reuse_question`. | Their expectations gain the two new keys in Task 1. |
| 11 | Loading a large report slows every call. | Prototype: 2,000 articles with a 10 MB report: 2.17 s without the flag, 2.61 s with it. | Accepted and documented. The lookup table is built once, not per hit. |
| 12 | A warning on stdout would corrupt `--json` or break scripts reading human output. | — | The warning goes to stderr and only in human mode; JSON carries the field instead. Tested: stderr is empty with `--json`. |

## Review Focus

1. Lean source edited after the report was written: the reader expects to be told the signature may be stale.
   Not detectable without Lean; the README says so. No test.
2. A report from another project that shares declaration names: the reader expects not to be misled. Only the
   mismatch warning protects them (risk 7). No test beyond the mismatch flag.
3. A report of hundreds of megabytes: the reader expects a slow answer, not a crash. Not tested; the loader
   reads it whole.
4. A report path that is a pipe or device: expected refusal. The guard is pinned by the directory case in Task 2.
5. A report written by an older or newer CLI: expected refusal that names the schema this CLI reads. Pinned in
   Task 2 through `SKELETON_SCHEMA`.

---

### Task 1: Signatures from a report in `search_blueprint`

**Files:**
- Modify: `autoform_cli/skeleton.py` (class `SkeletonReport`, insert one method before `def node`)
- Modify: `autoform_cli/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: `load_skeleton_report(path) -> SkeletonReport`, `SkeletonError.issues`, `_blueprint_hash(graph)`
  (all existing in `autoform_cli/skeleton.py`).
- Produces: `SkeletonReport.describes(graph: Graph) -> bool`;
  `search_blueprint(..., skeleton: str | Path | None = None, ...)`;
  `SearchLeanTarget.signature: str | None` (JSON key `signature`);
  `SearchResult.skeleton_matches_blueprint: bool | None` (JSON key of the same name; `None` without a report);
  `SearchError` messages `"skeleton report does not exist or is not a regular file"` and
  `"skeleton report is malformed"`.
  Test helpers `_skeleton_report(project, signatures, *, only=None, blueprint=None) -> Path` and
  `_signatures(project, query, **options) -> dict[str, str | None]` in `tests/test_search.py`.

- [ ] **Step 1: Add the imports and helpers to `tests/test_search.py`**

Replace the two import lines

```python
from autoform_cli.runtime import RuntimeProjectionError, load_runtime_graph
from autoform_cli.search import SEARCH_SCHEMA, SearchError, search_blueprint, statement_preview
```

with

```python
from autoform_cli.graph import load_graph
from autoform_cli.lean import declaration_names
from autoform_cli.runtime import RuntimeProjectionError, load_runtime_graph
from autoform_cli.search import SEARCH_SCHEMA, SearchError, search_blueprint, statement_preview
from autoform_cli.skeleton import (
    SKELETON_SCHEMA,
    DeclarationSkeleton,
    NodeSkeleton,
    SkeletonReport,
    UnresolvedTarget,
    _blueprint_hash,
    load_skeleton_report,
)
```

Append at the end of the file:

```python


_SEMANTIC = json.dumps(
    {"generated": [], "root": {"safety": "safe", "type": {"sort": {"zero": None}}}}, separators=(",", ":")
)


def _skeleton_report(
    project: Path,
    signatures: dict[str, str],
    *,
    only: tuple[str, ...] | None = None,
    blueprint: Path | None = None,
) -> Path:
    """Write the report extraction would give if Lean elaborated ``signatures``, without running Lean."""

    graph = load_graph(blueprint or project / "blueprint")
    targets = tuple(
        (node_id, tuple(declaration_names(node.lean))) for node_id, node in sorted(graph.nodes.items()) if node.lean
    )
    selected = tuple(node_id for node_id, _ in targets if only is None or node_id in only)
    nodes: list[NodeSkeleton] = []
    unresolved: list[UnresolvedTarget] = []
    for node_id, names in targets:
        if node_id not in selected:
            continue
        unresolved += [UnresolvedTarget(node_id, name, "not built") for name in names if name not in signatures]
        declarations = tuple(
            DeclarationSkeleton(
                name=name,
                kind="theorem",
                module="Project",
                path=None,
                start_line=None,
                end_line=None,
                signature=signatures[name],
                raw_signature=signatures[name],
                semantic=_SEMANTIC,
                depends=(),
                source_withheld=True,
                lean_version="4.32.2",
                trusted=(),
                assumed=(),
                assumed_semantics=(),
                boundary_modules=(),
                axioms=(),
                axiom_semantics=(),
            )
            for name in names
            if name in signatures
        )
        article_path = graph.nodes[node_id].path.relative_to(graph.blueprint_dir).as_posix()
        nodes.append(NodeSkeleton(node_id, article_path, declarations, complete=len(declarations) == len(names)))
    report = SkeletonReport(
        blueprint_hash=_blueprint_hash(graph),
        targets=targets,
        selection="all" if only is None else "filtered",
        selected_nodes=selected,
        nodes=tuple(nodes),
        unresolved=tuple(unresolved),
    )
    path = project / "skeleton.json"
    path.write_text(report.to_json(), encoding="utf-8")
    # Search must accept what extraction writes and nothing else.
    assert load_skeleton_report(path) == report
    return path


def _signatures(project: Path, query: str, **options: object) -> dict[str, str | None]:
    return {
        target.declaration: target.signature
        for hit in search_blueprint(project, query, **options).hits
        for target in hit.lean_targets
    }
```

`SKELETON_SCHEMA` is used only in Task 2; ruff will flag it as unused until then, which is expected at this
step. The helper asserts that the real loader accepts what it wrote, so it cannot drift into a format search
would never meet.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_search.py`:

```python


def test_a_skeleton_report_attaches_the_signature_of_each_declaration_it_holds(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(
        project,
        "convexity/pair.md",
        title="Convex pair",
        metadata=("declaration: theorem", "lean: Project.left, Project.right"),
    )
    report = _skeleton_report(
        project, {"Project.separation": "Project.separation : True", "Project.left": "Project.left :\n  1 = 1"}
    )

    assert _signatures(project, "separating", skeleton=report) == {"Project.separation": "Project.separation : True"}
    # A declaration extraction did not resolve has no signature; its neighbour keeps its own.
    assert _signatures(project, "pair", skeleton=report) == {
        "Project.left": "Project.left :\n  1 = 1",
        "Project.right": None,
    }
    assert _signatures(project, "separating") == {"Project.separation": None}


def test_a_report_of_selected_articles_leaves_the_others_without_a_signature(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _article(project, "convexity/other.md", title="Convex other", metadata=("lean: Project.other",))
    signatures = {"Project.separation": "Project.separation : True", "Project.other": "Project.other : True"}
    report = _skeleton_report(project, signatures, only=("convexity/other",))

    assert _signatures(project, "separating", skeleton=report) == {"Project.separation": None}
    assert _signatures(project, "other", skeleton=report) == {"Project.other": "Project.other : True"}


def test_a_report_matches_however_the_blueprint_path_was_spelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    monkeypatch.chdir(project)
    report = _skeleton_report(project, {"Project.separation": "S"}, blueprint=Path("blueprint"))

    assert search_blueprint(project, "separating").skeleton_matches_blueprint is None
    for target in (project, project / "blueprint", Path("."), Path("blueprint")):
        for path in (report, Path("skeleton.json")):
            assert search_blueprint(target, "separating", skeleton=path).skeleton_matches_blueprint is True


def test_a_report_outlives_blueprint_edits_and_says_that_it_no_longer_matches(tmp_path: Path) -> None:
    project = _project(tmp_path)
    report = _skeleton_report(project, {"Project.separation": "Project.separation : True"})
    roadmap = project / "blueprint/roadmap/convexity"

    # The article is reworded and moved, and another one starts naming the declaration.
    old = roadmap / "hyperplane.md"
    (roadmap / "support.md").unlink()
    (roadmap / "moved.md").write_text(old.read_text(encoding="utf-8").replace("affine", "linear"), encoding="utf-8")
    old.unlink()
    _article(project, "convexity/new.md", title="New", metadata=("lean: Project.added, Project.separation",))

    result = search_blueprint(project, "Project.separation", skeleton=report)
    assert result.skeleton_matches_blueprint is False
    assert {hit.node_id: [target.signature for target in hit.lean_targets] for hit in result.hits} == {
        "convexity/moved": ["Project.separation : True"],
        # Nothing was extracted for a declaration named after the report was written.
        "convexity/new": [None, "Project.separation : True"],
    }
```

In the existing `test_search_writes_nothing_and_starts_no_process`, replace

```python
    monkeypatch.setattr(socket, "socket", forbidden)
    before = {path: path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()}

    assert search_blueprint(project, "convex", lean_root=project).total_matches == 3
```

with

```python
    monkeypatch.setattr(socket, "socket", forbidden)
    report = _skeleton_report(project, {"Project.separation": "Project.separation : True"})
    before = {path: path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()}

    assert search_blueprint(project, "convex", lean_root=project, skeleton=report).total_matches == 3
```

In `test_search_cli_emits_stable_json`, replace

```python
        "schema": SEARCH_SCHEMA,
        "source_revision": load_runtime_graph(project).source_revision,
```

with

```python
        "schema": SEARCH_SCHEMA,
        "skeleton_matches_blueprint": None,
        "source_revision": load_runtime_graph(project).source_revision,
```

and replace

```python
        "lean_targets": [{"declaration": "Project.separation", "line": None, "source_file": None}],
```

with

```python
        "lean_targets": [{"declaration": "Project.separation", "line": None, "signature": None, "source_file": None}],
```

In `test_the_bundled_example_answers_a_reuse_question`, replace

```python
        {"declaration": "CabannesThesis.NonAmbiguous", "line": 11, "source_file": "src/CabannesThesis/Basic.lean"}
```

with

```python
        {
            "declaration": "CabannesThesis.NonAmbiguous",
            "line": 11,
            "signature": None,
            "source_file": "src/CabannesThesis/Basic.lean",
        }
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `.venv/bin/python -m pytest tests/test_search.py -q 2>&1 | tail -15`

Expected: 7 failed, 31 passed. The four new tests and `test_search_writes_nothing_and_starts_no_process` fail
with `TypeError: search_blueprint() got an unexpected keyword argument 'skeleton'` or an `AttributeError` on
`signature` or `skeleton_matches_blueprint`; the two updated expectations fail on the missing keys. If anything
fails at import, the helper is wrong: fix it before going on.

- [ ] **Step 4: Add `SkeletonReport.describes`**

In `autoform_cli/skeleton.py`, inside `class SkeletonReport`, insert directly before
`    def node(self, node_id: str) -> NodeSkeleton | None:`:

```python
    def describes(self, graph: Graph) -> bool:
        """Whether the report was extracted from exactly the articles of ``graph``."""

        return self.blueprint_hash == _blueprint_hash(graph)

```

Do not rename or move `_blueprint_hash` (deviation 2).

- [ ] **Step 5: Implement in `autoform_cli/search.py`**

Imports: add after the `from .runtime import ...` line:

```python
from .skeleton import SkeletonError, SkeletonReport, load_skeleton_report
```

Replace `SearchLeanTarget` so it reads:

```python
@dataclass(frozen=True, slots=True)
class SearchLeanTarget:
    declaration: str
    source_file: str | None
    line: int | None
    #: The elaborated signature a skeleton report records for the declaration.
    signature: str | None = None

    def as_dict(self) -> dict[str, int | str | None]:
        return {
            "declaration": self.declaration,
            "line": self.line,
            "signature": self.signature,
            "source_file": self.source_file,
        }
```

In `SearchResult`, add a last field after `hits: tuple[SearchHit, ...]`:

```python
    #: Whether the skeleton report was extracted from the blueprint as it is now; ``None`` without a report.
    skeleton_matches_blueprint: bool | None = None
```

and in `SearchResult.as_dict`, add after the `"hits": ...` entry:

```python
            "skeleton_matches_blueprint": self.skeleton_matches_blueprint,
```

In `search_blueprint`'s signature, add after `lean_root: str | Path | None = None,`:

```python
    skeleton: str | Path | None = None,
```

Extend its docstring so the last paragraph reads:

```python
    Nothing is written and nothing is kept between calls: each one reads the
    blueprint again, so a hit describes the Markdown as it is now. ``skeleton``
    names a report written by ``autoform skeleton --output``; its signatures
    are attached by declaration name as recorded, and Lean is not run to
    confirm them.
    """
```

Directly after `graph = load_graph(paths.blueprint_dir)` add:

```python
    report = _skeleton_report(skeleton)
    # A signature states a Lean declaration, whichever article names it, so a
    # report outlives edits to the blueprint it was extracted from.
    signatures = {
        declaration.name: declaration.signature
        for node in (report.nodes if report else ())
        for declaration in node.declarations
    }
```

Replace the `lean_targets=` argument of `SearchHit(...)` with:

```python
            lean_targets=tuple(
                _lean_target(target.declaration, lean_index, signatures.get(target.declaration))
                for target in node.lean_targets
            ),
```

In the final `return SearchResult(...)`, add after the `hits=...` argument:

```python
        skeleton_matches_blueprint=report.describes(graph) if report else None,
```

Replace `_lean_target` with the following two functions:

```python
def _skeleton_report(report_path: str | Path | None) -> SkeletonReport | None:
    if report_path is None:
        return None
    path = Path(report_path).expanduser()
    # The report is read whole, so a pipe or a device is never opened.
    if not path.is_file():
        raise SearchError("skeleton report does not exist or is not a regular file")
    try:
        return load_skeleton_report(path)
    except SkeletonError as error:
        raise SearchError("; ".join(error.issues)) from None
    except (RecursionError, ValueError):
        raise SearchError("skeleton report is malformed") from None


def _lean_target(name: str, index: SourceIndex | None, signature: str | None) -> SearchLeanTarget:
    declaration = index.find(name) if index is not None else None
    if declaration is None:
        return SearchLeanTarget(name, None, None, signature)
    return SearchLeanTarget(name, declaration.path.as_posix(), declaration.line, signature)
```

- [ ] **Step 6: Run the tests and watch them pass**

Run: `.venv/bin/python -m pytest tests/test_search.py -q 2>&1 | tail -3`

Expected: `38 passed`.

- [ ] **Step 7: Check that each test catches its fault**

Make each change below, run `.venv/bin/python -m pytest tests/test_search.py -q 2>&1 | tail -6`, confirm the
named failure, and restore the line, with `git diff autoform_cli/search.py` showing the change gone, before the
next one.

| Temporary change in `autoform_cli/search.py` | Expected failures |
|---|---|
| `report.describes(graph) if report else None` → `True if report else None` | `test_a_report_outlives_blueprint_edits_and_says_that_it_no_longer_matches` |
| `signatures.get(target.declaration)` → `signatures.get(node.id)` | the attach, selected-articles and outlives tests |

No commit in this task: the PR is one commit, made in Task 3.

---

### Task 2: The `--skeleton` flag, its output, its warning, and its refusals

**Files:**
- Modify: `autoform_cli/__main__.py` (the `search` subparser, `_search`)
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: `search_blueprint(..., skeleton=...)`, `SearchLeanTarget.signature`,
  `SearchResult.skeleton_matches_blueprint`, the two `SearchError` messages, and the helper `_skeleton_report`
  from Task 1.
- Produces: CLI flag `--skeleton REPORT`; in human output, each signature line printed under its `Lean:` line
  with four spaces of indentation, and one `warning:` line on stderr when the report does not match the
  blueprint.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_search.py`:

```python


def test_search_cli_shows_a_reported_signature_under_its_declaration(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path)
    signature = "Project.separation {s : Set E}\x1b[2J :\n  True"
    report = _skeleton_report(project, {"Project.separation": signature})
    command = ["search", str(project), "separating", "--skeleton", str(report)]

    assert cli.main(command) == 0
    output = capsys.readouterr().out
    assert "\x1b" not in output
    lines = output.splitlines()
    start = lines.index("  Lean: Project.separation")
    assert lines[start + 1 : start + 3] == ["    Project.separation {s : Set E}\\x1b[2J :", "      True"]

    assert cli.main([*command, "--json"]) == 0
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert captured.err == "" and document["skeleton_matches_blueprint"] is True
    assert document["hits"][0]["lean_targets"] == [
        {"declaration": "Project.separation", "line": None, "signature": signature, "source_file": None}
    ]

    _article(project, "convexity/new.md", title="New")
    warning = (
        "warning: the blueprint changed after the skeleton report was extracted; "
        "a declaration named since then has no signature\n"
    )
    for query in ("separating", "nowhere"):
        assert cli.main(["search", str(project), query, "--skeleton", str(report)]) == 0
        assert capsys.readouterr().err == warning
    assert cli.main([*command, "--json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == "" and json.loads(captured.out)["skeleton_matches_blueprint"] is False


def test_search_cli_refuses_a_report_it_cannot_trust(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path)
    good = _skeleton_report(project, {"Project.separation": "Project.separation : True"})
    document = json.loads(good.read_text(encoding="utf-8"))
    bad = tmp_path / "bad.json"

    def refusal(path: Path) -> str:
        for arguments in ([], ["--json"]):
            assert cli.main(["search", str(project), "separating", "--skeleton", str(path), *arguments]) == 2
            captured = capsys.readouterr()
            assert captured.out == ""
        assert captured.err.startswith("error: ") and captured.err.count("\n") == 1
        # A generic path error would send the reader to the blueprint, which is sound.
        assert "project, blueprint" not in captured.err
        return captured.err

    assert refusal(tmp_path / "missing.json") == "error: skeleton report does not exist or is not a regular file\n"
    assert refusal(project) == "error: skeleton report does not exist or is not a regular file\n"

    bad.write_text("not json", encoding="utf-8")
    assert "cannot read skeleton report" in refusal(bad)
    bad.write_bytes(b"\xff\xfe")
    assert "cannot read skeleton report" in refusal(bad)
    bad.write_text("[" * 100_000, encoding="utf-8")
    assert refusal(bad) == "error: skeleton report is malformed\n"
    bad.write_text(json.dumps(document | {"schema": "autoform-skeleton/v0"}), encoding="utf-8")
    assert f"is not an {SKELETON_SCHEMA} report" in refusal(bad)
    document["nodes"][0]["declarations"][0]["name"] = "Project.forged"
    bad.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    assert "untargeted declaration" in refusal(bad)

    bad.write_text(good.read_text(encoding="utf-8"), encoding="utf-8")
    assert cli.main(["search", str(project), "separating", "--skeleton", str(bad)]) == 0
    capsys.readouterr()
```

The last three lines prove the refusals came from the file's content, not from the path `bad.json`. The file
must end with exactly one newline.

- [ ] **Step 2: Run the tests and watch them fail**

Run: `.venv/bin/python -m pytest tests/test_search.py -q -k "search_cli_shows or search_cli_refuses" 2>&1 | tail -8`

Expected: 2 failed, each with `SystemExit: 2` from argparse (`unrecognized arguments: --skeleton`).

- [ ] **Step 3: Add the flag, the output, and the warning**

In `autoform_cli/__main__.py`, directly after
`search.add_argument("--lean-root", type=Path, help="resolve local Lean declaration targets")` add:

```python
    search.add_argument(
        "--skeleton",
        type=Path,
        metavar="REPORT",
        help="attach each Lean target's signature from this report of autoform skeleton --output; Lean is not run",
    )
```

In `_search`, add `skeleton=args.skeleton,` to the `search_blueprint(...)` call, after
`lean_root=args.lean_root,`.

In `_search`, between the `if args.json:` block and `if not result.hits:`, add:

```python
    if result.skeleton_matches_blueprint is False:
        print(
            "warning: the blueprint changed after the skeleton report was extracted; "
            "a declaration named since then has no signature",
            file=sys.stderr,
        )
```

In `_search`'s loop over `hit.lean_targets`, after the line
`print(_human_text(f"  Lean: {target.declaration}{location}"))` add:

```python
            for line in (target.signature or "").splitlines():
                print(_human_text(f"    {line}"))
```

Do not add an `except SkeletonError` clause: `search.py` already turns every report failure into a
`SearchError`, which `_search` prints.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `.venv/bin/python -m pytest tests/test_search.py -q 2>&1 | tail -3`

Expected: `40 passed`.

- [ ] **Step 5: Check that each refusal is pinned**

Make each change, run the same command, confirm `test_search_cli_refuses_a_report_it_cannot_trust` fails, and
restore.

| Temporary change in `autoform_cli/search.py` | Why it must fail |
|---|---|
| `except (RecursionError, ValueError):` → `except (KeyError,):` | the nested-JSON case falls to the generic path message |
| `if not path.is_file():` → `if False:` | the missing and directory cases get the loader's message instead |

---

### Task 3: Document the flag, run every gate, commit

**Files:**
- Modify: `autoform_cli/README.md` (the search examples under "Commands", and "Search contract")

**Interfaces:**
- Consumes: the behavior of Tasks 1 and 2.
- Produces: the commit for PR 4.

- [ ] **Step 1: Add the example**

In `autoform_cli/README.md`, in the fenced block of search examples, add a fourth line after
`autoform search blueprint "interlacing" --state proved --state fully_proved`:

```bash
autoform search . "separating hyperplane" --skeleton skeleton.json --json
```

- [ ] **Step 2: Add the contract paragraph**

In the "Search contract" section, insert this paragraph, followed by a blank line, directly before the
paragraph that begins "Search rereads each article it matches against":

```markdown
`--skeleton REPORT` names a report that `autoform skeleton --output` wrote.
Each Lean target then also carries `signature`, the elaborated signature the
report records for a declaration of that name; it is null without the flag and
for a name the report does not hold, which a `--node` selection, an unresolved
declaration, or a later edit to the blueprint can cause. Search reads the
report and runs neither Lean nor Lake, so a signature is as old as the report:
editing a Lean file does not invalidate it, and it is a reading aid for
deciding reuse, not review evidence. Signatures are matched by name alone, so
pass only a report of this project. `skeleton_matches_blueprint` is true when
the report was extracted from exactly the articles being searched, false when
any article was added, edited, or removed since, and null without the flag;
when it is false the human output warns on standard error and the report is
still used. Search refuses, with exit 2, a report that is missing, is not a
regular file, or is not a canonical report of the schema this version writes.
Reading the report adds to the cost of each call.
```

In the paragraph beginning "`--json` writes `autoform-search/v1`", change the list of top-level keys from

```markdown
`open_statements`, `query`, `terms`, `filters`, `limit`, `total_matches`, and
`hits`, with no timestamp and no path outside the project.
```

to

```markdown
`open_statements`, `query`, `terms`, `filters`, `limit`, `total_matches`,
`skeleton_matches_blueprint`, and `hits`, with no timestamp and no path outside
the project.
```

The first of those two lines begins mid-sentence in the file; match on the text shown and rewrap only those
lines. Change nothing else in the section: the sentence "A Lean target has `declaration`, `source_file` ... and
`line`; the last two are null ..." stays as written and stays true.

- [ ] **Step 3: Confirm the documented behavior by hand**

Run:

```bash
.venv/bin/python -m autoform_cli search skills/setup/assets/cabannes-thesis-project "non-ambiguous" --skeleton /nonexistent.json; echo "exit $?"
.venv/bin/python -m autoform_cli search --help | grep -A2 -- "--skeleton"
```

Expected: `error: skeleton report does not exist or is not a regular file` then `exit 2`; and the help text of
the flag.

- [ ] **Step 4: Run every gate**

```bash
make lint 2>&1 | tail -3
make test 2>&1 | tail -5
make check-example; echo "exit $?"
```

Expected: `All checks passed!`; exactly the two baseline failures named in Global Constraints and no others
(1,984 passed); `exit 0`.

- [ ] **Step 5: Commit**

```bash
git status --short            # only autoform_cli/{README.md,__main__.py,search.py,skeleton.py} and tests/test_search.py
git add autoform_cli/README.md autoform_cli/__main__.py autoform_cli/search.py autoform_cli/skeleton.py tests/test_search.py
git commit -F - <<'EOF'
Show a declaration's signature in search from a skeleton report

A search hit names the Lean declarations of an article but not what they
state, so deciding whether one can be reused meant opening each file.
`autoform search --skeleton REPORT` attaches the elaborated signature an
existing `autoform skeleton --output` report records for each target.

Search still runs neither Lean nor Lake. Signatures are matched by
declaration name, so a report stays useful while articles are added and
edited; `skeleton_matches_blueprint` and a warning say when the report was
extracted from another state of the blueprint. Lean files edited after
the extraction are not detected; the reference says so. A report that is
not the canonical report this version writes is refused.

`signature` is a new key of every Lean target in `autoform-search/v1`,
null when no report is given or the report lacks the declaration.

Part of #143.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
git log --oneline -6
```

Expected: five commits above `cc7e3a8`, the new one on top of `0d566b1`. **Do not push.**

- [ ] **Step 6: Confirm the commit still merges with the open upstream work**

```bash
git fetch upstream --quiet
for ref in upstream/main upstream/pr-172; do
  git merge-tree --write-tree HEAD "$ref" >/dev/null && echo "clean with $ref" || echo "CONFLICT with $ref"
done
```

Expected: `clean with upstream/main` and `clean with upstream/pr-172`. If `upstream/pr-172` is missing, fetch it
with `git fetch upstream pull/172/head:refs/remotes/upstream/pr-172`. A conflict is a finding to report, not to
resolve silently.

---

## Self-review

- **Spec coverage.** Flag and loader, never runs Lean: Tasks 1–2, with the no-process test extended.
  `signature` on every Lean target, `null` otherwise, additive in v1: Task 1. Spec tests: a matching report
  attaches signatures (Task 1); a filtered report yields `null` for unselected articles (Task 1); a malformed
  report exits 2 (Task 2); "a report for another blueprint is refused" is replaced, per deviation 1, by the
  outlives test and the warning test. Docs in "Search contract": Task 3.
- **Not done, on purpose.** No check of signatures against the Lean sources (follow-up); no guard against a
  report of another project beyond the mismatch warning; no cap on signature length in human output; no skill
  changes.
