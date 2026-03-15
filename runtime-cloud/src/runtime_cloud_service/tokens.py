from livekit import api

from .config import RuntimeCloudConfig


def issue_room_participant_token(
    config: RuntimeCloudConfig,
    room_name: str,
    identity: str,
    name: str | None = None,
) -> str:
    token = (
        api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
        .with_identity(identity)
        .with_name(name or identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
    )
    return token.to_jwt()


def issue_trusted_leg_token(
    config: RuntimeCloudConfig,
    room_name: str,
    identity: str,
    name: str | None = None,
) -> str:
    return issue_room_participant_token(config, room_name, identity, name)
