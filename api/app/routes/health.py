from fastapi import APIRouter

router = APIRouter(tags=["système"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
