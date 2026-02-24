# locations/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Mood(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre del Vibe")
    slug = models.SlugField(unique=True, help_text="Identificador único para URLs")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Mood / Vibe"
        verbose_name_plural = "Moods / Vibes"

    def __str__(self):
        return self.name


class Location(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Borrador / Pendiente"
        APPROVED = "approved", "Publicado / Aprobado"
        ARCHIVED = "archived", "Archivado (No Visible)"

    class Category(models.TextChoices):
        RESTAURANT = "restaurant", "Restaurante"
        BAR = "bar", "Bar / Pub"
        ATTRACTION = "attraction", "Atracción Turística"
        OTHER = "other", "Otro"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.OTHER
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    city = models.CharField(max_length=100, default="Santiago")
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )

    qr_code = models.CharField(
        max_length=100, blank=True, unique=True, help_text="Código único del QR"
    )

    moods = models.ManyToManyField(Mood, related_name="locations", blank=True)

    image_url = models.URLField(max_length=500, blank=True)
    vibe_match_score = models.IntegerField(
        default=70, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lugar"
        verbose_name_plural = "Lugares"

    def __str__(self):
        return self.name


class Visit(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ACTIVE = "active", "Activo"
        COMPLETED = "completed", "Completado"

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    checked_in_at = models.DateTimeField(auto_now_add=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Visita"
        verbose_name_plural = "Visitas"

    def __str__(self):
        return f"{self.user.username} @ {self.location.name}"


class Collectible(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "location")
        verbose_name = "Coleccionable"
        verbose_name_plural = "Coleccionables"


class Favorite(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "location")
        verbose_name = "Favorito"
        verbose_name_plural = "Favoritos"


class Promotion(models.Model):
    title = models.CharField(max_length=255)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Promoción"
        verbose_name_plural = "Promociones"


# ✅ NUEVO: persiste los 4 scores del checkout
class Review(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="reviews")
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="reviews")
    visit = models.OneToOneField(Visit, on_delete=models.CASCADE, related_name="review")

    service_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    quality_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    price_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    vibe_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reseña"
        verbose_name_plural = "Reseñas"
