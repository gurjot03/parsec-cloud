# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

import os

import trio
import pytest
from pathlib import Path
from unittest.mock import patch

from parsec.core.mountpoint import (
    mountpoint_manager_factory,
    MountpointDisabled,
    MountpointConfigurationError,
    MountpointAlreadyMounted,
    MountpointNotMounted,
    MountpointDriverCrash,
)

from parsec.core import logged_core_factory


@pytest.fixture
def base_mountpoint(tmpdir):
    return Path(tmpdir / "base_mountpoint")


@pytest.mark.trio
async def test_runner_not_available(alice_fs, event_bus):
    base_mountpoint = Path("/foo")

    with patch("parsec.core.mountpoint.manager.get_mountpoint_runner", return_value=None):
        with pytest.raises(RuntimeError):
            async with mountpoint_manager_factory(alice_fs, event_bus, base_mountpoint):
                pass


@pytest.mark.trio
async def test_mountpoint_disabled(alice_fs, event_bus):
    base_mountpoint = Path("/foo")

    await alice_fs.workspace_create("/w")

    with patch("parsec.core.mountpoint.manager.get_mountpoint_runner", return_value=None):
        async with mountpoint_manager_factory(
            alice_fs, event_bus, base_mountpoint, enabled=False
        ) as mountpoint_manager:
            with pytest.raises(MountpointDisabled):
                await mountpoint_manager.mount_workspace("w")


@pytest.mark.trio
async def test_mount_unknown_workspace(base_mountpoint, alice_fs, event_bus):
    async with mountpoint_manager_factory(
        alice_fs, event_bus, base_mountpoint
    ) as mountpoint_manager:
        with pytest.raises(MountpointConfigurationError) as exc:
            await mountpoint_manager.mount_workspace("dummy")

        assert exc.value.args == ("Workspace `dummy` doesn't exist",)


@pytest.mark.trio
@pytest.mark.mountpoint
async def test_base_mountpoint_not_created(base_mountpoint, alice, alice_fs, event_bus):
    # Path should be created if it doesn' exist
    base_mountpoint = base_mountpoint / "dummy/dummy/dummy"
    mountpoint = f"{base_mountpoint.absolute()}/{alice.user_id}-w"

    await alice_fs.workspace_create("/w")
    await alice_fs.file_create("/w/bar.txt")

    bar_txt = trio.Path(f"{mountpoint}/bar.txt")

    # Now we can start fuse

    async with mountpoint_manager_factory(
        alice_fs, event_bus, base_mountpoint
    ) as mountpoint_manager:

        await mountpoint_manager.mount_workspace("w")
        assert await bar_txt.exists()


@pytest.mark.trio
@pytest.mark.mountpoint
# @pytest.mark.skipif(os.name == "nt", reason="Error message is POSIX-specific")
async def test_mountpoint_already_in_use(base_mountpoint, alice, alice_fs, alice2_fs, event_bus):
    # Path should be created if it doesn' exist
    mountpoint = f"{base_mountpoint.absolute()}/{alice.user_id}-w"

    await alice_fs.workspace_create("/w")
    await alice_fs.file_create("/w/bar.txt")
    await alice2_fs.workspace_create("/w")
    await alice2_fs.file_create("/w/bar.txt")

    bar_txt = trio.Path(f"{mountpoint}/bar.txt")

    # Now we can start fuse

    async with mountpoint_manager_factory(alice_fs, event_bus, base_mountpoint) as alice_mm:

        async with mountpoint_manager_factory(alice_fs, event_bus, base_mountpoint) as alice2_mm:

            await alice_mm.mount_workspace("w")
            assert await bar_txt.exists()

            with pytest.raises(MountpointDriverCrash) as exc:
                await alice2_mm.mount_workspace("w")
            assert exc.value.args == (f"Fuse has crashed on {mountpoint}: EPERM",)
            assert await bar_txt.exists()

        assert await bar_txt.exists()

    assert not await bar_txt.exists()


