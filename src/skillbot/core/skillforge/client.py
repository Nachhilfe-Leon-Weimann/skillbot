from httpx import Timeout
from skillforge_client import AuthenticatedClient
from skillforge_client.api.system import liveness_check_health_live_get
from skillforge_client.models import HealthCheckResponse

from skillbot.core.config import SkillForgeSettings

from .helpers import skillforge_boundary


@skillforge_boundary
class SkillForgeClient:
    def __init__(self, settings: SkillForgeSettings) -> None:
        self.settings = settings

        self.client = AuthenticatedClient(
            base_url=settings.base_url,
            token=settings.client_token.get_secret_value(),
            timeout=Timeout(settings.timeout_seconds),
        )

    async def close(self) -> None:
        await self.client.get_async_httpx_client().aclose()

    async def liveness_check(self) -> HealthCheckResponse | None:
        return await liveness_check_health_live_get.asyncio(client=self.client)
