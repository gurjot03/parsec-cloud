# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

import pytest
from uuid import UUID
import trio
from pendulum import Pendulum

from parsec.api.protocole import RealmRole

from tests.backend.test_events import events_subscribe, events_listen_nowait


NOW = Pendulum(2000, 1, 1)
VLOB_ID = UUID("00000000000000000000000000000001")
OTHER_VLOB_ID = UUID("00000000000000000000000000000002")
YET_ANOTHER_VLOB_ID = UUID("00000000000000000000000000000003")
REALM_ID = UUID("0000000000000000000000000000000A")
OTHER_REALM_ID = UUID("0000000000000000000000000000000B")
YET_ANOTHER_REALM_ID = UUID("0000000000000000000000000000000C")


@pytest.mark.trio
async def test_vlobs_updated_event_ok(backend, alice_backend_sock, alice, alice2):
    # Not listened events
    await backend.vlob.create(
        organization_id=alice.organization_id,
        author=alice.device_id,
        realm_id=REALM_ID,
        encryption_revision=1,
        vlob_id=VLOB_ID,
        timestamp=NOW,
        blob=b"v1",
    )
    await backend.event_bus.spy.wait_multiple_with_timeout(
        ["realm.roles_updated", "realm.vlobs_updated"]
    )

    # Start listening events
    await events_subscribe(alice_backend_sock)

    # Good events
    with backend.event_bus.listen() as spy:

        await backend.vlob.create(
            organization_id=alice.organization_id,
            author=alice2.device_id,
            realm_id=OTHER_REALM_ID,
            encryption_revision=1,
            vlob_id=OTHER_VLOB_ID,
            timestamp=NOW,
            blob=b"v1",
        )
        await backend.vlob.update(
            organization_id=alice.organization_id,
            author=alice2.device_id,
            encryption_revision=1,
            vlob_id=VLOB_ID,
            version=2,
            timestamp=NOW,
            blob=b"v2",
        )
        await backend.vlob.update(
            organization_id=alice.organization_id,
            author=alice2.device_id,
            encryption_revision=1,
            vlob_id=VLOB_ID,
            version=3,
            timestamp=NOW,
            blob=b"v3",
        )

        # No guarantees those events occur before the commands' return
        # On top of that, other `realm.vlobs_updated` has been triggered
        # before us (i.g. during alice user vlob creation). In case of slow
        # database those events could pop only now, hence shadowing the ones
        # we are waiting for. To avoid this we have to specify event params.
        await spy.wait_multiple_with_timeout(
            [
                (
                    "realm.roles_updated",
                    {
                        "organization_id": alice2.organization_id,
                        "author": alice2.device_id,
                        "realm_id": OTHER_REALM_ID,
                        "user": alice2.user_id,
                        "role": RealmRole.OWNER,
                    },
                ),
                (
                    "realm.vlobs_updated",
                    {
                        "organization_id": alice2.organization_id,
                        "author": alice2.device_id,
                        "realm_id": OTHER_REALM_ID,
                        "checkpoint": 1,
                        "src_id": OTHER_VLOB_ID,
                        "src_version": 1,
                    },
                ),
                (
                    "realm.vlobs_updated",
                    {
                        "organization_id": alice2.organization_id,
                        "author": alice2.device_id,
                        "realm_id": REALM_ID,
                        "checkpoint": 2,
                        "src_id": VLOB_ID,
                        "src_version": 2,
                    },
                ),
                (
                    "realm.vlobs_updated",
                    {
                        "organization_id": alice2.organization_id,
                        "author": alice2.device_id,
                        "realm_id": REALM_ID,
                        "checkpoint": 3,
                        "src_id": VLOB_ID,
                        "src_version": 3,
                    },
                ),
            ]
        )

    reps = [
        await events_listen_nowait(alice_backend_sock),
        await events_listen_nowait(alice_backend_sock),
        await events_listen_nowait(alice_backend_sock),
        await events_listen_nowait(alice_backend_sock),
        await events_listen_nowait(alice_backend_sock),
    ]
    assert reps == [
        {
            "status": "ok",
            "event": "realm.roles_updated",
            "realm_id": OTHER_REALM_ID,
            "role": RealmRole.OWNER,
        },
        {
            "status": "ok",
            "event": "realm.vlobs_updated",
            "realm_id": OTHER_REALM_ID,
            "checkpoint": 1,
            "src_id": OTHER_VLOB_ID,
            "src_version": 1,
        },
        {
            "status": "ok",
            "event": "realm.vlobs_updated",
            "realm_id": REALM_ID,
            "checkpoint": 2,
            "src_id": VLOB_ID,
            "src_version": 2,
        },
        {
            "status": "ok",
            "event": "realm.vlobs_updated",
            "realm_id": REALM_ID,
            "checkpoint": 3,
            "src_id": VLOB_ID,
            "src_version": 3,
        },
        {"status": "no_events"},
    ]


