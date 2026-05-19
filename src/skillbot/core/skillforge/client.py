import asyncio
import json
from typing import Any, Protocol
from urllib import error, parse, request
from uuid import UUID

from skillbot.core.models import (
    ActivateStudentRequest,
    ActivateTeacherRequest,
    BotUser,
    CommandEnvChannel,
    CommandEnvKind,
    MemberRole,
    PermissionGrant,
    PermissionGrantEffect,
    PermissionPrincipal,
    PermissionSubject,
    PermissionSubjectType,
    Student,
    Teacher,
)


class SkillforgeError(Exception):
    pass


# region Protocol


class SkillforgeClient(Protocol):
    async def close(self) -> None: ...

    async def get_teacher_by_discord_id(self, discord_id: int) -> Teacher | None: ...

    async def get_student_by_discord_id(self, discord_id: int) -> Student | None: ...

    async def list_teacher_discord_ids(self) -> set[int]: ...

    async def list_student_discord_ids(self) -> set[int]: ...

    async def activate_teacher(self, request: ActivateTeacherRequest) -> Teacher: ...

    async def activate_student(self, request: ActivateStudentRequest) -> Student: ...

    async def get_permission_principal(self, discord_user_id: int) -> PermissionPrincipal | None: ...

    async def list_permission_grants(self, subjects: tuple[PermissionSubject, ...]) -> list[PermissionGrant]: ...

    async def get_command_env_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind,
    ) -> CommandEnvChannel | None: ...

    async def get_owner_command_env_channel_id(
        self,
        *,
        guild_id: int,
        owner_user_id: int,
        kind: CommandEnvKind,
    ) -> int | None: ...

    async def upsert_command_env_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind,
        owner_user_id: int | None,
    ) -> None: ...

    async def get_user_id_by_discord_id(self, discord_id: int) -> int | None: ...


# region NotConfiguredClient


class SkillforgeClientNotConfigured(SkillforgeClient):
    async def close(self) -> None:
        return None

    def _raise(self) -> None:
        raise SkillforgeError("Skillforge client is not configured.")

    async def get_teacher_by_discord_id(self, discord_id: int) -> Teacher | None:
        del discord_id
        self._raise()

    async def get_student_by_discord_id(self, discord_id: int) -> Student | None:
        del discord_id
        self._raise()

    async def list_teacher_discord_ids(self) -> set[int]:  # type: ignore
        self._raise()

    async def list_student_discord_ids(self) -> set[int]:  # type: ignore
        self._raise()

    async def activate_teacher(self, request: ActivateTeacherRequest) -> Teacher:  # type: ignore
        del request
        self._raise()

    async def activate_student(self, request: ActivateStudentRequest) -> Student:  # type: ignore
        del request
        self._raise()

    async def get_permission_principal(self, discord_user_id: int) -> PermissionPrincipal | None:
        del discord_user_id
        self._raise()

    async def list_permission_grants(self, subjects: tuple[PermissionSubject, ...]) -> list[PermissionGrant]:  # type: ignore
        del subjects
        self._raise()

    async def get_command_env_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind,
    ) -> CommandEnvChannel | None:
        del guild_id, channel_id, kind
        self._raise()

    async def get_owner_command_env_channel_id(
        self,
        *,
        guild_id: int,
        owner_user_id: int,
        kind: CommandEnvKind,
    ) -> int | None:
        del guild_id, owner_user_id, kind
        self._raise()

    async def upsert_command_env_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind,
        owner_user_id: int | None,
    ) -> None:
        del guild_id, channel_id, kind, owner_user_id
        self._raise()

    async def get_user_id_by_discord_id(self, discord_id: int) -> int | None:
        del discord_id
        self._raise()


# region HttpClient


