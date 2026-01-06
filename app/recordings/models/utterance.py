import uuid
from django.db import models

from .transcript import Transcript


class Utterance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(Transcript, on_delete=models.CASCADE, related_name='utterances')

    speaker = models.CharField(max_length=50)
    text = models.TextField()

    start_time = models.FloatField()
    end_time = models.FloatField()

    confidence = models.FloatField(default=0.0)
    sequence_number = models.IntegerField()

    class Meta:
        verbose_name = "Фраза"
        verbose_name_plural = "Фразы"
        ordering = ['sequence_number']
        indexes = [
            models.Index(fields=['transcript', 'sequence_number']),
            models.Index(fields=['speaker']),
        ]

    def __str__(self):
        return f"{self.speaker}: {self.text[:50]}..."

    @property
    def duration(self):
        return self.end_time - self.start_time

    @property
    def time_formatted(self):
        minutes = int(self.start_time // 60)
        seconds = int(self.start_time % 60)
        return f"{minutes}:{seconds:02d}"
