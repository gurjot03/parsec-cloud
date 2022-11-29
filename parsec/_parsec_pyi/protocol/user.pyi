# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 (eventually AGPL-3.0) 2016-present Scille SAS

from typing import Iterable

from parsec._parsec import UserProfile, UserID, HumanHandle

# Users
class UsersPerProfileDetailItem:
    def __init__(self, profile: UserProfile, active: int, revoked: int) -> None: ...
    @property
    def profile(self) -> UserProfile: ...
    @property
    def active(self) -> int: ...
    @property
    def revoked(self) -> int: ...

class UserGetReq:
    def __init__(self, user_id: UserID) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def user_id(self) -> UserID: ...

class UserGetRep:
    def dump(self) -> bytes: ...
    @classmethod
    def load(cls, buf: bytes) -> UserGetRep: ...

class UserGetRepOk(UserGetRep):
    def __init__(
        self,
        user_certificate: bytes,
        revoked_user_certificate: bytes | None,
        device_certificates: Iterable[bytes],
        trustchain: Trustchain,
    ) -> None: ...
    @property
    def user_certificate(self) -> bytes: ...
    @property
    def revoked_user_certificate(self) -> bytes | None: ...
    @property
    def device_certificates(self) -> tuple[bytes]: ...
    @property
    def trustchain(self) -> Trustchain: ...

class UserGetRepNotFound(UserGetRep): ...

class UserGetRepUnknownStatus(UserGetRep):
    def __init__(self, status: str, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class UserCreateReq:
    def __init__(
        self,
        user_certificate: bytes,
        device_certificate: bytes,
        redacted_user_certificate: bytes,
        redacted_device_certificate: bytes,
    ) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def user_certificate(self) -> bytes: ...
    @property
    def device_certificate(self) -> bytes: ...
    @property
    def redacted_user_certificate(self) -> bytes: ...
    @property
    def redacted_device_certificate(self) -> bytes: ...

class UserCreateRep:
    def dump(self) -> bytes: ...
    @classmethod
    def load(cls, buf: bytes) -> UserCreateRep: ...

class UserCreateRepOk(UserCreateRep): ...

class UserCreateRepNotAllowed(UserCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class UserCreateRepInvalidCertification(UserCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class UserCreateRepInvalidData(UserCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class UserCreateRepAlreadyExists(UserCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class UserCreateRepActiveUsersLimitReached(UserCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class UserCreateRepUnknownStatus(UserCreateRep):
    def __init__(self, status: str, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class UserRevokeReq:
    def __init__(self, revoked_user_certificate: bytes) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def revoked_user_certificate(self) -> bytes: ...

class UserRevokeRep:
    def dump(self) -> bytes: ...
    @classmethod
    def load(cls, buf: bytes) -> UserRevokeRep: ...

class UserRevokeRepOk(UserRevokeRep): ...

class UserRevokeRepNotAllowed(UserRevokeRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class UserRevokeRepInvalidCertification(UserRevokeRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class UserRevokeRepNotFound(UserRevokeRep): ...

class UserRevokeRepAlreadyRevoked(UserRevokeRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class UserRevokeRepUnknownStatus(UserRevokeRep):
    def __init__(self, status: str, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class DeviceCreateReq:
    def __init__(self, device_certificate: bytes, redacted_device_certificate: bytes) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def device_certificate(self) -> bytes: ...
    @property
    def redacted_device_certificate(self) -> bytes: ...

class DeviceCreateRep:
    def dump(self) -> bytes: ...
    @classmethod
    def load(cls, buf: bytes) -> DeviceCreateRep: ...

class DeviceCreateRepOk(DeviceCreateRep): ...

class DeviceCreateRepInvalidCertification(DeviceCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class DeviceCreateRepBadUserId(DeviceCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class DeviceCreateRepInvalidData(DeviceCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class DeviceCreateRepAlreadyExists(DeviceCreateRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class DeviceCreateRepUnknownStatus(DeviceCreateRep):
    def __init__(self, status: str, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class HumanFindReq:
    def __init__(
        self,
        query: str | None,
        omit_revoked: bool,
        omit_non_human: bool,
        page: int,
        per_page: int,
    ) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def query(self) -> str | None: ...
    @property
    def omit_revoked(self) -> bool: ...
    @property
    def omit_non_human(self) -> bool: ...
    @property
    def page(self) -> int: ...
    @property
    def per_page(self) -> int: ...

class HumanFindRep:
    def dump(self) -> bytes: ...
    @classmethod
    def load(cls, buf: bytes) -> HumanFindRep: ...

class HumanFindRepOk(HumanFindRep):
    def __init__(
        self, results: Iterable[HumanFindResultItem], page: int, per_page: int, total: int
    ) -> None: ...
    @property
    def results(self) -> tuple[HumanFindResultItem]: ...
    @property
    def page(self) -> int: ...
    @property
    def per_page(self) -> int: ...
    @property
    def total(self) -> int: ...

class HumanFindRepNotAllowed(HumanFindRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class HumanFindRepUnknownStatus(HumanFindRep):
    def __init__(self, status: str, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class Trustchain:
    def __init__(
        self, devices: Iterable[bytes], users: Iterable[bytes], revoked_users: Iterable[bytes]
    ) -> None: ...
    @property
    def devices(self) -> tuple[bytes]: ...
    @property
    def users(self) -> tuple[bytes]: ...
    @property
    def revoked_users(self) -> tuple[bytes]: ...

class HumanFindResultItem:
    def __init__(
        self, user_id: UserID, human_handle: HumanHandle | None, revoked: bool
    ) -> None: ...
    @property
    def user_id(self) -> UserID: ...
    @property
    def human_handle(self) -> HumanHandle | None: ...
    @property
    def revoked(self) -> bool: ...
