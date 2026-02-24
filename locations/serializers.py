from urllib import request
from rest_framework import serializers
from .models import Mood, Location, Visit, Collectible, Favorite, Promotion
from .utils import calculate_vibe_match 

class MoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mood
        fields = ("id", "name", "slug")


class LocationListSerializer(serializers.ModelSerializer):
    moods = serializers.SlugRelatedField(many=True, read_only=True, slug_field="slug")

    class Meta:
        model = Location
        fields = ("id", "name", "city", "image_url", "moods", "vibe_match_score")


class LocationDetailSerializer(serializers.ModelSerializer):
    moods = MoodSerializer(many=True, read_only=True)
    vibe_match = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Location
        fields = (
            "id",
            "name",
            "description",
            "city",
            "address",
            "latitude",
            "longitude",
            "image_url",
            "moods",
            "vibe_match",
        )

    def get_vibe_match(self, obj):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            return calculate_vibe_match(request.user, obj)
        return None


class VibeMatchSerializer(serializers.Serializer):
    vibe_match = serializers.IntegerField(default=50)


class VisitCheckinSerializer(serializers.Serializer):
    qr_code = serializers.CharField(allow_blank=False)


class VisitCheckoutSerializer(serializers.Serializer):
    # Se validan los scores aquí.
    # El guardado se realiza en el modelo Review desde la vista de checkout.
    service_score = serializers.IntegerField(min_value=1, max_value=5)
    quality_score = serializers.IntegerField(min_value=1, max_value=5)
    price_score = serializers.IntegerField(min_value=1, max_value=5)
    vibe_score = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True)


class VisitSerializer(serializers.ModelSerializer):
    location = LocationListSerializer(read_only=True)

    class Meta:
        model = Visit
        fields = ("id", "location", "status", "checked_in_at", "checked_out_at")


class CollectibleSerializer(serializers.ModelSerializer):
    location = LocationListSerializer(read_only=True)

    class Meta:
        model = Collectible
        fields = ("id", "location", "awarded_at")


class FavoriteToggleSerializer(serializers.Serializer):
    location_id = serializers.IntegerField(min_value=1)


class FavoriteSerializer(serializers.ModelSerializer):
    location = LocationListSerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ("id", "location", "created_at")


class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = ("id", "title", "is_active", "created_at")
