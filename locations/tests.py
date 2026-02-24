from django.test import TestCase
from django.contrib.auth.models import User
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
