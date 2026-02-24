from django.contrib import admin
from .models import (
    UserProfile,
    EmailVerificationToken,
    PasswordResetToken,
    UserSession,
    LoginAttempt,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user_id", "username", "email", "date_joined"]
    search_fields = ["username", "email"]
    list_filter = ["date_joined"]


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "expires_at", "is_used"]
    list_filter = ["is_used", "created_at", "expires_at"]
    search_fields = ["user__email", "user__username"]
    readonly_fields = ["token", "created_at"]

    def has_add_permission(self, request):
        return False


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "expires_at", "is_used", "ip_address"]
    list_filter = ["is_used", "created_at", "expires_at"]
    search_fields = ["user__email", "user__username", "ip_address"]
    readonly_fields = ["token", "created_at", "ip_address"]

    def has_add_permission(self, request):
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "device_name", "ip_address", "created_at", "last_seen_at", "is_active"]
    list_filter = ["is_active", "created_at", "last_seen_at"]
    search_fields = ["user__email", "user__username", "device_name", "ip_address"]
    readonly_fields = ["refresh_token_jti", "user_agent", "created_at", "last_seen_at"]

    def has_add_permission(self, request):
        return False


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ["identifier", "attempts", "locked_until", "last_attempt"]
    list_filter = ["locked_until", "last_attempt"]
    search_fields = ["identifier"]
    readonly_fields = ["last_attempt"]
