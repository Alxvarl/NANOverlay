import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget, QPushButton, QLabel
from PyQt5.QtGui import QIcon, QPainter, QColor, QPixmap, QCursor, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from pynput import keyboard
SETTINGS_PANEL_SIZE = (350, 350)
SETTINGS_HEADER_HEIGHT = 30
FADE_DURATION_MS = 250
DEFAULT_TRIGGER_KEY = "F5"
BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / "ressources" / "settings.novres"


def _build_special_key_map():
    mapping = {
        "ESC": keyboard.Key.esc,
        "ENTER": keyboard.Key.enter,
        "RETURN": keyboard.Key.enter,
        "SPACE": keyboard.Key.space,
        "TAB": keyboard.Key.tab,
    }
    for index in range(1, 25):
        attr = f"f{index}"
        if hasattr(keyboard.Key, attr):
            mapping[f"F{index}"] = getattr(keyboard.Key, attr)
    return mapping


SPECIAL_PYNPUT_KEYS = _build_special_key_map()


def is_valid_hotkey_name(name):
    if not name:
        return False
    value = name.upper()
    if value in SPECIAL_PYNPUT_KEYS:
        return True
    return len(value) == 1 and value.isalnum()


def normalize_hotkey_name(name):
    if not name:
        return None
    trimmed = name.strip().upper()
    if is_valid_hotkey_name(trimmed):
        return trimmed
    return None


def ensure_settings_file():
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(
            f"key={DEFAULT_TRIGGER_KEY}\npanel_open=0\n",
            encoding="utf-8",
        )


def read_settings_map():
    ensure_settings_file()
    settings = {}
    for line in SETTINGS_FILE.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        settings[k.strip()] = v.strip()
    return settings


def write_settings_map(settings):
    ensure_settings_file()
    lines = [f"{key}={value}\n" for key, value in settings.items()]
    SETTINGS_FILE.write_text("".join(lines), encoding="utf-8")


def load_hotkey_from_file():
    settings = read_settings_map()
    value = normalize_hotkey_name(settings.get("key")) if settings else None
    if value is not None:
        return value
    return save_hotkey_to_file(DEFAULT_TRIGGER_KEY)


def save_hotkey_to_file(key_name):
    normalized = normalize_hotkey_name(key_name) or DEFAULT_TRIGGER_KEY
    settings = read_settings_map()
    settings["key"] = normalized
    if "panel_open" not in settings:
        settings["panel_open"] = "0"
    write_settings_map(settings)
    return normalized


def load_panel_open_state():
    settings = read_settings_map()
    return settings.get("panel_open", "0") == "1"


def save_panel_open_state(is_open):
    settings = read_settings_map()
    settings.setdefault("key", DEFAULT_TRIGGER_KEY)
    settings["panel_open"] = "1" if is_open else "0"
    write_settings_map(settings)


def pynput_key_matches_hotkey(pynput_key, hotkey_name):
    target = hotkey_name.upper()
    special = SPECIAL_PYNPUT_KEYS.get(target)
    if special is not None:
        return pynput_key == special
    if isinstance(pynput_key, keyboard.KeyCode) and pynput_key.char:
        return pynput_key.char.upper() == target
    return False


def qt_key_event_to_name(event):
    key = event.key()
    if Qt.Key_F1 <= key <= Qt.Key_F35:
        return f"F{key - Qt.Key_F1 + 1}"
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(ord('A') + (key - Qt.Key_A))
    if Qt.Key_0 <= key <= Qt.Key_9:
        return str(key - Qt.Key_0)
    mapping = {
        Qt.Key_Space: "SPACE",
        Qt.Key_Tab: "TAB",
        Qt.Key_Return: "ENTER",
        Qt.Key_Enter: "ENTER",
    }
    if key in mapping:
        return mapping[key]
    text = event.text().strip().upper()
    return text or None

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


