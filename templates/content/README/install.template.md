Requires `<Python version range>` and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url>
cd <repo-name>
uv sync --locked
```

<If this repo publishes an installable package, also document that path:>

```bash
uv add <package-name>
# or
pip install <package-name>
```
