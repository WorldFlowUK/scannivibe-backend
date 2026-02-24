"""
Utilidades para el sistema de autenticación.
Incluye: envío de emails, rate limiting, extracción de metadata del request.
"""
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import EmailVerificationToken, PasswordResetToken, LoginAttempt
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """
    Extrae la IP del cliente del request.
    Considera headers de proxy (X-Forwarded-For).
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Extrae el User-Agent del request."""
    return request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit length


def send_verification_email(user, raw_token):
    """
    Envía el email de verificación al usuario.
    En producción, usar un template HTML profesional.
    """
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"

    subject = "Verifica tu email - Mexicapp"
    message = f"""
Hola {user.username},

Gracias por registrarte en Mexicapp. Por favor verifica tu email haciendo click en el siguiente enlace:

{verification_link}

Este enlace expira en 24 horas.

Si no te registraste en Mexicapp, ignora este email.

Saludos,
El equipo de Mexicapp
    """.strip()

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Verification email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
        return False


def send_password_reset_email(user, raw_token):
    """
    Envía el email de recuperación de contraseña.
    En producción, usar un template HTML profesional.
    """
    reset_link = f"{settings.FRONTEND_URL}/password-reset/confirm?token={raw_token}"

    subject = "Recuperación de contraseña - Mexicapp"
    message = f"""
Hola {user.username},

Recibimos una solicitud para restablecer tu contraseña. Haz click en el siguiente enlace para continuar:

{reset_link}

Este enlace expira en 1 hora.

Si no solicitaste restablecer tu contraseña, ignora este email y tu contraseña permanecerá sin cambios.

Saludos,
El equipo de Mexicapp
    """.strip()

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Password reset email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
        return False


def create_email_verification_token(user):
    """
    Crea un token de verificación de email para el usuario.
    Retorna (token_object, raw_token) para enviar por email.
    """
    # Generar token raw
    raw_token = EmailVerificationToken.generate_token()

    # Hashear para almacenar
    hashed_token = EmailVerificationToken.hash_token(raw_token)

    # Crear el token en DB
    token = EmailVerificationToken.objects.create(
        user=user,
        token=hashed_token,
        expires_at=timezone.now() + timedelta(hours=24)
    )

    return token, raw_token


def create_password_reset_token(user, ip_address=None):
    """
    Crea un token de reset de password para el usuario.
    Retorna (token_object, raw_token) para enviar por email.
    """
    # Invalidar tokens anteriores (opcional pero recomendado)
    PasswordResetToken.objects.filter(
        user=user,
        is_used=False,
        expires_at__gt=timezone.now()
    ).update(is_used=True)

    # Generar token raw
    raw_token = PasswordResetToken.generate_token()

    # Hashear para almacenar
    hashed_token = PasswordResetToken.hash_token(raw_token)

    # Crear el token en DB
    token = PasswordResetToken.objects.create(
        user=user,
        token=hashed_token,
        expires_at=timezone.now() + timedelta(hours=1),
        ip_address=ip_address
    )

    return token, raw_token


def check_rate_limit(identifier, max_attempts=5, lockout_duration_minutes=15):
    """
    Verifica rate limiting para login.
    Retorna (is_allowed: bool, attempts_left: int, locked_until: datetime|None)

    Args:
        identifier: email o IP
        max_attempts: intentos máximos antes de bloqueo
        lockout_duration_minutes: minutos de bloqueo
    """
    attempt, created = LoginAttempt.objects.get_or_create(
        identifier=identifier,
        defaults={'attempts': 0}
    )

    # Si está bloqueado, verificar si ya expiró
    if attempt.is_locked():
        return False, 0, attempt.locked_until

    # Si pasó el tiempo de reset (ej: 1 hora sin intentos), resetear
    if attempt.last_attempt and (timezone.now() - attempt.last_attempt) > timedelta(hours=1):
        attempt.reset_attempts()
        return True, max_attempts, None

    # Verificar si hay intentos disponibles
    attempts_left = max_attempts - attempt.attempts
    if attempts_left > 0:
        return True, attempts_left, None

    # Sin intentos, bloquear
    attempt.locked_until = timezone.now() + timedelta(minutes=lockout_duration_minutes)
    attempt.save()

    return False, 0, attempt.locked_until


def record_failed_login(identifier):
    """
    Registra un intento fallido de login.
    """
    attempt, created = LoginAttempt.objects.get_or_create(
        identifier=identifier,
        defaults={'attempts': 0}
    )

    attempt.attempts += 1
    attempt.save()

    logger.warning(f"Failed login attempt for {identifier} (attempt {attempt.attempts})")


def reset_login_attempts(identifier):
    """
    Resetea los intentos de login después de un login exitoso.
    """
    try:
        attempt = LoginAttempt.objects.get(identifier=identifier)
        attempt.reset_attempts()
        logger.info(f"Login attempts reset for {identifier}")
    except LoginAttempt.DoesNotExist:
        pass
