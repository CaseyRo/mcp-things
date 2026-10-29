# Contributing

Thanks for helping. Bug reports, client-compatibility reports and ideas are as
welcome as code.

## Reporting

- **Bugs and client problems:** [open an issue](https://github.com/CaseyRo/mcp-things/issues/new/choose). The forms ask for what's needed to reproduce it.
- **Questions, setups, open ideas:** [Discussions](https://github.com/CaseyRo/mcp-things/discussions).
- **Security issues:** report privately, see [SECURITY.md](SECURITY.md).

## Changing code

1. For anything bigger than a fix, open an idea issue or a discussion first, so we agree on the shape before you build it.
2. New tools and breaking changes get an OpenSpec change in `openspec/changes/` (see [docs/development.md](docs/development.md#planning-changes-with-openspec)).
3. Branch from `source` (the default branch) and open the pull request against it.
4. Before pushing:

   ```bash
   uv sync
   uv run pytest                                   # CI-safe; no Things needed
   uv run ruff check . && uv run ruff format --check .
   ```

5. If you added or changed a tool, run `uv run python scripts/gen_tools_doc.py` and commit `docs/tools.md`.

Real integration tests (`-m real`) need Things 3 and a token on your Mac; CI never runs them. Mention in the PR whether you ran them.

## Ground rules

- Never log task titles, notes or tokens; use `get_logger(__name__)`.
- Fail with `ToolError`, not an error payload.
- Don't bump `version` in `pyproject.toml`; releases are git tags.

How the code is organized: [docs/architecture.md](docs/architecture.md). Patterns for tools and tests: [docs/development.md](docs/development.md).
