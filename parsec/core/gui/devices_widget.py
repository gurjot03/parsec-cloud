# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

import pendulum
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import QWidget, QMenu
from PyQt5.QtGui import QPixmap

from parsec.types import DeviceID
from parsec.crypto import build_revoked_device_certificate
from parsec.core.backend_connection import BackendNotAvailable, BackendCmdsBadResponse

from parsec.core.gui.trio_thread import JobResultError, ThreadSafeQtSignal, QtToTrioJob
from parsec.core.gui.lang import translate as _
from parsec.core.gui.custom_widgets import TaskbarButton, show_info, show_error, QuestionDialog
from parsec.core.gui.ui.devices_widget import Ui_DevicesWidget
from parsec.core.gui.register_device_dialog import RegisterDeviceDialog
from parsec.core.gui.ui.device_button import Ui_DeviceButton


class DeviceButton(QWidget, Ui_DeviceButton):
    revoke_clicked = pyqtSignal(QWidget)

    def __init__(
        self, device_name, is_current_device, is_revoked, revoked_on, certified_on, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.revoked_on = revoked_on
        self.label.is_revoked = is_revoked
        self.is_current_device = is_current_device
        self.label.setPixmap(QPixmap(":/icons/images/icons/personal-computer.png"))
        self.device_name = device_name
        self.certified_on = certified_on
        self.set_display(device_name)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def set_display(self, value):
        if len(value) > 16:
            value = value[:16] + "-\n" + value[16:]
        if self.is_current_device:
            value += _("\n(current)")
        self.label_device.setText(value)

    @property
    def is_revoked(self):
        return self.label.is_revoked

    @is_revoked.setter
    def is_revoked(self, value):
        self.label.is_revoked = value
        self.label.repaint()

    def show_context_menu(self, pos):
        global_pos = self.mapToGlobal(pos)
        menu = QMenu(self)
        action = menu.addAction(_("Show info"))
        action.triggered.connect(self.show_device_info)
        if not self.label.is_revoked and not self.is_current_device:
            action = menu.addAction(_("Revoke"))
            action.triggered.connect(self.revoke)
        menu.exec_(global_pos)

    def show_device_info(self):
        text = "{}\n\n".format(self.device_name)
        text += _("Created on {}").format(self.certified_on.format("%x %X"))
        if self.label.is_revoked:
            text += "\n\n"
            text += _("This device has been revoked.")
        show_info(self, text)

    def revoke(self):
        self.revoke_clicked.emit(self)


async def _do_revoke_device(core, device_name, button):
    try:
        revoked_device_certificate = build_revoked_device_certificate(
            core.device.device_id,
            core.device.signing_key,
            DeviceID(f"{core.device.device_id.user_id}@{device_name}"),
            pendulum.now(),
        )
        await core.user_fs.backend_cmds.device_revoke(revoked_device_certificate)
        return button
    except BackendCmdsBadResponse as exc:
        raise JobResultError(exc.status)


async def _do_list_devices(core):
    try:
        current_device = core.device
        _, devices = await core.remote_devices_manager.get_user_and_devices(current_device.user_id)
        return devices
    except BackendNotAvailable:
        raise JobResultError("offline")


class DevicesWidget(QWidget, Ui_DevicesWidget):
    revoke_success = pyqtSignal(QtToTrioJob)
    revoke_error = pyqtSignal(QtToTrioJob)
    list_success = pyqtSignal(QtToTrioJob)
    list_error = pyqtSignal(QtToTrioJob)

    def __init__(self, core, jobs_ctx, event_bus, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setupUi(self)
        self.jobs_ctx = jobs_ctx
        self.core = core
        self.event_bus = event_bus
        self.devices = []
        self.taskbar_buttons = []
        button_add_device = TaskbarButton(icon_path=":/icons/images/icons/plus_off.png")
        button_add_device.clicked.connect(self.register_new_device)
        self.taskbar_buttons.append(button_add_device)
        self.filter_timer = QTimer()
        self.filter_timer.setInterval(300)
        self.revoke_success.connect(self.on_revoke_success)
        self.revoke_error.connect(self.on_revoke_error)
        self.list_success.connect(self.on_list_success)
        self.list_error.connect(self.on_list_error)
        self.line_edit_search.textChanged.connect(self.filter_timer.start)
        self.filter_timer.timeout.connect(self.on_filter_timer_timeout)
        self.reset()

    def disconnect_all(self):
        pass

    def get_taskbar_buttons(self):
        return self.taskbar_buttons.copy()

    def on_filter_timer_timeout(self):
        self.filter_devices(self.line_edit_search.text())

    def filter_devices(self, pattern):
        pattern = pattern.lower()
        for i in range(self.layout_devices.count()):
            item = self.layout_devices.itemAt(i)
            if item:
                w = item.widget()
                if pattern and pattern not in w.device_name.lower():
                    w.hide()
                else:
                    w.show()

    def on_revoke_success(self, job):
        button = job.ret
        show_info(self, _('Device "{}" has been revoked.').format(button.device_name))
        button.is_revoked = True

    def on_revoke_error(self, job):
        status = job.status
        if status == "already_revoked":
            show_error(self, _("Device has already been revoked."))
        elif status == "not_found":
            show_error(self, _("Device not found."))
        elif status == "invalid_role" or status == "invalid_certification":
            show_error(self, _("You don't have the permission to revoke this device."))
        elif status == "error":
            show_error(self, _("Can not revoke this device."))

    def revoke_device(self, device_button):
        result = QuestionDialog.ask(
            self,
            _("Confirmation"),
            _('Are you sure you want to revoke device "{}" ?').format(device_button.device_name),
        )
        if not result:
            return
        self.jobs_ctx.submit_job(
            ThreadSafeQtSignal(self, "revoke_success", QtToTrioJob),
            ThreadSafeQtSignal(self, "revoke_error", QtToTrioJob),
            _do_revoke_device,
            core=self.core,
            device_name=device_button.device_name,
            button=device_button,
        )

    def register_new_device(self):
        self.register_device_dialog = RegisterDeviceDialog(
            core=self.core, jobs_ctx=self.jobs_ctx, parent=self
        )
        self.register_device_dialog.exec_()
        self.reset()

    def add_device(self, device_name, is_current_device, is_revoked, revoked_on, certified_on):
        if device_name in self.devices:
            return
        button = DeviceButton(device_name, is_current_device, is_revoked, revoked_on, certified_on)
        self.layout_devices.addWidget(
            button, int(len(self.devices) / 4), int(len(self.devices) % 4)
        )
        button.revoke_clicked.connect(self.revoke_device)
        button.show()
        self.devices.append(device_name)

    def on_list_success(self, job):
        devices = job.ret
        current_device = self.core.device
        self.devices = []
        while self.layout_devices.count() != 0:
            item = self.layout_devices.takeAt(0)
            if item:
                w = item.widget()
                self.layout_devices.removeWidget(w)
                w.setParent(None)

        for device in devices:
            self.add_device(
                device.device_name,
                is_current_device=device.device_name == current_device.device_name,
                is_revoked=bool(device.revoked_on),
                revoked_on=device.revoked_on,
                certified_on=device.certified_on,
            )

    def on_list_error(self, job):
        pass

    def reset(self):
        self.jobs_ctx.submit_job(
            ThreadSafeQtSignal(self, "list_success", QtToTrioJob),
            ThreadSafeQtSignal(self, "list_error", QtToTrioJob),
            _do_list_devices,
            core=self.core,
        )
