"""
Tests para el sistema de autenticación mejorado.
Cubre: registro, verificación email, login, password reset, sessions, rate limiting.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta

from .models import (
    EmailVerificationToken,
    PasswordResetToken,
    UserSession,
    LoginAttempt,
)
from .utils import create_email_verification_token, create_password_reset_token


class AuthenticationFlowTests(TestCase):
    """Tests del flujo completo de autenticación."""

    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/v1/auth/register/"
        self.verify_url = "/api/v1/auth/verify-email/"
        self.login_url = "/api/v1/auth/login/"
        self.me_url = "/api/v1/auth/me/"

    def test_register_creates_inactive_user(self):
        """Test: Registro crea usuario con is_active=False."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = self.client.post(self.register_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("message", response.data)
        self.assertIn("user", response.data)

        # Verificar usuario creado
        user = User.objects.get(username="testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertFalse(user.is_active)  # Debe estar inactivo

        # Verificar token creado
        self.assertTrue(
            EmailVerificationToken.objects.filter(user=user).exists()
        )

    def test_login_without_verification_fails(self):
        """Test: Login sin verificar email devuelve 403."""
        # Crear usuario sin verificar
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            is_active=False,
        )

        # Intentar login
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "SecurePass123!"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)
        self.assertIn("email no ha sido verificado", response.data["error"])

    def test_full_registration_and_login_flow(self):
        """Test: Flujo completo registro → verificación → login exitoso."""
        # 1. Registrar
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123!",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 2. Obtener token de verificación (crear uno nuevo para test)
        user = User.objects.get(username="testuser")
        _, raw_token = create_email_verification_token(user)

        # 3. Verificar email
        response = self.client.post(self.verify_url, {"token": raw_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 4. Verificar que el usuario está activo
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # 5. Login exitoso
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "SecurePass123!"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)

        # 6. Verificar que se creó una sesión
        self.assertTrue(
            UserSession.objects.filter(user=user, is_active=True).exists()
        )

    def test_verify_email_with_invalid_token(self):
        """Test: Verificar con token inválido devuelve 400."""
        response = self.client.post(
            self.verify_url,
            {"token": "invalid_token_12345"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_email_with_expired_token(self):
        """Test: Token expirado no puede verificar email."""
        # Crear usuario
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            is_active=False,
        )

        # Crear token expirado
        _, raw_token = create_email_verification_token(user)
        hashed_token = EmailVerificationToken.hash_token(raw_token)
        token_obj = EmailVerificationToken.objects.get(token=hashed_token)

        # Expirar el token
        token_obj.expires_at = timezone.now() - timedelta(hours=1)
        token_obj.save()

        # Intentar verificar
        response = self.client.post(self.verify_url, {"token": raw_token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetFlowTests(TestCase):
    """Tests del flujo de recuperación de contraseña."""

    def setUp(self):
        self.client = APIClient()
        self.reset_request_url = "/api/v1/auth/password-reset/request/"
        self.reset_confirm_url = "/api/v1/auth/password-reset/confirm/"
        self.login_url = "/api/v1/auth/login/"

        # Crear usuario activo
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="OldPassword123!",
            is_active=True,
        )

    def test_password_reset_request_always_returns_ok(self):
        """Test: Reset request siempre retorna 200 (no revela existencia)."""
        # Email existente
        response = self.client.post(
            self.reset_request_url,
            {"email": "test@example.com"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Email no existente (también retorna 200)
        response = self.client.post(
            self.reset_request_url,
            {"email": "nonexistent@example.com"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_full_password_reset_flow(self):
        """Test: Flujo completo de reset de contraseña."""
        # 1. Solicitar reset
        response = self.client.post(
            self.reset_request_url,
            {"email": "test@example.com"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 2. Crear nuevo token para tener el raw
        _, raw_token = create_password_reset_token(self.user)

        # 3. Confirmar reset con nueva contraseña
        response = self.client.post(
            self.reset_confirm_url,
            {
                "token": raw_token,
                "new_password": "NewSecurePass456!",
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 4. Verificar que la contraseña cambió
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("NewSecurePass456!")
        )

        # 5. Login con nueva contraseña debe funcionar
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "NewSecurePass456!"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 6. Login con contraseña vieja debe fallar
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "OldPassword123!"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SessionManagementTests(TestCase):
    """Tests de gestión de sesiones."""

    def setUp(self):
        self.client = APIClient()
        self.login_url = "/api/v1/auth/login/"
        self.logout_url = "/api/v1/auth/logout/"
        self.logout_all_url = "/api/v1/auth/logout-all/"
        self.sessions_url = "/api/v1/auth/sessions/"

        # Crear usuario activo
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            is_active=True,
        )

    def test_logout_invalidates_session(self):
        """Test: Logout invalida la sesión actual."""
        # Login
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "SecurePass123!"}
        )
        refresh_token = response.data["refresh"]
        access_token = response.data["access"]

        # Verificar sesión activa
        self.assertEqual(
            UserSession.objects.filter(user=self.user, is_active=True).count(),
            1
        )

        # Logout
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.post(
            self.logout_url,
            {"refresh": refresh_token}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verificar sesión inactiva
        self.assertEqual(
            UserSession.objects.filter(user=self.user, is_active=True).count(),
            0
        )

    def test_logout_all_invalidates_all_sessions(self):
        """Test: Logout-all invalida todas las sesiones."""
        # Crear múltiples sesiones (login múltiple)
        tokens = []
        for i in range(3):
            response = self.client.post(
                self.login_url,
                {
                    "username": "testuser",
                    "password": "SecurePass123!",
                    "device_name": f"Device {i}",
                }
            )
            tokens.append(response.data["access"])

        # Verificar 3 sesiones activas
        self.assertEqual(
            UserSession.objects.filter(user=self.user, is_active=True).count(),
            3
        )

        # Logout-all
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens[0]}")
        response = self.client.post(self.logout_all_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verificar 0 sesiones activas
        self.assertEqual(
            UserSession.objects.filter(user=self.user, is_active=True).count(),
            0
        )

    def test_list_active_sessions(self):
        """Test: Listar sesiones activas del usuario."""
        # Crear 2 sesiones
        tokens = []
        for i in range(2):
            response = self.client.post(
                self.login_url,
                {
                    "username": "testuser",
                    "password": "SecurePass123!",
                    "device_name": f"Device {i}",
                }
            )
            tokens.append(response.data["access"])

        # Listar sesiones
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens[0]}")
        response = self.client.get(self.sessions_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)


class RateLimitingTests(TestCase):
    """Tests de rate limiting en login."""

    def setUp(self):
        self.client = APIClient()
        self.login_url = "/api/v1/auth/login/"

        # Crear usuario activo
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            is_active=True,
        )

    def test_rate_limiting_after_multiple_failed_attempts(self):
        """Test: Rate limiting bloquea después de 5 intentos fallidos."""
        # Intentar login 5 veces con contraseña incorrecta
        for i in range(5):
            response = self.client.post(
                self.login_url,
                {"username": "testuser", "password": "WrongPassword!"}
            )
            # Los primeros 5 deben retornar 401
            if i < 5:
                self.assertIn(
                    response.status_code,
                    [status.HTTP_401_UNAUTHORIZED, status.HTTP_429_TOO_MANY_REQUESTS]
                )

        # El 6to intento debe estar bloqueado
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "WrongPassword!"}
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("bloqueada temporalmente", response.data["error"])

    def test_successful_login_resets_attempts(self):
        """Test: Login exitoso resetea el contador de intentos."""
        # 2 intentos fallidos
        for _ in range(2):
            self.client.post(
                self.login_url,
                {"username": "testuser", "password": "WrongPassword!"}
            )

        # Login exitoso
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "SecurePass123!"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verificar que el contador se reseteó
        try:
            attempt = LoginAttempt.objects.get(identifier="testuser")
            self.assertEqual(attempt.attempts, 0)
        except LoginAttempt.DoesNotExist:
            pass


class UserProfileTests(TestCase):
    """Tests de actualización de perfil."""

    def setUp(self):
        self.client = APIClient()
        self.login_url = "/api/v1/auth/login/"
        self.me_url = "/api/v1/auth/me/"

        # Crear usuario activo
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            is_active=True,
        )

        # Login para obtener token
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "SecurePass123!"}
        )
        self.access_token = response.data["access"]

    def test_get_user_profile(self):
        """Test: GET /me retorna datos del usuario."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")
        self.assertEqual(response.data["email"], "test@example.com")
        self.assertIn("is_email_verified", response.data)

    def test_get_user_profile_without_auth_uses_standard_error_contract(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "UNAUTHORIZED")
        self.assertIn("request_id", response.data)
        self.assertIn("X-Request-ID", response)

    def test_update_user_profile(self):
        """Test: PATCH /me actualiza first_name y last_name."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.patch(
            self.me_url,
            {
                "first_name": "John",
                "last_name": "Doe",
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "John")
        self.assertEqual(response.data["last_name"], "Doe")

        # Verificar en DB
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "John")
        self.assertEqual(self.user.last_name, "Doe")
