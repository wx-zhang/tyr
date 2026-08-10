from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def ready() -> dict[str, str]:
    return {"status": "ready"}
