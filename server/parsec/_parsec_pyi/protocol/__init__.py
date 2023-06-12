# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPL-3.0 2016-present Scille SAS

from __future__ import annotations

from parsec._parsec import VlobID

from . import anonymous_cmds, authenticated_cmds, invited_cmds


class ProtocolErrorFields:
    @classmethod
    def NotHandled(cls) -> ProtocolErrorFields:
        ...

    @classmethod
    def BadRequest(cls, exc: str) -> ProtocolErrorFields:
        ...

    @property
    def exc(self) -> ProtocolErrorFields:
        ...


class ProtocolError(BaseException, ProtocolErrorFields):
    ...


class ReencryptionBatchEntry:
    def __init__(self, vlob_id: VlobID, version: int, blob: bytes) -> None:
        ...

    @property
    def vlob_id(self) -> VlobID:
        ...

    @property
    def version(self) -> int:
        ...

    @property
    def blob(self) -> bytes:
        ...


class ActiveUsersLimit:
    NO_LIMIT: ActiveUsersLimit

    @classmethod
    def FromOptionalInt(cls, count: int | None) -> ActiveUsersLimit:
        ...

    @classmethod
    def LimitedTo(cls, user_count_limit: int) -> ActiveUsersLimit:
        ...

    def to_int(self) -> int | None:
        ...

    "Returns the user limit count as an integer or None if there's no limit specified"

    def __eq__(self, other: object) -> bool:
        ...

    def __ge__(self, other: object) -> bool:
        ...

    def __gt__(self, other: object) -> bool:
        ...

    def __le__(self, other: object) -> bool:
        ...

    def __lt__(self, other: object) -> bool:
        ...

    def __ne__(self, other: object) -> bool:
        ...


__all__ = [
    "ReencryptionBatchEntry",
    "ActiveUsersLimit",
    "anonymous_cmds",
    "invited_cmds",
    "authenticated_cmds",
]