import inspect
from collections.abc import Awaitable, Callable
from functools import wraps

import httpx
from skillforge_client.errors import UnexpectedStatus

from .errors import SkillForgeResponseError, SkillForgeTimeout, SkillForgeUnavailable


def translate_skillforge_errors[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    @wraps(func)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except httpx.TimeoutException as exc:
            raise SkillForgeTimeout("SkillForge did not answer in time") from exc
        except httpx.TransportError as exc:
            raise SkillForgeUnavailable("SkillForge is currently unavailable") from exc
        except UnexpectedStatus as exc:
            raise SkillForgeResponseError(f"SkillForge returned HTTP {exc.status_code}") from exc

    return wrapped


def skillforge_boundary[R](cls: type[R]) -> type[R]:
    for name, attribute in vars(cls).items():
        if name.startswith("_") or name == "close":
            continue

        if inspect.iscoroutinefunction(attribute):
            setattr(cls, name, translate_skillforge_errors(attribute))

    return cls
