from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from core.throttling import CreateMasjidAnonThrottle, CreateSuggestionMasjidModificationAnonThrottle

import logging

logger = logging.getLogger(__name__)

from .models import Masjid, SuggestionMasjidModification
from .serializers import (MasjidSerializer, MasjidMapSerializer, SuggestionMasjidModificationSerializer)
from .filters import MasjidFilter
from core.permissions import IsManagerOfMasjid


class MasjidViewSet(viewsets.ModelViewSet):
    queryset = Masjid.objects.all()
    serializer_class = MasjidSerializer
    filterset_class = MasjidFilter
    lookup_field = "uuid"
    ordering_fields = ['name', 'created_at', 'updated_at'] 
    
    def get_permissions(self):
        if self.action in ('destroy',):
            self.permission_classes = [IsAuthenticated, IsAdminUser]
        elif self.action in ('update', 'partial_update'):
            self.permission_classes = [IsAuthenticated, IsManagerOfMasjid]
        else:
            self.permission_classes = []
        return super().get_permissions()

    def get_throttles(self):
        if self.action == 'create':
            return [CreateMasjidAnonThrottle()]
        return super().get_throttles()
    
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'], url_path='map')
    def map_data(self, request):
        """
        Get all mosques for map display with only essential fields (name, lat, lon).
        Returns all mosques without pagination for optimal map performance.
        """
        # Get all active mosques with coordinates
        queryset = self.get_queryset().filter(
            is_active=True,
            address__coordinates__isnull=False
        ).select_related('address')
        
        # Apply any filters if needed (e.g., by city, state)
        queryset = self.filter_queryset(queryset)
        
        # Serialize with lightweight serializer
        serializer = MasjidMapSerializer(queryset, many=True)
        
        return Response(serializer.data)

class SuggestionMasjidModificationViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing SuggestionMasjidModification instances.
    """
    queryset = SuggestionMasjidModification.objects.all()
    serializer_class = SuggestionMasjidModificationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'suggestion_masjid__uuid']
    lookup_field = "uuid"

    def get_permissions(self):
        if self.action in ('destroy', 'update',):
            self.permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            self.permission_classes = []
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    def get_throttles(self):
        if self.action == 'create':
            return [CreateSuggestionMasjidModificationAnonThrottle()]
        return super().get_throttles()
