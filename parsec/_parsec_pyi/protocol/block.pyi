# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 (eventually AGPL-3.0) 2016-present Scille SAS
from parsec._parsec import BlockID, RealmID

# Block
class BlockCreateReq:
    def __init__(self, block_id: BlockID, realm_id: RealmID, block: bytes) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def block_id(self) -> BlockID: ...
    @property
    def realm_id(self) -> RealmID: ...
    @property
    def block(self) -> bytes: ...

class BlockCreateRep:
    def dump(self) -> bytes: ...
    @classmethod
    def load(cls, buf: bytes) -> BlockCreateRep: ...

class BlockCreateRepOk(BlockCreateRep): ...
class BlockCreateRepAlreadyExists(BlockCreateRep): ...
class BlockCreateRepNotFound(BlockCreateRep): ...
class BlockCreateRepTimeout(BlockCreateRep): ...
class BlockCreateRepNotAllowed(BlockCreateRep): ...
class BlockCreateRepInMaintenance(BlockCreateRep): ...

class BlockCreateRepUnknownStatus(BlockCreateRep):
    def __init__(self, status: str, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class BlockReadReq:
    def __init__(self, block_id: BlockID) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def block_id(self) -> BlockID: ...

class BlockReadRep:
    def dump(self) -> bytes: ...
    @classmethod
    def load(cls, buf: bytes) -> BlockReadRep: ...

class BlockReadRepOk(BlockReadRep):
    def __init__(self, block: bytes) -> None: ...
    @property
    def block(self) -> bytes: ...

class BlockReadRepNotFound(BlockReadRep): ...
class BlockReadRepTimeout(BlockReadRep): ...
class BlockReadRepNotAllowed(BlockReadRep): ...
class BlockReadRepInMaintenance(BlockReadRep): ...

class BlockReadRepUnknownStatus(BlockReadRep):
    def __init__(self, status: str, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...