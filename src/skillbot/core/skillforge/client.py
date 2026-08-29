from http import HTTPStatus

import httpx
from skillforge_client import AuthenticatedClient, Client
from skillforge_client.api.bot import upsert_discord_user_endpoint_api_v1_bot_users_discord_id_put
from skillforge_client.api.system import liveness_check_health_live_get
from skillforge_client.models import DiscordUserUpsertRequest, HealthCheckResponse

from skillbot.core.config import SkillForgeSettings

from .auth import ClientCredentialsAuth
from .helpers import require_response, skillforge_boundary
from .models import DiscordUser, MemberRole


@skillforge_boundary
class SkillForgeClient:
    def __init__(self, settings: SkillForgeSettings) -> None:
        self.settings = settings
        timeout = httpx.Timeout(settings.timeout_seconds)

        self._public_client = Client(
            base_url=settings.base_url,
            timeout=timeout,
            raise_on_unexpected_status=True,
        )

        self._auth = ClientCredentialsAuth(
            client=self._public_client,
            client_id=settings.client_id,
            client_secret=settings.client_secret,
        )
        self._http_client = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=timeout,
            auth=self._auth,
        )
        self._client = AuthenticatedClient(
            base_url=settings.base_url,
            # Authentication is supplied by ClientCredentialsAuth on the AsyncClient.
            token="",
            raise_on_unexpected_status=True,
        ).set_async_httpx_client(self._http_client)

    async def close(self) -> None:
        try:
            await self._http_client.aclose()
        finally:
            await self._public_client.get_async_httpx_client().aclose()

    async def liveness_check(self) -> HealthCheckResponse | None:
        return await liveness_check_health_live_get.asyncio(client=self._public_client)

    async def upsert_discord_user(
        self,
        discord_id: int,
        *,
        nick_name: str,
        role: MemberRole,
        active: bool = True,
    ) -> DiscordUser:
        request = DiscordUserUpsertRequest(
            nick_name=nick_name,
            role=role,
            active=active,
        )

        response = await upsert_discord_user_endpoint_api_v1_bot_users_discord_id_put.asyncio_detailed(
            discord_id=discord_id,
            client=self._client,
            body=request,
        )

        return require_response(
            response,
            status=HTTPStatus.OK,
            model=DiscordUser,
        )
