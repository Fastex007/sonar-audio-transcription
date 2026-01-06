#!/bin/bash

# Выход при ошибке
set -e

# Устанавливаем PYTHONPATH для корректной работы импортов
export PYTHONPATH=/app

echo "Waiting for database..."
sleep 2

echo "Creating directories..."
mkdir -p /app/media/recordings
mkdir -p /app/staticfiles

# Переходим в директорию с Django проектом
cd /app/app

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || true

echo "Starting server..."
exec "$@"
