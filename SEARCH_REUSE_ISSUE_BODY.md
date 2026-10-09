## Problem

An agent working in an Autoform project has no way to ask "does this result already exist here?" and get an answer
it can act on. As a blueprint grows, the likely outcome is duplicated nodes, re-proved lemmas, and parallel agents
formalizing the same statement in incompatible ways.

The gap has five parts. References are to `main` at `7b65ebc`.

1. **No agent-facing search.** The generated site enables the MkDocs `search` plugin
   (`autoform_cli/templates/mkdocs.yml`), so a person can search the published book. There is no CLI command, so an
   agent cannot. The site's index carries status only as unstructured page text and does not contain Lean
   declaration names, and neither can be filtered on.
2. **Article prose never enters the graph.** `Node` (`autoform_cli/graph.py:61`) and `RuntimeNode`
   (`autoform_cli/runtime.py:95`) hold the title, edges and assertions, but no body text. `WorkItem`
   (`autoform_cli/work.py:32`), which `autoform work context` returns, has no statement prose and no Lean
   signature, so an agent cannot judge a candidate for reuse without opening several files.
3. **The description has no contract.** For a formalizable article, `autoform audit` reports
   `missing-statement-text` only when no visible prose sits between the H1 and the first H2
   (`autoform_cli/audit.py:246`). A leaf whose statement is `TODO` produces no finding. The coverage contract
   already rejects placeholder evidence (`autoform_cli/coverage.py:534`); statements do not get the same treatment.
4. **The skills name no way to search the blueprint.** Roadmap says to "Inspect the repository and existing vault
   before writing" (`skills/roadmap/SKILL.md:46`), but gives no tool and no search-before-add rule. The only
   explicit search instructions point at Mathlib: "Search the pinned Mathlib checkout before planning a
   replacement" (`skills/roadmap/SKILL.md:52`) and the same before adding helpers
   (`skills/formalize/SKILL.md:63`).
5. **Duplicates across articles are not detected.** `load_graph` rejects duplicate files, node IDs and
   `article_id` values (`autoform_cli/graph.py:150-175`). Two articles may still name the same `lean:`
   declaration, and neither `check` nor `audit` reports it.

