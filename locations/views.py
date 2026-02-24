# locations/views.py
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .utils import calculate_vibe_match

from .models import Mood, Location, Visit, Collectible, Favorite, Review  # ✅ + Review
from .serializers import (
    MoodSerializer,
    LocationListSerializer,
    LocationDetailSerializer,
    VisitCheckinSerializer,
    VisitCheckoutSerializer,
    VisitSerializer,
    CollectibleSerializer,
    FavoriteToggleSerializer,
    FavoriteSerializer,
)


class MoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Mood.objects.filter(is_active=True)
    serializer_class = MoodSerializer
    permission_classes = (AllowAny,)


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (AllowAny,)

    def get_queryset(self):
        qs = (
            Location.objects.filter(status=Location.Status.APPROVED)
            .prefetch_related("moods")
            .order_by("-created_at")  # 🔥 agregado
        )

        mood = self.request.query_params.get("mood")
        if mood:
            qs = qs.filter(moods__slug=mood)

        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return LocationDetailSerializer
        return LocationListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)


class VibeMatchAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, id):
        try:
            location = Location.objects.get(id=id, status=Location.Status.APPROVED)
        except Location.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        match = calculate_vibe_match(request.user, location)
        return Response({"vibe_match": match}, status=status.HTTP_200_OK)


class VisitCheckinAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    def post(self, request):
        serializer = VisitCheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            location = Location.objects.get(
                qr_code=serializer.validated_data["qr_code"],
                status=Location.Status.APPROVED,
            )
        except Location.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # ✅ Antes: si ya tenía collectible => 409
        # ✅ Ahora: permitir revisita; solo no crear collectible duplicado
        collectible_awarded = False
        if not Collectible.objects.filter(
            user=request.user, location=location
        ).exists():
            Collectible.objects.create(
                user=request.user, location=location, awarded_at=timezone.now()
            )
            collectible_awarded = True

        visit = Visit.objects.create(
            user=request.user,
            location=location,
            status=Visit.Status.ACTIVE,
            checked_in_at=timezone.now(),
        )

        return Response(
            {"visit_id": visit.id, "collectible_awarded": collectible_awarded},
            status=status.HTTP_201_CREATED,
        )


class VisitCheckoutAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    @transaction.atomic  # ✅ para que Review + Visit se guarden juntos
    def post(self, request, id):
        try:
            visit = Visit.objects.get(id=id)
        except Visit.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if visit.user != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        if visit.status != Visit.Status.ACTIVE:
            return Response(status=status.HTTP_409_CONFLICT)

        serializer = VisitCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # ✅ NUEVO: persistir rating en Review (si ya existe, evitamos duplicado)
        if hasattr(visit, "review"):
            # ya fue calificada (por seguridad)
            return Response(
                {"error": "This visit is already reviewed."},
                status=status.HTTP_409_CONFLICT,
            )

        data = serializer.validated_data
        review = Review.objects.create(
            user=request.user,
            location=visit.location,
            visit=visit,
            service_score=data["service_score"],
            quality_score=data["quality_score"],
            price_score=data["price_score"],
            vibe_score=data["vibe_score"],
            comment=data.get("comment", ""),
        )

        visit.status = Visit.Status.COMPLETED
        visit.checked_out_at = timezone.now()
        visit.save()

        return Response({"review_id": review.id}, status=status.HTTP_200_OK)


class MyVisitsAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        qs = Visit.objects.filter(user=request.user).select_related("location")
        return Response(VisitSerializer(qs, many=True).data)


class MyCollectiblesAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        qs = Collectible.objects.filter(user=request.user).select_related("location")
        return Response(CollectibleSerializer(qs, many=True).data)


class FavoriteToggleAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = FavoriteToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            location = Location.objects.get(id=serializer.validated_data["location_id"])
        except Location.DoesNotExist:
            return Response(
                {"error": "Location not found"}, status=status.HTTP_404_NOT_FOUND
            )

        fav, created = Favorite.objects.get_or_create(
            user=request.user, location=location
        )
        if not created:
            fav.delete()
            return Response(status=status.HTTP_200_OK)

        return Response(status=status.HTTP_201_CREATED)


class MyFavoritesAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        qs = Favorite.objects.filter(user=request.user).select_related("location")
        return Response(FavoriteSerializer(qs, many=True).data)


class FavoriteDeleteAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def delete(self, request, location_id):
        Favorite.objects.filter(user=request.user, location_id=location_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
