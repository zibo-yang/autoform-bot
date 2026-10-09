Part of #143: phase 1 items 1, 2, 3 (without `--skeleton`) and 5. Four commits, reviewable one at a time; each builds on the one before. What phase 1 still needs after this PR is under "Not in this PR".

The branch was rewritten after each of the two reviews: the fixes are folded into the commits they belong to, and the former fifth commit (`--skeleton`) is removed.

## Commit 1: one definition of an article's statement

`audit._read_article` and `render._split_body` each decided where a statement ends, and disagreed: the audit stopped at the first H2, the site at the first heading of any level. An article with an H3 before its first H2 had statement text for the audit and a truncated theorem box on the site.

`markdown.article_parts(text)` now returns the statement and the H2 sections, and both callers use it. The statement is the body from the end of the frontmatter to the first `##` heading, without the H1 line. A `##` inside a fenced block or an HTML comment does not end it.

| Case | Audit | Site |
| --- | --- | --- |
| H3 before the first H2 | unchanged | the statement box now runs to the first H2, with the H3 demoted, instead of stopping at the H3 |
| Prose above the H1 | now counts as statement text | unchanged |
| Indented code only | no longer counts as statement text | unchanged |
| `##` inside an HTML comment | unchanged | no longer cuts the statement |

**The graph loader reads fences and comments through the same helper.** It used to remove comments before it recognised fences, so a `<!--` shown inside a code block hid every section after it: the article's dependency edges were dropped, and with the audit moved to `article_parts` nothing reported it. Two rules follow the page:

- A fence closes only on a bare fence line. `main` also closed it on a fence line with trailing text.
- A fence that never closes hides nothing for the graph and the statement, because the site draws it as plain text with the headings and links after it in view. So a ` ```lean ... ``` -- end` block above `## Depends on` loses no edge.
- **This can change what loads.** On an article with a fence that never closes, or a fence line with trailing text, `autoform check` can newly fail (a `# ` line in what is now plain text is a second H1: `multiple H1 titles`) and the graph can gain or lose an edge. For example, under `## Depends on`, the lines ` ``` -- end`, ` ```lean`, `- [a](a.md)` and an indented bare ` ``` ` gave the edge to `a` on `main` and give none here: the first line opens a fence with the info string `-- end`, so the site shows the link as code. Where the two differ, this head is the one that agrees with the rendered page.

The coverage and link checks keep reading an unclosed fence as open, as on `main`: a table in the same paragraph as such a fence is not published. The bundled example's graph is identical before and after.

The render change in the first row of the table and this loader change are the ones to decide at review. The bundled example has no article in any row: its rendered site is byte-identical to `main`'s.

## Commit 2: audit statements that are empty or only a placeholder

A formalizable article passed the audit with `TODO` as its statement, or with markup that publishes nothing. The statement is judged as the site publishes it, so one whose published prose has a letter or digit is never missing or empty. At most one statement finding now fires per article, in this order:

- `missing-statement-text` (existing): no prose outside code blocks, HTML comments and headings.
- `empty-statement-text`: the published prose has no letter or digit.
- `placeholder-statement-text`: every word is one of `pending`, `placeholder`, `todo`, `tbd`, `unknown`, or the statement opens with one of them followed by a colon or a dash.

The prose is judged as the site publishes it, through a new `markdown.visible_prose`. The placeholder rule is the one coverage evidence already follows; `is_placeholder` and `has_substance` move from `coverage.py` to `markdown.py` so both share it.

What an existing user will notice:

- A blueprint with such statements gains findings, and `autoform audit` and `autoform doctor` then exit 1. No generated workflow runs either command. The bundled example gains none.
- **Coverage behaviour change:** a single hyphen or en dash marks a placeholder only when a space follows it, so evidence such as `Unknown-variance case, ...` is no longer rejected. The same rule now also accepts `TBD-later`, `TODO-choose a milestone` and `pending-review`. Across 7,130 generated evidence cells, these hyphen cases were the only verdicts that changed. `Unknown–known duality ...` passes for the same reason.
- The audit renders each formalizable statement, about 1 ms each: 0.64 s to 1.68 s at 1,000 articles.

Two renderer faults that coverage could already reach would otherwise reach every statement, so they are fixed here. Say if you would rather have them as a separate PR.

- `rendered_visible_text` raised an uncaught `RecursionError` on markup nested about 1,000 elements deep. Its tree walk is now iterative. `published_tables` still recurses and still raises on such input, as it does on `main`; statements do not go through it.
- A conversion that failed midway left the cached converter returning raw source for every later text. `render_html` now discards the converter when a conversion raises.

## Commit 3: `autoform search`

`autoform search TARGET QUERY [--lean-root PATH] [--state KEY]... [--declaration KIND]... [--limit N] [--json]` reports the articles that contain every query term. It is read-only, keeps no index and starts no process. Each hit carries the statement as authored, the derived state, Lean targets with file and line, sources, and up to ten dependents with the full count. `--json` writes `autoform-search/v1`; the contract is in `autoform_cli/README.md` under "Search contract".

Where it departs from the issue, and why:

- **Fields.** `lean` and `node_id` match only the last component of a name, and a new lowest-ranked field, `qualified_names`, holds the path ID and Lean names in full. With the issue's fields, every article in a chapter matched the chapter's directory name: on a 2,031-article test blueprint, the one article whose statement was about a probability measure ranked 102 of 102 for "measure". It now ranks 2.
- **`## Execution notes` is not searched**, although #143 item 3 lists it, because #172 (open) moves those notes out of the article. Indexing it now would add a `matched_fields` name to the contract that #172 then empties.
- **A full Lean name finds its owner first.** A term that is a whole `lean:` or `mathlib_declaration` name, or its last components (`Convex.separation` of `Project.Convex.separation`), counts as a `lean` match, with or without `_root_.` and `«»`. A namespace alone still matches only `qualified_names`. Otherwise an article that cites a declaration in its statement outranked the article that owns it.
- **Folding goes beyond case:** width, accents on letters, typographic dashes and quotes, and invisible characters, so `hahn-banach` finds "Hahn–Banach". `≠` does not match `=`. A term sheds the sentence punctuation, quotation marks, backticks, `$` and wrapping emphasis around it, and parentheses that are unbalanced or wrap the whole term, in any combination, so `Hahn–Banach,`, `"non-ambiguous"`, `` `Nat.succ` ``, `(**weak**)`, `$L^2$,` and `(f(x))` find what the bare terms find. `C*`, `foo_` and `!=` are kept as typed.
- **Titles are matched as the page shows them,** like the statement: `Non-*ambiguous* map` is found by `non-ambiguous`, and an entity name or a link URL in a title is not searched.
- **Softer terms.** Words that carry no meaning (`of`, `the`, `if`, ...) are dropped, and a word of letters loses a common ending, so `recovered` finds `recovers`, `topologies` finds `topology` and `cones` finds `cone`. Only the query is shortened, so this only adds hits, and an article holding the words as typed is listed before one reached only through a shortened word.
- **Ordering** follows the issue (best field, dependents, node ID) with two tie-breaks before dependents: within one best field, an article holding every word as typed comes before one reached only through a shortened word, and then the hit whose weakest term sits in a better field comes first.
- **Only the query is shortened.** `topologies` and `topology` are both searched as `topolog`, so each finds the other, but a form that does not begin with the shortened word does not: `indices` does not find "index", `sets` "set", `bodies` "body", nor `define` "defining". Shortening is kept because it only ever adds hits, and a missed hit is what leads to a duplicate. The search contract states the limit.
- **Extra keys:** `article_revision`, `mathlib_declarations`, `mathlib_file`, `shared_title` per hit and `open_statements` at the top, since sibling schemas carry them and a key added later means a version bump.

