from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from booking.config import settings
import booking.models  # noqa: F401  (register tables)
from booking.errors import register_error_handlers


def create_app(init_db: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if init_db:
            from booking.db import Base, engine
            Base.metadata.create_all(engine)
            from sqlalchemy import select

            from booking import clock
            from booking.db import SessionLocal
            from booking.models import Tenant
            from booking.seed import seed
            with SessionLocal() as s:
                if s.scalars(select(Tenant.id).limit(1)).first() is None:
                    seed(s, clock.now())
        yield

    app = FastAPI(title="Booking API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    from booking.routers import admin, services, staff, tenants
    app.include_router(admin.router)
    app.include_router(tenants.router)
    app.include_router(staff.router)
    app.include_router(services.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
