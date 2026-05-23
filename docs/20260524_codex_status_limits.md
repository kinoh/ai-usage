# Codex Status Limit CLI Decisions

## Context

This repository started empty, so there were no existing runtime, package, or CLI conventions to preserve. Python 3.10 was available locally, and the installed Codex command reported `codex-cli 0.133.0`.

## Decisions

- Use a small Python package with a console script because it avoids adding runtime dependencies and can drive a PTY through the standard library.
- Drive `codex --no-alt-screen` instead of reading private Codex state because `/status` is the user-visible source of truth for the requested limit information.
- Parse the terminal output after stripping ANSI sequences because `/status` is rendered by the TUI rather than exposed as a documented machine-readable command.
- Keep tests focused on the two product responsibilities: collecting the Codex status output and parsing the limit rows from that output.

## Verification Notes

The primary runtime path must start Codex, submit `/status`, and extract both inline reset values and reset values rendered on the following row.