Search rereads each article and exits 2 on bytes other than those the graph was built from, and refuses what `autoform work` refuses (a symlinked roadmap entry, an escaping target).

## Commit 4: the skills search before adding a result

Search prevents a duplicate only if an agent runs it first, so three skill files gain one paragraph each. None restates a flag; each names `autoform search` and links to the search contract.

- **Roadmap** (`skills/roadmap/SKILL.md`): before adding a formalizable article, search by a few distinctive words and by a Lean name when one is known, read each hit's statement, and retry with fewer words and other usual names before treating the result as new. When another article already states the result, link to it under `## Depends on` or `## Proof depends on` and from the coverage row. A hit that is more general, a special case, or only similar does not replace the result.
- **Formalize** (`skills/formalize/SKILL.md`): before adding a helper, search the blueprint as well. A hit's declaration is used only when the claimed article's dependencies reach that hit's article and the open-statement policy allows it; a hit they do not reach is a missing prerequisite, never something to restate.
- **Agent review** (`references/roadmap-quality.md`): a new evidence item runs the search for each main result in scope and lists the queries. Finding no duplicate is not proof, because matching is literal.

Both skills say that a refusal (exit 2) is not an empty result. Two tests back this. One checks that every skill link into `autoform_cli/README.md` lands on an existing section. The other reads the paragraph that names `autoform search` in each file and checks that it keeps the rule: the contract link, the retry with fewer words, what to do with a hit (link under `## Depends on` instead of adding a node; use a hit only when dependencies reach it, otherwise a missing prerequisite), and that a refusal is not an empty result. It is a presence check: each instruction must be there, in one sentence, but an inverted rule that kept the words would pass.

