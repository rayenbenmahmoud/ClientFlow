from django.core.management.base import BaseCommand

from apps.automation import rules


class Command(BaseCommand):
    help = "Run time-based workflow rules (flag overdue lead follow-ups). Schedule daily via cron/systemd."

    def handle(self, *args, **options):
        result = rules.flag_overdue_leads()
        self.stdout.write(
            self.style.SUCCESS(f"Overdue leads flagged: {result['flagged']}, cleared: {result['cleared']}")
        )
