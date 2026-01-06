.PHONY: help build up down restart logs shell migrate test clean

help: ## Показать эту справку
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Docker команды
build: ## Собрать Docker образы
	docker compose build

up: ## Запустить контейнеры
	docker compose up -d

down: ## Остановить контейнеры
	docker compose down

restart: ## Перезапустить контейнеры
	docker compose restart

logs: ## Показать логи
	docker compose logs -f

ps: ## Показать статус контейнеров
	docker compose ps

# Приложение
shell: ## Django shell
	docker compose exec web python manage.py shell

bash: ## Bash в контейнере
	docker compose exec web bash

migrate: ## Применить миграции
	docker compose exec web python manage.py migrate

makemigrations: ## Создать миграции
	docker compose exec web python manage.py makemigrations

collectstatic: ## Собрать статику
	docker compose exec web python manage.py collectstatic --noinput

createsuperuser: ## Создать суперпользователя
	docker compose exec web python manage.py createsuperuser

# Разработка
dev: ## Запустить локально без Docker
	source venv/bin/activate && python manage.py runserver

# Тестирование
test: ## Запустить тесты
	docker compose exec web python manage.py test

check: ## Проверить проект
	docker compose exec web python manage.py check

# Очистка
clean: ## Остановить и удалить все контейнеры и volumes
	docker compose down -v

clean-all: ## Полная очистка включая образы
	docker compose down -v --rmi all

prune: ## Очистить неиспользуемые Docker ресурсы
	docker system prune -f

# Утилиты
backup-media: ## Создать backup медиа файлов
	docker run --rm -v sonar_media_data:/data -v $$(pwd):/backup alpine tar czf /backup/media-backup-$$(date +%Y%m%d-%H%M%S).tar.gz /data

restore-media: ## Восстановить медиа файлы (требует файл media-backup.tar.gz)
	docker run --rm -v sonar_media_data:/data -v $$(pwd):/backup alpine tar xzf /backup/media-backup.tar.gz -C /

backup-db: ## Создать backup базы данных
	docker compose exec web python manage.py dumpdata > backup-$$(date +%Y%m%d-%H%M%S).json

# Production
prod-build: ## Собрать production образы
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

prod-up: ## Запустить production
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
