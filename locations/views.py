# locations/views.py
import logging
import time
from datetime import timedelta
from django.db import transaction
from django.db.models import Count, Max, Min
from django.db.models.functions import TruncDay
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .utils import calculate_vibe_match

from .models import Mood, Location, Visit, Collectible, Favorite, Review
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
    HeatmapFilterSerializer,
)
from api.error_utils import (
    create_error_response,
    get_request_id,
    log_error,
    ErrorResponseBuilder,
    server_error,
)

logger = logging.getLogger(__name__)

HEATMAP_TIME_WINDOWS = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
}


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


class HeatmapAPIView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        request_id = get_request_id(request)
        started_at = time.perf_counter()
        try:
            raw_categories = []
            for raw_value in request.query_params.getlist("category"):
                raw_categories.extend(
                    [category.strip() for category in raw_value.split(",") if category.strip()]
                )

            source = request.query_params.get("source")
            if source == "checkins":
                source = "visits"

            filter_payload = {
                "source": source or "visits",
                "threshold": request.query_params.get("threshold", 0),
                "palette": request.query_params.get("palette", "viridis"),
            }
            time_window = request.query_params.get("time_window")
            if time_window:
                filter_payload["time_window"] = time_window
            from_query = request.query_params.get("from")
            to_query = request.query_params.get("to")
            if from_query:
                filter_payload["from_datetime"] = from_query
            if to_query:
                filter_payload["to_datetime"] = to_query
            if raw_categories:
                filter_payload["category"] = raw_categories

            filter_serializer = HeatmapFilterSerializer(data=filter_payload)
            if not filter_serializer.is_valid():
                elapsed_ms = round((time.perf_counter() - started_at) * 1000)
                log_error(
                    "INVALID_FILTERS",
                    request_id=request_id,
                    latency_ms=elapsed_ms,
                    errors=str(filter_serializer.errors),
                )
                return (
                    ErrorResponseBuilder("INVALID_FILTERS")
                    .with_message("Invalid heatmap filters.")
                    .with_details(dict(filter_serializer.errors))
                    .with_request_id(request_id)
                    .build()
                )
            filters = filter_serializer.validated_data

            queryset = Visit.objects.filter(
                location__status=Location.Status.APPROVED,
                location__latitude__isnull=False,
                location__longitude__isnull=False,
            )

            time_window = filters.get("time_window")
            from_datetime = filters.get("from_datetime")
            to_datetime = filters.get("to_datetime")
            if time_window:
                now = timezone.now()
                from_datetime = now - HEATMAP_TIME_WINDOWS[time_window]
                to_datetime = now

            if from_datetime:
                queryset = queryset.filter(checked_in_at__gte=from_datetime)
            if to_datetime:
                queryset = queryset.filter(checked_in_at__lte=to_datetime)

            categories = filters.get("category")
            if categories:
                queryset = queryset.filter(location__category__in=categories)

            threshold = filters.get("threshold", 0)
            points_qs = (
                queryset.annotate(timestamp=TruncDay("checked_in_at"))
                .values(
                    "location_id",
                    "location__name",
                    "location__city",
                    "location__latitude",
                    "location__longitude",
                    "timestamp",
                )
                .annotate(value=Count("id"))
                .filter(value__gte=threshold)
                .order_by("timestamp", "location_id")
            )

            points = []
            values = []
            for point in points_qs:
                value = point["value"]
                values.append(value)
                timestamp = point["timestamp"]
                points.append(
                    {
                        "value": value,
                        "unit": "visits",
                        "lat": float(point["location__latitude"]),
                        "lng": float(point["location__longitude"]),
                        "timestamp": timestamp.isoformat() if timestamp else None,
                        "location": {
                            "id": point["location_id"],
                            "name": point["location__name"],
                            "city": point["location__city"],
                        },
                    }
                )

            aggregate = points_qs.aggregate(min=Min("value"), max=Max("value"))
            generated_at = timezone.now()
            response_payload = {
                "points": points,
                "min": aggregate["min"] if values else 0,
                "max": aggregate["max"] if values else 0,
                "normalizationMeta": {
                    "mode": "none",
                    "note": "Raw visit counts per location per day.",
                },
                "appliedFilters": {
                    "from": from_datetime.isoformat() if from_datetime else None,
                    "to": to_datetime.isoformat() if to_datetime else None,
                    "source": filters.get("source", "visits"),
                    "category": categories or [],
                    "threshold": threshold,
                    "palette": filters.get("palette", "viridis"),
                    "time_window": time_window,
                },
                "generated_at": generated_at.isoformat(),
                "request_id": request_id,
            }
            elapsed_ms = round((time.perf_counter() - started_at) * 1000)
            logger.info(
                "heatmap_fetch_success latency_ms=%s request_id=%s points=%s threshold=%s categories=%s time_window=%s",
                elapsed_ms,
                request_id,
                len(points),
                threshold,
                ",".join(categories or []),
                time_window,
            )
            return Response(response_payload, status=status.HTTP_200_OK)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started_at) * 1000)
            log_error(
                "HEATMAP_FETCH_FAILED",
                request_id=request_id,
                latency_ms=elapsed_ms,
                exception=str(exc),
            )
            return server_error(request, "Unable to fetch heatmap data.")


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
