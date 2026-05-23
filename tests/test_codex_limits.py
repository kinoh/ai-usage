import unittest

from ai_usage.codex_limits import format_limits, parse_limits


STATUS_OUTPUT = """
│  5h limit:                    [████████████████████] 98% left (resets 04:25) │
│  Weekly limit:                [██████████░░░░░░░░░░] 49% left                │
│                               (resets 10:00 on 27 May)                       │
│  GPT-5.3-Codex-Spark limit:                                                  │
│  5h limit:                    [████████████████████] 100% left               │
│                               (resets 05:53)                                 │
│  Weekly limit:                [████████████████████] 100% left               │
│                               (resets 00:53 on 31 May)                       │
"""


class CodexLimitParsingTest(unittest.TestCase):
    def test_parse_limits_extracts_percent_and_reset_rows(self):
        limits = parse_limits(STATUS_OUTPUT)

        self.assertEqual(
            [(limit.name, limit.percent_left, limit.resets) for limit in limits],
            [
                ("5h limit", 98, "04:25"),
                ("Weekly limit", 49, "10:00 on 27 May"),
                ("GPT-5.3-Codex-Spark limit", None, None),
                ("5h limit", 100, "05:53"),
                ("Weekly limit", 100, "00:53 on 31 May"),
            ],
        )

    def test_format_limits_keeps_unknown_when_percent_is_absent(self):
        output = format_limits(parse_limits(STATUS_OUTPUT))

        self.assertIn("GPT-5.3-Codex-Spark limit: unknown", output)


if __name__ == "__main__":
    unittest.main()
