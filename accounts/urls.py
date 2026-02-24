from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    ping,
    RegisterView,
    VerifyEmailView,
    ResendVerificationView,
    CustomLoginView,
    LogoutView,
    LogoutAllView,
    MeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    SessionListView,
    SessionRevokeView,
)

app_name = "accounts"

urlpatterns = [
    # Health check
    path("ping/", ping, name="ping"),

    # Registration & Email Verification
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend_verification"),

    # Authentication (JWT)
    path("login/", CustomLoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout-all/", LogoutAllView.as_view(), name="logout_all"),

    # User Profile
    path("me/", MeView.as_view(), name="me"),

    # Password Reset
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),

    # Session Management
    path("sessions/", SessionListView.as_view(), name="session_list"),
    path("sessions/<str:jti>/", SessionRevokeView.as_view(), name="session_revoke"),
]
