from django.contrib import admin
from django.db import connection
from django.urls import reverse
from django.utils.html import format_html
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
import logging

from .models import StagedMosque

log = logging.getLogger(__name__)


def approve_rows(modeladmin, request, queryset):
    updated = queryset.filter(
        status__in=['new', 'duplicate']
    ).update(
        status='approved',
        reviewed_by_id=request.user.id,
        reviewed_by_username=request.user.username,
        reviewed_at=__import__('django.utils.timezone', fromlist=['now']).now()
    )
    modeladmin.message_user(request, f"{updated} rows approved.")


approve_rows.short_description = "Approve selected rows"


def reject_rows(modeladmin, request, queryset):
    updated = queryset.filter(
        status__in=['new', 'approved', 'duplicate']
    ).update(
        status='rejected',
        reviewed_by_id=request.user.id,
        reviewed_by_username=request.user.username,
        reviewed_at=__import__('django.utils.timezone', fromlist=['now']).now()
    )
    modeladmin.message_user(request, f"{updated} rows rejected.")


reject_rows.short_description = "Reject selected rows"


def import_approved(modeladmin, request, queryset):
    from core.services.staged_import import import_staged_mosques

    approved = queryset.filter(status='approved')
    if not approved.exists():
        modeladmin.message_user(request, "No approved rows selected.")
        return

    try:
        from django.db import connections
        staging_conn = connections['staging'].get_connection()
        cursor = staging_conn.cursor()

        slugs = list(approved.values_list('source_id', flat=True))
        import_staged_mosques(dry_run=False, slug_filter=slugs)
        modeladmin.message_user(request, f"Import started for {len(slugs)} approved rows.")
    except Exception as e:
        log.exception("Import failed: %s", e)
        modeladmin.message_user(request, f"Import error: {str(e)}", level='error')


import_approved.short_description = "Import selected approved rows"


@admin.register(StagedMosque)
class StagedMosqueAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'name_ar', 'city', 'status', 'enriched_flag',
        'first_seen', 'matched_masjid_id', 'reviewed_by_username',
        'mawaqit_link', 'osm_link'
    )
    list_filter = ('status', 'source', ('enriched_at', admin.EmptyFieldListFilter))
    search_fields = ('name', 'name_ar', 'city', 'source_id')
    readonly_fields = (
        'id', 'source', 'source_id', 'raw', 'details', 'enriched_at',
        'enrich_error', 'match_distance_m', 'match_name_score', 'first_seen',
        'last_seen', 'duplicate_of_id'
    )
    fieldsets = (
        ('Location & Identity', {
            'fields': (
                'id', 'source', 'source_id', 'name', 'name_ar', 'lat', 'lon',
                'address', 'city', 'state', 'zip_code', 'country', 'phone',
                'image_url'
            )
        }),
        ('Enrichment', {
            'fields': ('details', 'enriched_at', 'enrich_error')
        }),
        ('Review', {
            'fields': (
                'status', 'reviewed_by_id', 'reviewed_by_username',
                'reviewed_at', 'review_note'
            )
        }),
        ('Matching', {
            'fields': (
                'duplicate_of_id', 'matched_masjid_id', 'match_distance_m',
                'match_name_score'
            )
        }),
        ('Raw Data', {
            'fields': ('raw', 'first_seen', 'last_seen'),
            'classes': ('collapse',)
        }),
    )
    actions = [approve_rows, reject_rows, import_approved]

    def enriched_flag(self, obj):
        if obj.enriched_at:
            return format_html(
                '<span style="color: green;">✓</span>'
            )
        return format_html(
            '<span style="color: red;">✗</span>'
        )
    enriched_flag.short_description = "Enriched"

    def mawaqit_link(self, obj):
        if obj.source == 'mawaqit' and obj.source_id:
            url = f"https://mawaqit.net/fr/{obj.source_id}"
            return format_html(
                '<a href="{}" target="_blank">Mawaqit</a>', url
            )
        return "—"
    mawaqit_link.short_description = "Links"

    def osm_link(self, obj):
        if obj.lat and obj.lon:
            url = f"https://www.openstreetmap.org/?mlat={obj.lat}&mlon={obj.lon}&zoom=15"
            return format_html(
                '<a href="{}" target="_blank">OSM</a>', url
            )
        return "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.using('staging')

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Only staff with explicit permission
        return request.user.is_staff and request.user.has_perm(
            'staging_review.review_stagedmosque'
        )

    def has_view_permission(self, request, obj=None):
        # Only staff with explicit permission
        return request.user.is_staff and request.user.has_perm(
            'staging_review.review_stagedmosque'
        )
