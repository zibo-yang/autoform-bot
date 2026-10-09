# SDD ledger — plan: /workspaces/autoform-bot/docs/superpowers/plans/2026-10-06-statement-span.md
Pre-flight: T1 produces article_parts/ArticleParts/ArticleSection(title, heading, body) + visible_text; T2 consumes .statement, .sections[].title — match. T3 consumes .statement, .sections[].title/.heading/.body — match. No conflicts.
Task 1: complete (commits 7fa6d1d..5fc72aa, tests: uv run pytest tests/test_markdown.py -q → 67 passed in 1.85s)
Task 2: complete (commits 5fc72aa..cc22ce1, tests: uv run pytest tests/test_audit.py tests/test_graph_scale.py -q → 62 passed in 1.72s)
Task 3: complete (commits cc22ce1..0ef6873, tests: uv run pytest tests/test_render.py tests/test_skill_examples.py -q → 102 passed in 2.53s)
Task 4: complete (no commits; make lint clean; make test 1801 passed, 2 baseline failures in test_project_create swapped_in_before_open also failing on main; make check-example exit 0; example site IDENTICAL)
Task 4: Ruling: plan Step 4's diff differs only by the HEAD commit embedded in links — reran both renders with --ref pinned --repository-url; result IDENTICAL — cost if wrong: none, strictly a fairer comparison
Final: fixed stale missing-statement-text reason — test_missing_statement_text_names_the_span_the_audit_reads RED→GREEN, suite 1804 passed + 2 baseline failures
Final: fixed test gaps (case-insensitive Depends on; Proof depends on not republished) — each new test fails under the reviewer's mutation
Final: fixed dead _mask_indented_code call in article_parts — suite unchanged
Final: Ruling: I1/I2 audit-vs-graph disagreement on malformed fences — not fixed; graph.py is out of scope per spec; disclosed — cost if wrong: maintainer asks for loader alignment in this PR
Final: Ruling: I3 unclosed <!-- (incl. in inline code) pulls sections into the theorem box — not fixed; the fix belongs in shared strip_line_comments which coverage relies on to fail closed; disclosed — cost if wrong: a rare article renders its sections inside the box until fixed
Final: Ruling: U1 heading-only statement now passes audit — stands; a heading is text a reader sees — cost if wrong: one weak statement passes
Final: minor (deferred): M2 article_parts counts '<!-- a --> ## Sources' as a section though the site does not
Final: minor (deferred): M5 remainder and visible_text have no caller until later PRs
Final: minor (deferred): M6 _demote_headings uses render's looser fence closer on the statement
