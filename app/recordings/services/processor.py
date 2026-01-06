import os
import logging
import torch
import whisper
from pyannote.audio import Pipeline
import warnings
from tqdm import tqdm

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class MLProcessor:
    def _setup_devices(self):
        logger.info("🔧 Настройка устройств для обработки...")
        logger.info(f"   CUDA доступен: {torch.cuda.is_available()}")
        logger.info(f"   MPS доступен: {torch.backends.mps.is_available()}")

        # Проверяем, запущены ли мы в Docker (MPS не работает в Docker на Mac)
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('CUDA_VISIBLE_DEVICES') == ''
        if is_docker:
            logger.info("🐳 Обнаружен Docker - используем только CPU")

        # ВАЖНО: На M1/M2 Mac Whisper работает стабильнее на CPU
        # из-за проблем совместимости с MPS на ARM64
        self.whisper_device = "cpu"

        # Для diarization пробуем использовать GPU/MPS если доступно
        # НО не в Docker на Mac (MPS не поддерживается)
        if torch.cuda.is_available() and not is_docker:
            self.torch_device = "cuda"
            logger.info("✅ Используем CUDA GPU")
        elif torch.backends.mps.is_available() and not is_docker:
            self.torch_device = "mps"
            logger.info("✅ Используем CPU для Whisper, MPS для диаризации")
        else:
            self.torch_device = "cpu"
            logger.info("✅ Используем CPU для всех операций")

        # Для обратной совместимости
        self.device = self.whisper_device

        logger.info(f"📱 Whisper device: {self.whisper_device.upper()}")
        logger.info(f"📱 Torch device: {self.torch_device.upper()}")

    def __init__(self):
        logger.info("=" * 70)
        logger.info("🚀 Initializing ML Processor...")
        logger.info("=" * 70)

        # Настройка устройств
        self._setup_devices()

        # Информация о кешировании
        cache_dir = os.path.expanduser("~/.cache")
        whisper_cache = os.path.join(cache_dir, "whisper")
        torch_cache = os.path.join(cache_dir, "torch")

        whisper_cached = os.path.exists(os.path.join(whisper_cache, "base.pt"))
        logger.info(f"📦 Whisper cache: {'✅ Found' if whisper_cached else '⏬ Will download (~150MB)'}")
        logger.info(f"📂 Cache location: {whisper_cache}")

        # Загружаем Whisper модель (base для стабильности на ARM64)
        logger.info("")
        logger.info("=" * 70)
        logger.info("🎤 Loading Whisper model (base)...")
        logger.info("=" * 70)

        if not whisper_cached:
            logger.info("⏬ Downloading Whisper model... (~150MB)")
            logger.info("💡 Tip: Model will be cached for future use")

        self.whisper_model = whisper.load_model("base", device=self.device)
        logger.info("✅ Whisper model loaded successfully")

        # Загружаем pyannote модель для диаризации
        logger.info("")
        logger.info("=" * 70)
        logger.info("👥 Loading pyannote diarization model...")
        logger.info("=" * 70)

        try:
            # Получаем токен HuggingFace
            hf_token = os.environ.get('HF_TOKEN', None)
            logger.info(f"🔑 HuggingFace token: {'✅ Found' if hf_token else '❌ Not set'}")

            if not hf_token:
                logger.error("HUGGINGFACE_TOKEN не установлен! Диаризация не будет работать")
                logger.error("Установите токен: export HF_TOKEN=hf_your_token")
                self.diarization_pipeline = None
                logger.warning("⚠️  Diarization отключена из-за отсутствия токена")
            elif not hf_token.startswith('hf_'):
                logger.error(f"Неверный формат токена HuggingFace: {hf_token[:10]}...")
                logger.error("Токен должен начинаться с 'hf_'")
                self.diarization_pipeline = None
                logger.warning("⚠️  Diarization отключена из-за неверного формата токена")
            else:
                # Загружаем модель
                logger.info("⏬ Загрузка модели pyannote/speaker-diarization-3.1...")
                try:
                    self.diarization_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=hf_token
                    )
                    logger.info("✅ Модель pyannote успешно загружена")
                except Exception as download_error:
                    logger.error(f"Ошибка загрузки модели 3.1: {download_error}")
                    logger.info("Пробуем альтернативную модель pyannote/speaker-diarization...")
                    try:
                        self.diarization_pipeline = Pipeline.from_pretrained(
                            "pyannote/speaker-diarization",
                            use_auth_token=hf_token
                        )
                        logger.info("✅ Альтернативная модель загружена")
                    except Exception as alt_error:
                        logger.error(f"Ошибка загрузки альтернативной модели: {alt_error}")
                        raise download_error

                # КРИТИЧНО: Переносим pipeline на устройство с fallback
                if self.torch_device != "cpu":
                    try:
                        logger.info(f"Переносим diarization на {self.torch_device.upper()}...")
                        self.diarization_pipeline = self.diarization_pipeline.to(
                            torch.device(self.torch_device)
                        )
                        logger.info(f"✅ Diarization загружена на {self.torch_device.upper()}")
                    except Exception as e:
                        logger.warning(f"⚠️  Не удалось переместить на {self.torch_device}: {e}")
                        logger.info("Используем CPU вместо этого...")
                        self.diarization_pipeline = self.diarization_pipeline.to(
                            torch.device("cpu")
                        )
                        logger.info("✅ Diarization загружена на CPU")
                else:
                    self.diarization_pipeline = self.diarization_pipeline.to(
                        torch.device("cpu")
                    )
                    logger.info("✅ Diarization загружена на CPU")

                logger.info("✅ Diarization готова к использованию")

        except Exception as e:
            logger.error(f"Критическая ошибка загрузки pyannote: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            import traceback
            logger.error(f"Стек вызовов:\n{traceback.format_exc()}")
            logger.warning("⚠️  Diarization будет отключена")
            self.diarization_pipeline = None

        logger.info("")
        logger.info("=" * 70)
        logger.info("✨ ML Processor ready!")
        logger.info("=" * 70)

    def transcribe_audio(self, audio_path, language='ru'):
        logger.info(f"Transcribing audio: {audio_path}")

        try:
            # Распознаем речь
            # fp16=False критично для стабильности на ARM64 Mac
            result = self.whisper_model.transcribe(
                audio_path,
                language=language,
                task='transcribe',
                verbose=False,
                word_timestamps=True,  # Получаем временные метки для слов
                fp16=False  # Отключаем fp16 для совместимости с ARM64
            )

            logger.info("Transcription completed successfully")
            logger.info(f"Detected language: {result['language']}")
            logger.info(f"Text length: {len(result['text'])} chars")
            logger.info(f"Segments: {len(result['segments'])}")

            return result

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

    def diarize_audio(self, audio_path):
        if not self.diarization_pipeline:
            logger.warning("Diarization pipeline not available, skipping")
            return []

        logger.info(f"Diarizing audio: {audio_path}")

        try:
            # Запускаем диаризацию
            diarization = self.diarization_pipeline(audio_path)

            # Преобразуем результат в список
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    'start': turn.start,
                    'end': turn.end,
                    'speaker': speaker
                })

            logger.info("Diarization completed successfully")
            logger.info(f"Found {len(set(s['speaker'] for s in segments))} speakers")
            logger.info(f"Total segments: {len(segments)}")

            return segments

        except Exception as e:
            logger.error(f"Diarization error: {e}")
            # Не падаем, просто возвращаем пустой список
            return []

    def merge_transcription_and_diarization(self, transcription, diarization):
        logger.info("Merging transcription and diarization...")

        utterances = []

        if not diarization:
            # Если диаризация не прошла, используем только транскрипцию
            logger.info("No diarization data, using transcription only")
            for idx, segment in enumerate(transcription['segments']):
                utterances.append({
                    'speaker': 'SPEAKER_00',
                    'text': segment['text'].strip(),
                    'start': segment['start'],
                    'end': segment['end'],
                    'confidence': segment.get('no_speech_prob', 0.0)
                })
            return utterances

        # Объединяем сегменты транскрипции с диаризацией
        for segment in transcription['segments']:
            seg_start = segment['start']
            seg_end = segment['end']
            seg_text = segment['text'].strip()

            # Находим спикера для этого сегмента
            # Берем спикера с наибольшим перекрытием
            best_speaker = 'SPEAKER_00'
            max_overlap = 0

            for dia_seg in diarization:
                # Вычисляем перекрытие
                overlap_start = max(seg_start, dia_seg['start'])
                overlap_end = min(seg_end, dia_seg['end'])
                overlap = max(0, overlap_end - overlap_start)

                if overlap > max_overlap:
                    max_overlap = overlap
                    best_speaker = dia_seg['speaker']

            utterances.append({
                'speaker': best_speaker,
                'text': seg_text,
                'start': seg_start,
                'end': seg_end,
                'confidence': 1.0 - segment.get('no_speech_prob', 0.0)
            })

        # Группируем последовательные utterances одного спикера
        merged_utterances = []
        current = None

        for utt in utterances:
            if current is None:
                current = utt.copy()
            elif current['speaker'] == utt['speaker'] and (utt['start'] - current['end']) < 1.0:
                # Тот же спикер и перерыв < 1 сек - объединяем
                current['text'] += ' ' + utt['text']
                current['end'] = utt['end']
                current['confidence'] = (current['confidence'] + utt['confidence']) / 2
            else:
                # Новый спикер или большой перерыв - сохраняем и начинаем новый
                merged_utterances.append(current)
                current = utt.copy()

        if current:
            merged_utterances.append(current)

        logger.info(f"Merged {len(merged_utterances)} utterances successfully")

        return merged_utterances


# Singleton instance - модели загружаются один раз при импорте
_ml_processor = None


def get_ml_processor():
    global _ml_processor
    if _ml_processor is None:
        _ml_processor = MLProcessor()
    return _ml_processor