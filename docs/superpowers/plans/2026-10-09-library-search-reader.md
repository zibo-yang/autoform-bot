# Library Search Reader (issue 203, PR 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `autoform search --library NAME` returns matches from a verified index that a Lake dependency
publishes, and `autoform library list` reports which locked packages have a usable index, both without starting
a process or writing a file.

**Architecture:** A new package `autoform_cli/library/` holds four small modules: the index format and its
digests (`index.py`), finding a locked package's checkout from `lake-manifest.json` (`locate.py`), verifying an
index against that checkout (`verify.py`), and matching declarations (`search.py`), plus the listing
(`listing.py`). `autoform_cli/search.py` changes by one parameter; the blueprint search and its
`autoform-search/v1` output are untouched. `autoform_cli/library/search.py` composes the blueprint result with
the library results into `autoform-search/v2`.

**Tech Stack:** Python 3.10+ (`autoform_cli/`), pytest, ruff (line length 120), Markdown reference
(`autoform_cli/README.md`, wrapped at 80). No new dependency.

**Spec:** `/workspaces/autoform-bot/ISSUE_203_REVISED_BODY.md` (the body of facebookresearch/autoform-bot#203
as revised on 2026-10-09). This plan covers "Delivery" item 1 only: the `v0` index schema,
`autoform library list` and the reader. The generator (item 2) and the skill wording (item 3) get their own
plans.

## Global Constraints

- Work on a new branch `feat/issue-203-library-search` created from `main` at `89dff27`, in a worktree made
  with superpowers:using-git-worktrees. Run every command from that worktree.
- One commit for the whole PR, made in Task 7. Commit after each task while working, then squash.
  **Do not push and do not open or update any pull request.**
- Never `git add` anything under `docs/superpowers/`, and never add `ISSUE_203_REVISED_BODY.md`. Never use
  bare `git stash`.
- `/workspaces` has about 3.9 GB free. Put any scratch data under `/tmp`, never in the repository.
- Search and `autoform library list` start no subprocess, open no socket and write nothing.
- Without `--library`, `autoform search --json` output is byte-identical to `main`, and every existing test in
  `tests/test_search.py` passes unmodified.
- The index schema value is exactly `autoform-library-index/v0`. The default index file name is exactly
  `autoform-library-index.jsonl`. The search schema with `--library` is exactly `autoform-search/v2`.
- Every refusal of a library exits 2 and its message starts with `library NAME:`. A project whose own
  `lake-manifest.json` cannot be used is refused with exit 2 and a message about the project, without that
  prefix.
- Library text (docstrings, module headers, names) is untrusted: human-readable output goes through
  `_human_text`, and the `import` line is built from a validated module name, never copied from the index.
- No skill file changes in this PR. `autoform_cli/README.md` is the only documentation touched, and it must
  call the index format provisional.
- Gates before the final commit: `make lint`, `make test`, `make check-example`.

## Decisions this plan adds to the spec

The spec leaves these open; the plan fixes them so the tasks agree. Each is small and reversible while the
schema is `v0`.

1. **Record discriminator.** Every index line has a `record` key: `"header"`, `"module"` or `"declaration"`.
2. **What a source directory covers.** An entry `X` of `source_dirs` covers the file `X.lean` and every `.lean`
   file under `X/`. A Lake library `MathlibExt` has its root module in `MathlibExt.lean`, beside the directory.
3. **Tree digest framing.** SHA-256 over `autoform-library-tree/v0\0`, then `module\0NAME\0SHA\n` for each
   module in name order, then `file\0NAME\0LENGTH\0BYTES` for each of `lean-toolchain`, `lake-manifest.json`,
   `lakefile.lean`, `lakefile.toml` that exists, in name order, with `\r\n` replaced by `\n` in the bytes.
4. **`module_doc` in a hit** is the module header when it matched and `null` otherwise, so every hit has the
   same keys.
5. **A library named twice** in one call is refused.
6. **A `lakeDir` other than `.lake`** is refused, because the overrides file is read from `.lake`.
7. **`autoform library list` schema** is `autoform-library-list/v1`.

## Review Focus

Inputs the spec implies but does not list, most likely first. Each has a test in the task that owns the code.

1. **`.lake` is a symbolic link** (common when a small volume fills up). The spec refuses a symlinked packages
   directory; the refusal must name the library and say why, and search without `--library` must be
   unaffected. Test in Task 2.
2. **The library name is spelled differently from the manifest** (`my-pkg` against `«my-pkg»`, or wrong case).
   The escaped spelling must match; a wrong name must list the packages that exist. Test in Task 2.
3. **The index starts with a byte-order mark or has CRLF line endings.** CRLF is accepted; a BOM is refused
   with a message that says so, not a JSON traceback. Test in Task 1.
4. **A word that matches thousands of declarations.** `--limit` bounds the hits, `total_matches` counts them
   all, and the call stays within the time bound. Test in Task 5.
5. **An index with modules and no declarations**, or a query no declaration matches. The answer is an empty
   list with `total_matches: 0`, exit 0, not a refusal. Test in Task 5.

## File Structure

| File | Responsibility |
| --- | --- |
| `autoform_cli/library/__init__.py` | Re-exports the public names |
| `autoform_cli/library/index.py` | Record types, parsing an untrusted index, serialising one, module and tree digests |
| `autoform_cli/library/locate.py` | Reading the project's Lake manifest and overrides, finding a package's checkout, resolving `HEAD` from files |
| `autoform_cli/library/verify.py` | Checking an index against its checkout and computing pin differences |
| `autoform_cli/library/listing.py` | `autoform library list` |
| `autoform_cli/library/search.py` | Matching declarations, the `autoform-search/v2` result |
| `autoform_cli/search.py` | `_ranks` takes the field order as a parameter (no behaviour change) |
| `autoform_cli/__main__.py` | `--library` on `search`, the `library list` command, human output |
| `autoform_cli/README.md` | Commands and the two search schemas |
| `tests/library_fixture.py` | Builds a consumer project with a locked, indexed checkout, without Git or Lean |
| `tests/test_library_index.py`, `test_library_locate.py`, `test_library_verify.py`, `test_library_listing.py`, `test_library_search.py` | One test file per module |

---

### Task 1: The index format

**Files:**
- Create: `autoform_cli/library/__init__.py`
- Create: `autoform_cli/library/index.py`
- Test: `tests/test_library_index.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `INDEX_SCHEMA = "autoform-library-index/v0"`, `INDEX_FILE = "autoform-library-index.jsonl"`,
    `MAX_INDEX_BYTES = 64 * 1024 * 1024`, `TREE_FILES = ("lake-manifest.json", "lakefile.lean", "lakefile.toml", "lean-toolchain")`
  - `class LibraryIndexError(ValueError)`
  - `IndexDependency(name: str, type: str, rev: str | None)`
  - `IndexHeader(generator: str, probe: int, package: str, source_dirs: tuple[str, ...], lean_toolchain: str, dependencies: tuple[IndexDependency, ...], tree: str)`
  - `IndexModule(name: str, source_file: str, sha256: str, module_doc: str | None, module_system: bool)`
  - `IndexDeclaration(name: str, module: str, kind: str, status: str, line: int, signature: str, statement: str, docstring: str | None, mentions: tuple[str, ...], auto_named: bool)`
  - `LibraryIndex(header: IndexHeader, modules: tuple[IndexModule, ...], declarations: tuple[IndexDeclaration, ...])`
  - `parse_index(data: bytes) -> LibraryIndex` (raises `LibraryIndexError`)
  - `dump_index(index: LibraryIndex) -> bytes`
  - `module_digest(data: bytes) -> str`
  - `tree_digest(modules: Iterable[tuple[str, str]], files: Iterable[tuple[str, bytes]]) -> str`
  - `relative_path(value: object) -> PurePosixPath | None`
  - `covers(source_dirs: Sequence[str], path: str) -> bool`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_library_index.py`:

```python
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from autoform_cli.library.index import (
    INDEX_SCHEMA,
    IndexDeclaration,
    IndexDependency,
    IndexHeader,
    IndexModule,
    LibraryIndex,
    LibraryIndexError,
    covers,
    dump_index,
    module_digest,
    parse_index,
    relative_path,
    tree_digest,
)

_SHA = "a" * 64


def _index() -> LibraryIndex:
    return LibraryIndex(
        header=IndexHeader(
            generator="0.9.0",
            probe=1,
            package="atlas",
            source_dirs=("Lib",),
            lean_toolchain="leanprover/lean4:v4.34.1",
            dependencies=(IndexDependency("mathlib", "git", "2" * 40),),
            tree=_SHA,
        ),
        modules=(
            IndexModule("Lib.Convex", "Lib/Convex.lean", _SHA, "Convex sets.", True),
            IndexModule("Lib", "Lib.lean", _SHA, None, False),
        ),
        declarations=(
            IndexDeclaration(
                name="Lib.Convex.separation",
                module="Lib.Convex",
                kind="theorem",
                status="complete",
                line=3,
                signature="True",
                statement="theorem separation : True",
                docstring="Two disjoint convex sets are separated.",
                mentions=("True",),
                auto_named=False,
            ),
        ),
    )


def _lines(index: LibraryIndex) -> list[dict]:
    return [json.loads(line) for line in dump_index(index).decode("utf-8").splitlines()]


def _bytes(records: list[dict]) -> bytes:
    return "".join(json.dumps(record) + "\n" for record in records).encode("utf-8")


def test_an_index_survives_a_round_trip_and_is_written_in_one_order() -> None:
    index = _index()
    data = dump_index(index)

    parsed = parse_index(data)

    assert parsed.header == index.header
    assert [module.name for module in parsed.modules] == ["Lib", "Lib.Convex"]
    assert parsed.declarations == index.declarations
    assert dump_index(parsed) == data
    assert data.endswith(b"\n") and b"\r" not in data
    assert [record["record"] for record in _lines(index)] == ["header", "module", "module", "declaration"]
    assert _lines(index)[0]["schema"] == INDEX_SCHEMA
    # Keys are sorted and nothing is escaped, so the bytes do not depend on the writer.
    first = data.split(b"\n", 1)[0].decode("utf-8")
    assert first == json.dumps(json.loads(first), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_crlf_line_endings_are_accepted() -> None:
    data = dump_index(_index()).replace(b"\n", b"\r\n")

    assert parse_index(data) == parse_index(dump_index(_index()))


def test_a_byte_order_mark_is_refused_by_name() -> None:
    with pytest.raises(LibraryIndexError, match="byte-order mark"):
        parse_index(b"\xef\xbb\xbf" + dump_index(_index()))


def test_an_unknown_schema_is_named() -> None:
    records = _lines(_index())
    records[0]["schema"] = "autoform-library-index/v9"

    with pytest.raises(LibraryIndexError, match="unknown index schema autoform-library-index/v9"):
        parse_index(_bytes(records))


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "has no header"),
        (b"\xff\xfe\n", "not valid UTF-8"),
        (dump_index(_index())[:-1], "does not end with a newline"),
        (dump_index(_index()) + b"\n", "empty line"),
        (dump_index(_index()) + b"[1]\n", "line 5 is not a JSON object"),
        (dump_index(_index()) + b'{"record":"header"}\n', "line 5"),
        (b'{"record":"module","record":"module"}\n', "repeats the key record"),
        (b'{"record":"header","probe":NaN}\n', "line 1 is not JSON"),
    ],
)
def test_a_malformed_file_is_refused(data: bytes, message: str) -> None:
    with pytest.raises(LibraryIndexError, match=message):
        parse_index(data)


def test_an_index_over_the_size_limit_is_refused_before_it_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    from autoform_cli.library import index as index_module

    monkeypatch.setattr(index_module, "MAX_INDEX_BYTES", 10)
    with pytest.raises(LibraryIndexError, match="larger than"):
        parse_index(dump_index(_index()))
    monkeypatch.setattr(index_module, "MAX_INDEX_BYTES", 64 * 1024 * 1024)
    monkeypatch.setattr(index_module, "MAX_LINE_BYTES", 10)
    with pytest.raises(LibraryIndexError, match="line 1 is longer than"):
        parse_index(dump_index(_index()))


def _changed(position: int, **changes: object) -> bytes:
    records = _lines(_index())
    records[position].update(changes)
    return _bytes(records)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (_changed(0, probe=True), "header: probe"),
        (_changed(0, source_dirs=[]), "header: source_dirs"),
        (_changed(0, source_dirs=["../Lib"]), "header: source_dirs"),
        (_changed(0, source_dirs=["/Lib"]), "header: source_dirs"),
        (_changed(0, tree="xyz"), "header: tree"),
        (_changed(0, dependencies=[{"name": "mathlib", "type": "git", "rev": None}]), "header: dependencies"),
        (_changed(0, extra=1), "header: unexpected key extra"),
        (_changed(1, sha256="A" * 64), "module Lib: sha256"),
        (_changed(1, name="Lib..X"), "line 2: module name"),
        (_changed(1, source_file="Other/Lib.lean"), "module Lib: source_file"),
        (_changed(1, source_file="Lib/../Lib.lean"), "module Lib: source_file"),
        (_changed(1, source_file="Lib/Convex.lean"), "two modules share the source file Lib/Convex.lean"),
        (_changed(1, name="Lib.Convex"), "two records for module Lib.Convex"),
        (_changed(3, module="Lib.Missing"), "names module Lib.Missing, which has no record"),
        (_changed(3, line=0), "declaration Lib.Convex.separation: line"),
        (_changed(3, line=1.5), "declaration Lib.Convex.separation: line"),
        (_changed(3, kind="axiom"), "declaration Lib.Convex.separation: kind"),
        (_changed(3, status="incomplete"), "declaration Lib.Convex.separation: status"),
        (_changed(3, mentions="True"), "declaration Lib.Convex.separation: mentions"),
        (_changed(3, docstring=7), "declaration Lib.Convex.separation: docstring"),
    ],
)
def test_a_record_outside_the_schema_is_refused(data: bytes, message: str) -> None:
    with pytest.raises(LibraryIndexError, match=message):
        parse_index(data)


def test_a_declaration_is_keyed_by_name_and_module() -> None:
    index = _index()
    twin = replace(index.declarations[0], module="Lib")
    assert len(parse_index(dump_index(replace(index, declarations=(*index.declarations, twin)))).declarations) == 2

    repeated = replace(index, declarations=(*index.declarations, index.declarations[0]))
    with pytest.raises(LibraryIndexError, match="two records for declaration Lib.Convex.separation in Lib.Convex"):
        parse_index(dump_index(repeated))


def test_a_module_digest_ignores_crlf_and_nothing_else() -> None:
    assert module_digest(b"a\r\nb\n") == module_digest(b"a\nb\n")
    assert module_digest(b"a\rb\n") != module_digest(b"a\nb\n")
    assert module_digest(b"\xef\xbb\xbfa\n") != module_digest(b"a\n")


def test_the_tree_digest_covers_every_module_and_pin_file_in_one_order() -> None:
    modules = [("Lib", _SHA), ("Lib.Convex", "b" * 64)]
    files = [("lean-toolchain", b"leanprover/lean4:v4.34.1\n"), ("lake-manifest.json", b"{}\n")]
    digest = tree_digest(modules, files)

    assert digest == tree_digest(reversed(modules), reversed(files))
    assert digest == tree_digest(modules, [(name, data.replace(b"\n", b"\r\n")) for name, data in files])
    assert digest != tree_digest([("Lib", _SHA), ("Lib.Convex", "c" * 64)], files)
    assert digest != tree_digest(modules, [files[0], ("lake-manifest.json", b"{ }\n")])
    assert digest != tree_digest(modules, files[:1])


def test_relative_paths_and_source_directories() -> None:
    assert relative_path("Lib/Convex.lean") is not None
    for unsafe in ("", "/Lib", "Lib/../x", "./Lib", "Lib//x", "Lib\\x", "C:/Lib", "Lib\0", 7, None):
        assert relative_path(unsafe) is None
    assert covers(("Lib",), "Lib.lean") and covers(("Lib",), "Lib/A/B.lean")
    assert not covers(("Lib",), "Library.lean") and not covers(("Lib",), "Other/Lib.lean")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_library_index.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'autoform_cli.library'`.

