#!/usr/bin/env python3
"""
Скрипт для проверки загрузки ML моделей
Запустить: docker compose exec worker python3 /app/test_ml_loading.py
"""

import sys
import os

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/app/app')

import django
django.setup()

print("\n" + "="*70)
print("🧪 Testing ML Models Loading...")
print("="*70 + "\n")

# Импортируем и инициализируем процессор
from app.recordings.services.processor import get_ml_processor

print("\n📥 Initializing ML Processor (this will load models)...\n")

processor = get_ml_processor()

print("\n" + "="*70)
print("✅ SUCCESS! ML Processor is ready")
print("="*70)
print(f"\n📊 Details:")
print(f"   Whisper Device: {processor.whisper_device}")
print(f"   Torch Device: {processor.torch_device}")
print(f"   Whisper: {'✅ Loaded' if processor.whisper_model else '❌ Not loaded'}")
print(f"   Diarization: {'✅ Loaded' if processor.diarization_pipeline else '❌ Not loaded'}")
if processor.diarization_pipeline:
    print(f"   🎉 Diarization is working! No segmentation fault!")
else:
    print(f"   ⚠️  Diarization is not available (check HF_TOKEN)")
print()
