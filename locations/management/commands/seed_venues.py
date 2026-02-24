from decimal import Decimal

from django.core.management.base import BaseCommand

from locations.models import Location, Mood


MOODS_DATA = [
    {"name": "Romantico", "slug": "romantico"},
    {"name": "Aventurero", "slug": "aventurero"},
    {"name": "Cultural", "slug": "cultural"},
    {"name": "Chill", "slug": "chill"},
]


VENUES = [
    # Condesa (12)
    {"name": "Paramo", "cat": "bar", "addr": "Av. Nuevo Leon 154, Condesa", "lat": 19.4112, "lng": -99.1718, "moods": ["chill", "romantico"], "score": 88},
    {"name": "Baltra Bar", "cat": "bar", "addr": "Iztaccihuatl 36D, Condesa", "lat": 19.4098, "lng": -99.1742, "moods": ["aventurero", "chill"], "score": 82},
    {"name": "Cafe Toscano", "cat": "restaurant", "addr": "Atlixco 44, Condesa", "lat": 19.4121, "lng": -99.1728, "moods": ["romantico"], "score": 79},
    {"name": "Lardo", "cat": "restaurant", "addr": "Agustin Melgar 6, Condesa", "lat": 19.4135, "lng": -99.1710, "moods": ["cultural", "romantico"], "score": 91},
    {"name": "Blanco Colima", "cat": "restaurant", "addr": "Colima 268, Condesa", "lat": 19.4155, "lng": -99.1685, "moods": ["chill"], "score": 76},
    {"name": "Gin Gin", "cat": "bar", "addr": "Montes de Oca 86, Condesa", "lat": 19.4088, "lng": -99.1752, "moods": ["aventurero"], "score": 84},
    {"name": "Kaah Siis", "cat": "restaurant", "addr": "Tamaulipas 41, Condesa", "lat": 19.4101, "lng": -99.1700, "moods": ["cultural", "chill"], "score": 87},
    {"name": "Expendio de Maiz", "cat": "restaurant", "addr": "Av. Yucatan 84, Condesa", "lat": 19.4090, "lng": -99.1695, "moods": ["cultural"], "score": 93},
    {"name": "Cafebreria El Pendulo", "cat": "attraction", "addr": "Av. Nuevo Leon 115, Condesa", "lat": 19.4125, "lng": -99.1732, "moods": ["cultural", "chill"], "score": 80},
    {"name": "Salon Malafama", "cat": "bar", "addr": "Michoacan 78, Condesa", "lat": 19.4145, "lng": -99.1690, "moods": ["aventurero"], "score": 77},
    {"name": "Riviera del Sur", "cat": "restaurant", "addr": "Insurgentes Sur 398, Condesa", "lat": 19.4070, "lng": -99.1715, "moods": ["romantico", "chill"], "score": 85},
    {"name": "Terrace Condesa", "cat": "bar", "addr": "Alfonso Reyes 120, Condesa", "lat": 19.4160, "lng": -99.1738, "moods": ["romantico", "aventurero"], "score": 89},
    # Roma Norte (10)
    {"name": "Contramar", "cat": "restaurant", "addr": "Durango 200, Roma Norte", "lat": 19.4198, "lng": -99.1630, "moods": ["cultural", "romantico"], "score": 95},
    {"name": "Rosetta", "cat": "restaurant", "addr": "Colima 166, Roma Norte", "lat": 19.4205, "lng": -99.1622, "moods": ["romantico"], "score": 94},
    {"name": "Departamento", "cat": "bar", "addr": "Edinburgo 51, Roma Norte", "lat": 19.4185, "lng": -99.1645, "moods": ["aventurero", "chill"], "score": 81},
    {"name": "Mercado Roma", "cat": "restaurant", "addr": "Queretaro 225, Roma Norte", "lat": 19.4192, "lng": -99.1610, "moods": ["cultural", "aventurero"], "score": 86},
    {"name": "Cicatriz Cafe", "cat": "restaurant", "addr": "Nuevo Leon 68, Roma Norte", "lat": 19.4215, "lng": -99.1618, "moods": ["chill"], "score": 74},
    {"name": "La Clandestina", "cat": "bar", "addr": "Alvaro Obregon 298, Roma Norte", "lat": 19.4178, "lng": -99.1638, "moods": ["aventurero"], "score": 83},
    {"name": "Tierra Garat", "cat": "restaurant", "addr": "Orizaba 141, Roma Norte", "lat": 19.4188, "lng": -99.1612, "moods": ["chill", "cultural"], "score": 78},
    {"name": "Bosforo", "cat": "bar", "addr": "Luis Moya 31, Roma Norte", "lat": 19.4210, "lng": -99.1605, "moods": ["aventurero", "romantico"], "score": 80},
    {"name": "Casa Lam", "cat": "attraction", "addr": "Alvaro Obregon 99, Roma Norte", "lat": 19.4220, "lng": -99.1598, "moods": ["cultural"], "score": 76},
    {"name": "Maison Artemisia", "cat": "restaurant", "addr": "Tonala 23, Roma Norte", "lat": 19.4175, "lng": -99.1650, "moods": ["romantico", "cultural"], "score": 90},
    # Polanco (8)
    {"name": "Pujol", "cat": "restaurant", "addr": "Tennyson 133, Polanco", "lat": 19.4325, "lng": -99.1942, "moods": ["cultural", "romantico"], "score": 97},
    {"name": "Quintonil", "cat": "restaurant", "addr": "Newton 55, Polanco", "lat": 19.4318, "lng": -99.1920, "moods": ["romantico"], "score": 96},
    {"name": "Museo Soumaya", "cat": "attraction", "addr": "Blvd. Miguel de Cervantes, Polanco", "lat": 19.4405, "lng": -99.2052, "moods": ["cultural"], "score": 92},
    {"name": "Museo Jumex", "cat": "attraction", "addr": "Blvd. Miguel de Cervantes 303, Polanco", "lat": 19.4402, "lng": -99.2045, "moods": ["cultural", "aventurero"], "score": 88},
    {"name": "King Cole Bar", "cat": "bar", "addr": "Campos Eliseos 252, Polanco", "lat": 19.4292, "lng": -99.1955, "moods": ["romantico", "chill"], "score": 85},
    {"name": "Dulce Patria", "cat": "restaurant", "addr": "Anatole France 100, Polanco", "lat": 19.4312, "lng": -99.1910, "moods": ["cultural"], "score": 89},
    {"name": "Ivoire", "cat": "restaurant", "addr": "Emilio Castelar 95, Polanco", "lat": 19.4305, "lng": -99.1935, "moods": ["romantico", "chill"], "score": 82},
    {"name": "Chapulin", "cat": "bar", "addr": "Av. Presidente Masaryk 201, Polanco", "lat": 19.4330, "lng": -99.1900, "moods": ["aventurero"], "score": 79},
    # Centro Historico (8)
    {"name": "El Moro Churreria", "cat": "restaurant", "addr": "Eje Central 42, Centro", "lat": 19.4330, "lng": -99.1340, "moods": ["cultural", "chill"], "score": 87},
    {"name": "Azul Historico", "cat": "restaurant", "addr": "Isabel la Catolica 30, Centro", "lat": 19.4335, "lng": -99.1360, "moods": ["cultural", "romantico"], "score": 84},
    {"name": "Palacio de Bellas Artes", "cat": "attraction", "addr": "Av. Juarez S/N, Centro", "lat": 19.4352, "lng": -99.1412, "moods": ["cultural"], "score": 98},
    {"name": "Templo Mayor Museum", "cat": "attraction", "addr": "Seminario 8, Centro", "lat": 19.4345, "lng": -99.1320, "moods": ["cultural", "aventurero"], "score": 91},
    {"name": "Hosteria de Santo Domingo", "cat": "restaurant", "addr": "Belisario Dominguez 72, Centro", "lat": 19.4355, "lng": -99.1372, "moods": ["cultural"], "score": 83},
    {"name": "Cafe de Tacuba", "cat": "restaurant", "addr": "Tacuba 28, Centro", "lat": 19.4365, "lng": -99.1390, "moods": ["cultural", "chill"], "score": 86},
    {"name": "Zinco Jazz Club", "cat": "bar", "addr": "Motolinia 20, Centro", "lat": 19.4340, "lng": -99.1380, "moods": ["romantico", "cultural"], "score": 81},
    {"name": "Miralto", "cat": "restaurant", "addr": "Torre Latinoamericana Piso 41, Centro", "lat": 19.4338, "lng": -99.1405, "moods": ["romantico", "aventurero"], "score": 90},
    # Coyoacan (6)
    {"name": "Museo Frida Kahlo", "cat": "attraction", "addr": "Londres 247, Coyoacan", "lat": 19.3556, "lng": -99.1624, "moods": ["cultural"], "score": 96},
    {"name": "Los Danzantes", "cat": "restaurant", "addr": "Jardin Centenario 12, Coyoacan", "lat": 19.3498, "lng": -99.1622, "moods": ["cultural", "romantico"], "score": 85},
    {"name": "Cafe Avellaneda", "cat": "restaurant", "addr": "Higuera 40-A, Coyoacan", "lat": 19.3510, "lng": -99.1615, "moods": ["chill"], "score": 78},
    {"name": "Mercado de Coyoacan", "cat": "attraction", "addr": "Ignacio Allende s/n, Coyoacan", "lat": 19.3505, "lng": -99.1618, "moods": ["cultural", "aventurero"], "score": 82},
    {"name": "Corazon de Maguey", "cat": "bar", "addr": "Jardin Centenario 9, Coyoacan", "lat": 19.3495, "lng": -99.1625, "moods": ["aventurero", "cultural"], "score": 80},
    {"name": "Centenario 107", "cat": "restaurant", "addr": "Centenario 107, Coyoacan", "lat": 19.3488, "lng": -99.1630, "moods": ["romantico", "chill"], "score": 83},
    # Santa Fe (6)
    {"name": "Morimoto", "cat": "restaurant", "addr": "Juan Salvador Agraz 37, Santa Fe", "lat": 19.3665, "lng": -99.2618, "moods": ["romantico"], "score": 88},
    {"name": "Terrace Santa Fe", "cat": "bar", "addr": "Vasco de Quiroga 3800, Santa Fe", "lat": 19.3652, "lng": -99.2605, "moods": ["chill", "romantico"], "score": 79},
    {"name": "La Unica", "cat": "restaurant", "addr": "Av. Santa Fe 440, Santa Fe", "lat": 19.3670, "lng": -99.2625, "moods": ["aventurero"], "score": 75},
    {"name": "Arango Design Center", "cat": "attraction", "addr": "Av. Santa Fe 170, Santa Fe", "lat": 19.3675, "lng": -99.2630, "moods": ["cultural"], "score": 77},
    {"name": "Nobu Santa Fe", "cat": "restaurant", "addr": "Juan Salvador Agraz 50, Santa Fe", "lat": 19.3658, "lng": -99.2610, "moods": ["romantico", "cultural"], "score": 91},
    {"name": "Sky Bar Santa Fe", "cat": "bar", "addr": "Antonio Dovali 70 Piso 25, Santa Fe", "lat": 19.3648, "lng": -99.2598, "moods": ["aventurero", "chill"], "score": 84},
]


