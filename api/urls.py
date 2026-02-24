from django.urls import path, include

urlpatterns = [
    # Auth (accounts maneja register/login/refresh/me)
    path("auth/", include("accounts.urls")),

    # Locations domain (MVP)
    path("", include("locations.urls")),  # aquí cuelgas moods/locations/visits/favorites/collectibles
]
