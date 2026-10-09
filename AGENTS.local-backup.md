# AGENTS.md

This repository is AutoformBot, a Python CLI and plugin for Lean 4 formalization projects. The project is organized around source-grounded Markdown blueprints, validation/rendering commands, and server-side Lean tooling.

## Primary references

- [README.md](README.md) for product overview, install flow, and workflows.
- [autoform_cli/README.md](autoform_cli/README.md) for the blueprint contract and CLI semantics.
- [servers/README.md](servers/README.md) for the Lean LSP/REPL architecture.
- [Makefile](Makefile) for the supported local validation commands.

## Working conventions

- Use Python 3.10+ and `uv` for dependency management and execution.
- Prefer the repo’s existing Make targets over ad hoc commands:
  - `make setup`
  - `make test`
  - `make lint`
  - `make check-example`
- Keep changes small and targeted. The repository expects narrow, well-scoped fixes.
- Prefer extending or updating existing patterns over introducing new frameworks or architectures.
- Preserve the project’s “Markdown is the source of truth” principle: blueprint files are authoritative, while generated views are derived outputs.

## Architecture snapshot

- `autoform_cli/`: CLI entrypoints, blueprint validation, rendering, and graph generation.
- `servers/`: Lean runtime, LSP, and REPL services.
- `skills/`: hosted skill definitions and example assets for roadmap and review workflows.
- `tests/`: pytest coverage for CLI behavior, rendering, runtime integration, and blueprint contracts.

## Validation and test expectations

- Run the narrowest relevant check before concluding work.
- The standard local commands are:

```bash
make test
make lint
make check-example
```

- When validating blueprint behavior, use the CLI commands described in [autoform_cli/README.md](autoform_cli/README.md), especially:

```bash
autoform check blueprint --lean-root .
autoform audit blueprint --lean-root .
autoform render blueprint --output site-src --lean-root . --require-declarations
```

- Keep `ruff` conventions in mind: repository config enforces a 120-character line length.

## Repo-specific cautions

- The default branch is `main`; the autonomous execution overlay is on the `execution` branch and is not the default setup.
- `autoform check --lean-root` validates lexical references to Lean names; it does not prove compilation.
- For generated site verification, use the project’s strict MkDocs pipeline rather than treating renderer output as final.

## Model-focused guidance

When working with AI-model or agent-driven features in this repo:

- prefer verifiable, source-grounded changes over inferred or opaque transformations;
- keep documentation and CLI behavior aligned with the actual implementation;
- update tests and docs together when a behavior or contract changes;
- when a change affects the blueprint, validation, or publication contract, treat the relevant docs and tests as the canonical source of truth.

This file is intentionally minimal and should be supplemented by the linked documentation above for detailed project semantics.
