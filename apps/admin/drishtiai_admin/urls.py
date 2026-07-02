from django.contrib import admin
from django.urls import path
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok", "version": "0.0.0", "service": "drishtiai-admin"})


urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),
]
