import sys
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget, QPushButton
from PyQt5.QtGui import QIcon, QPainter, QColor, QPixmap, QCursor
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint
from pynput import keyboard

SETTINGS_PANEL_STATE = {"open": False, "pos": None}
SETTINGS_PANEL_SIZE = (350, 350)
SETTINGS_HEADER_HEIGHT = 30

class SettingsButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)
        self.icon = QPixmap("ressources/sett.png")
        self._state = "normal"
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)
        self._last_inside = False
        self._last_mouse_down = False
        self._lock_state = None
        self._state_timer = QTimer(self)
        self._state_timer.setInterval(16)
        self._state_timer.timeout.connect(self._update_state_from_cursor)
        self._state_timer.start()

    def _set_state(self, state):
        if self._state == state:
            return
        self._state = state
        self.update()

    def _color(self):
        if self._state == "pressed":
            return QColor(230, 230, 230)
        if self._state == "hover":
            return QColor(204, 204, 204)
        return QColor(140, 139, 139)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(self._color())
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)
        if not self.icon.isNull():
            icon_size = 32
            x = (self.width() - icon_size) // 2
            y = (self.height() - icon_size) // 2
            painter.drawPixmap(x, y, icon_size, icon_size, self.icon)

    def _update_state_from_cursor(self, force=False):
        if self._lock_state is not None and not force:
            self._set_state(self._lock_state)
            return
        local_pos = self.mapFromGlobal(QCursor.pos())
        inside = self.rect().contains(local_pos)
        mouse_down = bool(QApplication.mouseButtons() & Qt.LeftButton)

        if inside and mouse_down:
            self._set_state("pressed")
        elif inside:
            self._set_state("hover")
        else:
            self._set_state("normal")

        if (
            self._lock_state is None and
            self._last_inside and inside and self._last_mouse_down and not mouse_down
        ):
            self.clicked.emit()

        self._last_inside = inside
        self._last_mouse_down = mouse_down

    def lock_state(self, state="pressed"):
        self._lock_state = state
        self._set_state(state)

    def unlock_state(self):
        self._lock_state = None
        self._update_state_from_cursor(force=True)

