from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MoodViewSet,
    LocationViewSet,
    VibeMatchAPIView,
    HeatmapAPIView,
    VisitCheckinAPIView,
    VisitCheckoutAPIView,
    MyVisitsAPIView,
    MyCollectiblesAPIView,
    FavoriteToggleAPIView,
    MyFavoritesAPIView,
    FavoriteDeleteAPIView,
)

router = DefaultRouter()
router.register("moods", MoodViewSet, basename="moods")
router.register("locations", LocationViewSet, basename="locations")

urlpatterns = [
    path("", include(router.urls)),

    # ✅ Slash final (consistente con DRF)
    path("locations/<int:id>/vibe-match/", VibeMatchAPIView.as_view()),
    path("heatmap/", HeatmapAPIView.as_view()),
    path("visits/checkin/", VisitCheckinAPIView.as_view()),
    path("visits/<int:id>/checkout/", VisitCheckoutAPIView.as_view()),
    path("visits/me/", MyVisitsAPIView.as_view()),
    path("me/collectibles/", MyCollectiblesAPIView.as_view()),
    path("favorites/", FavoriteToggleAPIView.as_view()),
    path("favorites/me/", MyFavoritesAPIView.as_view()),
    path("favorites/<int:location_id>/", FavoriteDeleteAPIView.as_view()),
]
