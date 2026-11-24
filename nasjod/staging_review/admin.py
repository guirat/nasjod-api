from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.conf import settings
import logging

from .models import StagedMosque

log = logging.getLogger(__name__)


def _can_transition(current_status, new_status):
    """Check if status transition is allowed."""
    allowed_transitions = {
        'new': ['approved', 'rejected'],
        'duplicate': ['approved', 'rejected'],
        'approved': ['rejected'],  # Can undo to rejected (implicit from rejected → new)
        'rejected': ['new'],
    }
    return new_status in allowed_transitions.get(current_status, [])


def approve_rows(modeladmin, request, queryset):
    """Approve selected rows with proper transition checks."""
    now = timezone.now()
    rows = list(queryset.using('staging'))
    updated = 0
    skipped = 0

    for row in rows:
        if _can_transition(row.status, 'approved'):
            row.status = 'approved'
            row.reviewed_by_id = request.user.id
            row.reviewed_by_username = request.user.username
            row.reviewed_at = now
            row.save(using='staging')
            updated += 1
        else:
            skipped += 1

    modeladmin.message_user(request, f"Approved {updated} rows" + (f" ({skipped} skipped)" if skipped else ""))


approve_rows.short_description = "Approve selected rows"


def reject_rows(modeladmin, request, queryset):
    """Reject selected rows with proper transition checks."""
    now = timezone.now()
    rows = list(queryset.using('staging'))
    updated = 0
    skipped = 0

    for row in rows:
        if _can_transition(row.status, 'rejected'):
            row.status = 'rejected'
            row.reviewed_by_id = request.user.id
            row.reviewed_by_username = request.user.username
            row.reviewed_at = now
            row.save(using='staging')
            updated += 1
        else:
            skipped += 1

    modeladmin.message_user(request, f"Rejected {updated} rows" + (f" ({skipped} skipped)" if skipped else ""))


reject_rows.short_description = "Reject selected rows"


def import_approved(modeladmin, request, queryset):
    """Import selected approved rows into main DB."""
    from core.services.staged_import import import_staged_mosques

    approved = list(queryset.filter(status='approved').using('staging'))
    if not approved:
        modeladmin.message_user(request, "No approved rows selected.")
        return

    try:
        slugs = [row.source_id for row in approved]
        imported, skipped, errors = import_staged_mosques(dry_run=False, slug_filter=slugs)
        msg = f"Imported {imported}"
        if skipped:
            msg += f", {skipped} skipped"
        if errors:
            msg += f", {errors} errors"
        modeladmin.message_user(request, msg)
    except Exception as e:
        log.exception("Import failed: %s", e)
        modeladmin.message_user(request, f"Import error: {str(e)}", level='error')


import_approved.short_description = "Import selected approved rows"


class StagedMosqueAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'name_ar', 'city', 'status', 'enriched_flag',
        'first_seen', 'matched_masjid_id', 'reviewed_by_username',
        'mawaqit_link', 'osm_link'
    )
    list_filter = ('status', 'source', ('enriched_at', admin.EmptyFieldListFilter))
    search_fields = ('name', 'name_ar', 'city', 'source_id')
    readonly_fields = (
        'id', 'source', 'source_id', 'name', 'name_ar', 'lat', 'lon',
        'address', 'city', 'state', 'zip_code', 'country', 'phone',
        'image_url', 'raw', 'details', 'enriched_at',
        'enrich_error', 'match_distance_m', 'match_name_score', 'first_seen',
        'last_seen', 'duplicate_of_id', 'status', 'reviewed_by_id',
        'reviewed_by_username', 'reviewed_at'
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


# Register admin only if staging DB is configured
if 'staging' in settings.DATABASES:
    admin.site.register(StagedMosque, StagedMosqueAdmin)
