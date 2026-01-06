#!/bin/bash
# Удобный скрипт для запуска Django команд в Docker контейнере

if [ -z "$1" ]; then
    echo "Использование: ./manage.sh <django_command> [args...]"
    echo ""
    echo "Примеры:"
    echo "  ./manage.sh makemigrations"
    echo "  ./manage.sh migrate"
    echo "  ./manage.sh createsuperuser"
    echo "  ./manage.sh shell"
    echo "  ./manage.sh showmigrations"
    exit 1
fi

docker compose exec api sh -c "export PYTHONPATH=/app && cd /app/app && python manage.py $*"
