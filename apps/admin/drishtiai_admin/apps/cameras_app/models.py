"""
Django proxy model that maps to the shared `cameras` Postgres table.
We don't use Django ORM for migrations — Alembic owns the schema.
This model is managed=False so Django admin can display and edit cameras
without re-creating the table.
"""
import uuid

from django.db import models


class CameraProxy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_id = models.UUIDField()
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, default="ip")
    stream_url = models.CharField(max_length=1024, blank=True, null=True)
    resolution_w = models.IntegerField(null=True, blank=True)
    resolution_h = models.IntegerField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    gpu_slot = models.IntegerField(null=True, blank=True)
    role = models.CharField(max_length=30, default="general")
    ptz = models.BooleanField(default=False)
    onvif_profile = models.CharField(max_length=64, blank=True, null=True)
    health_status = models.CharField(max_length=20, default="unknown")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cameras"
        managed = False
        verbose_name = "Camera"
        verbose_name_plural = "Cameras"

    def __str__(self) -> str:
        return self.name
