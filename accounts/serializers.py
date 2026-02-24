from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import UserSession


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Para respuestas (ej: /me). Nunca incluye password.
    Incluye estado de verificación de email.
    """
    is_email_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "is_email_verified", "date_joined", "last_login"]
        read_only_fields = ["id", "date_joined", "last_login", "is_email_verified"]

    def get_is_email_verified(self, obj):
        """Verificamos si el usuario está activo (usaremos is_active como flag de verificación)."""
        return obj.is_active


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Para actualizar perfil (PATCH /me/).
    Solo permite actualizar first_name y last_name.
    """
    class Meta:
        model = User
        fields = ["first_name", "last_name"]

    def validate_first_name(self, value):
        return value.strip() if value else ""

    def validate_last_name(self, value):
        return value.strip() if value else ""


class RegisterSerializer(serializers.ModelSerializer):
    """
    Para registro (crea usuario). Incluye password write_only.
    El usuario se crea con is_active=False hasta verificar email.
    """
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "password"]

    def validate_username(self, value: str) -> str:
        value = value.strip()
        qs = User.objects.filter(username=value)

        # Si en el futuro reutilizas este serializer para update, esto evita falso positivo
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Este username ya está en uso.")
        return value

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()

        if not value:
            raise serializers.ValidationError("El email es requerido.")

        qs = User.objects.filter(email=value)

        # Si en el futuro reutilizas este serializer para update, esto evita falso positivo
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Este email ya está registrado.")
        return value

    def validate_password(self, value):
        """Usa los validadores de password de Django."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        username = validated_data["username"].strip()
        email = validated_data["email"].lower().strip()

        first_name = (validated_data.get("first_name") or "").strip()
        last_name = (validated_data.get("last_name") or "").strip()
        password = validated_data["password"]

        # create_user => hashea password correctamente
        # is_active=False hasta que verifique el email
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=False  # Requiere verificación de email
        )
        return user


class EmailVerificationSerializer(serializers.Serializer):
    """Para verificar el email con token."""
    token = serializers.CharField(required=True, max_length=64)


class ResendVerificationSerializer(serializers.Serializer):
    """Para reenviar el email de verificación."""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return value.lower().strip()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Para solicitar reset de password (siempre responde OK por seguridad)."""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Para confirmar reset de password con token."""
    token = serializers.CharField(required=True, max_length=64)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)

    def validate_new_password(self, value):
        """Usa los validadores de password de Django."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value


class UserSessionSerializer(serializers.ModelSerializer):
    """Para listar sesiones activas del usuario."""
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id",
            "device_name",
            "user_agent",
            "ip_address",
            "created_at",
            "last_seen_at",
            "is_active",
            "is_current",
        ]
        read_only_fields = fields

    def get_is_current(self, obj):
        """Determina si esta es la sesión actual del request."""
        request = self.context.get("request")
        if not request:
            return False

        # Obtener el JTI del token actual del request (si existe)
        # Esto lo implementaremos en la view
        current_jti = self.context.get("current_jti")
        return obj.refresh_token_jti == current_jti if current_jti else False
