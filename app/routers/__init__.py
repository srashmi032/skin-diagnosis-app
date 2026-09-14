from app.routers import analyses, auth, conditions, consents, health, images

ROUTERS = [
    health.router,
    auth.router,
    consents.router,
    images.router,
    analyses.router,
    conditions.router,
]

__all__ = ["ROUTERS"]
