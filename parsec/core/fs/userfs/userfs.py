# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

import trio
from pathlib import Path
from contextlib import ExitStack
from pendulum import Pendulum, now as pendulum_now
from typing import List, Tuple, Optional, Union
from structlog import get_logger

from parsec.event_bus import EventBus
from parsec.crypto import SecretKey
from parsec.api.data import (
    DataError,
    RealmRoleCertificateContent,
    MessageContent,
    SharingGrantedMessageContent,
    SharingReencryptedMessageContent,
    SharingRevokedMessageContent,
    PingMessageContent,
    UserManifest,
)
from parsec.api.protocol import UserID, DeviceID, MaintenanceType
from parsec.core.types import (
    EntryID,
    LocalDevice,
    LocalWorkspaceManifest,
    WorkspaceEntry,
    WorkspaceRole,
    LocalUserManifest,
)
from parsec.core.fs.local_storage import LocalStorage
from parsec.core.backend_connection import (
    BackendCmdsPool,
    BackendNotAvailable,
    BackendCmdsBadResponse,
    BackendCmdsNotAllowed,
    BackendCmdsAlreadyExists,
    BackendCmdsRoleAlreadyGranted,
    BackendCmdsBadVersion,
    BackendCmdsInMaintenance,
    BackendCmdsParticipantsMismatchError,
    BackendConnectionError,
)
from parsec.core.remote_devices_manager import (
    RemoteDevicesManager,
    RemoteDevicesManagerError,
    RemoteDevicesManagerBackendOfflineError,
)

from parsec.core.fs.workspacefs import WorkspaceFS
from parsec.core.fs.remote_loader import RemoteLoader
from parsec.core.fs.realm_storage import UserStorage
from parsec.core.fs.userfs.merging import merge_local_user_manifests, merge_workspace_entry
from parsec.core.fs.exceptions import (
    FSError,
    FSWorkspaceNoAccess,
    FSWorkspaceNotFoundError,
    FSBackendOfflineError,
    FSSharingNotAllowedError,
    FSWorkspaceInMaintenance,
    FSWorkspaceNotInMaintenance,
)


logger = get_logger()