class HotkeyInput(QWidget):
    hotkey_selected = pyqtSignal(str)
    capture_started = pyqtSignal()
    capture_finished = pyqtSignal()

    def __init__(self, key_name, parent=None):
        super().__init__(parent)
        self._current_key = key_name
        self._display_text = key_name
        self._capturing = False
        self._prev_key = key_name
        self.setFixedSize(140, 32)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setCursor(Qt.PointingHandCursor)
        self._font = QFont("Segoe UI", 12)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QColor("#D9D9D9"))
        painter.setPen(Qt.black)
        painter.drawRoundedRect(self.rect(), 6, 6)
        painter.setFont(self._font)
        painter.setPen(Qt.black)
        painter.drawText(self.rect(), Qt.AlignCenter, self._display_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_capture()
        super().mousePressEvent(event)

    def focusOutEvent(self, event):
        if self._capturing:
            self._stop_capture(commit=False)
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if not self._capturing:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key_Escape:
            self._current_key = self._prev_key
            self._display_text = self._current_key
            self._stop_capture(commit=False)
            return
        key_name = qt_key_event_to_name(event)
        if not key_name:
            return
        self._current_key = key_name
        self._display_text = key_name
        self._stop_capture(commit=True)
        self.hotkey_selected.emit(key_name)

    def _start_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self._prev_key = self._current_key
        self._display_text = "..."
        self.capture_started.emit()
        self.setFocus()
        self.update()

    def _stop_capture(self, commit):
        if not self._capturing:
            return
        self._capturing = False
        if not commit:
            self._display_text = self._current_key
        self.capture_finished.emit()
        self.update()

    def set_key(self, key_name):
        self._current_key = key_name
        if not self._capturing:
            self._display_text = key_name
            self.update()

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
    hotkey_changed = pyqtSignal(str)
    hotkey_capture_started = pyqtSignal()
    hotkey_capture_finished = pyqtSignal()

    def __init__(self, parent=None, hotkey_name=DEFAULT_TRIGGER_KEY):
        super().__init__(parent)
        self.setFixedSize(*SETTINGS_PANEL_SIZE)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        self.header = DraggableHeader(self)
        self.header.setFixedHeight(SETTINGS_HEADER_HEIGHT)
        self.header.setGeometry(0, 0, self.width(), self.header.height())
        self.header.drag_delta.connect(self._handle_drag)

        self.close_button = QPushButton("X", self.header)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setStyleSheet(
            "background-color: transparent; color: #FFFFFF; font-weight: bold; border: none;"
        )
        self.close_button.clicked.connect(self.close_panel)
        self._place_close_button()

        label_y = self.header.height() + 30
        self.hotkey_label = QLabel("NANOverlay Key:", self)
        self.hotkey_label.setStyleSheet("color: #000000; font-size: 14px; font-weight: bold;")
        self.hotkey_label.adjustSize()
        self.hotkey_label.move(20, label_y)

        self.hotkey_input = HotkeyInput(hotkey_name, self)
        input_x = self.hotkey_label.x() + self.hotkey_label.width() + 12
        input_y = label_y - (self.hotkey_input.height() - self.hotkey_label.height()) // 2
        self.hotkey_input.move(input_x, input_y)
        self.hotkey_input.hotkey_selected.connect(self._hotkey_selected)
        self.hotkey_input.capture_started.connect(self.hotkey_capture_started)
        self.hotkey_input.capture_finished.connect(self.hotkey_capture_finished)

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
        label_y = self.header.height() + 30
        self.hotkey_label.move(20, label_y)
        input_x = self.hotkey_label.x() + self.hotkey_label.width() + 12
        input_y = label_y - (self.hotkey_input.height() - self.hotkey_label.height()) // 2
        self.hotkey_input.move(input_x, input_y)
        super().resizeEvent(event)

    def close_panel(self):
        self.hide()
        self.panel_closed.emit()

    def _handle_drag(self, delta):
        self.move(self.pos() + delta)

    def _hotkey_selected(self, key_name):
        self.hotkey_changed.emit(key_name)

    def set_hotkey_name(self, key_name):
        self.hotkey_input.set_key(key_name)

class Overlay(QWidget):
    def __init__(self, app_controller, hotkey_name):
        super().__init__()
        self._app_controller = app_controller
        self._hotkey_name = hotkey_name
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
        self._instruction_text = ""
        self.banner = QPixmap("ressources/banner.png")
        self.settings_button = SettingsButton(self)
        self.settings_panel = SettingsPanel(self, hotkey_name)
        self.settings_panel.hide()
        self.settings_panel.panel_closed.connect(self._on_settings_panel_closed)
        self.settings_panel.hotkey_changed.connect(self._on_hotkey_changed)
        self.settings_panel.hotkey_capture_started.connect(self._notify_hotkey_capture_start)
        self.settings_panel.hotkey_capture_finished.connect(self._notify_hotkey_capture_finish)
        self.settings_button.clicked.connect(self._handle_settings_button)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(FADE_DURATION_MS)
        self._fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_finished)
        self._is_fading_out = False
        self._skip_fade = False
        self.setWindowOpacity(0.0)
        self.show()
        self.activateWindow()
        self.setFocus()
        self._position_button()
        self._center_settings_panel()
        if load_panel_open_state():
            self._show_settings_panel()
        else:
            self.settings_panel.hide()
            self.settings_button.unlock_state()
        self.update()
        self._update_instruction_text()
        self._start_fade_in()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(23, 22, 22, 204))
        if self._instruction_text:
            font = QFont("Segoe UI", 12)
            painter.setFont(font)
            painter.setPen(QColor("#FFFFFF"))
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(self._instruction_text)
            text_x = (self.width() - text_width) // 2
            text_y = metrics.ascent() + 5
            painter.drawText(text_x, text_y, self._instruction_text)
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

    def _update_instruction_text(self):
        self._instruction_text = f"Press {self._hotkey_name} or ESC to minimise NANOverlay"
        self.update()

    def _handle_settings_button(self):
        if self.settings_panel.isVisible():
            return
        self._show_settings_panel()
        save_panel_open_state(True)

    def _show_settings_panel(self):
        self._center_settings_panel()
        self.settings_panel.show()
        self.settings_panel.raise_()
        self.settings_button.lock_state("pressed")

    def _on_settings_panel_closed(self):
        self.settings_button.unlock_state()
        save_panel_open_state(False)

    def _on_hotkey_changed(self, key_name):
        if key_name == self._hotkey_name:
            return
        self._hotkey_name = key_name
        self.settings_panel.set_hotkey_name(key_name)
        self._update_instruction_text()
        if self._app_controller is not None:
            self._app_controller.apply_hotkey_change(key_name)

    def _center_settings_panel(self):
        x = (self.width() - self.settings_panel.width()) // 2
        y = (self.height() - self.settings_panel.height()) // 2
        self.settings_panel.move(x, y)

    def set_hotkey_name(self, key_name):
        if key_name == self._hotkey_name:
            return
        self._hotkey_name = key_name
        self.settings_panel.set_hotkey_name(key_name)
        self._update_instruction_text()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self._skip_fade:
            if not self._is_fading_out:
                event.ignore()
                self._is_fading_out = True
                self._start_fade_out()
                return
        self._skip_fade = False
        save_panel_open_state(self.settings_panel.isVisible())
        self.releaseKeyboard()
        QApplication.restoreOverrideCursor()
        if self._app_controller is not None:
            self._app_controller.set_hotkey_capture(False)
        self.deleteLater()
        super().closeEvent(event)

    def _start_fade_in(self):
        self._is_fading_out = False
        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _start_fade_out(self):
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_finished(self):
        if self._is_fading_out:
            self._is_fading_out = False
            self._skip_fade = True
            self.close()

    def _notify_hotkey_capture_start(self):
        if self._app_controller is not None:
            self._app_controller.set_hotkey_capture(True)

    def _notify_hotkey_capture_finish(self):
        if self._app_controller is not None:
            self._app_controller.set_hotkey_capture(False)

