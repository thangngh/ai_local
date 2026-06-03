# Contributing to AI Local

Thanks for your interest in contributing to AI Local.

AI Local is a local-first AI agent infrastructure project. It is currently an MVP foundation, not a production-ready autonomous agent platform. Contributions should make the runtime more inspectable, testable, and safer without inflating the project with unsupported claims.

## Project Direction

AI Local should remain:

- local-first by default
- cloud-optional, not cloud-dependent
- requirements-first
- harness-first
- evidence-driven
- explicit about runtime boundaries
- honest about MVP limitations

Avoid contributions that turn the project into a generic chatbot wrapper, a vague AI SaaS scaffold, or a production/security marketing claim that the code does not support.

## Good Contribution Areas

Useful contributions include:

- focused bug fixes
- stronger tests and harness cases
- clearer documentation
- reproducible local demos
- safer sandbox boundaries
- better queue and worker reliability
- retrieval quality improvements
- memory governance checks
- CLI and developer workflow improvements
- CI gate improvements

## Before Opening a Pull Request

Please check that your change has a clear requirement and a matching validation path.

A good pull request should answer:

1. What requirement or problem does this change address?
2. What behavior changed?
3. What tests or gates validate it?
4. What runtime boundary or risk is affected?
5. What remains intentionally out of scope?

## Development Flow

The preferred flow is:

1. Define the requirement.
2. Convert it into acceptance criteria.
3. Add or update focused harness tests.
4. Implement the smallest safe patch.
5. Run local gates.
6. Document behavior and limitations.

Do not implement broad agent-generated changes without a reviewable requirement and tests. Large patches with unclear intent are difficult to review and may be rejected.

## Local Setup

Create a virtual environment:

```powershell
python -m venv .venv
```

Install the project with development dependencies:

```powershell
.\.venv\Scripts\python -m pip install -e .[dev]
```

On Linux/macOS, use the equivalent shell path for the virtual environment.

Install `ripgrep` so retrieval and full tests can run.

## Gate Commands

Run focused harness tests:

```powershell
.\.venv\Scripts\python -m pytest tests\harness
```

Run the full test suite:

```powershell
.\.venv\Scripts\python -m pytest
```

Run quality gates:

```powershell
.\.venv\Scripts\python -m ruff check ai_local tests
.\.venv\Scripts\python -m mypy ai_local tests
```

Run configured gate commands through the CLI:

```powershell
.\.venv\Scripts\python -m ai_local.cli gate test.pytest test.ruff test.mypy
```

Run promotion gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli promote --max-level hard
```

## Pull Request Expectations

A pull request should be small enough to review. Prefer a series of focused pull requests over one large generated patch.

Include:

- summary of the change
- related requirement or issue
- tests run
- risk notes
- screenshots or terminal output when relevant

Keep documentation honest. If a feature is an adapter, boundary, prototype, or roadmap item, say so directly.

## Security and Sandbox Notes

AI Local currently uses a subprocess-based sandbox adapter for MVP execution. Do not describe it as a completed secure sandbox.

Changes touching command execution, writable paths, network access, approval flow, prompt injection handling, or tool policies must include focused tests.

## Coding Style

- Python 3.11+
- Type hints required
- Keep functions small and reviewable
- Prefer explicit models and boundaries
- Avoid hidden side effects
- Avoid broad global state
- Keep line length within the configured ruff limit

## AI-Assisted Contributions

AI-assisted patches are allowed, but the human contributor is responsible for the result.

Before submitting AI-generated code:

- read the diff manually
- remove unused abstractions
- verify tests are meaningful
- check that docs do not exaggerate implementation status
- ensure no secrets, local paths, or private data are included

The project welcomes tools. It does not welcome unsupervised tool worship.

## License

By contributing, you agree that your contributions are licensed under the Apache License 2.0, the same license used by this repository.
