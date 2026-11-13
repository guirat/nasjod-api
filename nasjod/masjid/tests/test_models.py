import pytest
from datetime import datetime, timedelta
from hijri_converter import Gregorian

from datetime import date, time
from django.core.exceptions import ValidationError
from core.models import Address
from ..models import Masjid
from prayertime.models import EidPrayerTime, JumuahPrayerTime, PrayerTime

@pytest.mark.django_db
def test_create_masjid(masjid):
    assert masjid.name == "Sakiet Eddayer Mosque"
    assert masjid.address.street == "Mahdia"
    assert masjid.address.city == "Sakiet Eddaier"
    assert masjid.address.state == "Sfax Governorate"
    assert masjid.address.zip_code == "3011"
    assert masjid.address.country == "Tunisia"
    assert masjid.address.coordinates.x == 10.780081214495699
    assert masjid.address.coordinates.y == 34.79051319533724
    assert masjid.telephone == ""
    assert masjid.size == 'L'
    assert masjid.parking is True
    assert masjid.disabled_access is True
    assert masjid.ablution_room is True
    assert masjid.woman_space is True
    assert masjid.adult_courses is False
    assert masjid.children_courses is False
    assert masjid.salat_al_eid is True
    assert masjid.salat_al_janaza is True
    assert masjid.iftar_ramadhan is True
    assert masjid.itikef is False

@pytest.mark.django_db
def test_get_masjid(masjid):    
    masjid = Masjid.objects.get(uuid=masjid.uuid)
    assert masjid.name == 'Sakiet Eddayer Mosque'
    assert masjid.address.street == 'Mahdia'

@pytest.mark.django_db
def test_update_masjid(masjid):    
    new_address = Address.objects.create(
        street='Updated Street',
        city='Updated City',
        state='Updated State',
        zip_code='67890',
        country='Updated Country',
        coordinates="POINT (30.000000 40.000000)"
    )
    masjid.name = 'Updated Masjid'
    masjid.address = new_address
    masjid.size = 'L'
    masjid.save()
    
    updated_masjid = Masjid.objects.get(uuid=masjid.uuid)
    assert updated_masjid.name == 'Updated Masjid'
    assert updated_masjid.address.street == 'Updated Street'
    assert updated_masjid.size == 'L'

@pytest.mark.django_db
def test_delete_masjid(masjid, address):
    masjid_uuid = masjid.uuid
    address_id = address.id
    masjid.delete()
    
    with pytest.raises(Masjid.DoesNotExist):
        Masjid.objects.get(uuid=masjid_uuid)
    
    with pytest.raises(Address.DoesNotExist):
        Address.objects.get(id=address_id)

@pytest.mark.django_db
def test_add_manager(masjid, manager_user):
    masjid.managers.add(manager_user)
    assert manager_user in masjid.managers.all()

@pytest.mark.django_db
def test_add_assistant(masjid, assistant_user):
    masjid.assistants.add(assistant_user)
    assert assistant_user in masjid.assistants.all()

@pytest.mark.django_db
def test_validate_unique_roles(masjid, manager_user, assistant_user):
    masjid.managers.add(manager_user)
    with pytest.raises(ValidationError) as excinfo:
        masjid.assistants.add(manager_user)
    assert "A user cannot be both a manager and an assistant in the same masjid." in str(excinfo.value)

# Prayer times

@pytest.mark.django_db
def test_prayer_time_model(prayer_time):
    hijri_date = str(Gregorian(prayer_time.date.year, prayer_time.date.month, prayer_time.date.day).to_hijri())
    assert prayer_time.hijri_date == hijri_date
    assert prayer_time.fajr == "05:00"
    assert prayer_time.sunrise == "06:30"
    assert prayer_time.dhuhr == "12:00"
    assert prayer_time.asr == "15:30"
    assert prayer_time.maghrib == "18:00"
    assert prayer_time.isha == "19:30"

@pytest.mark.django_db
def test_jumuah_prayer_time_model(jumuah_prayer_time):
    hijri_date = str(Gregorian(jumuah_prayer_time.date.year, jumuah_prayer_time.date.month, jumuah_prayer_time.date.day).to_hijri())
    assert jumuah_prayer_time.hijri_date == hijri_date
    assert jumuah_prayer_time.jumuah_time == "13:00"
    assert jumuah_prayer_time.date.weekday() == 4  # Ensure it's a Friday

@pytest.mark.django_db
def test_jumuah_prayer_time_model_invalid_date(masjid):
    invalid_date = datetime.today() + timedelta((1 - datetime.today().weekday()) % 7)  # Next Monday
    with pytest.raises(ValidationError):
        jumuah_prayer_time = JumuahPrayerTime(
            masjid=masjid,
            date=invalid_date.date(),
            jumuah_time="13:00"
        )
        jumuah_prayer_time.clean()

@pytest.mark.django_db
def test_jumuah_prayer_time_model_unique_constraint(masjid, jumuah_prayer_time):
    with pytest.raises(ValidationError):
        duplicate_jumuah_prayer_time = JumuahPrayerTime(
            masjid=masjid,
            date=jumuah_prayer_time.date,
            jumuah_time=jumuah_prayer_time.jumuah_time
        )
        duplicate_jumuah_prayer_time.full_clean()

@pytest.mark.django_db
def test_eid_prayer_time_model(eid_prayer_time):
    hijri_date = str(Gregorian(eid_prayer_time.date.year, eid_prayer_time.date.month, eid_prayer_time.date.day).to_hijri())
    assert eid_prayer_time.hijri_date == hijri_date
    assert eid_prayer_time.eid_time == "08:00"

@pytest.mark.django_db
def test_eid_prayer_time_model_unique_constraint(masjid, eid_prayer_time):
    with pytest.raises(ValidationError):
        duplicate_eid_prayer_time = EidPrayerTime(
            date=eid_prayer_time.date,
            eid_time=eid_prayer_time.eid_time
        )
        duplicate_eid_prayer_time.full_clean()
        duplicate_eid_prayer_time.save()
        duplicate_eid_prayer_time.masjids.add(masjid)
