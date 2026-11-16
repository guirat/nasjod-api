from datetime import date, timedelta

from django.db import transaction
from django.contrib.auth import get_user_model
from core._consts import TUNISIA_PRAYER_TIMES_CITIES
from django.conf import settings
from core._helpers import get_next_friday
from rest_framework import serializers

from .models import Masjid, SuggestionMasjidModification
from core.models import Address
from core.serializers import AddressSerializer
from prayertime.models import EidPrayerTime, IqamaTime, JumuahPrayerTime, PrayerTime
from prayertime.serializers import EidPrayerTimeSerializer, IqamaTimeMasjidSerializer, IqamaTimeSerializer, JumuahPrayerTimeMasjidSerializer, JumuahPrayerTimeSerializer, PrayerTimeMasjidSerializer


User = get_user_model()


class MasjidMapSerializer(serializers.ModelSerializer):
    """Lightweight serializer for map view with only essential fields"""
    address = AddressSerializer()
    
    class Meta:
        model = Masjid
        fields = ['uuid', 'name', 'address']


class MasjidSerializer(serializers.ModelSerializer):
    address = AddressSerializer()
    jumuah_prayer_times = JumuahPrayerTimeMasjidSerializer(many=True, required=False)
    eid_prayer_times = EidPrayerTimeSerializer(many=True, read_only=True)
    today_prayer_times = serializers.SerializerMethodField()
    iqamas = IqamaTimeMasjidSerializer(many=True, required=False)
    jumuah_prayer_time_this_week = serializers.SerializerMethodField()

    class Meta:
        model = Masjid
        fields = [
            'uuid',
            'name',
            'is_active',
            'are_infos_complete',
            'address',
            'cover',
            'size',
            'parking',
            'disabled_access',
            'ablution_room',
            'woman_space',
            'adult_courses',
            'children_courses',
            'salat_al_eid',
            'salat_al_janaza',
            'iftar_ramadhan',
            'itikef',
            'jumuah_prayer_times',
            'eid_prayer_times',
            'today_prayer_times',
            'iqamas',
            'jumuah_prayer_time_this_week',
        ]
        read_only_fields = [
            'is_active',
            'are_infos_complete',
        ]

    def get_today_prayer_times(self, obj):
        today = date.today()
        prayer_times = PrayerTime.objects.filter(masjids=obj, date=today)
        return PrayerTimeMasjidSerializer(prayer_times, many=True).data

    def get_jumuah_prayer_time_this_week(self, obj):

        # Filter JumuahPrayerTime for this mosque and the calculated upcoming Friday
        jumuah_prayer_times_this_week = JumuahPrayerTime.objects.filter(masjid__uuid=obj.uuid)

        # Prepare the response data manually using the model method
        response_data = []
        for jumuah_prayer_time in jumuah_prayer_times_this_week:
            response_data.append({
                'date': get_next_friday(),
                'jumuah_time': jumuah_prayer_time.get_jumuah_time(),
                'first_timeslot_jumuah': jumuah_prayer_time.first_timeslot_jumuah
            })

        return response_data

    def get_eid_prayer_time_this_week(self, obj):
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())  # Start of the week (Monday)
        end_of_week = start_of_week + timedelta(days=6)  # End of the week (Sunday)
        eid_prayer_times = EidPrayerTime.objects.filter(masjids=obj, date__range=[start_of_week, end_of_week])
        return EidPrayerTimeSerializer(eid_prayer_times, many=True).data

    def create(self, validated_data):
        address_data = validated_data.pop('address')
        iqamas_data = validated_data.pop('iqamas', [])
        jumuah_prayer_times_data = validated_data.pop('jumuah_prayer_times', [])

        # Check if an address with the same coordinates exists
        try:
            address = Address.objects.get(coordinates=address_data.get('coordinates'))
        except Address.DoesNotExist:
            # If not found, create a new address
            address = Address.objects.create(**address_data)

        masjid = Masjid.objects.create(address=address, is_active=False, **validated_data)
        
        # Create iqamas directly
        for iqama_data in iqamas_data:
            IqamaTime.objects.create(
                masjid=masjid,
                **iqama_data
            )

        # Create jumuah prayer times directly
        for jumuah_data in jumuah_prayer_times_data:
            JumuahPrayerTime.objects.create(
                masjid=masjid,
                **jumuah_data
            )

        # Now create the Masjid with the retrieved or newly created address
        
        # If the address has a city, update the prayer times based on city changes
        if masjid.address and masjid.address.city:
            # 2. Link the Masjid to PrayerTimes in the new city
            city_to_use = masjid.address.city
            # Special handling to use main cities for prayer times
            if settings.USE_MAIN_CITY_FOR_PRAYER_TIMES:
                city_to_use = TUNISIA_PRAYER_TIMES_CITIES.get(masjid.address.state.lower())
            matching_prayer_times = PrayerTime.objects.filter(location__city__iexact=city_to_use)
            with transaction.atomic():
                masjid.prayertime_set.add(*matching_prayer_times)
        return masjid

    def update(self, instance, validated_data):
        address_data = validated_data.pop('address', None)
        if address_data:
            address = instance.address
            for attr, value in address_data.items():
                setattr(address, attr, value)
            address.save()

         # If the address has a city, update the prayer times based on city changes
        if instance.address and instance.address.city:
            # 1. Find mismatched PrayerTimes (old city)
            mismatched_prayer_times = PrayerTime.objects.filter(
                masjids=instance
            ).exclude(location__city=instance.address.city)

            # Bulk remove using `remove(*mismatched_prayer_times)`
            if mismatched_prayer_times:
                with transaction.atomic():
                    instance.prayertime_set.remove(*mismatched_prayer_times)

            # 2. Link the Masjid to PrayerTimes in the new city
            matching_prayer_times = PrayerTime.objects.filter(location__city__iexact=instance.address.city)
            with transaction.atomic():
                instance.prayertime_set.add(*matching_prayer_times)
        return super().update(instance, validated_data)


class SuggestionMasjidModificationSerializer(serializers.ModelSerializer):
    suggestion_masjid = serializers.SlugRelatedField(
        queryset=Masjid.objects.all(),
        slug_field='uuid'  # Use 'uuid' for lookups instead of the primary key
    )
    address = AddressSerializer()  # Nested serializer for Address

    class Meta:
        model = SuggestionMasjidModification
        fields = [
            # Base fields from ObjectBase
            'uuid', 'created_at', 'updated_at',
            # Fields from SuggestionMasjidModification
            'id', 'name', 'suggestion_masjid', 'address', 'telephone', 'photo', 'cover', 
            'size', 'message', 'is_active', 'parking', 'disabled_access', 'ablution_room', 
            'woman_space', 'adult_courses', 'children_courses', 'salat_al_eid', 
            'salat_al_janaza', 'iftar_ramadhan', 'itikef', 'fajr_iqama', 'dhuhr_iqama', 
            'asr_iqama', 'maghrib_iqama', 'isha_iqama', 'jumuah_time', 'first_timeslot_jumuah', 
            'eid_time'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Handle the address
        address_data = validated_data.pop('address', None)
        if address_data:
            address = Address.objects.create(**address_data)
            validated_data['address'] = address

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Handle address updates
        address_data = validated_data.pop('address', None)
        if address_data:
            if instance.address:
                for key, value in address_data.items():
                    setattr(instance.address, key, value)
                instance.address.save()
            else:
                instance.address = Address.objects.create(**address_data)

        return super().update(instance, validated_data)
