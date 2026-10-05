from fastapi import FastAPI

from app.core.database import lifespan
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.users import router as users_router

app = FastAPI(
    title="Company Command Center",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
