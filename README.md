# ai-usage

`codex-limit` starts the Codex CLI, sends `/status`, and extracts the limit rows.

## Usage

```sh
python -m pip install -e .
codex-limit
codex-limit --json
codex-limit --codex /path/to/codex --timeout 30
```

The command requires a working Codex login because the limit data is read from Codex itself.
