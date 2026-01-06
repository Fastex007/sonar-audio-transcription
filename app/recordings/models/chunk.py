from django.db import models
from django.utils import timezone
import uuid

from .session import Session


class AudioChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='chunks')

    chunk_number = models.IntegerField()
    chunk_size = models.IntegerField(help_text="Size in bytes")
    file_path = models.CharField(max_length=500)

    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Чанк"
        verbose_name_plural = "Чанки"
        ordering = ['chunk_number']
        unique_together = [['session', 'chunk_number']]
        indexes = [
            models.Index(fields=['session', 'chunk_number']),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_number} for session {self.session_id}"
