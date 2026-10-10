from datetime import datetime, timezone as dt_timezone
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from apps.common.management.commands import run_scheduled_jobs as command


def fake_job(name, result=0, error=None):
    job = MagicMock(name=name, return_value=result, side_effect=error)
    job.name = name
    return job


class RunScheduledJobsTests(SimpleTestCase):
    def run_at(self, hour, *args, frequent=(), daily=()):
        now = datetime(2026, 1, 1, hour, 5, tzinfo=dt_timezone.utc)
        with patch.object(command, "FREQUENT_JOBS", list(frequent)), \
                patch.object(command, "DAILY_JOBS", list(daily)), \
                patch.object(command.timezone, "now", return_value=now):
            call_command("run_scheduled_jobs", *args, stdout=StringIO())

    def test_daily_jobs_only_run_in_their_window_or_when_forced(self):
        frequent, daily = fake_job("frequent"), fake_job("daily")
        self.run_at(14, frequent=[frequent], daily=[daily])
        daily.assert_not_called()
        self.run_at(command.DAILY_HOUR_UTC, frequent=[frequent], daily=[daily])
        self.run_at(14, "--daily", frequent=[frequent], daily=[daily])
        self.assertEqual(daily.call_count, 2)
        self.assertEqual(frequent.call_count, 3)

    def test_one_failing_job_does_not_stop_the_rest(self):
        broken, healthy = fake_job("broken", error=RuntimeError("boom")), fake_job("healthy")
        with self.assertRaisesMessage(CommandError, "broken"), self.assertLogs(command.logger, "ERROR"):
            self.run_at(14, frequent=[broken, healthy])
        healthy.assert_called_once()
