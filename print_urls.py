import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_rest_main.settings")
django.setup()

from django.urls import get_resolver

def list_urls(urlpatterns, prefix=""):
    for p in urlpatterns:
        if hasattr(p, "url_patterns"):  # include()
            list_urls(p.url_patterns, prefix + str(p.pattern))
        else:
            print(prefix + str(p.pattern))

resolver = get_resolver()
list_urls(resolver.url_patterns)