class AppWithGlobalKeyHandler(QApplication):
    request_toggle = pyqtSignal()
    request_close = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.overlay = None
        self.hotkey_name = load_hotkey_from_file()
        self._suspend_hotkey_listener = False
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()
        self.request_toggle.connect(self.toggle_overlay, Qt.QueuedConnection)
        self.request_close.connect(self._close_overlay, Qt.QueuedConnection)

    def on_key_press(self, key):
        if self._suspend_hotkey_listener:
            return
        try:
            if pynput_key_matches_hotkey(key, self.hotkey_name):
                self.request_toggle.emit()
        except Exception:
            pass

    def toggle_overlay(self):
        if self.overlay is None or not self.overlay.isVisible():
            self.overlay = Overlay(self, self.hotkey_name)
            self.overlay.destroyed.connect(self._clear_overlay)
        else:
            self.overlay.close()
            self.overlay = None

    def _clear_overlay(self, *args):
        self.overlay = None

    def _close_overlay(self):
        if self.overlay is not None:
            self.overlay.close()

    def apply_hotkey_change(self, key_name):
        normalized = save_hotkey_to_file(key_name)
        if normalized == self.hotkey_name:
            return
        self.hotkey_name = normalized
        if self.overlay is not None:
            self.overlay.set_hotkey_name(normalized)

    def set_hotkey_capture(self, active):
        self._suspend_hotkey_listener = active

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