from rest_framework import serializers
from django.contrib.gis.geos import Point

from core.models import Address
from core.serializers import AddressSerializer
from masjid.models import Masjid
from .models import JumuahPrayerTime, EidPrayerTime, IqamaTime, PrayerTime


class BasePrayerTimeSerializer(serializers.ModelSerializer):
    hijri_date = serializers.CharField(read_only=True)
    location = AddressSerializer(required=False, allow_null=True)
    masjids = serializers.SlugRelatedField(
        many=True,
        slug_field='uuid',  # Use the UUID for masjid
        queryset=Masjid.objects.all()
    )
    remove_masjids = serializers.SlugRelatedField(
        many=True,
        slug_field='uuid',  # Use the UUID for masjids to be removed
        queryset=Masjid.objects.all(),
        required=False,  # Optional field for removing masjids
        write_only=True  # This field is only for writing, not for reading
    )


    class Meta:
        abstract = True

    def create(self, validated_data):
        # Handle location (Address)
        address_data = validated_data.pop('location', None)
        if address_data:
            # Check if an address with the same coordinates exists
            try:
                address = Address.objects.get(coordinates=address_data.get('coordinates'))
            except Address.DoesNotExist:
                # If not found, create a new address
                address = Address.objects.create(**address_data)
            validated_data['location'] = address

        # Convert list of UUIDs to Masjid instances
        masjids = validated_data.pop('masjids', [])
        # Create the prayer time instance (e.g., PrayerTime or EidPrayerTime)
        instance = super().create(validated_data)
        # Set the many-to-many relationship with the masjids
        instance.masjids.set(masjids)

        return instance
    
    def update(self, instance, validated_data):
        # Handle location (Address)
        address_data = validated_data.pop('location', None)
        if address_data:
            try:
                address = Address.objects.get(coordinates=address_data.get('coordinates'))
            except Address.DoesNotExist:
                address = Address.objects.create(**address_data)
            instance.location = address

        # Add new masjids to the existing masjids (without replacing)
        new_masjids = validated_data.pop('masjids', [])
        if new_masjids:
            for masjid in new_masjids:
                instance.masjids.add(masjid)  # Add new masjids to the existing relationship

        # Remove masjids if 'remove_masjids' flag is provided
        remove_masjids = validated_data.pop('remove_masjids', [])
        if remove_masjids:
            for masjid in remove_masjids:
                instance.masjids.remove(masjid)  # Remove specific masjids

        # Update the other fields in the instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Save the updated instance
        instance.save()

        return instance


class PrayerTimeSerializer(BasePrayerTimeSerializer):
    class Meta:
        model = PrayerTime
        fields = '__all__'


class PrayerTimeMasjidSerializer(BasePrayerTimeSerializer):
    class Meta:
        model = PrayerTime
        fields = ("date", "hijri_date", 
                  "fajr",
                  "sunrise",
                  "dhuhr",
                  "asr",
                  "maghrib",
                  "isha",
                )



class EidPrayerTimeSerializer(BasePrayerTimeSerializer):
    class Meta:
        model = EidPrayerTime
        fields = '__all__'


class JumuahPrayerTimeSerializer(serializers.ModelSerializer):
    masjid = serializers.SlugRelatedField(
        slug_field='uuid',  # Use 'uuid' for serialization
        queryset=Masjid.objects.all()
    )

    class Meta:
        model = JumuahPrayerTime
        fields = ('date', 'jumuah_time', 'first_timeslot_jumuah', 'masjid')


class JumuahPrayerTimeMasjidSerializer(serializers.ModelSerializer):
    class Meta:
        model = JumuahPrayerTime
        fields = ("date", "hijri_date", "jumuah_time", 'first_timeslot_jumuah',)
        read_only_fields = ('hijri_date',)


class IqamaTimeSerializer(serializers.ModelSerializer):
    """Serializer for IqamaTime with masjid represented by its UUID."""
    masjid = serializers.SlugRelatedField(
        slug_field='uuid',  # Use 'uuid' for serialization
        queryset=Masjid.objects.all()
    )

    class Meta:
        model = IqamaTime
        fields = ('date', 'fajr_iqama', 'dhuhr_iqama', 'dhuhr_iqama_from_asr', 'dhuhr_iqama_hour', 'dhuhr_iqama_in_hours', 'asr_iqama', 
                'maghrib_iqama', 'isha_iqama', 'masjid')

class IqamaTimeMasjidSerializer(serializers.ModelSerializer):
    """Serializer for IqamaTime used in MasjidSerializer to avoid nested masjid representation."""
    class Meta:
        model = IqamaTime
        fields = ("date", "hijri_date", 
                "fajr_iqama",
                "dhuhr_iqama",
                'dhuhr_iqama_from_asr',
                'dhuhr_iqama_hour',
                'dhuhr_iqama_in_hours',
                "asr_iqama",
                "maghrib_iqama",
                "isha_iqama",
                )
        read_only_fields = ('hijri_date',)
