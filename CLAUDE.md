# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django REST API for a tourism/location discovery application with enterprise-grade authentication. Users can explore locations by mood/vibe, check in via QR codes, collect location badges, and manage favorites. Built with Django 6.0, Django REST Framework, and JWT authentication (Firebase-like system).

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source mexenv/Scripts/activate  # Git Bash on Windows
# or
.\mexenv\Scripts\activate  # PowerShell

# Install dependencies
pip install -r requirements.txt

# Environment configuration
# Create .env file with required variables (see Configuration section)
```

### Database Operations
```bash
# Run migrations
python manage.py migrate

# Create migrations after model changes
python manage.py makemigrations

# Create superuser for admin access
python manage.py createsuperuser
```

### Running the Server
```bash
# Development server
python manage.py runserver

# Access points:
# - API: http://localhost:8000/api/v1/
# - Admin: http://localhost:8000/admin/
```

### Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test accounts
python manage.py test locations

# Run with verbosity
python manage.py test --verbosity=2
```

## Architecture

### App Structure

**accounts**: User authentication and profile management (Firebase-like system)
- JWT-based authentication using djangorestframework-simplejwt
- Email verification workflow (one-time SHA256 tokens, 24h expiration)
- Password reset flow (one-time tokens, 1h expiration)
- Session management (track devices, multi-device logout)
- Rate limiting (5 attempts, 15min lockout)
- Token rotation + blacklist on refresh
- Security audit logging
- Models: User (Django built-in), UserProfile, EmailVerificationToken, PasswordResetToken, UserSession, LoginAttempt

**locations**: Core tourism/location features
- Moods/Vibes: Categorize locations by atmosphere/vibe
- Locations: Places with status workflow (pending → approved → archived)
- Visits: Check-in/check-out tracking via QR codes
- Collectibles: Badge/achievement system awarded on first visit
- Favorites: User-saved locations
- Promotions: Location-specific offers

### URL Structure

Base API path: `/api/v1/`

**Authentication** (`/api/v1/auth/`):
- `POST /auth/register/` - User registration (creates inactive user, sends verification email)
- `POST /auth/verify-email/` - Verify email with token
- `POST /auth/resend-verification/` - Resend verification email
- `POST /auth/login/` - Login with email verification check + rate limiting
- `POST /auth/refresh/` - Refresh access token (rotation enabled)
- `POST /auth/logout/` - Logout current session (blacklist refresh token)
- `POST /auth/logout-all/` - Logout all devices
- `GET /auth/me/` - Get authenticated user info
- `PATCH /auth/me/` - Update user profile (first_name, last_name)
- `POST /auth/password-reset/request/` - Request password reset (always returns 200)
- `POST /auth/password-reset/confirm/` - Confirm password reset with token
- `GET /auth/sessions/` - List active sessions
- `DELETE /auth/sessions/<jti>/` - Revoke specific session

**Locations Domain** (`/api/v1/`):
- `GET /moods/` - List active moods/vibes
- `GET /locations/` - List approved locations (filterable by `?mood=slug`)
- `GET /locations/{id}/` - Location detail with moods
- `GET /locations/{id}/vibe-match/` - Calculate vibe match score
- `POST /visits/checkin/` - Check in with QR code
- `POST /visits/{id}/checkout/` - Check out from visit
- `GET /visits/me/` - User's visit history
- `GET /me/collectibles/` - User's collected badges
- `POST /favorites/` - Toggle favorite (add/remove)
- `GET /favorites/me/` - User's favorite locations
- `DELETE /favorites/{location_id}/` - Remove favorite

### Data Models

**Location**: Central model with many-to-many relationship to Moods
- Status workflow: pending → approved → archived
- Categories: restaurant, bar, attraction, other
- QR code for check-ins (unique)
- Geographic data: city, address, lat/long
- vibe_match_score: 0-100 integer

**Visit**: Tracks user check-ins/check-outs
- Status: pending → active → completed
- Timestamps: checked_in_at, checked_out_at

**Collectible**: One-per-user-per-location badge system
- Unique constraint on (user, location)
- Awarded automatically on first check-in

**Favorite**: User-saved locations
- Unique constraint on (user, location)

**EmailVerificationToken**: One-time email verification tokens
- SHA256 hashed token storage
- 24 hour expiration
- is_used flag prevents reuse

