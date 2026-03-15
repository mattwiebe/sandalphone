import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class RuntimeCloudConfig:
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    trusted_room_prefix: str = "call"


def load_runtime_cloud_config() -> RuntimeCloudConfig:
    return RuntimeCloudConfig(
        livekit_url=os.getenv("LIVEKIT_URL", ""),
        livekit_api_key=os.getenv("LIVEKIT_API_KEY", ""),
        livekit_api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
        trusted_room_prefix=os.getenv("TRUSTED_ROOM_PREFIX", "call"),
    )
