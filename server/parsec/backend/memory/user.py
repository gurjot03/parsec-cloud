# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 2016-present Scille SAS
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, Iterable, List, Tuple

import attr

from parsec._parsec import (
    ActiveUsersLimit,
    BackendEventCertificatesUpdated,
    BackendEventUserUpdatedOrRevoked,
    DateTime,
    DeviceID,
    DeviceName,
    HumanHandle,
    OrganizationID,
    UserID,
    UserProfile,
)
from parsec.backend.user import (
    BaseUserComponent,
    Device,
    GetUserAndDevicesResult,
    HumanFindResultItem,
    Trustchain,
    UserActiveUsersLimitReached,
    UserAlreadyExistsError,
    UserAlreadyRevokedError,
    UserNotFoundError,
)
from parsec.backend.user_type import User, UserUpdate

if TYPE_CHECKING:
    from parsec.backend.memory.organization import MemoryOrganizationComponent
    from parsec.backend.memory.realm import MemoryRealmComponent
    from parsec.backend.memory.sequester import MemorySequesterComponent


@attr.s
class OrganizationStore:
    human_handle_to_user_id: Dict[HumanHandle, UserID] = attr.ib(factory=dict)
    users: Dict[UserID, User] = attr.ib(factory=dict)
    devices: Dict[UserID, Dict[DeviceName, Device]] = attr.ib(factory=lambda: defaultdict(dict))


