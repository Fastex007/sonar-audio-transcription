import os
import shutil
import struct
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from app.recordings.models import Session, AudioChunk, Transcript, Utterance

logger = logging.getLogger(__name__)

# Глобальный процессор ML (инициализируется в worker'е, не при импорте)
_ml_processor = None


def get_ml_processor_for_task():
    global _ml_processor
    if _ml_processor is None:
        logger.info("🚀 Initializing ML Processor inside Celery worker...")
        from app.recordings.services.processor import MLProcessor
        _ml_processor = MLProcessor()
        logger.info("✅ ML Processor initialized successfully in worker")
    return _ml_processor


@shared_task(bind=True, max_retries=3)
def process_audio_task(self, session_id):
    try:
        logger.info(f"Starting audio processing for session: {session_id}")

        # Получаем сессию
        session = Session.objects.get(id=session_id)
        session.status = 'processing'
        session.processing_started_at = timezone.now()
        session.save()

        # 1. Склеиваем чанки
        logger.info(f"Step 1: Concatenating audio chunks...")
        audio_file_path = concatenate_audio_chunks(session)

        if not audio_file_path or not os.path.exists(audio_file_path):
            raise Exception("Failed to concatenate audio chunks")

        # Обновляем информацию о файле
        session.audio_file = audio_file_path
        session.file_size = os.path.getsize(audio_file_path)
        session.save()

        logger.info(f"Audio file created: {audio_file_path} ({session.file_size} bytes)")

        # 2. Получаем ML процессор (создаётся внутри worker'а, не при импорте)
        processor = get_ml_processor_for_task()

        # 3. Распознавание речи
        logger.info(f"Step 2: Speech recognition with Whisper...")
        transcription_result = processor.transcribe_audio(audio_file_path, language='ru')

        # 4. Диаризация
        logger.info(f"Step 3: Speaker diarization with pyannote...")
        diarization_result = processor.diarize_audio(audio_file_path)

        # 5. Объединяем результаты
        logger.info(f"Step 4: Merging transcription and diarization...")
        utterances = processor.merge_transcription_and_diarization(
            transcription_result,
            diarization_result
        )

        # 6. Сохраняем в БД
        logger.info(f"Step 5: Saving results to database...")
        save_transcription_results(session, transcription_result, utterances)

        # 7. Финализация
        session.status = 'completed'
        session.processing_completed_at = timezone.now()
        session.save()

        logger.info(f"Audio processing completed for session: {session_id}")

        return {
            'session_id': session_id,
            'status': 'completed',
            'total_speakers': len(set(u['speaker'] for u in utterances)),
            'total_utterances': len(utterances)
        }

    except Session.DoesNotExist:
        logger.error(f"Session not found: {session_id}")
        return {'error': 'Session not found'}

    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}", exc_info=True)

        # Сохраняем ошибку
        try:
            session = Session.objects.get(id=session_id)
            session.status = 'failed'
            session.processing_error = str(e)
            session.processing_completed_at = timezone.now()
            session.save()
        except:
            pass

        # Повторяем попытку если возможно
        raise self.retry(exc=e, countdown=60)


def concatenate_audio_chunks(session):
    try:
        chunks_dir = os.path.join(settings.MEDIA_ROOT, "chunks", str(session.id))

        if not os.path.exists(chunks_dir):
            logger.warning(f"Chunks directory not found: {chunks_dir}")
            return None

        # Получаем все чанки из БД отсортированные по номеру
        chunks = AudioChunk.objects.filter(session=session).order_by('chunk_number')

        if not chunks.exists():
            logger.warning(f"No chunks found for session")
            return None

        chunk_files = [chunk.file_path for chunk in chunks]

        # Создаем директорию для итоговых файлов
        recordings_dir = os.path.join(settings.MEDIA_ROOT, "recordings")
        os.makedirs(recordings_dir, exist_ok=True)

        # Имя итогового файла
        timestamp = session.started_at.strftime("%Y%m%d_%H%M%S")
        final_filename = f"recording_{timestamp}_{str(session.id)[:8]}.wav"
        final_filepath = os.path.join(recordings_dir, final_filename)

        if len(chunk_files) == 1:
            # Один чанк - просто копируем
            shutil.copy2(chunk_files[0], final_filepath)
            logger.info(f"Single chunk copied to: {final_filepath}")
        else:
            # Несколько чанков - склеиваем
            concatenate_wav_files(chunk_files, final_filepath)
            logger.info(f"{len(chunk_files)} chunks concatenated to: {final_filepath}")

        # Удаляем временные чанки
        shutil.rmtree(chunks_dir)
        logger.info(f"Temporary chunks directory deleted")

        return final_filepath

    except Exception as e:
        logger.error(f"Error concatenating chunks: {e}", exc_info=True)
        raise


def concatenate_wav_files(input_files, output_file):

    with open(input_files[0], 'rb') as f:
        header = bytearray(f.read(44))

    # Собираем все PCM данные
    pcm_data = bytearray()
    for wav_file in input_files:
        with open(wav_file, 'rb') as f:
            f.read(44)  # Пропускаем заголовок
            pcm_data.extend(f.read())

    # Обновляем размеры в заголовке
    total_size = 36 + len(pcm_data)
    struct.pack_into('<I', header, 4, total_size)
    struct.pack_into('<I', header, 40, len(pcm_data))

    # Записываем итоговый файл
    with open(output_file, 'wb') as f:
        f.write(header)
        f.write(pcm_data)

    logger.debug(f"WAV file created: {len(pcm_data)} bytes PCM data")


def save_transcription_results(session, transcription_result, utterances):
    try:
        # Создаем транскрипт
        full_text = " ".join([u['text'] for u in utterances])

        transcript = Transcript.objects.create(
            session=session,
            full_text=full_text,
            language=transcription_result.get('language', 'ru'),
            total_speakers=len(set(u['speaker'] for u in utterances)),
            total_utterances=len(utterances),
            confidence_avg=sum(u.get('confidence', 0) for u in utterances) / len(utterances) if utterances else 0,
            whisper_model='medium',
            diarization_model='pyannote/speaker-diarization-3.1'
        )

        # Создаем реплики
        for idx, utterance_data in enumerate(utterances):
            Utterance.objects.create(
                transcript=transcript,
                speaker=utterance_data['speaker'],
                text=utterance_data['text'],
                start_time=utterance_data['start'],
                end_time=utterance_data['end'],
                confidence=utterance_data.get('confidence', 0.0),
                sequence_number=idx
            )

        logger.info(f"Saved {len(utterances)} utterances to database")

    except Exception as e:
        logger.error(f"Error saving transcription results: {e}", exc_info=True)
        raise