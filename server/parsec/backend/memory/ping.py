# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 2016-present Scille SAS
from __future__ import annotations

from typing import Any, Callable, Coroutine

from parsec._parsec import BackendEventPinged, DeviceID, OrganizationID
from parsec.backend.ping import BasePingComponent


class MemoryPingComponent(BasePingComponent):
    def __init__(self, send_event: Callable[..., Coroutine[Any, Any, None]]) -> None:
        self._send_event = send_event

    def register_components(self, **other_components: Any) -> None:
        pass

    async def ping(
        self, organization_id: OrganizationID, author: DeviceID | None, ping: str
    ) -> None:
        if author:
            await self._send_event(
                BackendEventPinged(organization_id=organization_id, author=author, ping=ping)
            )

    def test_duplicate_organization(self, id: OrganizationID, new_id: OrganizationID) -> None:
        pass

    def test_drop_organization(self, id: OrganizationID) -> None:
        pass
