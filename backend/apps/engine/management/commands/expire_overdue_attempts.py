from django.core.management.base import BaseCommand, CommandError

from apps.engine.services import expire_overdue_attempts


class Command(BaseCommand):
    help = 'Expire abandoned IN_PROGRESS examination attempts whose server deadline + grace period has passed.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report overdue attempts that would be expired without modifying the database.',
        )
        parser.add_argument(
            '--exam-id',
            type=str,
            default=None,
            help='Optional Examination UUID to limit expiration sweep.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Maximum number of attempts to lock and expire per transaction batch (default: 500).',
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run', False))
        exam_id = options.get('exam_id')
        batch_size = options.get('batch_size', 500)

        try:
            summary = expire_overdue_attempts(
                exam_id=exam_id,
                batch_size=batch_size,
                dry_run=dry_run,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"[dry-run] {summary['would_expire']} overdue IN_PROGRESS attempt(s) would be auto-submitted."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Scanned {summary['scanned']} overdue attempt(s); auto-submitted {summary['expired']}."
                )
            )
