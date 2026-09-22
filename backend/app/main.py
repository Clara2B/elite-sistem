from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.audiencias import router as audiencias_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.laudos import router as laudos_router
from app.api.pendencias import router as pendencias_router
from app.api.usuarios import router as usuarios_router
from app.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sem DATABASE_URL configurado, o app ainda sobe (útil para dev local
    # sem banco e para o healthcheck) — só as rotas de negócio exigem banco.
    if settings.database_url:
        init_db()
    yield


app = FastAPI(title="Elite Sistem API", lifespan=lifespan)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(usuarios_router)
app.include_router(laudos_router)
app.include_router(audiencias_router)
app.include_router(pendencias_router)
