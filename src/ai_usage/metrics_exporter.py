"""Prometheus metrics exporter for Codex usage limits."""

from __future__ import annotations

import argparse
import http.server
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Sequence

from ai_usage.codex_limits import CodexLimitError, LimitInfo, collect_status_output, parse_limits


METRIC_NAME = "codex_usage_limit_percent_left"


@dataclass(frozen=True)
class MetricSample:
    """A Prometheus gauge sample."""

    account: str
    scope: str
    window: str
    value: int


class LimitMetricsCache:
    """Stores the latest successfully collected metric samples."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._samples: list[MetricSample] = []

    def get(self) -> list[MetricSample]:
        with self._lock:
            return list(self._samples)

    def replace(self, samples: Sequence[MetricSample]) -> None:
        with self._lock:
            self._samples = list(samples)


def slug_label(value: str) -> str:
    """Convert Codex status labels to stable Prometheus label values."""

    slug = []
    previous_was_separator = False
    for character in value.lower():
        if character.isalnum():
            slug.append(character)
            previous_was_separator = False
        elif not previous_was_separator:
            slug.append("_")
            previous_was_separator = True
    return "".join(slug).strip("_")


def window_from_limit_name(name: str) -> str:
    """Map Codex limit names to compact window labels."""

    normalized = name.lower().replace(" limit", "").strip()
    return slug_label(normalized)


def samples_from_limits(account: str, limits: Sequence[LimitInfo]) -> list[MetricSample]:
    """Build gauge samples from parsed Codex limits."""

    samples: list[MetricSample] = []
    account_label = slug_label(account)
    scope = "default"

    for limit in limits:
        if limit.percent_left is None:
            scope = slug_label(limit.name.removesuffix(" limit"))
            continue

        samples.append(
            MetricSample(
                account=account_label,
                scope=scope,
                window=window_from_limit_name(limit.name),
                value=limit.percent_left,
            )
        )

    return samples


def render_prometheus_metrics(samples: Sequence[MetricSample]) -> bytes:
    """Render samples in the Prometheus text exposition format."""

    lines = [
        f"# HELP {METRIC_NAME} Codex usage limit percentage left.",
        f"# TYPE {METRIC_NAME} gauge",
    ]
    for sample in samples:
        lines.append(
            f'{METRIC_NAME}{{account="{sample.account}",scope="{sample.scope}",window="{sample.window}"}} '
            f"{sample.value}"
        )
    return ("\n".join(lines) + "\n").encode()


def collect_samples(account: str, codex_command: str, timeout: float) -> list[MetricSample]:
    status_output = collect_status_output(codex_command, timeout)
    return samples_from_limits(account, parse_limits(status_output))


def run_collector(
    cache: LimitMetricsCache,
    stop_event: threading.Event,
    account: str,
    codex_command: str,
    timeout: float,
    interval: float,
    retry_interval: float,
) -> None:
    """Collect Codex limits until stopped."""

    while not stop_event.wait(interval):
        try:
            cache.replace(collect_samples(account, codex_command, timeout))
        except CodexLimitError as error:
            print(f"codex-limit-exporter: {error}", file=sys.stderr)
            while not stop_event.wait(retry_interval):
                try:
                    cache.replace(collect_samples(account, codex_command, timeout))
                    break
                except CodexLimitError as retry_error:
                    print(f"codex-limit-exporter: {retry_error}", file=sys.stderr)


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler serving the cached Prometheus metrics."""

    cache: LimitMetricsCache

    def do_GET(self) -> None:
        if self.path != "/metrics":
            self.send_error(404)
            return

        body = render_prometheus_metrics(self.cache.get())
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def build_handler(cache: LimitMetricsCache) -> type[MetricsHandler]:
    class BoundMetricsHandler(MetricsHandler):
        pass

    BoundMetricsHandler.cache = cache
    return BoundMetricsHandler


def serve_metrics(host: str, port: int, cache: LimitMetricsCache) -> http.server.ThreadingHTTPServer:
    server = http.server.ThreadingHTTPServer((host, port), build_handler(cache))
    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expose Codex usage limits as Prometheus metrics.")
    parser.add_argument("--account", required=True, help="Account label to attach to every metric sample.")
    parser.add_argument("--host", default="127.0.0.1", help="Address to bind.")
    parser.add_argument("--port", type=int, default=9108, help="Port to bind.")
    parser.add_argument("--interval", type=float, default=60.0, help="Seconds between Codex collections.")
    parser.add_argument("--retry-interval", type=float, default=5.0, help="Seconds between failed collections.")
    parser.add_argument("--codex", default="codex", help="Codex executable to run.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Seconds to wait for each Codex collection.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval <= 0:
        print("codex-limit-exporter: --interval must be greater than zero.", file=sys.stderr)
        return 1
    if args.retry_interval <= 0:
        print("codex-limit-exporter: --retry-interval must be greater than zero.", file=sys.stderr)
        return 1

    cache = LimitMetricsCache()
    try:
        cache.replace(collect_samples(args.account, args.codex, args.timeout))
    except CodexLimitError as error:
        print(f"codex-limit-exporter: {error}", file=sys.stderr)
        return 1

    stop_event = threading.Event()
    collector = threading.Thread(
        target=run_collector,
        args=(cache, stop_event, args.account, args.codex, args.timeout, args.interval, args.retry_interval),
        daemon=True,
    )
    collector.start()

    server = serve_metrics(args.host, args.port, cache)

    def stop(_signum: int, _frame: object) -> None:
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        server.serve_forever()
    finally:
        stop_event.set()
        collector.join(timeout=1.0)
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
