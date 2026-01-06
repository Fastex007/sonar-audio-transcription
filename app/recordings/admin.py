from django.contrib import admin
from .models import Session, AudioChunk, Transcript, Utterance


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'started_at', 'status', 'total_chunks', 'tab_title', 'tab_url_short')
    list_filter = ('status', 'started_at')
    search_fields = ('id', 'tab_url', 'tab_title', 'ip_address')
    readonly_fields = ('id', 'started_at', 'ended_at', 'processing_started_at', 'processing_completed_at')

    fieldsets = (
        ('Основная информация', {
            'fields': ('id', 'status', 'started_at', 'ended_at')
        }),
        ('Информация о вкладке', {
            'fields': ('tab_url', 'tab_title', 'tab_favicon', 'browser_info')
        }),
        ('Запись', {
            'fields': ('total_chunks', 'total_duration', 'audio_file', 'file_size')
        }),
        ('Служебная информация', {
            'fields': ('user_agent', 'ip_address')
        }),
        ('Обработка', {
            'fields': ('processing_started_at', 'processing_completed_at', 'processing_error')
        }),
    )

    def tab_url_short(self, obj):
        if obj.tab_url:
            return obj.tab_url[:50] + '...' if len(obj.tab_url) > 50 else obj.tab_url
        return '-'
    tab_url_short.short_description = 'URL вкладки'


@admin.register(AudioChunk)
class AudioChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'chunk_number', 'chunk_size', 'received_at')
    list_filter = ('received_at',)
    search_fields = ('session__id',)


@admin.register(Transcript)
class TranscriptAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'language', 'total_speakers', 'total_utterances', 'created_at')
    list_filter = ('language', 'created_at')
    search_fields = ('session__id', 'full_text')
    readonly_fields = ('created_at',)


@admin.register(Utterance)
class UtteranceAdmin(admin.ModelAdmin):
    list_display = ('id', 'transcript', 'speaker', 'text_short', 'start_time', 'end_time', 'confidence')
    list_filter = ('speaker',)
    search_fields = ('text', 'speaker')

    def text_short(self, obj):
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    text_short.short_description = 'Текст'
