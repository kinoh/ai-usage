import unittest

from ai_usage.codex_limits import LimitInfo
from ai_usage.metrics_exporter import render_prometheus_metrics, samples_from_limits


class MetricsExporterTest(unittest.TestCase):
    def test_samples_from_limits_keeps_only_percent_left_values(self):
        samples = samples_from_limits(
            "Work Account",
            [
                LimitInfo("5h limit", 97, "04:25", "5h limit: 97% left"),
                LimitInfo("Weekly limit", 49, "10:00 on 27 May", "Weekly limit: 49% left"),
                LimitInfo("GPT-5.3-Codex-Spark limit", None, None, "GPT-5.3-Codex-Spark limit:"),
                LimitInfo("5h limit", 100, "06:14", "5h limit: 100% left"),
                LimitInfo("Weekly limit", 100, "01:14 on 31 May", "Weekly limit: 100% left"),
            ]
        )

        rendered = render_prometheus_metrics(samples).decode()

        self.assertIn(
            'codex_usage_limit_percent_left{account="work_account",scope="default",window="5h"} 97',
            rendered,
        )
        self.assertIn(
            'codex_usage_limit_percent_left{account="work_account",scope="default",window="weekly"} 49',
            rendered,
        )
        self.assertIn(
            'codex_usage_limit_percent_left{account="work_account",scope="gpt_5_3_codex_spark",window="5h"} 100',
            rendered,
        )
        self.assertIn(
            'codex_usage_limit_percent_left{account="work_account",scope="gpt_5_3_codex_spark",window="weekly"} 100',
            rendered,
        )
        self.assertNotIn("success", rendered)
        self.assertNotIn("last_success", rendered)


if __name__ == "__main__":
    unittest.main()
