from rest_framework.throttling import AnonRateThrottle


class CreateMasjidAnonThrottle(AnonRateThrottle):
    scope = 'anon_create_masjid'

class CreateSuggestionMasjidModificationAnonThrottle(AnonRateThrottle):
    scope = 'anon_create_suggestion_masjid_modification'

