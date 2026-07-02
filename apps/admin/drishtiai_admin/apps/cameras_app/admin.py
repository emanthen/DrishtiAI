from django.contrib import admin
from django.utils.html import format_html

from .models import CameraProxy


@admin.register(CameraProxy)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("name", "site_id", "kind", "role", "health_badge", "enabled", "stream_url")
    list_filter = ("kind", "role", "health_status", "enabled")
    search_fields = ("name", "stream_url")
    readonly_fields = ("id", "created_at", "updated_at", "health_status")
    ordering = ("name",)

    fieldsets = (
        (None, {"fields": ("id", "site_id", "name", "enabled")}),
        ("Stream", {"fields": ("kind", "stream_url", "role", "fps", "resolution_w", "resolution_h")}),
        ("Status", {"fields": ("health_status", "created_at", "updated_at")}),
    )

    @admin.display(description="Health")
    def health_badge(self, obj):
        color_map = {
            "online": "green",
            "offline": "red",
            "degraded": "orange",
            "unknown": "grey",
        }
        color = color_map.get(obj.health_status, "grey")
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color,
            obj.health_status.upper(),
        )
