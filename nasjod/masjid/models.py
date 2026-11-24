import phonenumbers
from hijri_converter import Gregorian

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_delete
from django.dispatch import receiver

from prayertime.models import PrayerTime
from core.models import Address, ObjectBase
from core._helpers import image_path_upload



User = get_user_model()

class Masjid(ObjectBase):
    SIZE_CHOICES = (
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
    )

    name = models.CharField(max_length=255)
    name_ar = models.CharField(max_length=255, null=True, blank=True)
    address = models.OneToOneField(Address, related_name='address_masjid',
                                   on_delete=models.SET_NULL, null=True, blank=True)
    telephone = models.CharField(max_length=20, null=True, blank=True)
    mawaqit_slug = models.CharField(max_length=255, null=True, blank=True, unique=True)
    photo = models.ImageField(null=True, blank=True, upload_to=image_path_upload)
    cover = models.ImageField(null=True, blank=True, upload_to=image_path_upload)
    size = models.CharField(max_length=1, choices=SIZE_CHOICES, default='M')

    # Boolean fields
    is_active = models.BooleanField(default=True)
    parking = models.BooleanField(default=False)
    disabled_access = models.BooleanField(default=False)
    ablution_room = models.BooleanField(default=False)
    woman_space = models.BooleanField(default=False)
    adult_courses = models.BooleanField(default=False)
    children_courses = models.BooleanField(default=False)
    salat_al_eid = models.BooleanField(default=False)
    salat_al_janaza = models.BooleanField(default=False)
    iftar_ramadhan = models.BooleanField(default=False)
    itikef = models.BooleanField(default=False)

    # Users
    managers = models.ManyToManyField(User, related_name='managed_masjids', blank=True)
    assistants = models.ManyToManyField(User, related_name='assisted_masjids', blank=True)
    mousallis = models.ManyToManyField(User, related_name='favorite_masjids', blank=True)
    imams = models.ManyToManyField(User, related_name='led_masjids', blank=True)

    # prayer times
    prayer_times = models.ForeignKey('Masjid', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name_plural = "Masajid"
    @property
    def are_infos_complete(self):
        """Check if all non-boolean fields are filled."""
        required_fields = [
            'name', 'address', 'cover', 'size'
        ]
        for field in required_fields:
            if getattr(self, field) in [None, '', False]:
                return False
        # Check if linked to IqamaTime
        has_iqama_time = self.iqamatime_set.exists()

        # Check if linked to JumuahPrayerTime
        has_jumuah_prayer_time = self.jumuahprayertime_set.exists()

        # Return True only if all conditions are met
        return has_iqama_time and has_jumuah_prayer_time

    def __str__(self):
        return self.name
    
    def clean(self):
        super().clean()
        # Only perform the uniqueness check if the address is not None
        if self.address is not None:
            if Masjid.objects.filter(address=self.address).exclude(id=self.id).exists():
                raise ValidationError("A Masjid with this address already exists.")

    def save(self, *args, **kwargs):
        # Save the masjid (this might update the address)
        self.clean()
        super().save(*args, **kwargs)


@receiver(m2m_changed, sender=Masjid.managers.through)
@receiver(m2m_changed, sender=Masjid.assistants.through)
def validate_unique_roles(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action == 'post_add' or action == 'post_remove' or action == 'post_clear':
        managers = set(instance.managers.all())
        assistants = set(instance.assistants.all())

        if managers.intersection(assistants):
            raise ValidationError("A user cannot be both a manager and an assistant in the same masjid.")

@receiver(post_delete, sender=Masjid)
def delete_associated_address(sender, instance, **kwargs):
    if instance.address:
        instance.address.delete()


class SuggestionMasjidModification(ObjectBase):
    SIZE_CHOICES = (
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
    )

    name = models.CharField(max_length=255, default="")
    suggestion_masjid = models.ForeignKey(Masjid, on_delete=models.CASCADE, related_name="suggestions", null=True)
    address = models.OneToOneField(Address, related_name='address_suggestion_masjid_modification',
                                   on_delete=models.SET_NULL, null=True, blank=True)
    telephone = models.CharField(max_length=20, null=True, blank=True)
    photo = models.ImageField(null=True, blank=True, upload_to=image_path_upload)
    cover = models.ImageField(null=True, blank=True, upload_to=image_path_upload)
    size = models.CharField(max_length=1, choices=SIZE_CHOICES, default='M')
    message = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Optional message to provide additional information about the masjid modification suggestion."
    )

    # Boolean fields
    is_active = models.BooleanField(default=True)
    parking = models.BooleanField(default=False)
    disabled_access = models.BooleanField(default=False)
    ablution_room = models.BooleanField(default=False)
    woman_space = models.BooleanField(default=False)
    adult_courses = models.BooleanField(default=False)
    children_courses = models.BooleanField(default=False)
    salat_al_eid = models.BooleanField(default=False)
    salat_al_janaza = models.BooleanField(default=False)
    iftar_ramadhan = models.BooleanField(default=False)
    itikef = models.BooleanField(default=False)

    # iqama

    fajr_iqama = models.IntegerField(null=True, blank=True,)
    dhuhr_iqama = models.IntegerField(null=True, blank=True,)
    asr_iqama = models.IntegerField(null=True, blank=True,)
    maghrib_iqama = models.IntegerField(null=True, blank=True,)
    isha_iqama = models.IntegerField(null=True, blank=True,)

    # Jumuah
    jumuah_time = models.TimeField(null=True, blank=True,)
    first_timeslot_jumuah = models.BooleanField(default=False)

    # Eid prayer time
    eid_time = models.TimeField(null=True, blank=True,)


    class Meta:
        verbose_name_plural = "SuggestionMasjidModifications"

    def __str__(self):
        return self.name
