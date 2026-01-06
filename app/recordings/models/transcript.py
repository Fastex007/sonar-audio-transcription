from django.db import models
from django.utils import timezone
import uuid

from .session import Session


class Transcript(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name='transcript')

    full_text = models.TextField()
    language = models.CharField(max_length=10, default='ru')

    total_speakers = models.IntegerField(default=0)
    total_utterances = models.IntegerField(default=0)
    confidence_avg = models.FloatField(default=0.0, help_text="Average confidence score")

    whisper_model = models.CharField(max_length=50, default='medium')
    diarization_model = models.CharField(max_length=100, default='pyannote/speaker-diarization-3.1')

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Транскрипт"
        verbose_name_plural = "Транскрипты"
        indexes = [
            models.Index(fields=['session']),
        ]

    def __str__(self):
        return f"Transcript for session {self.session_id}"
