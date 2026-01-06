from django.urls import re_path
from app.recordings.consumers.audio import AudioConsumer

websocket_urlpatterns = [
    re_path(r'ws/audio/$', AudioConsumer.as_asgi()),
]