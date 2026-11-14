import pytest
from django.urls import reverse
from rest_framework import status
from core.tests.fixtures import *


@pytest.mark.django_db
class TestURLPaths:
    """Test that URLs are correctly routed without /api/ prefix"""

    def test_version_endpoint_unprefixed(self, api_client):
        """GET /version/ returns 200 with version key"""
        response = api_client.get('/version/')
        assert response.status_code == status.HTTP_200_OK
        assert 'version' in response.json()

    def test_version_url_reverse(self):
        """reverse('version') returns unprefixed path"""
        path = reverse('version')
        assert path == '/version/'

    def test_api_root_returns_200(self, api_client):
        """GET / returns 200 (API root)"""
        response = api_client.get('/')
        assert response.status_code == status.HTTP_200_OK

    def test_api_version_is_404(self, api_client):
        """GET /api/version/ returns 404 (no alias)"""
        response = api_client.get('/api/version/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_api_masajid_is_404(self, api_client):
        """GET /api/masajid/ returns 404 (no alias)"""
        response = api_client.get('/api/masajid/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_schema_url_reverse(self):
        """reverse('schema') returns unprefixed path"""
        path = reverse('schema')
        assert path == '/schema/'
        assert not path.startswith('/api/')

    def test_schema_endpoint_returns_200(self, api_client):
        """GET /schema/ returns 200"""
        response = api_client.get('/schema/')
        assert response.status_code == status.HTTP_200_OK

    def test_schema_has_no_api_prefix_in_paths(self, api_client):
        """Generated OpenAPI schema has no paths starting with /api/"""
        response = api_client.get('/schema/')
        assert response.status_code == status.HTTP_200_OK
        schema = response.data
        if 'paths' in schema:
            for path_key in schema['paths'].keys():
                assert not path_key.startswith('/api/'), \
                    f"Found /api/ prefix in schema path: {path_key}"

    def test_token_obtain_pair_url_reverse(self):
        """reverse('token_obtain_pair') returns unprefixed path"""
        path = reverse('token_obtain_pair')
        assert path == '/auth/token/'
        assert not path.startswith('/api/')

    def test_token_refresh_url_reverse(self):
        """reverse('token_refresh') returns unprefixed path"""
        path = reverse('token_refresh')
        assert path == '/auth/token/refresh/'
        assert not path.startswith('/api/')

    def test_masjid_list_url_reverse(self):
        """reverse('masjid-list') returns unprefixed path"""
        path = reverse('masjid-list')
        assert path == '/masajid/'
        assert not path.startswith('/api/')

    def test_user_list_url_reverse(self):
        """reverse('user-list') returns unprefixed path"""
        path = reverse('user-list')
        assert path == '/users/'
        assert not path.startswith('/api/')

    def test_user_contributors_url_reverse(self):
        """reverse('user-contributors') returns unprefixed path"""
        path = reverse('user-contributors')
        assert path == '/contributors/'
        assert not path.startswith('/api/')

    def test_prayer_time_list_url_reverse(self):
        """reverse('prayer-time-list') returns unprefixed path"""
        path = reverse('prayer-time-list')
        assert path == '/prayer-times/'
        assert not path.startswith('/api/')

    def test_swagger_ui_url_reverse(self):
        """reverse('swagger-ui') returns unprefixed path"""
        path = reverse('swagger-ui')
        assert path == '/schema/swagger-ui/'
        assert not path.startswith('/api/')

    def test_redoc_url_reverse(self):
        """reverse('redoc') returns unprefixed path"""
        path = reverse('redoc')
        assert path == '/schema/redoc/'
        assert not path.startswith('/api/')

    def test_suggestion_modification_url_reverse(self):
        """reverse('suggestion-modification-masjid-list') returns unprefixed path"""
        path = reverse('suggestion-modification-masjid-list')
        assert path == '/suggestions-modification-masjid/'
        assert not path.startswith('/api/')

    def test_admin_still_resolves(self, api_client):
        """GET /admin/ still resolves to admin (302 redirect to login)"""
        response = api_client.get('/admin/', follow=False)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_302_FOUND]

    def test_iqama_time_list_url_reverse(self):
        """reverse('iqamas-list') returns unprefixed path"""
        path = reverse('iqamas-list')
        assert path == '/iqamas/'
        assert not path.startswith('/api/')

    def test_jumuah_prayer_time_list_url_reverse(self):
        """reverse('jumuah-prayer-time-list') returns unprefixed path"""
        path = reverse('jumuah-prayer-time-list')
        assert path == '/jumuah-prayer-times/'
        assert not path.startswith('/api/')

    def test_eid_prayer_time_list_url_reverse(self):
        """reverse('eid-prayer-time-list') returns unprefixed path"""
        path = reverse('eid-prayer-time-list')
        assert path == '/eid-prayer-times/'
        assert not path.startswith('/api/')
