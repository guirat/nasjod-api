import os

from django.core.management.base import BaseCommand, CommandError

from core.services.staged_import import import_staged_mosques


class Command(BaseCommand):
    help = ('Import mosques from the discovery staging DB into the main DB. Reads "approved" rows. '
            'Skips rows within ~100 m of an existing Masjid, with matching mawaqit_slug, or with a '
            'very similar name nearby; imported rows are marked "imported", skipped ones "duplicate".')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only; change nothing')
        parser.add_argument('--staging-url', default=os.environ.get('STAGING_DATABASE_URL'))

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        staging_url = options['staging_url']

        if not staging_url:
            raise CommandError('Set STAGING_DATABASE_URL or pass --staging-url')

        try:
            imported, skipped, errors = import_staged_mosques(
                dry_run=dry_run,
                staging_url=staging_url
            )
            verb = 'would import' if dry_run else 'imported'
            self.stdout.write(self.style.SUCCESS(
                f'Done: {verb} {imported}, skipped {skipped}, errors {errors}'
            ))
        except Exception as e:
            raise CommandError(str(e))