- [ ] **Step 3: Write the implementation**

Create `autoform_cli/library/__init__.py`:

```python
"""Search of a shared Lean library through the index it publishes."""
```

Create `autoform_cli/library/index.py`:

```python
"""The index a shared Lean library publishes: its records, its bytes, and its digests.

The file is written by another repository, so :func:`parse_index` treats every
byte as untrusted and refuses anything outside the schema.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

#: Provisional until the generator has shown it can produce every field.
INDEX_SCHEMA = "autoform-library-index/v0"
INDEX_FILE = "autoform-library-index.jsonl"
MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
#: The files beside the sources whose bytes decide what the library builds against.
TREE_FILES = ("lake-manifest.json", "lakefile.lean", "lakefile.toml", "lean-toolchain")
#: The keyword a declaration is written with.
KINDS = ("abbrev", "class", "def", "inductive", "instance", "lemma", "opaque", "structure", "theorem")
STATUSES = ("complete", "wanted")
_DEPENDENCY_TYPES = ("git", "path")
_MODULE_COMPONENT = re.compile(r"[A-Za-z_][A-Za-z0-9_'!?]*")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_HEADER_KEYS = frozenset(
    {"record", "schema", "generator", "probe", "package", "source_dirs", "lean_toolchain", "dependencies", "tree"}
)
_MODULE_KEYS = frozenset({"record", "name", "source_file", "sha256", "module_doc", "module_system"})
_DECLARATION_KEYS = frozenset(
    {
        "record", "name", "module", "kind", "status", "line", "signature", "statement", "docstring", "mentions",
        "auto_named",
    }
)


class LibraryIndexError(ValueError):
    """An index file is not one this reader accepts."""


@dataclass(frozen=True, slots=True)
class IndexDependency:
    name: str
    type: str
    rev: str | None


@dataclass(frozen=True, slots=True)
class IndexHeader:
    generator: str
    probe: int
    package: str
    source_dirs: tuple[str, ...]
    lean_toolchain: str
    dependencies: tuple[IndexDependency, ...]
    tree: str

    def as_dict(self) -> dict[str, object]:
        return {
            "record": "header",
            "schema": INDEX_SCHEMA,
            "generator": self.generator,
            "probe": self.probe,
            "package": self.package,
            "source_dirs": list(self.source_dirs),
            "lean_toolchain": self.lean_toolchain,
            "dependencies": [
                {"name": dependency.name, "type": dependency.type, "rev": dependency.rev}
                for dependency in self.dependencies
            ],
            "tree": self.tree,
        }


@dataclass(frozen=True, slots=True)
class IndexModule:
    name: str
    source_file: str
    #: Of the source after each CRLF became LF; see :func:`module_digest`.
    sha256: str
    module_doc: str | None
    #: Whether the file starts with ``module``. A module file cannot import one that does not.
    module_system: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "record": "module",
            "name": self.name,
            "source_file": self.source_file,
            "sha256": self.sha256,
            "module_doc": self.module_doc,
            "module_system": self.module_system,
        }


@dataclass(frozen=True, slots=True)
class IndexDeclaration:
    name: str
    module: str
    kind: str
    status: str
    line: int
    signature: str
    statement: str
    docstring: str | None
    mentions: tuple[str, ...]
    auto_named: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "record": "declaration",
            "name": self.name,
            "module": self.module,
            "kind": self.kind,
            "status": self.status,
            "line": self.line,
            "signature": self.signature,
            "statement": self.statement,
            "docstring": self.docstring,
            "mentions": list(self.mentions),
            "auto_named": self.auto_named,
        }


@dataclass(frozen=True, slots=True)
class LibraryIndex:
    header: IndexHeader
    modules: tuple[IndexModule, ...]
    declarations: tuple[IndexDeclaration, ...]


def dump_index(index: LibraryIndex) -> bytes:
    """Return the one byte string that holds ``index``: the header, then modules, then declarations."""

    records = [
        index.header.as_dict(),
        *(module.as_dict() for module in sorted(index.modules, key=lambda module: module.name)),
        *(
            declaration.as_dict()
            for declaration in sorted(index.declarations, key=lambda item: (item.name, item.module))
        ),
    ]
    return "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for record in records
    ).encode("utf-8")


def module_digest(data: bytes) -> str:
    """SHA-256 of a source file as Git would store it, whatever line endings the checkout has."""

    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def tree_digest(modules: Iterable[tuple[str, str]], files: Iterable[tuple[str, bytes]]) -> str:
    """Digest every module digest and pin file together.

    A declaration's status and printed type can change when another module
    does, so two current indexes can merge, line by line, into a stale one
    whose module digests are all right. Only generation can produce this value.
    """

    digest = hashlib.sha256(b"autoform-library-tree/v0\0")
    for name, sha256 in sorted(modules):
        digest.update(f"module\0{name}\0{sha256}\n".encode("utf-8"))
    for name, data in sorted(files):
        body = data.replace(b"\r\n", b"\n")
        digest.update(f"file\0{name}\0{len(body)}\0".encode("utf-8"))
        digest.update(body)
    return digest.hexdigest()


def relative_path(value: object) -> PurePosixPath | None:
    """Return ``value`` as a path that stays inside the directory it is joined to, or ``None``."""

    if type(value) is not str or not value or any(character in value for character in "\\:\0"):
        return None
    if value.startswith("/") or any(part in ("", ".", "..") for part in value.split("/")):
        return None
    return PurePosixPath(value)


def covers(source_dirs: Sequence[str], path: str) -> bool:
    """Whether ``path`` is a library root file ``X.lean`` or lies under ``X/`` for a source directory ``X``."""

    return any(path == f"{directory}.lean" or path.startswith(f"{directory}/") for directory in source_dirs)


def parse_index(data: bytes) -> LibraryIndex:
    """Decode an untrusted index, refusing whatever the schema does not describe."""

    if len(data) > MAX_INDEX_BYTES:
        raise LibraryIndexError(f"index is larger than {MAX_INDEX_BYTES // (1024 * 1024)} MiB")
    if data.startswith(b"\xef\xbb\xbf"):
        raise LibraryIndexError("index starts with a byte-order mark")
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise LibraryIndexError("index is not valid UTF-8") from None
    if not text:
        raise LibraryIndexError("index has no header")
    if not text.endswith("\n"):
        raise LibraryIndexError("index does not end with a newline; its last record may be cut short")

    header: IndexHeader | None = None
    modules: dict[str, IndexModule] = {}
    source_files: set[str] = set()
    declarations: dict[tuple[str, str], IndexDeclaration] = {}
    for number, line in enumerate(text[:-1].split("\n"), start=1):
        line = line.removesuffix("\r")
        if not line:
            raise LibraryIndexError(f"index line {number} is an empty line")
        if len(line.encode("utf-8")) > MAX_LINE_BYTES:
            raise LibraryIndexError(f"index line {number} is longer than {MAX_LINE_BYTES // 1024} KiB")
        record = _record(line, number)
        kind = record.get("record")
        if number == 1:
            if kind != "header":
                raise LibraryIndexError("index has no header on its first line")
            header = _header(record)
        elif kind == "module":
            module = _module(record, number, header.source_dirs)
            if module.name in modules:
                raise LibraryIndexError(f"index has two records for module {module.name}")
            if module.source_file in source_files:
                raise LibraryIndexError(f"two modules share the source file {module.source_file}")
            modules[module.name] = module
            source_files.add(module.source_file)
        elif kind == "declaration":
            declaration = _declaration(record, number)
            key = (declaration.name, declaration.module)
            if key in declarations:
                raise LibraryIndexError(
                    f"index has two records for declaration {declaration.name} in {declaration.module}"
                )
            declarations[key] = declaration
        else:
            raise LibraryIndexError(f"index line {number} is neither a module nor a declaration record")
    for declaration in declarations.values():
        if declaration.module not in modules:
            raise LibraryIndexError(
                f"declaration {declaration.name} names module {declaration.module}, which has no record"
            )
    return LibraryIndex(
        header=header,
        modules=tuple(modules[name] for name in sorted(modules)),
        declarations=tuple(declarations[key] for key in sorted(declarations)),
    )


def _record(line: str, number: int) -> dict[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        record: dict[str, object] = {}
        for key, value in pairs:
            if key in record:
                raise LibraryIndexError(f"index line {number} repeats the key {key}")
            record[key] = value
        return record

    def constant(_name: str) -> None:
        raise ValueError("constant")

    try:
        record = json.loads(line, object_pairs_hook=unique, parse_constant=constant)
    except LibraryIndexError:
        raise
    except (RecursionError, ValueError):
        raise LibraryIndexError(f"index line {number} is not JSON") from None
    if type(record) is not dict:
        raise LibraryIndexError(f"index line {number} is not a JSON object")
    return record


def _keys(record: dict[str, object], expected: frozenset[str], where: str) -> None:
    for key in sorted(record.keys() - expected):
        raise LibraryIndexError(f"{where}: unexpected key {key}")
    for key in sorted(expected - record.keys()):
        raise LibraryIndexError(f"{where}: {key} is missing")


def _field(record: dict[str, object], key: str, where: str, accepts) -> object:
    value = record[key]
    if not accepts(value):
        raise LibraryIndexError(f"{where}: {key} is not a value this schema allows")
    return value


def _text(value: object) -> bool:
    return type(value) is str


def _name(value: object) -> bool:
    return type(value) is str and bool(value)


def _optional_text(value: object) -> bool:
    return value is None or type(value) is str


def _flag(value: object) -> bool:
    return type(value) is bool


def _module_name(value: object) -> bool:
    return type(value) is str and all(_MODULE_COMPONENT.fullmatch(part) for part in value.split("."))


def _header(record: dict[str, object]) -> IndexHeader:
    # The schema is read first, so a later version is named and not reported key by key.
    schema = record.get("schema")
    if schema != INDEX_SCHEMA:
        raise LibraryIndexError(f"unknown index schema {schema if type(schema) is str else 'value'}")
    where = "index header"
    _keys(record, _HEADER_KEYS, where)

    def source_dirs(value: object) -> bool:
        return (
            type(value) is list
            and bool(value)
            and all(relative_path(item) is not None for item in value)
            and len(set(value)) == len(value)
        )

    def dependencies(value: object) -> bool:
        if type(value) is not list:
            return False
        for item in value:
            if type(item) is not dict or item.keys() != {"name", "type", "rev"} or not _name(item["name"]):
                return False
            if item["type"] not in _DEPENDENCY_TYPES:
                return False
            locked = type(item["rev"]) is str and _OBJECT_ID.fullmatch(item["rev"]) is not None
            if (item["type"] == "git") != locked or (item["type"] == "path" and item["rev"] is not None):
                return False
        return len({item["name"] for item in value}) == len(value)

    return IndexHeader(
        generator=_field(record, "generator", where, _name),
        probe=_field(record, "probe", where, lambda value: type(value) is int and value >= 0),
        package=_field(record, "package", where, _name),
        source_dirs=tuple(_field(record, "source_dirs", where, source_dirs)),
        lean_toolchain=_field(record, "lean_toolchain", where, _name),
        dependencies=tuple(
            IndexDependency(item["name"], item["type"], item["rev"])
            for item in sorted(_field(record, "dependencies", where, dependencies), key=lambda item: item["name"])
        ),
        tree=_field(record, "tree", where, lambda value: type(value) is str and _SHA256.fullmatch(value) is not None),
    )


def _module(record: dict[str, object], number: int, source_dirs: tuple[str, ...]) -> IndexModule:
    if not _module_name(record.get("name")):
        raise LibraryIndexError(f"index line {number}: module name is not a Lean module name")
    where = f"module {record['name']}"
    _keys(record, _MODULE_KEYS, where)

    def source_file(value: object) -> bool:
        return relative_path(value) is not None and value.endswith(".lean") and covers(source_dirs, value)

    return IndexModule(
        name=record["name"],
        source_file=_field(record, "source_file", where, source_file),
        sha256=_field(
            record, "sha256", where, lambda value: type(value) is str and _SHA256.fullmatch(value) is not None
        ),
        module_doc=_field(record, "module_doc", where, _optional_text),
        module_system=_field(record, "module_system", where, _flag),
    )


def _declaration(record: dict[str, object], number: int) -> IndexDeclaration:
    if not _name(record.get("name")):
        raise LibraryIndexError(f"index line {number}: declaration has no name")
    where = f"declaration {record['name']}"
    _keys(record, _DECLARATION_KEYS, where)
    return IndexDeclaration(
        name=record["name"],
        module=_field(record, "module", where, _module_name),
        kind=_field(record, "kind", where, lambda value: type(value) is str and value in KINDS),
        status=_field(record, "status", where, lambda value: type(value) is str and value in STATUSES),
        line=_field(record, "line", where, lambda value: type(value) is int and value >= 1),
        signature=_field(record, "signature", where, _text),
        statement=_field(record, "statement", where, _text),
        docstring=_field(record, "docstring", where, _optional_text),
        mentions=tuple(
            _field(record, "mentions", where, lambda value: type(value) is list and all(map(_name, value)))
        ),
        auto_named=_field(record, "auto_named", where, _flag),
    )


__all__ = [
    "INDEX_FILE",
    "INDEX_SCHEMA",
    "KINDS",
    "MAX_INDEX_BYTES",
    "STATUSES",
    "TREE_FILES",
    "IndexDeclaration",
    "IndexDependency",
    "IndexHeader",
    "IndexModule",
    "LibraryIndex",
    "LibraryIndexError",
    "covers",
    "dump_index",
    "module_digest",
    "parse_index",
    "relative_path",
    "tree_digest",
]
```

`type(True) is int` is false, so `probe=True` and `line=True` are refused without a separate check. A second
header line falls into the last `else` branch, whose message names the line.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_library_index.py -q`
Expected: all pass. Then `uv run ruff check autoform_cli/library tests/test_library_index.py` reports nothing.

- [ ] **Step 5: Commit**

```bash
git add autoform_cli/library/__init__.py autoform_cli/library/index.py tests/test_library_index.py
git commit -m "Add the library index format"
```

---

### Task 2: Finding a locked package's checkout

**Files:**
- Create: `autoform_cli/library/locate.py`
- Create: `tests/library_fixture.py`
- Test: `tests/test_library_locate.py`

**Interfaces:**
- Consumes: `relative_path` from Task 1. From the existing code: `autoform_cli.project._snapshot`
  (`_capture_decision_snapshot`, `_DecisionSnapshot`, `_MANIFEST`, `_OVERRIDES`),
  `autoform_cli.project._lake_metadata` (`_JsonInteger`, `_canonical_toml_name`, `_decode_package_entry`,
  `_json_default`, `_json_optional`, `_manifest_layout`, `_reject_json_constant`, `_validate_manifest_root`),
  `autoform_cli.project.inspect._trim_elan_whitespace`.
- Produces:
  - `class WorkspaceError(ValueError)`: the project's own Lake files cannot be used.
  - `class LibraryError(ValueError)` with attributes `library: str` and `reason: str`; `str(error)` is
    `f"library {library}: {reason}"`.
  - `class HeadError(ValueError)` with attribute `needs_git: bool`.
  - `LockedPackage(name: str, type: str, rev: str | None, sub_dir: str | None, inherited: bool)`
  - `LakeWorkspace(root: Path, lean_toolchain: str | None, packages_dir: str, packages: tuple[LockedPackage, ...], overridden: frozenset[str])`
  - `read_workspace(root: str | Path) -> LakeWorkspace`
  - `locked_packages(snapshot: _DecisionSnapshot, relative: str) -> tuple[dict[str, object], tuple[LockedPackage, ...]] | None`
  - `toolchain(snapshot: _DecisionSnapshot) -> str | None`
  - `find_package(workspace: LakeWorkspace, library: str) -> LockedPackage`
  - `checkout_paths(workspace: LakeWorkspace, package: LockedPackage) -> tuple[Path, Path]` (the Git checkout,
    then the package root)
  - `resolve_head(checkout: Path) -> str`
  - From `tests/library_fixture.py`: `REV`, `MATHLIB_REV`, `entry(...)`, `manifest(...)`.

- [ ] **Step 1: Write the fixture helper**

Create `tests/library_fixture.py` (Task 3 extends it):

```python
"""Build a consumer project with one locked library checkout, without running Git or Lean."""

