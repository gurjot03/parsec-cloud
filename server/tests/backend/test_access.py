# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 2016-present Scille SAS
from __future__ import annotations

import pytest

from parsec._parsec import InvitationType
from parsec.api.protocol import AUTHENTICATED_CMDS, INVITED_CMDS, packb, unpackb


async def check_forbidden_cmds(ws, cmds):
    for cmd in cmds:
        if cmd == "events_listen":
            # Must pass wait option otherwise backend will hang forever
            await ws.send(packb({"cmd": cmd, "wait": False}))
        else:
            await ws.send(packb({"cmd": cmd}))
        rep = await ws.receive()
        assert unpackb(rep) == {"status": "invalid_msg_format", "reason": "Invalid message format"}


async def check_allowed_cmds(ws, cmds):
    for cmd in cmds:
        if cmd == "events_listen":
            # Must pass wait option otherwise backend will hang forever
            await ws.send(packb({"cmd": cmd, "wait": False}))
        else:
            await ws.send(packb({"cmd": cmd}))
        rep = await ws.receive()
        assert unpackb(rep)["status"] != "unknown_command"


@pytest.mark.trio
async def test_invited_has_limited_access(
    backend, backend_asgi_app, backend_invited_ws_factory, alice
):
    invitation = await backend.invite.new_for_device(
        organization_id=alice.organization_id, greeter_user_id=alice.user_id
    )

    async with backend_invited_ws_factory(
        backend_asgi_app,
        organization_id=alice.organization_id,
        invitation_type=InvitationType.DEVICE,
        token=invitation.token,
    ) as ws:
        await check_forbidden_cmds(ws, AUTHENTICATED_CMDS - INVITED_CMDS)
        await check_allowed_cmds(ws, INVITED_CMDS)


@pytest.mark.trio
async def test_authenticated_has_limited_access(alice_ws):
    await check_forbidden_cmds(alice_ws, INVITED_CMDS - AUTHENTICATED_CMDS)
    await check_allowed_cmds(alice_ws, AUTHENTICATED_CMDS)