**PasswordResetToken**: One-time password reset tokens
- SHA256 hashed token storage
- 1 hour expiration
- is_used flag prevents reuse
- IP address tracking for audit

**UserSession**: Track active user sessions/devices
- Linked to refresh token JTI
- Device metadata (name, user_agent, IP)
- is_active flag for revocation
- auto_now for last_seen_at

**LoginAttempt**: Rate limiting tracking
- identifier (username or IP)
- attempts counter
- locked_until timestamp

### Authentication Pattern

- Uses `rest_framework_simplejwt` for JWT tokens
- Access token lifetime: 1 hour
- Refresh token lifetime: 1 day
- Tokens rotate on refresh with blacklist support (ROTATE_REFRESH_TOKENS=True, BLACKLIST_AFTER_ROTATION=True)
- Auth header: `Authorization: Bearer <access_token>`
- Email verification required: Users with is_active=False cannot login
- Rate limiting: 5 failed attempts → 15min lockout
- Password change → all sessions invalidated
- One-time tokens: email verification (24h), password reset (1h)
- Security: Tokens SHA256 hashed in DB, generic error messages (no user enumeration)

### Key Patterns

**ViewSet Usage**: DRF ViewSets for CRUD operations
- `MoodViewSet`, `LocationViewSet`: Read-only viewsets
- Custom serializers for list vs. detail views

**Permission Classes**:
- `AllowAny`: Public endpoints (moods, locations list, auth)
- `IsAuthenticated`: User-specific endpoints (visits, favorites, collectibles)

**Serializers**:
- Separate list/detail serializers for optimized responses
- Location list: minimal fields for browsing
- Location detail: includes moods, is_favorited status

**Atomic Transactions**: Check-in flow uses `@transaction.atomic` to ensure Visit + Collectible creation consistency

**Query Optimization**: Uses `prefetch_related("moods")` to avoid N+1 queries

## Configuration

**Settings** (`django_rest_main/settings.py`):
- Environment variables via `python-decouple`
- Required: `SECRET_KEY`
- Optional: `DEBUG` (defaults to False), `LOG_LEVEL` (defaults to INFO)
- Database: SQLite (default), single file `db.sqlite3`
- Pagination: 10 items per page
- Default permissions: AllowAny (override per view)

**Email Configuration** (`.env`):
```bash
# Development (console backend - emails print to console)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@mexicapp.com
FRONTEND_URL=http://localhost:3000

# Production (SMTP backend)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@mexicapp.com
FRONTEND_URL=https://yourdomain.com
```

**Database**: SQLite for development. Migration files in `*/migrations/`.

## Notes

- Spanish verbose names in models (Meta.verbose_name/verbose_name_plural)
- QR codes must be unique per location
- Collectibles prevent duplicate awards via unique_together constraint
- Location filtering by mood uses slug field (e.g., `?mood=romantico`)
- All timestamps use Django's timezone-aware datetime

## Security Features

**Implemented Protections**:
- Email verification required for login
- Rate limiting on login (5 attempts → 15min lockout)
- One-time tokens with expiration (SHA256 hashed)
- JWT rotation on refresh (old refresh invalidated)
- Session tracking with device metadata
- Multi-device logout support
- Password change → all sessions invalidated
- Generic error messages (no user enumeration)
- Audit logging (login attempts, sessions, password changes)
- Django password validators (min length, complexity, common passwords)

**OWASP Top 10**:
- A01: JWT auth, permission classes, user-specific queries
- A02: SHA256 token hashing, Django password hashing, HTTPS recommended
- A03: Django ORM (parameterized queries), input validation
- A04: Secure auth flow, rate limiting, token expiration
- A05: Environment variables, DEBUG=False in prod
- A07: Strong password policy, rate limiting, session management
- A08: Token rotation, blacklist, signed JWTs
- A09: Comprehensive logging of auth events

**Production Checklist**:
- Set DEBUG=False
- Generate strong SECRET_KEY (50+ chars)
- Configure SMTP email backend
- Use PostgreSQL/MySQL instead of SQLite
- Set ALLOWED_HOSTS properly
- Enable HTTPS (Nginx + Let's Encrypt)
- Configure CORS if using frontend
- Set up proper logging (file/cloudwatch)
- Configure reverse proxy rate limiting
- Set up monitoring (Sentry, New Relic)
- Review JWT lifetimes
- Set up periodic cleanup of expired tokens (celery task)
