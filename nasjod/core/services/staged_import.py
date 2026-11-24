"""Import service for staging mosque data."""
import io
import logging
import os
from difflib import SequenceMatcher
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras
import requests
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.files.base import ContentFile
from django.db import transaction

from core.models import Address
from masjid.models import Masjid

log = logging.getLogger(__name__)

NEAR_M = 100
NAME_SEARCH_M = 1000
NAME_THRESHOLD = 0.9

# Map mawaqit-api response camelCase keys to Masjid boolean fields
DETAILS_FIELD_MAP = {
    'parking': 'parking',
    'handicapAccessibility': 'disabled_access',
    'ablutions': 'ablution_room',
    'womenSpace': 'woman_space',
    'adultCourses': 'adult_courses',
    'childrenCourses': 'children_courses',
    'aidPrayer': 'salat_al_eid',
    'janazaPrayer': 'salat_al_janaza',
}


def _similarity(a, b):
    a, b = (a or '').strip().lower(), (b or '').strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _download_photo(image_url):
    """Download photo from image_url with validations.

    - Only allow cdn.mawaqit.net domain
    - Only https
    - Content-Type must be image/*
    - Size limit: 5 MB
    - Timeout: 20 seconds

    Returns: ContentFile or None
    """
    if not image_url:
        return None

    try:
        parsed = urlparse(image_url)
        if parsed.scheme != 'https' or parsed.hostname != 'cdn.mawaqit.net':
            log.debug("Skipping photo: not https or not from cdn.mawaqit.net: %s", image_url)
            return None

        resp = requests.get(image_url, timeout=20, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            log.debug("Skipping photo: Content-Type not image/*: %s", content_type)
            return None

        content = io.BytesIO()
        size = 0
        max_size = 5 * 1024 * 1024
        for chunk in resp.iter_content(chunk_size=8192):
            size += len(chunk)
            if size > max_size:
                log.warning("Photo too large (>5MB): %s", image_url)
                return None
            content.write(chunk)

        content.seek(0)
        filename = image_url.split('/')[-1]
        if '.' not in filename:
            filename += '.jpg'
        return ContentFile(content.read(), name=filename)

    except requests.RequestException as e:
        log.warning("Failed to download photo %s: %s", image_url, e)
        return None
    except Exception as e:
        log.warning("Error processing photo %s: %s", image_url, e)
        return None


def _apply_details(masjid, details):
    """Apply mawaqit-api details to Masjid model."""
    if not details:
        return

    for api_key, model_field in DETAILS_FIELD_MAP.items():
        value = details.get(api_key)
        if value is not None:
            setattr(masjid, model_field, bool(value))

    if 'phone' in details and details['phone'] and not masjid.telephone:
        phone = str(details['phone']).strip()
        if phone:
            masjid.telephone = phone[:20]


def import_staged_mosques(dry_run=False, slug_filter=None, ids=None, staging_url=None):
    """Import approved staged mosques into main DB.

    Args:
        dry_run: if True, don't modify anything
        slug_filter: (deprecated) if set, only import these slugs
        ids: if set, only import these row ids
        staging_url: STAGING_DATABASE_URL (defaults to env var)

    Returns:
        (imported, skipped, errors) tuple
    """
    if staging_url is None:
        staging_url = os.environ.get('STAGING_DATABASE_URL')
    if not staging_url:
        raise ValueError('STAGING_DATABASE_URL not set')

    conn = psycopg2.connect(staging_url)
    imported = skipped = errors = 0

    try:
        query = "SELECT * FROM staged_mosque WHERE status = %s"
        params = ['approved']

        if ids:
            query += " AND id = ANY(%s)"
            params.append(ids)
        elif slug_filter:
            query += " AND source_id = ANY(%s)"
            params.append(slug_filter)

        query += " ORDER BY id"

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        for row in rows:
            label = f'#{row["id"]} {row["source"]}:{row["source_id"]} "{row["name"]}"'
            try:
                match = _find_existing(row)
                if match:
                    masjid, dist, score = match
                    log.warning(
                        '%s: skipped, matches Masjid %d "%s" (%d m, score %.2f)',
                        label, masjid.id, masjid.name, int(dist), score
                    )
                    if not dry_run:
                        _mark_staging_row(conn, row['id'], 'duplicate', masjid.id, dist, score)
                    skipped += 1
                    continue

                if dry_run:
                    log.info('%s: would import', label)
                else:
                    masjid = _create_masjid(row)
                    _mark_staging_row(conn, row['id'], 'imported', masjid.id)
                    log.info('%s: imported as Masjid %d', label, masjid.id)

                imported += 1

            except Exception as e:
                errors += 1
                log.exception('%s: error', label)

        log.info(
            'Import complete: %s %d, skipped %d, errors %d',
            'would import' if dry_run else 'imported',
            imported, skipped, errors
        )

    finally:
        conn.close()

    return imported, skipped, errors


def _find_existing(row):
    """Return (masjid, distance_m, name_score) of existing match.

    Check in this order:
    1. mawaqit_slug match (if source='mawaqit')
    2. Within NEAR_M
    3. Similar name within NAME_SEARCH_M
    """
    if row.get('source') == 'mawaqit' and row.get('source_id'):
        try:
            masjid = Masjid.objects.get(mawaqit_slug=row['source_id'])
            return (masjid, 0, 1.0)
        except Masjid.DoesNotExist:
            pass

    pt = Point(row['lon'], row['lat'], srid=4326)
    nearby = (Masjid.objects
              .filter(address__coordinates__distance_lte=(pt, D(m=NAME_SEARCH_M)))
              .annotate(dist=Distance('address__coordinates', pt)))

    best = None
    for m in nearby:
        dist = m.dist.m
        score = max(
            _similarity(row['name'], m.name),
            _similarity(row.get('name_ar'), m.name_ar),
            _similarity(row['name'], m.name_ar),
            _similarity(row.get('name_ar'), m.name)
        )
        if dist <= NEAR_M or score >= NAME_THRESHOLD:
            if best is None or dist < best[1]:
                best = (m, dist, score)

    return best


def _create_masjid(row):
    """Create Masjid from staged row with photo and details."""
    photo_content = None
    if row.get('image_url'):
        photo_content = _download_photo(row['image_url'])

    with transaction.atomic():
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

        masjid = Masjid(
            name=name[:255],
            name_ar=(row.get('name_ar') or None),
            address=address,
            telephone=(row.get('phone') or '')[:20] or None,
        )

        if row.get('source') == 'mawaqit' and row.get('source_id'):
            masjid.mawaqit_slug = row['source_id']

        _apply_details(masjid, row.get('details'))

        if photo_content:
            masjid.photo = photo_content

        masjid.save()

    return masjid


def _mark_staging_row(conn, row_id, status, masjid_id=None, distance=None, score=None):
    """Mark staging row with result."""
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE staged_mosque SET status=%s, matched_masjid_id=%s,
               match_distance_m=%s, match_name_score=%s WHERE id=%s""",
            (status, masjid_id, distance, score, row_id)
        )
    conn.commit()
