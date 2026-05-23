"""Read Codex usage limits by driving the interactive /status command."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pty
import re
import select
import shutil
import signal
import struct
import sys
import time
from dataclasses import asdict, dataclass
from typing import Sequence


ANSI_PATTERN = re.compile(
    r"\x1b\][^\x07]*(?:\x07|\x1b\\)"
    r"|\x1b\[[0-?]*[ -/]*[@-~]"
    r"|\x1b[()][A-Za-z0-9]"
    r"|\x1b[=>]"
)
LIMIT_PATTERN = re.compile(r"^(?P<name>.+?limit):\s*(?P<value>.*?)(?:\s{2,}|\s*$)", re.IGNORECASE)
RESET_PATTERN = re.compile(r"\(resets (?P<reset>[^)]+)\)", re.IGNORECASE)
PERCENT_PATTERN = re.compile(r"(?P<percent>\d+)%\s+left", re.IGNORECASE)


@dataclass(frozen=True)
class LimitInfo:
    """A single limit row reported by Codex /status."""

    name: str
    percent_left: int | None
    resets: str | None
    raw: str


class CodexLimitError(RuntimeError):
    """Raised when Codex limit information cannot be collected."""


def strip_terminal_sequences(text: str) -> str:
    """Remove common terminal control sequences from Codex TUI output."""

    previous = None
    current = text
    while previous != current:
        previous = current
        current = ANSI_PATTERN.sub("", current)
    return current.replace("\r", "\n")


def normalize_status_line(line: str) -> str:
    """Convert a TUI row into parseable text."""

    line = "".join(ch for ch in line if ch == "\t" or ch == "\n" or ord(ch) >= 32)
    line = re.sub(r"^[^\w/(>]+", "", line.strip())
    line = re.sub(r"\s*[^\x00-\x7F]+$", "", line)
    return re.sub(r"\s+", " ", line).strip()


def parse_limits(status_text: str) -> list[LimitInfo]:
    """Extract limit rows from cleaned Codex /status output."""

    limits: list[LimitInfo] = []
    pending: LimitInfo | None = None

    for raw_line in strip_terminal_sequences(status_text).splitlines():
        line = normalize_status_line(raw_line)
        if not line:
            continue

        limit_match = LIMIT_PATTERN.match(line)
        if not limit_match:
            reset_match = RESET_PATTERN.search(line)
            if reset_match and pending and pending.resets is None:
                pending = LimitInfo(
                    name=pending.name,
                    percent_left=pending.percent_left,
                    resets=reset_match.group("reset"),
                    raw=f"{pending.raw} {line}",
                )
                limits[-1] = pending
            continue

        name = limit_match.group("name")
        value = limit_match.group("value")
        percent_match = PERCENT_PATTERN.search(value)
        reset_match = RESET_PATTERN.search(value)
        pending = LimitInfo(
            name=name,
            percent_left=int(percent_match.group("percent")) if percent_match else None,
            resets=reset_match.group("reset") if reset_match else None,
            raw=line,
        )
        limits.append(pending)

    if not limits:
        raise CodexLimitError("Codex /status output did not contain limit rows.")
    return limits


def collect_status_output(codex_command: str, timeout: float) -> str:
    """Start Codex, send /status, and return captured terminal output."""

    if timeout <= 0:
        raise CodexLimitError("--timeout must be greater than zero.")

    codex_path = shutil.which(codex_command) if os.path.basename(codex_command) == codex_command else codex_command
    if not codex_path or not os.path.exists(codex_path):
        raise CodexLimitError(f"Codex executable was not found: {codex_command}")

    pid, fd = pty.fork()
    if pid == 0:
        os.environ.setdefault("TERM", "xterm-256color")
        os.execvp(codex_path, [codex_path, "--no-alt-screen"])

    fcntl.ioctl(fd, termios_tiocswinsz(), struct.pack("HHHH", 32, 120, 0, 0))
    output = bytearray()
    start = time.monotonic()
    sent_status = False
    last_read = time.monotonic()

    try:
        while time.monotonic() - start < timeout:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if ready:
                chunk = os.read(fd, 8192)
                if not chunk:
                    break
                output.extend(chunk)
                last_read = time.monotonic()

            text = output.decode(errors="replace")
            cleaned = strip_terminal_sequences(text)
            if not sent_status and "›" in cleaned:
                os.write(fd, b"/status\r")
                sent_status = True

            if sent_status and "Weekly limit:" in cleaned and time.monotonic() - last_read > 0.8:
                return text

        raise CodexLimitError("Timed out while waiting for Codex /status limit output.")
    finally:
        try:
            os.write(fd, b"\x03")
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass


def termios_tiocswinsz() -> int:
    """Return the platform TIOCSWINSZ value."""

    import termios

    return termios.TIOCSWINSZ


def format_limits(limits: Sequence[LimitInfo]) -> str:
    """Format parsed limits for terminal output."""

    rows = []
    for limit in limits:
        percent = f"{limit.percent_left}% left" if limit.percent_left is not None else "unknown"
        reset = f", resets {limit.resets}" if limit.resets else ""
        rows.append(f"{limit.name}: {percent}{reset}")
    return "\n".join(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read Codex usage limits from /status.")
    parser.add_argument("--codex", default="codex", help="Codex executable to run.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for /status output.")
    parser.add_argument("--json", action="store_true", help="Emit parsed limits as JSON.")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print cleaned Codex /status output instead of parsed limit rows.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        status_output = collect_status_output(args.codex, args.timeout)
        if args.raw:
            print(strip_terminal_sequences(status_output).strip())
            return 0

        limits = parse_limits(status_output)
        if args.json:
            print(json.dumps([asdict(limit) for limit in limits], ensure_ascii=False, indent=2))
        else:
            print(format_limits(limits))
        return 0
    except CodexLimitError as error:
        print(f"codex-limit: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
