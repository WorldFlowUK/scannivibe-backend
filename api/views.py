from django.http import JsonResponse

def LocationsView(request):
    data = [
        {"id": 1, "name": "Ciudad de México", "country": "México"},
        {"id": 2, "name": "Guadalajara", "country": "México"},
        {"id": 3, "name": "Monterrey", "country": "México"},
    ]
    return JsonResponse(data, safe=False)
