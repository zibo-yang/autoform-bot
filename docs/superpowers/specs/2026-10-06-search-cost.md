# Search cost is linear in blueprint size

A note on one risk in the [phase 1 design](2026-10-06-blueprint-search-design.md) for
[#143](https://github.com/facebookresearch/autoform-bot/issues/143). Local working document, not part of any pull
request.

## Summary

Every `autoform search` call does work proportional to the number of articles in the blueprint, and it does all of
that work again on the next call. Measured on synthetic blueprints, one query costs about 0.2 s at 100 articles,
1.7 s at 1,000 and 5 s at 3,000. Roughly half of that is the cost of loading the blueprint, which every `autoform
work` call already pays today. The other half is new: rendering each statement to the text a reader sees.

The recommendation is to ship PR 3 as designed, record these numbers in the PR, and keep one optimisation in
reserve (several queries per call) for when a real project reports the cost as a problem.

## Why the cost is linear

The design keeps no index, by choice: Markdown is the only authored state, and the issue lists a persisted index or
cache as a non-goal. So each call starts from nothing and does four things for every article:

1. `load_graph` reads and parses it.
2. `build_runtime_graph` reads it again, hashes it, and walks the roadmap for symbolic links.
3. Search reads it a third time to check its hash and split out the statement.
4. Search renders the statement through Python-Markdown and an HTML5 parser to get its visible text.

Steps 1 and 2 are existing behaviour. Step 4 is the expensive new one. It exists so that a match is judged on what
the site publishes: emphasis markers and line wraps do not hide a match, and text in an HTML comment or a `hidden`
element does not produce one.

## Measurements

Synthetic blueprints of 20-article chapters, each article one theorem with a five-line statement containing inline
and display LaTeX. One run each, on a 4-core Codespace with Python 3.14. Times are seconds.

| Articles | `load_graph` | `build_runtime_graph` | Render statements | Substring match | Total | `audit_graph`, for scale |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 106 | 0.05 | 0.02 | 0.12 | 0.000 | 0.19 | 0.02 |
| 1,051 | 0.47 | 0.26 | 0.94 | 0.000 | 1.67 | 0.17 |
| 3,151 | 1.43 | 0.77 | 2.95 | 0.001 | 5.15 | 0.51 |

Rendering costs about 0.9 ms per article and scales linearly. The matching itself is negligible. Masking fences and
comments without rendering costs about 0.01 ms per article, a hundred times less.

Reproduce with [search-cost-bench.py](search-cost-bench.py):
`uv run python docs/superpowers/specs/search-cost-bench.py <empty-scratch-dir>`.

What these numbers leave out:

- Python and `uv` start-up, a fixed cost of a few tenths of a second per call.
- The Lean source index built for `--lean-root`. It is linear in the Lean sources, not the blueprint, and was not
  measured.
- Longer statements. Render time grows with statement length, and real statements vary far more than this fixture.
- The third read of each article (step 3), which is small next to steps 1 and 2.

## Who this affects

A person running one search will not notice 2 s. The cost matters for the search-first rule in PR 5, which tells an
agent to search before every new leaf and every new helper. A Roadmap pass that creates 200 leaves in a
3,000-article blueprint would spend about 17 minutes in search. The same pass at 300 articles would spend under two
minutes.

The only project the CLI reference cites has 43 finished nodes. The Prove2Me paper describes missions of "hundreds
or even thousands" of statements. So today's projects sit at the cheap end and the cost is a scaling risk, not a
present defect.

## Options

| Option | Effect at 3,000 articles | Cost |
| --- | --- | --- |
| A. Ship as designed | 5 s per query | None |
| B. Several queries in one call | 5 s for the first query, about 1 ms for each further one | The command takes a list of queries and the JSON gains a per-query level, so it must be decided before `autoform-search/v1` ships or it needs a v2 |
| C. Match on masked source instead of rendered text | About 2.3 s per query | Matches are no longer judged on published text: link URLs become searchable, HTML-hidden text matches, and a word split by emphasis markers is missed |
| D. Cache rendered text by article hash | About 2.2 s per query after the first | A stored cache, which the issue rules out |
| E. Render only candidates that pass a cheap source filter | Up to 2.3 s per query | No cheap filter is sound: a term can appear in rendered text without being contiguous in the source, so some true matches would be dropped |

No option gets below the 2.2 s that loading costs. Going lower means making `load_graph` and `build_runtime_graph`
faster, which is outside this issue and would help every command.

## Recommendation

Ship option A in PR 3.

- It is the only option that keeps matching exact and adds no contract.
- Half the cost is shared with every other command, so search is not out of line with `autoform work`.
- The scale where it hurts is one no known project has reached.

Two things go into PR 3 so the risk is visible rather than hidden:

- The "Search contract" section of the CLI reference states that each call reads and renders every article, with
  the per-article figure above.
- The PR description carries the measurement table, so the maintainer can ask for option B before the schema is
  fixed.

Option B is the one to reach for if the cost bites. It keeps exact matching, needs no stored state, and makes the
agent workflow nearly free after the first query. Its price is a different command and JSON shape, which is why the
choice between A and B should be made before PR 3 merges, not after.

## Decision

Taken on 2026-10-06: option A. `autoform-search/v1` takes one query per call. The measurement table still goes
into the PR 3 description so the maintainer can ask for option B before the schema is fixed.
