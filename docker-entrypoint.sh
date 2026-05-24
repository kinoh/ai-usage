#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
    set -- exporter
fi

case "$1" in
    exporter)
        shift
        exec python3 -m ai_usage.metrics_exporter --host 0.0.0.0 "$@"
        ;;
    ai-usage)
        shift
        exec python3 -m ai_usage.codex_limits "$@"
        ;;
    codex)
        exec "$@"
        ;;
    *)
        exec python3 -m ai_usage.metrics_exporter --host 0.0.0.0 "$@"
        ;;
esac
