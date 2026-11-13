import pytest
import datetime

from django.urls import reverse
from rest_framework import status
from django.contrib.gis.geos import GEOSGeometry

from ..models import Masjid
from prayertime.models import EidPrayerTime, JumuahPrayerTime, PrayerTime
from core.models import Address


@pytest.mark.django_db
def test_create_masjid(api_client, admin_user, masjid_payload):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(reverse('masjid-list'), masjid_payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    assert 'uuid' in response.data
    assert 'name' in response.data
    assert response.data['name'] == masjid_payload['name']

@pytest.mark.django_db
def test_get_masjid(api_client, admin_user, masjid):
    api_client.force_authenticate(user=admin_user)
    url = reverse('masjid-detail', args=[masjid.uuid])
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data['name'] == masjid.name

@pytest.mark.django_db
def test_partial_update_masjid(api_client, manager_user, masjid):
    api_client.force_authenticate(user=manager_user)
    masjid.managers.add(manager_user)
    update_data = {"name": "Updated Masjid"}
    url = reverse('masjid-detail', args=[masjid.uuid])
    response = api_client.patch(url, update_data)
    assert response.status_code == status.HTTP_200_OK
    masjid.refresh_from_db()
    assert masjid.name == "Updated Masjid"

@pytest.mark.django_db
def test_partial_update_masjid_address(api_client, manager_user, masjid):
    api_client.force_authenticate(user=manager_user)
    masjid.managers.add(manager_user)
    
    update_data = {
        "address": {
            "street": "Rue de Sfax",
            "route_km_marker": 5.5,
            "city": "Sfax",
            "state": "Sfax Governorate",
            "zip_code": "3000",
            "country": "Tunisia",
            "coordinates": "POINT (10.760028 34.745000)"
        }
    }
    url = reverse('masjid-detail', args=[masjid.uuid])
    response = api_client.patch(url, update_data, format='json')
    assert response.status_code == status.HTTP_200_OK
    masjid.refresh_from_db()
    address = masjid.address
    assert address.street == "Rue de Sfax"
    assert address.route_km_marker == 5.5
    assert address.city == "Sfax"
    assert address.state == "Sfax Governorate"
    assert address.zip_code == "3000"
    assert address.country == "Tunisia"
    assert address.coordinates.equals(GEOSGeometry("POINT (10.760028 34.745000)"))

@pytest.mark.django_db
def test_delete_masjid(api_client, admin_user, masjid, address):
    api_client.force_authenticate(user=admin_user)
    url = reverse('masjid-detail', args=[masjid.uuid])
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    with pytest.raises(Masjid.DoesNotExist):
        Masjid.objects.get(uuid=masjid.uuid)
    with pytest.raises(Address.DoesNotExist):
        Address.objects.get(id=address.id)

# Test permissions for Masjid

@pytest.mark.django_db
def test_masjid_permissions(api_client, manager_user, assistant_user, mousalli_user, imam_user, masjid):
    url = reverse('masjid-detail', kwargs={'uuid': masjid.uuid})

    # Manager
    api_client.force_authenticate(user=manager_user)
    response = api_client.patch(url, {'name': 'Updated Masjid'}, format='json')
    assert response.status_code == status.HTTP_200_OK

    # Assistant
    api_client.force_authenticate(user=assistant_user)
    response = api_client.patch(url, {'name': 'Updated Masjid by Assistant'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Mousalli
    api_client.force_authenticate(user=mousalli_user)
    response = api_client.patch(url, {'name': 'Updated Masjid by Mousalli'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Imam
    api_client.force_authenticate(user=imam_user)
    response = api_client.patch(url, {'name': 'Updated Masjid by Imam'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Anonymous
    api_client.force_authenticate(user=None)
    response = api_client.patch(url, {'name': 'Updated Masjid by Anonymous'}, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_masjid_creation_permissions(api_client, masjid_payload, admin_user, manager_user, assistant_user, mousalli_user, imam_user):
    url = reverse('masjid-list')
    Masjid.objects.all().delete()
    # Admin
    api_client.force_authenticate(user=admin_user)
    response = api_client.post(url, masjid_payload, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    Masjid.objects.get(uuid=response.data['uuid']).delete()

    # Manager
    api_client.force_authenticate(user=manager_user)
    response = api_client.post(url, masjid_payload, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Assistant
    api_client.force_authenticate(user=assistant_user)
    response = api_client.post(url, masjid_payload, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Mousalli
    api_client.force_authenticate(user=mousalli_user)
    response = api_client.post(url, masjid_payload, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Imam
    api_client.force_authenticate(user=imam_user)
    response = api_client.post(url, masjid_payload, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Anonymous
    api_client.force_authenticate(user=None)
    response = api_client.post(url, masjid_payload, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_masjid_deletion_permissions(api_client, admin_user, manager_user, assistant_user, mousalli_user, imam_user, masjid):
    url = reverse('masjid-detail', kwargs={'uuid': masjid.uuid})

    # Admin
    api_client.force_authenticate(user=admin_user)
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Manager
    api_client.force_authenticate(user=manager_user)
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Assistant
    api_client.force_authenticate(user=assistant_user)
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Mousalli
    api_client.force_authenticate(user=mousalli_user)
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Imam
    api_client.force_authenticate(user=imam_user)
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Anonymous
    api_client.force_authenticate(user=None)
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_masjid_get_permissions(api_client, manager_user, assistant_user, mousalli_user, imam_user, masjid):
    url = reverse('masjid-detail', kwargs={'uuid': masjid.uuid})

    # Manager
    api_client.force_authenticate(user=manager_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Assistant
    api_client.force_authenticate(user=assistant_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Mousalli
    api_client.force_authenticate(user=mousalli_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Imam
    api_client.force_authenticate(user=imam_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Anonymous
    api_client.force_authenticate(user=None)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.django_db
def test_masjid_list_permissions(api_client, manager_user, assistant_user, mousalli_user, imam_user):
    url = reverse('masjid-list')

    # Manager
    api_client.force_authenticate(user=manager_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Assistant
    api_client.force_authenticate(user=assistant_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Mousalli
    api_client.force_authenticate(user=mousalli_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Imam
    api_client.force_authenticate(user=imam_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Anonymous
    api_client.force_authenticate(user=None)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

# Tests for prayer times

@pytest.mark.django_db
def test_create_prayer_time(api_client, admin_user, masjid):
    api_client.force_authenticate(user=admin_user)
    url = reverse('prayer-time-list', kwargs={'masjid_uuid': masjid.uuid})
    data = {
        'date': '2024-05-28',
        'fajr': '05:00',
        'sunrise': '06:30',
        'dhuhr': '12:00',
        'asr': '15:30',
        'maghrib': '18:00',
        'isha': '19:30',
        'fajr_iqama': 20,
        'dhuhr_iqama': 10,
        'asr_iqama': 15,
        'maghrib_iqama': 5,
        'isha_iqama': 25
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    created_prayer_time = PrayerTime.objects.get(masjid=masjid, date='2024-05-28')
    assert created_prayer_time.fajr == datetime.time(5, 0)
    assert created_prayer_time.sunrise == datetime.time(6, 30)
    assert created_prayer_time.dhuhr == datetime.time(12, 0)
    assert created_prayer_time.asr == datetime.time(15, 30)
    assert created_prayer_time.maghrib == datetime.time(18, 0)
    assert created_prayer_time.isha == datetime.time(19, 30)
    assert created_prayer_time.fajr_iqama == 20
    assert created_prayer_time.dhuhr_iqama == 10
    assert created_prayer_time.asr_iqama == 15
    assert created_prayer_time.maghrib_iqama == 5
    assert created_prayer_time.isha_iqama == 25

@pytest.mark.django_db
def test_update_prayer_time(api_client, admin_user, prayer_time):
    api_client.force_authenticate(user=admin_user)
    url = reverse('prayer-time-detail', kwargs={'masjid_uuid': prayer_time.masjid.uuid, 'pk': prayer_time.pk})
    data = {
        'fajr': '05:15',
        'fajr_iqama': 25
    }
    response = api_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    prayer_time.refresh_from_db()
    assert prayer_time.fajr == datetime.time(5, 15)
    assert prayer_time.fajr_iqama == 25

@pytest.mark.django_db
def test_delete_prayer_time(api_client, admin_user, prayer_time):
    api_client.force_authenticate(user=admin_user)
    url = reverse('prayer-time-detail', kwargs={'masjid_uuid': prayer_time.masjid.uuid, 'pk': prayer_time.pk})
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert PrayerTime.objects.count() == 0

@pytest.mark.django_db
def test_create_jumuah_prayer_time(api_client, admin_user, masjid):
    api_client.force_authenticate(user=admin_user)
    url = reverse('jumuah-prayer-time-list', kwargs={'masjid_uuid': masjid.uuid})
    data = {
        'date': '2024-05-31',  # Ensure this is a Friday
        'jumuah_time': '13:00'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    created_jumuah_prayer_time = JumuahPrayerTime.objects.get(masjid=masjid, date='2024-05-31')
    assert created_jumuah_prayer_time.jumuah_time == datetime.time(13, 0)

@pytest.mark.django_db
def test_update_jumuah_prayer_time(api_client, admin_user, jumuah_prayer_time):
    api_client.force_authenticate(user=admin_user)
    url = reverse('jumuah-prayer-time-detail', kwargs={'masjid_uuid': jumuah_prayer_time.masjid.uuid, 'pk': jumuah_prayer_time.pk})
    data = {
        'jumuah_time': '13:15'
    }
    response = api_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    jumuah_prayer_time.refresh_from_db()
    assert jumuah_prayer_time.jumuah_time == datetime.time(13, 15)

@pytest.mark.django_db
def test_delete_jumuah_prayer_time(api_client, admin_user, jumuah_prayer_time):
    api_client.force_authenticate(user=admin_user)
    url = reverse('jumuah-prayer-time-detail', kwargs={'masjid_uuid': jumuah_prayer_time.masjid.uuid, 'pk': jumuah_prayer_time.pk})
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert JumuahPrayerTime.objects.count() == 0

@pytest.mark.django_db
def test_create_eid_prayer_time(api_client, admin_user, masjid):
    api_client.force_authenticate(user=admin_user)
    url = reverse('eid-prayer-time-list', kwargs={'masjid_uuid': masjid.uuid})
    data = {
        'date': '2024-05-28',
        'eid_time': '08:00'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == status.HTTP_201_CREATED
    created_eid_prayer_time = EidPrayerTime.objects.get(masjid=masjid, date='2024-05-28')
    assert created_eid_prayer_time.eid_time == datetime.time(8, 0)

@pytest.mark.django_db
def test_update_eid_prayer_time(api_client, admin_user, eid_prayer_time):
    api_client.force_authenticate(user=admin_user)
    url = reverse('eid-prayer-time-detail', kwargs={'masjid_uuid': eid_prayer_time.masjid.uuid, 'pk': eid_prayer_time.pk})
    data = {
        'eid_time': '08:30'
    }
    response = api_client.patch(url, data, format='json')
    assert response.status_code == status.HTTP_200_OK
    eid_prayer_time.refresh_from_db()
    assert eid_prayer_time.eid_time == datetime.time(8, 30)

@pytest.mark.django_db
def test_delete_eid_prayer_time(api_client, admin_user, eid_prayer_time):
    api_client.force_authenticate(user=admin_user)
    url = reverse('eid-prayer-time-detail', kwargs={'masjid_uuid': eid_prayer_time.masjid.uuid, 'pk': eid_prayer_time.pk})
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert EidPrayerTime.objects.count() == 0

# Permission Tests
@pytest.mark.django_db
def test_prayer_time_permissions(api_client, manager_user, assistant_user, mousalli_user, imam_user, prayer_time):
    url = reverse('prayer-time-detail', kwargs={'masjid_uuid': prayer_time.masjid.uuid, 'pk': prayer_time.pk})

    # Manager
    api_client.force_authenticate(user=manager_user)
    response = api_client.patch(url, {'fajr': '05:15'}, format='json')
    assert response.status_code == status.HTTP_200_OK

    # Assistant
    api_client.force_authenticate(user=assistant_user)
    response = api_client.patch(url, {'fajr': '05:30'}, format='json')
    assert response.status_code == status.HTTP_200_OK

    # Mousalli
    api_client.force_authenticate(user=mousalli_user)
    response = api_client.patch(url, {'fajr': '05:45'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Imam
    api_client.force_authenticate(user=imam_user)
    response = api_client.patch(url, {'fajr': '06:00'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_jumuah_prayer_time_permissions(api_client, manager_user, assistant_user, mousalli_user, imam_user, jumuah_prayer_time):
    url = reverse('jumuah-prayer-time-detail', kwargs={'masjid_uuid': jumuah_prayer_time.masjid.uuid, 'pk': jumuah_prayer_time.pk})

    # Manager
    api_client.force_authenticate(user=manager_user)
    response = api_client.patch(url, {'jumuah_time': '13:15'}, format='json')
    assert response.status_code == status.HTTP_200_OK

    # Assistant
    api_client.force_authenticate(user=assistant_user)
    response = api_client.patch(url, {'jumuah_time': '13:30'}, format='json')
    assert response.status_code == status.HTTP_200_OK

    # Mousalli
    api_client.force_authenticate(user=mousalli_user)
    response = api_client.patch(url, {'jumuah_time': '13:45'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Imam
    api_client.force_authenticate(user=imam_user)
    response = api_client.patch(url, {'jumuah_time': '14:00'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_eid_prayer_time_permissions(api_client, manager_user, assistant_user, mousalli_user, imam_user, eid_prayer_time):
    url = reverse('eid-prayer-time-detail', kwargs={'masjid_uuid': eid_prayer_time.masjid.uuid, 'pk': eid_prayer_time.pk})

    # Manager
    api_client.force_authenticate(user=manager_user)
    response = api_client.patch(url, {'eid_time': '08:30'}, format='json')
    assert response.status_code == status.HTTP_200_OK

    # Assistant
    api_client.force_authenticate(user=assistant_user)
    response = api_client.patch(url, {'eid_time': '09:00'}, format='json')
    assert response.status_code == status.HTTP_200_OK

    # Mousalli
    api_client.force_authenticate(user=mousalli_user)
    response = api_client.patch(url, {'eid_time': '09:30'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Imam
    api_client.force_authenticate(user=imam_user)
    response = api_client.patch(url, {'eid_time': '10:00'}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN

