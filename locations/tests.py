from datetime import timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from .models import Mood, Location, Visit, Collectible, Review


class LocationsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Usuario principal
        self.user = User.objects.create_user(
            username="tester",
            email="test@vibe.com",
            password="pass12345",
            is_active=True,
        )

        # Otro usuario (para probar 403)
        self.other_user = User.objects.create_user(
            username="other",
            email="other@vibe.com",
            password="pass12345",
            is_active=True,
        )

        # Mood + Location aprobada con QR
        self.mood = Mood.objects.create(
            name="Aventura", slug="aventura", is_active=True
        )
        self.location = Location.objects.create(
            name="Test Bar",
            description="Lugar de prueba",
            city="Santiago",
            status=Location.Status.APPROVED,
            qr_code="QR123",
        )
        self.location.moods.add(self.mood)

        # Rutas base (según tu urls actual)
        self.locations_list_url = "/api/v1/locations/"
        self.checkin_url = "/api/v1/visits/checkin/"

    def test_locations_list_public_ok(self):
        """GET /locations/ debe ser público y devolver 200."""
        res = self.client.get(self.locations_list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_checkin_requires_auth(self):
        """POST /visits/checkin/ sin auth => 401."""
        res = self.client.post(self.checkin_url, {"qr_code": "QR123"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", res.data)
        self.assertEqual(res.data["error"]["code"], "UNAUTHORIZED")
        self.assertIn("request_id", res.data)
        self.assertIn("X-Request-ID", res)

    def test_checkin_creates_visit_and_collectible_first_time(self):
        """Primer checkin: crea visita ACTIVE y collectible_awarded=True."""
        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.checkin_url, {"qr_code": "QR123"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.assertIn("visit_id", res.data)
        self.assertIn("collectible_awarded", res.data)
        self.assertTrue(res.data["collectible_awarded"])

        visit_id = res.data["visit_id"]
        visit = Visit.objects.get(id=visit_id)
        self.assertEqual(visit.user, self.user)
        self.assertEqual(visit.location, self.location)
        self.assertEqual(visit.status, Visit.Status.ACTIVE)

        self.assertTrue(
            Collectible.objects.filter(user=self.user, location=self.location).exists()
        )

    def test_checkin_second_time_does_not_conflict_and_does_not_duplicate_collectible(
        self,
    ):
        """Segundo checkin mismo lugar: 201 y collectible_awarded=False (sin duplicar)."""
        # Pre-crea collectible
        Collectible.objects.create(user=self.user, location=self.location)

        self.client.force_authenticate(user=self.user)
        res = self.client.post(self.checkin_url, {"qr_code": "QR123"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("collectible_awarded", res.data)
        self.assertFalse(res.data["collectible_awarded"])

        # Sigue existiendo solo 1 collectible
        self.assertEqual(
            Collectible.objects.filter(user=self.user, location=self.location).count(),
            1,
        )

    def test_checkin_invalid_qr_returns_404(self):
        """QR inválido => 404."""
        self.client.force_authenticate(user=self.user)
        res = self.client.post(
            self.checkin_url, {"qr_code": "NO_EXISTE"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_checkout_forbidden_for_other_user(self):
        """Checkout de visita ajena => 403."""
        visit = Visit.objects.create(
            user=self.user, location=self.location, status=Visit.Status.ACTIVE
        )

        self.client.force_authenticate(user=self.other_user)
        checkout_url = f"/api/v1/visits/{visit.id}/checkout/"
        res = self.client.post(
            checkout_url,
            {"service_score": 5, "quality_score": 5, "price_score": 5, "vibe_score": 5},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_checkout_persists_review_and_completes_visit(self):
        """Checkout válido: crea Review y marca Visit COMPLETED."""
        visit = Visit.objects.create(
            user=self.user, location=self.location, status=Visit.Status.ACTIVE
        )

        self.client.force_authenticate(user=self.user)
        checkout_url = f"/api/v1/visits/{visit.id}/checkout/"
        res = self.client.post(
            checkout_url,
            {
                "service_score": 5,
                "quality_score": 4,
                "price_score": 3,
                "vibe_score": 5,
                "comment": "Excelente!",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("review_id", res.data)

        # Visit debe quedar completada
        visit.refresh_from_db()
        self.assertEqual(visit.status, Visit.Status.COMPLETED)
        self.assertIsNotNone(visit.checked_out_at)

        # Review creada y ligada 1-1 a Visit
        self.assertTrue(
            Review.objects.filter(
                visit=visit, user=self.user, location=self.location
            ).exists()
        )

    def test_vibe_match_endpoint_requires_auth(self):
        """GET /locations/<id>/vibe-match/ sin auth => 401"""
        url = f"/api/v1/locations/{self.location.id}/vibe-match/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_vibe_match_no_history_returns_default_70(self):
        """Usuario autenticado sin visitas COMPLETED => 70."""
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/locations/{self.location.id}/vibe-match/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["vibe_match"], 70)

    def test_vibe_match_with_history_overlap_returns_gt_70(self):
        """Con historial COMPLETED y mismo mood => match alto (esperable > 70)."""
        # Creamos una visita COMPLETED a la misma location (comparte moods)
        Visit.objects.create(
            user=self.user,
            location=self.location,
            status=Visit.Status.COMPLETED,
        )

        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/locations/{self.location.id}/vibe-match/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # En este caso debería dar 100 (1/1 moods overlap), clamp 30..100
        self.assertTrue(res.data["vibe_match"] > 70)


class HeatmapAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="heat-user",
            email="heat@example.com",
            password="pass12345",
            is_active=True,
        )

        self.location_restaurant = Location.objects.create(
            name="Heat Restaurant",
            city="Santiago",
            category=Location.Category.RESTAURANT,
            status=Location.Status.APPROVED,
            latitude=-33.4489,
            longitude=-70.6693,
            qr_code="HEAT-R1",
        )
        self.location_bar = Location.objects.create(
            name="Heat Bar",
            city="Santiago",
            category=Location.Category.BAR,
            status=Location.Status.APPROVED,
            latitude=-33.4560,
            longitude=-70.6483,
            qr_code="HEAT-B1",
        )

        now = timezone.now()
        # 2 visits on the same day/location -> value should aggregate to 2
        visit_rest_1 = Visit.objects.create(
            user=self.user,
            location=self.location_restaurant,
            status=Visit.Status.COMPLETED,
        )
        Visit.objects.filter(id=visit_rest_1.id).update(
            checked_in_at=now - timedelta(hours=2)
        )
        visit_rest_2 = Visit.objects.create(
            user=self.user,
            location=self.location_restaurant,
            status=Visit.Status.COMPLETED,
        )
        Visit.objects.filter(id=visit_rest_2.id).update(
            checked_in_at=now - timedelta(hours=1)
        )
        # 1 recent visit to validate short live windows.
        visit_rest_3 = Visit.objects.create(
            user=self.user,
            location=self.location_restaurant,
            status=Visit.Status.ACTIVE,
        )
        Visit.objects.filter(id=visit_rest_3.id).update(
            checked_in_at=now - timedelta(minutes=5)
        )
        # 1 visit for a different category/location
        visit_bar = Visit.objects.create(
            user=self.user,
            location=self.location_bar,
            status=Visit.Status.ACTIVE,
        )
        Visit.objects.filter(id=visit_bar.id).update(
            checked_in_at=now - timedelta(days=1)
        )

        self.heatmap_url = "/api/v1/heatmap/"

    def test_heatmap_is_public_and_returns_contract(self):
        res = self.client.get(self.heatmap_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertIn("points", res.data)
        self.assertIn("min", res.data)
        self.assertIn("max", res.data)
        self.assertIn("normalizationMeta", res.data)
        self.assertIn("appliedFilters", res.data)
        self.assertIn("generated_at", res.data)
        self.assertIn("request_id", res.data)
        self.assertEqual(res.data["normalizationMeta"]["mode"], "none")

        self.assertTrue(len(res.data["points"]) >= 2)
        first_point = res.data["points"][0]
        self.assertIn("value", first_point)
        self.assertIn("unit", first_point)
        self.assertIn("lat", first_point)
        self.assertIn("lng", first_point)
        self.assertIn("timestamp", first_point)
        self.assertEqual(first_point["unit"], "visits")

    def test_heatmap_threshold_filters_low_values(self):
        res = self.client.get(self.heatmap_url, {"threshold": 2})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        points = res.data["points"]
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["value"], 3)
        self.assertEqual(points[0]["location"]["id"], self.location_restaurant.id)

    def test_heatmap_category_filter(self):
        res = self.client.get(self.heatmap_url, {"category": "bar"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["points"]), 1)
        self.assertEqual(
            res.data["points"][0]["location"]["id"], self.location_bar.id
        )

    def test_heatmap_invalid_palette_returns_400(self):
        res = self.client.get(self.heatmap_url, {"palette": "rainbow"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", res.data)
        self.assertEqual(res.data["error"]["code"], "INVALID_FILTERS")
        self.assertIn("request_id", res.data)

    def test_heatmap_time_window_filters_recent_points(self):
        res = self.client.get(self.heatmap_url, {"time_window": "15m"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        points = res.data["points"]
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["location"]["id"], self.location_restaurant.id)
        self.assertEqual(points[0]["value"], 1)
        self.assertEqual(res.data["appliedFilters"]["time_window"], "15m")

    def test_heatmap_time_window_cannot_be_combined_with_from_to(self):
        now_iso = timezone.now().isoformat()
        res = self.client.get(
            self.heatmap_url,
            {"time_window": "1h", "from": now_iso},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"]["code"], "INVALID_FILTERS")
        self.assertIn("time_window", res.data["error"]["details"])

    def test_heatmap_uses_request_id_from_header(self):
        res = self.client.get(self.heatmap_url, HTTP_X_REQUEST_ID="req-123")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["request_id"], "req-123")
        self.assertEqual(res["X-Request-ID"], "req-123")

    def test_heatmap_generates_and_returns_request_id_header(self):
        res = self.client.get(self.heatmap_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("X-Request-ID", res)
        self.assertTrue(res["X-Request-ID"])
        self.assertEqual(res.data["request_id"], res["X-Request-ID"])
