# autoform-bot vs Prove2Me: capability comparison

As of 2026-10-04.

## Summary

autoform-bot does not have all of Prove2Me's advantages. Of the three things Anthropic's Fermat's Last Theorem article
credits Prove2Me for, autoform-bot on `main` has one, has the raw material for a second, and lacks the third.

It also has no proving workflow on `main`. In the other direction, it is stronger than Prove2Me on statement
faithfulness and source coverage.

The two tools sit at different layers. autoform-bot plans and audits a formalization inside a repository you own.
Prove2Me is a hosted service that coordinates many agents proving statements and verifies each proof on its server.

## What Prove2Me is

Prove2Me is a hosted platform for collaborative Lean 4 formalization, driven mainly by AI agents with humans
supervising. Papers and textbooks become "missions": a goal theorem broken into small Lean statements that anyone's
agent can prove.

The public repository `prove2me/prove2me_workspace` is not the server's source code. It holds the agent instructions
(`SKILL.md` plus 14 reference playbooks), an empty working directory layout, and two Lean scripts for importing an
existing project. The verifier, API and web app are not published there.

How it works:

1. The agent clones the workspace, gets an API key for the user's account, and installs Lean pinned to a platform
   environment.
2. It picks an open statement from a mission's dependency tree.
3. It uploads a `solution.lean` containing a top-level `theorem solution` whose type matches the target exactly.
4. The server type-checks the file and returns a verdict such as `ACCEPTED`, `SKETCH_ACCEPTED`, `CE` or `WA`.
5. The agent attaches a written explanation and moves to the next statement.

The central mechanism is the reduction, which the platform calls a sketch. Every theorem is stored as an importable
stub ending in `sorry`. A proof that imports open theorems is accepted as a sketch, and those imports become the
parent's children. When every child is proved, the parent is marked proved automatically.

Contributors pay for their own agent's model usage and compute. The platform pays for hosting and verification.
Public contributions are licensed Apache 2.0.

As of 4 October 2026 the site reported about 800 accounts, 103,725 public statements (92,663 proved) and 1,306 public
missions.

## How Prove2Me helped the Fermat's Last Theorem work

According to Anthropic's article of 4 September 2026, switching to Prove2Me is what made the attempt succeed. Earlier
attempts failed because agents "quickly lost track of the project's state and stopped collaborating effectively".

The result was about 13 million lines of Lean and 30,300 theorems, produced by a team of agents in a little under two
weeks for roughly 6 billion output tokens. Tianyi Peng of Columbia, who designed Prove2Me with collaborators, is named
on the work, and Kevin Buzzard reviewed the proof.

The article credits Prove2Me with three things:

1. **A dependency graph of theorem statements** that agents used to decide what to prove next. The article says this
   helped with memory degradation and let many agents work in parallel.
2. **Faster compilation and lower resource use**, from keeping statements and proofs in separate files with the links
   between them maintained independently.
3. **Search and reuse**, from a natural-language description on every statement, which the article says led to a
   simpler proof path.

The article also reports that failed attempts contributed about 7% of the non-boilerplate lines in the final proof. In
a smaller experiment, three personal Claude Max plans formalized Vinogradov's Three Primes Theorem in three days
through Prove2Me.

The article admits the proof is "likely much longer than it needs to be" compared with Mathlib.

## The three named advantages

autoform-bot has the first, lacks the second, and partly has the third.

