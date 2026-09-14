import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from http import HTTPStatus
from typing import Any

import httpx
from skillforge_client.errors import UnexpectedStatus
from skillforge_client.types import Response

from .errors import (
    SkillForgeClientAuthenticationError,
    SkillForgeResponseError,
    SkillForgeTimeout,
    SkillForgeUnavailable,
)


def require_response[T](
    response: Response[Any],
    *,
    status: HTTPStatus,
    model: type[T],
) -> T:
    """Return a successful parsed response or raise a SkillForge error."""

    _raise_common_response_error(response)

    if response.status_code != status:
        raise SkillForgeResponseError(
            f"Expected SkillForge HTTP {status.value}, received HTTP {response.status_code.value}"
        )

    if not isinstance(response.parsed, model):
        raise SkillForgeResponseError(f"Expected SkillForge response model {model.__name__}")

    return response.parsed


def require_no_content(
    response: Response[Any],
    *,
    status: HTTPStatus = HTTPStatus.NO_CONTENT,
) -> None:
    """Validate a successful SkillForge response without a payload."""

    _raise_common_response_error(response)

    if response.status_code != status:
        raise SkillForgeResponseError(
            f"Expected SkillForge HTTP {status.value}, received HTTP {response.status_code.value}"
        )

    if response.parsed is not None:
        raise SkillForgeResponseError("Expected an empty SkillForge response")


def _raise_common_response_error(response: Response[Any]) -> None:
    if response.status_code == HTTPStatus.UNAUTHORIZED:
        raise SkillForgeClientAuthenticationError("SkillForge rejected the access token")

    if response.status_code == HTTPStatus.FORBIDDEN:
        raise SkillForgeResponseError("SkillForge rejected the client scope")

    if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        raise SkillForgeUnavailable(f"SkillForge returned HTTP {response.status_code.value}")


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
