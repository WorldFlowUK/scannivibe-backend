from django.contrib import admin
from .models import Mood, Location, Visit, Collectible, Favorite, Promotion

@admin.register(Mood)
class MoodAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)} # Autocompleta el slug

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "status", "qr_code")
    list_filter = ("status", "city")
    search_fields = ("name", "qr_code")
    filter_horizontal = ("moods",) # Esto crea una interfaz genial para elegir vibes

@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "status", "checked_in_at")

admin.site.register(Collectible)
admin.site.register(Favorite)
admin.site.register(Promotion)