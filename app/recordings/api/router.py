from ninja import Router
from app.recordings.api import recordings

router = Router()

router.add_router("", recordings.router, tags=["recordings"])
