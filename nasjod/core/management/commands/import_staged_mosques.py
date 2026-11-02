import os
from difflib import SequenceMatcher

import psycopg2
import psycopg2.extras
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Address
from masjid.models import Masjid

NEAR_M = 100          # skip anything this close to an existing Masjid
NAME_SEARCH_M = 1000  # radius within which a very similar name counts as the same mosque
NAME_THRESHOLD = 0.9


def _similarity(a, b):
    a, b = (a or '').strip().lower(), (b or '').strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


class StagingDB:
    """Thin wrapper over the staging Postgres (separate from the main DB)."""

    def __init__(self, url):
        self.conn = psycopg2.connect(url)

    def rows(self, statuses):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM staged_mosque WHERE status = ANY(%s) ORDER BY id', (list(statuses),))
            return cur.fetchall()

    def mark(self, row_id, status, masjid_id=None, distance=None, score=None):
        with self.conn.cursor() as cur:
            cur.execute(
                'UPDATE staged_mosque SET status=%s, matched_masjid_id=%s, match_distance_m=%s, '
                'match_name_score=%s WHERE id=%s',
                (status, masjid_id, distance, score, row_id))
        self.conn.commit()


class Command(BaseCommand):
    help = ('Import mosques from the discovery staging DB into the main DB. Reads "approved" rows '
            '(plus "new" rows with --auto). Skips rows within ~100 m of an existing Masjid or with a '
            'very similar name nearby; imported rows are marked "imported", skipped ones "duplicate".')

    def add_arguments(self, parser):
        parser.add_argument('--auto', action='store_true', help='Also import rows with status "new"')
        parser.add_argument('--dry-run', action='store_true', help='Report only; change nothing')
        parser.add_argument('--staging-url', default=os.environ.get('STAGING_DATABASE_URL'))

    def handle(self, *args, staging=None, **options):
        dry_run, auto = options['dry_run'], options['auto']
        if staging is None:
            if not options['staging_url']:
                raise CommandError('Set STAGING_DATABASE_URL or pass --staging-url')
            staging = StagingDB(options['staging_url'])
        statuses = ['approved'] + (['new'] if auto else [])
        imported = skipped = errors = 0
        for row in staging.rows(statuses):
            label = f'#{row["id"]} {row["source"]}:{row["source_id"]} "{row["name"]}"'
            try:
                match = self.find_existing(row)
                if match:
                    masjid, dist, score = match
                    self.stdout.write(self.style.WARNING(
                        f'{label}: skipped, matches Masjid {masjid.id} "{masjid.name}" '
                        f'({dist:.0f} m, name score {score:.2f})'))
                    if not dry_run:
                        staging.mark(row['id'], 'duplicate', masjid.id, dist, score)
                    skipped += 1
                    continue
                if dry_run:
                    self.stdout.write(self.style.SUCCESS(f'{label}: would import'))
                else:
                    with transaction.atomic():
                        masjid = self.create_masjid(row)
                    staging.mark(row['id'], 'imported', masjid.id)
                    self.stdout.write(self.style.SUCCESS(f'{label}: imported as Masjid {masjid.id}'))
                imported += 1
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f'{label}: error {e}'))
        verb = 'would import' if dry_run else 'imported'
        self.stdout.write(self.style.SUCCESS(f'Done: {verb} {imported}, skipped {skipped}, errors {errors}'))

    def find_existing(self, row):
        """Return (masjid, distance_m, name_score) of an existing Masjid that is the same mosque."""
        pt = Point(row['lon'], row['lat'], srid=4326)
        nearby = (Masjid.objects
                  .filter(address__coordinates__distance_lte=(pt, D(m=NAME_SEARCH_M)))
                  .annotate(dist=Distance('address__coordinates', pt)))
        best = None
        for m in nearby:
            dist = m.dist.m
            score = max(_similarity(row['name'], m.name), _similarity(row.get('name_ar'), m.name_ar),
                        _similarity(row['name'], m.name_ar), _similarity(row.get('name_ar'), m.name))
            if dist <= NEAR_M or score >= NAME_THRESHOLD:
                if best is None or dist < best[1]:
                    best = (m, dist, score)
        return best

    def create_masjid(self, row):
        # Same shape as import_mosques_from_csv: Address + Masjid
        address = Address.objects.create(
            country='tunisia',
            state=row.get('state') or None,
            city=(row.get('city') or '')[:100] or None,
            street=(row.get('address') or '')[:255] or None,
            zip_code=(row.get('zip_code') or '')[:10] or None,
            coordinates=Point(row['lon'], row['lat'], srid=4326),
        )
        name = (row['name'] or row.get('name_ar') or '').strip()
        if not name:
            raise ValueError('row has no name')
        return Masjid.objects.create(
            name=name[:255], name_ar=(row.get('name_ar') or None), address=address,
            telephone=(row.get('phone') or '')[:20] or None,
        )
