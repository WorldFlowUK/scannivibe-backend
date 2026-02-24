from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets
import hashlib


class UserProfile(models.Model):
    """
    Modelo legacy de perfil (actualmente no usado, pero mantenido por compatibilidad).
    """
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username


class EmailVerificationToken(models.Model):
    """
    Token one-time para verificación de email.
    - Expira en 24 horas
    - Se marca como usado después del primer uso
    - Token hasheado en DB (SHA256)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_verification_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Token de verificación de email"
        verbose_name_plural = "Tokens de verificación de email"
        ordering = ["-created_at"]

    def __str__(self):
        return f"EmailVerification for {self.user.email} ({'used' if self.is_used else 'active'})"

    def is_valid(self):
        """Verifica si el token es válido (no usado y no expirado)."""
        return not self.is_used and self.expires_at > timezone.now()

    @staticmethod
    def generate_token():
        """Genera un token seguro de 32 bytes (64 chars hex)."""
        return secrets.token_hex(32)

    @staticmethod
    def hash_token(raw_token):
        """Hashea el token con SHA256 para almacenamiento."""
        return hashlib.sha256(raw_token.encode()).hexdigest()


class PasswordResetToken(models.Model):
    """
    Token one-time para recuperación de contraseña.
    - Expira en 1 hora
    - Se marca como usado después del primer uso
    - Token hasheado en DB (SHA256)
    - Auditoría de IP para seguridad
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Token de recuperación de contraseña"
        verbose_name_plural = "Tokens de recuperación de contraseña"
        ordering = ["-created_at"]

    def __str__(self):
        return f"PasswordReset for {self.user.email} ({'used' if self.is_used else 'active'})"

    def is_valid(self):
        """Verifica si el token es válido (no usado y no expirado)."""
        return not self.is_used and self.expires_at > timezone.now()

    @staticmethod
    def generate_token():
        """Genera un token seguro de 32 bytes (64 chars hex)."""
        return secrets.token_hex(32)

    @staticmethod
    def hash_token(raw_token):
        """Hashea el token con SHA256 para almacenamiento."""
        return hashlib.sha256(raw_token.encode()).hexdigest()


class UserSession(models.Model):
    """
    Tracking de sesiones/dispositivos activos del usuario.
    - Asociado al JWT ID (jti) del refresh token
    - Metadata: device_name, user_agent, IP
    - is_active: permite revocar sesiones individuales
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    refresh_token_jti = models.CharField(max_length=255, unique=True, db_index=True)
    device_name = models.CharField(max_length=255, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "Sesión de usuario"
        verbose_name_plural = "Sesiones de usuario"
        ordering = ["-last_seen_at"]

    def __str__(self):
        device = self.device_name or "Unknown device"
        return f"{self.user.username} - {device} ({'active' if self.is_active else 'revoked'})"


class LoginAttempt(models.Model):
    """
    Tracking de intentos de login para rate limiting.
    - identifier: email o IP
    - locked_until: timestamp hasta cuando está bloqueado
    - Limpieza automática de registros antiguos recomendada vía cron/celery
    """
    identifier = models.CharField(max_length=255, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    last_attempt = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Intento de login"
        verbose_name_plural = "Intentos de login"
        ordering = ["-last_attempt"]

    def __str__(self):
        return f"{self.identifier} - {self.attempts} attempts"

    def is_locked(self):
        """Verifica si el identifier está bloqueado."""
        if self.locked_until is None:
            return False
        return self.locked_until > timezone.now()

    def reset_attempts(self):
        """Resetea el contador de intentos."""
        self.attempts = 0
        self.locked_until = None
        self.save()