Reuse across projects has a further blocker: dependency edges stop at the blueprint boundary (#20).

## What Prove2Me does

Prove2Me ([arXiv:2608.28433](https://arxiv.org/abs/2608.28433)) is a hosted platform for collaborative Lean
formalization. Its paper names reusability as one of three obstacles in existing projects (§1, §2) and describes its
answer in §3.1 and §4.3. The concrete API is documented in the public agent playbooks,
[`prove2me/prove2me_workspace`](https://github.com/prove2me/prove2me_workspace) (read at version 0.11.8).

The search itself is simple. `GET /api/v1/theorems?q=...` is documented as a case-insensitive substring match over
the title, the Lean name and the natural-language statement, with filters for status and tags and a sort by newest
or by votes (`references/discover.md`). The playbooks describe no embeddings and no relevance ranking. The paper's
conclusion lists "how agents should search a large, evolving corpus" as an open question.

What makes that search sufficient is the system around it:

| Mechanism | How Prove2Me does it | Source |
| --- | --- | --- |
| Required description | Every agent must submit a "detailed, standardized natural-language description" with its Lean statement, and that is what search indexes. | Paper §4.3, §7 |
| Description contract | Written like a paper, not a Lean dump; standard notation; every symbol given context; a paragraph on the result's role or reuse value; no proof details; an optional closing note for Lean-specific choices. The server returns a digest of these rules whenever a description is submitted or changed. | `references/contribute.md` |
| Name-independent title | A human title, not unique, separate from the Lean identifier, so a result is findable by its usual name. | `references/contribute.md` |
| One-call decision | Each hit returns the Lean statement, description, status, tags and source together. | `references/discover.md` |
| Search before submit | Agents are told to search before drafting a statement, before proving any standard result, and when Mathlib lacks a result. | Paper §4.3; `references/mission_captain.md`, `references/mission_solver.md` |
| Canonical targets | Milestones give one authoritative statement per source lemma, so agents converge instead of restating. | Paper §4.4 |
| Reuse is cheap and rewarded | Any statement is importable in one line from any mission in the same Lean environment, and its author earns credit when others import it. | Paper §4.2, §4.3; `references/prove.md` |
| Corpus hygiene | Retired statements are hidden from search and must name their replacement. | `references/contribute.md` |

The paper reports no measurement of how often reuse happens, so the evidence that this works is the design argument
and the completed missions in its Table 1, not a controlled result.

### What transfers

Autoform already has several of these in a different form:

- The H1 title is separate from the path ID and from `lean:`.
- A coverage contract and source-grounded articles play the role of milestones as canonical targets.
- `mathlib: true` with `mathlib_declaration` already records reuse of a Mathlib result.
- `render.py` already computes reverse dependency edges for its "Used by" lists (`autoform_cli/render.py:1504`).
- Formalize already keeps distilled evidence from failed routes under `## Execution notes`.

Three things are missing and transferable: a contract on the description, a search command whose hits support a
decision in one call, and a rule that agents search first. Two things do not transfer: Prove2Me's hosted corpus of
atomized statement stubs, and its credit system.

## Goal

Before adding a roadmap node or a Lean helper, an agent can find out in one deterministic, local, read-only call
whether the blueprint already contains that result, see enough to decide whether to reuse it, and record the reuse
as an ordinary dependency link.

## Proposed delivery

### Phase 1: search and reuse inside one blueprint

Phase 1 needs no other open issue. Item 4 delivers, for a single blueprint, one acceptance criterion that #20 lists
for workspaces.

1. **Define the statement span once.** Audit and render currently disagree about what an article's statement is:

   | | `audit._read_article` | `render._split_body` |
   | --- | --- | --- |
   | Statement ends at | the first H2 | the first heading of any level |
   | Fenced blocks and HTML comments | ignored | kept |
   | Prose before the H1 | not counted | included |
   | Returns | a boolean | the text |

   So an article with an H3 before its first H2 has statement text for audit and an empty statement box on the
   site. Search would be a third reading. This issue should settle one rule in `autoform_cli/markdown.py` with two
   views of the same span: the raw Markdown, which render needs because a statement may contain a fenced block, and
   the visible text, which audit and search need. The proposed boundary is the first H2, matching the documented
   article shape. That changes what render shows for the H3 case, so it needs a maintainer decision and tests for
   each row above.

2. **Give the statement text a contract.** Add deterministic audit findings for a formalizable leaf, judged on
   rendered visible text as the coverage contract already does:
   - `placeholder-statement-text`: the statement is only a placeholder, or opens with one used as a marker.
   - `empty-statement-text`: the statement has source characters but renders nothing a reader sees.

   This means promoting `_is_placeholder`, `_has_substance` and `_PLACEHOLDER_EVIDENCE` out of `coverage.py` into
   shared code. Rules that need judgment stay out of the audit. Add them to
   `skills/agent-review/references/roadmap-quality.md` under usability: the statement uses standard notation, gives
   context for each symbol, says what the result is for, and contains no proof steps.

3. **Add `autoform search`.**

   ```bash
   autoform search blueprint "separating hyperplane" --lean-root .
   autoform search blueprint "non-ambiguous" --lean-root . --json --limit 20
   autoform search blueprint "interlacing" --state proved --state fully_proved --declaration theorem
   ```

   Behaviour:

   - Read-only and local. It writes nothing and keeps no stored index, so the Markdown stays the only authored
     state.
   - It loads through `load_runtime_graph`, so symlinked roadmap entries and escaping source targets are refused as
     they are for `autoform work`.
   - It indexes the article bytes that produced each node's `source_sha256`, and the output carries the graph
     `source_revision`, so a hit is bound to an exact revision.
   - A query is split into terms. A node matches when every term occurs in some indexed field; different terms may
     match in different fields. Matching is case-insensitive after Unicode normalization.
   - Indexed fields, in ranking order: title; `lean:` and `mathlib_declaration` names; path ID; statement text;
     `## Execution notes`; titles of ancestor containers.
   - Prose fields are matched on rendered visible text, not Markdown source, so emphasis markers and line wrapping
     do not hide a match. Frontmatter, fenced blocks, indented code and HTML comments are not indexed.
   - Order is deterministic: best matching field, then more dependents first, then node ID.
   - `--state` takes exact derived-state keys from `status.STATES` and may be repeated. `--limit` truncates the
     list, and the output reports the total number of matches.
   - `--json` emits a versioned `autoform-search/v1` document with no timestamp or absolute path. Human-readable
     output passes through `_human_text`, as `work list` does, so article text cannot forge report lines.

   Each hit carries what an agent needs to decide on reuse. An illustrative hit for the second command above, from
   the bundled example:

   ```json
   {
     "node_id": "infimum-loss/definitions/non-ambiguity",
     "article_id": "af_fb4bc2e0d1d9b34cfcc377b4",
     "article_path": "blueprint/roadmap/infimum-loss/definitions/non-ambiguity.md",
     "title": "Non-ambiguity",
     "declaration": "def",
     "state": "fully_proved",
     "statement_text": "A weak observation $S : Y \\to \\mathrm{Prop}$ is **non-ambiguous** when ...",
     "lean_targets": [
       {"declaration": "CabannesThesis.NonAmbiguous", "source_file": "src/CabannesThesis/Basic.lean", "line": 11}
     ],
     "mathlib": false,
     "source_targets": ["../../../sources/thesis.md"],
     "used_by_count": 2,
     "used_by": [
       "infimum-loss/theorems/non-ambiguity-determinism",
       "infimum-loss/theorems/supervision-non-ambiguous"
     ],
     "matched_fields": ["statement_text"]
   }
   ```

   Two details are new relative to existing schemas. `line` is not in `autoform-work/v1`'s Lean target today; the
   lexical index already has it. `used_by` is capped at a fixed length, with `used_by_count` giving the full number.

   With `--skeleton REPORT`, each resolved Lean target also carries the elaborated `signature` from an existing
   `autoform-skeleton/v4` report. Search never runs Lean itself, and it refuses a report whose recorded blueprint
   identity does not match the blueprint being searched.

   Hits that share a title after case and whitespace folding are marked as such in the output. That is advisory:
   Prove2Me deliberately allows repeated titles, and two chapters may each have a legitimate "Main theorem".

4. **Report duplicate Lean targets in `autoform audit`.** Add `duplicate-lean-target` when the same declaration
   name appears in the `lean:` value of two different articles. An article may still list several names. #20 lists
   "Duplicate primary ownership of a Lean declaration is reported deterministically" for workspaces; this is the
   single-blueprint case of that criterion.

5. **Teach the skills to search first.**
   - Roadmap: before creating a formalizable leaf, search the blueprint for the result. If it exists, link to it
     under `## Depends on` or `## Proof depends on` instead of adding a node.
   - Formalize: when a proof needs a helper, search the blueprint first, then the pinned Mathlib checkout. A hit
     that is not yet a declared dependency of the claimed article goes back to Roadmap, as a missing prerequisite
     already does.
   - Agent Review: the roadmap-quality rubric already asks reviewers to identify duplicates; point it at the
     command.
   - Document the command once in `autoform_cli/README.md`, which the skills link to, and add acceptance assertions
     to `tests/test_skill_examples.py`.

### Phase 2: search across projects

Blocked. It depends on #20, which depends on #18, which depends on #17 and on the workspace manifest from PR #8.
PR #8 is closed and unmerged, and `main` has no workspace concept today. If maintainers prefer, phase 2 can be split
into its own `blocked` issue.

1. `autoform search` accepts a workspace and returns hits from every project in it, each labelled with its project
   identity.
2. Each hit from another project reports whether that project's Lean toolchain and Mathlib lock identify the same
   release as the caller's, using the identity `autoform project inspect` already computes. This is the equivalent
   of Prove2Me's isolated environments: a result on a different Mathlib revision is visible but flagged as not
   directly importable.
3. Reuse is recorded as a cross-project dependency edge in the form #20 defines. Search proposes the edge; it does
   not add a Lake `require`.
4. Text returned from another project is untrusted data. The skills must say that an agent treats it as content to
   evaluate, never as instructions.

## Acceptance criteria

Phase 1:

- [ ] One function in `markdown.py` defines the statement span, with a raw view and a visible-text view. Audit,
      render and search all use it.
- [ ] Tests cover each case where audit and render disagree today: an H3 before the first H2, a fenced block only,
      an HTML comment only, prose before the H1, and unterminated frontmatter.
- [ ] `autoform audit` reports `placeholder-statement-text` and `empty-statement-text`, with tests for decorated
      placeholders and for text hidden by HTML.
- [ ] `autoform search` finds a node by a word that appears only in its statement text, only in its title, and
      only in its `lean:` name, and by two terms that match in two different fields.
- [ ] Text in frontmatter, fenced blocks, indented code and HTML comments does not produce a hit.
- [ ] Output order and `--json` bytes are identical across runs on identical input. The JSON contains the
      `source_revision` and no timestamp or absolute path.
- [ ] Each hit includes statement text, derived state, Lean targets, sources, and a capped dependents list with
      its full count.
- [ ] The command writes nothing and invokes no subprocess, network service or Lean process. A roadmap containing
      a symlink is refused.
- [ ] Human-readable output escapes nonprintable characters from article text.
- [ ] `--skeleton` refuses a report made for a different blueprint.
- [ ] `autoform audit` reports `duplicate-lean-target`, and still accepts one article listing several names.
- [ ] Roadmap and Formalize state the search-first rule, the CLI reference documents the command, and
      `tests/test_skill_examples.py` asserts both.
- [ ] A test asserts with a counter that search reads each article once and builds reverse edges once, in the
      style of `test_audit_does_not_scan_for_children_per_node`.
- [ ] The new audit codes produce no finding on the bundled example. `make check-example` does not run audit, so
      this needs its own test.
- [ ] `make test`, `make lint` and `make check-example` pass.

Phase 2:

- [ ] A workspace search returns hits from more than one project in a stable order, each with its project identity.
- [ ] A hit from a project on a different Lean or Mathlib release is flagged, not hidden.
- [ ] Single-blueprint invocations behave exactly as in phase 1.

## Non-goals

- Embedding-based or other model-backed search, a hosted index, or any network call. Results must be reproducible
  from the checkout alone.
- A persisted search index or cache.
- Searching Mathlib or community libraries through Autoform. `servers/README.md` deliberately leaves that to
  host-native tools.
- Prove2Me's statement stubs, immutable statements, or separate proof files. Compiling a proof against statement
  stubs is a separate question from search.
- Credit, reputation or leaderboards. The dependents count is a ranking signal only.
- Automatically merging duplicate articles or rewriting links.
- Failing the audit on repeated titles.

## Open questions

1. **Statement boundary.** Is the first H2 the right end of the statement span, given that render currently stops
   at any heading?
2. **Alternative names.** Should articles accept an optional `aliases` frontmatter key for results known by several
   names? It would improve recall, but `graph.py` rejects unknown keys by design, so this is a contract change. The
   proposal above leaves it out.
3. **Shared Lean targets.** Is there a legitimate case for two articles naming the same declaration? If so,
   `duplicate-lean-target` needs an explicit exemption.
4. **Near-duplicates.** Similar-but-not-identical statements need a heuristic. Should that exist as an advisory
   `autoform search --similar-to NODE`, or not at all in phase 1?
5. **Prose in `work context`.** Should `autoform work context` also return the statement text, so a dispatched
   subagent gets it without a second command? That would change the `autoform-work/v1` schema.
6. **Scale target.** The Prove2Me paper says a mission usually involves "hundreds or even thousands" of supporting
   statements (§3.3). The one project cited in the CLI reference has 43 finished nodes. What article count should
   the search test exercise?

## Review

@Deicyde, could you review this proposal? The points that most need a maintainer decision are the statement boundary in phase 1 item 1 and the open questions above. I'm happy to take on the phase 1 implementation once the design is agreed.
