import asyncio
from collections.abc import AsyncGenerator
from http import HTTPStatus
from time import monotonic
from typing import Never

import httpx
from pydantic import SecretStr
from skillforge_client import Client
from skillforge_client.api.auth import create_token_api_v1_auth_token_post
from skillforge_client.models import AccessTokenResponse, BodyCreateTokenApiV1AuthTokenPost

from .errors import SkillForgeClientAuthenticationError, SkillForgeResponseError, SkillForgeUnavailable


class ClientCredentialsAuth(httpx.Auth):
    """Acquire and refresh SkillForge access tokens for HTTPX requests."""

    # A request may be replayed once after SkillForge rejects an access token.
    requires_request_body = True
    requires_response_body = True

    def __init__(
        self,
        *,
        client: Client,
        client_id: str,
        client_secret: SecretStr,
    ) -> None:
        self._client = client
        self._client_id = client_id
        self._client_secret = client_secret

        self._access_token: str | None = None
        self._access_token_valid_until = 0.0
        self._token_lock = asyncio.Lock()

    async def async_auth_flow(
        self,
        request: httpx.Request,
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        access_token = await self._get_access_token()
        request.headers["Authorization"] = f"Bearer {access_token}"

        response = yield request
        if response.status_code != HTTPStatus.UNAUTHORIZED:
            return

        access_token = await self._refresh_rejected_access_token(access_token)
        request.headers["Authorization"] = f"Bearer {access_token}"
        yield request

    async def _get_access_token(self) -> str:
        if self._token_is_valid():
            assert self._access_token is not None
            return self._access_token

        async with self._token_lock:
            if not self._token_is_valid():
                await self._refresh_access_token()

        assert self._access_token is not None
        return self._access_token

    async def _refresh_rejected_access_token(self, rejected_access_token: str) -> str:
        async with self._token_lock:
            # Another concurrent request may already have replaced the rejected token.
            if self._access_token == rejected_access_token:
                await self._refresh_access_token()

        assert self._access_token is not None
        return self._access_token

    def _token_is_valid(self) -> bool:
        return self._access_token is not None and monotonic() < self._access_token_valid_until

    async def _refresh_access_token(self) -> None:
        response = await create_token_api_v1_auth_token_post.asyncio_detailed(
            client=self._client,
            body=BodyCreateTokenApiV1AuthTokenPost(
                grant_type="client_credentials",
                client_id=self._client_id,
                client_secret=self._client_secret.get_secret_value(),
            ),
        )

        if response.status_code != HTTPStatus.OK or not isinstance(response.parsed, AccessTokenResponse):
            self._raise_token_error(response.status_code)

        token = response.parsed
        if token.expires_in <= 0:
            raise SkillForgeResponseError("SkillForge returned an already expired access token")

        refresh_margin = min(30.0, token.expires_in * 0.1)
        self._access_token = token.access_token
        self._access_token_valid_until = monotonic() + token.expires_in - refresh_margin

    @staticmethod
    def _raise_token_error(status_code: HTTPStatus) -> Never:
        if status_code in {
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        }:
            raise SkillForgeClientAuthenticationError("SkillForge rejected the client credentials")

        if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise SkillForgeUnavailable("SkillForge could not issue an access token")

        raise SkillForgeResponseError(f"Unexpected SkillForge token response: HTTP {status_code}")
