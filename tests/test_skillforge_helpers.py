from http import HTTPStatus
from typing import Any

import pytest
from skillforge_client.types import Response

from skillbot.core.skillforge.errors import (
    SkillForgeClientAuthenticationError,
    SkillForgeResponseError,
    SkillForgeUnavailable,
)
from skillbot.core.skillforge.helpers import require_no_content, require_response


class _Payload:
    pass


def _response(status: HTTPStatus, parsed: Any = None) -> Response[Any]:
    return Response(
        status_code=status,
        content=b"",
        headers={},
        parsed=parsed,
    )


def test_require_response_returns_expected_model() -> None:
    payload = _Payload()

    result = require_response(
        _response(HTTPStatus.OK, payload),
        status=HTTPStatus.OK,
        model=_Payload,
    )

    assert result is payload


def test_require_response_rejects_wrong_success_status() -> None:
    with pytest.raises(SkillForgeResponseError, match="Expected SkillForge HTTP 201"):
        require_response(
            _response(HTTPStatus.OK, _Payload()),
            status=HTTPStatus.CREATED,
            model=_Payload,
        )


def test_require_response_rejects_wrong_payload_model() -> None:
    with pytest.raises(SkillForgeResponseError, match="Expected SkillForge response model _Payload"):
        require_response(
            _response(HTTPStatus.OK, object()),
            status=HTTPStatus.OK,
            model=_Payload,
        )


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (HTTPStatus.UNAUTHORIZED, SkillForgeClientAuthenticationError),
        (HTTPStatus.FORBIDDEN, SkillForgeResponseError),
        (HTTPStatus.INTERNAL_SERVER_ERROR, SkillForgeUnavailable),
        (HTTPStatus.SERVICE_UNAVAILABLE, SkillForgeUnavailable),
    ],
)
def test_require_response_translates_common_errors(
    status: HTTPStatus,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        require_response(
            _response(status),
            status=HTTPStatus.OK,
            model=_Payload,
        )


def test_require_no_content_accepts_empty_response() -> None:
    assert require_no_content(_response(HTTPStatus.NO_CONTENT)) is None


def test_require_no_content_rejects_payload() -> None:
    with pytest.raises(SkillForgeResponseError, match="Expected an empty SkillForge response"):
        require_no_content(_response(HTTPStatus.NO_CONTENT, _Payload()))
