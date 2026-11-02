import io

import pytest
from django.contrib.gis.geos import Point
from django.core.management import call_command

from core.models import Address
from masjid.models import Masjid


class FakeStaging:
    def __init__(self, rows):
        self.data = {r['id']: r for r in rows}
        self.marks = {}

    def rows(self, statuses):
        return [r for r in self.data.values() if r['status'] in statuses]

    def mark(self, row_id, status, masjid_id=None, distance=None, score=None):
        self.marks[row_id] = (status, masjid_id)
        self.data[row_id]['status'] = status


def row(i, status='approved', name='Mosquée Ennour', lat=34.7, lon=10.7, **kw):
    base = dict(id=i, source='mawaqit', source_id=f's{i}', name=name, name_ar=None, lat=lat, lon=lon,
                address='Rue 1', city='Sfax', state=None, zip_code='3000', phone='+21671000000',
                status=status)
    return {**base, **kw}


def run(rows, **opts):
    st = FakeStaging(rows)
    out = io.StringIO()
    call_command('import_staged_mosques', staging=st, stdout=out, **opts)
    return st, out.getvalue()


def make_masjid(name='Existing', lat=34.7, lon=10.7):
    a = Address.objects.create(country='tunisia', coordinates=Point(lon, lat, srid=4326))
    return Masjid.objects.create(name=name, address=a)


@pytest.mark.django_db
def test_imports_approved_only_and_creates_address():
    st, _ = run([row(1), row(2, status='new', lat=35.0), row(3, status='rejected', lat=36.0)])
    assert st.marks.keys() == {1}
    m = Masjid.objects.get(name='Mosquée Ennour')
    assert st.marks[1] == ('imported', m.id)
    assert m.telephone == '+21671000000' and m.address.city == 'sfax'
    assert (m.address.coordinates.x, m.address.coordinates.y) == (10.7, 34.7)


@pytest.mark.django_db
def test_auto_includes_new():
    st, _ = run([row(1), row(2, status='new', lat=35.0)], auto=True)
    assert st.marks.keys() == {1, 2}


@pytest.mark.django_db
def test_skips_within_100m():
    existing = make_masjid(name='Completely different')
    st, out = run([row(1, lat=34.7005)])  # ~55 m
    assert st.marks[1] == ('duplicate', existing.id)
    assert Masjid.objects.count() == 1 and 'skipped' in out


@pytest.mark.django_db
def test_imports_when_150m_away_with_different_name():
    make_masjid(name='Completely different')
    st, _ = run([row(1, lat=34.7014)])  # ~155 m
    assert st.marks[1][0] == 'imported'


@pytest.mark.django_db
def test_skips_similar_name_nearby():
    existing = make_masjid(name='Mosquée Ennour')
    st, _ = run([row(1, lat=34.704)])  # ~450 m, identical name
    assert st.marks[1] == ('duplicate', existing.id)


@pytest.mark.django_db
def test_dry_run_changes_nothing():
    st, out = run([row(1)], dry_run=True)
    assert st.marks == {} and Masjid.objects.count() == 0 and 'would import' in out


@pytest.mark.django_db
def test_arabic_only_row_uses_arabic_name():
    run([row(1, name='', name_ar='جامع النور')])
    m = Masjid.objects.get()
    assert m.name == 'جامع النور' and m.name_ar == 'جامع النور'