from __future__ import annotations

import json
from pathlib import Path

REV = "1" * 40
MATHLIB_REV = "2" * 40


def entry(
    name: str,
    rev: str = REV,
    *,
    inherited: bool = False,
    sub_dir: str | None = None,
    path: str | None = None,
) -> dict[str, object]:
    """One package entry as Lake 4.32 to 4.34 writes it (manifest version 1.2.0)."""

    common = {
        "name": name,
        "scope": "",
        "inherited": inherited,
        "configFile": "lakefile.toml",
        "manifestFile": "lake-manifest.json",
    }
    if path is not None:
        return {**common, "type": "path", "dir": path}
    return {
        **common,
        "type": "git",
        "url": f"https://example.invalid/{name}",
        "rev": rev,
        "inputRev": "main",
        "subDir": sub_dir,
    }


def manifest(packages: list[dict[str, object]], *, packages_dir: str | None = ".lake/packages", **root) -> str:
    payload: dict[str, object] = {"version": "1.2.0", "name": "project", "lakeDir": ".lake", "packages": packages}
    if packages_dir is not None:
        payload["packagesDir"] = packages_dir
    payload.update(root)
    return json.dumps(payload, indent=1) + "\n"


def checkout(project: Path, name: str, rev: str = REV, *, packages_dir: str = ".lake/packages") -> Path:
    """Create the directory Lake clones ``name`` into, with ``HEAD`` detached at ``rev``."""

    directory = project / packages_dir / name
    (directory / ".git").mkdir(parents=True)
    (directory / ".git/HEAD").write_text(rev + "\n", encoding="utf-8")
    return directory
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_library_locate.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoform_cli.library.locate import (
    HeadError,
    LibraryError,
    WorkspaceError,
    checkout_paths,
    find_package,
    read_workspace,
    resolve_head,
)
from tests.library_fixture import MATHLIB_REV, REV, checkout, entry, manifest


def _project(tmp_path: Path, packages: list[dict[str, object]], **root: object) -> Path:
    project = tmp_path / "project"
    project.mkdir(parents=True)
    (project / "lean-toolchain").write_text("leanprover/lean4:v4.34.1\n", encoding="utf-8")
    (project / "lake-manifest.json").write_text(manifest(packages, **root), encoding="utf-8")
    return project


def test_a_workspace_lists_its_locked_packages_by_unescaped_name(tmp_path: Path) -> None:
    project = _project(
        tmp_path,
        [entry("atlas"), entry("mathlib", MATHLIB_REV, inherited=True), entry("«my-pkg»"), entry("local", path="../local")],
    )

    workspace = read_workspace(project)

    assert workspace.lean_toolchain == "leanprover/lean4:v4.34.1"
    assert workspace.packages_dir == ".lake/packages"
    assert [(package.name, package.type, package.rev, package.inherited) for package in workspace.packages] == [
        ("atlas", "git", REV, False),
        ("local", "path", None, False),
        ("mathlib", "git", MATHLIB_REV, True),
        ("my-pkg", "git", REV, False),
    ]
    assert workspace.overridden == frozenset()


def test_packages_dir_defaults_and_must_stay_inside_the_project(tmp_path: Path) -> None:
    assert read_workspace(_project(tmp_path, [entry("atlas")], packages_dir=None)).packages_dir == ".lake/packages"
    for index, unsafe in enumerate(("/abs/packages", "../packages", ".lake/../../packages")):
        project = _project(tmp_path / str(index), [entry("atlas")], packages_dir=unsafe)
        with pytest.raises(WorkspaceError, match="packagesDir"):
            read_workspace(project)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (None, "has no lake-manifest.json"),
        ("{", "not a Lake manifest"),
        ('{"version": "1.2.0", "packages": [{"name": "atlas"}]}', "not a Lake manifest"),
        ('{"version": 4, "packages": []}', "not a Lake manifest"),
        (manifest([entry("atlas")], lakeDir="build/.lake"), "lakeDir"),
    ],
)
def test_a_manifest_autoform_cannot_use_is_refused(tmp_path: Path, text: str | None, message: str) -> None:
    project = _project(tmp_path, [])
    if text is None:
        (project / "lake-manifest.json").unlink()
    else:
        (project / "lake-manifest.json").write_text(text, encoding="utf-8")

    with pytest.raises(WorkspaceError, match=message):
        read_workspace(project)


def test_a_library_is_found_by_either_spelling_of_its_name(tmp_path: Path) -> None:
    workspace = read_workspace(_project(tmp_path, [entry("atlas"), entry("«my-pkg»")]))

    assert find_package(workspace, "atlas").name == "atlas"
    assert find_package(workspace, "my-pkg").name == "my-pkg"
    assert find_package(workspace, "«my-pkg»").name == "my-pkg"


def test_a_name_that_is_not_locked_lists_the_packages_that_are(tmp_path: Path) -> None:
    workspace = read_workspace(_project(tmp_path, [entry("atlas"), entry("mathlib", MATHLIB_REV)]))

    with pytest.raises(LibraryError) as refusal:
        find_package(workspace, "Atlas")

    assert refusal.value.library == "Atlas"
    assert str(refusal.value) == (
        "library Atlas: it is not a package in lake-manifest.json; the locked packages are: atlas, mathlib"
    )


def test_a_path_dependency_and_an_overridden_package_are_refused(tmp_path: Path) -> None:
    project = _project(tmp_path, [entry("atlas"), entry("local", path="../local")])
    (project / ".lake").mkdir()
    (project / ".lake/package-overrides.json").write_text(
        json.dumps({"schemaVersion": "1.2.0", "packages": [entry("atlas", path="../other")]}), encoding="utf-8"
    )
    workspace = read_workspace(project)

    assert workspace.overridden == frozenset({"atlas"})
    with pytest.raises(LibraryError, match="library local: it is a path dependency, which has no locked revision"):
        find_package(workspace, "local")
    with pytest.raises(LibraryError, match=r"library atlas: \.lake/package-overrides\.json replaces it"):
        find_package(workspace, "atlas")


def test_the_checkout_is_under_packages_dir_and_the_package_root_adds_sub_dir(tmp_path: Path) -> None:
    project = _project(
        tmp_path, [entry("atlas"), entry("mono", sub_dir="sub/pkg"), entry("«my-pkg»")], packages_dir="deps/pkgs"
    )
    for name in ("atlas", "mono", "my-pkg"):
        checkout(project, name, packages_dir="deps/pkgs")
    (project / "deps/pkgs/mono/sub/pkg").mkdir(parents=True)
    workspace = read_workspace(project)

    assert checkout_paths(workspace, find_package(workspace, "atlas")) == (
        project / "deps/pkgs/atlas",
        project / "deps/pkgs/atlas",
    )
    assert checkout_paths(workspace, find_package(workspace, "mono")) == (
        project / "deps/pkgs/mono",
        project / "deps/pkgs/mono/sub/pkg",
    )
    assert checkout_paths(workspace, find_package(workspace, "my-pkg"))[0] == project / "deps/pkgs/my-pkg"


def test_a_package_that_is_not_checked_out_or_escapes_is_refused(tmp_path: Path) -> None:
    project = _project(tmp_path, [entry("atlas"), entry("mono", sub_dir="../elsewhere"), entry("«a/b»")])
    checkout(project, "mono")
    workspace = read_workspace(project)

    with pytest.raises(LibraryError, match="library atlas: it is not checked out"):
        checkout_paths(workspace, find_package(workspace, "atlas"))
    with pytest.raises(LibraryError, match="library mono: its subDir"):
        checkout_paths(workspace, find_package(workspace, "mono"))
    with pytest.raises(LibraryError, match="library a/b: its name is not a directory name"):
        checkout_paths(workspace, find_package(workspace, "a/b"))


def test_a_checkout_reached_through_a_symbolic_link_is_refused_by_name(tmp_path: Path) -> None:
    # A small volume is often relieved by moving .lake elsewhere and linking it back.
    project = _project(tmp_path, [entry("atlas")])
    elsewhere = tmp_path / "big-disk"
    checkout(elsewhere, "atlas", packages_dir="packages")
    (project / ".lake").symlink_to(elsewhere, target_is_directory=True)
    workspace = read_workspace(project)

    with pytest.raises(LibraryError) as refusal:
        checkout_paths(workspace, find_package(workspace, "atlas"))

    assert str(refusal.value) == "library atlas: its checkout is reached through the symbolic link .lake"


def _git(tmp_path: Path) -> Path:
    directory = tmp_path / "checkout"
    (directory / ".git/refs/heads").mkdir(parents=True)
    return directory


def test_head_is_resolved_from_a_commit_id_a_ref_file_and_a_packed_ref(tmp_path: Path) -> None:
    directory = _git(tmp_path)
    git = directory / ".git"

    (git / "HEAD").write_text(REV + "\n", encoding="utf-8")
    assert resolve_head(directory) == REV

    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs/heads/main").write_text(MATHLIB_REV + "\n", encoding="utf-8")
    assert resolve_head(directory) == MATHLIB_REV

    (git / "refs/heads/main").unlink()
    (git / "packed-refs").write_text(
        f"# pack-refs with: peeled fully-peeled sorted\n{'3' * 40} refs/heads/other\n{REV} refs/heads/main\n^{'4' * 40}\n",
        encoding="utf-8",
    )
    assert resolve_head(directory) == REV


