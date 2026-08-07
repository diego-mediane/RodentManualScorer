import csv
import json
import logging
import os
import sys
import time
from copy import deepcopy
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import pandas as pd
from PyQt5.QtCore import QEvent, QMutex, QSettings, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QKeySequence, QPainter, QPalette, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

WINDOWS_MODE = False

logging.basicConfig(
    filename='behaviour_scoring_log.txt',
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
)

GLOBAL_STYLE = """
QWidget { background-color: #1e1e1e; color: #f0f0f0; font-size: 13px; }
QMainWindow { background-color: #1e1e1e; }
QLabel { color: #f0f0f0; background: transparent; }
QMenuBar { background-color: #2a2a2a; color: #f0f0f0; }
QMenuBar::item { background: transparent; padding: 5px 12px; }
QMenuBar::item:selected { background: #3d6fb4; color: #ffffff; }
QMenu { background-color: #2a2a2a; color: #f0f0f0; border: 1px solid #555555; }
QMenu::item { padding: 5px 24px; }
QMenu::item:selected { background-color: #3d6fb4; color: #ffffff; }
QGroupBox { color: #f0f0f0; border: 1px solid #5a5a5a; border-radius: 8px; margin-top: 18px; padding-top: 10px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 6px; color: #9ecbff; }
QCheckBox, QRadioButton { color: #f0f0f0; spacing: 7px; background: transparent; }
QComboBox, QLineEdit { background-color: #333333; color: #f0f0f0; border: 1px solid #777777; border-radius: 5px; padding: 5px; }
QComboBox QAbstractItemView { background-color: #333333; color: #f0f0f0; selection-background-color: #3d6fb4; }
QPushButton { background-color: #4a4a4a; color: #ffffff; border: 1px solid #777777; border-radius: 7px; padding: 6px 10px; }
QPushButton:hover { background-color: #606060; }
QPushButton:pressed { background-color: #3d6fb4; }
QSlider::groove:horizontal { height: 6px; background: #555555; border-radius: 3px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #9ecbff; border-radius: 7px; }
QTableWidget, QListWidget, QTextBrowser { background-color: #252525; color: #f0f0f0; border: 1px solid #555555; }
QHeaderView::section { background-color: #444444; color: #ffffff; padding: 4px; border: 1px solid #555555; }
QToolTip { background-color: #f5f5f5; color: #111111; border: 1px solid #777777; padding: 4px; }
"""

MODIFIER_MASK = int(Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
RESERVED_KEYS = {
    int(Qt.Key_Space),
    int(Qt.Key_P),
    int(Qt.Key_F1),
    int(Qt.Key_F11),
}


def clamp(value, low, high):
    return max(low, min(high, value))


def combined_key_from_event(event):
    return int(event.key()) | (int(event.modifiers()) & MODIFIER_MASK)


def parse_time(value):
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass
    parts = text.split(':')
    try:
        nums = [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f'Invalid time value: {value}') from exc
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 1:
        return nums[0]
    raise ValueError(f'Invalid time value: {value}')


def format_time(seconds):
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours:
        return f'{hours:02d}:{minutes:02d}:{secs:06.3f}'
    return f'{minutes:02d}:{secs:06.3f}'


def frame_to_qimage(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()


def open_capture(path):
    backends = []
    if WINDOWS_MODE and hasattr(cv2, 'CAP_FFMPEG'):
        backends.append(cv2.CAP_FFMPEG)
    backends.append(None)
    for backend in backends:
        cap = cv2.VideoCapture(path) if backend is None else cv2.VideoCapture(path, backend)
        if cap.isOpened():
            return cap
        cap.release()
    return None


class VideoThread(QThread):
    frame_ready = pyqtSignal(QImage, int)
    video_ended = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, path, fps, total_frames, parent=None):
        super().__init__(parent)
        self.path = path
        self.fps = max(float(fps), 0.001)
        self.total_frames = max(int(total_frames), 1)
        self.playback_speed = 1.0
        self.displayed_frame = 0
        self._running = True
        self._paused = True
        self._seek_target = 0
        self._seek_pending = True
        self._lock = Lock()

    def set_speed(self, speed):
        with self._lock:
            self.playback_speed = max(0.05, float(speed))

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def seek(self, frame_index):
        with self._lock:
            self._seek_target = clamp(int(frame_index), 0, self.total_frames - 1)
            self._seek_pending = True

    def stop(self):
        with self._lock:
            self._running = False
        self.wait(2000)

    def is_paused(self):
        with self._lock:
            return self._paused

    def run(self):
        cap = open_capture(self.path)
        if cap is None:
            self.error.emit('Could not open the video file.')
            return
        try:
            while True:
                with self._lock:
                    if not self._running:
                        break
                    paused = self._paused
                    seek_pending = self._seek_pending
                    seek_target = self._seek_target
                    if seek_pending:
                        self._seek_pending = False
                    speed = self.playback_speed
                if seek_pending:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, seek_target)
                    ok, frame = cap.read()
                    if ok:
                        self.displayed_frame = seek_target
                        self.frame_ready.emit(frame_to_qimage(frame), seek_target)
                    else:
                        self.error.emit('Could not seek to the requested frame.')
                    continue
                if paused:
                    self.msleep(10)
                    continue
                started = time.perf_counter()
                ok, frame = cap.read()
                if not ok:
                    with self._lock:
                        self._paused = True
                    self.video_ended.emit()
                    continue
                frame_no = int(round(cap.get(cv2.CAP_PROP_POS_FRAMES))) - 1
                frame_no = clamp(frame_no, 0, self.total_frames - 1)
                self.displayed_frame = frame_no
                self.frame_ready.emit(frame_to_qimage(frame), frame_no)
                delay = max(0.0, (1.0 / (self.fps * speed)) - (time.perf_counter() - started))
                if delay:
                    self.msleep(max(1, int(delay * 1000)))
        except Exception as exc:
            logging.exception('Video thread failed')
            self.error.emit(str(exc))
        finally:
            cap.release()


