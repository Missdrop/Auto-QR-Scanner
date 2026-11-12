# Development

Use Python 3.12 and uv. Develop on `dev`.

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
uv run python -W error::ResourceWarning -m unittest discover -s tests -v
```

Use ordinary classes with explicit constructors. Organize concrete operations through composition. Keep names clear, methods focused and control flow shallow. Separate logical steps with blank lines and useful English comments. Use English identifiers, comments and program output, and add necessary type annotations.

Validate each independent change before making a small local commit. Use a short English message beginning with a lowercase verb, without a mandatory Conventional Commits prefix. Add behavior tests as features are implemented; empty classes do not count as verified features.

Push, pull request creation and merging require explicit user instructions. Include only files related to the current task.

The `wechat` extra installs the free Windows backend. Local image tests do not require a logged-in WeChat client. Integration with a real group, student login and a valid AMS code must be reported separately from automated tests. Keep private photos, databases and browser profiles out of Git.
