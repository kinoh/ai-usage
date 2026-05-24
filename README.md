# ai-usage

`codex-limit` starts the Codex CLI, sends `/status`, and extracts the limit rows.
`codex-limit-exporter` keeps collecting the same data and exposes only the latest
`percent_left` values as Prometheus metrics.

## Usage

```sh
python -m pip install -e .
codex-limit
codex-limit --json
codex-limit --codex /path/to/codex --timeout 30
CODEX_HOME=/codex-home codex-limit-exporter --account work --host 127.0.0.1 --port 9108 --interval 60 --retry-interval 5
```

The command requires a working Codex login because the limit data is read from Codex itself.

## Metrics

```prometheus
codex_usage_limit_percent_left{account="work",scope="default",window="5h"} 97
codex_usage_limit_percent_left{account="work",scope="default",window="weekly"} 49
codex_usage_limit_percent_left{account="work",scope="gpt_5_3_codex_spark",window="5h"} 100
codex_usage_limit_percent_left{account="work",scope="gpt_5_3_codex_spark",window="weekly"} 100
```
