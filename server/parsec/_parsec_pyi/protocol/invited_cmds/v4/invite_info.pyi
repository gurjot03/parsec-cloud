# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 2016-present Scille SAS

from __future__ import annotations

from parsec._parsec import HumanHandle, UserID

class UserOrDevice:
    pass

class UserOrDeviceUser(UserOrDevice):
    def __init__(
        self, claimer_email: str, greeter_user_id: UserID, greeter_human_handle: HumanHandle
    ) -> None: ...
    @property
    def claimer_email(self) -> str: ...
    @property
    def greeter_user_id(self) -> UserID: ...
    @property
    def greeter_human_handle(self) -> HumanHandle: ...

class UserOrDeviceDevice(UserOrDevice):
    def __init__(self, greeter_user_id: UserID, greeter_human_handle: HumanHandle) -> None: ...
    @property
    def greeter_user_id(self) -> UserID: ...
    @property
    def greeter_human_handle(self) -> HumanHandle: ...

class Req:
    def __init__(
        self,
    ) -> None: ...
    def dump(self) -> bytes: ...

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
    def __init__(self, unit: UserOrDevice) -> None: ...
    @property
    def unit(self) -> UserOrDevice: ...
