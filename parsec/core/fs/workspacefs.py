# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

import inspect
from typing import Tuple, Union, Iterator
from uuid import UUID

from parsec.core.local_storage import LocalStorageMissingEntry
from parsec.core.types import FsPath, AccessID, FileDescriptor
from parsec.core.fs.file_transactions import FileTransactions
from parsec.core.fs.entry_transactions import EntryTransactions
from parsec.core.fs.local_folder_fs import FSManifestLocalMiss, FSMultiManifestLocalMiss

# from parsec.core.fs.exceptions import FSBackendOfflineError, FSError
# from parsec.core.backend_connection import BackendNotAvailable, BackendConnectionError

AnyPath = Union[FsPath, str]


class WorkspaceFS:
    def __init__(
        self,
        workspace_entry,
        device,
        local_storage,
        backend_cmds,
        event_bus,
        _local_folder_fs,
        _remote_loader,
        _syncer,
    ):
        self.workspace_entry = workspace_entry
        self.device = device
        self.local_storage = local_storage
        self.backend_cmds = backend_cmds
        self.event_bus = event_bus
        self._local_folder_fs = _local_folder_fs
        self._remote_loader = _remote_loader
        self._syncer = _syncer

        self.file_transactions = FileTransactions(local_storage, self._remote_loader, event_bus)
        self.entry_transactions = EntryTransactions(
            self.device, workspace_entry, local_storage, self._remote_loader, event_bus
        )

    @property
    def workspace_name(self):
        return self.workspace_entry.name

    # Information

    async def workspace_info(self):
        # try:
        #     user_roles = await self.backend_cmds.vlob_group_get_roles(
        #         self.workspace_entry.access.id
        #     )

        # except BackendNotAvailable as exc:
        #     raise FSBackendOfflineError(str(exc)) from exc

        # except BackendConnectionError as exc:
        #     raise FSError(f"Cannot retreive workspace's vlob group rights: {exc}") from exc

        # TODO: finish me !
        try:
            manifest = self.local_storage.get_manifest(self.workspace_entry.access)
        except LocalStorageMissingEntry as exc:
            manifest = await self._remote_loader.load_manifest(exc.access)
        return {
            "role": self.workspace_entry.role,
            "creator": manifest.creator,
            "participants": list(manifest.participants),
        }

    async def path_info(self, path: AnyPath) -> dict:
        return await self.entry_transactions.entry_info(FsPath(path))

    # Legacy methods - to remove after the FS class has been completely removed

    async def entry_rename(self, src: FsPath, dst: FsPath, overwrite: bool = True) -> AccessID:
        return await self.entry_transactions.entry_rename(src, dst, overwrite)

    async def folder_create(self, path: FsPath) -> AccessID:
        return await self.entry_transactions.folder_create(path)

    async def folder_delete(self, path: FsPath) -> AccessID:
        return await self.entry_transactions.folder_delete(path)

    async def file_create(self, path: FsPath, open: bool = True) -> Tuple[AccessID, FileDescriptor]:
        return await self.entry_transactions.file_create(path, open=open)

    async def file_open(self, path: FsPath, mode="rw") -> Tuple[AccessID, FileDescriptor]:
        return await self.entry_transactions.file_open(path, mode=mode)

    async def file_delete(self, path: FsPath) -> AccessID:
        return await self.entry_transactions.file_delete(path)

    async def fd_close(self, fd: int) -> None:
        await self.file_transactions.fd_close(fd)

    async def fd_seek(self, fd: int, offset: int) -> None:
        await self.file_transactions.fd_seek(fd, offset)

    async def fd_resize(self, fd: int, length: int) -> None:
        await self.file_transactions.fd_resize(fd, length)

    async def fd_write(self, fd: int, content: bytes, offset: int = None) -> int:
        return await self.file_transactions.fd_write(fd, content, offset)

    async def fd_flush(self, fd: int) -> None:
        await self.file_transactions.fd_flush(fd)

    async def fd_read(self, fd: int, size: int = -1, offset: int = None) -> bytes:
        return await self.file_transactions.fd_read(fd, size, offset)

    async def file_write(self, path: FsPath, content: bytes, offset: int = 0) -> int:
        _, fd = await self.file_open(path, "rw")
        try:
            if offset:
                await self.fd_seek(fd, offset)
            return await self.fd_write(fd, content)
        finally:
            await self.fd_close(fd)

    async def file_resize(self, path: FsPath, length: int) -> None:
        _, fd = await self.file_open(path, "w")
        try:
            await self.fd_resize(fd, length)
        finally:
            await self.fd_close(fd)

    async def file_read(self, path: FsPath, size: int = -1, offset: int = 0) -> bytes:
        _, fd = await self.file_open(path, "r")
        try:
            if offset:
                await self.fd_seek(fd, offset)
            return await self.fd_read(fd, size)
        finally:
            await self.fd_close(fd)

    # Pathlib-like interface

    async def is_dir(self, path: AnyPath) -> bool:
        path = FsPath(path)
        info = await self.entry_transactions.entry_info(path)
        return info["type"] == "folder"

    async def is_file(self, path: AnyPath) -> bool:
        path = FsPath(path)
        info = await self.entry_transactions.entry_info(FsPath(path))
        return info["type"] == "file"

    async def iterdir(self, path: AnyPath) -> Iterator[FsPath]:
        path = FsPath(path)
        info = await self.entry_transactions.entry_info(path)
        for child in info["children"]:
            yield path / child

    async def rename(self, source: AnyPath, destination: AnyPath, overwrite: bool = True) -> None:
        source = FsPath(source)
        destination = FsPath(destination)
        await self.entry_transactions.entry_rename(source, destination, overwrite=overwrite)

    async def mkdir(self, path: AnyPath, parents: bool = False, exist_ok: bool = False) -> None:
        path = FsPath(path)
        try:
            await self.entry_transactions.folder_create(path)
        except FileNotFoundError:
            if not parents or path.parent == path:
                raise
            await self.mkdir(path.parent, parents=True, exist_ok=True)
            await self.mkdir(path, parents=False, exist_ok=exist_ok)
        except FileExistsError:
            if not exist_ok or not await self.is_dir(path):
                raise

    async def rmdir(self, path: AnyPath) -> None:
        path = FsPath(path)
        await self.entry_transactions.folder_delete(path)

    async def touch(self, path: AnyPath, exist_ok: bool = True) -> None:
        path = FsPath(path)
        try:
            await self.entry_transactions.file_create(path, open=False)
        except FileExistsError:
            if not exist_ok or not await self.is_file(path):
                raise

    async def unlink(self, path: AnyPath) -> None:
        path = FsPath(path)
        await self.entry_transactions.file_delete(path)

    async def truncate(self, path: AnyPath, length: int) -> None:
        path = FsPath(path)
        _, fd = await self.entry_transactions.file_open(path, "w")
        try:
            return await self.file_transactions.fd_resize(fd, length)
        finally:
            await self.file_transactions.fd_close(fd)

    async def read_bytes(self, path: AnyPath, size: int = -1, offset: int = 0) -> bytes:
        path = FsPath(path)
        _, fd = await self.entry_transactions.file_open(path, "r")
        try:
            return await self.file_transactions.fd_read(fd, size, offset)
        finally:
            await self.file_transactions.fd_close(fd)

    async def write_bytes(self, path: AnyPath, data: bytes, offset: int = 0) -> int:
        path = FsPath(path)
        _, fd = await self.entry_transactions.file_open(path, "w")
        try:
            return await self.file_transactions.fd_write(fd, data, offset)
        finally:
            await self.file_transactions.fd_close(fd)

    # Shutil-like interface

    def move(self, source: AnyPath, destination: AnyPath):
        source = FsPath(source)
        destination = FsPath(destination)
        raise NotImplementedError

    def rmtree(self, path: AnyPath):
        path = FsPath(path)
        raise NotImplementedError

    # Left to migrate

    def _cook_path(self, relative_path=""):
        return FsPath(f"/{self.workspace_name}/{relative_path}")

    async def _load_and_retry(self, fn, *args, **kwargs):
        while True:
            try:
                if inspect.iscoroutinefunction(fn):
                    return await fn(*args, **kwargs)
                else:
                    return fn(*args, **kwargs)

            except FSManifestLocalMiss as exc:
                await self._remote_loader.load_manifest(exc.access)

            except FSMultiManifestLocalMiss as exc:
                for access in exc.accesses:
                    await self._remote_loader.load_manifest(access)

    async def sync(self, path: FsPath, recursive: bool = True) -> None:
        path = self._cook_path(path)
        await self._load_and_retry(self._syncer.sync, path, recursive=recursive)

    # TODO: do we really need this ? or should we provide id manipulation at this level ?
    async def sync_by_id(self, entry_id: AccessID) -> None:
        assert isinstance(entry_id, UUID)
        await self._load_and_retry(self._syncer.sync_by_id, entry_id)

    async def get_entry_path(self, id: AccessID) -> FsPath:
        assert isinstance(id, UUID)
        path, _, _ = await self._load_and_retry(self._local_folder_fs.get_entry_path, id)
        return path