def test_head_is_resolved_through_a_git_file_of_a_linked_worktree(tmp_path: Path) -> None:
    main = _git(tmp_path)
    (main / ".git/refs/heads/topic").write_text(REV + "\n", encoding="utf-8")
    private = main / ".git/worktrees/linked"
    private.mkdir(parents=True)
    (private / "HEAD").write_text("ref: refs/heads/topic\n", encoding="utf-8")
    (private / "commondir").write_text("../..\n", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").write_text(f"gitdir: {private}\n", encoding="utf-8")

    assert resolve_head(linked) == REV


def test_a_head_that_files_cannot_answer_says_why(tmp_path: Path) -> None:
    directory = _git(tmp_path)
    git = directory / ".git"

    with pytest.raises(HeadError, match="no readable Git HEAD"):
        resolve_head(directory)

    (git / "HEAD").write_text("ref: refs/heads/missing\n", encoding="utf-8")
    with pytest.raises(HeadError, match="a ref that does not exist") as missing:
        resolve_head(directory)
    assert not missing.value.needs_git

    (git / "HEAD").write_text("ref: ../../outside\n", encoding="utf-8")
    with pytest.raises(HeadError, match="unsafe ref"):
        resolve_head(directory)

    (git / "HEAD").write_text("ref: refs/heads/.invalid\n", encoding="utf-8")
    (git / "reftable").mkdir()
    with pytest.raises(HeadError, match="cannot be read without Git") as reftable:
        resolve_head(directory)
    assert reftable.value.needs_git

    with pytest.raises(HeadError, match="not a Git checkout"):
        resolve_head(tmp_path)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_library_locate.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'autoform_cli.library.locate'`.

- [ ] **Step 4: Write the implementation**

Create `autoform_cli/library/locate.py`:

```python
"""Find a locked Lake package's checkout by reading files only.

Lake clones a Git dependency into ``<packagesDir>/<name>`` and records the
commit in ``lake-manifest.json``. Nothing here runs Lake or Git, so what they
would report is read from the files they read.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from ..project import _snapshot
from ..project._lake_metadata import (
    _JsonInteger,
    _canonical_toml_name,
    _decode_package_entry,
    _json_default,
    _json_optional,
    _manifest_layout,
    _reject_json_constant,
    _validate_manifest_root,
)
from ..project._snapshot import _DecisionSnapshot, _MANIFEST, _OVERRIDES
from ..project.inspect import _trim_elan_whitespace
from .index import relative_path

_DEFAULT_PACKAGES_DIR = ".lake/packages"
_SNAPSHOT_ATTEMPTS = 3
_OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_REFTABLE = re.compile(r"(?im)^\s*refstorage\s*=\s*reftable\s*$")
_MAX_REF_BYTES = 4096
_MAX_GIT_FILE_BYTES = 16 * 1024 * 1024


class WorkspaceError(ValueError):
    """The project's own Lake files cannot tell where its packages are."""


class LibraryError(ValueError):
    """One named library cannot be searched; the message says which and why."""

    def __init__(self, library: str, reason: str) -> None:
        super().__init__(f"library {library}: {reason}")
        self.library = library
        self.reason = reason


class HeadError(ValueError):
    """A checkout's commit cannot be read from its files."""

    def __init__(self, reason: str, *, needs_git: bool = False) -> None:
        super().__init__(reason)
        self.needs_git = needs_git


@dataclass(frozen=True, slots=True)
class LockedPackage:
    #: As the project's ``require`` names it, without Lean's quoting marks.
    name: str
    type: str
    rev: str | None
    sub_dir: str | None
    inherited: bool


@dataclass(frozen=True, slots=True)
class LakeWorkspace:
    root: Path
    lean_toolchain: str | None
    packages_dir: str
    packages: tuple[LockedPackage, ...]
    #: Packages ``.lake/package-overrides.json`` replaces. The manifest does not record this.
    overridden: frozenset[str]


def read_workspace(root: str | Path) -> LakeWorkspace:
    """Read the files that decide which packages ``root`` builds against, as one generation."""

    directory = Path(root).expanduser().resolve()
    if not directory.is_dir():
        raise WorkspaceError("Lean root does not exist or is not a directory")
    for _attempt in range(_SNAPSHOT_ATTEMPTS):
        snapshot = _snapshot._capture_decision_snapshot(directory)
        if snapshot.stable and snapshot == _snapshot._capture_decision_snapshot(directory):
            return _workspace(directory, snapshot)
    raise WorkspaceError("project configuration changed while it was being read; retry after the project is idle")


def _workspace(root: Path, snapshot: _DecisionSnapshot) -> LakeWorkspace:
    decoded = locked_packages(snapshot, _MANIFEST)
    if decoded is None:
        raise WorkspaceError("the Lean root has no lake-manifest.json; run `lake update` first")
    payload, packages = decoded
    try:
        _validate_manifest_root(payload)
        lake_dir = _json_default(payload, "lakeDir", ".lake", str)
        packages_dir = _json_optional(payload, "packagesDir", str) or _DEFAULT_PACKAGES_DIR
    except ValueError:
        raise WorkspaceError(f"{_MANIFEST} is not a Lake manifest Autoform reads") from None
    if lake_dir not in (".lake", "./.lake"):
        raise WorkspaceError(f"{_MANIFEST} sets lakeDir to {lake_dir!r}; only .lake is supported")
    if relative_path(packages_dir) is None:
        raise WorkspaceError(f"{_MANIFEST} sets packagesDir to {packages_dir!r}, which is not inside the project")
    overrides = locked_packages(snapshot, _OVERRIDES)
    return LakeWorkspace(
        root=root,
        lean_toolchain=toolchain(snapshot),
        packages_dir=packages_dir,
        packages=packages,
        overridden=frozenset(package.name for package in overrides[1]) if overrides is not None else frozenset(),
    )


def locked_packages(
    snapshot: _DecisionSnapshot, relative: str
) -> tuple[dict[str, object], tuple[LockedPackage, ...]] | None:
    """Decode a Lake manifest or package-overrides file from a snapshot, or ``None`` when there is none."""

    file = snapshot.file(relative)
    if file.state == "missing":
        return None
    try:
        if file.state != "regular" or file.content is None:
            raise ValueError(relative)
        payload = json.loads(
            file.content.decode("utf-8"), parse_constant=_reject_json_constant, parse_int=_JsonInteger
        )
        if type(payload) is not dict:
            raise ValueError(relative)
        # A package-overrides file names its version schemaVersion.
        if _manifest_layout(payload.get("version", payload.get("schemaVersion"))) != "current":
            raise ValueError(relative)
        entries = payload.get("packages")
        entries = [] if entries is None else entries
        if type(entries) is not list:
            raise ValueError(relative)
        # Lake inserts entries into a name map in order, so the last duplicate wins.
        packages: dict[str, LockedPackage] = {}
        for item in entries:
            name, lock = _decode_package_entry(item, relative)
            spelled = ".".join(text for _kind, text in name)
            packages[spelled] = LockedPackage(spelled, lock.type, lock.rev, lock.sub_dir, lock.inherited)
    except (AttributeError, RecursionError, UnicodeError, ValueError):
        raise WorkspaceError(f"{relative} is not a Lake manifest Autoform reads") from None
    return payload, tuple(packages[name] for name in sorted(packages))


def toolchain(snapshot: _DecisionSnapshot) -> str | None:
    """Return the toolchain elan reads from ``lean-toolchain``: its trimmed first line."""

    file = snapshot.file("lean-toolchain")
    if file.state != "regular" or file.content is None:
        return None
    try:
        text = file.content.decode("utf-8")
    except UnicodeError:
        return None
    return _trim_elan_whitespace(text.split("\n", 1)[0]) or None


def find_package(workspace: LakeWorkspace, library: str) -> LockedPackage:
    """Return the locked Git package ``library`` names, refusing one whose sources the lock does not fix."""

    wanted = ".".join(text for _kind, text in _canonical_toml_name(library))
    package = next((package for package in workspace.packages if package.name == wanted), None)
    if package is None:
        locked = ", ".join(package.name for package in workspace.packages) or "none"
        raise LibraryError(library, f"it is not a package in {_MANIFEST}; the locked packages are: {locked}")
    if package.name in workspace.overridden:
        raise LibraryError(library, f"{_OVERRIDES} replaces it, so the build does not use the locked checkout")
    if package.type != "git":
        raise LibraryError(library, "it is a path dependency, which has no locked revision")
    return package


def checkout_paths(workspace: LakeWorkspace, package: LockedPackage) -> tuple[Path, Path]:
    """Return a package's Git checkout and its package root, which ``subDir`` may place below it."""

    name = package.name
    if not name or name in (".", "..") or any(character in name for character in "/\\\0"):
        raise LibraryError(name, "its name is not a directory name")
    checkout = _descend(workspace.root, f"{workspace.packages_dir}/{name}", name, "it is not checked out")
    if package.sub_dir in (None, "", ".", "./"):
        return checkout, checkout
    if relative_path(package.sub_dir) is None:
        raise LibraryError(name, f"its subDir {package.sub_dir!r} is not inside the checkout")
    return checkout, _descend(checkout, package.sub_dir, name, f"its subDir {package.sub_dir!r} is missing")


def _descend(base: Path, relative: str, library: str, missing: str) -> Path:
    """Join ``relative`` to ``base`` one component at a time, following no symbolic link."""

    path, walked = base, []
    for part in relative.split("/"):
        path = path / part
        walked.append(part)
        try:
            mode = os.lstat(path).st_mode
        except OSError:
            raise LibraryError(library, missing) from None
        if stat.S_ISLNK(mode):
            raise LibraryError(library, f"its checkout is reached through the symbolic link {'/'.join(walked)}")
        if not stat.S_ISDIR(mode):
            raise LibraryError(library, missing)
    return path


def resolve_head(checkout: Path) -> str:
    """Return the commit ``checkout`` is at, as ``git rev-parse HEAD`` would, by reading files."""

    git = checkout / ".git"
    if git.is_file():
        # A linked worktree or a submodule keeps its Git directory elsewhere.
        pointer = _small(git, _MAX_REF_BYTES) or ""
        if not pointer.startswith("gitdir: "):
            raise HeadError("its .git file names no Git directory")
        git = (checkout / pointer.removeprefix("gitdir: ").strip()).resolve()
    if not git.is_dir():
        raise HeadError("it is not a Git checkout")
    common = git
    shared = _small(git / "commondir", _MAX_REF_BYTES)
    if shared is not None:
        common = (git / shared.strip()).resolve()
    if (common / "reftable").is_dir() or _REFTABLE.search(_small(common / "config", _MAX_GIT_FILE_BYTES) or ""):
        raise HeadError("its HEAD cannot be read without Git (reftable ref storage)", needs_git=True)
    value = _small(git / "HEAD", _MAX_REF_BYTES)
    if value is None:
        raise HeadError("it has no readable Git HEAD")
    value = value.strip()
    # A symbolic ref may name another; Git itself stops after a few.
    for _hop in range(5):
        if _OBJECT_ID.fullmatch(value):
            return value
        if not value.startswith("ref: "):
            raise HeadError("its HEAD is neither a commit nor a ref")
        ref = value.removeprefix("ref: ").strip()
        if relative_path(ref) is None:
            raise HeadError("its HEAD names an unsafe ref")
        loose = _small(common / ref, _MAX_REF_BYTES)
        value = loose.strip() if loose is not None else _packed(common, ref)
    raise HeadError("its HEAD is a chain of symbolic refs")


def _packed(common: Path, ref: str) -> str:
    packed = _small(common / "packed-refs", _MAX_GIT_FILE_BYTES) or ""
    for line in packed.splitlines():
        if line[:1] in ("#", "^"):
            continue
        commit, _space, name = line.partition(" ")
        if name == ref:
            return commit
    raise HeadError("its HEAD names a ref that does not exist")


def _small(path: Path, limit: int) -> str | None:
    """Return a small Git metadata file's text, or ``None`` when there is no such file."""

    try:
        with open(path, "rb") as stream:
            data = stream.read(limit + 1)
    except OSError:
        return None
    if len(data) > limit:
        raise HeadError("its Git metadata is larger than Autoform reads")
    try:
        return data.decode("utf-8")
    except UnicodeError:
        raise HeadError("its Git metadata is not UTF-8") from None


__all__ = [
    "HeadError",
    "LakeWorkspace",
    "LibraryError",
    "LockedPackage",
    "WorkspaceError",
    "checkout_paths",
    "find_package",
    "locked_packages",
    "read_workspace",
    "resolve_head",
    "toolchain",
]
```

Notes for the implementer:

- `_capture_decision_snapshot` reads `lean-toolchain`, `lakefile.lean`, `lakefile.toml`, `lake-manifest.json`
  and `.lake/package-overrides.json`, each bounded at 1 MiB, and reports a file as `missing`, `regular`,
  `unreadable` or `changed`. It follows a symlinked `.lake` when reading the overrides file, as Lake does;
  `_descend` is what refuses a symlink on the way to a checkout.
- In the symlink test `find_package` succeeds and `checkout_paths` refuses, so the message names `.lake`.
- `_canonical_toml_name("«my-pkg»")` and `_canonical_toml_name("my-pkg")` both give `(("str", "my-pkg"),)`.
  If the second does not (the function may fall back to the whole string as one simple name, which is the same
  value), the test still holds; do not special-case it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_library_locate.py -q`
Expected: all pass. Then `uv run ruff check autoform_cli/library tests/library_fixture.py tests/test_library_locate.py`.

- [ ] **Step 6: Commit**

```bash
git add autoform_cli/library/locate.py tests/library_fixture.py tests/test_library_locate.py
git commit -m "Find a locked Lake package's checkout from files"
```

---

### Task 3: Verifying an index against its checkout

**Files:**
- Create: `autoform_cli/library/verify.py`
- Modify: `tests/library_fixture.py` (append)
- Test: `tests/test_library_verify.py`

**Interfaces:**
- Consumes: everything Task 1 and Task 2 produce; `autoform_cli._tree_snapshot`
  (`bind_directory_tree`, `TreeSelection`, `TreeCaptureLimits`, `TreeSnapshotError`);
  `autoform_cli.project.catalog.canonical_lean_toolchain`.
- Produces:
  - `Difference(what: str, name: str | None, library: str | None, project: str | None)` with `as_dict()`;
    `what` is `"lean_toolchain"` or `"dependency"`.
  - `VerifiedLibrary(name: str, revision: str, index: LibraryIndex, differences: tuple[Difference, ...])`
  - `load_library(workspace: LakeWorkspace, library: str, index_path: Path | None = None) -> VerifiedLibrary`
    (raises `LibraryError`)
  - From `tests/library_fixture.py`: `SOURCES`, `declaration(...)`, `build_index(...)`, `write_index(...)`,
    `Library`, `make_library(...)`.

- [ ] **Step 1: Extend the fixture helper**

Append to `tests/library_fixture.py`, and add these imports at its top: `from dataclasses import dataclass`,
and from `autoform_cli.library.index` the names `INDEX_FILE`, `TREE_FILES`, `IndexDeclaration`,
`IndexDependency`, `IndexHeader`, `IndexModule`, `LibraryIndex`, `dump_index`, `module_digest`, `tree_digest`.

```python
SOURCES = {
    "Lib.lean": "import Lib.Convex\n",
    "Lib/Convex.lean": "module\n/-! Convex sets and separation. -/\npublic theorem separation : True := trivial\n",
    "Lib/Classic.lean": "theorem classic : True := trivial\n",
}


def declaration(name: str = "Lib.Convex.separation", *, module: str = "Lib.Convex", **changes) -> IndexDeclaration:
    fields = {
        "kind": "theorem",
        "status": "complete",
        "line": 3,
        "signature": "True",
        "statement": "public theorem separation : True",
        "docstring": "Two disjoint convex sets are separated by a hyperplane.",
        "mentions": ("True",),
        "auto_named": False,
    }
    return IndexDeclaration(name=name, module=module, **{**fields, **changes})


def build_index(
    root: Path,
    declarations: tuple[IndexDeclaration, ...],
    *,
    source_dirs: tuple[str, ...] = ("Lib",),
    module_docs: dict[str, str] | None = None,
) -> LibraryIndex:
    """Index the sources and pin files that are on disk under ``root``, as the generator will."""

    modules = []
    for directory in source_dirs:
        files = sorted((root / directory).rglob("*.lean")) + [root / f"{directory}.lean"]
        for path in files:
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            name = relative.removesuffix(".lean").replace("/", ".")
            data = path.read_bytes()
            modules.append(
                IndexModule(
                    name=name,
                    source_file=relative,
                    sha256=module_digest(data),
                    module_doc=(module_docs or {}).get(name),
                    module_system=data.startswith(b"module"),
                )
            )
    locked = json.loads((root / "lake-manifest.json").read_text(encoding="utf-8"))["packages"]
    header = IndexHeader(
        generator="0.9.0",
        probe=1,
        package="atlas",
        source_dirs=source_dirs,
        lean_toolchain=(root / "lean-toolchain").read_text(encoding="utf-8").split("\n", 1)[0].strip(),
        dependencies=tuple(
            IndexDependency(item["name"], item["type"], item.get("rev")) for item in locked if not item["inherited"]
        ),
        tree=tree_digest(
            ((module.name, module.sha256) for module in modules),
            ((name, (root / name).read_bytes()) for name in TREE_FILES if (root / name).is_file()),
        ),
    )
    return LibraryIndex(header, tuple(modules), declarations)


def write_index(root: Path, index: LibraryIndex) -> None:
    (root / INDEX_FILE).write_bytes(dump_index(index))


@dataclass(frozen=True, slots=True)
class Library:
    project: Path
    checkout: Path
    root: Path
    index: LibraryIndex


def make_library(
    tmp_path: Path,
    *,
    name: str = "atlas",
    sub_dir: str | None = None,
    packages_dir: str = ".lake/packages",
    sources: dict[str, str] | None = None,
    declarations: tuple[IndexDeclaration, ...] | None = None,
    module_docs: dict[str, str] | None = None,
    project_toolchain: str = "leanprover/lean4:v4.34.1",
    project_mathlib: str = MATHLIB_REV,
) -> Library:
    """A project that locks ``name`` at ``REV`` with a current index in its checkout."""

    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    (project / "lean-toolchain").write_text(project_toolchain + "\n", encoding="utf-8")
    (project / "lake-manifest.json").write_text(
        manifest(
            [entry(name, sub_dir=sub_dir), entry("mathlib", project_mathlib, inherited=True)],
            packages_dir=packages_dir,
        ),
        encoding="utf-8",
    )
    directory = checkout(project, name.replace("«", "").replace("»", ""), packages_dir=packages_dir)
    root = directory / sub_dir if sub_dir else directory
    root.mkdir(parents=True, exist_ok=True)
    (root / "lean-toolchain").write_text("leanprover/lean4:v4.34.1\n", encoding="utf-8")
    (root / "lakefile.toml").write_text('name = "atlas"\n', encoding="utf-8")
    (root / "lake-manifest.json").write_text(manifest([entry("mathlib", MATHLIB_REV)]), encoding="utf-8")
    for relative, text in (SOURCES if sources is None else sources).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
    index = build_index(
        root, (declaration(),) if declarations is None else declarations, module_docs=module_docs
    )
    write_index(root, index)
    return Library(project, directory, root, index)
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_library_verify.py`:

```python
from __future__ import annotations

import os
import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from autoform_cli.library.index import INDEX_FILE
from autoform_cli.library.locate import LibraryError, read_workspace
from autoform_cli.library.verify import Difference, load_library
from tests.library_fixture import MATHLIB_REV, REV, build_index, make_library, write_index


def _load(library, name: str = "atlas", index_path: Path | None = None):
    return load_library(read_workspace(library.project), name, index_path)


def _refusal(library, name: str = "atlas", index_path: Path | None = None) -> str:
    with pytest.raises(LibraryError) as refusal:
        _load(library, name, index_path)
    assert refusal.value.library == name
    return refusal.value.reason


def test_a_current_index_is_loaded_with_its_revision(tmp_path: Path) -> None:
    library = make_library(tmp_path)

    verified = _load(library)

    assert (verified.name, verified.revision) == ("atlas", REV)
    assert [item.name for item in verified.index.declarations] == ["Lib.Convex.separation"]
    assert verified.differences == ()


def test_a_package_in_a_sub_directory_or_with_a_quoted_name_is_loaded(tmp_path: Path) -> None:
    assert _load(make_library(tmp_path / "a", sub_dir="sub/pkg", packages_dir="deps/pkgs")).revision == REV
    assert _load(make_library(tmp_path / "b", name="«my-pkg»"), "my-pkg").name == "my-pkg"


def test_a_checkout_with_crlf_line_endings_matches_an_index_made_from_lf(tmp_path: Path) -> None:
    library = make_library(tmp_path)
    for path in [*library.root.rglob("*.lean"), library.root / "lean-toolchain", library.root / "lakefile.toml",
                 library.root / "lake-manifest.json", library.root / INDEX_FILE]:
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    assert _load(library).revision == REV


def test_a_checkout_at_another_revision_or_without_readable_head_is_refused(tmp_path: Path) -> None:
    library = make_library(tmp_path)
    (library.checkout / ".git/HEAD").write_text("3" * 40 + "\n", encoding="utf-8")
    assert _refusal(library) == "its checkout is at 333333333333, not the locked revision 111111111111"

    (library.checkout / ".git/HEAD").write_text("ref: refs/heads/.invalid\n", encoding="utf-8")
    (library.checkout / ".git/reftable").mkdir()
    assert _refusal(library) == "its HEAD cannot be read without Git (reftable ref storage)"


def test_a_missing_symlinked_or_malformed_index_is_refused(tmp_path: Path) -> None:
    library = make_library(tmp_path)
    index = library.root / INDEX_FILE
    data = index.read_bytes()

    index.unlink()
    assert _refusal(library) == f"it has no index ({INDEX_FILE})"

    (tmp_path / "elsewhere.jsonl").write_bytes(data)
    index.symlink_to(tmp_path / "elsewhere.jsonl")
    assert _refusal(library) == "its index is not a regular file"

    index.unlink()
    index.write_bytes(data.replace(b"autoform-library-index/v0", b"autoform-library-index/v9"))
    assert _refusal(library) == "its index is not usable: unknown index schema autoform-library-index/v9"


def test_sources_that_do_not_match_the_index_are_refused_by_name(tmp_path: Path) -> None:
    library = make_library(tmp_path)
    (library.root / "Lib/Convex.lean").write_text("theorem changed : True := trivial\n", encoding="utf-8")
    assert _refusal(library) == "1 source file differs from its index: Lib/Convex.lean"

    library = make_library(tmp_path / "extra")
    (library.root / "Lib/New.lean").write_text("theorem added : True := trivial\n", encoding="utf-8")
    assert _refusal(library) == "1 Lean file is not in its index: Lib/New.lean"

    library = make_library(tmp_path / "missing")
    (library.root / "Lib/Classic.lean").unlink()
    assert _refusal(library) == "1 indexed source file is missing: Lib/Classic.lean"

    library = make_library(tmp_path / "outside")
    (library.root / "Scratch.lean").write_text("-- not under a source directory\n", encoding="utf-8")
    assert _load(library).revision == REV


def test_a_symbolic_link_under_a_source_directory_is_refused(tmp_path: Path) -> None:
    library = make_library(tmp_path)
    (library.root / "Lib/Link.lean").symlink_to("Convex.lean")
    assert _refusal(library) == "a source directory holds the symbolic link Lib/Link.lean"

    library = make_library(tmp_path / "directory")
    (library.root / "Lib/Linked").symlink_to(tmp_path, target_is_directory=True)
    assert _refusal(library) == "a source directory holds the symbolic link Lib/Linked"


def test_an_index_merged_from_two_current_ones_is_refused(tmp_path: Path) -> None:
    # Every module digest is right, and the tree value is one side's.
    library = make_library(tmp_path)
    stale = library.index.header.tree
    (library.root / "Lib/Classic.lean").write_text("theorem classic : True := by sorry\n", encoding="utf-8")
    current = build_index(library.root, library.index.declarations)
    write_index(library.root, replace(current, header=replace(current.header, tree=stale)))

    assert _refusal(library) == (
        "its index does not match its sources and pins as a whole; it was merged or edited, not generated"
    )


def test_a_header_that_disagrees_with_the_checkout_is_refused(tmp_path: Path) -> None:
    library = make_library(tmp_path)
    header = library.index.header
    write_index(library.root, replace(library.index, header=replace(header, lean_toolchain="leanprover/lean4:v4.30.0")))
    assert _refusal(library) == (
        "its index was generated for leanprover/lean4:v4.30.0, but the checkout pins leanprover/lean4:v4.34.1"
    )

    write_index(library.root, replace(library.index, header=replace(header, dependencies=())))
    assert _refusal(library) == "its index does not list the dependencies its lake-manifest.json locks"


def test_pins_that_differ_from_the_project_are_reported_not_refused(tmp_path: Path) -> None:
    library = make_library(tmp_path, project_toolchain="leanprover/lean4:v4.32.2", project_mathlib="5" * 40)

    assert _load(library).differences == (
        Difference("lean_toolchain", None, "leanprover/lean4:v4.34.1", "leanprover/lean4:v4.32.2"),
        Difference("dependency", "mathlib", MATHLIB_REV, "5" * 40),
    )

    alias = make_library(tmp_path / "alias", project_toolchain="v4.34.1")
    assert _load(alias).differences == ()


def test_an_index_given_by_path_is_checked_against_the_checkout(tmp_path: Path) -> None:
    library = make_library(tmp_path)
    published = tmp_path / "asset.jsonl"
    published.write_bytes((library.root / INDEX_FILE).read_bytes())
    (library.root / INDEX_FILE).unlink()

    assert _load(library, index_path=published).revision == REV

    (library.root / "Lib/Convex.lean").write_text("theorem changed : True := trivial\n", encoding="utf-8")
    assert _refusal(library, index_path=published) == "1 source file differs from its index: Lib/Convex.lean"
    assert _refusal(library, index_path=tmp_path / "absent.jsonl") == "it has no index (absent.jsonl)"


def test_loading_starts_no_process_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    library = make_library(tmp_path)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("verification must not start a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    before = {path: path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()}

    _load(library)

    assert {path: path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()} == before


def test_an_index_with_no_declarations_is_usable(tmp_path: Path) -> None:
    assert _load(make_library(tmp_path, declarations=())).index.declarations == ()

```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_library_verify.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'autoform_cli.library.verify'`.

- [ ] **Step 4: Write the implementation**

Create `autoform_cli/library/verify.py`:

```python
"""Check that a library's index describes the checkout the project builds against.

The index comes from another repository. It is used only when the checkout is
at the locked commit, its sources and pin files are the ones the index was
generated from, and the index as a whole is one generation.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .._tree_snapshot import TreeCaptureLimits, TreeSelection, TreeSnapshotError, bind_directory_tree
from ..project import _snapshot
from ..project._snapshot import _MANIFEST
from ..project.catalog import canonical_lean_toolchain
from .index import (
    INDEX_FILE,
    MAX_INDEX_BYTES,
    TREE_FILES,
    LibraryIndex,
    LibraryIndexError,
    covers,
    module_digest,
    parse_index,
    tree_digest,
)
from .locate import (
    HeadError,
    LakeWorkspace,
    LibraryError,
    WorkspaceError,
    checkout_paths,
    find_package,
    locked_packages,
    resolve_head,
    toolchain,
)

#: Far above any library today; a bound so a hostile checkout cannot hold the reader.
_SOURCE_LIMITS = TreeCaptureLimits(max_entries=200_000, max_total_bytes=1024 * 1024 * 1024)
_NAMED = 5


@dataclass(frozen=True, slots=True)
class Difference:
    """One pin the library was indexed with that the project does not share."""

    what: str
    name: str | None
    library: str | None
    project: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {"what": self.what, "name": self.name, "library": self.library, "project": self.project}


@dataclass(frozen=True, slots=True)
class VerifiedLibrary:
    name: str
    revision: str
    index: LibraryIndex
    differences: tuple[Difference, ...]


def load_library(workspace: LakeWorkspace, library: str, index_path: Path | None = None) -> VerifiedLibrary:
    """Return ``library``'s index once every check against its checkout has passed."""

    package = find_package(workspace, library)
    name = package.name

    def refuse(reason: str) -> LibraryError:
        return LibraryError(library, reason)

    try:
        checkout, root = checkout_paths(workspace, package)
    except LibraryError as error:
        raise refuse(error.reason) from None
    try:
        head = resolve_head(checkout)
    except HeadError as error:
        raise refuse(str(error)) from None
    if head.lower() != (package.rev or "").lower():
        raise refuse(f"its checkout is at {head[:12]}, not the locked revision {(package.rev or '')[:12]}")

    path = root / INDEX_FILE if index_path is None else Path(index_path)
    try:
        index = parse_index(_index_bytes(path))
    except FileNotFoundError:
        raise refuse(f"it has no index ({path.name})") from None
    except OSError:
        raise refuse("its index is not a regular file") from None
    except LibraryIndexError as error:
        raise refuse(f"its index is not usable: {error}") from None

    pins = _snapshot._capture_decision_snapshot(root)
    pinned = toolchain(pins)
    if pinned != index.header.lean_toolchain:
        raise refuse(
            f"its index was generated for {index.header.lean_toolchain}, but the checkout pins {pinned or 'nothing'}"
        )
    try:
        decoded = locked_packages(pins, _MANIFEST)
    except WorkspaceError:
        raise refuse(f"its {_MANIFEST} is not a Lake manifest Autoform reads") from None
    direct = sorted(
        (item.name, item.type, item.rev) for item in (decoded[1] if decoded is not None else ()) if not item.inherited
    )
    if direct != [(item.name, item.type, item.rev) for item in index.header.dependencies]:
        raise refuse(f"its index does not list the dependencies its {_MANIFEST} locks")

    found = _sources(root, index.header.source_dirs, refuse)
    expected = {module.source_file: module.sha256 for module in index.modules}
    _same(
        sorted(found.keys() - expected.keys()),
        "Lean file is not in its index",
        "Lean files are not in its index",
        refuse,
    )
    _same(
        sorted(expected.keys() - found.keys()),
        "indexed source file is missing",
        "indexed source files are missing",
        refuse,
    )
    _same(
        sorted(path for path in expected if found[path] != expected[path]),
        "source file differs from its index",
        "source files differ from its index",
        refuse,
    )
    files = [
        (relative, pins.file(relative).content)
        for relative in TREE_FILES
        if pins.file(relative).state == "regular" and pins.file(relative).content is not None
    ]
    if tree_digest(((module.name, module.sha256) for module in index.modules), files) != index.header.tree:
        raise refuse("its index does not match its sources and pins as a whole; it was merged or edited, not generated")
    return VerifiedLibrary(name, head.lower(), index, _differences(workspace, index))


def _index_bytes(path: Path) -> bytes:
    """Read an index that is a regular file, following no symbolic link."""

    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("not a regular file")
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            # One byte over the limit is enough for the parser to refuse by size.
            return stream.read(MAX_INDEX_BYTES + 1)
    finally:
        os.close(descriptor)


def _sources(root: Path, source_dirs: tuple[str, ...], refuse) -> dict[str, str]:
    """Return the digest of every Lean file the source directories hold."""

    def inside(path: PurePosixPath) -> bool:
        return covers(source_dirs, path.as_posix())

    def reaches(path: PurePosixPath) -> bool:
        # A source directory may be nested, so its parents are walked as well.
        text = path.as_posix()
        return any(
            text == directory or text.startswith(f"{directory}/") or directory.startswith(f"{text}/")
            for directory in source_dirs
        )

    selection = TreeSelection(
        # A link under a source directory is captured, whatever it is named, so it can be refused.
        include=lambda path, mode: inside(path) and (path.suffix == ".lean" or stat.S_ISLNK(mode)),
        descend=reaches,
        record_omitted=False,
        limits=_SOURCE_LIMITS,
    )
    try:
        with bind_directory_tree(root, selection=selection) as bound:
            snapshot = bound.capture()
    except TreeSnapshotError as error:
        raise refuse(f"its sources cannot be read safely: {error}") from None
    links = [relative for relative, _target in snapshot.symlinks if inside(PurePosixPath(relative))]
    if links:
        raise refuse(f"a source directory holds the symbolic link {links[0]}")
    return {relative: module_digest(data) for relative, data in snapshot.files if inside(PurePosixPath(relative))}


def _same(paths: list[str], one: str, many: str, refuse) -> None:
    if not paths:
        return
    named = ", ".join(paths[:_NAMED]) + (", ..." if len(paths) > _NAMED else "")
    raise refuse(f"{len(paths)} {one if len(paths) == 1 else many}: {named}")


def _differences(workspace: LakeWorkspace, index: LibraryIndex) -> tuple[Difference, ...]:
    """Where the project's pins differ from the ones the library was indexed with.

    Lake builds a dependency with the project's toolchain and the project's
    own requirement wins over the library's lock, so a difference does not
    mean the library fails to build. It is reported, never refused.
    """

    differences: list[Difference] = []
    theirs, ours = index.header.lean_toolchain, workspace.lean_toolchain
    if ours is None or canonical_lean_toolchain(theirs) != canonical_lean_toolchain(ours):
        differences.append(Difference("lean_toolchain", None, theirs, ours))
    locked = {package.name: package for package in workspace.packages}
    for dependency in index.header.dependencies:
        package = locked.get(dependency.name)
        project = package.rev if package is not None else None
        if package is None or package.type != dependency.type or project != dependency.rev:
            differences.append(Difference("dependency", dependency.name, dependency.rev, project))
    return tuple(differences)


__all__ = ["Difference", "VerifiedLibrary", "load_library"]
```

Notes for the implementer:

- `TreeSelection.include(path, mode)` receives the entry's `st_mode`; `snapshot.symlinks` lists included links
  as `(relative, target)` and `snapshot.files` as `(relative, bytes)`. A link to a directory is reported only
  when `include` accepts its name, which is why `include` accepts any link under a source directory.
- A link named `Lib/Linked` is not a `.lean` file, so `inside()` must be true for it: `covers(("Lib",),
  "Lib/Linked")` is true because it only tests the prefix.
- The singular and plural wording in `_same` must produce exactly the strings the tests assert, for example
  `"1 Lean file is not in its index: Lib/New.lean"`.
- If `os.open` with `O_NOFOLLOW` on a symbolic link raises `OSError` with `ELOOP`, that is the "not a regular
  file" branch. `FileNotFoundError` is a subclass of `OSError`, so it must be caught first, as written.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_library_verify.py tests/test_library_locate.py tests/test_library_index.py -q`
Expected: all pass. Then `uv run ruff check autoform_cli/library tests`.

- [ ] **Step 6: Commit**

```bash
git add autoform_cli/library/verify.py tests/library_fixture.py tests/test_library_verify.py
git commit -m "Verify a library index against its checkout"
```

---

### Task 4: `autoform library list`

**Files:**
- Create: `autoform_cli/library/listing.py`
- Modify: `autoform_cli/__main__.py` (parser near line 240, dispatch near line 343, a new `_library_list`
  function beside `_search`)
- Test: `tests/test_library_listing.py`

**Interfaces:**
- Consumes: `read_workspace`, `checkout_paths`, `LibraryError`, `WorkspaceError` (Task 2); `load_library`
  (Task 3); `INDEX_FILE` (Task 1).
- Produces:
  - `LIBRARY_LIST_SCHEMA = "autoform-library-list/v1"`
  - `ListedPackage(name: str, type: str, revision: str | None, index: bool, usable: bool, reason: str | None)`
  - `LibraryListing(packages: tuple[ListedPackage, ...])` with `as_dict()` and `to_json()`
  - `list_libraries(root: str | Path) -> LibraryListing` (raises `WorkspaceError`)
  - CLI: `autoform library list TARGET [--json]`, exit 0 with the listing, exit 2 when the project's Lake
    files cannot be read.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_library_listing.py`:

```python
from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

from autoform_cli import __main__ as cli
from autoform_cli.library.index import INDEX_FILE
from autoform_cli.library.listing import LIBRARY_LIST_SCHEMA, list_libraries
from tests.library_fixture import MATHLIB_REV, REV, checkout, entry, make_library, manifest


def _with_more_packages(tmp_path: Path):
    library = make_library(tmp_path)
    (library.project / "lake-manifest.json").write_text(
        manifest(
            [
                entry("atlas"),
                entry("mathlib", MATHLIB_REV, inherited=True),
                entry("local", path="../local"),
                entry("absent"),
            ]
        ),
        encoding="utf-8",
    )
    checkout(library.project, "mathlib", MATHLIB_REV)
    return library


def test_each_locked_package_is_listed_with_whether_search_can_use_it(tmp_path: Path) -> None:
    library = _with_more_packages(tmp_path)

    listing = list_libraries(library.project)

    assert [(item.name, item.type, item.revision, item.index, item.usable, item.reason) for item in listing.packages] == [
        ("absent", "git", REV, False, False, "it is not checked out"),
        ("atlas", "git", REV, True, True, None),
        ("local", "path", None, False, False, "it is a path dependency, which has no locked revision"),
        ("mathlib", "git", MATHLIB_REV, False, False, f"it has no index ({INDEX_FILE})"),
    ]


def test_a_package_with_an_index_search_would_refuse_is_not_usable(tmp_path: Path) -> None:
    library = make_library(tmp_path)
    (library.root / "Lib/Convex.lean").write_text("theorem changed : True := trivial\n", encoding="utf-8")

    (atlas,) = [item for item in list_libraries(library.project).packages if item.name == "atlas"]

    assert (atlas.index, atlas.usable) == (True, False)
    assert atlas.reason == "1 source file differs from its index: Lib/Convex.lean"


def test_listing_starts_no_process_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    library = _with_more_packages(tmp_path)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("listing must not start a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    before = {path: path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()}

    list_libraries(library.project)

    assert {path: path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()} == before


def test_library_list_cli_emits_stable_json(tmp_path: Path, capsys) -> None:
    library = _with_more_packages(tmp_path)

    assert cli.main(["library", "list", str(library.project), "--json"]) == 0
    first = capsys.readouterr().out
    assert cli.main(["library", "list", str(library.project), "--json"]) == 0
    assert capsys.readouterr().out == first

    payload = json.loads(first)
    assert payload["schema"] == LIBRARY_LIST_SCHEMA
    assert payload["packages"][1] == {
        "index": True,
        "name": "atlas",
        "reason": None,
        "revision": REV,
        "type": "git",
        "usable": True,
    }
    assert first == json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def test_library_list_cli_prints_one_line_per_package_and_escapes_names(tmp_path: Path, capsys) -> None:
    library = make_library(tmp_path)
    (library.project / "lake-manifest.json").write_text(
        manifest([entry("atlas"), entry("«bad\u001b[31mname»")]), encoding="utf-8"
    )

    assert cli.main(["library", "list", str(library.project)]) == 0
    out = capsys.readouterr().out

    assert "atlas  git 111111111111  usable" in out
    assert "bad\\x1b[31mname  git 111111111111  not usable: it is not checked out" in out
    assert "\u001b" not in out


def test_library_list_cli_reports_an_unreadable_project_with_exit_2(tmp_path: Path, capsys) -> None:
    assert cli.main(["library", "list", str(tmp_path)]) == 2
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == "error: the Lean root has no lake-manifest.json; run `lake update` first\n"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_library_listing.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'autoform_cli.library.listing'`.

- [ ] **Step 3: Write the listing**

Create `autoform_cli/library/listing.py`:

```python
"""Which of a project's locked packages publish an index that search can use."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path

from .index import INDEX_FILE
from .locate import LibraryError, checkout_paths, read_workspace
from .verify import load_library

LIBRARY_LIST_SCHEMA = "autoform-library-list/v1"


@dataclass(frozen=True, slots=True)
class ListedPackage:
    name: str
    type: str
    revision: str | None
    #: Whether the checkout holds an index file at all.
    index: bool
    #: Whether ``autoform search --library`` would accept it. The same checks decide both.
    usable: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class LibraryListing:
    packages: tuple[ListedPackage, ...]

    def as_dict(self) -> dict[str, object]:
        return {"schema": LIBRARY_LIST_SCHEMA, "packages": [asdict(package) for package in self.packages]}

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


def list_libraries(root: str | Path) -> LibraryListing:
    """Report every package ``root`` locks, running for each the checks search runs."""

    workspace = read_workspace(root)
    listed: list[ListedPackage] = []
    for package in workspace.packages:
        reason = None
        try:
            load_library(workspace, package.name)
        except LibraryError as error:
            reason = error.reason
        listed.append(
            ListedPackage(
                name=package.name,
                type=package.type,
                revision=package.rev,
                index=_has_index(workspace, package),
                usable=reason is None,
                reason=reason,
            )
        )
    return LibraryListing(tuple(listed))


def _has_index(workspace, package) -> bool:
    if package.type != "git":
        return False
    try:
        _checkout, root = checkout_paths(workspace, package)
        return stat.S_ISREG(os.lstat(root / INDEX_FILE).st_mode)
    except (LibraryError, OSError):
        return False


__all__ = ["LIBRARY_LIST_SCHEMA", "LibraryListing", "ListedPackage", "list_libraries"]
```

- [ ] **Step 4: Wire the command**

In `autoform_cli/__main__.py`:

Add beside the other imports near line 30:

```python
from .library.listing import list_libraries
from .library.locate import WorkspaceError
```

Add after the `search` parser's last `add_argument` (line 239) and before the `claim` parser:

```python
    library = subparsers.add_parser("library", help="inspect the shared Lean libraries a project depends on")
    library_subparsers = library.add_subparsers(dest="library_command", required=True)
    library_list = library_subparsers.add_parser(
        "list", help="list the locked Lake packages and whether each publishes an index search can use"
    )
    library_list.add_argument("target", type=Path, help="Lean project root, where lake-manifest.json is")
    library_list.add_argument("--json", action="store_true", help="write stable machine-readable output")
```

Add beside the `if args.command == "search":` dispatch (line 343):

```python
    if args.command == "library":
        return _library_list(args)
```

Add after the `_search` function:

```python
def _library_list(args: argparse.Namespace) -> int:
    try:
        listing = list_libraries(args.target)
    except WorkspaceError as error:
        print(f"error: {_human_text(error)}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError):
        print("error: Lean root path cannot be read", file=sys.stderr)
        return 2

    if args.json:
        print(listing.to_json())
        return 0
    if not listing.packages:
        print("No locked packages.")
        return 0
    for package in listing.packages:
        where = package.type if package.revision is None else f"{package.type} {package.revision[:12]}"
        verdict = "usable" if package.usable else f"not usable: {package.reason}"
        print(_human_text(f"{package.name}  {where}  {verdict}"))
    return 0
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_library_listing.py tests/test_cli.py -q`
Expected: all pass. Then `uv run ruff check autoform_cli tests`.

- [ ] **Step 6: Commit**

```bash
git add autoform_cli/library/listing.py autoform_cli/__main__.py tests/test_library_listing.py
git commit -m "Add autoform library list"
```

---

### Task 5: Matching declarations and the v2 result

**Files:**
- Create: `autoform_cli/library/search.py`
- Modify: `autoform_cli/search.py:276-289` (`_ranks` takes the field order)
- Test: `tests/test_library_search.py`

**Interfaces:**
- Consumes: `search_blueprint`, `SearchError`, `SearchResult`, `_lean_name`, `_normalize`, `_ranks`, `_words`
  from `autoform_cli/search.py`; `read_workspace`, `LibraryError` (Task 2); `load_library`, `Difference`
  (Task 3); `IndexDeclaration`, `IndexModule`, `LibraryIndex`, `INDEX_SCHEMA` (Task 1).
- Produces:
  - `SEARCH_LIBRARY_SCHEMA = "autoform-search/v2"`
  - `LIBRARY_FIELDS = ("lean", "docstring", "module_doc", "qualified_names", "mentions", "kind")`
  - `LibraryHit(declaration: IndexDeclaration, source_file: str, module_system: bool, module_doc: str | None, matched_fields: tuple[str, ...])`
    with property `import_line: str | None` and `as_dict()`
  - `LibraryResult(name: str, revision: str, index_schema: str, generator: str, probe: int, differences: tuple[Difference, ...], total_matches: int, hits: tuple[LibraryHit, ...])`
    with `as_dict()`
  - `LibrarySearch(blueprint: SearchResult, libraries: tuple[LibraryResult, ...])` with `as_dict()` and
    `to_json()`
  - `library_argument(value: str) -> tuple[str, Path | None]` (raises `ValueError`)
  - `match_index(index: LibraryIndex, words: tuple[str, ...], terms: tuple[str, ...], limit: int) -> tuple[int, tuple[LibraryHit, ...]]`
  - `search_with_libraries(project_or_blueprint, query, *, lean_root, libraries: Sequence[tuple[str, Path | None]], states=(), declarations=(), limit=20) -> LibrarySearch`
    (raises `SearchError`, `LibraryError`, `WorkspaceError`, and whatever `search_blueprint` raises)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_library_search.py`:

```python
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from autoform_cli.library.index import INDEX_SCHEMA
from autoform_cli.library.locate import LibraryError
from autoform_cli.library.search import (
    LIBRARY_FIELDS,
    SEARCH_LIBRARY_SCHEMA,
    library_argument,
    search_with_libraries,
)
from autoform_cli.search import SEARCH_SCHEMA, SearchError, search_blueprint
from tests.library_fixture import REV, declaration, make_library
from tests.test_search import _project

_DOCS = {"Lib.Convex": "Hahn-Banach separation in locally convex spaces."}


def _library(tmp_path: Path, *declarations, **options):
    # The blueprint and the Lake project share one root, as in a real consumer.
    _project(tmp_path)
    return make_library(tmp_path, declarations=declarations, module_docs=_DOCS, **options)


def _search(library, query: str, *, limit: int = 20, name: str = "atlas", index_path: Path | None = None):
    result = search_with_libraries(
        library.project, query, lean_root=library.project, libraries=[(name, index_path)], limit=limit
    )
    return result.libraries[0]


def _names(library, query: str) -> list[str]:
    return [hit.declaration.name for hit in _search(library, query).hits]


def _matched(library, query: str) -> dict[str, tuple[str, ...]]:
    return {hit.declaration.name: hit.matched_fields for hit in _search(library, query).hits}


def test_a_declaration_is_found_by_its_name_docstring_module_header_or_mentions(tmp_path: Path) -> None:
    library = _library(
        tmp_path,
        declaration("Lib.Convex.choquet_representation", docstring="Every point is a barycentre.",
                    mentions=("Convex", "MeasureTheory.Measure")),
    )

    assert _matched(library, "choquet") == {"Lib.Convex.choquet_representation": ("lean",)}
    assert _matched(library, "barycentre") == {"Lib.Convex.choquet_representation": ("docstring",)}
    assert _matched(library, "banach") == {"Lib.Convex.choquet_representation": ("module_doc",)}
    assert _matched(library, "measuretheory") == {"Lib.Convex.choquet_representation": ("mentions",)}
    assert _matched(library, "Lib.Convex") == {"Lib.Convex.choquet_representation": ("qualified_names",)}
    assert _names(library, "nowhere") == []


def test_every_term_must_occur_and_the_kind_does_not_empty_a_query(tmp_path: Path) -> None:
    library = _library(
        tmp_path,
        declaration(
            "Lib.Convex.choquet_representation", docstring=None, signature="Sentinel", statement="theorem marker"
        ),
    )

    assert _matched(library, "Choquet representation theorem") == {
        "Lib.Convex.choquet_representation": ("lean", "kind")
    }
    assert _names(library, "choquet lemma") == []
    # The signature and the statement are returned and never matched.
    assert _names(library, "sentinel") == []
    assert _names(library, "marker") == []


def test_a_whole_lean_name_matches_as_the_name(tmp_path: Path) -> None:
    library = _library(
        tmp_path,
        declaration("IsCompact.exists_isMinOn", docstring=None),
        declaration("Lib.Convex.cites", docstring="See IsCompact.exists_isMinOn."),
    )

    assert _names(library, "IsCompact.exists_isMinOn") == ["IsCompact.exists_isMinOn", "Lib.Convex.cites"]
    assert _matched(library, "IsCompact.exists_isMinOn")["IsCompact.exists_isMinOn"] == ("lean",)


def test_hits_sort_by_field_then_typed_form_then_status_then_name(tmp_path: Path) -> None:
    library = _library(
        tmp_path,
        declaration("Lib.Convex.b_separation", status="wanted"),
        declaration("Lib.Convex.c_separation"),
        declaration("Lib.Convex.a_separation"),
        declaration("Lib.Convex.z", docstring="A separation result."),
        declaration("Lib.Convex.separated", docstring=None),
    )

    # The name first, complete before wanted; then the docstring; then the
    # module header, which every declaration of the module shares.
    assert _names(library, "separation") == [
        "Lib.Convex.a_separation",
        "Lib.Convex.c_separation",
        "Lib.Convex.b_separation",
        "Lib.Convex.z",
        "Lib.Convex.separated",
    ]
    # "separating" is cut to a stem that "separation" and "separated" contain; no name holds the word as typed.
    assert _names(library, "separating")[-1] == "Lib.Convex.z"
    assert LIBRARY_FIELDS == ("lean", "docstring", "module_doc", "qualified_names", "mentions", "kind")


def test_the_same_name_in_two_modules_is_two_hits(tmp_path: Path) -> None:
    library = _library(
        tmp_path,
        declaration("Lib.wanted_result", module="Lib.Convex", status="wanted", kind="theorem"),
        declaration("Lib.wanted_result", module="Lib.Classic", status="wanted", kind="theorem"),
    )

    assert [(hit.declaration.name, hit.declaration.module) for hit in _search(library, "wanted_result").hits] == [
        ("Lib.wanted_result", "Lib.Classic"),
        ("Lib.wanted_result", "Lib.Convex"),
    ]


def test_a_hit_carries_what_an_agent_needs_to_use_it(tmp_path: Path) -> None:
    library = _library(
        tmp_path,
        declaration("Lib.Convex.separation"),
        declaration("Lib.Classic.classic", module="Lib.Classic", docstring="A classic separation fact."),
        declaration("Lib.Convex.open_separation", status="wanted"),
    )

    hits = {hit.declaration.name: hit.as_dict() for hit in _search(library, "separation").hits}

    assert hits["Lib.Convex.separation"] == {
        "auto_named": False,
        "docstring": "Two disjoint convex sets are separated by a hyperplane.",
        "import": "import Lib.Convex",
        "kind": "theorem",
        "line": 3,
        # One term, so one field: the best one it occurs in.
        "matched_fields": ["lean"],
        "mentions": ["True"],
        "module": "Lib.Convex",
        # The header did not decide this match, so it is not repeated here.
        "module_doc": None,
        "module_system": True,
        "name": "Lib.Convex.separation",
        "signature": "True",
        "source_file": "Lib/Convex.lean",
        "statement": "public theorem separation : True",
        "status": "complete",
    }
    assert hits["Lib.Classic.classic"]["module_system"] is False
    assert hits["Lib.Classic.classic"]["module_doc"] is None
    assert hits["Lib.Classic.classic"]["import"] == "import Lib.Classic"
    assert hits["Lib.Convex.open_separation"]["import"] is None
    by_header = _search(library, "banach").hits[0].as_dict()
    assert by_header["matched_fields"] == ["module_doc"]
    assert by_header["module_doc"] == "Hahn-Banach separation in locally convex spaces."


def test_the_result_is_search_v2_and_its_bytes_are_stable(tmp_path: Path) -> None:
    library = _library(tmp_path, declaration(), project_toolchain="leanprover/lean4:v4.32.2")
    arguments = {"lean_root": library.project, "libraries": [("atlas", None)]}

    result = search_with_libraries(library.project, "separation", **arguments)
    payload = json.loads(result.to_json())

    assert result.to_json() == search_with_libraries(library.project, "separation", **arguments).to_json()
    assert result.to_json() == json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert payload["schema"] == SEARCH_LIBRARY_SCHEMA == "autoform-search/v2"
    blueprint = search_blueprint(library.project, "separation", lean_root=library.project).as_dict()
    assert {key: value for key, value in payload.items() if key not in ("schema", "libraries")} == {
        key: value for key, value in blueprint.items() if key != "schema"
    }
    assert blueprint["schema"] == SEARCH_SCHEMA == "autoform-search/v1"
    (atlas,) = payload["libraries"]
    assert {key: value for key, value in atlas.items() if key != "hits"} == {
        "differences": [
            {
                "library": "leanprover/lean4:v4.34.1",
                "name": None,
                "project": "leanprover/lean4:v4.32.2",
                "what": "lean_toolchain",
            }
        ],
        "generator": "0.9.0",
        "index_schema": INDEX_SCHEMA,
        "name": "atlas",
        "probe": 1,
        "revision": REV,
        "total_matches": 1,
    }
    assert "compatible" not in atlas


def test_the_limit_bounds_each_list_and_the_total_counts_every_match(tmp_path: Path) -> None:
    library = _library(tmp_path, *(declaration(f"Lib.Convex.separation_{number:04d}") for number in range(3000)))

    result = _search(library, "separation", limit=5)

    assert result.total_matches == 3000
    assert [hit.declaration.name for hit in result.hits] == [f"Lib.Convex.separation_{n:04d}" for n in range(5)]


def test_an_index_with_no_declarations_or_no_match_is_an_empty_answer(tmp_path: Path) -> None:
    empty = _library(tmp_path)

    result = _search(empty, "separation")

    assert (result.total_matches, result.hits) == (0, ())


def test_one_refused_library_refuses_the_whole_call(tmp_path: Path) -> None:
    library = _library(tmp_path, declaration())
    (library.root / "Lib/Convex.lean").write_text("theorem changed : True := trivial\n", encoding="utf-8")

    with pytest.raises(LibraryError, match="library atlas: 1 source file differs from its index"):
        search_with_libraries(library.project, "separation", lean_root=library.project, libraries=[("atlas", None)])
    # The blueprint alone is still searchable.
    assert search_blueprint(library.project, "separating").total_matches == 1


def test_a_library_named_twice_or_without_a_lean_root_is_refused(tmp_path: Path) -> None:
    library = _library(tmp_path, declaration())

    with pytest.raises(SearchError, match="library atlas is given twice"):
        search_with_libraries(
            library.project, "separation", lean_root=library.project, libraries=[("atlas", None), ("atlas", None)]
        )
    with pytest.raises(SearchError, match="--library needs --lean-root"):
        search_with_libraries(library.project, "separation", lean_root=None, libraries=[("atlas", None)])


def test_an_index_from_a_path_is_searched(tmp_path: Path) -> None:
    library = _library(tmp_path, declaration())
    published = tmp_path / "asset.jsonl"
    published.write_bytes((library.root / "autoform-library-index.jsonl").read_bytes())
    (library.root / "autoform-library-index.jsonl").unlink()

    assert _search(library, "separation", index_path=published).total_matches == 1


def test_a_library_argument_is_a_name_with_an_optional_index_path() -> None:
    assert library_argument("atlas") == ("atlas", None)
    assert library_argument("atlas=/tmp/index.jsonl") == ("atlas", Path("/tmp/index.jsonl"))
    assert library_argument("atlas=a=b.jsonl") == ("atlas", Path("a=b.jsonl"))
    for malformed in ("", "=index.jsonl", "atlas="):
        with pytest.raises(ValueError):
            library_argument(malformed)


def test_a_library_the_size_of_atlas_is_searched_within_the_bound(tmp_path: Path) -> None:
    # 1,800 modules and 9,000 declarations: an index of about 15 MB, most of it text that is not matched.
    _project(tmp_path)
    sources = {"Lib.lean": "-- root\n"}
    declarations = []
    for module in range(1800):
        sources[f"Lib/M{module:04d}.lean"] = f"theorem t{module} : True := trivial\n" * 20
        for item in range(5):
            declarations.append(
                declaration(
                    f"Lib.M{module:04d}.result_{item}",
                    module=f"Lib.M{module:04d}",
                    docstring="A statement about convex sets and their separation. " * 4,
                    statement="theorem result : " + "(x : Nat) → " * 120 + "True",
                )
            )
    library = make_library(tmp_path, sources=sources, declarations=tuple(declarations))
    assert (library.root / "autoform-library-index.jsonl").stat().st_size > 12 * 1024 * 1024

    started = time.perf_counter()
    result = _search(library, "separation hyperplane", limit=20)
    elapsed = time.perf_counter() - started

    assert result.total_matches == 0
    assert _search(library, "result_3", limit=20).total_matches == 1800
    # Measured at about one second for the library part; the bound leaves room for a loaded CI machine.
    assert elapsed < 15, f"library search took {elapsed:.1f} s"

```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_library_search.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'autoform_cli.library.search'`.

- [ ] **Step 3: Let `_ranks` take the field order**

In `autoform_cli/search.py`, replace the `_ranks` function (lines 276-289) with:

```python
def _ranks(terms: tuple[str, ...], fields: dict[str, str], order: tuple[str, ...] = _FIELDS) -> list[int] | None:
    """Return each term's best field in ``order``, or ``None`` when a term occurs in none."""

    ranks: list[int] = []
    for term in terms:
        rank = next((rank for rank, name in enumerate(order) if term in fields[name]), None)
        # A declaration's whole name, or its last components, names the
        # declaration as its last component does. A namespace alone does not.
        if f".{_lean_name(term)} " in fields["lean_names"]:
            rank = min(order.index("lean"), len(order) if rank is None else rank)
        if rank is None:
            return None
        ranks.append(rank)
    return ranks
```

Run: `uv run pytest tests/test_search.py -q`
Expected: every existing test passes unmodified.

- [ ] **Step 4: Write the library search**

Create `autoform_cli/library/search.py`:

```python
"""Search the declarations of verified library indexes beside one blueprint."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..search import SearchError, SearchResult, _lean_name, _normalize, _ranks, _words, search_blueprint
from .index import INDEX_SCHEMA, IndexDeclaration, LibraryIndex
from .locate import read_workspace
from .verify import Difference, load_library

SEARCH_LIBRARY_SCHEMA = "autoform-search/v2"
#: Indexed fields, best first. ``lean`` is the last component of the name and
#: ``qualified_names`` the name and module in full, as in the blueprint search.
#: ``mentions`` are the constants in the type, so a declaration without a
#: docstring is found by what it is about; ``kind`` is last, so "theorem" in a
#: query does not empty the answer. The signature and statement are returned
#: and not matched: binder words such as ``Type`` occur in nearly all of them.
LIBRARY_FIELDS = ("lean", "docstring", "module_doc", "qualified_names", "mentions", "kind")


@dataclass(frozen=True, slots=True)
class LibraryHit:
    declaration: IndexDeclaration
    source_file: str
    module_system: bool
    #: The module header when it is what matched, so twenty hits do not repeat one header.
    module_doc: str | None
    matched_fields: tuple[str, ...]

    @property
    def import_line(self) -> str | None:
        """The line that makes the declaration available; a wanted result has none."""

        # Built from the module name the index parser validated, never copied from the file.
        return f"import {self.declaration.module}" if self.declaration.status == "complete" else None

    def as_dict(self) -> dict[str, object]:
        declaration = self.declaration
        return {
            "auto_named": declaration.auto_named,
            "docstring": declaration.docstring,
            "import": self.import_line,
            "kind": declaration.kind,
            "line": declaration.line,
            "matched_fields": list(self.matched_fields),
            "mentions": list(declaration.mentions),
            "module": declaration.module,
            "module_doc": self.module_doc,
            "module_system": self.module_system,
            "name": declaration.name,
            "signature": declaration.signature,
            "source_file": self.source_file,
            "statement": declaration.statement,
            "status": declaration.status,
        }


@dataclass(frozen=True, slots=True)
class LibraryResult:
    name: str
    revision: str
    index_schema: str
    generator: str
    probe: int
    differences: tuple[Difference, ...]
    total_matches: int
    hits: tuple[LibraryHit, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "revision": self.revision,
            "index_schema": self.index_schema,
            "generator": self.generator,
            "probe": self.probe,
            "differences": [difference.as_dict() for difference in self.differences],
            "total_matches": self.total_matches,
            "hits": [hit.as_dict() for hit in self.hits],
        }


@dataclass(frozen=True, slots=True)
class LibrarySearch:
    blueprint: SearchResult
    libraries: tuple[LibraryResult, ...]

    def as_dict(self) -> dict[str, object]:
        # Every v1 key keeps its meaning; ``source_revision`` still covers the blueprint only.
        return {
            **self.blueprint.as_dict(),
            "schema": SEARCH_LIBRARY_SCHEMA,
            "libraries": [library.as_dict() for library in self.libraries],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


def library_argument(value: str) -> tuple[str, Path | None]:
    """Split ``NAME`` or ``NAME=PATH`` as ``--library`` takes it."""

    name, separator, path = value.partition("=")
    if not name or (separator and not path):
        raise ValueError("expected NAME or NAME=INDEX_PATH")
    return name, Path(path) if separator else None


def search_with_libraries(
    project_or_blueprint: str | Path,
    query: str,
    *,
    lean_root: str | Path | None,
    libraries: Sequence[tuple[str, Path | None]],
    states: Sequence[str] = (),
    declarations: Sequence[str] = (),
    limit: int = 20,
) -> LibrarySearch:
    """Search the blueprint and each named library, or refuse the whole call.

    One library that cannot be searched refuses everything, the blueprint
    results included: an answer without it would read as "this result is new".
    """

    if lean_root is None:
        raise SearchError("--library needs --lean-root, which names the Lake project that locks the library")
    names = [name for name, _path in libraries]
    for name in names:
        if names.count(name) > 1:
            raise SearchError(f"library {name} is given twice")
    blueprint = search_blueprint(
        project_or_blueprint, query, lean_root=lean_root, states=states, declarations=declarations, limit=limit
    )
    workspace = read_workspace(lean_root)
    words = _words(query)
    results: list[LibraryResult] = []
    for name, index_path in libraries:
        verified = load_library(workspace, name, index_path)
        total, hits = match_index(verified.index, words, blueprint.terms, limit)
        results.append(
            LibraryResult(
                name=name,
                revision=verified.revision,
                index_schema=INDEX_SCHEMA,
                generator=verified.index.header.generator,
                probe=verified.index.header.probe,
                differences=verified.differences,
                total_matches=total,
                hits=hits,
            )
        )
    return LibrarySearch(blueprint, tuple(results))


def match_index(
    index: LibraryIndex, words: tuple[str, ...], terms: tuple[str, ...], limit: int
) -> tuple[int, tuple[LibraryHit, ...]]:
    """Return how many declarations hold every term, and the first ``limit`` of them in order."""

    modules = {module.name: module for module in index.modules}
    # A header is shared by every declaration of its module, so it is folded once.
    headers = {module.name: _normalize(module.module_doc or "") for module in index.modules}
    matches: list[tuple[int, bool, int, bool, str, str, tuple[int, ...]]] = []
    for declaration in index.declarations:
        name = _normalize(declaration.name)
        fields = {
            "lean": _normalize(declaration.name.rpartition(".")[2]),
            "docstring": _normalize(declaration.docstring or ""),
            "module_doc": headers[declaration.module],
            "qualified_names": f"{name}\n{_normalize(declaration.module)}",
            "mentions": _normalize("\n".join(declaration.mentions)),
            "kind": declaration.kind,
            # Not a field of its own: the name between a dot and a space, so a
            # term is looked up as the whole name or as its last components.
            "lean_names": f".{_lean_name(name)} ",
        }
        ranks = _ranks(terms, fields, LIBRARY_FIELDS)
        if ranks is None:
            continue
        matches.append(
            (
                min(ranks),
                _ranks(words, fields, LIBRARY_FIELDS) is None,
                max(ranks),
                declaration.status == "wanted",
                declaration.name,
                declaration.module,
                tuple(sorted(set(ranks))),
            )
        )
    # The best field first, then the words as typed, then the better worst
    # field, then a complete result before a wanted one, then by name.
    matches.sort()
    by_key = {(declaration.name, declaration.module): declaration for declaration in index.declarations}
    hits = []
    for *_order, name, module, ranks in matches[:limit]:
        fields = tuple(LIBRARY_FIELDS[rank] for rank in ranks)
        hits.append(
            LibraryHit(
                declaration=by_key[(name, module)],
                source_file=modules[module].source_file,
                module_system=modules[module].module_system,
                module_doc=modules[module].module_doc if "module_doc" in fields else None,
                matched_fields=fields,
            )
        )
    return len(matches), tuple(hits)


__all__ = [
    "LIBRARY_FIELDS",
    "SEARCH_LIBRARY_SCHEMA",
    "LibraryHit",
    "LibraryResult",
    "LibrarySearch",
    "library_argument",
    "match_index",
    "search_with_libraries",
]
```

Notes for the implementer:

- `for *_order, name, module, ranks in matches[:limit]` unpacks the last three of the seven tuple items.
- `tests/test_search.py::_project` writes its blueprint under `tmp_path / "project"`, the directory
  `make_library` also uses, so the two fixtures compose without change. If `_project` fails because the
  directory exists, call `_project` first, as `_library` does.
- If the sort-order test fails on the "separating" line, check what `_stem("separating")` returns in a Python
  shell before changing the code: the assertion only says the docstring hit sorts last, which holds for any
  stem that both names contain.
- The 3,000-declaration and 9,000-declaration tests build real files; they take a few seconds each. Do not
  mark them slow or skip them.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_library_search.py tests/test_search.py -q`
Expected: all pass. Then `uv run ruff check autoform_cli tests`.

- [ ] **Step 6: Commit**

```bash
git add autoform_cli/search.py autoform_cli/library/search.py tests/test_library_search.py
git commit -m "Match library declarations and compose the v2 search result"
```

---

### Task 6: `autoform search --library` and the reference

**Files:**
- Modify: `autoform_cli/__main__.py` (the `search` parser near line 239 and `_search` at lines 699-749)
- Modify: `autoform_cli/library/__init__.py`
- Modify: `autoform_cli/README.md` (command examples near line 711 and "Search contract" at line 892)
- Test: `tests/test_library_search.py` (append the CLI tests)

**Interfaces:**
- Consumes: `library_argument`, `search_with_libraries`, `LibrarySearch`, `LibraryResult` (Task 5);
  `LibraryError`, `WorkspaceError` (Task 2).
- Produces: `autoform search TARGET QUERY --lean-root ROOT --library NAME[=INDEX_PATH] [--json]`.

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/test_library_search.py` (add `from autoform_cli import __main__ as cli` to its imports):

```python
def _cli(library, *arguments: str) -> list[str]:
    return ["search", str(library.project), *arguments, "--lean-root", str(library.project)]


def test_search_cli_without_library_is_unchanged_by_this_feature(tmp_path: Path, capsys) -> None:
    library = _library(tmp_path, declaration())

    assert cli.main([*_cli(library, "separating"), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema"] == "autoform-search/v1"
    assert "libraries" not in payload


def test_search_cli_emits_v2_json_with_a_library(tmp_path: Path, capsys) -> None:
    library = _library(tmp_path, declaration())

    assert cli.main([*_cli(library, "separation"), "--library", "atlas", "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert out == json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    assert payload["schema"] == "autoform-search/v2"
    assert [hit["name"] for hit in payload["libraries"][0]["hits"]] == ["Lib.Convex.separation"]
    assert payload["libraries"][0]["hits"][0]["import"] == "import Lib.Convex"


def test_search_cli_prints_library_hits_after_the_blueprint_hits(tmp_path: Path, capsys) -> None:
    library = _library(
        tmp_path,
        declaration(),
        declaration("Lib.Convex.open_separation", status="wanted", docstring=None),
        project_toolchain="leanprover/lean4:v4.32.2",
    )

    assert cli.main([*_cli(library, "separation"), "--library", "atlas"]) == 0
    out = capsys.readouterr().out

    assert out.index("Separating hyperplane (convexity/hyperplane)") < out.index("Library atlas @ 111111111111")
    assert "1 of 1 matching article(s) shown.\n" in out
    assert (
        "Library atlas @ 111111111111\n"
        "  differs: lean_toolchain leanprover/lean4:v4.34.1 (project: leanprover/lean4:v4.32.2)\n"
        "Lib.Convex.separation (theorem, complete)\n"
        "  Lib/Convex.lean:3\n"
        "  import Lib.Convex\n"
        "  Signature: True\n"
        "  Docstring: Two disjoint convex sets are separated by a hyperplane.\n"
        "  Matched: lean\n"
        "Lib.Convex.open_separation (theorem, wanted)\n"
        "  Lib/Convex.lean:3\n"
        "  Signature: True\n"
        "  Matched: lean\n"
        "2 of 2 matching declaration(s) shown.\n"
    ) in out


def test_search_cli_says_when_neither_list_has_a_match(tmp_path: Path, capsys) -> None:
    library = _library(tmp_path, declaration())

    assert cli.main([*_cli(library, "nowhere"), "--library", "atlas"]) == 0

    assert capsys.readouterr().out == (
        "No matching articles.\nLibrary atlas @ 111111111111\nNo matching declarations.\n"
    )


def test_search_cli_escapes_library_text(tmp_path: Path, capsys) -> None:
    library = _library(
        tmp_path, declaration(docstring="separation \u001b[31mIGNORE PREVIOUS\nerror: forged", signature="A\u0007B")
    )

    assert cli.main([*_cli(library, "separation"), "--library", "atlas"]) == 0
    out = capsys.readouterr().out

    assert "\u001b" not in out and "\u0007" not in out
    assert "\nerror: forged" not in out
    assert "Docstring: separation \\x1b[31mIGNORE PREVIOUS\\nerror: forged" in out


def test_search_cli_refuses_a_library_it_cannot_verify_and_prints_no_blueprint_hits(tmp_path: Path, capsys) -> None:
    library = _library(tmp_path, declaration())
    (library.root / "Lib/Convex.lean").write_text("theorem changed : True := trivial\n", encoding="utf-8")

    assert cli.main([*_cli(library, "separating"), "--library", "atlas", "--json"]) == 2
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == "error: library atlas: 1 source file differs from its index: Lib/Convex.lean\n"


def test_search_cli_refuses_library_without_lean_root_or_with_a_malformed_argument(tmp_path: Path, capsys) -> None:
    library = _library(tmp_path, declaration())

    assert cli.main(["search", str(library.project), "separation", "--library", "atlas"]) == 2
    assert capsys.readouterr().err == (
        "error: --library needs --lean-root, which names the Lake project that locks the library\n"
    )
    with pytest.raises(SystemExit) as stopped:
        cli.main([*_cli(library, "separation"), "--library", "atlas="])
    assert stopped.value.code == 2


def test_search_cli_reports_a_project_without_a_manifest(tmp_path: Path, capsys) -> None:
    library = _library(tmp_path, declaration())
    (library.project / "lake-manifest.json").unlink()

    assert cli.main([*_cli(library, "separation"), "--library", "atlas"]) == 2
    assert capsys.readouterr().err == "error: the Lean root has no lake-manifest.json; run `lake update` first\n"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_library_search.py -q -k cli`
Expected: FAIL, `error: unrecognized arguments: --library atlas`.

- [ ] **Step 3: Add the option**

In `autoform_cli/__main__.py`, extend the imports added in Task 4 to:

```python
from .library.listing import list_libraries
from .library.locate import LibraryError, WorkspaceError
from .library.search import LibraryResult, library_argument, search_with_libraries
```

Add after the `--limit` argument of the `search` parser (line 238), before `--json`:

```python
    search.add_argument(
        "--library",
        action="append",
        default=[],
        dest="libraries",
        type=_library_argument,
        metavar="NAME[=INDEX]",
        help="also search the index a locked Lake package publishes (repeatable); needs --lean-root. "
        "INDEX reads the index from a file instead of the package's checkout",
    )
```

Add near `_human_text`:

```python
def _library_argument(value: str):
    try:
        return library_argument(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None
```

- [ ] **Step 4: Rewrite `_search`**

Replace the whole `_search` function (lines 699-749) with:

```python
def _search(args: argparse.Namespace) -> int:
    # Only reading the blueprint and the libraries can fail on the project's
    # paths; printing the result stays outside, so an output error is not
    # reported as one.
    options = {
        "lean_root": args.lean_root,
        "states": args.states,
        "declarations": args.declarations,
        "limit": args.limit,
    }
    libraries: tuple[LibraryResult, ...] = ()
    try:
        if args.libraries:
            # A library that cannot be verified refuses the whole call: the
            # blueprint hits alone would read as "this result is new".
            combined = search_with_libraries(args.target, args.query, libraries=args.libraries, **options)
            result, libraries = combined.blueprint, combined.libraries
        else:
            combined = None
            result = search_blueprint(args.target, args.query, **options)
    except (GraphValidationError, RuntimeProjectionError) as error:
        for issue in error.issues:
            print(f"error: {_human_text(issue)}", file=sys.stderr)
        return 2
    except (SearchError, LibraryError, WorkspaceError) as error:
        print(f"error: {_human_text(error)}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError):
        print("error: project, blueprint, or Lean root path cannot be read", file=sys.stderr)
        return 2

    if args.json:
        print(result.to_json() if combined is None else combined.to_json())
        return 0
    if not result.hits:
        print("No matching articles.")
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
    if result.hits:
        print(f"{len(result.hits)} of {result.total_matches} matching article(s) shown.")
    for library in libraries:
        _print_library(library)
    return 0


def _print_library(library: LibraryResult) -> None:
    print(_human_text(f"Library {library.name} @ {library.revision[:12]}"))
    for difference in library.differences:
        what = difference.what if difference.name is None else difference.name
        print(_human_text(f"  differs: {what} {difference.library} (project: {difference.project})"))
    if not library.hits:
        print("No matching declarations.")
        return
    for hit in library.hits:
        declaration = hit.declaration
        print(_human_text(f"{declaration.name} ({declaration.kind}, {declaration.status})"))
        print(_human_text(f"  {hit.source_file}:{declaration.line}"))
        if hit.import_line is not None:
            print(_human_text(f"  {hit.import_line}"))
        print(_human_text(f"  Signature: {_one_line(declaration.signature)}"))
        if declaration.docstring:
            print(_human_text(f"  Docstring: {_one_line(declaration.docstring)}"))
        print("  Matched: " + ", ".join(hit.matched_fields))
    print(f"{len(library.hits)} of {library.total_matches} matching declaration(s) shown.")


def _one_line(text: str) -> str:
    """Cut library text to what fits one report line; the JSON output carries it whole."""

    return text if len(text) <= 200 else text[:197].rstrip() + "..."
```

The existing behaviour without `--library` must not change by a byte: "No matching articles." is still the
only line when there are no hits, and the count line is still printed when there are. The dependency
difference line reads `differs: mathlib <library rev> (project: <project rev>)`.

`_human_text` turns the newline inside a docstring into the two characters `\n`, which is what the escaping
test asserts; do not replace newlines yourself.

- [ ] **Step 5: Re-export the public names**

Replace `autoform_cli/library/__init__.py` with:

```python
"""Search of a shared Lean library through the index it publishes."""

from .index import INDEX_FILE, INDEX_SCHEMA, LibraryIndex, LibraryIndexError, dump_index, parse_index
from .listing import LIBRARY_LIST_SCHEMA, LibraryListing, list_libraries
from .locate import LibraryError, WorkspaceError
from .search import SEARCH_LIBRARY_SCHEMA, LibrarySearch, search_with_libraries
from .verify import VerifiedLibrary, load_library

__all__ = [
    "INDEX_FILE",
    "INDEX_SCHEMA",
    "LIBRARY_LIST_SCHEMA",
    "SEARCH_LIBRARY_SCHEMA",
    "LibraryError",
    "LibraryIndex",
    "LibraryIndexError",
    "LibraryListing",
    "LibrarySearch",
    "VerifiedLibrary",
    "WorkspaceError",
    "dump_index",
    "list_libraries",
    "load_library",
    "parse_index",
    "search_with_libraries",
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_library_search.py tests/test_library_listing.py tests/test_search.py tests/test_cli.py -q`
Expected: all pass, with `tests/test_search.py` unmodified (`git diff --stat main -- tests/test_search.py`
prints nothing).

- [ ] **Step 7: Update the reference**

In `autoform_cli/README.md`:

(a) After the three `autoform search` example lines near line 711, add inside the same code block:

```bash
autoform search . "separating hyperplane" --lean-root . --library atlas
autoform library list .
```

(b) In "Search contract" (line 892), change the first sentence from

```
`autoform search` is a read-only projection of Markdown: it writes nothing,
keeps no index, and starts no process.
```

to

```
`autoform search` is a read-only projection of Markdown: it writes nothing,
builds no index, and starts no process.
```

(c) At the end of the "Search contract" section, before the next `## ` heading, add:

```markdown
### Searching a library the project depends on

`--library NAME` (repeatable) also searches the index a locked Lake package
publishes, and needs `--lean-root`, which names the Lake project.
`autoform library list ROOT` reports each package in `lake-manifest.json`
with its type, locked revision, whether its checkout holds an index, and
whether search would accept it; `--json` emits `autoform-library-list/v1`.
Neither command starts a process or writes a file.

The index is the file `autoform-library-index.jsonl` at the package root, or
the file given as `--library NAME=PATH`. Its format,
`autoform-library-index/v0`, is provisional: no generator ships yet and the
format may change without notice.

Before an index is used, search checks by reading files that the checkout is
at the locked revision, that the index's toolchain and direct dependencies are
the ones the checkout pins, that the Lean files under the indexed directories
are exactly the indexed modules with the recorded digests, and that the index
as a whole is one generation. A package that is not locked, not checked out, a
path dependency, replaced by `.lake/package-overrides.json`, without an index,
or failing a check is refused with exit 2 and a message that begins
`library NAME:`. One refused library refuses the whole call, blueprint hits
included, since a partial answer would read as "this result is new". A
package replaced with `lake --packages=` and an edit to a declaration record
inside the index file are not detected.

A declaration matches when every term occurs in its last name component
(`lean`), docstring, module header (`module_doc`), full name or module
(`qualified_names`), the constants in its type (`mentions`), or its keyword
(`kind`), ranked in that order. Hits sort by best field, then the words as
typed before a stem, then worst field, then `complete` before `wanted`, then
name. `--state` and `--declaration` apply to articles only; `--limit` applies
to each list.

With `--library` the JSON schema is `autoform-search/v2`: every
`autoform-search/v1` key keeps its meaning, and `libraries` lists, in the
order given, `name`, `revision`, `index_schema`, `generator`, `probe`,
`differences`, `total_matches`, and `hits`. A hit carries the declaration's
`name`, `kind`, `status`, `module`, `source_file`, `line`, `signature`,
`statement`, `docstring`, `mentions`, `auto_named`, `module_system`,
`matched_fields`, `module_doc` (the module header when it matched, otherwise
`null`), and `import`, the line that makes a `complete` declaration available
(`null` for a `wanted` one, which carries no proof). `module_system: false`
marks a file a Lean module file cannot import. `differences` lists the
library's toolchain and each direct dependency whose locked revision is not
the project's; it does not say the library fails to build. Without
`--library` the output stays `autoform-search/v1`, byte for byte.
```

- [ ] **Step 8: Commit**

```bash
git add autoform_cli/__main__.py autoform_cli/library/__init__.py autoform_cli/README.md tests/test_library_search.py
git commit -m "Add autoform search --library"
```

---

### Task 7: Gates, the byte-identity check, and the single commit

**Files:**
- No new files.

- [ ] **Step 1: Run the full gates**

```bash
make lint
make test
make check-example
```

Expected: `ruff` reports nothing; pytest ends with no failures (Lean-dependent tests may skip when `lake` is
not on `PATH`; run `export PATH="$HOME/.elan/bin:$PATH"` first to include them); the example validates and its
site builds. `make check-example` needs the example's Mathlib cache, which is present on this machine.

If a test outside the five new files fails, read it before changing anything: `tests/test_cli.py` and
`tests/test_skill_examples.py` assert on the README and on the command list. Fix the cause in the new code or
the README text; do not edit an existing assertion to make it pass without saying so in the report.

- [ ] **Step 2: Prove the output without `--library` is byte-identical to `main`**

```bash
EXAMPLE=skills/setup/assets/cabannes-thesis-project
uv run autoform search $EXAMPLE "interlacing" --lean-root $EXAMPLE --json > /tmp/search-branch.json
git stash list   # must print nothing; do not stash
git worktree add /tmp/autoform-main-203 89dff27
(cd /tmp/autoform-main-203 && uv run --project . autoform search \
    /workspaces/autoform-bot/$EXAMPLE "interlacing" \
    --lean-root /workspaces/autoform-bot/$EXAMPLE --json) > /tmp/search-main.json
cmp /tmp/search-main.json /tmp/search-branch.json && echo IDENTICAL
git worktree remove /tmp/autoform-main-203
```

Expected: `IDENTICAL`. Adjust the example path to the worktree you are in; both runs must read the same
example directory. If `uv run --project .` tries to build a second virtual environment under `/workspaces`,
set `UV_PROJECT_ENVIRONMENT=/tmp/autoform-main-203-venv` for that command.

- [ ] **Step 3: Check the acceptance criteria of the spec's "Reader" list against the tests**

Open `ISSUE_203_REVISED_BODY.md`, section "Acceptance criteria", list "Reader". For each line, name the test
that covers it. Every line must map to a test in `tests/test_library_*.py` except the two noted below. If one
does not, add the test to the file that owns the code and make it pass before continuing.

Two criteria are met differently, and the report to the user must say so:
- "A `packagesDir` that is absolute or contains `..` is refused" is a `WorkspaceError` (the project's own
  manifest is unusable), so its message does not begin `library NAME:`.
- "`autoform library list` ... agrees with the reader on every refusal case" holds by construction:
  `list_libraries` calls `load_library`.

- [ ] **Step 4: Squash to one commit**

```bash
git status --short            # only the files this plan names; nothing under docs/superpowers
git reset --soft 89dff27
git commit -m "$(cat <<'EOF'
Search a locked Lean library from `autoform search`

`autoform search --library NAME` also searches the index a locked Lake
package publishes, and `autoform library list` reports which packages
have one search can use. Both read files only.

An index is used only when the checkout is at the locked revision, its
sources and pin files are the ones the index records, and the index is
one generation. One refused library refuses the whole call. With
`--library` the JSON schema is autoform-search/v2; without it the
output is unchanged.

The index format, autoform-library-index/v0, is provisional until the
generator lands.

Part of #203.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
git log --oneline 89dff27..HEAD   # exactly one commit
make lint && make test
```

Expected: one commit on `feat/issue-203-library-search`, gates green. **Do not push. Do not open a pull
request.** Report the commit hash, the test counts, the `IDENTICAL` result, and the two acceptance-criteria
notes from Step 3.