@pytest.mark.trio
async def test_vlobs_updated_event_handle_self_events(backend, alice_backend_sock, alice):
    await events_subscribe(alice_backend_sock)

    with backend.event_bus.listen() as spy:

        await backend.vlob.create(
            organization_id=alice.organization_id,
            author=alice.device_id,
            realm_id=REALM_ID,
            encryption_revision=1,
            vlob_id=VLOB_ID,
            timestamp=NOW,
            blob=b"v1",
        )

        await backend.vlob.create(
            organization_id=alice.organization_id,
            author=alice.device_id,
            realm_id=REALM_ID,
            encryption_revision=1,
            vlob_id=OTHER_VLOB_ID,
            timestamp=NOW,
            blob=b"v1",
        )
        await backend.vlob.update(
            organization_id=alice.organization_id,
            author=alice.device_id,
            encryption_revision=1,
            vlob_id=VLOB_ID,
            version=2,
            timestamp=NOW,
            blob=b"v2",
        )

        # Wait for events to be processed by the backend
        await spy.wait_multiple_with_timeout(
            [
                "realm.roles_updated",
                "realm.vlobs_updated",
                "realm.vlobs_updated",
                "realm.vlobs_updated",
            ]
        )

    # Only self-events not ignored is the roles_updated one
    rep = await events_listen_nowait(alice_backend_sock)
    assert rep == {
        "status": "ok",
        "event": "realm.roles_updated",
        "realm_id": REALM_ID,
        "role": RealmRole.OWNER,
    }

    # Other self-events should have been ignored
    rep = await events_listen_nowait(alice_backend_sock)
    assert rep == {"status": "no_events"}


@pytest.mark.trio
async def test_vlobs_updated_event_not_participant(backend, alice_backend_sock, bob):
    await events_subscribe(alice_backend_sock)

    with backend.event_bus.listen() as spy:

        await backend.vlob.create(
            organization_id=bob.organization_id,
            author=bob.device_id,
            realm_id=REALM_ID,
            encryption_revision=1,
            vlob_id=VLOB_ID,
            timestamp=NOW,
            blob=b"v1",
        )
        await backend.vlob.update(
            organization_id=bob.organization_id,
            author=bob.device_id,
            encryption_revision=1,
            vlob_id=VLOB_ID,
            version=2,
            timestamp=NOW,
            blob=b"v2",
        )

        # Wait for events to be processed by the backend
        await spy.wait_multiple_with_timeout(
            ["realm.roles_updated", "realm.vlobs_updated", "realm.vlobs_updated"]
        )

    rep = await events_listen_nowait(alice_backend_sock)
    assert rep == {"status": "no_events"}


@pytest.mark.trio
@pytest.mark.parametrize("realm_created_by_self", (True, False))
async def test_vlobs_updated_event_realm_created_after_subscribe(
    backend, alice_backend_sock, alice, alice2, realm_created_by_self
):
    await events_subscribe(alice_backend_sock)

    # New realm, should get events anyway
    with backend.event_bus.listen() as spy:
        realm_creator = alice if realm_created_by_self else alice2
        # Create the realm
        await backend.vlob.create(
            organization_id=realm_creator.organization_id,
            author=realm_creator.device_id,
            realm_id=REALM_ID,
            encryption_revision=1,
            vlob_id=VLOB_ID,
            timestamp=NOW,
            blob=b"v1",
        )
        # Update vlob in realm
        await backend.vlob.update(
            organization_id=alice2.organization_id,
            author=alice2.device_id,
            encryption_revision=1,
            vlob_id=VLOB_ID,
            version=2,
            timestamp=NOW,
            blob=b"v2",
        )
        # Create vlob in realm
        await backend.vlob.create(
            organization_id=alice2.organization_id,
            author=alice2.device_id,
            realm_id=REALM_ID,
            encryption_revision=1,
            vlob_id=OTHER_VLOB_ID,
            timestamp=NOW,
            blob=b"v1",
        )

        # Wait for events to be processed by the backend
        await spy.wait_multiple_with_timeout(
            [
                "realm.roles_updated",
                "realm.vlobs_updated",
                "realm.vlobs_updated",
                "realm.vlobs_updated",
            ]
        )

    # Realm access granted
    rep = await events_listen_nowait(alice_backend_sock)
    assert rep == {
        "status": "ok",
        "event": "realm.roles_updated",
        "realm_id": REALM_ID,
        "role": RealmRole.OWNER,
    }

    if not realm_created_by_self:
        # Create realm event
        rep = await events_listen_nowait(alice_backend_sock)
        assert rep == {
            "status": "ok",
            "event": "realm.vlobs_updated",
            "realm_id": REALM_ID,
            "checkpoint": 1,
            "src_id": VLOB_ID,
            "src_version": 1,
        }

    # Update vlob in realm event
    rep = await events_listen_nowait(alice_backend_sock)
    assert rep == {
        "status": "ok",
        "event": "realm.vlobs_updated",
        "realm_id": REALM_ID,
        "checkpoint": 2,
        "src_id": VLOB_ID,
        "src_version": 2,
    }

    # Create vlob in realm event
    rep = await events_listen_nowait(alice_backend_sock)
    assert rep == {
        "status": "ok",
        "event": "realm.vlobs_updated",
        "realm_id": REALM_ID,
        "checkpoint": 3,
        "src_id": OTHER_VLOB_ID,
        "src_version": 1,
    }

    rep = await events_listen_nowait(alice_backend_sock)
    assert rep == {"status": "no_events"}
