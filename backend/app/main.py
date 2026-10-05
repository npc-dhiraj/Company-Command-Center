from fastapi import FastAPI

from app.core.database import lifespan
from app.routes.health import router as health_router

app = FastAPI(
    title="Company Command Center",
    lifespan=lifespan,
)

app.include_router(health_router)
