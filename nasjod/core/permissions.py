from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

from masjid.models import Masjid


# General Role Check Permissions

class IsManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.managed_masjids.exists()


class IsAssistant(BasePermission):
    def has_permission(self, request, view):
        return request.user.assisted_masjids.exists()


class IsImam(BasePermission):
    def has_permission(self, request, view):
        return request.user.led_masjids.exists()


class IsMousalli(BasePermission):
    def has_permission(self, request, view):
        return request.user.attended_masjids.exists()


# Specific Masjid Check Permissions    

class IsManagerOfMasjid(BasePermission):
    def has_permission(self, request, view):
        masjid_uuid = view.kwargs.get(settings.MASJID_LOOKUP_FIELD) or view.kwargs.get("uuid")
        if not masjid_uuid:
            return False
        try:
            masjid = Masjid.objects.get(uuid=masjid_uuid)
            return masjid.managers.filter(id=request.user.id).exists()
        except Masjid.DoesNotExist:
            return False


class IsAssistantOfMasjid(BasePermission):
    def has_permission(self, request, view):
        masjid_uuid = view.kwargs.get(settings.MASJID_LOOKUP_FIELD) or view.kwargs.get("uuid")
        if not masjid_uuid:
            return False
        try:
            masjid = Masjid.objects.get(uuid=masjid_uuid)
            return request.user in masjid.assistants.all()
        except Masjid.DoesNotExist:
            return False

class IsManagerOrAssistant(BasePermission):
    def has_permission(self, request, view):
        masjid_uuid = view.kwargs.get(settings.MASJID_LOOKUP_FIELD) or view.kwargs.get("uuid")
        if not masjid_uuid:
            return False
        try:
            masjid = Masjid.objects.get(uuid=masjid_uuid)
            return masjid.managers.filter(id=request.user.id).exists() or masjid.assistants.filter(id=request.user.id).exists()
        except Masjid.DoesNotExist:
            return False

class IsAdminOrManagerOrAssistant(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        masjid_uuid = view.kwargs.get(settings.MASJID_LOOKUP_FIELD) or view.kwargs.get("uuid")
        if not masjid_uuid:
            return False
        try:
            masjid = Masjid.objects.get(uuid=masjid_uuid)
            return masjid.managers.filter(id=request.user.id).exists() or masjid.assistants.filter(id=request.user.id).exists()
        except Masjid.DoesNotExist:
            return False

class IsImamOfMasjid(BasePermission):
    def has_permission(self, request, view):
        masjid_uuid = view.kwargs.get(settings.MASJID_LOOKUP_FIELD) or view.kwargs.get("uuid")
        if not masjid_uuid:
            return False
        try:
            masjid = Masjid.objects.get(uuid=masjid_uuid)
            return request.user in masjid.imams.all()
        except Masjid.DoesNotExist:
            return False


class IsMousalliOfMasjid(BasePermission):
    def has_permission(self, request, view):
        masjid_uuid = view.kwargs.get(settings.MASJID_LOOKUP_FIELD) or view.kwargs.get("uuid")
        if not masjid_uuid:
            return False
        try:
            masjid = Masjid.objects.get(uuid=masjid_uuid)
            return request.user in masjid.mousallis.all()
        except Masjid.DoesNotExist:
            return False

class FrontendAppPermission(BasePermission):
    """
    Custom permission to check if the request is authenticated using an app token.
    """

    def has_permission(self, request, view):
        # Check if the request was authenticated by AppTokenAuthentication
        if not request.auth:
            return False

        # Validate the app claim in the token
        app_name = request.auth.get("app")
        return app_name == "frontend"
