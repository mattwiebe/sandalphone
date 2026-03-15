from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import load_runtime_cloud_config
from .tokens import issue_trusted_leg_token


app = FastAPI(title="Levi Runtime Cloud")


class TrustedTokenRequest(BaseModel):
    room_name: str
    identity: str
    name: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    config = load_runtime_cloud_config()
    missing = [
        key
        for key, value in {
            "LIVEKIT_URL": config.livekit_url,
            "LIVEKIT_API_KEY": config.livekit_api_key,
            "LIVEKIT_API_SECRET": config.livekit_api_secret,
        }.items()
        if not value
    ]
    return {
        "status": "healthy" if not missing else "degraded",
        "missing": ",".join(missing),
    }


@app.post("/tokens/trusted")
def trusted_token(request: TrustedTokenRequest) -> dict[str, str]:
    config = load_runtime_cloud_config()
    if not config.livekit_api_key or not config.livekit_api_secret:
        raise HTTPException(status_code=503, detail="LiveKit credentials not configured")

    token = issue_trusted_leg_token(
        config=config,
        room_name=request.room_name,
        identity=request.identity,
        name=request.name,
    )
    return {
        "token": token,
        "room_name": request.room_name,
        "identity": request.identity,
        "livekit_url": config.livekit_url,
    }