class DraggableHeader(QWidget):
    drag_delta = pyqtSignal(QPoint)
    drag_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._normal_color = QColor(128, 128, 128)
        self._drag_color = QColor(158, 158, 158)
        self._current_color = self._normal_color
        self._dragging = False
        self._last_global_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), self._current_color)
        pen = painter.pen()
        pen.setColor(Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_global_pos = event.globalPos()
            self._set_drag_color(True)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self._last_global_pos is not None:
            delta = event.globalPos() - self._last_global_pos
            self._last_global_pos = event.globalPos()
            self.drag_delta.emit(delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self._last_global_pos = None
            self._set_drag_color(False)
            self.drag_finished.emit()
        super().mouseReleaseEvent(event)

    def _set_drag_color(self, dragging):
        self._current_color = self._drag_color if dragging else self._normal_color
        self.update()

class SettingsPanel(QWidget):
    panel_closed = pyqtSignal()
    panel_moved = pyqtSignal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(*SETTINGS_PANEL_SIZE)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        self.header = DraggableHeader(self)
        self.header.setFixedHeight(SETTINGS_HEADER_HEIGHT)
        self.header.setGeometry(0, 0, self.width(), self.header.height())
        self.header.drag_delta.connect(self._handle_drag)
        self.header.drag_finished.connect(self._emit_position)

        self.close_button = QPushButton("X", self.header)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(
            "background-color: transparent; color: #FFFFFF; font-weight: bold; border: none;"
        )
        self.close_button.clicked.connect(self.close_panel)
        self._place_close_button()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#B3B3B3"))
        pen = painter.pen()
        pen.setColor(Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _place_close_button(self):
        margin = 12
        x = self.header.width() - self.close_button.width() - margin
        y = (self.header.height() - self.close_button.height()) // 2
        self.close_button.move(x, y)

    def resizeEvent(self, event):
        self.header.setGeometry(0, 0, self.width(), self.header.height())
        self._place_close_button()
        super().resizeEvent(event)

    def close_panel(self):
        self.hide()
        self.panel_closed.emit()

    def _handle_drag(self, delta):
        self.move(self.pos() + delta)
        self.panel_moved.emit(self.pos())

    def _emit_position(self):
        self.panel_moved.emit(self.pos())

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.StrongFocus)
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)
        QApplication.setOverrideCursor(Qt.ArrowCursor)
        self.banner = QPixmap("ressources/banner.png")
        self.settings_button = SettingsButton(self)
        self.settings_panel = SettingsPanel(self)
        self.settings_panel.hide()
        self.settings_panel.panel_closed.connect(self._on_settings_panel_closed)
        self.settings_panel.panel_moved.connect(self._store_settings_position)
        self.settings_button.clicked.connect(self._handle_settings_button)
        self.show()
        self.activateWindow()
        self.setFocus()
        self._position_button()
        self._restore_settings_panel_state()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(23, 22, 22, 204))
        if not self.banner.isNull():
            target_width = int(self.width() * 0.13)
            aspect_ratio = self.banner.width() / self.banner.height()
            target_height = int(target_width / aspect_ratio)
            x = (self.width() - target_width) // 2
            y = int(self.height() * 0.03)
            painter.drawPixmap(x, y, target_width, target_height, self.banner)

    def resizeEvent(self, event):
        self._position_button()
        super().resizeEvent(event)

    def _position_button(self):
        btn_size = self.settings_button.width()
        btn_x = (self.width() - btn_size) // 2
        btn_y = int(self.height() * 0.97) - btn_size
        self.settings_button.move(btn_x, btn_y)

    def _handle_settings_button(self):
        if self.settings_panel.isVisible():
            return
        self._show_settings_panel()

    def _show_settings_panel(self):
        self._apply_panel_position()
        self.settings_panel.show()
        self.settings_panel.raise_()
        self.settings_button.lock_state("pressed")
        self._store_settings_position(self.settings_panel.pos())
        SETTINGS_PANEL_STATE["open"] = True

    def _on_settings_panel_closed(self):
        SETTINGS_PANEL_STATE["open"] = False
        self.settings_button.unlock_state()

    def _store_settings_position(self, pos):
        SETTINGS_PANEL_STATE["pos"] = QPoint(pos)

    def _apply_panel_position(self):
        saved_pos = SETTINGS_PANEL_STATE.get("pos")
        if saved_pos is not None:
            self.settings_panel.move(saved_pos)
        else:
            self._center_settings_panel()

    def _center_settings_panel(self):
        x = (self.width() - self.settings_panel.width()) // 2
        y = (self.height() - self.settings_panel.height()) // 2
        self.settings_panel.move(x, y)

    def _restore_settings_panel_state(self):
        self._apply_panel_position()
        if SETTINGS_PANEL_STATE.get("open"):
            self._show_settings_panel()
        else:
            self.settings_panel.hide()
            self.settings_button.unlock_state()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_F5, Qt.Key_Escape):
            self.close()

    def closeEvent(self, event):
        self._store_settings_position(self.settings_panel.pos())
        SETTINGS_PANEL_STATE["open"] = self.settings_panel.isVisible()
        self.releaseKeyboard()
        QApplication.restoreOverrideCursor()
        self.deleteLater()
        super().closeEvent(event)

class AppWithGlobalKeyHandler(QApplication):
    request_toggle = pyqtSignal()
    request_close = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.overlay = None
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()
        self.request_toggle.connect(self.toggle_overlay, Qt.QueuedConnection)
        self.request_close.connect(self._close_overlay, Qt.QueuedConnection)

    def on_key_press(self, key):
        try:
            if key == keyboard.Key.f5:
                self.request_toggle.emit()
            elif key == keyboard.Key.esc:
                self.request_close.emit()
        except Exception:
            pass

    def toggle_overlay(self):
        if self.overlay is None or not self.overlay.isVisible():
            self.overlay = Overlay()
            self.overlay.destroyed.connect(self._clear_overlay)
        else:
            self.overlay.close()
            self.overlay = None

    def _clear_overlay(self, *args):
        self.overlay = None

    def _close_overlay(self):
        if self.overlay is not None:
            self.overlay.close()

def main():
    app = AppWithGlobalKeyHandler(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    tray_icon = QSystemTrayIcon()
    tray_icon.setIcon(QIcon("ressources/tray.png"))
    tray_icon.setToolTip("NANOverlay")

    menu = QMenu()
    close_action = menu.addAction("Close")
    close_action.triggered.connect(app.quit)

    tray_icon.setContextMenu(menu)
    tray_icon.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()