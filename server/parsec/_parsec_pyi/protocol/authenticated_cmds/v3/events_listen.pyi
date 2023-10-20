# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 2016-present Scille SAS

from __future__ import annotations

from parsec._parsec import InvitationStatus, InvitationToken, RealmRole, VlobID

class APIEvent:
    pass

class APIEventPinged(APIEvent):
    def __init__(self, ping: str) -> None: ...
    @property
    def ping(self) -> str: ...

class APIEventMessageReceived(APIEvent):
    def __init__(self, index: int) -> None: ...
    @property
    def index(self) -> int: ...

class APIEventInviteStatusChanged(APIEvent):
    def __init__(self, token: InvitationToken, invitation_status: InvitationStatus) -> None: ...
    @property
    def token(self) -> InvitationToken: ...
    @property
    def invitation_status(self) -> InvitationStatus: ...

class APIEventRealmMaintenanceStarted(APIEvent):
    def __init__(self, realm_id: VlobID, encryption_revision: int) -> None: ...
    @property
    def realm_id(self) -> VlobID: ...
    @property
    def encryption_revision(self) -> int: ...

class APIEventRealmMaintenanceFinished(APIEvent):
    def __init__(self, realm_id: VlobID, encryption_revision: int) -> None: ...
    @property
    def realm_id(self) -> VlobID: ...
    @property
    def encryption_revision(self) -> int: ...

class APIEventRealmVlobsUpdated(APIEvent):
    def __init__(
        self, realm_id: VlobID, checkpoint: int, src_id: VlobID, src_version: int
    ) -> None: ...
    @property
    def realm_id(self) -> VlobID: ...
    @property
    def checkpoint(self) -> int: ...
    @property
    def src_id(self) -> VlobID: ...
    @property
    def src_version(self) -> int: ...

class APIEventRealmRolesUpdated(APIEvent):
    def __init__(self, realm_id: VlobID, role: RealmRole | None) -> None: ...
    @property
    def realm_id(self) -> VlobID: ...
    @property
    def role(self) -> RealmRole | None: ...

class APIEventPkiEnrollmentUpdated(APIEvent):
    def __init__(
        self,
    ) -> None: ...

class Req:
    def __init__(self, wait: bool) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def wait(self) -> bool: ...

class Rep:
    @staticmethod
    def load(raw: bytes) -> Rep: ...
    def dump(self) -> bytes: ...

class RepUnknownStatus(Rep):
    def __init__(self, status: str, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class RepOk(Rep):
    def __init__(self, unit: APIEvent) -> None: ...
    @property
    def unit(self) -> APIEvent: ...

class RepCancelled(Rep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class RepNoEvents(Rep):
    def __init__(
        self,
    ) -> None: ...
