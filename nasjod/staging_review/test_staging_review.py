import os
import pytest
from django.test import TestCase, TransactionTestCase
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()
from django.db import connections
from django.contrib.admin.sites import AdminSite
from staging_review.models import StagedMosque
from staging_review.admin import StagedMosqueAdmin


pytestmark = pytest.mark.skipif(
    'staging' not in settings.DATABASES,
    reason="STAGING_DATABASE_URL not configured"
)


class StagedMosqueAdminTest(TransactionTestCase):
    databases = {'default', 'staging'}

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='pass'
        )
        self.site = AdminSite()
        self.admin = StagedMosqueAdmin(StagedMosque, self.site)

        # Create a test row in staging DB (unmanaged table: not flushed by the test runner)
        with connections['staging'].cursor() as cursor:
            cursor.execute("DELETE FROM staged_mosque")
            cursor.execute("""
                INSERT INTO staged_mosque
                (source, source_id, name, lat, lon, raw, status, first_seen, last_seen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, now(), now())
            """, ('mawaqit', 'test-slug', 'Test Mosque', 35.0, 10.0, '{}', 'new'))

    def tearDown(self):
        with connections['staging'].cursor() as cursor:
            cursor.execute("DELETE FROM staged_mosque")

    def test_approve_action(self):
        """Test that approve action changes status."""
        rows = StagedMosque.objects.using('staging').filter(source_id='test-slug')
        self.assertEqual(rows.count(), 1)

        from django.contrib.messages.storage.cookie import CookieStorage as FallbackStorage
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user
        request._messages = FallbackStorage(request)

        from staging_review.admin import approve_rows
        queryset = StagedMosque.objects.using('staging').all()
        approve_rows(self.admin, request, queryset)

        updated = StagedMosque.objects.using('staging').get(source_id='test-slug')
        self.assertEqual(updated.status, 'approved')
        self.assertEqual(updated.reviewed_by_id, self.user.id)

    def test_reject_action(self):
        """Test that reject action changes status."""
        from django.contrib.messages.storage.cookie import CookieStorage as FallbackStorage
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user
        request._messages = FallbackStorage(request)

        from staging_review.admin import reject_rows
        queryset = StagedMosque.objects.using('staging').all()
        reject_rows(self.admin, request, queryset)

        updated = StagedMosque.objects.using('staging').get(source_id='test-slug')
        self.assertEqual(updated.status, 'rejected')
        self.assertEqual(updated.reviewed_by_username, 'admin')

    def test_no_delete_permission(self):
        """Test that delete is disabled."""
        self.assertFalse(self.admin.has_delete_permission(None))

    def test_no_add_permission(self):
        """Test that add is disabled."""
        self.assertFalse(self.admin.has_add_permission(None))

    def test_staging_db_routing(self):
        """Test that queries use staging DB."""
        queryset = self.admin.get_queryset(None)
        # This should use staging DB
        self.assertEqual(queryset.query.db, 'staging')
