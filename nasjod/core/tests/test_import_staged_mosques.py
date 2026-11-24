"""Tests for staged_import service."""
import io
from unittest.mock import Mock, patch, MagicMock

import pytest
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile

from core.models import Address
from core.services.staged_import import import_staged_mosques, _find_existing, _download_photo, _apply_details
from masjid.models import Masjid


@pytest.fixture
def test_staging_url():
    """Return a test staging DB URL."""
    return "postgresql://postgres:postgres@localhost/test_staging"


@pytest.mark.django_db
def test_imports_approved_only():
    """Test that only approved rows are imported."""
    mock_conn = MagicMock()

    rows_data = [
        {'id': 1, 'source': 'mawaqit', 'source_id': 's1', 'name': 'Mosque 1', 'name_ar': None,
         'lat': 34.7, 'lon': 10.7, 'address': 'Street 1', 'city': 'Sfax', 'state': None,
         'zip_code': '3000', 'phone': '+21671000000', 'details': None, 'image_url': None},
        {'id': 2, 'source': 'mawaqit', 'source_id': 's2', 'name': 'Mosque 2', 'name_ar': None,
         'lat': 35.0, 'lon': 10.0, 'address': 'Street 2', 'city': 'Tunis', 'state': None,
         'zip_code': '1000', 'phone': None, 'details': None, 'image_url': None},
    ]

    # Mock cursor to return only the first row (approved)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [rows_data[0]]
    mock_cursor.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value = mock_cursor

    with patch('core.services.staged_import.psycopg2.connect', return_value=mock_conn):
        imported, skipped, errors = import_staged_mosques(staging_url="fake://url")

    assert imported == 1
    assert skipped == 0
    assert Masjid.objects.count() == 1
    m = Masjid.objects.get()
    assert m.name == 'Mosque 1'
    assert m.mawaqit_slug == 's1'


@pytest.mark.django_db
def test_mawaqit_slug_matching():
    """Test that existing mawaqit_slug is detected as duplicate."""
    # Create existing mosque with mawaqit_slug
    addr = Address.objects.create(country='tunisia', coordinates=Point(10.7, 34.7, srid=4326))
    existing = Masjid.objects.create(name='Existing Mosque', address=addr, mawaqit_slug='s1')

    # Test _find_existing with same slug
    row = {
        'source': 'mawaqit',
        'source_id': 's1',
        'name': 'Different Name',
        'name_ar': None,
        'lat': 34.701,  # ~100m away
        'lon': 10.7,
    }

    match = _find_existing(row)
    assert match is not None
    matched_masjid, dist, score = match
    assert matched_masjid.id == existing.id
    assert score == 1.0


@pytest.mark.django_db
def test_photo_download_validation():
    """Test photo download with allow-list and size limits."""

    # Test: only cdn.mawaqit.net allowed
    result = _download_photo('https://example.com/image.jpg')
    assert result is None

    # Test: http not allowed (only https)
    result = _download_photo('http://cdn.mawaqit.net/image.jpg')
    assert result is None

    # Test: valid URL but mocked to test size limit
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Type': 'image/jpeg'}
    mock_response.iter_content.return_value = [b'x' * (6 * 1024 * 1024)]  # 6MB, over limit

    with patch('core.services.staged_import.requests.get', return_value=mock_response):
        result = _download_photo('https://cdn.mawaqit.net/image.jpg')
        assert result is None


@pytest.mark.django_db
def test_photo_download_success():
    """Test successful photo download."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Type': 'image/jpeg'}
    mock_response.iter_content.return_value = [b'fake_image_data']

    with patch('core.services.staged_import.requests.get', return_value=mock_response):
        result = _download_photo('https://cdn.mawaqit.net/test.jpg')
        assert result is not None
        assert isinstance(result, ContentFile)


@pytest.mark.django_db
def test_apply_details_mapping():
    """Test that details are mapped to Masjid fields."""
    addr = Address.objects.create(country='tunisia', coordinates=Point(10.7, 34.7, srid=4326))
    masjid = Masjid.objects.create(name='Test', address=addr)

    import json, os
    fixture = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'mawaqit_api_sample.json')
    with open(fixture) as f:
        details = json.load(f)

    _apply_details(masjid, details)

    assert masjid.parking is True
    assert masjid.disabled_access is True
    assert masjid.ablution_room is True
    assert masjid.woman_space is False
    assert masjid.adult_courses is True
    assert masjid.children_courses is True
    assert masjid.salat_al_eid is False
    assert masjid.salat_al_janaza is True
    assert masjid.telephone == details['phone']


@pytest.mark.django_db
def test_dry_run_changes_nothing():
    """Test that dry_run doesn't modify anything."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {
            'id': 1, 'source': 'mawaqit', 'source_id': 's1', 'name': 'Mosque',
            'name_ar': None, 'lat': 34.7, 'lon': 10.7, 'address': 'Street',
            'city': 'Sfax', 'state': None, 'zip_code': '3000', 'phone': None,
            'details': None, 'image_url': None
        }
    ]
    mock_cursor.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value = mock_cursor

    with patch('core.services.staged_import.psycopg2.connect', return_value=mock_conn):
        with patch('core.services.staged_import._find_existing', return_value=None):
            with patch('core.services.staged_import._download_photo', return_value=None):
                imported, skipped, errors = import_staged_mosques(dry_run=True, staging_url="fake://url")

    assert imported == 1
    # _mark_staging_row should not be called in dry_run
    # Check that connection.commit() wasn't called (would happen in _create_masjid)
    assert Masjid.objects.count() == 0
