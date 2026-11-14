from datetime import datetime, timedelta

from core.tests.fixtures import *

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import Address
from ..models import Masjid
from prayertime.models import EidPrayerTime, JumuahPrayerTime, PrayerTime

User = get_user_model()

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test to prevent throttle counter leakage"""
    cache.clear()
    yield
    cache.clear()

# Override or add additional fixtures specific to app2
@pytest.fixture
def address():
    return Address.objects.create(
        street="Mahdia",
        city="Sakiet Eddaier",
        state="Sfax Governorate",
        zip_code="3011",
        country="Tunisia",
        coordinates="POINT (10.780081214495699 34.79051319533724)"
    )

@pytest.fixture
def masjid_payload():
    return {
        "name": "Sakiet Eddayer Mosque",
        "address": {
            "street": "Mahdia",
            "city": "Sakiet Eddaier",
            "state": "Sfax Governorate",
            "zip_code": "3011",
            "country": "Tunisia",
            "coordinates": "POINT(10.780081214495699 34.79051319533724)"
        },
        "telephone": "",
        "photo": None,
        "cover": None,
        "size": "L",
        "parking": True,
        "disabled_access": True,
        "ablution_room": True,
        "woman_space": True,
        "adult_courses": False,
        "children_courses": False,
        "salat_al_eid": True,
        "salat_al_janaza": True,
        "iftar_ramadhan": True,
        "itikef": False
    }

@pytest.fixture
def masjid(address, manager_user, assistant_user, mousalli_user, imam_user):
    masjid = Masjid.objects.create(
        name="Sakiet Eddayer Mosque",
        address=address,
        telephone="",
        photo=None,
        cover=None,
        size='L',
        parking=True,
        disabled_access=True,
        ablution_room=True,
        woman_space=True,
        adult_courses=False,
        children_courses=False,
        salat_al_eid=True,
        salat_al_janaza=True,
        iftar_ramadhan=True,
        itikef=False
    )
    masjid.managers.add(manager_user)
    masjid.assistants.add(assistant_user)
    masjid.mousallis.add(mousalli_user)
    masjid.imams.add(imam_user)
    return masjid

@pytest.fixture
def prayer_time(masjid):
    prayer_time = PrayerTime.objects.create(
        date=datetime.today().date(),
        fajr="05:00",
        sunrise="06:30",
        dhuhr="12:00",
        asr="15:30",
        maghrib="18:00",
        isha="19:30"
    )
    prayer_time.masjids.add(masjid)
    return prayer_time

@pytest.fixture
def jumuah_prayer_time(masjid):
    # Ensure the date is a Friday
    today = datetime.today()
    next_friday = today + timedelta((4 - today.weekday()) % 7)
    return JumuahPrayerTime.objects.create(
        masjid=masjid,
        date=next_friday.date(),
        jumuah_time="13:00"
    )

@pytest.fixture
def eid_prayer_time(masjid):
    eid_prayer_time = EidPrayerTime.objects.create(
        date=datetime.today().date(),
        eid_time="08:00"
    )
    eid_prayer_time.masjids.add(masjid)
    return eid_prayer_time