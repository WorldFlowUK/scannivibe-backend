# locations/utils.py
from __future__ import annotations

from typing import Optional, Set

from django.contrib.auth.models import AbstractBaseUser

from .models import Visit, Location


DEFAULT_VIBE_MATCH = 70
MIN_VIBE_MATCH = 30
MAX_VIBE_MATCH = 100


def calculate_vibe_match(user: AbstractBaseUser, location: Location) -> int:
    """
    Vibe Match MVP (determinístico, sin ML):
    - Usa overlap entre moods del location actual y moods de locations
      visitadas por el usuario con status COMPLETED.
    - Si el usuario no tiene historial COMPLETED o el location no tiene moods => 70
    - Clamp final: 30..100
    """

    # Si por alguna razón llega un user no autenticado, devolvemos default seguro
    if not getattr(user, "is_authenticated", False):
        return DEFAULT_VIBE_MATCH

    # 1) Moods del location actual
    location_mood_ids: Set[int] = set(location.moods.values_list("id", flat=True))
    if not location_mood_ids:
        return DEFAULT_VIBE_MATCH

    # 2) Moods de locations visitadas (COMPLETED) por el usuario
    visited_mood_ids = set(
        Visit.objects.filter(user=user, status=Visit.Status.COMPLETED)
        .values_list("location__moods__id", flat=True)
        .distinct()
    )

    # values_list puede traer None si alguna location no tiene moods
    visited_mood_ids.discard(None)

    if not visited_mood_ids:
        return DEFAULT_VIBE_MATCH

    # 3) Overlap
    common = location_mood_ids.intersection(visited_mood_ids)
    raw_pct = int((len(common) / len(location_mood_ids)) * 100)

    # 4) Clamp 30..100
    return max(MIN_VIBE_MATCH, min(raw_pct, MAX_VIBE_MATCH))
