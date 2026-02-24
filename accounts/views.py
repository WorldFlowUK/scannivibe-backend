from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db import transaction
from rest_framework import generics, status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from .serializers import (
    RegisterSerializer,
    UserPublicSerializer,
    UserUpdateSerializer,
    EmailVerificationSerializer,
    ResendVerificationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserSessionSerializer,
)
from .models import EmailVerificationToken, PasswordResetToken, UserSession
from .utils import (
    get_client_ip,
    get_user_agent,
    send_verification_email,
    send_password_reset_email,
    create_email_verification_token,
    create_password_reset_token,
    check_rate_limit,
    record_failed_login,
    reset_login_attempts,
)
import logging

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def ping(request):
    """
    Endpoint simple para verificar que el servicio de accounts está activo.
    Útil para health checks y debug.
    """
    return Response({"ok": True, "service": "accounts"})


class RegisterView(generics.CreateAPIView):
    """
    Registro de usuarios con verificación de email.

    - Crea un User con is_active=False
    - Genera token de verificación
    - Envía email con link de verificación
    - Accesible sin autenticación

    Response:
        201: Usuario creado, email de verificación enviado
        400: Error de validación
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Crear token de verificación
        _, raw_token = create_email_verification_token(user)

        # Enviar email
        email_sent = send_verification_email(user, raw_token)

        logger.info(f"User registered: {user.email} (email_sent={email_sent})")

        return Response(
            {
                "message": "Usuario registrado exitosamente. Revisa tu email para verificar tu cuenta.",
                "user": UserPublicSerializer(user).data,
                "email_sent": email_sent,
            },
            status=status.HTTP_201_CREATED
        )


class VerifyEmailView(views.APIView):
    """
    Verifica el email del usuario con el token recibido.

    POST /auth/verify-email/
    Body: {"token": "..."}

    Response:
        200: Email verificado exitosamente
        400: Token inválido, expirado o ya usado
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_token = serializer.validated_data["token"]
        hashed_token = EmailVerificationToken.hash_token(raw_token)

        try:
            token = EmailVerificationToken.objects.get(token=hashed_token)
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {"error": "Token inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not token.is_valid():
            return Response(
                {"error": "Token expirado o ya usado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Activar usuario
        user = token.user
        user.is_active = True
        user.save()

        # Marcar token como usado
        token.is_used = True
        token.save()

        logger.info(f"Email verified for user: {user.email}")

        return Response(
            {
                "message": "Email verificado exitosamente. Ya puedes iniciar sesión.",
                "user": UserPublicSerializer(user).data,
            },
            status=status.HTTP_200_OK
        )


class ResendVerificationView(views.APIView):
    """
    Reenvía el email de verificación.

    POST /auth/resend-verification/
    Body: {"email": "..."}

    Response:
        200: Siempre retorna OK (no revela si el email existe)
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)

            # Si ya está verificado, no hacer nada
            if user.is_active:
                logger.info(f"Resend verification requested for already verified user: {email}")
                return Response(
                    {"message": "Si el email existe en nuestro sistema, recibirás un email de verificación."},
                    status=status.HTTP_200_OK
                )

            # Invalidar tokens anteriores
            EmailVerificationToken.objects.filter(
                user=user,
                is_used=False,
                expires_at__gt=timezone.now()
            ).update(is_used=True)

            # Crear nuevo token
            _, raw_token = create_email_verification_token(user)

            # Enviar email
            send_verification_email(user, raw_token)

            logger.info(f"Verification email resent to: {email}")

        except User.DoesNotExist:
            logger.warning(f"Resend verification requested for non-existent email: {email}")

        # Siempre retornar OK (no revelar si existe el usuario)
        return Response(
            {"message": "Si el email existe en nuestro sistema, recibirás un email de verificación."},
            status=status.HTTP_200_OK
        )


class CustomLoginView(views.APIView):
    """
    Login personalizado con:
    - Verificación de email obligatoria
    - Rate limiting
    - Creación de UserSession
    - No revela si el usuario existe

    POST /auth/login/
    Body: {"username": "...", "password": "..."}

    Response:
        200: Login exitoso (access + refresh tokens)
        401: Credenciales inválidas o email no verificado
        429: Demasiados intentos (bloqueado temporalmente)
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"error": "Username y password son requeridos."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Rate limiting por username (o por IP si prefieres)
        identifier = username.lower()
        is_allowed, _, locked_until = check_rate_limit(identifier)

        if not is_allowed:
            logger.warning(f"Login rate limit exceeded for {identifier} (locked until {locked_until})")
            return Response(
                {
                    "error": "Demasiados intentos fallidos. Tu cuenta ha sido bloqueada temporalmente.",
                    "locked_until": locked_until.isoformat() if locked_until else None
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Verificar si el usuario existe y si está inactivo (no verificado)
        # Django's authenticate() retorna None para usuarios con is_active=False
        # Por eso primero verificamos manualmente
        try:
            user_obj = User.objects.get(username=username)
            if not user_obj.is_active:
                logger.warning(f"Login attempt for unverified user: {user_obj.email}")
                return Response(
                    {
                        "error": "Tu email no ha sido verificado. Revisa tu correo para verificar tu cuenta.",
                        "email": user_obj.email,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
        except User.DoesNotExist:
            pass

        # Intentar autenticar
        user = authenticate(request, username=username, password=password)

        if user is None:
            # Credenciales inválidas
            record_failed_login(identifier)
            logger.warning(f"Failed login attempt for {identifier}")

            return Response(
                {"error": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Login exitoso - resetear intentos
        reset_login_attempts(identifier)

        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Crear sesión de usuario
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        device_name = request.data.get("device_name", "")  # Opcional

        UserSession.objects.create(
            user=user,
            refresh_token_jti=str(refresh["jti"]),
            device_name=device_name,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        logger.info(f"User logged in: {user.email} from IP {ip_address}")

        return Response(
            {
                "access": access_token,
                "refresh": refresh_token,
                "user": UserPublicSerializer(user).data,
            },
            status=status.HTTP_200_OK
        )


class LogoutView(views.APIView):
    """
    Logout del usuario (invalida el refresh token actual).

    POST /auth/logout/
    Body: {"refresh": "..."}

    Response:
        200: Sesión cerrada exitosamente
        400: Token inválido
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"error": "Refresh token es requerido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            jti = str(token["jti"])

            # Invalidar sesión
            UserSession.objects.filter(
                refresh_token_jti=jti,
                user=request.user
            ).update(is_active=False)

            # Blacklist el token
            token.blacklist()

            logger.info(f"User logged out: {request.user.email}")

            return Response(
                {"message": "Sesión cerrada exitosamente."},
                status=status.HTTP_200_OK
            )

        except TokenError as e:
            return Response(
                {"error": "Token inválido o ya expirado."},
                status=status.HTTP_400_BAD_REQUEST
            )


class LogoutAllView(views.APIView):
    """
    Cierra todas las sesiones del usuario (invalida todos los refresh tokens).

    POST /auth/logout-all/

    Response:
        200: Todas las sesiones cerradas
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user

        # Invalidar todas las sesiones
        UserSession.objects.filter(user=user, is_active=True).update(is_active=False)

        # Blacklist todos los tokens outstanding del usuario
        outstanding_tokens = OutstandingToken.objects.filter(user=user)

        for outstanding in outstanding_tokens:
            try:
                # Verificar si ya está en blacklist
                if not BlacklistedToken.objects.filter(token=outstanding).exists():
                    BlacklistedToken.objects.create(token=outstanding)
            except Exception:
                pass

        logger.info(f"All sessions logged out for user: {user.email}")

        return Response(
            {"message": "Todas las sesiones han sido cerradas exitosamente."},
            status=status.HTTP_200_OK
        )


class MeView(generics.RetrieveUpdateAPIView):
    """
    Retorna y actualiza los datos del usuario autenticado.

    GET /auth/me/ - Obtener datos del usuario
    PATCH /auth/me/ - Actualizar first_name, last_name

    Requiere JWT: Authorization: Bearer <access_token>
    """
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserUpdateSerializer
        return UserPublicSerializer


class PasswordResetRequestView(views.APIView):
    """
    Solicita un reset de contraseña.

    POST /auth/password-reset/request/
    Body: {"email": "..."}

    Response:
        200: Siempre retorna OK (no revela si el email existe)
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        ip_address = get_client_ip(request)

        try:
            user = User.objects.get(email=email, is_active=True)

            # Crear token de reset
            _, raw_token = create_password_reset_token(user, ip_address)

            # Enviar email
            send_password_reset_email(user, raw_token)

            logger.info(f"Password reset requested for: {email}")

        except User.DoesNotExist:
            logger.warning(f"Password reset requested for non-existent/inactive email: {email}")

        # Siempre retornar OK (no revelar si existe el usuario)
        return Response(
            {"message": "Si el email existe en nuestro sistema, recibirás un email con instrucciones para restablecer tu contraseña."},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(views.APIView):
    """
    Confirma el reset de contraseña con token.

    POST /auth/password-reset/confirm/
    Body: {"token": "...", "new_password": "..."}

    Response:
        200: Contraseña actualizada exitosamente
        400: Token inválido, expirado o ya usado
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        hashed_token = PasswordResetToken.hash_token(raw_token)

        try:
            token = PasswordResetToken.objects.get(token=hashed_token)
        except PasswordResetToken.DoesNotExist:
            return Response(
                {"error": "Token inválido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not token.is_valid():
            return Response(
                {"error": "Token expirado o ya usado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Actualizar contraseña
        user = token.user
        user.set_password(new_password)
        user.save()

        # Marcar token como usado
        token.is_used = True
        token.save()

        # Invalidar todas las sesiones del usuario (seguridad)
        UserSession.objects.filter(user=user, is_active=True).update(is_active=False)

        # Blacklist todos los tokens (opcional pero recomendado)
        outstanding_tokens = OutstandingToken.objects.filter(user=user)
        for outstanding in outstanding_tokens:
            try:
                if not BlacklistedToken.objects.filter(token=outstanding).exists():
                    BlacklistedToken.objects.create(token=outstanding)
            except Exception:
                pass

        logger.info(f"Password reset confirmed for user: {user.email}")

        return Response(
            {"message": "Contraseña actualizada exitosamente. Por favor inicia sesión con tu nueva contraseña."},
            status=status.HTTP_200_OK
        )


class SessionListView(generics.ListAPIView):
    """
    Lista todas las sesiones activas del usuario autenticado.

    GET /auth/sessions/

    Response:
        200: Lista de sesiones
    """
    serializer_class = UserSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by("-last_seen_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # TODO: Extraer JTI del token actual para marcar is_current
        # Esto requiere decodificar el access token del request
        context["current_jti"] = None
        return context


class SessionRevokeView(views.APIView):
    """
    Revoca una sesión específica del usuario.

    DELETE /auth/sessions/<jti>/

    Response:
        200: Sesión revocada exitosamente
        404: Sesión no encontrada
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, jti):
        try:
            session = UserSession.objects.get(
                refresh_token_jti=jti,
                user=request.user,
                is_active=True
            )

            # Invalidar sesión
            session.is_active = False
            session.save()

            # Blacklist el token si existe
            try:
                outstanding = OutstandingToken.objects.get(jti=jti, user=request.user)
                if not BlacklistedToken.objects.filter(token=outstanding).exists():
                    BlacklistedToken.objects.create(token=outstanding)
            except OutstandingToken.DoesNotExist:
                pass

            logger.info(f"Session revoked for user {request.user.email}: {jti}")

            return Response(
                {"message": "Sesión revocada exitosamente."},
                status=status.HTTP_200_OK
            )

        except UserSession.DoesNotExist:
            return Response(
                {"error": "Sesión no encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )
