# Mexicapp - Tourism Discovery API

Django REST API for a tourism/location discovery application with enterprise-grade authentication. Users can explore locations by mood/vibe, check in via QR codes, collect location badges, and manage favorites.

## Tech Stack

- **Django 6.0** - Web framework
- **Django REST Framework 3.16** - API toolkit
- **djangorestframework-simplejwt 5.5** - JWT authentication
- **Python 3.14** - Programming language
- **SQLite** - Database (development)

## Features

### Authentication System (Firebase-like)
- ✅ User registration with email verification
- ✅ Secure JWT-based authentication (access + refresh tokens)
- ✅ Email verification workflow (one-time tokens, 24h expiration)
- ✅ Password reset flow (one-time tokens, 1h expiration)
- ✅ Rate limiting on login (5 attempts, 15min lockout)
- ✅ Session management (track devices/browsers)
- ✅ Multi-device logout support
- ✅ Token rotation + blacklist
- ✅ Security audit logging

### Location Features
- Browse locations by mood/vibe (romantic, adventurous, etc.)
- QR code check-in/check-out system
- Collectible badges (earned on first visit)
- Favorite locations management
- Vibe matching score calculation

## Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd Mexicapp

# Create virtual environment
python -m venv mexenv

# Activate virtual environment
# Windows (Git Bash):
source mexenv/Scripts/activate
# Windows (PowerShell):
.\mexenv\Scripts\activate
# Linux/Mac:
source mexenv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the project root:

```env
# Required
SECRET_KEY=your-secret-key-here
DEBUG=True

# Email Configuration (Development - Console Backend)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@mexicapp.com
FRONTEND_URL=http://localhost:3000

# Email Configuration (Production - SMTP)
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your-email@gmail.com
# EMAIL_HOST_PASSWORD=your-app-password
# DEFAULT_FROM_EMAIL=noreply@mexicapp.com
# FRONTEND_URL=https://yourdomain.com

# Optional
LOG_LEVEL=INFO
```

### 3. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser
```

### 4. Run Development Server

```bash
python manage.py runserver
```

Access points:
- **API**: http://localhost:8000/api/v1/
- **Admin**: http://localhost:8000/admin/
- **API Docs**: See [Authentication Endpoints](#authentication-endpoints) below

## Authentication Endpoints

Base URL: `/api/v1/auth/`

### Registration & Email Verification

#### Register User
```bash
POST /api/v1/auth/register/
Content-Type: application/json

{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}

Response 201:
{
  "message": "Usuario registrado exitosamente. Revisa tu email para verificar tu cuenta.",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "is_email_verified": false
  },
  "email_sent": true
}
```

#### Verify Email
```bash
POST /api/v1/auth/verify-email/
Content-Type: application/json

{
  "token": "abc123...token_from_email"
}

Response 200:
{
  "message": "Email verificado exitosamente. Ya puedes iniciar sesión.",
  "user": {...}
}
```

#### Resend Verification Email
```bash
POST /api/v1/auth/resend-verification/
Content-Type: application/json

{
  "email": "john@example.com"
}

Response 200:
{
  "message": "Si el email existe en nuestro sistema, recibirás un email de verificación."
}
```

### Authentication

#### Login
```bash
POST /api/v1/auth/login/
Content-Type: application/json

{
  "username": "johndoe",
  "password": "SecurePass123!",
  "device_name": "iPhone 13"  # Optional
}

Response 200:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbG...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbG...",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "is_email_verified": true
  }
}

Response 403 (Email not verified):
{
  "error": "Tu email no ha sido verificado...",
  "email": "john@example.com"
}

Response 429 (Rate limited):
{
  "error": "Demasiados intentos fallidos...",
  "locked_until": "2026-02-02T15:30:00Z"
}
```

#### Refresh Token
```bash
POST /api/v1/auth/refresh/
Content-Type: application/json

{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbG..."
}

Response 200:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbG...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbG..."  # New refresh token (rotation)
}
```

#### Logout
```bash
POST /api/v1/auth/logout/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbG..."
}

Response 200:
{
  "message": "Sesión cerrada exitosamente."
}
```

#### Logout All Devices
```bash
POST /api/v1/auth/logout-all/
Authorization: Bearer <access_token>

Response 200:
{
  "message": "Todas las sesiones han sido cerradas exitosamente."
}
```

### User Profile

#### Get Profile
```bash
GET /api/v1/auth/me/
Authorization: Bearer <access_token>

Response 200:
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_email_verified": true,
  "date_joined": "2026-02-02T10:00:00Z",
  "last_login": "2026-02-02T12:30:00Z"
}
```

#### Update Profile
```bash
PATCH /api/v1/auth/me/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "first_name": "Johnny",
  "last_name": "Doe"
}

Response 200:
{
  "first_name": "Johnny",
  "last_name": "Doe"
}
```

### Password Reset

#### Request Password Reset
```bash
POST /api/v1/auth/password-reset/request/
Content-Type: application/json

{
  "email": "john@example.com"
}

Response 200 (always):
{
  "message": "Si el email existe en nuestro sistema, recibirás un email con instrucciones..."
}
```

#### Confirm Password Reset
```bash
POST /api/v1/auth/password-reset/confirm/
Content-Type: application/json

{
  "token": "xyz789...token_from_email",
  "new_password": "NewSecurePass456!"
}

Response 200:
{
  "message": "Contraseña actualizada exitosamente. Por favor inicia sesión con tu nueva contraseña."
}
```

### Session Management

#### List Active Sessions
```bash
GET /api/v1/auth/sessions/
Authorization: Bearer <access_token>

Response 200:
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "device_name": "iPhone 13",
      "user_agent": "Mozilla/5.0...",
      "ip_address": "192.168.1.100",
      "created_at": "2026-02-02T10:00:00Z",
      "last_seen_at": "2026-02-02T12:30:00Z",
      "is_active": true,
      "is_current": true
    },
    {
      "id": 2,
      "device_name": "Chrome Desktop",
      "user_agent": "Mozilla/5.0...",
      "ip_address": "192.168.1.101",
      "created_at": "2026-02-01T09:00:00Z",
      "last_seen_at": "2026-02-01T18:00:00Z",
      "is_active": true,
      "is_current": false
    }
  ]
}
```

#### Revoke Specific Session
```bash
DELETE /api/v1/auth/sessions/<jti>/
Authorization: Bearer <access_token>

Response 200:
{
  "message": "Sesión revocada exitosamente."
}
```

## Location Endpoints

Base URL: `/api/v1/`

### Locations
- `GET /moods/` - List active moods/vibes
- `GET /locations/` - List approved locations (filterable by `?mood=slug`)
- `GET /locations/{id}/` - Location detail with moods
- `GET /locations/{id}/vibe-match/` - Calculate vibe match score

### Visits & Check-ins
- `POST /visits/checkin/` - Check in with QR code
- `POST /visits/{id}/checkout/` - Check out from visit
- `GET /visits/me/` - User's visit history

### Collectibles & Favorites
- `GET /me/collectibles/` - User's collected badges
- `POST /favorites/` - Toggle favorite (add/remove)
- `GET /favorites/me/` - User's favorite locations
- `DELETE /favorites/{location_id}/` - Remove favorite

## Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test accounts
python manage.py test locations

# Run with verbosity
python manage.py test accounts --verbosity=2
```

## Security Features

### Implemented Protections

1. **Email Verification**: Users cannot login until email is verified
2. **Rate Limiting**: 5 failed login attempts → 15min lockout
3. **Token Security**:
   - One-time use tokens (email verification, password reset)
   - Short expiration times (1h for password reset, 24h for email verify)
   - SHA256 hashing for token storage
   - JWT rotation on refresh (old refresh invalidated)
4. **Session Management**:
   - Track device metadata (user agent, IP, device name)
   - Revoke individual sessions or all sessions
   - Password change → all sessions invalidated
5. **Password Security**:
   - Django's built-in validators (min length, complexity, common passwords)
   - Argon2/PBKDF2 hashing (Django default)
6. **Information Disclosure Prevention**:
   - Generic error messages (don't reveal if user exists)
   - Password reset always returns 200 OK
7. **Audit Logging**:
   - Login attempts (success/failure)
   - Session creation/revocation
   - Password changes
   - Email verification events

### OWASP Top 10 Considerations

- ✅ **A01: Broken Access Control** - JWT authentication, permission classes, user-specific queries
- ✅ **A02: Cryptographic Failures** - Tokens hashed (SHA256), passwords hashed (Django default), HTTPS recommended
- ✅ **A03: Injection** - Django ORM (parameterized queries), input validation
- ✅ **A04: Insecure Design** - Secure auth flow, rate limiting, token expiration
- ✅ **A05: Security Misconfiguration** - Environment variables, DEBUG=False in production, secure defaults
- ✅ **A07: Identification & Authentication Failures** - Strong password policy, MFA-ready, rate limiting, session management
- ✅ **A08: Software & Data Integrity Failures** - Token rotation, blacklist, signed JWTs
- ✅ **A09: Security Logging & Monitoring** - Comprehensive logging of auth events

## Production Checklist

Before deploying to production:

- [ ] Set `DEBUG=False` in `.env`
- [ ] Generate strong `SECRET_KEY` (50+ chars, random)
- [ ] Configure SMTP email backend (Gmail, SendGrid, AWS SES, etc.)
- [ ] Use PostgreSQL/MySQL instead of SQLite
- [ ] Set `ALLOWED_HOSTS` properly
- [ ] Enable HTTPS (use Nginx + Let's Encrypt)
- [ ] Configure CORS (if using frontend)
- [ ] Set up proper logging (file/cloudwatch logs)
- [ ] Configure reverse proxy (Nginx/Apache)
- [ ] Use environment-specific requirements (gunicorn, psycopg2, etc.)
- [ ] Set up database backups
- [ ] Configure rate limiting at reverse proxy level (Nginx limit_req)
- [ ] Set up monitoring (Sentry, New Relic, etc.)
- [ ] Review and adjust JWT lifetimes for your use case
- [ ] Set up periodic cleanup of expired tokens (celery task)

## Project Structure

```
Mexicapp/
├── accounts/              # Authentication & user management
│   ├── models.py          # User, EmailVerificationToken, PasswordResetToken, UserSession, LoginAttempt
│   ├── serializers.py     # API serializers for auth endpoints
│   ├── views.py           # Auth views (register, login, logout, password reset, sessions)
│   ├── urls.py            # Auth URL routing
│   ├── utils.py           # Email sending, rate limiting, token generation
│   ├── admin.py           # Django admin configuration
│   └── tests.py           # Comprehensive auth tests
├── locations/             # Location domain (moods, locations, visits, collectibles)
├── django_rest_main/      # Django project settings
│   ├── settings.py        # Configuration (JWT, email, logging)
│   └── urls.py            # Root URL configuration
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
├── README.md              # This file
└── CLAUDE.md              # Project guidance for Claude Code
```

## Deploy to Render (via GitHub)

This repo includes `render.yaml` so Render can auto-detect service settings.

1. Push this backend repo to GitHub.
2. In Render: **New +** → **Blueprint**.
3. Select this GitHub repository.
4. Render will create:
   - Web service: `turismomundial-backend`
   - PostgreSQL database: `turismomundial-db`
5. Set/update environment values in Render if needed:
   - `FRONTEND_URL`
   - `CORS_ALLOWED_ORIGINS`
   - `CSRF_TRUSTED_ORIGINS`
6. After first deploy, verify health:
   - `GET /api/v1/auth/ping/` should return `{"ok": true, "service": "accounts"}`.

## Contributing

1. Create a feature branch
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass: `python manage.py test`
5. Submit a pull request

## License

[Your License Here]

## Support

For issues, questions, or contributions, please open an issue in the repository.