@pytest.mark.skipif(os.name == "nt", reason="Not available yet for WinFSP...")
@pytest.mark.trio
@pytest.mark.mountpoint
@pytest.mark.parametrize("manual_unmount", [True, False])
async def test_mount_and_explore_workspace(
    base_mountpoint, alice, alice_fs, event_bus, manual_unmount
):
    # Populate a bit the fs first...

    await alice_fs.workspace_create("/w")
    await alice_fs.folder_create("/w/foo")
    await alice_fs.file_create("/w/bar.txt")
    await alice_fs.file_write("/w/bar.txt", b"Hello world !")

    # Now we can start fuse

    with event_bus.listen() as spy:

        async with mountpoint_manager_factory(
            alice_fs, event_bus, base_mountpoint
        ) as mountpoint_manager:

            await mountpoint_manager.mount_workspace("w")
            mountpoint = f"{base_mountpoint.absolute()}/{alice.user_id}-w"

            spy.assert_events_occured(
                [
                    ("mountpoint.starting", {"mountpoint": mountpoint}),
                    ("mountpoint.started", {"mountpoint": mountpoint}),
                ]
            )

            # Finally explore the mountpoint

            def inspect_mountpoint():
                wksp_children = set(os.listdir(f"{mountpoint}"))
                assert wksp_children == {"foo", "bar.txt"}

                bar_stat = os.stat(f"{mountpoint}/bar.txt")
                assert bar_stat.st_size == len(b"Hello world !")

                with open(f"{mountpoint}/bar.txt", "rb") as fd:
                    bar_txt = fd.read()
                assert bar_txt == b"Hello world !"

            # Note given python fs api is blocking, we must run it inside a thread
            # to avoid blocking the trio loop and ending up in a deadlock
            await trio.run_sync_in_worker_thread(inspect_mountpoint)

            if manual_unmount:
                await mountpoint_manager.unmount_workspace("w")
                # Mountpoint should be stopped by now
                spy.assert_events_occured([("mountpoint.stopped", {"mountpoint": mountpoint})])

        if not manual_unmount:
            # Mountpoint should be stopped by now
            spy.assert_events_occured([("mountpoint.stopped", {"mountpoint": mountpoint})])


@pytest.mark.skipif(os.name == "nt", reason="Not available yet for WinFSP...")
@pytest.mark.trio
@pytest.mark.mountpoint
@pytest.mark.parametrize("manual_unmount", [True, False])
async def test_idempotent_mount(base_mountpoint, alice, alice_fs, event_bus, manual_unmount):
    mountpoint = f"{base_mountpoint.absolute()}/{alice.user_id}-w"

    # Populate a bit the fs first...

    await alice_fs.workspace_create("/w")
    await alice_fs.file_create("/w/bar.txt")

    bar_txt = trio.Path(f"{mountpoint}/bar.txt")

    # Now we can start fuse

    async with mountpoint_manager_factory(
        alice_fs, event_bus, base_mountpoint
    ) as mountpoint_manager:

        await mountpoint_manager.mount_workspace("w")
        assert await bar_txt.exists()

        with pytest.raises(MountpointAlreadyMounted):
            await mountpoint_manager.mount_workspace("w")
        assert await bar_txt.exists()

        await mountpoint_manager.unmount_workspace("w")
        assert not await bar_txt.exists()

        with pytest.raises(MountpointNotMounted):
            await mountpoint_manager.unmount_workspace("w")
        assert not await bar_txt.exists()

        await mountpoint_manager.mount_workspace("w")
        assert await bar_txt.exists()


@pytest.mark.trio
@pytest.mark.mountpoint
@pytest.mark.skipif(os.name == "nt", reason="Fusermount not available on Windows")
async def test_unmount_with_fusermount(base_mountpoint, alice, alice_fs, event_bus):
    mountpoint = f"{base_mountpoint.absolute()}/{alice.user_id}-w"
    await alice_fs.workspace_create("/w")
    await alice_fs.file_create("/w/bar.txt")

    bar_txt = trio.Path(f"{mountpoint}/bar.txt")

    async with mountpoint_manager_factory(
        alice_fs, event_bus, base_mountpoint
    ) as mountpoint_manager:

        with event_bus.listen() as spy:
            await mountpoint_manager.mount_workspace("w")
            proc = trio.Process(f"fusermount -u {mountpoint}".split())
            await proc.wait()

        spy.assert_events_occured([("mountpoint.stopped", {"mountpoint": mountpoint})])
        assert not await bar_txt.exists()


@pytest.mark.trio
@pytest.mark.skipif(os.name == "nt", reason="FUSE not used on Windows")
async def test_hard_crash_in_fuse_thread(base_mountpoint, alice_fs, event_bus):
    await alice_fs.workspace_create("/w")

    class ToughLuckError(Exception):
        pass

    def _crash_fuse(*args, **kwargs):
        raise ToughLuckError()

    with patch("parsec.core.mountpoint.fuse_runner.FUSE", new=_crash_fuse):
        async with mountpoint_manager_factory(
            alice_fs, event_bus, base_mountpoint
        ) as mountpoint_manager:

            with pytest.raises(MountpointDriverCrash):
                await mountpoint_manager.mount_workspace("w")


@pytest.mark.trio
@pytest.mark.mountpoint
@pytest.mark.skipif(os.name == "nt", reason="WinFSP doesn't support `pathlib.Path.stat` yet...")
async def test_work_within_logged_core(base_mountpoint, core_config, alice, tmpdir):
    core_config = core_config.evolve(mountpoint_enabled=True, mountpoint_base_dir=base_mountpoint)
    mountpoint = f"{base_mountpoint.absolute()}/{alice.user_id}-w"
    bar_txt = trio.Path(f"{mountpoint}/bar.txt")

    async with logged_core_factory(core_config, alice) as alice_core:
        await alice_core.fs.workspace_create("/w")
        await alice_core.fs.file_create("/w/bar.txt")

        assert not await bar_txt.exists()

        await alice_core.mountpoint_manager.mount_workspace("w")

        assert await bar_txt.exists()

    assert not await bar_txt.exists()