class Command(BaseCommand):
    help = "Seed 50 CDMX venues with moods"

    def handle(self, *args, **options):
        mood_objects = {}
        for mood in MOODS_DATA:
            obj, _ = Mood.objects.get_or_create(
                slug=mood["slug"],
                defaults={"name": mood["name"], "is_active": True},
            )
            fields_to_update = []
            if obj.name != mood["name"]:
                obj.name = mood["name"]
                fields_to_update.append("name")
            if not obj.is_active:
                obj.is_active = True
                fields_to_update.append("is_active")
            if fields_to_update:
                obj.save(update_fields=fields_to_update)
            mood_objects[mood["slug"]] = obj

        created = 0
        for index, venue in enumerate(VENUES, start=1):
            defaults = {
                "name": venue["name"],
                "description": f"Popular {venue['cat']} in CDMX's {venue['addr'].split(',')[-1].strip()} neighborhood.",
                "category": venue["cat"],
                "status": Location.Status.APPROVED,
                "city": "CDMX",
                "address": venue["addr"],
                "latitude": Decimal(str(venue["lat"])),
                "longitude": Decimal(str(venue["lng"])),
                "image_url": f"https://picsum.photos/seed/venue{index}/600/400",
                "vibe_match_score": venue["score"],
            }

            location, was_created = Location.objects.get_or_create(
                qr_code=f"VEN-{index:03d}",
                defaults=defaults,
            )

            if not was_created:
                update_fields = []
                for field_name, value in defaults.items():
                    if getattr(location, field_name) != value:
                        setattr(location, field_name, value)
                        update_fields.append(field_name)
                if update_fields:
                    location.save(update_fields=update_fields)
            else:
                created += 1

            location.moods.set([mood_objects[slug] for slug in venue["moods"]])

        total_seeded = Location.objects.filter(qr_code__startswith="VEN-").count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {created} created, {total_seeded} total VEN-* venues."
            )
        )
