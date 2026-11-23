from django.db import models


class StagedMosque(models.Model):
    id = models.BigAutoField(primary_key=True)
    source = models.TextField()
    source_id = models.TextField()
    name = models.TextField()
    name_ar = models.TextField(null=True, blank=True)
    lat = models.FloatField()
    lon = models.FloatField()
    geom = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.TextField(null=True, blank=True)
    state = models.TextField(null=True, blank=True)
    zip_code = models.TextField(null=True, blank=True)
    country = models.TextField(null=True, blank=True)
    phone = models.TextField(null=True, blank=True)
    image_url = models.TextField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    raw = models.JSONField()
    status = models.TextField()
    duplicate_of_id = models.BigIntegerField(null=True, blank=True)
    matched_masjid_id = models.BigIntegerField(null=True, blank=True)
    match_distance_m = models.FloatField(null=True, blank=True)
    match_name_score = models.FloatField(null=True, blank=True)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    enriched_at = models.DateTimeField(null=True, blank=True)
    enrich_error = models.TextField(null=True, blank=True)
    reviewed_by_id = models.BigIntegerField(null=True, blank=True)
    reviewed_by_username = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'staged_mosque'