class HttpSkillforgeClient(SkillforgeClient):
    """Small HTTP boundary for the future Skillforge API.

    The concrete route names are intentionally isolated here. Bot services call
    methods on ``SkillforgeClient`` and stay unaware of HTTP, JSON and DB shape.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_seconds = timeout_seconds

    async def close(self) -> None:
        return None

    async def get_teacher_by_discord_id(self, discord_id: int) -> Teacher | None:
        payload = await self._get_json_or_none(f"/bot/teachers/by-discord/{discord_id}")
        return _teacher(payload) if payload is not None else None

    async def get_student_by_discord_id(self, discord_id: int) -> Student | None:
        payload = await self._get_json_or_none(f"/bot/students/by-discord/{discord_id}")
        return _student(payload) if payload is not None else None

    async def list_teacher_discord_ids(self) -> set[int]:
        payload = await self._request_json("GET", "/bot/teachers/discord-ids")
        return {int(value) for value in payload.get("discord_ids", [])}

    async def list_student_discord_ids(self) -> set[int]:
        payload = await self._request_json("GET", "/bot/students/discord-ids")
        return {int(value) for value in payload.get("discord_ids", [])}

    async def activate_teacher(self, request: ActivateTeacherRequest) -> Teacher:
        payload = await self._request_json(
            "POST",
            "/bot/teachers/activate",
            body={
                "discord_id": request.discord_id,
                "full_name": request.full_name,
                "teaching_category_id": request.teaching_category_id,
                "command_channel_id": request.command_channel_id,
            },
        )
        return _teacher(payload)

    async def activate_student(self, request: ActivateStudentRequest) -> Student:
        payload = await self._request_json(
            "POST",
            "/bot/students/activate",
            body={
                "teacher_discord_id": request.teacher_discord_id,
                "student_discord_id": request.student_discord_id,
                "full_name": request.full_name,
                "customer_id": request.customer_id,
            },
        )
        return _student(payload)

    async def get_permission_principal(self, discord_user_id: int) -> PermissionPrincipal | None:
        payload = await self._get_json_or_none(f"/bot/permissions/principals/{discord_user_id}")
        return _principal(discord_user_id, payload) if payload is not None else None

    async def list_permission_grants(self, subjects: tuple[PermissionSubject, ...]) -> list[PermissionGrant]:
        payload = await self._request_json(
            "POST",
            "/bot/permissions/grants/query",
            body={
                "subjects": [
                    {
                        "type": subject.type.value,
                        "key": subject.key,
                    }
                    for subject in subjects
                ]
            },
        )
        return [_permission_grant(row) for row in payload.get("grants", [])]

    async def get_command_env_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind,
    ) -> CommandEnvChannel | None:
        query = parse.urlencode({"kind": kind.value})
        payload = await self._get_json_or_none(f"/bot/command-env/channels/{guild_id}/{channel_id}?{query}")
        return _command_env_channel(payload) if payload is not None else None

    async def get_owner_command_env_channel_id(
        self,
        *,
        guild_id: int,
        owner_user_id: int,
        kind: CommandEnvKind,
    ) -> int | None:
        query = parse.urlencode({"kind": kind.value})
        payload = await self._get_json_or_none(f"/bot/command-env/owners/{guild_id}/{owner_user_id}?{query}")
        if payload is None:
            return None
        channel_id = payload.get("channel_id")
        return int(channel_id) if channel_id is not None else None

    async def upsert_command_env_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind,
        owner_user_id: int | None,
    ) -> None:
        await self._request_json(
            "PUT",
            "/bot/command-env/channels",
            body={
                "guild_id": guild_id,
                "channel_id": channel_id,
                "kind": kind.value,
                "owner_user_id": owner_user_id,
            },
        )

    async def get_user_id_by_discord_id(self, discord_id: int) -> int | None:
        payload = await self._get_json_or_none(f"/bot/users/by-discord/{discord_id}")
        if payload is None:
            return None
        user_id = payload.get("id")
        return int(user_id) if user_id is not None else None

    async def _get_json_or_none(self, path: str) -> dict[str, Any] | None:
        try:
            return await self._request_json("GET", path)
        except SkillforgeNotFound:
            return None

    async def _request_json(self, method: str, path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        req = request.Request(url, data=data, headers=headers, method=method)
        return await asyncio.to_thread(self._send, req)

    def _send(self, req: request.Request) -> dict[str, Any]:
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                raw = response.read()
        except error.HTTPError as exc:
            if exc.code == 404:
                raise SkillforgeNotFound(str(req.full_url)) from exc
            raise SkillforgeError(f"Skillforge request failed with HTTP {exc.code}: {req.full_url}") from exc
        except error.URLError as exc:
            raise SkillforgeError(f"Skillforge request failed: {exc.reason}") from exc

        if not raw:
            return {}
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise SkillforgeError("Skillforge response must be a JSON object.")
        return decoded


class SkillforgeNotFound(SkillforgeError):
    pass


# region Payload Mappers


def _bot_user(payload: dict[str, Any]) -> BotUser:
    return BotUser(
        id=int(payload["id"]),
        discord_id=int(payload["discord_id"]),
        full_name=str(payload["full_name"]),
        role=MemberRole(str(payload["role"])),
    )


def _teacher(payload: dict[str, Any]) -> Teacher:
    return Teacher(
        user_id=int(payload["user_id"]),
        discord_id=int(payload["discord_id"]),
        full_name=str(payload["full_name"]),
        teaching_category_id=_optional_int(payload.get("teaching_category_id")),
        command_channel_id=_optional_int(payload.get("command_channel_id")),
    )


def _student(payload: dict[str, Any]) -> Student:
    return Student(
        user_id=int(payload["user_id"]),
        discord_id=int(payload["discord_id"]),
        full_name=str(payload["full_name"]),
        party_id=UUID(str(payload["party_id"])),
        teacher_user_id=_optional_int(payload.get("teacher_user_id")),
        channel_id=_optional_int(payload.get("channel_id")),
    )


def _principal(discord_user_id: int, payload: dict[str, Any]) -> PermissionPrincipal:
    user_payload = payload.get("user")
    groups = payload.get("group_keys", ())
    return PermissionPrincipal(
        discord_user_id=discord_user_id,
        user=_bot_user(user_payload) if isinstance(user_payload, dict) else None,
        group_keys=tuple(str(key) for key in groups),
    )


def _permission_grant(payload: dict[str, Any]) -> PermissionGrant:
    return PermissionGrant(
        subject_type=PermissionSubjectType(str(payload["subject_type"])),
        subject_key=str(payload["subject_key"]),
        action_key=str(payload["action_key"]),
        effect=PermissionGrantEffect(str(payload["effect"])),
        priority=int(payload.get("priority", 0)),
    )


def _command_env_channel(payload: dict[str, Any]) -> CommandEnvChannel:
    return CommandEnvChannel(
        guild_id=int(payload["guild_id"]),
        channel_id=int(payload["channel_id"]),
        kind=CommandEnvKind(str(payload["kind"])),
        owner_user_id=_optional_int(payload.get("owner_user_id")),
        active=bool(payload.get("active", True)),
    )


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None  # type: ignore
