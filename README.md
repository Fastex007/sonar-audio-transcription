# Sonar - Audio Transcription System

Real-time audio transcription system with speaker diarization. Captures audio from browser tabs, transcribes speech using Whisper, and identifies speakers using Pyannote.

## Features

- WebSocket-based real-time audio capture from browser tabs
- Speech-to-text transcription (Whisper)
- Speaker diarization (Pyannote)
- Session management and recording history
- Browser extension for Chrome/Edge
- RESTful API and WebSocket support

## Tech Stack

**Backend:**
- Django 4.2
- Django Ninja (REST API)
- Django Channels (WebSocket)
- Celery (async task processing)
- PostgreSQL / SQLite
- Redis (channels & celery broker)

**ML Models:**
- OpenAI Whisper (speech recognition)
- Pyannote.audio (speaker diarization)
- PyTorch

**Frontend:**
- Chrome Extension (Manifest V3)
- Vanilla JavaScript

## System Requirements

- Python 3.12+
- PostgreSQL 14+ (production) or SQLite (development)
- Redis 5+
- Docker & Docker Compose (optional)
- Chrome/Edge browser

## Installation

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd sonar
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Run migrations:
```bash
cd app
python manage.py migrate
python manage.py createsuperuser
```

6. Start services:

Terminal 1 (Django):
```bash
daphne -b 0.0.0.0 -p 8001 config.asgi:application
```

Terminal 2 (Celery):
```bash
celery -A config worker -l info
```

Terminal 3 (Redis):
```bash
redis-server
```

### Docker Deployment

```bash
docker-compose up -d
```

Access:
- Django Admin: http://localhost:8000/admin
- API Documentation: http://localhost:8000/api/docs
- WebSocket: ws://localhost:8001/ws/audio/

## Configuration

### Environment Variables

Create `.env` file:

```env
# Django
DEBUG=True
DJANGO_SECRET_KEY=your-secret-key
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/sonar

# Redis
REDIS_URL=redis://localhost:6379/0

# ML Models
HF_TOKEN=hf_your_huggingface_token
```

### HuggingFace Token

Required for speaker diarization:

1. Get token: https://huggingface.co/settings/tokens
2. Accept terms: https://huggingface.co/pyannote/speaker-diarization-3.1
3. Add to `.env`: `HF_TOKEN=hf_...`

## Browser Extension Setup

1. Open Chrome/Edge
2. Go to `chrome://extensions/`
3. Enable "Developer mode"
4. Click "Load unpacked"
5. Select `extension/` folder

## Usage

### Recording Audio

1. Click extension icon
2. Click "Start Recording"
3. Grant tab capture permission
4. Audio streams to backend via WebSocket
5. Click "Stop Recording" when done
6. Processing starts automatically

### API Endpoints

```
GET  /api/recordings          - List all recordings
GET  /api/play/{filename}     - Stream recording
DELETE /api/delete/{filename} - Delete recording
```

### WebSocket Protocol

Connect to `ws://localhost:8001/ws/audio/`

**Messages:**

Client → Server:
```json
{
  "type": "audio_chunk",
  "audio_data": "base64_encoded_wav",
  "chunk_number": 1
}
```

```json
{
  "type": "metadata",
  "metadata": {
    "tab_url": "https://example.com",
    "tab_title": "Example",
    "user_agent": "..."
  }
}
```

Server → Client:
```json
{
  "type": "session_started",
  "session_id": "uuid",
  "status": "connected"
}
```

```json
{
  "type": "chunk_received",
  "chunk_number": 1,
  "size": 12345
}
```

## Processing Pipeline

1. Audio chunks received via WebSocket
2. Saved to disk and database
3. Celery task triggered on session completion
4. Chunks concatenated into single WAV file
5. Whisper transcribes audio to text
6. Pyannote identifies speakers
7. Results merged and saved to database

## Architecture

```
extension/
  background.js     - Service worker
  offscreen.js      - Audio capture
  popup.js          - UI controller

app/
  config/           - Django settings
  recordings/
    models/         - Database models
    consumers/      - WebSocket handlers
    tasks/          - Celery tasks
    services/       - ML processing
    api/            - REST endpoints
```

## Development

### Run Tests

```bash
python manage.py test
```

### Code Quality

```bash
black .
flake8
mypy app/
```

### Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

## ML Models

### Model Caching

Models are cached in Docker volume `models_cache`:
- Whisper model: ~150MB (base) or ~1.5GB (medium)
- Pyannote model: ~300MB

First run downloads models (10-15 min). Subsequent runs load from cache (30-60 sec).

### Performance

**CPU (current config):**
- 1 min audio = ~40-60 sec processing
- Whisper: ~30 sec
- Pyannote: ~20 sec

**GPU (if configured):**
- 1 min audio = ~5-10 sec processing
- 4-6x speedup

See [docs/ML_MODELS.md](docs/ML_MODELS.md) for details.

## Troubleshooting

### WebSocket Connection Failed

- Check Daphne is running on port 8001
- Verify Redis is running
- Check CORS settings

### ML Processing Errors

- Verify HF_TOKEN is set correctly
- Check disk space (3GB+ required)
- Review worker logs: `docker-compose logs worker`

### Extension Not Working

- Reload extension after code changes
- Check background service worker console
- Verify API_BASE_URL in background.js

## Production Deployment

1. Set `DEBUG=False`
2. Configure PostgreSQL
3. Set strong `DJANGO_SECRET_KEY`
4. Configure HTTPS/WSS
5. Set proper `DJANGO_ALLOWED_HOSTS`
6. Use production-grade ASGI server
7. Set up nginx reverse proxy
8. Configure SSL certificates


## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Write tests
5. Submit pull request
