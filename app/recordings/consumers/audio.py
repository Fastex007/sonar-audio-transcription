import base64
import json
import os
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.utils import timezone

from app.recordings.models import Session, AudioChunk

logger = logging.getLogger(__name__)


class AudioConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            # Создаем новую сессию записи
            self.session = await self.create_session()
            self.session_id = str(self.session.id)
            self.chunk_counter = 0

            # Создаем директорию для чанков
            self.chunks_dir = os.path.join(settings.MEDIA_ROOT, "chunks", self.session_id)
            os.makedirs(self.chunks_dir, exist_ok=True)

            await self.accept()

            # Отправляем session_id клиенту
            await self.send(text_data=json.dumps({
                'type': 'session_started',
                'session_id': self.session_id,
                'status': 'connected'
            }))

            logger.info(f"New session started: {self.session_id}")

        except Exception as e:
            logger.error(f"Error in connect: {e}", exc_info=True)
            await self.close()

    async def disconnect(self, close_code):
        try:
            # Обновляем статус сессии
            if hasattr(self, 'session') and hasattr(self, 'session_id'):
                logger.info(f"Session {self.session_id} disconnecting (code: {close_code})")

                await self.finalize_session(close_code)

                # Запускаем обработку аудио в Celery
                from app.recordings.tasks.processing import process_audio_task
                process_audio_task.delay(self.session_id)
            else:
                logger.warning(f"WebSocket disconnected before session was created (code: {close_code})")

        except Exception as e:
            logger.error(f"Error in disconnect: {e}", exc_info=True)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            if text_data:
                # JSON сообщения (метаданные)
                data = json.loads(text_data)
                message_type = data.get('type')

                if message_type == 'audio_chunk':
                    # Бинарные данные закодированы в base64
                    await self.handle_audio_chunk(data)

                elif message_type == 'metadata':
                    # Обновляем метаданные сессии
                    await self.update_metadata(data)

            elif bytes_data:
                # Прямая передача бинарных данных
                await self.handle_binary_chunk(bytes_data)

        except Exception as e:
            logger.error(f"Error receiving data: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_audio_chunk(self, data):
        try:
            self.chunk_counter += 1

            # Декодируем base64
            audio_data = base64.b64decode(data.get('audio_data', ''))
            chunk_number = data.get('chunk_number', self.chunk_counter)

            # Сохраняем чанк
            chunk_path = await self.save_chunk(audio_data, chunk_number)

            # Отправляем подтверждение
            await self.send(text_data=json.dumps({
                'type': 'chunk_received',
                'chunk_number': chunk_number,
                'size': len(audio_data)
            }))

            logger.debug(f"Chunk {chunk_number} received: {len(audio_data)} bytes")

        except Exception as e:
            logger.error(f"Error handling audio chunk: {e}", exc_info=True)
            raise

    async def handle_binary_chunk(self, bytes_data):
        try:
            self.chunk_counter += 1

            # Сохраняем чанк
            chunk_path = await self.save_chunk(bytes_data, self.chunk_counter)

            # Отправляем подтверждение
            await self.send(text_data=json.dumps({
                'type': 'chunk_received',
                'chunk_number': self.chunk_counter,
                'size': len(bytes_data)
            }))

            logger.debug(f"Binary chunk {self.chunk_counter} received: {len(bytes_data)} bytes")

        except Exception as e:
            logger.error(f"Error handling binary chunk: {e}", exc_info=True)
            raise

    @database_sync_to_async
    def create_session(self):
        session = Session.objects.create(
            status='active',
            started_at=timezone.now()
        )
        return session

    @database_sync_to_async
    def save_chunk(self, audio_data, chunk_number):
        chunk_filename = f"chunk_{chunk_number:04d}.wav"
        chunk_filepath = os.path.join(self.chunks_dir, chunk_filename)

        with open(chunk_filepath, 'wb') as f:
            f.write(audio_data)

        # Сохраняем запись в БД
        AudioChunk.objects.create(
            session=self.session,
            chunk_number=chunk_number,
            chunk_size=len(audio_data),
            file_path=chunk_filepath
        )

        # Обновляем счетчик чанков в сессии
        self.session.total_chunks = chunk_number
        self.session.save(update_fields=['total_chunks'])

        return chunk_filepath

    @database_sync_to_async
    def update_metadata(self, data):
        metadata = data.get('metadata', {})

        logger.info(f"Updating session {self.session_id} metadata: {metadata}")

        # Tab information
        if 'tab_url' in metadata:
            self.session.tab_url = metadata['tab_url']
        if 'tab_title' in metadata:
            self.session.tab_title = metadata['tab_title']
        if 'tab_favicon' in metadata:
            self.session.tab_favicon = metadata['tab_favicon']

        # Browser and connection info
        if 'user_agent' in metadata:
            self.session.user_agent = metadata['user_agent']
        if 'ip_address' in metadata:
            self.session.ip_address = metadata['ip_address']
        if 'browser_info' in metadata:
            self.session.browser_info = metadata['browser_info']

        self.session.save()
        logger.info(f"Session {self.session_id} metadata updated successfully")

    @database_sync_to_async
    def finalize_session(self, close_code):
        self.session.ended_at = timezone.now()

        # Определяем статус в зависимости от кода закрытия
        if close_code == 1000:
            # Нормальное закрытие
            self.session.status = 'completed'
        else:
            # Аварийное закрытие
            self.session.status = 'failed'

        self.session.save()

        logger.info(f"Session {self.session_id} finalized with status: {self.session.status}")