# ai-usage

`ai-usage` starts the Codex CLI, sends `/status`, and extracts the limit rows.
`ai-usage-exporter` keeps collecting the same data and exposes only the latest
`percent_left` values as Prometheus metrics.

## Usage

```sh
uv run ai-usage
uv run ai-usage --json
uv run ai-usage --codex /path/to/codex --timeout 30
CODEX_HOME=/codex-home uv run ai-usage-exporter --account work --host 127.0.0.1 --port 9108 --interval 60 --retry-interval 5
```

The command requires a working Codex login because the limit data is read from Codex itself.

## Container

Images are published by GitHub Actions to `ghcr.io/kinoh/ai-usage`.

```sh
docker run --rm \
  -p 9108:9108 \
  -v codex-home-work:/codex-home \
  ghcr.io/kinoh/ai-usage:latest \
  exporter \
  --account work
```

Use the same image for every account and mount a different volume at `/codex-home`.

Run Codex login once per account volume:

```sh
docker run --rm -it \
  -v codex-home-work:/codex-home \
  ghcr.io/kinoh/ai-usage:latest \
  codex login
```

## Metrics

```prometheus
codex_usage_limit_percent_left{account="work",scope="default",window="5h"} 97
codex_usage_limit_percent_left{account="work",scope="default",window="weekly"} 49
codex_usage_limit_percent_left{account="work",scope="gpt_5_3_codex_spark",window="5h"} 100
codex_usage_limit_percent_left{account="work",scope="gpt_5_3_codex_spark",window="weekly"} 100
```