class ReencryptionJob:
    def __init__(self, backend_cmds, new_workspace_entry, old_workspace_entry):
        self.backend_cmds = backend_cmds
        self.new_workspace_entry = new_workspace_entry
        self.old_workspace_entry = old_workspace_entry
        assert new_workspace_entry.id == old_workspace_entry.id

    async def do_one_batch(self, size=100) -> Tuple[int, int]:
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSWorkspaceInMaintenance
            FSWorkspaceNoAccess
        """
        workspace_id = self.new_workspace_entry.id
        new_encryption_revision = self.new_workspace_entry.encryption_revision

        # Get the batch
        try:
            batch = await self.backend_cmds.vlob_maintenance_get_reencryption_batch(
                workspace_id, new_encryption_revision, size
            )

            donebatch = []
            for vlob_id, version, blob in batch:
                cleartext = self.old_workspace_entry.key.decrypt(blob)
                newciphered = self.new_workspace_entry.key.encrypt(cleartext)
                donebatch.append((vlob_id, version, newciphered))

            total, done = await self.backend_cmds.vlob_maintenance_save_reencryption_batch(
                workspace_id, new_encryption_revision, donebatch
            )

            if total == done:
                # Finish the maintenance
                await self.backend_cmds.realm_finish_reencryption_maintenance(
                    workspace_id, new_encryption_revision
                )

        except BackendNotAvailable as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except BackendConnectionError as exc:
            if exc.status in ("not_in_maintenance", "bad_encryption_revision"):
                raise FSWorkspaceNotInMaintenance("Reencryption job already finished") from exc

            if exc.status == "not_allowed":
                raise FSWorkspaceNoAccess(
                    f"Not allowed to do reencryption maintenance on workspace {workspace_id}: {exc}"
                ) from exc

            raise FSError(
                f"Cannot do reencryption maintenance on workspace {workspace_id}: {exc}"
            ) from exc

        return total, done


class UserFS:
    def __init__(
        self,
        device: LocalDevice,
        path: Path,
        backend_cmds: BackendCmdsPool,
        remote_devices_manager: RemoteDevicesManager,
        event_bus: EventBus,
    ):
        self.device = device
        self.path = path
        self.backend_cmds = backend_cmds
        self.remote_devices_manager = remote_devices_manager
        self.event_bus = event_bus

        self.storage = None

        # Message processing is done in-order, hence it is pointless to do
        # it concurrently
        self._exit_stack = ExitStack()
        self._process_messages_lock = trio.Lock()
        self._update_user_manifest_lock = trio.Lock()
        self._workspace_storages = {}

        now = pendulum_now()
        wentry = WorkspaceEntry(
            name="<user manifest>",
            id=device.user_manifest_id,
            key=device.user_manifest_key,
            encryption_revision=1,
            encrypted_on=now,
            role_cached_on=now,
            role=WorkspaceRole.OWNER,
        )
        self.remote_loader = RemoteLoader(
            self.device,
            self.device.user_manifest_id,
            lambda: wentry,
            self.backend_cmds,
            self.remote_devices_manager,
            # Hack, but fine as long as we only call `load_realm_current_roles`
            None,
        )

    def __enter__(self):
        self.storage = self._exit_stack.enter_context(
            UserStorage.factory(self.device, self.path, self.user_manifest_id)
        )
        return self

    def __exit__(self, *args):
        self._exit_stack.close()

    @property
    def user_manifest_id(self) -> EntryID:
        return self.device.user_manifest_id

    def get_user_manifest(self) -> LocalUserManifest:
        return self.storage.get_user_manifest()

    def set_user_manifest(self, manifest: LocalUserManifest) -> None:
        self.storage.set_user_manifest(manifest)

    def _instantiate_workspace_local_storage(self, workspace_id: EntryID) -> LocalStorage:
        path = self.path / str(workspace_id)
        local_storage = LocalStorage(self.device.device_id, self.device.local_symkey, path)
        self._exit_stack.enter_context(local_storage)
        return local_storage

    def _instantiate_workspace(self, workspace_id: EntryID) -> WorkspaceFS:
        # Workspace entry can change at any time, so we provide a way for
        # WorskpaeFS to load it each time it is needed
        def get_workspace_entry():
            user_manifest = self.get_user_manifest()
            workspace_entry = user_manifest.get_workspace_entry(workspace_id)
            if not workspace_entry:
                raise FSWorkspaceNotFoundError(f"Unknown workspace `{workspace_id}`")
            return workspace_entry

        # Instantiate the local storage
        local_storage = self._instantiate_workspace_local_storage(workspace_id)

        # Instantiate the workspace
        return WorkspaceFS(
            workspace_id=workspace_id,
            get_workspace_entry=get_workspace_entry,
            device=self.device,
            local_storage=local_storage,
            backend_cmds=self.backend_cmds,
            event_bus=self.event_bus,
            remote_device_manager=self.remote_devices_manager,
        )

    async def _create_workspace(
        self, workspace_id: EntryID, manifest: LocalWorkspaceManifest
    ) -> None:
        """
        Raises: Nothing
        """
        workspace = self._instantiate_workspace(workspace_id)

        async with workspace.local_storage.lock_entry_id(workspace_id):
            workspace.local_storage.set_manifest(workspace_id, manifest)

        self._workspace_storages.setdefault(workspace_id, workspace)

    def get_workspace(self, workspace_id: EntryID) -> WorkspaceFS:
        """
        Raises:
            FSWorkspaceNotFoundError
        """
        # The workspace has already been instantiated
        if workspace_id in self._workspace_storages:
            return self._workspace_storages[workspace_id]

        # Instantiate the workpace
        workspace = self._instantiate_workspace(workspace_id)

        # Sanity check to make sure workspace_id is valid
        workspace.get_workspace_entry()

        # Set and return
        return self._workspace_storages.setdefault(workspace_id, workspace)

    async def workspace_create(self, name: str) -> EntryID:
        """
        Raises: Nothing !
        """
        workspace_entry = WorkspaceEntry.new(name)
        workspace_manifest = LocalWorkspaceManifest.new_placeholder(id=workspace_entry.id)
        async with self._update_user_manifest_lock:
            user_manifest = self.get_user_manifest()
            user_manifest = user_manifest.evolve_workspaces_and_mark_updated(workspace_entry)
            await self._create_workspace(workspace_entry.id, workspace_manifest)
            self.set_user_manifest(user_manifest)
            self.event_bus.send("fs.entry.updated", id=self.user_manifest_id)
            self.event_bus.send("fs.workspace.created", new_entry=workspace_entry)

        return workspace_entry.id

    async def workspace_rename(self, workspace_id: EntryID, new_name: str) -> None:
        """
        Raises:
            FSWorkspaceNotFoundError
        """
        async with self._update_user_manifest_lock:
            user_manifest = self.get_user_manifest()
            workspace_entry = user_manifest.get_workspace_entry(workspace_id)
            if not workspace_entry:
                raise FSWorkspaceNotFoundError(f"Unknown workspace `{workspace_id}`")

            updated_workspace_entry = workspace_entry.evolve(name=new_name)
            updated_user_manifest = user_manifest.evolve_workspaces_and_mark_updated(
                updated_workspace_entry
            )
            self.set_user_manifest(updated_user_manifest)
            self.event_bus.send("fs.entry.updated", id=self.user_manifest_id)

    async def _fetch_remote_user_manifest(self, version: int = None) -> UserManifest:
        """
        Raises:
            FSError
            FSWorkspaceInMaintenance
            FSBackendOfflineError
        """
        try:
            # Note encryption_revision is always 1 given we never reencrypt
            # the user manifest's realm
            args = await self.backend_cmds.vlob_read(1, self.user_manifest_id, version)
            expected_author, expected_timestamp, expected_version, blob = args

        except BackendNotAvailable as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except BackendCmdsInMaintenance as exc:
            raise FSWorkspaceInMaintenance(
                f"Cannot access workspace data while it is in maintenance"
            ) from exc

        except BackendConnectionError as exc:
            raise FSError(f"Cannot fetch user manifest from backend: {exc}") from exc

        try:
            author = await self.remote_devices_manager.get_device(expected_author)

        except RemoteDevicesManagerBackendOfflineError as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except RemoteDevicesManagerError as exc:
            raise FSError(f"Cannot retrieve author public key: {exc}") from exc

        try:
            manifest = UserManifest.decrypt_verify_and_load(
                blob,
                key=self.device.user_manifest_key,
                author_verify_key=author.verify_key,
                expected_id=self.device.user_manifest_id,
                expected_author=expected_author,
                expected_timestamp=expected_timestamp,
                expected_version=version if version is not None else expected_version,
            )

        except DataError as exc:
            raise FSError(f"Invalid user manifest: {exc}") from exc

        return manifest

    async def sync(self) -> None:
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSWorkspaceNotFoundError
        """
        user_manifest = self.get_user_manifest()
        if user_manifest.need_sync:
            await self._outbound_sync()
        else:
            await self._inbound_sync()

    async def _inbound_sync(self) -> None:
        # Retrieve remote
        target_um = await self._fetch_remote_user_manifest()
        diverged_um = self.get_user_manifest()
        if target_um.version == diverged_um.base_version:
            # Nothing new
            return

        # New things in remote, merge is needed
        async with self._update_user_manifest_lock:
            diverged_um = self.get_user_manifest()
            if target_um.version <= diverged_um.base_version:
                # Sync already achieved by a concurrent operation
                return
            merged_um = merge_local_user_manifests(diverged_um, target_um)
            self.set_user_manifest(merged_um)
            # In case we weren't online when the sharing message arrived,
            # we will learn about the change in the sharing only now.
            # Hence send the corresponding events !
            self._detect_and_send_shared_events(diverged_um, merged_um)
            # TODO: deprecated event ?
            self.event_bus.send("fs.entry.remote_changed", path="/", id=self.user_manifest_id)
            return

    def _detect_and_send_shared_events(self, old_um, new_um):
        entries = {}
        for old_entry in old_um.workspaces:
            entries[old_entry.id] = [old_entry, None]
        for new_entry in new_um.workspaces:
            try:
                entries[new_entry.id][1] = new_entry
            except KeyError:
                entries[new_entry.id] = [None, new_entry]

        for old_entry, new_entry in entries.values():
            if new_entry is None:
                logger.warning(
                    "Workspace entry has diseaper from user manifest", workspace_entry=old_entry
                )
            elif old_entry is None:
                if new_entry.role is not None:
                    # New sharing
                    self.event_bus.send("sharing.updated", new_entry=new_entry, previous_entry=None)
            else:
                # Sharing role has changed
                # Note it's possible to have `old_entry.role == new_entry.role`
                # (e.g. if our role went A -> B then B -> A while we were offline)
                # We should notify this anyway given it means some events could not
                # have been delivered to us (typically if we got revoked for a
                # short period of time while a `realm.vlobs_updated` event occured).
                self.event_bus.send(
                    "sharing.updated", new_entry=new_entry, previous_entry=old_entry
                )

    async def _outbound_sync(self) -> None:
        while True:
            try:
                await self._outbound_sync_inner()
                return

            except (BackendCmdsAlreadyExists, BackendCmdsBadVersion):
                # Concurrency error, fetch and merge remote changes before
                # retrying the sync
                await self._inbound_sync()
                continue

    async def _outbound_sync_inner(self):
        base_um = self.get_user_manifest()
        if not base_um.need_sync:
            return

        # Make sure the corresponding realm has been created in the backend
        if base_um.is_placeholder:
            certif = RealmRoleCertificateContent.build_realm_root_certif(
                author=self.device.device_id,
                timestamp=pendulum_now(),
                realm_id=self.device.user_manifest_id,
            ).dump_and_sign(self.device.signing_key)

            try:
                await self.backend_cmds.realm_create(certif)

            except BackendCmdsBadResponse as exc:
                if exc.status == "already_exists":
                    # It's possible a previous attempt to create this realm
                    # succeeded but we didn't receive the confirmation, hence
                    # we play idempotent here.
                    pass
                else:
                    raise FSError(f"Cannot create user manifest's realm in backend: {exc}") from exc

            except BackendNotAvailable as exc:
                raise FSBackendOfflineError(str(exc)) from exc

            except BackendConnectionError as exc:
                raise FSError(f"Cannot create user manifest's realm in backend: {exc}") from exc

        # Sync placeholders
        for w in base_um.workspaces:
            await self._workspace_minimal_sync(w)

        # Build vlob
        now = pendulum_now()
        to_sync_um = base_um.to_remote(author=self.device.device_id, timestamp=now)
        ciphered = to_sync_um.dump_sign_and_encrypt(
            author_signkey=self.device.signing_key, key=self.device.user_manifest_key
        )

        # Sync the vlob with backend
        try:
            # Note encryption_revision is always 1 given we never reencrypt
            # the user manifest's realm
            if to_sync_um.version == 1:
                await self.backend_cmds.vlob_create(
                    self.user_manifest_id, 1, self.user_manifest_id, now, ciphered
                )
            else:
                await self.backend_cmds.vlob_update(
                    1, self.user_manifest_id, to_sync_um.version, now, ciphered
                )

        except (BackendCmdsAlreadyExists, BackendCmdsBadVersion):
            # Concurrency error (handled by the caller)
            raise

        except BackendNotAvailable as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except BackendCmdsInMaintenance as exc:
            raise FSWorkspaceInMaintenance(
                f"Cannot modify workspace data while it is in maintenance"
            ) from exc

        except BackendConnectionError as exc:
            raise FSError(f"Cannot sync user manifest: {exc}") from exc

        # Merge back the manifest in local
        async with self._update_user_manifest_lock:
            diverged_um = self.get_user_manifest()
            # Final merge could have been achieved by a concurrent operation
            if to_sync_um.version > diverged_um.base_version:
                merged_um = merge_local_user_manifests(diverged_um, to_sync_um)
                self.set_user_manifest(merged_um)
            self.event_bus.send("fs.entry.synced", path="/", id=self.user_manifest_id)

    async def _workspace_minimal_sync(self, workspace_entry: WorkspaceEntry):
        """
        Raises:
            FSError
            FSBackendOfflineError
        """
        workspace = self.get_workspace(workspace_entry.id)
        await workspace.minimal_sync(workspace_entry.id)

    async def workspace_share(
        self, workspace_id: EntryID, recipient: UserID, role: Optional[WorkspaceRole]
    ) -> None:
        """
        Raises:
            FSError
            FSWorkspaceNotFoundError
            FSBackendOfflineError
            FSSharingNotAllowedError
        """
        if self.device.user_id == recipient:
            raise FSError("Cannot share to oneself")

        user_manifest = self.get_user_manifest()
        workspace_entry = user_manifest.get_workspace_entry(workspace_id)
        if not workspace_entry:
            raise FSWorkspaceNotFoundError(f"Unknown workspace `{workspace_id}`")

        # Make sure the workspace is not a placeholder
        await self._workspace_minimal_sync(workspace_entry)

        # Retrieve the user
        try:
            recipient_user, revoked_recipient_user = await self.remote_devices_manager.get_user(
                recipient
            )

        except RemoteDevicesManagerBackendOfflineError as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except RemoteDevicesManagerError as exc:
            raise FSError(f"Cannot retreive recipient: {exc}") from exc

        if revoked_recipient_user:
            raise FSError(f"User {recipient} revoked")

        # Note we don't bother to check workspace's access roles given they
        # could be outdated (and backend will do the check anyway)

        now = pendulum_now()

        # Build the sharing message
        try:
            if role is not None:
                recipient_message = SharingGrantedMessageContent(
                    author=self.device.device_id,
                    timestamp=now,
                    name=workspace_entry.name,
                    id=workspace_entry.id,
                    encryption_revision=workspace_entry.encryption_revision,
                    encrypted_on=workspace_entry.encrypted_on,
                    key=workspace_entry.key,
                )

            else:
                recipient_message = SharingRevokedMessageContent(
                    author=self.device.device_id, timestamp=now, id=workspace_entry.id
                )

            ciphered_recipient_message = recipient_message.dump_sign_and_encrypt_for(
                author_signkey=self.device.signing_key, recipient_pubkey=recipient_user.public_key
            )

        except DataError as exc:
            raise FSError(f"Cannot create sharing message for `{recipient}`: {exc}") from exc

        # Build role certificate
        role_certificate = RealmRoleCertificateContent(
            author=self.device.device_id,
            timestamp=now,
            realm_id=workspace_id,
            user_id=recipient,
            role=role,
        ).dump_and_sign(self.device.signing_key)

        # Actually send the command to the backend
        try:
            await self.backend_cmds.realm_update_roles(role_certificate, ciphered_recipient_message)

        except BackendNotAvailable as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except BackendCmdsNotAllowed as exc:
            raise FSSharingNotAllowedError(
                "Must be Owner or Manager on the workspace is mandatory to share it"
            ) from exc

        except BackendCmdsInMaintenance as exc:
            raise FSWorkspaceInMaintenance(
                f"Cannot share workspace while it is in maintenance"
            ) from exc

        except BackendCmdsRoleAlreadyGranted:
            # Stay idempotent
            return

        except BackendConnectionError as exc:
            raise FSError(f"Error while trying to set vlob group roles in backend: {exc}") from exc

    async def process_last_messages(self) -> List[Tuple[int, Exception]]:
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSSharingNotAllowedError
        """
        errors = []
        # Concurrent message processing is totally pointless
        async with self._process_messages_lock:
            user_manifest = self.get_user_manifest()
            initial_last_processed_message = user_manifest.last_processed_message
            try:
                messages = await self.backend_cmds.message_get(
                    offset=initial_last_processed_message
                )

            except BackendNotAvailable as exc:
                raise FSBackendOfflineError(str(exc)) from exc

            except BackendConnectionError as exc:
                raise FSError(f"Cannot retrieve user messages: {exc}") from exc

            new_last_processed_message = initial_last_processed_message
            for msg_offset, msg_sender, msg_timestamp, msg_body in messages:
                try:
                    await self._process_message(msg_sender, msg_timestamp, msg_body)
                    new_last_processed_message = msg_offset

                except FSBackendOfflineError:
                    raise

                except FSError as exc:
                    logger.warning(
                        "Invalid message", reason=exc, sender=msg_sender, offset=msg_offset
                    )
                    errors.append((msg_offset, exc))

            # Update message offset in user manifest
            async with self._update_user_manifest_lock:
                user_manifest = self.get_user_manifest()
                if user_manifest.last_processed_message < new_last_processed_message:
                    user_manifest = user_manifest.evolve_and_mark_updated(
                        last_processed_message=new_last_processed_message
                    )
                    self.set_user_manifest(user_manifest)
                    self.event_bus.send("fs.entry.updated", id=self.user_manifest_id)

        return errors

    async def _process_message(
        self, sender_id: DeviceID, expected_timestamp: Pendulum, ciphered: bytes
    ):
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSSharingNotAllowedError
        """
        # Retrieve the sender
        try:
            sender = await self.remote_devices_manager.get_device(sender_id)

        except RemoteDevicesManagerBackendOfflineError as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except RemoteDevicesManagerError as exc:
            raise FSError(f"Cannot retrieve message sender `{sender_id}`: {exc}") from exc

        # Decrypt&verify message
        try:
            msg = MessageContent.decrypt_verify_and_load_for(
                ciphered,
                recipient_privkey=self.device.private_key,
                author_verify_key=sender.verify_key,
                expected_author=sender_id,
                expected_timestamp=expected_timestamp,
            )

        except DataError as exc:
            raise FSError(f"Cannot decrypt&validate message from `{sender_id}`: {exc}") from exc

        if isinstance(msg, (SharingGrantedMessageContent, SharingReencryptedMessageContent)):
            await self._process_message_sharing_granted(msg)

        elif isinstance(msg, SharingRevokedMessageContent):
            await self._process_message_sharing_revoked(msg)

        elif isinstance(msg, PingMessageContent):
            self.event_bus.send("pinged")

    async def _process_message_sharing_granted(
        self, msg: Union[SharingRevokedMessageContent, SharingReencryptedMessageContent]
    ):
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSSharingNotAllowedError
        """
        # We cannot blindly trust the message sender ! Hence we first
        # interrogate the backend to make sure he is a workspace manager/owner.
        # Note this means we refuse to process messages from a former-manager,
        # even if the message was sent at a time the user was manager (in such
        # case the user can still ask for another manager to re-do the sharing
        # so it's no big deal).
        try:
            roles = await self.remote_loader.load_realm_current_roles(msg.id)

        except FSWorkspaceNoAccess:
            # Seems we lost the access roles anyway, nothing to do then
            return

        if roles.get(msg.author.user_id, None) not in (WorkspaceRole.OWNER, WorkspaceRole.MANAGER):
            raise FSSharingNotAllowedError(
                f"User {msg.author.user_id} cannot share workspace `{msg.id}`"
                " with us (requires owner or manager right)"
            )

        # Determine the access roles we have been given to
        self_role = roles.get(self.device.user_id)

        # Finally insert the new workspace entry into our user manifest
        workspace_entry = WorkspaceEntry(
            # Name are not required to be unique across workspaces, so no check to do here
            name=f"{msg.name} (shared by {msg.author.user_id})",
            id=msg.id,
            key=msg.key,
            encryption_revision=msg.encryption_revision,
            encrypted_on=msg.encrypted_on,
            role=self_role,
            role_cached_on=pendulum_now(),
        )

        async with self._update_user_manifest_lock:
            user_manifest = self.get_user_manifest()

            # Check if we already know this workspace
            already_existing_entry = user_manifest.get_workspace_entry(msg.id)
            if already_existing_entry:
                # Merge with existing as target to keep possible workpace rename
                workspace_entry = merge_workspace_entry(
                    None, workspace_entry, already_existing_entry
                )

            user_manifest = user_manifest.evolve_workspaces_and_mark_updated(workspace_entry)
            self.set_user_manifest(user_manifest)
            self.event_bus.send("userfs.updated")

            if not already_existing_entry:
                # TODO: remove this event ?
                self.event_bus.send("fs.entry.synced", id=workspace_entry.id, path=f"/{msg.name}")

            self.event_bus.send(
                "sharing.updated", new_entry=workspace_entry, previous_entry=already_existing_entry
            )

    async def _process_message_sharing_revoked(self, msg: SharingRevokedMessageContent):
        """
        Raises:
            FSError
            FSBackendOfflineError
        """
        # Unlike when somebody grant us workspace access, here we should no
        # longer be able to access the workspace.
        # This also include workspace participants, hence we have no way
        # verifying the sender is manager/owner... But this is not really a trouble:
        # if we cannot access the workspace info, we have been revoked anyway !
        try:
            await self.remote_loader.load_realm_current_roles(msg.id)

        except FSWorkspaceNoAccess:
            # Exactly what we expected !
            pass

        else:
            # We still have access over the workspace, nothing to do then
            return

        async with self._update_user_manifest_lock:
            user_manifest = self.get_user_manifest()

            # Save the revocation information in the user manifest
            existing_workspace_entry = user_manifest.get_workspace_entry(msg.id)
            if not existing_workspace_entry:
                # No workspace entry, nothing to update then
                return

            workspace_entry = merge_workspace_entry(
                None,
                existing_workspace_entry,
                existing_workspace_entry.evolve(role=None, role_cached_on=pendulum_now()),
            )
            if existing_workspace_entry == workspace_entry:
                # Cheap idempotent check
                return

            user_manifest = user_manifest.evolve_workspaces_and_mark_updated(workspace_entry)
            self.set_user_manifest(user_manifest)
            self.event_bus.send("userfs.updated")
            self.event_bus.send(
                "sharing.updated",
                new_entry=workspace_entry,
                previous_entry=existing_workspace_entry,
            )

    async def _retreive_participants(self, workspace_id):
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSWorkspaceNoAccess
        """
        # First retrieve workspace participants list
        roles = await self.remote_loader.load_realm_current_roles(workspace_id)

        # Then retrieve each participant user data
        try:
            users = []
            for user_id in roles.keys():
                user, revoked_user = await self.remote_devices_manager.get_user(user_id)
                if not revoked_user:
                    users.append(user)

        except RemoteDevicesManagerBackendOfflineError as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except RemoteDevicesManagerError as exc:
            raise FSError(f"Cannot retrieve workspace {workspace_id} participants: {exc}") from exc

        return users

    def _generate_reencryption_messages(self, new_workspace_entry, users, now: Pendulum):
        """
        Raises:
            FSError
        """
        msg = SharingReencryptedMessageContent(
            author=self.device.device_id,
            timestamp=now,
            name=new_workspace_entry.name,
            id=new_workspace_entry.id,
            encryption_revision=new_workspace_entry.encryption_revision,
            encrypted_on=new_workspace_entry.encrypted_on,
            key=new_workspace_entry.key,
        )

        per_user_ciphered_msgs = {}
        for user in users:
            try:
                ciphered = msg.dump_sign_and_encrypt_for(
                    author_signkey=self.device.signing_key, recipient_pubkey=user.public_key
                )
                per_user_ciphered_msgs[user.user_id] = ciphered
            except DataError as exc:
                raise FSError(
                    f"Cannot create reencryption message for `{user.user_id}`: {exc}"
                ) from exc

        return per_user_ciphered_msgs

    async def _send_start_reencryption_cmd(
        self, workspace_id, encryption_revision, timestamp, per_user_ciphered_msgs
    ):
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSWorkspaceNoAccess
            BackendCmdsParticipantsMismatchError
        """
        # Finally send command to the backend
        try:
            await self.backend_cmds.realm_start_reencryption_maintenance(
                workspace_id, encryption_revision, timestamp, per_user_ciphered_msgs
            )

        except BackendCmdsParticipantsMismatchError:
            # Catched by caller
            raise

        except BackendNotAvailable as exc:
            raise FSBackendOfflineError(str(exc)) from exc

        except BackendConnectionError as exc:
            if exc.status == "in_maintenance":
                raise FSWorkspaceInMaintenance(f"Workspace {workspace_id} already in maintenance")

            if exc.status == "not_allowed":
                raise FSWorkspaceNoAccess(
                    f"Not allowed to start maintenance on workspace {workspace_id}: {exc}"
                ) from exc

            raise FSError(f"Cannot start maintenance on workspace {workspace_id}: {exc}") from exc

    async def workspace_start_reencryption(self, workspace_id: EntryID) -> ReencryptionJob:
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSWorkspaceNoAccess
            FSWorkspaceNotFoundError
        """
        user_manifest = self.get_user_manifest()
        workspace_entry = user_manifest.get_workspace_entry(workspace_id)
        if not workspace_entry:
            raise FSWorkspaceNotFoundError(f"Unknown workspace `{workspace_id}`")

        now = pendulum_now()
        new_workspace_entry = workspace_entry.evolve(
            encryption_revision=workspace_entry.encryption_revision + 1,
            encrypted_on=now,
            key=SecretKey.generate(),
        )

        while True:
            # In order to provide the new key to each participant, we must
            # encrypt a message for each of them
            participants = await self._retreive_participants(workspace_entry.id)
            reencryption_msgs = self._generate_reencryption_messages(
                new_workspace_entry, participants, now
            )

            # Actually ask the backend to start the reencryption
            try:
                await self._send_start_reencryption_cmd(
                    workspace_entry.id,
                    new_workspace_entry.encryption_revision,
                    now,
                    reencryption_msgs,
                )

            except BackendCmdsParticipantsMismatchError:
                # Participant list has changed concurrently
                logger.info(
                    "Realm participants list has changed during start reencryption tentative, retrying",
                    workspace_id=workspace_id,
                )
                continue

            else:
                break

        # Note we don't update the user manifest here, this will be done when
        # processing the `realm.updated` message from the backend

        return ReencryptionJob(self.backend_cmds, new_workspace_entry, workspace_entry)

    async def workspace_continue_reencryption(self, workspace_id: EntryID) -> ReencryptionJob:
        """
        Raises:
            FSError
            FSBackendOfflineError
            FSWorkspaceNoAccess
            FSWorkspaceNotFoundError
        """
        user_manifest = self.get_user_manifest()
        workspace_entry = user_manifest.get_workspace_entry(workspace_id)
        if not workspace_entry:
            raise FSWorkspaceNotFoundError(f"Unknown workspace `{workspace_id}`")

        # First make sure the workspace is under maintenance
        status = await self.backend_cmds.realm_status(workspace_entry.id)
        if (
            not status["in_maintenance"]
            or status["maintenance_type"] != MaintenanceType.REENCRYPTION
        ):
            raise FSWorkspaceNotInMaintenance("Not in reencryption maintenance")
        current_encryption_revision = status["encryption_revision"]
        if status["encryption_revision"] != workspace_entry.encryption_revision:
            raise FSError("Bad encryption revision")

        # Must retreive the previous encryption revision's key
        version_to_fetch = None
        while True:
            previous_user_manifest = await self._fetch_remote_user_manifest(
                version=version_to_fetch
            )
            previous_workspace_entry = previous_user_manifest.get_workspace_entry(
                workspace_entry.id
            )
            if not previous_workspace_entry:
                raise FSError(
                    f"Never had access to encryption revision {current_encryption_revision - 1}"
                )

            if previous_workspace_entry.encryption_revision == current_encryption_revision - 1:
                break
            else:
                version_to_fetch = previous_workspace_entry.version - 1

        return ReencryptionJob(self.backend_cmds, workspace_entry, previous_workspace_entry)
