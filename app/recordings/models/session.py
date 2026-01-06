from django.db import models
from django.utils import timezone
import uuid


class Session(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('processing', 'Processing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    total_chunks = models.IntegerField(default=0)
    total_duration = models.FloatField(default=0.0, help_text="Duration in seconds")

    audio_file = models.CharField(max_length=500, null=True, blank=True)
    file_size = models.BigIntegerField(default=0, help_text="File size in bytes")

    tab_url = models.URLField(max_length=2000, null=True, blank=True, help_text="URL вкладки откуда была запись")
    tab_title = models.CharField(max_length=500, null=True, blank=True, help_text="Заголовок вкладки")
    tab_favicon = models.URLField(max_length=2000, null=True, blank=True, help_text="URL иконки сайта")

    user_agent = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    browser_info = models.JSONField(null=True, blank=True, help_text="Дополнительная информация о браузере")

    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Сессия"
        verbose_name_plural = "Сессии"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['-started_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Session {self.id} ({self.status})"

    @property
    def duration_formatted(self):
        minutes = int(self.total_duration // 60)
        seconds = int(self.total_duration % 60)
        return f"{minutes}:{seconds:02d}"