class TimelineWidget(QWidget):
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = []
        self.total_duration = 1.0
        self.current_time = 0.0
        self.phase_colors = {'Default Phase': QColor('#ffffff')}
        self.setMinimumHeight(44)
        self.setMaximumHeight(60)
        self.setCursor(Qt.PointingHandCursor)

    def set_duration(self, duration):
        self.total_duration = max(float(duration), 0.001)
        self.update()

    def update_events(self, events):
        self.events = list(events or [])
        self.update()

    def set_phase_colors(self, phase_colors):
        self.phase_colors = {name: QColor(colour) if not isinstance(colour, QColor) else QColor(colour) for name, colour in (phase_colors or {}).items()}
        self.update()

    def set_current_time(self, value):
        self.current_time = clamp(float(value), 0.0, self.total_duration)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.width() > 0:
            fraction = clamp(event.x() / self.width(), 0.0, 1.0)
            self.seek_requested.emit(fraction * self.total_duration)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor('#2e2e2e'))
        h = max(5, rect.height() // 3)
        y = (rect.height() - h) // 2
        for item in self.events:
            start = clamp(float(item.get('start_time', 0.0)), 0.0, self.total_duration)
            end = clamp(float(item.get('end_time', start)), start, self.total_duration)
            x1 = (start / self.total_duration) * rect.width()
            x2 = (end / self.total_duration) * rect.width()
            phase = item.get('phase', 'Default Phase')
            colour = self.phase_colors.get(phase, QColor('#ffffff'))
            painter.fillRect(int(x1), y, max(1, int(x2 - x1)), h, colour)
        x = int((self.current_time / self.total_duration) * rect.width())
        pen = QPen(QColor('#ffffff'))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(x, 0, x, rect.height())
        painter.end()


class HistoryPanel(QListWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('History Panel')
        self.resize(420, 520)

    def add_action(self, text):
        self.addItem(text)
        self.scrollToBottom()


class Configuration:
    def __init__(self):
        self.settings = QSettings('BehaviourScoringApp', 'Settings')

    def load_settings(self):
        try:
            if not self.settings.contains('scoring_keys'):
                return {}
            raw = json.loads(self.settings.value('scoring_keys'))
            result = {}
            for name, value in raw.items():
                try:
                    if value is not None and int(value) != -1:
                        result[str(name)] = int(value)
                except Exception:
                    pass
            return result
        except Exception:
            logging.exception('Could not load key settings')
            return {}

    def save_settings(self, scoring_keys):
        clean = {str(name): int(key) for name, key in scoring_keys.items() if key is not None}
        self.settings.setValue('scoring_keys', json.dumps(clean))


class AssignKeyDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Assign Keys and Behaviours')
        self.setMinimumSize(650, 520)
        self.behaviour_keys = dict(parent.scoring_keys)
        self.current_behaviour = None
        self.waiting_for_key = False
        outer = QVBoxLayout(self)
        self.instructions = QLabel("Enter a behaviour name, click 'Add & Assign', then press its key.")
        outer.addWidget(self.instructions)
        add_row = QHBoxLayout()
        self.behaviour_input = QLineEdit()
        self.behaviour_input.setPlaceholderText('Enter behaviour name')
        add_row.addWidget(self.behaviour_input, 1)
        add_button = QPushButton('Add & Assign')
        add_button.clicked.connect(self.add_and_assign)
        add_row.addWidget(add_button)
        outer.addLayout(add_row)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Behaviour', 'Key'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.rename_selected)
        outer.addWidget(self.table)
        actions = QHBoxLayout()
        for label, slot in (
            ('Reassign Key', self.reassign_selected),
            ('Clear Key', self.clear_selected),
            ('Rename', self.rename_selected),
            ('Remove', self.remove_selected),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            actions.addWidget(button)
        actions.addStretch()
        outer.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.setFocusPolicy(Qt.StrongFocus)
        self.refresh()

    def selected_behaviour(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.text() if item else None

    def refresh(self):
        self.table.setRowCount(0)
        for name, key in self.behaviour_keys.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(QKeySequence(key).toString() if key is not None else ''))

    def add_and_assign(self):
        name = self.behaviour_input.text().strip()
        if not name:
            QMessageBox.warning(self, 'Input Error', 'Please enter a behaviour name.')
            return
        if name in self.behaviour_keys:
            QMessageBox.warning(self, 'Duplicate Name', 'That behaviour already exists.')
            return
        self.behaviour_keys[name] = None
        self.current_behaviour = name
        self.waiting_for_key = True
        self.instructions.setText(f"Press the key for '{name}'.")
        self.behaviour_input.clear()
        self.refresh()
        self.setFocus()

    def reassign_selected(self):
        name = self.selected_behaviour()
        if not name:
            return
        self.current_behaviour = name
        self.waiting_for_key = True
        self.instructions.setText(f"Press the new key for '{name}'.")
        self.setFocus()

    def clear_selected(self):
        name = self.selected_behaviour()
        if name:
            self.behaviour_keys[name] = None
            self.refresh()

    def rename_selected(self):
        name = self.selected_behaviour()
        if not name:
            return
        new_name, ok = QInputDialog.getText(self, 'Rename Behaviour', 'New name:', text=name)
        new_name = new_name.strip()
        if ok and new_name and (new_name == name or new_name not in self.behaviour_keys):
            key = self.behaviour_keys.pop(name)
            self.behaviour_keys[new_name] = key
            self.refresh()

    def remove_selected(self):
        name = self.selected_behaviour()
        if name:
            self.behaviour_keys.pop(name, None)
            self.refresh()

    def keyPressEvent(self, event):
        if self.waiting_for_key and not event.isAutoRepeat():
            if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
                return
            key = combined_key_from_event(event)
            modifiers = int(event.modifiers()) & MODIFIER_MASK
            primary = int(event.key())
            command = bool(modifiers & int(Qt.ControlModifier | Qt.MetaModifier))
            reserved_command = command and primary in {
                int(Qt.Key_O), int(Qt.Key_L), int(Qt.Key_S), int(Qt.Key_E),
                int(Qt.Key_N), int(Qt.Key_Q), int(Qt.Key_T), int(Qt.Key_Z), int(Qt.Key_Y),
            }
            if (primary in RESERVED_KEYS and modifiers == 0) or reserved_command:
                QMessageBox.warning(self, 'Reserved Key', 'That key combination is reserved by the application. Use another key or key combination.')
                return
            existing = next((name for name, value in self.behaviour_keys.items() if value == key and name != self.current_behaviour), None)
            if existing:
                answer = QMessageBox.question(
                    self,
                    'Key Already Assigned',
                    f"'{QKeySequence(key).toString()}' is assigned to '{existing}'. Reassign it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    return
                self.behaviour_keys[existing] = None
            self.behaviour_keys[self.current_behaviour] = key
            self.waiting_for_key = False
            self.instructions.setText('Assignment saved. Add another behaviour or press OK.')
            self.refresh()
            return
        super().keyPressEvent(event)

    def accept(self):
        self.behaviour_keys = {name: key for name, key in self.behaviour_keys.items() if key is not None}
        super().accept()


class LiveScoringPanel(QGroupBox):
    def __init__(self):
        super().__init__('Live Scoring')
        self.rows = {}
        outer = QVBoxLayout(self)
        self.status = QLabel('● Idle')
        outer.addWidget(self.status)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        holder = QWidget()
        self.rows_layout = QVBoxLayout(holder)
        self.rows_layout.setSpacing(6)
        self.rows_layout.addStretch()
        self.scroll.setWidget(holder)
        outer.addWidget(self.scroll)

    def set_status(self, scoring):
        if scoring:
            self.status.setText('● SCORING')
            self.status.setStyleSheet('color: #39d353; font-weight: bold;')
        else:
            self.status.setText('● Idle')
            self.status.setStyleSheet('color: #aaaaaa; font-weight: bold;')

    def rebuild(self, scoring_keys, time_spent, frequency_counts):
        for row in self.rows.values():
            row['frame'].setParent(None)
            row['frame'].deleteLater()
        self.rows = {}
        insert_at = self.rows_layout.count() - 1
        for name, key in scoring_keys.items():
            frame = QFrame()
            frame.setStyleSheet('QFrame { border: 1px solid #555; border-radius: 6px; background: #2a2a2a; }')
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(8, 6, 8, 6)
            title = QLabel(f'{name} [ {QKeySequence(key).toString()} ]')
            title.setStyleSheet('font-weight: bold; border: none;')
            stats = QLabel('')
            stats.setStyleSheet('border: none; color: #cccccc;')
            live = QLabel('')
            live.setStyleSheet('border: none; color: #39d353; font-weight: bold;')
            layout.addWidget(title)
            layout.addWidget(stats)
            layout.addWidget(live)
            self.rows_layout.insertWidget(insert_at, frame)
            insert_at += 1
            self.rows[name] = {'frame': frame, 'title': title, 'stats': stats, 'live': live}
            self.update_stats(name, key, time_spent.get(name, 0.0), frequency_counts.get(name, 0))

    def update_stats(self, name, key, total, count):
        row = self.rows.get(name)
        if not row:
            return
        row['title'].setText(f'{name} [ {QKeySequence(key).toString()} ]')
        row['stats'].setText(f'Time: {format_time(total)}   Count: {count}')

    def set_active(self, name, active):
        row = self.rows.get(name)
        if not row:
            return
        if active:
            row['frame'].setStyleSheet('QFrame { border: 2px solid #39d353; border-radius: 6px; background: #223529; }')
        else:
            row['frame'].setStyleSheet('QFrame { border: 1px solid #555; border-radius: 6px; background: #2a2a2a; }')
            row['live'].setText('')

    def set_live_elapsed(self, name, elapsed):
        row = self.rows.get(name)
        if row:
            row['live'].setText(f'▶ recording +{max(0.0, elapsed):0.2f}s')


class TutorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Tutorial — Rodent Manual Scorer')
        self.setMinimumSize(650, 560)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setHtml('''
        <h2>Rodent Manual Scorer</h2>
        <h3>1. Load a video</h3><p>Use <b>File → Load Video</b> or drag a supported video into the window.</p>
        <h3>2. Assign behaviours</h3><p>Click <b>Assign Keys</b>, create each behaviour and press the key combination you want to use.</p>
        <h3>3. Play and score</h3><p>Press <b>Space</b> to play. Hold a behaviour key while that behaviour occurs and release it when the bout ends. If the video reaches its end while a key is still held, the bout is automatically closed at the exact video duration.</p>
        <h3>4. Phases</h3><p>Press <b>P</b> or use <b>Start New Phase</b> to label a new phase.</p>
        <h3>5. Sessions</h3><p>Use <b>New Session</b> for another scoring pass. You can start fresh or copy the current pass.</p>
        <h3>6. Correct mistakes</h3><p>Use <b>Ctrl/Command+Z</b> to undo and <b>Ctrl/Command+Y</b> to redo.</p>
        <h3>7. Save</h3><p>Save CSV or export an Excel workbook. The application also writes a recovery CSV every five minutes.</p>
        ''')
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class NewSessionDialog(QDialog):
    def __init__(self, parent=None, default_name='Session'):
        super().__init__(parent)
        self.setWindowTitle('New Session')
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit(default_name)
        form.addRow('Session name:', self.name_input)
        layout.addLayout(form)
        self.fresh = QRadioButton('Start from scratch (empty scores, rewind to 0)')
        self.copy = QRadioButton('Continue from a copy of the current session')
        self.fresh.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.fresh)
        group.addButton(self.copy)
        layout.addWidget(self.fresh)
        layout.addWidget(self.copy)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def session_name(self):
        return self.name_input.text().strip()

    def mode(self):
        return 'copy' if self.copy.isChecked() else 'fresh'


class BehaviourScoringApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Rodent Manual Scorer')
        self.resize(1400, 820)
        self.video_path = ''
        self.fps = 0.0
        self.total_frames = 0
        self.total_duration = 0.0
        self.video_thread = None
        self.playback_speed = 1.0
        self.last_video_image = None
        self.scoring = False
        self.key_states = {}
        self.last_key_times = {}
        self.behaviour_events = []
        self.time_spent = {}
        self.frequency_counts = {}
        self.undo_stack = []
        self.redo_stack = []
        self.current_phase = 'Default Phase'
        self.phase_colors = {'Default Phase': QColor('#ffffff')}
        self.annotations = []
        self.sessions = []
        self.active_session_index = -1
        self.session_counter = 0
        self.suppress_session_switch = False
        self.slider_user_dragging = False
        self.slider_resume_after_seek = False
        self.is_fullscreen = False
        self.history_panel = HistoryPanel()
        self.config = Configuration()
        self.scoring_keys = self.config.load_settings()
        QApplication.instance().setStyleSheet(GLOBAL_STYLE)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor('#1e1e1e'))
        self.setPalette(palette)
        self.init_ui()
        QApplication.instance().installEventFilter(self)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave_session)
        self.autosave_timer.start(300000)
        self.scoring_timer = QTimer(self)
        self.scoring_timer.timeout.connect(self.update_live_timers)
        self.scoring_timer.start(40)
        self.create_initial_session()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        left = QVBoxLayout()
        right = QVBoxLayout()
        main.addLayout(left, 3)
        main.addLayout(right, 1)
        self.create_menu()
        self.video_label = QLabel('Load a video to begin')
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 420)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setStyleSheet('background: #101010; border: 1px solid #444; font-size: 16px;')
        left.addWidget(self.video_label, 1)
        self.timeline = TimelineWidget()
        self.timeline.seek_requested.connect(self.seek_to_time)
        left.addWidget(self.timeline)
        slider_row = QHBoxLayout()
        self.time_label = QLabel('00:00.000 / 00:00.000')
        slider_row.addWidget(self.time_label)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderPressed.connect(self.slider_pressed)
        self.position_slider.sliderReleased.connect(self.slider_released)
        slider_row.addWidget(self.position_slider, 1)
        left.addLayout(slider_row)
        controls = QHBoxLayout()
        self.play_button = QPushButton('Play')
        self.play_button.clicked.connect(self.toggle_playback)
        controls.addWidget(self.play_button)
        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop_video)
        controls.addWidget(self.stop_button)
        controls.addWidget(QLabel('Speed:'))
        self.speed_combo = QComboBox()
        for speed in (0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 8.0):
            self.speed_combo.addItem(f'{speed:g}x', speed)
        self.speed_combo.setCurrentText('1x')
        self.speed_combo.currentIndexChanged.connect(self.change_speed)
        controls.addWidget(self.speed_combo)
        controls.addStretch()
        left.addLayout(controls)
        session_group = QGroupBox('Session')
        session_layout = QVBoxLayout(session_group)
        self.session_combo = QComboBox()
        self.session_combo.currentIndexChanged.connect(self.switch_session)
        session_layout.addWidget(self.session_combo)
        new_session_button = QPushButton('New Session')
        new_session_button.clicked.connect(self.new_session)
        session_layout.addWidget(new_session_button)
        right.addWidget(session_group)
        assign_button = QPushButton('Assign Keys')
        assign_button.clicked.connect(self.open_assign_dialog)
        right.addWidget(assign_button)
        self.live_panel = LiveScoringPanel()
        right.addWidget(self.live_panel, 1)
        phase_group = QGroupBox('Phase')
        phase_layout = QVBoxLayout(phase_group)
        self.phase_label = QLabel('Default Phase')
        phase_layout.addWidget(self.phase_label)
        phase_button = QPushButton('Start New Phase')
        phase_button.clicked.connect(self.start_new_phase)
        phase_layout.addWidget(phase_button)
        right.addWidget(phase_group)
        summary_button = QPushButton('Show Time Spent')
        summary_button.clicked.connect(self.show_time_spent)
        right.addWidget(summary_button)
        tutorial_button = QPushButton('Tutorial (F1)')
        tutorial_button.clicked.connect(self.show_tutorial)
        right.addWidget(tutorial_button)
        self.live_panel.rebuild(self.scoring_keys, self.time_spent, self.frequency_counts)
        self.setAcceptDrops(True)

    def create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        self.add_action(file_menu, 'Load Video', 'Ctrl+O', self.upload_video)
        self.add_action(file_menu, 'Load Scoring CSV', 'Ctrl+L', self.load_scoring_csv)
        self.add_action(file_menu, 'Save Scoring CSV', 'Ctrl+S', self.save_scoring_csv)
        self.add_action(file_menu, 'Export Excel', 'Ctrl+E', self.export_excel)
        self.add_action(file_menu, 'New Session', 'Ctrl+N', self.new_session)
        self.add_action(file_menu, 'Exit', 'Ctrl+Q', self.close)
        edit_menu = menubar.addMenu('Edit')
        self.add_action(edit_menu, 'Undo Last', QKeySequence.Undo, self.undo_last_event)
        self.add_action(edit_menu, 'Redo', QKeySequence.Redo, self.redo_last_event)
        view_menu = menubar.addMenu('View')
        self.add_action(view_menu, 'Show History', None, self.toggle_history_panel)
        self.add_action(view_menu, 'Show Time Spent', 'Ctrl+T', self.show_time_spent)
        self.add_action(view_menu, 'Toggle Fullscreen', 'F11', self.toggle_fullscreen)
        help_menu = menubar.addMenu('Help')
        self.add_action(help_menu, 'Tutorial', 'F1', self.show_tutorial)

    def add_action(self, menu, text, shortcut, slot):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def create_initial_session(self):
        self.sessions = [self.empty_session('Session 1')]
        self.active_session_index = 0
        self.session_counter = 1
        self.refresh_session_combo()
        self.restore_session(self.sessions[0])

    def empty_session(self, name):
        return {
            'name': name,
            'behaviour_events': [],
            'time_spent': {},
            'frequency_counts': {},
            'undo_stack': [],
            'redo_stack': [],
            'current_phase': 'Default Phase',
            'phase_colors': {'Default Phase': '#ffffff'},
            'annotations': [],
            'video_time': 0.0,
        }

    def snapshot_current_session(self):
        if self.active_session_index < 0 or self.active_session_index >= len(self.sessions):
            return
        session = self.sessions[self.active_session_index]
        session.update({
            'behaviour_events': deepcopy(self.behaviour_events),
            'time_spent': dict(self.time_spent),
            'frequency_counts': dict(self.frequency_counts),
            'undo_stack': deepcopy(self.undo_stack),
            'redo_stack': deepcopy(self.redo_stack),
            'current_phase': self.current_phase,
            'phase_colors': {name: colour.name() for name, colour in self.phase_colors.items()},
            'annotations': deepcopy(self.annotations),
            'video_time': self.current_video_time(),
        })

    def restore_session(self, session):
        self._clear_active_bouts()
        self.behaviour_events = deepcopy(session.get('behaviour_events', []))
        self.time_spent = dict(session.get('time_spent', {}))
        self.frequency_counts = dict(session.get('frequency_counts', {}))
        self.undo_stack = deepcopy(session.get('undo_stack', []))
        self.redo_stack = deepcopy(session.get('redo_stack', []))
        self.current_phase = session.get('current_phase', 'Default Phase')
        self.phase_colors = {name: QColor(value) for name, value in session.get('phase_colors', {'Default Phase': '#ffffff'}).items()}
        self.annotations = deepcopy(session.get('annotations', []))
        self.phase_label.setText(self.current_phase)
        self.refresh_statistics()
        self.timeline.set_phase_colors(self.phase_colors)
        self.timeline.update_events(self.behaviour_events)
        if self.video_thread and self.fps:
            self.seek_to_time(float(session.get('video_time', 0.0)), resume=False)

    def refresh_session_combo(self):
        self.suppress_session_switch = True
        self.session_combo.clear()
        for session in self.sessions:
            self.session_combo.addItem(session['name'])
        if self.active_session_index >= 0:
            self.session_combo.setCurrentIndex(self.active_session_index)
        self.suppress_session_switch = False

    def new_session(self):
        self._finalize_active_bouts()
        self.pause_video(finalize=False)
        self.snapshot_current_session()
        self.session_counter += 1
        dialog = NewSessionDialog(self, f'Session {self.session_counter}')
        if dialog.exec_() != QDialog.Accepted:
            return
        name = dialog.session_name() or f'Session {self.session_counter}'
        if dialog.mode() == 'copy':
            session = deepcopy(self.sessions[self.active_session_index])
            session['name'] = name
            session['undo_stack'] = []
            session['redo_stack'] = []
        else:
            session = self.empty_session(name)
        self.sessions.append(session)
        self.active_session_index = len(self.sessions) - 1
        self.refresh_session_combo()
        self.restore_session(session)
        self.history_panel.add_action(f'Created session: {name}')

    def switch_session(self, index):
        if self.suppress_session_switch or index < 0 or index == self.active_session_index:
            return
        self._finalize_active_bouts()
        self.pause_video(finalize=False)
        self.snapshot_current_session()
        self.active_session_index = index
        self.restore_session(self.sessions[index])
        self.history_panel.add_action(f"Switched to session: {self.sessions[index]['name']}")

    def upload_video(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open Video', '', 'Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)')
        if path:
            self.load_video(path)

    def reset_scoring_for_new_video(self):
        self._clear_active_bouts()
        self.sessions = [self.empty_session('Session 1')]
        self.active_session_index = 0
        self.session_counter = 1
        self.refresh_session_combo()
        self.restore_session(self.sessions[0])
        self.history_panel.clear()

    def load_video(self, path):
        self._clear_active_bouts()
        self.pause_video(finalize=False)
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread = None
        cap = open_capture(path)
        if cap is None:
            QMessageBox.warning(self, 'Video Error', 'Could not open that video.')
            return
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0:
            fps, ok = QInputDialog.getDouble(self, 'Frame rate', 'Video FPS:', 30.0, 0.1, 1000.0, 3)
            if not ok:
                cap.release()
                return
        if total_frames <= 0:
            cap.release()
            QMessageBox.warning(self, 'Video Error', 'Could not determine the number of video frames.')
            return
        cap.release()
        self.video_path = path
        self.fps = fps
        self.total_frames = total_frames
        self.total_duration = total_frames / fps
        self.timeline.set_duration(self.total_duration)
        self.position_slider.setRange(0, total_frames - 1)
        self.time_label.setText(f'{format_time(0)} / {format_time(self.total_duration)}')
        self.video_thread = VideoThread(path, fps, total_frames, self)
        self.video_thread.frame_ready.connect(self.display_frame)
        self.video_thread.video_ended.connect(self.on_video_end)
        self.video_thread.error.connect(self.video_error)
        self.video_thread.set_speed(self.playback_speed)
        self.video_thread.start()
        self.reset_scoring_for_new_video()
        self.setWindowTitle(f'Rodent Manual Scorer — {os.path.basename(path)}')
        self.history_panel.add_action(f'Loaded video: {os.path.basename(path)}')

    def display_frame(self, image, frame_index):
        self.last_video_image = image
        self.render_video_image()
        current = min(frame_index / self.fps if self.fps else 0.0, self.total_duration)
        if not self.slider_user_dragging:
            self.position_slider.blockSignals(True)
            self.position_slider.setValue(frame_index)
            self.position_slider.blockSignals(False)
        self.timeline.set_current_time(current)
        self.time_label.setText(f'{format_time(current)} / {format_time(self.total_duration)}')

    def render_video_image(self):
        if self.last_video_image is None:
            return
        pixmap = QPixmap.fromImage(self.last_video_image)
        self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def current_video_time(self):
        if self.video_thread and self.fps:
            return clamp(self.video_thread.displayed_frame / self.fps, 0.0, self.total_duration)
        return 0.0

    def toggle_playback(self):
        if not self.video_thread:
            return
        if self.scoring:
            self.pause_video()
        else:
            self.play_video()

    def play_video(self):
        if not self.video_thread:
            return
        if self.video_thread.displayed_frame >= self.total_frames - 1:
            self.seek_to_time(0.0, resume=False)
        self.scoring = True
        self.video_thread.resume()
        self.play_button.setText('Pause')
        self.live_panel.set_status(True)

    def pause_video(self, finalize=True):
        if finalize:
            self._finalize_active_bouts()
        if self.video_thread:
            self.video_thread.pause()
        self.scoring = False
        self.play_button.setText('Play')
        self.live_panel.set_status(False)

    def stop_video(self):
        self._finalize_active_bouts()
        self.pause_video(finalize=False)
        self.seek_to_time(0.0, resume=False)
        self.history_panel.add_action('Stopped video')

    def on_video_end(self):
        self._finalize_active_bouts(self.total_duration)
        self.scoring = False
        self.play_button.setText('Play')
        self.live_panel.set_status(False)
        self.timeline.set_current_time(self.total_duration)
        self.time_label.setText(f'{format_time(self.total_duration)} / {format_time(self.total_duration)}')
        if self.total_frames:
            self.position_slider.setValue(self.total_frames - 1)
        self.history_panel.add_action('Video reached the end')

    def seek_to_time(self, seconds, resume=None):
        if not self.video_thread or not self.fps:
            return
        self._finalize_active_bouts()
        was_playing = self.scoring
        self.pause_video(finalize=False)
        seconds = clamp(float(seconds), 0.0, self.total_duration)
        frame = min(int(round(seconds * self.fps)), self.total_frames - 1)
        self.video_thread.seek(frame)
        if resume is True or (resume is None and was_playing):
            QTimer.singleShot(30, self.play_video)

    def slider_pressed(self):
        self.slider_user_dragging = True
        self.slider_resume_after_seek = self.scoring
        self._finalize_active_bouts()
        self.pause_video(finalize=False)

    def slider_released(self):
        self.slider_user_dragging = False
        if self.fps:
            self.seek_to_time(self.position_slider.value() / self.fps, resume=self.slider_resume_after_seek)

    def change_speed(self):
        speed = float(self.speed_combo.currentData() or 1.0)
        self.playback_speed = speed
        if self.video_thread:
            self.video_thread.set_speed(speed)

    def _behaviour_for_key(self, combined_key):
        return next((name for name, key in self.scoring_keys.items() if int(key) == int(combined_key)), None)

    def _record_active_bout(self, combined_key, end_time):
        state = self.key_states.pop(combined_key, None)
        start_time = self.last_key_times.pop(combined_key, None)
        behaviour = state['behaviour'] if isinstance(state, dict) else self._behaviour_for_key(combined_key)
        if behaviour:
            self.live_panel.set_active(behaviour, False)
        if start_time is None or not behaviour:
            return
        start_time = clamp(float(start_time), 0.0, self.total_duration)
        end_time = clamp(float(end_time), start_time, self.total_duration)
        event = {
            'phase': self.current_phase,
            'behaviour': behaviour,
            'start_time': start_time,
            'end_time': end_time,
            'duration': max(0.0, end_time - start_time),
        }
        self.behaviour_events.append(event)
        self.undo_stack.append(deepcopy(event))
        self.redo_stack.clear()
        self.recalculate_statistics()
        self.annotations.append(deepcopy(event))
        self.refresh_statistics()
        self.timeline.update_events(self.behaviour_events)
        self.history_panel.add_action(f'Added {behaviour}: {format_time(start_time)} to {format_time(end_time)}')
        self.snapshot_current_session()

    def _finalize_active_bouts(self, end_time=None):
        if not self.key_states:
            return
        if end_time is None:
            end_time = self.current_video_time()
        for combined_key in list(self.key_states.keys()):
            self._record_active_bout(combined_key, end_time)

    def _clear_active_bouts(self):
        for state in list(self.key_states.values()):
            if isinstance(state, dict) and state.get('behaviour'):
                self.live_panel.set_active(state['behaviour'], False)
        self.key_states.clear()
        self.last_key_times.clear()

    def update_live_timers(self):
        now = self.current_video_time()
        for key, state in list(self.key_states.items()):
            behaviour = state.get('behaviour') if isinstance(state, dict) else self._behaviour_for_key(key)
            start = self.last_key_times.get(key)
            if behaviour and start is not None:
                self.live_panel.set_live_elapsed(behaviour, now - start)

    def eventFilter(self, source, event):
        if event.type() not in (QEvent.KeyPress, QEvent.KeyRelease):
            return super().eventFilter(source, event)
        if QApplication.activeModalWidget() is not None:
            return super().eventFilter(source, event)
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            return super().eventFilter(source, event)
        if event.isAutoRepeat():
            return True
        if event.type() == QEvent.KeyPress:
            modifiers = int(event.modifiers()) & MODIFIER_MASK
            primary = int(event.key())
            if primary == int(Qt.Key_Space) and modifiers == 0:
                self.toggle_playback()
                return True
            if primary == int(Qt.Key_P) and modifiers == 0:
                if self.video_thread:
                    self.start_new_phase()
                return True
            command = bool(modifiers & int(Qt.ControlModifier | Qt.MetaModifier))
            if command and primary == int(Qt.Key_Z):
                if modifiers & int(Qt.ShiftModifier):
                    self.redo_last_event()
                else:
                    self.undo_last_event()
                return True
            if command and primary == int(Qt.Key_Y):
                self.redo_last_event()
                return True
            if self.scoring:
                combined = combined_key_from_event(event)
                behaviour = self._behaviour_for_key(combined)
                if behaviour and combined not in self.key_states:
                    self.key_states[combined] = {'base_key': primary, 'behaviour': behaviour}
                    self.last_key_times[combined] = self.current_video_time()
                    self.live_panel.set_active(behaviour, True)
                return behaviour is not None
        else:
            primary = int(event.key())
            active = [key for key, state in self.key_states.items() if isinstance(state, dict) and state.get('base_key') == primary]
            if active:
                end_time = self.current_video_time()
                for key in active:
                    self._record_active_bout(key, end_time)
                return True
        return super().eventFilter(source, event)

    def open_assign_dialog(self):
        self._finalize_active_bouts()
        was_playing = self.scoring
        self.pause_video(finalize=False)
        dialog = AssignKeyDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.scoring_keys = dict(dialog.behaviour_keys)
            self.config.save_settings(self.scoring_keys)
            self.refresh_statistics()
            self.history_panel.add_action('Updated behaviour key assignments')
        if was_playing:
            self.play_video()

    def start_new_phase(self):
        if not self.video_thread:
            return
        self._finalize_active_bouts()
        name, ok = QInputDialog.getText(self, 'New Phase', 'Phase name:')
        name = name.strip()
        if not ok or not name:
            return
        colour = QColorDialog.getColor(self.phase_colors.get(self.current_phase, QColor('#ffffff')), self, 'Phase colour')
        if not colour.isValid():
            return
        self.current_phase = name
        self.phase_colors[name] = colour
        self.timeline.set_phase_colors(self.phase_colors)
        self.phase_label.setText(name)
        self.history_panel.add_action(f'Started phase: {name}')
        self.snapshot_current_session()

    def recalculate_statistics(self):
        totals = {}
        counts = {}
        for event in self.behaviour_events:
            name = event.get('behaviour', '')
            if not name:
                continue
            totals[name] = totals.get(name, 0.0) + float(event.get('duration', 0.0))
            counts[name] = counts.get(name, 0) + 1
        self.time_spent = totals
        self.frequency_counts = counts

    def refresh_statistics(self):
        self.live_panel.rebuild(self.scoring_keys, self.time_spent, self.frequency_counts)
        for name, key in self.scoring_keys.items():
            self.live_panel.update_stats(name, key, self.time_spent.get(name, 0.0), self.frequency_counts.get(name, 0))

    def undo_last_event(self):
        self._finalize_active_bouts()
        if not self.behaviour_events:
            return
        event = self.behaviour_events.pop()
        self.redo_stack.append(deepcopy(event))
        if self.undo_stack:
            self.undo_stack.pop()
        self.recalculate_statistics()
        self.refresh_statistics()
        self.timeline.update_events(self.behaviour_events)
        self.seek_to_time(event.get('start_time', 0.0), resume=False)
        self.history_panel.add_action(f"Undid {event.get('behaviour', 'event')}")
        self.snapshot_current_session()

    def redo_last_event(self):
        self._finalize_active_bouts()
        if not self.redo_stack:
            return
        event = self.redo_stack.pop()
        self.behaviour_events.append(deepcopy(event))
        self.undo_stack.append(deepcopy(event))
        self.recalculate_statistics()
        self.refresh_statistics()
        self.timeline.update_events(self.behaviour_events)
        self.history_panel.add_action(f"Redid {event.get('behaviour', 'event')}")
        self.snapshot_current_session()

    def save_scoring_csv(self):
        self._finalize_active_bouts()
        path, _ = QFileDialog.getSaveFileName(self, 'Save Scoring CSV', '', 'CSV Files (*.csv)')
        if path:
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self.write_csv(path)
            QMessageBox.information(self, 'Saved', 'Scoring CSV saved successfully.')

    def write_csv(self, path):
        with open(path, 'w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.writer(handle)
            writer.writerow(['Phase', 'Behaviour', 'Start Time', 'End Time', 'Duration (s)'])
            for event in self.behaviour_events:
                writer.writerow([
                    event.get('phase', 'Default Phase'),
                    event.get('behaviour', ''),
                    format_time(event.get('start_time', 0.0)),
                    format_time(event.get('end_time', 0.0)),
                    f"{float(event.get('duration', 0.0)):.3f}",
                ])

    def load_scoring_csv(self):
        self._finalize_active_bouts()
        path, _ = QFileDialog.getOpenFileName(self, 'Open Scoring CSV', '', 'CSV Files (*.csv);;All Files (*)')
        if not path:
            return
        loaded = []
        try:
            with open(path, 'r', newline='', encoding='utf-8-sig') as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    behaviour = (row.get('Behaviour') or row.get('behaviour') or '').strip()
                    if not behaviour:
                        continue
                    phase = (row.get('Phase') or row.get('phase') or 'Default Phase').strip() or 'Default Phase'
                    start = parse_time(row.get('Start Time') or row.get('start_time') or row.get('Start') or 0)
                    end = parse_time(row.get('End Time') or row.get('end_time') or row.get('End') or start)
                    raw_duration = row.get('Duration (s)') or row.get('duration') or row.get('Duration')
                    duration = float(raw_duration) if raw_duration not in (None, '') else max(0.0, end - start)
                    loaded.append({
                        'phase': phase,
                        'behaviour': behaviour,
                        'start_time': float(start),
                        'end_time': float(end),
                        'duration': max(0.0, float(duration)),
                    })
        except Exception as exc:
            QMessageBox.warning(self, 'Load Error', f'Could not load the CSV:\n{exc}')
            return
        self._clear_active_bouts()
        self.behaviour_events = loaded
        self.undo_stack = []
        self.redo_stack = []
        self.annotations = deepcopy(loaded)
        phases = []
        for event in loaded:
            phase = event['phase']
            if phase not in phases:
                phases.append(phase)
        for phase in phases:
            self.phase_colors.setdefault(phase, QColor('#ffffff'))
        self.current_phase = phases[-1] if phases else 'Default Phase'
        self.phase_label.setText(self.current_phase)
        self.recalculate_statistics()
        self.refresh_statistics()
        self.timeline.set_phase_colors(self.phase_colors)
        self.timeline.update_events(self.behaviour_events)
        self.history_panel.clear()
        self.history_panel.add_action(f'Loaded scoring CSV: {os.path.basename(path)}')
        self.snapshot_current_session()
        QMessageBox.information(self, 'Loaded', 'Scoring CSV loaded successfully.')

    def export_excel(self):
        self._finalize_active_bouts()
        path, _ = QFileDialog.getSaveFileName(self, 'Export Excel', '', 'Excel Workbook (*.xlsx)')
        if not path:
            return
        if not path.lower().endswith('.xlsx'):
            path += '.xlsx'
        rows = []
        for event in self.behaviour_events:
            rows.append({
                'Phase': event.get('phase', 'Default Phase'),
                'Behaviour': event.get('behaviour', ''),
                'Start Time': format_time(event.get('start_time', 0.0)),
                'End Time': format_time(event.get('end_time', 0.0)),
                'Duration (s)': round(float(event.get('duration', 0.0)), 3),
            })
        detailed = pd.DataFrame(rows, columns=['Phase', 'Behaviour', 'Start Time', 'End Time', 'Duration (s)'])
        behaviours = list(dict.fromkeys(list(self.scoring_keys.keys()) + [event.get('behaviour', '') for event in self.behaviour_events if event.get('behaviour')]))
        summary = pd.DataFrame([
            {
                'Behaviour': name,
                'Total Time (s)': round(self.time_spent.get(name, 0.0), 3),
                'Count': self.frequency_counts.get(name, 0),
            }
            for name in behaviours
        ])
        engines = ['openpyxl', 'xlsxwriter'] if WINDOWS_MODE else ['xlsxwriter', 'openpyxl']
        last_error = None
        for engine in engines:
            try:
                with pd.ExcelWriter(path, engine=engine) as writer:
                    summary.to_excel(writer, sheet_name='Summary', index=False)
                    detailed.to_excel(writer, sheet_name='Detailed_Events', index=False)
                QMessageBox.information(self, 'Exported', 'Excel workbook exported successfully.')
                return
            except Exception as exc:
                last_error = exc
        QMessageBox.warning(self, 'Export Error', f'Could not export Excel:\n{last_error}')

    def autosave_session(self):
        if not self.behaviour_events:
            return
        try:
            directory = os.path.dirname(self.video_path) if self.video_path else os.getcwd()
            self.write_csv(os.path.join(directory, 'autosave_rms.csv'))
        except Exception:
            logging.exception('Autosave failed')

    def show_time_spent(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Time Spent')
        dialog.resize(520, 420)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(['Behaviour', 'Total time', 'Count'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        behaviours = list(dict.fromkeys(list(self.scoring_keys.keys()) + list(self.time_spent.keys())))
        for name in behaviours:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(format_time(self.time_spent.get(name, 0.0))))
            table.setItem(row, 2, QTableWidgetItem(str(self.frequency_counts.get(name, 0))))
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec_()

    def toggle_history_panel(self):
        if self.history_panel.isVisible():
            self.history_panel.hide()
        else:
            self.history_panel.show()
            self.history_panel.raise_()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.is_fullscreen = False
        else:
            self.showFullScreen()
            self.is_fullscreen = True

    def show_tutorial(self):
        TutorialDialog(self).exec_()

    def video_error(self, message):
        logging.error(message)
        QMessageBox.warning(self, 'Video Error', message)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if urls and Path(urls[0].toLocalFile()).suffix.lower() in {'.mp4', '.avi', '.mov', '.mkv'}:
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.load_video(urls[0].toLocalFile())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.render_video_image()
        if self.video_label.pixmap() and not self.video_label.pixmap().isNull():
            pass

    def closeEvent(self, event):
        self._finalize_active_bouts()
        self.snapshot_current_session()
        try:
            self.autosave_session()
        except Exception:
            pass
        if self.video_thread:
            self.video_thread.stop()
        self.history_panel.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Rodent Manual Scorer')
    window = BehaviourScoringApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()