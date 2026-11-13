from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from core.permissions import IsAdminOrManagerOrAssistantOfPrayerTime
from .models import PrayerTime, JumuahPrayerTime, EidPrayerTime, IqamaTime
from prayertime.serializers import (EidPrayerTimeSerializer, IqamaTimeSerializer, JumuahPrayerTimeSerializer,
                                    PrayerTimeSerializer)


class PrayerTimeViewSet(viewsets.ModelViewSet):
    serializer_class = PrayerTimeSerializer

    def get_queryset(self):
        return PrayerTime.objects.all()

    def get_permissions(self):
        if self.action in ('destroy',):
            self.permission_classes = [IsAuthenticated, IsAdminUser]
        elif self.action in ('create', 'update', 'partial_update'):
            self.permission_classes = [IsAuthenticated, IsAdminOrManagerOrAssistantOfPrayerTime]
        else:
            self.permission_classes = []
        return super().get_permissions()

class JumuahPrayerTimeViewSet(viewsets.ModelViewSet):
    queryset = JumuahPrayerTime.objects.all()
    serializer_class = JumuahPrayerTimeSerializer

    def get_permissions(self):
        if self.action in ('destroy',):
            self.permission_classes = [IsAuthenticated, IsAdminUser]
        elif self.action in ('create', 'update', 'partial_update'):
            self.permission_classes = [IsAuthenticated, IsAdminOrManagerOrAssistantOfPrayerTime]
        else:
            self.permission_classes = []
        return super().get_permissions()

class EidPrayerTimeViewSet(viewsets.ModelViewSet):
    queryset = EidPrayerTime.objects.all()
    serializer_class = EidPrayerTimeSerializer

    def get_permissions(self):
        if self.action in ('destroy',):
            self.permission_classes = [IsAuthenticated, IsAdminUser]
        elif self.action in ('create', 'update', 'partial_update'):
            self.permission_classes = [IsAuthenticated, IsAdminOrManagerOrAssistantOfPrayerTime]
        else:
            self.permission_classes = []
        return super().get_permissions()


class IqamaTimeViewSet(viewsets.ModelViewSet):
    queryset = IqamaTime.objects.all()
    serializer_class = IqamaTimeSerializer
    
    def get_permissions(self):
        if self.action in ('destroy',):
            self.permission_classes = [IsAuthenticated, IsAdminUser]
        elif self.action in ('update', 'partial_update'):
            self.permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            self.permission_classes = []
        return super().get_permissions()
