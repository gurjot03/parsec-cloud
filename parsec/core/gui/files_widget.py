import os
import pathlib
from uuid import UUID

from PyQt5.QtCore import Qt, QCoreApplication, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QListWidgetItem,
    QMenu,
    QStyledItemDelegate,
    QStyle,
    QFileDialog,
)
from PyQt5.QtGui import QColor

from parsec.core.gui import desktop
from parsec.core.gui.core_call import core_call
from parsec.core.gui.custom_widgets import show_error, show_warning, ask_question, get_text
from parsec.core.gui.ui.files_widget import Ui_FilesWidget
from parsec.core.gui.item_widget import FileItemWidget, FolderItemWidget, ParentItemWidget
from parsec.core.fs import FSEntryNotFound


class Delegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor(45, 144, 209))
        else:
            super().paint(painter, option, index)


class FilesWidget(QWidget, Ui_FilesWidget):
    fs_changed_qt = pyqtSignal(str, UUID, str)
    back_clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.list_files.setItemDelegate(Delegate())
        self.button_back.clicked.connect(self.back_clicked)
        self.button_create_folder.clicked.connect(self.create_folder_clicked)
        self.button_import_files.clicked.connect(self.import_files_clicked)
        self.button_import_folder.clicked.connect(self.import_folder_clicked)
        self.list_files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_files.customContextMenuRequested.connect(self.show_context_menu)
        self.list_files.currentItemChanged.connect(self.set_item_selected)
        self.list_files.itemDoubleClicked.connect(self.item_double_clicked)
        self.line_edit_search.textChanged.connect(self.filter_files)
        self.current_directory = ""
        self.mountpoint = ""
        self.workspace = None
        core_call().connect_event("fs.entry.updated", self._on_fs_entry_updated_trio)
        core_call().connect_event("fs.entry.synced", self._on_fs_entry_synced_trio)
        self.fs_changed_qt.connect(self._on_fs_changed_qt)

    def set_item_selected(self, current, previous):
        if previous:
            self.list_files.itemWidget(previous).set_selected(False)
        if current:
            self.list_files.itemWidget(current).set_selected(True)

    def set_workspace(self, workspace):
        self.workspace = workspace
        self.label_current_workspace.setText(workspace)
        self.load("")

    def load(self, directory):
        self.list_files.clear()
        self.current_directory = directory
        if self.current_directory:
            self._add_parent_folder()
        if not self.current_directory:
            self.label_current_directory.hide()
            self.label_caret.hide()
        else:
            self.label_current_directory.setText(self.current_directory)
            self.label_current_directory.show()
            self.label_caret.show()
        dir_path = os.path.join("/", self.workspace, self.current_directory)
        dir_stat = core_call().stat(dir_path)
        for child in dir_stat["children"]:
            child_stat = core_call().stat(os.path.join(dir_path, child))
            if child_stat["is_folder"]:
                self._add_folder(child)
            else:
                self._add_file(
                    child, child_stat["size"], child_stat["created"], child_stat["updated"]
                )

    def _import_folder(self, src, dst):
        err = False
        try:
            core_call().create_folder(dst)
            for f in src.iterdir():
                try:
                    if f.is_dir():
                        err |= self._import_folder(f, os.path.join(dst, f.name))
                    elif f.is_file():
                        err |= self._import_file(f, os.path.join(dst, f.name))
                except:
                    err = True
        except:
            err = True
        return err

    def _import_file(self, src, dst):
        fd_out = None
        try:
            core_call().file_create(dst)
            fd_out = core_call().file_open(dst)
            with open(src, "rb") as fd_in:
                while True:
                    chunk = fd_in.read(8192)
                    if not chunk:
                        break
                    core_call().file_write(fd_out, chunk)
            return False
        except:
            return True
        finally:
            if fd_out:
                core_call().file_close(fd_out)

    def import_files_clicked(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            QCoreApplication.translate("FilesWidget", "Select files to import"),
            str(pathlib.Path.home()),
        )
        if not paths:
            return
        for path in paths:
            p = pathlib.Path(path)
            err = self._import_file(
                str(p), os.path.join("/", self.workspace, self.current_directory, p.name)
            )
        if err:
            show_error(
                self, QCoreApplication.translate("FilesWidget", "Some files could not be imported.")
            )
        self.load(self.current_directory)

    def import_folder_clicked(self):
        path = QFileDialog.getExistingDirectory(
            self,
            QCoreApplication.translate("FilesWidget", "Select a directory to import"),
            str(pathlib.Path.home()),
        )
        if not path:
            return
        p = pathlib.Path(path)
        err = self._import_folder(
            p, os.path.join("/", self.workspace, self.current_directory, p.name)
        )
        if err:
            show_error(
                self, QCoreApplication.translate("FilesWidget", "The folder could not be imported.")
            )
        self.load(self.current_directory)

    def filter_files(self, pattern):
        pattern = pattern.lower()
        for i in range(self.list_files.count()):
            item = self.list_files.item(i)
            widget = self.list_files.itemWidget(item)
            if pattern not in widget.name.lower():
                item.setHidden(True)
            else:
                item.setHidden(False)

    def _create_folder(self, folder_name):
        try:
            core_call().create_folder(
                os.path.join("/", self.workspace, self.current_directory, folder_name)
            )
            return True
        except FileExistsError:
            show_error(
                self,
                QCoreApplication.translate(
                    "FilesWidget", "A folder with the same name already exists."
                ),
            )
            return False

    def _add_parent_folder(self):
        item = QListWidgetItem()
        widget = ParentItemWidget()
        item.setSizeHint(widget.sizeHint())
        self.list_files.addItem(item)
        self.list_files.setItemWidget(item, widget)

    def _add_folder(self, folder_name):
        item = QListWidgetItem()
        widget = FolderItemWidget(item, folder_name, parent=self.list_files)
        item.setSizeHint(widget.sizeHint())
        self.list_files.addItem(item)
        self.list_files.setItemWidget(item, widget)
        widget.delete_clicked.connect(self.delete)

    def _add_file(self, file_name, file_size, created_on, updated_on):
        item = QListWidgetItem()
        widget = FileItemWidget(
            item, file_name, file_size, created_on, updated_on, parent=self.list_files
        )
        item.setSizeHint(widget.sizeHint())
        self.list_files.addItem(item)
        self.list_files.setItemWidget(item, widget)
        widget.delete_clicked.connect(self.delete)

    def delete(self, item):
        widget = self.list_files.itemWidget(item)
        result = ask_question(
            self,
            QCoreApplication.translate("FilesWidget", "Confirmation"),
            QCoreApplication.translate(
                "FilesWidget", 'Are you sure you want to delete "{}" ?'
            ).format(widget.name),
        )
        if not result:
            return
        path = os.path.join("/", self.workspace, self.current_directory, widget.name)
        try:
            if isinstance(widget, FolderItemWidget):
                self._delete_folder(path)
            else:
                core_call().delete_file(path)
            self.list_files.takeItem(self.list_files.row(item))
        except:
            show_error(self, QCoreApplication.translate('Can not delete "{}"').format(widget.name))

    def _delete_folder(self, path):
        result = core_call().stat(path)
        for child in result.get("children", []):
            child_path = os.path.join(path, child)
            file_infos = core_call().stat(os.path.join(path, child))
            if file_infos["is_folder"]:
                self._delete_folder(child_path)
            else:
                core_call().delete_file(child_path)
        core_call().delete_folder(path)

    def create_folder_clicked(self):
        folder_name = get_text(
            self,
            QCoreApplication.translate("FilesWidget", "Folder name"),
            QCoreApplication.translate("FilesWidget", "Enter new folder name"),
            placeholder="Name",
        )
        if not folder_name:
            return
        self._create_folder(folder_name)

    def show_context_menu(self, pos):
        global_pos = self.list_files.mapToGlobal(pos)
        current_widget = self.list_files.itemWidget(self.list_files.currentItem())
        if isinstance(current_widget, ParentItemWidget):
            return
        menu = QMenu(self.list_files)
        if isinstance(current_widget, FileItemWidget):
            action = menu.addAction(QCoreApplication.translate("FilesWidget", "Open"))
        else:
            action = menu.addAction(QCoreApplication.translate("FilesWidget", "Open in explorer"))
        action.triggered.connect(self.open_file(current_widget))
        action = menu.addAction(QCoreApplication.translate("FilesWidget", "Rename"))
        action.triggered.connect(self.rename(current_widget))
        menu.exec_(global_pos)

    def rename(self, widget):
        def _inner_rename():
            new_name = get_text(
                self,
                QCoreApplication.translate("FilesWidget", "New name"),
                QCoreApplication.translate("FilesWidget", "Enter file new name"),
                placeholder="File name",
                default_text=widget.name,
            )
            if not new_name:
                return
            try:
                if isinstance(widget, FolderItemWidget):
                    core_call().move_folder(
                        os.path.join("/", self.workspace, self.current_directory, widget.name),
                        os.path.join("/", self.workspace, self.current_directory, new_name),
                    )
                else:
                    core_call().move_file(
                        os.path.join("/", self.workspace, self.current_directory, widget.name),
                        os.path.join("/", self.workspace, self.current_directory, new_name),
                    )
                self.load(self.current_directory)
            except:
                show_error(self, QCoreApplication.translate("FilesWidget", "Can not rename."))

        return _inner_rename

    def open_file(self, widget):
        def _inner_open_file():
            desktop.open_file(
                os.path.join(self.mountpoint, self.workspace, self.current_directory, widget.name)
            )

        return _inner_open_file

    def item_double_clicked(self, item):
        widget = self.list_files.itemWidget(item)
        if isinstance(widget, ParentItemWidget):
            self.load(os.path.dirname(self.current_directory))
        elif isinstance(widget, FileItemWidget):
            desktop.open_file(
                os.path.join(self.mountpoint, self.workspace, self.current_directory, widget.name)
            )
        elif isinstance(widget, FolderItemWidget):
            self.load(os.path.join(os.path.join(self.current_directory, widget.name)))

    def reset(self):
        self.workspace = ""
        self.current_directory = ""
        self.list_files.clear()

    def _on_fs_entry_synced_trio(self, event, path, id):
        self.fs_changed_qt.emit(event, id, path)

    def _on_fs_entry_updated_trio(self, event, id):
        self.fs_changed_qt.emit(event, id, None)

    def _on_fs_changed_qt(self, event, id, path):
        if not path:
            try:
                path = core_call().get_entry_path(id)
            except FSEntryNotFound:
                # Entry not locally present, nothing to do
                return

        # Modifications on root is handled by workspace_widget
        if path == "/":
            return

        # TODO: too cumbersome...
        if isinstance(path, pathlib.PurePosixPath):
            modified_hops = [x for x in path.parts if x != "/"]
        else:
            modified_hops = [x for x in path.split("/") if x and x != "/"]

        if self.workspace and self.current_directory:
            current_dir_hops = [self.workspace] + [
                x for x in self.current_directory.split("/") if x
            ]
        else:
            current_dir_hops = []
        # Only direct children to current directory require reloading
        if modified_hops == current_dir_hops or modified_hops[:-1] == current_dir_hops:
            self.load(self.current_directory)