class MemoryUserComponent(BaseUserComponent):
    def __init__(
        self, send_event: Callable[..., Coroutine[Any, Any, None]], *args: Any, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._send_event = send_event
        self._organizations: Dict[OrganizationID, OrganizationStore] = defaultdict(
            OrganizationStore
        )

    def register_components(
        self,
        organization: MemoryOrganizationComponent,
        realm: MemoryRealmComponent,
        sequester: MemorySequesterComponent,
        **other_components: Any,
    ) -> None:
        self._organization_component = organization
        self._realm_component = realm
        self._sequester_component = sequester

    def get_current_certificate_index(self, organization_id: OrganizationID) -> int:
        org = self._organizations[organization_id]

        index = len(org.devices)

        for user in org.users.values():
            index += 2 if user.revoked_user_certificate else 1

        for (realm_orgid, _), realm in self._realm_component._realms.items():
            if realm_orgid != organization_id:
                continue
            for granted_role in realm.granted_roles:
                index += len((granted_role.granted_on, granted_role.certificate))

        return index

    async def notify_certificates_update(
        self,
        organization_id: OrganizationID,
        index: int,
    ) -> None:
        event = BackendEventCertificatesUpdated(
            organization_id=organization_id,
            index=index,
        )
        await self._send_event(event)

    async def create_user(
        self, organization_id: OrganizationID, user: User, first_device: Device
    ) -> None:
        org = self._organizations[organization_id]
        active_users_limit = self._organization_component._organizations[
            organization_id
        ].active_users_limit
        active_users = (u for u in org.users.values() if u.revoked_on is None)
        if active_users_limit is not None and active_users_limit <= ActiveUsersLimit.LimitedTo(
            len(list(active_users))
        ):
            raise UserActiveUsersLimitReached()

        if user.user_id in org.users:
            raise UserAlreadyExistsError(f"User `{user.user_id.str}` already exists")

        if user.human_handle and user.human_handle in org.human_handle_to_user_id:
            raise UserAlreadyExistsError(
                f"Human handle `{user.human_handle.str}` already corresponds to a non-revoked user"
            )

        org.users[user.user_id] = user
        org.devices[first_device.user_id][first_device.device_name] = first_device
        if user.human_handle:
            org.human_handle_to_user_id[user.human_handle] = user.user_id

        await self.notify_certificates_update(
            organization_id=organization_id,
            index=self.get_current_certificate_index(organization_id),
        )
        await self.notify_certificates_update(
            organization_id=organization_id,
            index=self.get_current_certificate_index(organization_id),
        )

    async def create_device(
        self, organization_id: OrganizationID, device: Device, encrypted_answer: bytes = b""
    ) -> None:
        org = self._organizations[organization_id]

        if device.user_id not in org.users:
            raise UserNotFoundError(f"User `{device.user_id.str}` doesn't exists")

        user_devices = org.devices[device.user_id]
        if device.device_name in user_devices:
            raise UserAlreadyExistsError(f"Device `{device.device_id.str}` already exists")

        user_devices[device.device_name] = device

        await self.notify_certificates_update(
            organization_id=organization_id,
            index=self.get_current_certificate_index(organization_id),
        )

    async def _get_trustchain(
        self,
        organization_id: OrganizationID,
        *devices_ids: DeviceID | None,
        redacted: bool = False,
    ) -> Trustchain:
        trustchain_devices = set()
        trustchain_users = set()
        trustchain_revoked_users = set()
        in_trustchain = set()

        user_certif_field = "redacted_user_certificate" if redacted else "user_certificate"
        device_certif_field = "redacted_device_certificate" if redacted else "device_certificate"

        async def _recursive_extract_creators(device_id: DeviceID | None) -> None:
            if not device_id or device_id in in_trustchain:
                return
            in_trustchain.add(device_id)
            user = self._get_user(organization_id, device_id.user_id)
            device = self._get_device(organization_id, device_id)
            trustchain_devices.add(getattr(device, device_certif_field))
            trustchain_users.add(getattr(user, user_certif_field))
            if user.revoked_user_certificate:
                trustchain_revoked_users.add(user.revoked_user_certificate)
            await _recursive_extract_creators(device.device_certifier)
            await _recursive_extract_creators(user.revoked_user_certifier)
            await _recursive_extract_creators(user.user_certifier)

        for device_id in devices_ids:
            await _recursive_extract_creators(device_id)

        return Trustchain(
            devices=list(trustchain_devices),
            users=list(trustchain_users),
            revoked_users=list(trustchain_revoked_users),
        )

    def _get_user(self, organization_id: OrganizationID, user_id: UserID) -> User:
        org = self._organizations[organization_id]

        try:
            return org.users[user_id]

        except KeyError:
            raise UserNotFoundError(user_id)

    async def get_user(self, organization_id: OrganizationID, user_id: UserID) -> User:
        return self._get_user(organization_id, user_id)

    async def get_user_with_trustchain(
        self, organization_id: OrganizationID, user_id: UserID
    ) -> Tuple[User, Trustchain]:
        user = self._get_user(organization_id, user_id)
        trustchain = await self._get_trustchain(
            organization_id, user.user_certifier, user.revoked_user_certifier
        )
        return user, trustchain

    async def get_user_with_device_and_trustchain(
        self, organization_id: OrganizationID, device_id: DeviceID
    ) -> Tuple[User, Device, Trustchain]:
        user = self._get_user(organization_id, device_id.user_id)
        user_device = self._get_device(organization_id, device_id)
        trustchain = await self._get_trustchain(
            organization_id,
            user.user_certifier,
            user.revoked_user_certifier,
            user_device.device_certifier,
        )
        return user, user_device, trustchain

    async def get_user_with_devices_and_trustchain(
        self, organization_id: OrganizationID, user_id: UserID, redacted: bool = False
    ) -> GetUserAndDevicesResult:
        user = self._get_user(organization_id, user_id)
        user_devices = self._get_user_devices(organization_id, user_id)
        user_devices_values = tuple(user_devices.values())
        trustchain = await self._get_trustchain(
            organization_id,
            user.user_certifier,
            user.revoked_user_certifier,
            *[device.device_certifier for device in user_devices_values],
            redacted=redacted,
        )
        return GetUserAndDevicesResult(
            user_certificate=user.redacted_user_certificate if redacted else user.user_certificate,
            revoked_user_certificate=user.revoked_user_certificate,
            device_certificates=tuple(
                d.redacted_device_certificate if redacted else d.device_certificate
                for d in user_devices.values()
            ),
            trustchain_device_certificates=tuple(trustchain.devices),
            trustchain_user_certificates=tuple(trustchain.users),
            trustchain_revoked_user_certificates=tuple(trustchain.revoked_users),
        )

    def _get_device(self, organization_id: OrganizationID, device_id: DeviceID) -> Device:
        org = self._organizations[organization_id]

        try:
            return org.devices[device_id.user_id][device_id.device_name]

        except KeyError:
            raise UserNotFoundError(device_id)

    def _get_user_devices(
        self, organization_id: OrganizationID, user_id: UserID
    ) -> Dict[DeviceName, Device]:
        org = self._organizations[organization_id]
        # Make sure user exists
        self._get_user(organization_id, user_id)
        return org.devices[user_id]

    async def get_user_with_device(
        self, organization_id: OrganizationID, device_id: DeviceID
    ) -> Tuple[User, Device]:
        user = self._get_user(organization_id, device_id.user_id)
        device = self._get_device(organization_id, device_id)
        return user, device

    def _find_humans(
        self,
        organization_id: OrganizationID,
        query: str | None = None,
        page: int = 1,
        per_page: int = 100,
        omit_revoked: bool = False,
        omit_non_human: bool = False,
    ) -> Tuple[List[HumanFindResultItem], int]:
        assert page >= 1
        assert per_page >= 1

        org = self._organizations[organization_id]

        # Query is run against human handle field, hence non-human are automatically ignored
        users: Iterable[User]
        if query:
            # Handle a case insensitive find search to be conform with postgresql query
            users = []
            query_parts = query.lower().split()
            for user in org.users.values():
                label: str = ""
                email: str = ""
                if not user.human_handle:
                    label = user.user_id.str.lower()
                else:
                    email = user.human_handle.email.lower()
                    label = user.human_handle.label.lower()
                if all([part in email for part in query_parts]) or all(
                    [part in label for part in query_parts]
                ):
                    users.append(user)
        else:
            users = org.users.values()
            if omit_non_human:
                users = [r for r in users if r.human_handle is not None]
        # Sort human by label
        users = [
            *sorted(
                [res for res in users if res.human_handle is not None],
                key=lambda r: r.human_handle.label.lower(),
            ),
            *[res for res in users if res.human_handle is None],
        ]
        now = DateTime.now()
        results = [
            HumanFindResultItem(
                user_id=user.user_id,
                human_handle=user.human_handle,
                revoked=(user.revoked_on is not None and user.revoked_on <= now),
            )
            for user in users
        ]

        if omit_revoked:
            results = [res for res in results if not res.revoked]

        total = len(results)

        # Handle pagination
        paginated_results = results[(page - 1) * per_page : page * per_page]

        return paginated_results, total

    async def find_humans(
        self,
        organization_id: OrganizationID,
        query: str | None = None,
        page: int = 1,
        per_page: int = 100,
        omit_revoked: bool = False,
        omit_non_human: bool = False,
    ) -> Tuple[List[HumanFindResultItem], int]:
        return self._find_humans(
            organization_id=organization_id,
            query=query,
            page=page,
            per_page=per_page,
            omit_revoked=omit_revoked,
            omit_non_human=omit_non_human,
        )

    async def revoke_user(
        self,
        organization_id: OrganizationID,
        user_id: UserID,
        revoked_user_certificate: bytes,
        revoked_user_certifier: DeviceID,
        revoked_on: DateTime | None = None,
    ) -> None:
        revoked_on = revoked_on or DateTime.now()
        org = self._organizations[organization_id]

        try:
            user = org.users[user_id]

        except KeyError:
            raise UserNotFoundError(user_id)

        if user.revoked_on:
            raise UserAlreadyRevokedError()

        org.users[user_id] = user.evolve(
            revoked_on=revoked_on,
            revoked_user_certificate=revoked_user_certificate,
            revoked_user_certifier=revoked_user_certifier,
        )
        if user.human_handle:
            del org.human_handle_to_user_id[user.human_handle]

        await self.notify_certificates_update(
            organization_id=organization_id,
            index=self.get_current_certificate_index(organization_id),
        )
        await self._send_event(
            BackendEventUserUpdatedOrRevoked(
                organization_id=organization_id, user_id=user_id, profile=None
            )
        )

    async def update_user(
        self,
        organization_id: OrganizationID,
        user_id: UserID,
        new_profile: UserProfile,
        user_update_certificate: bytes,
        user_update_certifier: DeviceID,
        updated_on: DateTime | None = None,
    ) -> None:
        """
        Raises:
            UserNotFoundError
            UserAlreadyRevokedError
        """
        updated_on = updated_on or DateTime.now()
        org = self._organizations[organization_id]

        try:
            user = org.users[user_id]

        except KeyError:
            raise UserNotFoundError(user_id)

        if user.revoked_on or user.profile == new_profile:
            raise UserAlreadyExistsError()

        # TODO: check all user/device/realm roles certificates creation date against `updated_on`
        # and raise `UserRequireGreaterTimestampError`

        # TODO: check the last vlob the updated user has uploaded is not posterior to
        # `updated_on`, this is not strictly needed (unlike when we revoke) given any
        # role has the right to write in a realm, however this should be cheap and
        # can prevent future bug when we introduce more advanced profiles...
        # (`UserRequireGreaterTimestampError` should be raised in this case)

        # TODO: If the new role is OUTSIDER, check the user is not OWNER/MANAGER in
        # any shared realm (it is allowed for non-shared realm given the user must
        # be sole OWNER of the realm containing it own user manifest)
        # There is no dedicated error status for this behavior, but should we have it ?
        # This add complexity but allow to provide better error message to the end user
        # (e.g. "this user cannot be switched to outsider given ")

        org.users[user_id] = user.evolve(
            updates=tuple(
                (
                    *user.updates,
                    UserUpdate(
                        new_profile=new_profile,
                        updated_on=updated_on,
                        user_update_certificate=user_update_certificate,
                        user_update_certifier=user_update_certifier,
                    ),
                )
            )
        )
        if user.human_handle:
            del org.human_handle_to_user_id[user.human_handle]

        await self.notify_certificates_update(
            organization_id=organization_id,
            index=self.get_current_certificate_index(organization_id),
        )
        await self._send_event(
            BackendEventUserUpdatedOrRevoked(
                organization_id=organization_id, user_id=user_id, profile=new_profile
            )
        )

    async def dump_users(self, organization_id: OrganizationID) -> Tuple[List[User], List[Device]]:
        org = self._organizations[organization_id]
        devices: List[Device] = []
        for user_devices in org.devices.values():
            devices += user_devices.values()
        return list(org.users.values()), devices

    async def get_certificates(
        self, organization_id: OrganizationID, offset: int, redacted: bool
    ) -> list[bytes]:
        """
        Raises: Nothing !
        """
        certificates = []

        # Certificates with the same timestamp will be ordered by priority (lower first)
        # Multiple certificates can have the same timestamp if they have been created
        # together: so far this is only the case for organization bootstrap and user creation.
        # In such cases the events should also be ordered by they event types (e.g.
        # `UserCertificate` must always be before `DeviceCertificate`)
        SEQUESTER_AUTHORITY_PRIORITY = 0  # Max prio
        USER_PRIORITY = 1
        DEFAULT_PRIORITY = 2

        # 1) Add sequester authority certificate
        org = self._organization_component._organizations[organization_id]

        # 2) Add sequester service certificates
        if org.sequester_authority:
            certificates.append(
                (
                    org.bootstrapped_on,
                    SEQUESTER_AUTHORITY_PRIORITY,
                    org.sequester_authority.certificate,
                )
            )
            for service in self._sequester_component._services[organization_id].values():
                certificates.append(
                    (service.created_on, DEFAULT_PRIORITY, service.service_certificate)
                )

        # 3) Add user & revoked user certificates
        org = self._organizations[organization_id]
        for user in org.users.values():
            certif = user.redacted_user_certificate if redacted else user.user_certificate
            certificates.append((user.created_on, USER_PRIORITY, certif))
            if user.revoked_user_certificate:
                assert user.revoked_on is not None
                certificates.append(
                    (user.revoked_on, DEFAULT_PRIORITY, user.revoked_user_certificate)
                )

        # 4) Add device certificates
        for devices in org.devices.values():
            for device in devices.values():
                certif = (
                    device.redacted_device_certificate if redacted else device.device_certificate
                )
                certificates.append((device.created_on, DEFAULT_PRIORITY, certif))

        # 5) Add realm role certificates
        for (realm_orgid, _), realm in self._realm_component._realms.items():
            if realm_orgid != organization_id:
                continue
            for granted_role in realm.granted_roles:
                certificates.append(
                    (granted_role.granted_on, DEFAULT_PRIORITY, granted_role.certificate)
                )

        # Sort certificates by timestamp... and also type (see priority) !
        certificates.sort()

        return [certif for _, _, certif in certificates[offset:]]

    def test_duplicate_organization(self, id: OrganizationID, new_id: OrganizationID) -> None:
        self._organizations[new_id] = deepcopy(self._organizations[id])

    def test_drop_organization(self, id: OrganizationID) -> None:
        self._organizations.pop(id, None)
