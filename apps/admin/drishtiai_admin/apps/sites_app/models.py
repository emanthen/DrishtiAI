import uuid
from django.db import models


class SiteProxy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.UUIDField()
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True, null=True)
    timezone = models.CharField(max_length=64, default="Asia/Kathmandu")
    plate_region = models.CharField(max_length=10, default="NP")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sites"
        managed = False
        verbose_name = "Site"
        verbose_name_plural = "Sites"

    def __str__(self) -> str:
        return self.name