| Advantage | In autoform-bot | Evidence in the source |
| --- | --- | --- |
| Dependency graph that tells agents what to do next | Yes | [status.py](autoform_cli/status.py) derives `can_prove` and `fully_proved` from the graph on every run. [runtime.py](autoform_cli/runtime.py) marks dispatchable leaves. |
| Cheap compilation by separating statements from proofs | No | The project is an ordinary Lake project. Parallel agents serialize `lake build` behind a single `lake-build` claim ([claim contract](autoform_cli/README.md#claim-contract)). |
| Search and reuse through natural-language descriptions | Partly | Every article has prose, but there is no search command or index. Cross-project dependencies are open issue #20, marked blocked. |

Two qualifications:

- **Status is asserted, not verified.** A node counts as proved because an author wrote `proof: formalized` in its
  frontmatter. `autoform check --lean-root` only confirms the declaration name exists lexically. On Prove2Me the
  server sets the status after type-checking.
- **Single checks are fast.** The REPL and LSP servers keep warm Lean processes per project, so checking one snippet
  is quick. That does not remove the project-wide build lock.

## Other gaps in autoform-bot

Beyond the three named advantages, autoform-bot lacks five things Prove2Me provides.

- **No execution layer on `main`.** The roadmap skill says "do not prove Lean declarations". The prover and worker
  stack lives on the deprecated `execution` branch. [skills/human-review/SKILL.md](skills/human-review/SKILL.md) still
  hands Lean changes to an "Orchestrate" skill that does not exist on `main`.
- **No per-node verification verdict.** The generated
  [autoform-verify.yml](autoform_cli/templates/github/workflows/autoform-verify.yml) workflow builds the whole project
  and audits axioms in CI. Nothing feeds that result back into node status.
- **Closed coordination.** Claims are Git-ref leases on `origin`, so contributors need push access to the repository.
  There are no accounts, attribution or leaderboard.
- **No record of failed attempts and no disproof path.** Prove2Me keeps failed submissions readable and accepts
  disproofs. The `counterexample-hunter` agent exists only on the `execution` branch.
- **Unproven at scale.** The bundled example has 7 roadmap nodes, and the real project cited in the CLI reference has
  43. Open issues #60, #93 and #97 concern quadratic rendering. Prove2Me carried about 30,000 theorems for the Fermat
  proof.

## Where autoform-bot is stronger

autoform-bot is ahead on checking that the Lean says what the source says, and on tracking how much of the source is
covered.

| Area | autoform-bot | Prove2Me |
| --- | --- | --- |
| Faithfulness evidence | `autoform skeleton` computes the trusted closure from elaborated terms, strips comments, prints signatures raw to defeat notation tricks, and binds reviews to drift hashes and the cited passage. | A blind sub-agent writes a prose "read-back" of what the statement asserts. A human compares it with the source and a moderator reviews it. |
| Source coverage | A coverage contract records each source area as mapped, decomposed, deferred or out of scope, and `autoform audit` checks it. | Captain-curated milestones. I found no equivalent coverage record. |
| Dependency types | Statement dependencies and proof dependencies are separate edges, inside a hierarchical book. | One import-based dependency tree. |
| Ownership of the result | A normal Lean repository you control, reviewed against a Mathlib-style rubric, with no immutable names and no hosted service. | Published statements are immutable, and each proof is a separate `solution` file on the platform. |

Prove2Me's review process does have something autoform-bot lacks: a required human confirmation and a moderator
approval before a mission goes public.

## Options for closing the gap

Four changes would close most of the gap, listed by impact:

1. Add a proving workflow on `main`, replacing the deprecated `execution` branch.
2. Set node status from a verified build instead of an author's frontmatter assertion.
3. Let a proof compile against statement stubs, so that builds stop being a project-wide lock.
4. Add search over article prose, so agents can find existing results before proving new ones.

An alternative is to use both tools: export an autoform roadmap as a Prove2Me mission. Milestones with source-faithful
statements are what a mission proposal needs, and Prove2Me would supply the execution and verification that
autoform-bot lacks. The cost is that proofs would then live on a hosted platform under its immutability and Apache 2.0
terms.

## Sources and caveats

Sources read on 4 October 2026:

- [prove2.me](https://prove2.me), including its [Momentum](https://prove2.me/momentum) and
  [Users](https://prove2.me/users) pages
- [prove2me/prove2me_workspace](https://github.com/prove2me/prove2me_workspace) at version 0.11.8, cloned and read
  directly
- [Formalizing Fermat's Last Theorem](https://www.anthropic.com/research/formalizing-fermats-last-theorem), Anthropic
- The autoform-bot repository: its READMEs, skills, CLI and server layout, CI templates, open issues and the
  `execution` branch

Caveats:

- The website and the Anthropic article were read through a page summarizer. Quotes and figures from them are as it
  returned them and may be slightly off. The site's pages disagreed on some counts.
- Prove2Me's server code is not public, so statements about how it verifies and compiles come from its documentation
  and the article, not from its source.
- The mapping from the article's three advantages to specific Prove2Me features is an interpretation. The article does
  not name endpoints or file layouts.
- For autoform-bot the documentation and skills were read in full and the code selectively. The test suite and the
  tools were not run as part of this comparison.
