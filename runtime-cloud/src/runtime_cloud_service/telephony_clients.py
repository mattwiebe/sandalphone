from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import requests
from livekit import api

from .telephony_provisioning import (
    LiveKitSipPlan,
    TelephonyPlan,
    build_livekit_dispatch_request,
    build_livekit_inbound_trunk_request,
    build_livekit_outbound_trunk_request,
)


@dataclass(frozen=True)
class TwilioCredentials:
    account_sid: str
    auth_token: str


@dataclass(frozen=True)
class LiveKitCredentials:
    url: str
    api_key: str
    api_secret: str


@dataclass(frozen=True)
class ProvisionedLiveKitResources:
    inbound_trunk_id: str
    outbound_trunk_id: str
    dispatch_rule_id: str


@dataclass(frozen=True)
class ProvisionedTwilioResources:
    trunk_sid: str
    credential_list_sid: str
    phone_number_sid: str


class TwilioProvisioner:
    def __init__(self, credentials: TwilioCredentials) -> None:
        self._credentials = credentials
        self._trunking_base = "https://trunking.twilio.com/v1"
        self._voice_base = "https://voice.twilio.com/v1"
        self._phone_base = (
            f"https://api.twilio.com/2010-04-01/Accounts/{credentials.account_sid}"
        )
        self._sip_base = (
            f"https://api.twilio.com/2010-04-01/Accounts/{credentials.account_sid}/SIP"
        )

    def _get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        response = requests.get(
            url,
            auth=(self._credentials.account_sid, self._credentials.auth_token),
            timeout=20,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def _post(self, url: str, data: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            url,
            auth=(self._credentials.account_sid, self._credentials.auth_token),
            data=data,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def find_incoming_phone_number_sid(self, phone_number: str) -> str:
        payload = self._get(
            f"{self._phone_base}/IncomingPhoneNumbers.json",
            params={"PhoneNumber": phone_number},
        )
        for number in payload.get("incoming_phone_numbers", []):
            if number.get("phone_number") == phone_number:
                return str(number["sid"])
        raise RuntimeError(f"Twilio phone number not found: {phone_number}")

    def ensure_trunk(self, plan: TelephonyPlan) -> dict[str, Any]:
        payload = self._get(f"{self._trunking_base}/Trunks")
        for trunk in payload.get("trunks", []):
            if (
                trunk.get("friendly_name") == plan.twilio_trunk_friendly_name
                or trunk.get("domain_name") == plan.twilio_domain_name
            ):
                return trunk
        return self._post(
            f"{self._trunking_base}/Trunks",
            data={
                "FriendlyName": plan.twilio_trunk_friendly_name,
                "DomainName": plan.twilio_domain_name,
            },
        )

    def ensure_origination_url(self, trunk_sid: str, sip_url: str) -> None:
        payload = self._get(f"{self._trunking_base}/Trunks/{trunk_sid}/OriginationUrls")
        for url in payload.get("origination_urls", []):
            if url.get("sip_url") == sip_url:
                return
        self._post(
            f"{self._trunking_base}/Trunks/{trunk_sid}/OriginationUrls",
            data={
                "FriendlyName": "livekit-primary",
                "SipUrl": sip_url,
                "Priority": 10,
                "Weight": 10,
                "Enabled": "true",
            },
        )

    def ensure_phone_number(self, trunk_sid: str, phone_number_sid: str) -> None:
        payload = self._get(f"{self._trunking_base}/Trunks/{trunk_sid}/PhoneNumbers")
        for item in payload.get("phone_numbers", []):
            if item.get("phone_number_sid") == phone_number_sid:
                return
        self._post(
            f"{self._trunking_base}/Trunks/{trunk_sid}/PhoneNumbers",
            data={"PhoneNumberSid": phone_number_sid},
        )

    def ensure_credential_list(self, friendly_name: str) -> dict[str, Any]:
        payload = self._get(f"{self._sip_base}/CredentialLists.json")
        for item in payload.get("credential_lists", []):
            if item.get("friendly_name") == friendly_name:
                return item
        return self._post(
            f"{self._sip_base}/CredentialLists.json",
            data={"FriendlyName": friendly_name},
        )

    def ensure_credential(
        self,
        credential_list_sid: str,
        *,
        username: str,
        password: str,
    ) -> None:
        payload = self._get(
            f"{self._sip_base}/CredentialLists/{credential_list_sid}/Credentials.json"
        )
        for item in payload.get("credentials", []):
            if item.get("username") == username:
                return
        self._post(
            f"{self._sip_base}/CredentialLists/{credential_list_sid}/Credentials.json",
            data={"Username": username, "Password": password},
        )

    def ensure_trunk_credential_list(self, trunk_sid: str, credential_list_sid: str) -> None:
        payload = self._get(f"{self._trunking_base}/Trunks/{trunk_sid}/CredentialLists")
        for item in payload.get("credential_lists", []):
            if item.get("sid") == credential_list_sid:
                return
        self._post(
            f"{self._trunking_base}/Trunks/{trunk_sid}/CredentialLists",
            data={"CredentialListSid": credential_list_sid},
        )

    def ensure_resources(self, plan: TelephonyPlan) -> ProvisionedTwilioResources:
        phone_number_sid = self.find_incoming_phone_number_sid(plan.twilio_phone_number)
        trunk = self.ensure_trunk(plan)
        trunk_sid = str(trunk["sid"])
        self.ensure_origination_url(trunk_sid, plan.twilio_origination_uri)
        self.ensure_phone_number(trunk_sid, phone_number_sid)
        credential_list = self.ensure_credential_list(
            f"{plan.twilio_trunk_friendly_name}-termination"
        )
        credential_list_sid = str(credential_list["sid"])
        self.ensure_credential(
            credential_list_sid,
            username=plan.twilio_auth.username,
            password=plan.twilio_auth.password,
        )
        self.ensure_trunk_credential_list(trunk_sid, credential_list_sid)
        return ProvisionedTwilioResources(
            trunk_sid=trunk_sid,
            credential_list_sid=credential_list_sid,
            phone_number_sid=phone_number_sid,
        )


class LiveKitProvisioner:
    def __init__(self, credentials: LiveKitCredentials) -> None:
        self._credentials = credentials

    async def _create_api(self) -> api.LiveKitAPI:
        return api.LiveKitAPI(
            url=self._credentials.url.replace("wss://", "https://"),
            api_key=self._credentials.api_key,
            api_secret=self._credentials.api_secret,
        )

    async def ensure_resources(self, plan: LiveKitSipPlan) -> ProvisionedLiveKitResources:
        lk = await self._create_api()
        try:
            inbound_list = await lk.sip.list_inbound_trunk(api.ListSIPInboundTrunkRequest())
            inbound = next(
                (
                    item
                    for item in inbound_list.items
                    if item.name == plan.inbound_trunk_name
                ),
                None,
            )
            if inbound is None:
                inbound = await lk.sip.create_inbound_trunk(
                    build_livekit_inbound_trunk_request(plan)
                )

            outbound_list = await lk.sip.list_outbound_trunk(api.ListSIPOutboundTrunkRequest())
            outbound = next(
                (
                    item
                    for item in outbound_list.items
                    if item.name == plan.outbound_trunk_name
                ),
                None,
            )
            if outbound is None:
                outbound = await lk.sip.create_outbound_trunk(
                    build_livekit_outbound_trunk_request(plan)
                )

            rule_list = await lk.sip.list_dispatch_rule(api.ListSIPDispatchRuleRequest())
            rule = next(
                (
                    item
                    for item in rule_list.items
                    if item.name == plan.dispatch_rule_name
                ),
                None,
            )
            if rule is None:
                rule = await lk.sip.create_dispatch_rule(
                    build_livekit_dispatch_request(plan, trunk_id=inbound.sip_trunk_id)
                )

            return ProvisionedLiveKitResources(
                inbound_trunk_id=inbound.sip_trunk_id,
                outbound_trunk_id=outbound.sip_trunk_id,
                dispatch_rule_id=rule.sip_dispatch_rule_id,
            )
        finally:
            await lk.aclose()


def provision_telephony(
    *,
    twilio_credentials: TwilioCredentials,
    livekit_credentials: LiveKitCredentials,
    plan: TelephonyPlan,
) -> tuple[ProvisionedTwilioResources, ProvisionedLiveKitResources]:
    twilio = TwilioProvisioner(twilio_credentials)
    twilio_resources = twilio.ensure_resources(plan)
    livekit = LiveKitProvisioner(livekit_credentials)
    livekit_resources = asyncio.run(livekit.ensure_resources(plan.livekit))
    return twilio_resources, livekit_resources