The paragraphs are insert-only and sit away from the lines #172 rewrites; the merge with #172 is clean in both orders and the merged tree's skill tests pass.

## Not in this PR

- **Item 4, `duplicate-lean-target`** (criterion: "`autoform audit` reports duplicate canonical primary ownership ..."). Per the maintainer's comment on #143 it is to be implemented after #90 and the refreshed #119 artifact layer, and the #127 gate is not to be reused.
- **`autoform search --skeleton REPORT`** (the rest of item 3; criterion: "`--skeleton` refuses a report made for a different blueprint"). A report identifies the whole blueprint, so refusing on any difference makes the flag unusable while articles are being added, and accepting it lets an outdated signature through. The criterion needs a finer identity, to be agreed on #143; the implementation is kept on a separate branch for a follow-up PR.
- **The reverse-edge counter test.** The test here counts what search adds per article, one read and one render; the graph and the runtime projection each read the article as well, so "read once" does not hold for a whole call.

## Known limits

- **Search cost is linear with no index:** about 2 ms per article, 1.8 s at 1,000 articles. A statement with very many formulas costs what the site renderer costs.
- **Search matching is by substring, all terms required,** with no phrase or synonym handling: `map` matches `roadmap`, `unambiguous` does not match `non-ambiguous`, and `ℝ` folds to `r`, which matches nearly every article. The README tells agents to retry with fewer words before treating a result as new.
- `--state` keys are exact: `proved` does not include `fully_proved`.
- `source_revision` comes from the runtime's read, which upstream does not compare with `load_graph`'s. Search binds its own read to the graph's hashes; closing the remaining gap is a two-line change in `runtime.py` that I left out of this PR.
- A comment that never closes hides every heading and link after it, for the graph as well, although the site shows them: the audit reports `missing-depends-section` only when the comment sits above that heading on a formalizable article. This is `main`'s behaviour.
- A real statement that opens `Unknown: ...` or `Pending: ...` is reported as a placeholder and needs rewording, and one written in symbols alone (`⊥ ≠ ⊤.`) is reported as empty; `To be written` and `TODO state it` pass and are left to review. The README documents these.
- Search exits 2 on a blueprint the graph rejects, which is common while articles are being written; the skills tell the agent to resolve the refusal and search again.
- A fence whose closing line carries trailing text is closed by a later bare fence line of the same character and at least its length, even one that opens a longer or indented block, where the site asks for the opener's exact length and indent. The headings and links between the two are then hidden from the graph although the page shows them. This needs both a sloppy closer and a later, longer fence in one article; the README says so and a test pins it.
- Reading an unclosed fence as text rereads the article from that fence, which is more than linear on input built for it: 2,000 openers of strictly decreasing length take about a second. Ordinary articles are unaffected. One backward pass would remove the reread; I left it for a follow-up.
- `autoform_cli/render.py` keeps its own fence readers with the old rule, so a `###` after an unclosed fence inside a statement is not demoted on the page.
- `--declaration` accepts any string: a misspelt kind gives no hits with exit 0. `--state` is validated.
- A BOM before the frontmatter puts the frontmatter into the statement, as on `main`; search and the statement audit now read it.
- Square brackets are kept on a term, so `[weak]` and a pasted `[[wikilink]]` are searched with them.
- `foo'` is searched as `foo`: it finds the primed name but cannot rank it first. Keeping the quote would make a possessive miss.

## Overlap with open PRs

- #172: the merge is textually clean, but #172's `tests/test_audit.py::test_container_note_audit_handles_deep_containment_iteratively` builds `_ArticleShape(True, True)`, and commit 1 makes the first field `statement: str`. Whichever lands second changes that stub to `_ArticleShape("x", True)`. Search reads no notes.
- #183 conflicts in `autoform_cli/__main__.py` (same spot as the search parser) and in `autoform_cli/README.md`; whichever lands second needs a small rebase.
- #90 edits `audit._read_article` and nearby lines; a small manual rebase for whichever lands second.
- #165 conflicts in `coverage.py` (import block), `render.py` and `tests/test_render.py`, and touches `markdown.__all__`; coverage's call sites are unchanged here to keep that small.
- #141 adds its own `article_statement`. `article_parts(...).statement` is meant to be the one definition it reuses.

## Testing

- `make lint` clean; `make check-example` passes.
- `make test`: 2,010 passed. Two tests in `tests/test_project_create.py` (`test_file_swapped_in_before_open_is_not_called_a_link[parent]` and `[ancestor]`) fail on my machine on untouched `main` as well; they pass in CI.
- Each of the four commits passes lint and the full suite on its own.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


