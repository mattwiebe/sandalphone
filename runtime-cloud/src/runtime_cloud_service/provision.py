from __future__ import annotations

import json
import os
import secrets

from .telephony_clients import (
    LiveKitCredentials,
    TwilioCredentials,
    provision_telephony,
)
from .telephony_provisioning import TwilioTerminationAuth, build_telephony_plan


def main() -> None:
    trunk_stem = os.environ["TWILIO_TRUNK_STEM"]
    phone_number = os.environ["TWILIO_PHONE_NUMBER"]
    room_name = os.environ.get("LIVEKIT_ROOM_NAME", "call-main")
    username = os.environ.get("TWILIO_TERMINATION_USERNAME", f"{trunk_stem}-outbound")
    password = os.environ.get("TWILIO_TERMINATION_PASSWORD", secrets.token_urlsafe(24))

    plan = build_telephony_plan(
        trunk_stem=trunk_stem,
        phone_number=phone_number,
        livekit_url=os.environ["LIVEKIT_URL"],
        room_name=room_name,
        twilio_auth=TwilioTerminationAuth(
            username=username,
            password=password,
        ),
    )
    twilio_resources, livekit_resources = provision_telephony(
        twilio_credentials=TwilioCredentials(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        ),
        livekit_credentials=LiveKitCredentials(
            url=os.environ["LIVEKIT_URL"],
            api_key=os.environ["LIVEKIT_API_KEY"],
            api_secret=os.environ["LIVEKIT_API_SECRET"],
        ),
        plan=plan,
    )
    print(
        json.dumps(
            {
                "twilio_trunk_sid": twilio_resources.trunk_sid,
                "twilio_credential_list_sid": twilio_resources.credential_list_sid,
                "twilio_phone_number_sid": twilio_resources.phone_number_sid,
                "livekit_inbound_trunk_id": livekit_resources.inbound_trunk_id,
                "livekit_outbound_trunk_id": livekit_resources.outbound_trunk_id,
                "livekit_dispatch_rule_id": livekit_resources.dispatch_rule_id,
                "room_name": room_name,
                "twilio_termination_username": username,
                "twilio_termination_password": password,
                "twilio_origination_uri": plan.twilio_origination_uri,
                "twilio_domain_name": plan.twilio_domain_name,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
