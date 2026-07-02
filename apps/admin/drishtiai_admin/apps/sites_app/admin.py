from django.contrib import admin
from .models import SiteProxy


@admin.register(SiteProxy)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "plate_region", "timezone", "org_id")
    search_fields = ("name", "address")
    readonly_fields = ("id", "created_at", "updated_at")
