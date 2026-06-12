import sys
import os
import time
import cv2
import json
import pandas as pd
import numpy as np
import logging
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout, QLabel,
    QFileDialog, QHBoxLayout, QMessageBox, QSlider, QComboBox, QDialog,
    QLineEdit, QFormLayout, QListWidget, QSizePolicy, QInputDialog, QAction,
    QCheckBox, QGroupBox, QColorDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialogButtonBox, QSpacerItem, QSizePolicy as QSzPolicy,
    QScrollArea, QFrame, QTextBrowser, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QEvent, QRectF,
    QMutex, QMutexLocker, pyqtSlot, QSettings
)
from PyQt5.QtGui import QPalette, QColor, QPainter, QImage, QKeySequence, QPen

logging.basicConfig(
    filename='behaviour_scoring_log.txt',
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s'
)

NL = '\n'

# ---------------------------------------------------------------------------
# Global dark theme. The original app set only a dark window background while
# relying on a handful of per-widget stylesheets for light text. Any widget
# without an explicit colour (menus, group boxes, checkboxes, combo popups,
# message/input dialogs, tooltips) fell back to dark-on-dark and was unreadable.
# This single stylesheet guarantees readable, consistent text everywhere.
# ---------------------------------------------------------------------------
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

QGroupBox {
    color: #f0f0f0; border: 1px solid #5a5a5a; border-radius: 8px;
    margin-top: 18px; padding-top: 10px; font-size: 13px; font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 10px; padding: 0 6px; color: #9ecbff;
}

QCheckBox { color: #f0f0f0; spacing: 7px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked { border: 1px solid #888888; background: #2a2a2a; border-radius: 3px; }
QCheckBox::indicator:checked { border: 1px solid #3d6fb4; background: #3d6fb4; border-radius: 3px; }

QRadioButton { color: #f0f0f0; spacing: 7px; background: transparent; }

QComboBox {
    background-color: #333333; color: #f0f0f0; border: 1px solid #888888;
    border-radius: 5px; padding: 5px; min-width: 96px;
}
QComboBox:hover { background-color: #444444; }
QComboBox QAbstractItemView {
    background-color: #2a2a2a; color: #f0f0f0; border: 1px solid #555555;
    selection-background-color: #3d6fb4; selection-color: #ffffff;
}

QLineEdit {
    background-color: #2a2a2a; color: #f0f0f0; border: 1px solid #888888;
    border-radius: 4px; padding: 5px; selection-background-color: #3d6fb4;
}

QListWidget { background-color: #2e2e2e; color: #f0f0f0; border: 1px solid #555555; }
QListWidget::item:selected { background-color: #3d6fb4; color: #ffffff; }

QTableWidget { background-color: #2e2e2e; color: #f0f0f0; gridline-color: #555555; }
QTableWidget::item:selected { background-color: #3d6fb4; color: #ffffff; }
QHeaderView::section { background-color: #555555; color: #f0f0f0; padding: 5px; border: none; }

QDialog { background-color: #1e1e1e; color: #f0f0f0; }
QMessageBox { background-color: #2a2a2a; }
QMessageBox QLabel { color: #f0f0f0; }
QInputDialog { background-color: #2a2a2a; }
QInputDialog QLabel { color: #f0f0f0; }

QTextBrowser { background-color: #232323; color: #f0f0f0; border: 1px solid #555555; }

QScrollBar:vertical { background: #2a2a2a; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #5a5a5a; border-radius: 6px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #777777; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* Readable tooltips: light background, dark text, regardless of dark theme. */
QToolTip {
    background-color: #fff8dc; color: #1a1a1a; border: 1px solid #444444;
    padding: 6px 8px; font-size: 12px; border-radius: 4px;
}
"""

def get_fps(cap):
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or (isinstance(fps, float) and (np.isnan(fps) or fps <= 0)):
        return None
    return fps

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    update_slider_signal = pyqtSignal(int)
    video_ended_signal = pyqtSignal()
    seek_signal = pyqtSignal(int)

    def __init__(self, video_path, playback_speed, fps, start_frame=0, annotations=None):
        super().__init__()
        self.video_path = video_path
        self.playback_speed = float(playback_speed)
        self.fps = float(fps) if fps else 30.0
        self.cap = cv2.VideoCapture(self.video_path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._run_flag = True
        self.mutex = QMutex()
        self.annotations = annotations or []
        self.base_frame = int(start_frame)
        self.current_frame = int(start_frame)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.base_frame)
        else:
            logging.error("Error opening video stream or file")
            self._run_flag = False
        self.start_wall = time.perf_counter()
        self.seek_signal.connect(self.seek_position)

    @pyqtSlot(int)
    def seek_position(self, position):
        with QMutexLocker(self.mutex):
            position = int(position)
            if 0 <= position < self.total_frames:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, position)
                self.base_frame = position
                self.current_frame = position
                self.start_wall = time.perf_counter()
                logging.info(f"Seeked to frame: {position}")
            else:
                logging.warning(f"Seek position {position} out of range.")

    def set_speed(self, new_speed: float):
        with QMutexLocker(self.mutex):
            self.playback_speed = max(0.1, min(8.0, float(new_speed)))
            self.base_frame = self.current_frame
            self.start_wall = time.perf_counter()

    def _sleep_until_next_frame(self):
        """Sleep in small chunks until it is time to display the next frame.
        Looping ensures correctness at all speeds, including very slow playback."""
        while True:
            with QMutexLocker(self.mutex):
                if not self._run_flag:
                    return
                spd = max(0.1, min(8.0, float(self.playback_speed)))
                fps = float(self.fps) if self.fps and float(self.fps) > 0 else 30.0
                next_index_rel = (self.current_frame + 1 - self.base_frame) / (fps * spd)
                now_rel = time.perf_counter() - self.start_wall
                dt = next_index_rel - now_rel
            if dt <= 0:
                return
            if dt >= 0.05:
                QThread.msleep(50)
            elif dt >= 0.002:
                QThread.msleep(max(1, int(dt * 1000)))
            else:
                QThread.usleep(max(200, int(dt * 1_000_000)))

    def _catch_up_skip(self):
        with QMutexLocker(self.mutex):
            spd = max(0.1, min(8.0, self.playback_speed))
            now_rel = time.perf_counter() - self.start_wall
            target_index = int(now_rel * self.fps * spd) + self.base_frame
            target_index = min(target_index, self.total_frames - 1)
            delta = target_index - self.current_frame - 1
        if delta > 0:
            grabs = min(delta, 60)
            for _ in range(grabs):
                with QMutexLocker(self.mutex):
                    self.cap.grab()
            with QMutexLocker(self.mutex):
                self.current_frame += grabs

    def run(self):
        while self._run_flag:
            self._sleep_until_next_frame()
            self._catch_up_skip()
            with QMutexLocker(self.mutex):
                if not self._run_flag:
                    break
                ret, cv_img = self.cap.read()
            if not ret:
                self.video_ended_signal.emit()
                break
            with QMutexLocker(self.mutex):
                self.current_frame += 1
                frame_index = self.current_frame
                rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                frame_time = frame_index / self.fps if self.fps else 0.0
                for annotation in self.annotations:
                    if annotation['start_time'] <= frame_time <= annotation['end_time']:
                        behaviour = annotation['behaviour']
                        color = annotation.get('color', (255, 0, 0))
                        cv2.putText(rgb_image, behaviour, (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                                    1.5, color, 3, cv2.LINE_AA)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            self.change_pixmap_signal.emit(qt_image)
            self.update_slider_signal.emit(frame_index)
        with QMutexLocker(self.mutex):
            self.cap.release()

    def stop(self):
        with QMutexLocker(self.mutex):
            self._run_flag = False
        self.wait()

class VideoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.image:
            rect = self.rect()
            img_rect = QRectF(0, 0, self.image.width(), self.image.height())
            target_rect = QRectF(0, 0, rect.width(), rect.height())
            painter.drawImage(target_rect, self.image, img_rect)
        else:
            painter.fillRect(self.rect(), Qt.black)

    def update_image(self, qt_image):
        self.image = qt_image
        self.update()

class TimelineWidget(QWidget):
    def __init__(self, events, total_duration):
        super().__init__()
        self.events = events or []
        self.total_duration = total_duration or 1.0
        self.current_time = 0.0
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Expanding, QSzPolicy.Fixed)

    def update_events(self, events):
        self.events = events or []
        self.update()

    def set_current_time(self, t):
        self.current_time = clamp(float(t), 0.0, self.total_duration if self.total_duration else 0.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        width = rect.width()
        height = self.rect().height()
        painter.fillRect(rect, QColor("#2e2e2e"))
        behaviour_colors = {}
        palette = [
            QColor("#ff9999"), QColor("#99ff99"), QColor("#9999ff"),
            QColor("#ffff99"), QColor("#99ffff"), QColor("#ff99ff"),
            QColor("#ffcc99"), QColor("#ccff99"), QColor("#99ffcc"),
            QColor("#99ccff")
        ]
        phases = []
        for ev in self.events:
            ph = ev.get('phase', 'Default Phase')
            if ph not in phases:
                phases.append(ph)
        for idx, phase in enumerate(phases):
            behaviour_colors[phase] = palette[idx % len(palette)]
        for ev in self.events:
            phase = ev.get('phase', 'Default Phase')
            start_px = (ev['start_time'] / self.total_duration) * width if self.total_duration else 0
            end_px = (ev['end_time'] / self.total_duration) * width if self.total_duration else 0
            seg_h = max(4, height // 3)
            y_top = (height - seg_h) // 2
            painter.fillRect(QRectF(start_px, y_top, max(1.0, end_px - start_px), seg_h),
                             behaviour_colors.get(phase, QColor("#ffffff")))
        pos_x = 0 if not self.total_duration else (self.current_time / self.total_duration) * width
        pen = QPen(QColor('#ffffff'))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(int(pos_x), 0, int(pos_x), height)
        painter.end()

class HistoryPanel(QListWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('History Panel')
        self.setGeometry(50, 50, 300, 500)
        self.setStyleSheet('background-color: #2e2e2e; color: #ffffff;')

    def add_action(self, action_text):
        self.addItem(action_text)
        self.scrollToBottom()

class Configuration:
    def __init__(self):
        self.settings = QSettings('BehaviourScoringApp', 'Settings')

    def load_settings(self):
        try:
            if self.settings.contains('scoring_keys'):
                scoring_keys_json = self.settings.value('scoring_keys')
                raw = json.loads(scoring_keys_json)
                result = {}
                for k, v in raw.items():
                    try:
                        if v is None or v == -1:
                            continue
                        result[k] = int(v)
                    except Exception:
                        continue
                return result
            return {}
        except Exception as e:
            logging.error(f'Error loading settings: {e}')
            return {}

    def save_settings(self, scoring_keys):
        try:
            clean = {k: int(v) for k, v in scoring_keys.items() if isinstance(v, int)}
            scoring_keys_json = json.dumps(clean)
            self.settings.setValue('scoring_keys', scoring_keys_json)
        except Exception as e:
            logging.error(f'Error saving settings: {e}')

class AssignKeyDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Assign Keys and Behaviours')
        self.setMinimumSize(640, 520)
        self.behaviour_keys = self.parent().scoring_keys.copy()
        self.current_behaviour = None
        self.waiting_for_key = False
        outer = QVBoxLayout(self)
        self.instructions = QLabel("Enter behaviour name, click 'Add & Assign', then press a key...")
        self.instructions.setStyleSheet("color: white; font-size: 14px;")
        outer.addWidget(self.instructions)
        add_row = QHBoxLayout()
        self.behaviour_input = QLineEdit()
        self.behaviour_input.setPlaceholderText("Enter behaviour name")
        self.add_assign_btn = QPushButton('Add & Assign')
        self.add_assign_btn.setToolTip('Create a new behaviour and assign a key to it')
        self.add_assign_btn.clicked.connect(self.add_and_assign)
        for b in (self.add_assign_btn,):
            b.setStyleSheet("""
                QPushButton {
                    color: #ffffff;
                    background-color: #555555;
                    border: 2px solid #ffffff;
                    border-radius: 10px;
                    font-size: 14px;
                    padding: 5px 10px;
                }
                QPushButton:hover { background-color: #777777; }
            """)
        add_row.addWidget(self.behaviour_input, 1)
        add_row.addWidget(self.add_assign_btn, 0)
        outer.addLayout(add_row)
        self.assigned_table = QTableWidget()
        self.assigned_table.setColumnCount(2)
        self.assigned_table.setHorizontalHeaderLabels(['Behaviour', 'Key'])
        self.assigned_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.assigned_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.assigned_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.assigned_table.setStyleSheet("""
            QTableWidget {
                background-color: #2e2e2e;
                color: #ffffff;
                border: 1px solid #ffffff;
            }
            QHeaderView::section {
                background-color: #555555;
                color: #ffffff;
            }
        """)
        self.assigned_table.doubleClicked.connect(self.rename_selected)
        outer.addWidget(self.assigned_table)
        act_row = QHBoxLayout()
        self.assign_key_btn = QPushButton('Reassign Key')
        self.clear_key_btn = QPushButton('Clear Key')
        self.rename_btn = QPushButton('Rename')
        self.remove_btn = QPushButton('Remove')
        for b in (self.assign_key_btn, self.clear_key_btn, self.rename_btn, self.remove_btn):
            b.setStyleSheet("""
                QPushButton {
                    color: #ffffff;
                    background-color: #555555;
                    border: 2px solid #ffffff;
                    border-radius: 10px;
                    font-size: 13px;
                    padding: 4px 10px;
                }
                QPushButton:hover { background-color: #777777; }
            """)
        self.assign_key_btn.clicked.connect(self.reassign_selected)
        self.clear_key_btn.clicked.connect(self.clear_selected)
        self.rename_btn.clicked.connect(self.rename_selected)
        self.remove_btn.clicked.connect(self.remove_selected)
        act_row.addWidget(self.assign_key_btn)
        act_row.addWidget(self.clear_key_btn)
        act_row.addWidget(self.rename_btn)
        act_row.addWidget(self.remove_btn)
        act_row.addItem(QSpacerItem(10, 10, QSzPolicy.Expanding, QSzPolicy.Minimum))
        outer.addLayout(act_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.setFocusPolicy(Qt.StrongFocus)
        self.update_assigned_table()

    def _selected_behaviour(self):
        row = self.assigned_table.currentRow()
        if row < 0:
            return None
        return self.assigned_table.item(row, 0).text()

    def _confirm_replace_key(self, key_seq_str, existing_behaviour):
        return QMessageBox.question(
            self, 'Key Already Assigned',
            f"The key '{key_seq_str}' is already assigned to '{existing_behaviour}'.\n"
            f"Do you want to reassign it to the new behaviour?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes

    def _find_behaviour_by_key(self, keycode):
        for b, k in self.behaviour_keys.items():
            if k == keycode:
                return b
        return None

    def add_and_assign(self):
        behaviour = self.behaviour_input.text().strip()
        if not behaviour:
            QMessageBox.warning(self, 'Input Error', 'Please enter a behaviour name.')
            return
        if behaviour in self.behaviour_keys:
            QMessageBox.warning(self, 'Duplicate Name', 'A behaviour with this name already exists.')
            return
        self.current_behaviour = behaviour
        self.waiting_for_key = True
        self.instructions.setText(f"Assigning for '{behaviour}'. Press any key now... (Esc to cancel)")
        self.add_assign_btn.setEnabled(False)
        self.grabKeyboard()
        self.setFocus()

    def reassign_selected(self):
        behaviour = self._selected_behaviour()
        if not behaviour:
            QMessageBox.information(self, 'No Selection', 'Please select a behaviour to reassign.')
            return
        self.current_behaviour = behaviour
        self.waiting_for_key = True
        self.instructions.setText(f"Reassign key for '{behaviour}'. Press any key now... (Esc to cancel)")
        self.grabKeyboard()
        self.setFocus()

    def clear_selected(self):
        behaviour = self._selected_behaviour()
        if not behaviour:
            QMessageBox.information(self, 'No Selection', 'Please select a behaviour to clear/remove.')
            return
        del self.behaviour_keys[behaviour]
        self.update_assigned_table()

    def rename_selected(self):
        behaviour = self._selected_behaviour()
        if not behaviour:
            return
        new_name, ok = QInputDialog.getText(self, 'Rename Behaviour', 'New name:', text=behaviour)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, 'Invalid Name', 'Name cannot be empty.')
            return
        if new_name != behaviour and new_name in self.behaviour_keys:
            QMessageBox.warning(self, 'Duplicate Name', 'A behaviour with this name already exists.')
            return
        keycode = self.behaviour_keys[behaviour]
        del self.behaviour_keys[behaviour]
        self.behaviour_keys[new_name] = keycode
        self.update_assigned_table()

    def remove_selected(self):
        behaviour = self._selected_behaviour()
        if not behaviour:
            QMessageBox.information(self, 'No Selection', 'Please select a behaviour to remove.')
            return
        del self.behaviour_keys[behaviour]
        self.update_assigned_table()

    def keyPressEvent(self, event):
        if self.waiting_for_key:
            if event.key() == Qt.Key_Escape:
                self.waiting_for_key = False
                self.current_behaviour = None
                self.releaseKeyboard()
                self.add_assign_btn.setEnabled(True)
                self.instructions.setText("Key assignment cancelled. Enter behaviour and click 'Add & Assign'.")
                return
            key = event.key()
            modifiers = int(event.modifiers())
            combined_key = key + (modifiers << 16)
            key_seq_str = QKeySequence(combined_key).toString()
            existing = self._find_behaviour_by_key(combined_key)
            if existing and existing != self.current_behaviour:
                if not self._confirm_replace_key(key_seq_str, existing):
                    return
                del self.behaviour_keys[existing]
            if self.current_behaviour:
                self.behaviour_keys[self.current_behaviour] = combined_key
            self.current_behaviour = None
            self.waiting_for_key = False
            self.releaseKeyboard()
            self.add_assign_btn.setEnabled(True)
            self.behaviour_input.clear()
            self.instructions.setText("Assigned. Enter another behaviour or click Done.")
            self.update_assigned_table()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        try:
            if self.waiting_for_key:
                self.releaseKeyboard()
        except Exception:
            pass
        super().closeEvent(event)

    def update_assigned_table(self):
        self.assigned_table.setRowCount(0)
        for behaviour, key in self.behaviour_keys.items():
            row_position = self.assigned_table.rowCount()
            self.assigned_table.insertRow(row_position)
            self.assigned_table.setItem(row_position, 0, QTableWidgetItem(behaviour))
            self.assigned_table.setItem(row_position, 1, QTableWidgetItem(QKeySequence(key).toString()))

class TimeSpentDialog(QDialog):
    def __init__(self, parent, rows, total_seconds):
        super().__init__(parent)
        self.setWindowTitle('Time Spent (seconds)')
        self.setMinimumSize(480, 360)
        layout = QVBoxLayout(self)
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(['Behaviour', 'Seconds', 'Count', 'Percent'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #2e2e2e;
                color: #ffffff;
                border: 1px solid #ffffff;
            }
            QHeaderView::section {
                background-color: #555555;
                color: #ffffff;
            }
        """)
        table.setRowCount(len(rows) + 1)
        for i, r in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(r['behaviour']))
            table.setItem(i, 1, QTableWidgetItem(f"{r['seconds']:.3f}"))
            table.setItem(i, 2, QTableWidgetItem(str(r['count'])))
            pct = (r['seconds'] / total_seconds * 100.0) if total_seconds > 0 else 0.0
            table.setItem(i, 3, QTableWidgetItem(f"{pct:.1f}%"))
        total_count = sum(r['count'] for r in rows)
        table.setItem(len(rows), 0, QTableWidgetItem('Total'))
        table.setItem(len(rows), 1, QTableWidgetItem(f"{total_seconds:.3f}"))
        table.setItem(len(rows), 2, QTableWidgetItem(str(total_count)))
        table.setItem(len(rows), 3, QTableWidgetItem("100.0%" if total_seconds > 0 else "0.0%"))
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

class LiveScoringPanel(QGroupBox):
    """Right-hand live scoring readout.

    Shows one row per behaviour with its key, running total time and count.
    While a key is held (scoring in progress) the corresponding row lights up
    and displays the live elapsed time of the current press.
    """

    BASE_STYLE = (
        "QFrame#scoreRow { background-color: #2b2b2b; border: 1px solid #444444;"
        " border-radius: 8px; }"
    )
    ACTIVE_STYLE = (
        "QFrame#scoreRow { background-color: #14502a; border: 2px solid #39d353;"
        " border-radius: 8px; }"
    )

    def __init__(self, parent=None):
        super().__init__('Live Scoring', parent)
        self.rows = {}        # behaviour -> dict(frame,name_label,stat_label,live_label)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 14, 10, 10)
        outer.setSpacing(8)

        self.status_label = QLabel('\u25cf  Idle')
        self.status_label.setStyleSheet(
            'color: #aaaaaa; font-size: 15px; font-weight: bold; background: transparent;'
        )
        self.status_label.setToolTip(
            'Shows whether scoring is active. Turns green and pulses while a video '
            'is playing and you are recording behaviours.'
        )
        outer.addWidget(self.status_label)

        self.session_label = QLabel('Session: -')
        self.session_label.setStyleSheet(
            'color: #9ecbff; font-size: 13px; background: transparent;'
        )
        outer.addWidget(self.session_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        self._rows_layout.addStretch()
        scroll.setWidget(self._rows_host)
        outer.addWidget(scroll, 1)

        self.empty_label = QLabel('No behaviours assigned yet.\nClick "Assign Keys" to begin.')
        self.empty_label.setStyleSheet('color: #888888; font-size: 12px; background: transparent;')
        self.empty_label.setAlignment(Qt.AlignCenter)
        self._rows_layout.insertWidget(0, self.empty_label)

    def set_session_name(self, name):
        self.session_label.setText(f'Session: {name}')

    def set_status(self, scoring):
        if scoring:
            self.status_label.setText('\u25cf  SCORING')
            self.status_label.setStyleSheet(
                'color: #39d353; font-size: 15px; font-weight: bold; background: transparent;'
            )
        else:
            self.status_label.setText('\u25cf  Idle')
            self.status_label.setStyleSheet(
                'color: #aaaaaa; font-size: 15px; font-weight: bold; background: transparent;'
            )

    def rebuild(self, scoring_keys, time_spent, frequency_counts, format_time):
        # Clear existing rows.
        for data in self.rows.values():
            data['frame'].setParent(None)
            data['frame'].deleteLater()
        self.rows = {}
        if not scoring_keys:
            self.empty_label.setVisible(True)
            return
        self.empty_label.setVisible(False)
        insert_at = self._rows_layout.count() - 1  # before the stretch
        for behaviour, key in scoring_keys.items():
            frame = QFrame()
            frame.setObjectName('scoreRow')
            frame.setStyleSheet(self.BASE_STYLE)
            row_layout = QVBoxLayout(frame)
            row_layout.setContentsMargins(10, 7, 10, 7)
            row_layout.setSpacing(2)

            name_label = QLabel(f'{behaviour}    [ {QKeySequence(key).toString()} ]')
            name_label.setStyleSheet(
                'color: #ffffff; font-size: 14px; font-weight: bold; background: transparent; border: none;'
            )
            stat_label = QLabel(
                f'Time: {format_time(time_spent.get(behaviour, 0.0))}    '
                f'Count: {frequency_counts.get(behaviour, 0)}'
            )
            stat_label.setStyleSheet('color: #cfcfcf; font-size: 12px; background: transparent; border: none;')
            live_label = QLabel('')
            live_label.setStyleSheet('color: #39d353; font-size: 12px; font-weight: bold; background: transparent; border: none;')

            row_layout.addWidget(name_label)
            row_layout.addWidget(stat_label)
            row_layout.addWidget(live_label)
            self._rows_layout.insertWidget(insert_at, frame)
            insert_at += 1
            self.rows[behaviour] = {
                'frame': frame, 'name': name_label,
                'stat': stat_label, 'live': live_label
            }

    def update_stats(self, behaviour, key, time_str, count):
        data = self.rows.get(behaviour)
        if not data:
            return
        data['name'].setText(f'{behaviour}    [ {QKeySequence(key).toString()} ]')
        data['stat'].setText(f'Time: {time_str}    Count: {count}')

    def set_active(self, behaviour, active):
        data = self.rows.get(behaviour)
        if not data:
            return
        if active:
            data['frame'].setStyleSheet(self.ACTIVE_STYLE)
        else:
            data['frame'].setStyleSheet(self.BASE_STYLE)
            data['live'].setText('')

    def set_live_elapsed(self, behaviour, elapsed):
        data = self.rows.get(behaviour)
        if not data:
            return
        data['live'].setText(f'\u25b6 recording  +{elapsed:0.2f}s')


class TutorialDialog(QDialog):
    """A friendly, scrollable walkthrough of the application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Tutorial \u2014 Rodent Manual Scorer')
        self.setMinimumSize(640, 560)
        layout = QVBoxLayout(self)
        header = QLabel('How to use the Rodent Manual Scorer')
        header.setStyleSheet('color: #9ecbff; font-size: 20px; font-weight: bold;')
        layout.addWidget(header)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._content_html())
        layout.addWidget(browser, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _content_html(self):
        return """
        <style>
            body { color: #f0f0f0; font-size: 14px; line-height: 1.5; }
            h3 { color: #9ecbff; margin-bottom: 4px; }
            code { background: #333; padding: 1px 5px; border-radius: 3px; color: #ffd479; }
            li { margin-bottom: 6px; }
        </style>
        <h3>1. Load a video</h3>
        <p>Use <b>File &rarr; Load Video</b> (<code>Ctrl+O</code>) or simply drag a video file
        onto the window. Supported formats: AVI, MP4, MOV, MKV. If the file does not report a
        frame rate, you will be asked to type it in.</p>

        <h3>2. Assign behaviours to keys</h3>
        <p>Click <b>Assign Keys</b> on the right. Type a behaviour name, click
        <b>Add &amp; Assign</b>, then press the keyboard key you want to use for it. Repeat for
        each behaviour. You can rename, clear or remove assignments at any time.</p>

        <h3>3. Play and score</h3>
        <ul>
            <li><b>Space</b> plays / pauses the video.</li>
            <li><b>Hold</b> a behaviour key for as long as the behaviour lasts, then release.
            The duration between press and release is recorded as one event.</li>
            <li>The <b>Live Scoring</b> box on the right lights up green while a key is held and
            shows the live elapsed time, so you always know what is being recorded.</li>
            <li>Adjust playback speed with the speed dropdown (0.1x to 8x).</li>
        </ul>

        <h3>4. Phases</h3>
        <p>Press <b>P</b> (or click <b>Start New Phase</b>) to begin a labelled phase with its own
        colour. Phases appear as coloured bands on the timeline beneath the video.</p>

        <h3>5. Sessions (scoring the same video more than once)</h3>
        <ul>
            <li>Each scoring pass is a <b>session</b>. The current session is shown in the
            <b>Session</b> dropdown on the right.</li>
            <li>Click <b>New Session</b> to start another pass. You choose whether to
            <b>start from scratch</b> (empty scores, video rewound to 0) or to
            <b>continue from a copy</b> of the current session.</li>
            <li>Previous sessions are never discarded \u2014 switch back to any of them using the
            dropdown to view or keep editing their scores.</li>
        </ul>

        <h3>6. Fix mistakes</h3>
        <p><code>Ctrl+Z</code> undoes the last scored event (and rewinds the video to where it
        started); <code>Ctrl+Y</code> redoes it. <b>View &rarr; Show History</b> lists everything
        you have recorded.</p>

        <h3>7. Save your work</h3>
        <ul>
            <li><b>Save Scoring CSV</b> (<code>Ctrl+S</code>) and <b>Load Scoring CSV</b>
            (<code>Ctrl+L</code>).</li>
            <li><b>Export Excel</b> (<code>Ctrl+E</code>) writes a summary sheet plus a detailed
            event list.</li>
            <li>The app autosaves to <code>autosave_rms.csv</code> every five minutes.</li>
        </ul>

        <h3>Tip</h3>
        <p>Hover the mouse over any button or control to see a short description of what it does.</p>
        """


class NewSessionDialog(QDialog):
    """Ask the user how to begin a new scoring pass."""

    def __init__(self, parent=None, default_name='Session'):
        super().__init__(parent)
        self.setWindowTitle('New Session')
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)

        intro = QLabel(
            'Start another scoring pass over the same video.\n'
            'Your current session stays available in the dropdown.'
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.name_input = QLineEdit(default_name)
        self.name_input.setToolTip('A label for this scoring pass')
        form.addRow('Session name:', self.name_input)
        layout.addLayout(form)

        self.fresh_radio = QRadioButton('Start from scratch (empty scores, rewind to 0)')
        self.fresh_radio.setToolTip('Begin a clean pass with no events and the video at the start')
        self.copy_radio = QRadioButton('Continue from a copy of the current session')
        self.copy_radio.setToolTip('Duplicate the current scores so you can build on them')
        self.fresh_radio.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.fresh_radio)
        group.addButton(self.copy_radio)
        layout.addWidget(self.fresh_radio)
        layout.addWidget(self.copy_radio)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def session_name(self):
        return self.name_input.text().strip()

    def mode(self):
        return 'copy' if self.copy_radio.isChecked() else 'fresh'


class BehaviourScoringApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Rodent Manual Scorer')
        self.setGeometry(100, 100, 1400, 800)
        self.video_path = ''
        self.playback_speed = 1.0
        self.fps = None
        self.scoring_keys = {}
        self.time_spent = {}
        self.frequency_counts = {}
        self.scoring = False
        self.key_states = {}
        self.last_key_times = {}
        self.behaviour_events = []
        self.paused_frame = None
        self.undo_stack = []
        self.redo_stack = []
        self.current_phase = "Default Phase"
        self.phase_colors = {"Default Phase": QColor("#ffffff")}
        self.annotations = []
        self.is_fullscreen = False
        self.total_duration = 0.0

        # --- Multi-session state -------------------------------------------
        # Each session is a self-contained scoring pass over the same video.
        # The "active" session's data lives in the self.* attributes above;
        # other sessions are snapshotted into self.sessions and can be loaded
        # back at any time. This lets the user score the same video repeatedly
        # while keeping every previous pass available.
        self.sessions = []            # list of session-snapshot dicts
        self.active_session_index = -1
        self._session_counter = 0
        self._suppress_session_switch = False

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#1e1e1e"))
        self.setPalette(palette)
        # Apply the readable dark theme to the whole application (covers menus,
        # dialogs, group boxes, checkboxes, combo popups and tooltips).
        if QApplication.instance() is not None:
            QApplication.instance().setStyleSheet(GLOBAL_STYLE)
        self.history_panel = HistoryPanel()
        self.history_panel.hide()
        self.config = Configuration()
        self.scoring_keys = self.config.load_settings()
        self.initUI()
        self.installEventFilter(self)
        if QApplication.instance() is not None:
            QApplication.instance().installEventFilter(self)
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.autosave_session)
        self.autosave_timer.start(300000)
        self.video_thread = None

    def initUI(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        self.left_layout = QVBoxLayout()
        self.right_layout = QVBoxLayout()
        self.main_layout.addLayout(self.left_layout, 3)
        self.main_layout.addLayout(self.right_layout, 1)
        self.create_menu()
        self.create_video_display()
        self.create_controls()
        self.create_behaviour_controls()
        self.create_frequency_controls()
        self.create_phase_manager()
        self.scoring_timer = QTimer()
        self.scoring_timer.timeout.connect(self.update_timers)
        self.setAcceptDrops(True)

    def create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        file_menu.setToolTipsVisible(True)
        load_video_action = QAction('Load Video', self)
        load_video_action.setShortcut('Ctrl+O')
        load_video_action.setToolTip('Open a video file to score (or drag a file onto the window)')
        load_video_action.triggered.connect(self.upload_video)
        file_menu.addAction(load_video_action)
        load_csv_action = QAction('Load Scoring CSV', self)
        load_csv_action.setShortcut('Ctrl+L')
        load_csv_action.setToolTip('Load previously saved scoring data from a CSV file')
        load_csv_action.triggered.connect(self.load_scoring_csv)
        file_menu.addAction(load_csv_action)
        save_csv_action = QAction('Save Scoring CSV', self)
        save_csv_action.setShortcut('Ctrl+S')
        save_csv_action.setToolTip('Save the current session\'s scored events to a CSV file')
        save_csv_action.triggered.connect(self.save_scoring_csv)
        file_menu.addAction(save_csv_action)
        export_excel_action = QAction('Export Excel', self)
        export_excel_action.setShortcut('Ctrl+E')
        export_excel_action.setToolTip('Export a summary and detailed event list to an Excel workbook')
        export_excel_action.triggered.connect(self.export_excel)
        file_menu.addAction(export_excel_action)
        reset_action = QAction('New Session', self)
        reset_action.setShortcut('Ctrl+N')
        reset_action.setToolTip('Start a new scoring pass while keeping previous sessions available')
        reset_action.triggered.connect(self.new_session)
        file_menu.addAction(reset_action)
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setToolTip('Close the application')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu('Edit')
        edit_menu.setToolTipsVisible(True)
        undo_action = QAction('Undo Last (Ctrl+Z)', self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.setToolTip('Undo the last scored event and rewind to where it started')
        undo_action.triggered.connect(self.undo_last_event)
        edit_menu.addAction(undo_action)
        redo_action = QAction('Redo (Ctrl+Y)', self)
        redo_action.setShortcut('Ctrl+Y')
        redo_action.setToolTip('Redo the most recently undone event')
        redo_action.triggered.connect(self.redo_last_event)
        edit_menu.addAction(redo_action)

        view_menu = menubar.addMenu('View')
        view_menu.setToolTipsVisible(True)
        history_action = QAction('Show History', self)
        history_action.setToolTip('Show or hide the panel listing every recorded action')
        history_action.triggered.connect(self.toggle_history_panel)
        view_menu.addAction(history_action)
        time_spent_action = QAction('Show Time Spent', self)
        time_spent_action.setShortcut('Ctrl+T')
        time_spent_action.setToolTip('Show a table of total time and counts per behaviour')
        time_spent_action.triggered.connect(self.show_time_spent)
        view_menu.addAction(time_spent_action)
        fullscreen_action = QAction('Toggle Fullscreen', self)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.setToolTip('Switch between fullscreen and windowed view')
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        help_menu = menubar.addMenu('Help')
        help_menu.setToolTipsVisible(True)
        tutorial_action = QAction('Tutorial', self)
        tutorial_action.setShortcut('F1')
        tutorial_action.setToolTip('Open a step-by-step guide to using the scorer')
        tutorial_action.triggered.connect(self.show_tutorial)
        help_menu.addAction(tutorial_action)

    def toggle_history_panel(self):
        if self.history_panel.isVisible():
            self.history_panel.hide()
        else:
            self.history_panel.show()

    def create_video_display(self):
        self.video_widget = VideoWidget()
        self.video_widget.setMinimumSize(1000, 600)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSzPolicy.Expanding)
        self.video_widget.setStyleSheet("""
            QWidget {
                background-color: #000000;
                border: 1px solid #ffffff;
                border-radius: 15px;
            }
        """)
        self.left_layout.addWidget(self.video_widget)

    def create_controls(self):
        self.controls_layout = QHBoxLayout()
        self.left_layout.addLayout(self.controls_layout)
        self.play_button = self.create_button('Play', self.play_video)
        self.play_button.setToolTip('Play the video and begin scoring (shortcut: Space)')
        self.controls_layout.addWidget(self.play_button)
        self.pause_button = self.create_button('Pause', self.pause_video)
        self.pause_button.setToolTip('Pause playback; press again or Space to resume')
        self.controls_layout.addWidget(self.pause_button)
        self.stop_button = self.create_button('Stop', self.stop_video)
        self.stop_button.setToolTip('Stop playback and rewind to the beginning')
        self.controls_layout.addWidget(self.stop_button)
        self.fullscreen_button = self.create_button('Fullscreen', self.toggle_fullscreen)
        self.fullscreen_button.setToolTip('Toggle fullscreen view (shortcut: F11)')
        self.controls_layout.addWidget(self.fullscreen_button)
        self.controls_layout.addStretch()
        self.speed_dropdown = QComboBox()
        speeds = ['0.1x', '0.25x', '0.5x', '0.75x', '1x', '1.25x', '1.5x', '2x', '3x', '4x', '6x', '8x']
        self.speed_dropdown.addItems(speeds)
        self.speed_dropdown.setCurrentText('1x')
        self.speed_dropdown.currentIndexChanged.connect(self.change_playback_speed)
        self.speed_dropdown.setToolTip('Playback speed \u2014 slow down for fast behaviours, speed up to skim')
        self.speed_dropdown.setStyleSheet("""
            QComboBox {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #ffffff;
                border-radius: 5px;
                padding: 5px;
                min-width: 96px;
            }
            QComboBox:hover {
                background-color: #555555;
            }
        """)
        self.controls_layout.addWidget(self.speed_dropdown)
        self.video_slider = QSlider(Qt.Horizontal)
        self.video_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #333333;
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #ffffff;
                width: 18px;
                margin: -2px 0;
                border-radius: 3px;
            }
        """)
        self.video_slider.sliderMoved.connect(self.set_video_position)
        self.video_slider.setToolTip('Drag to scrub through the video')
        self.left_layout.addWidget(self.video_slider)
        self.timeline_widget = TimelineWidget([], 1.0)
        self.timeline_widget.setToolTip('Timeline of scored events; the white line marks the current position')
        self.left_layout.addWidget(self.timeline_widget)
        self.timestamp_label = QLabel('00:00:00.000 / 00:00:00.000')
        self.timestamp_label.setAlignment(Qt.AlignCenter)
        self.timestamp_label.setStyleSheet('color: #ffffff;')
        self.left_layout.addWidget(self.timestamp_label)

    def toggle_fullscreen(self):
        try:
            if not self.is_fullscreen:
                self.showFullScreen()
                self.is_fullscreen = True
            else:
                self.showNormal()
                self.is_fullscreen = False
        except Exception as e:
            logging.error(f'Error toggling fullscreen: {e}')

    def create_button(self, text, function):
        button = QPushButton(text)
        button.setMinimumSize(100, 40)
        button.setSizePolicy(QSizePolicy.Fixed, QSzPolicy.Fixed)
        button.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: transparent;
                border: 2px solid #ffffff;
                border-radius: 20px;
                font-size: 14px;
                padding: 5px 14px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """)
        button.clicked.connect(function)
        return button

    def create_behaviour_controls(self):
        # --- Session selector ---------------------------------------------
        self.session_groupbox = QGroupBox('Session')
        session_layout = QVBoxLayout()
        self.session_groupbox.setLayout(session_layout)
        self.session_dropdown = QComboBox()
        self.session_dropdown.setToolTip(
            'Switch between scoring passes. Each session keeps its own events, '
            'counts and timeline; switching never deletes the others.'
        )
        self.session_dropdown.currentIndexChanged.connect(self.on_session_dropdown_changed)
        session_layout.addWidget(self.session_dropdown)
        self.new_session_button = QPushButton('New Session')
        self.new_session_button.setStyleSheet(self._panel_button_style())
        self.new_session_button.setToolTip(
            'Start another scoring pass over the same video. You can begin from '
            'scratch (rewound to 0) or from a copy of the current session.'
        )
        self.new_session_button.clicked.connect(self.new_session)
        session_layout.addWidget(self.new_session_button)
        self.right_layout.addWidget(self.session_groupbox)

        # --- Assign keys ---------------------------------------------------
        self.assign_keys_button = QPushButton('Assign Keys')
        self.assign_keys_button.setStyleSheet(self._panel_button_style())
        self.assign_keys_button.setToolTip('Create behaviours and bind each one to a keyboard key')
        self.assign_keys_button.clicked.connect(self.open_assign_dialog)
        self.right_layout.addWidget(self.assign_keys_button)

        # --- Live scoring readout -----------------------------------------
        self.live_panel = LiveScoringPanel()
        self.live_panel.setToolTip(
            'Live readout of every behaviour. A row glows green while its key is '
            'held and shows the elapsed time of the current press.'
        )
        self.right_layout.addWidget(self.live_panel, 1)

        # --- Feedback line -------------------------------------------------
        self.feedback_label = QLabel('Load a video to begin. Press F1 for the tutorial.')
        self.feedback_label.setStyleSheet('color: #f0f0f0; font-size: 13px;')
        self.feedback_label.setWordWrap(True)
        self.right_layout.addWidget(self.feedback_label)

        # behaviour_labels is retained for backward compatibility but the
        # LiveScoringPanel is now the source of truth for the display.
        self.behaviour_labels = {}

    def _panel_button_style(self):
        return """
            QPushButton {
                color: #ffffff;
                background-color: #555555;
                border: 2px solid #ffffff;
                border-radius: 10px;
                font-size: 14px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """

    def show_tutorial(self):
        try:
            dlg = TutorialDialog(self)
            dlg.exec_()
        except Exception as e:
            logging.error(f'Error showing tutorial: {e}')

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------
    def _default_session_name(self):
        return f'Session {len(self.sessions) + 1}'

    def _make_session_snapshot(self, name):
        return {
            'name': name,
            'behaviour_events': [],
            'time_spent': {},
            'frequency_counts': {},
            'annotations': [],
            'undo_stack': [],
            'redo_stack': [],
            'current_phase': 'Default Phase',
            'phase_colors': {'Default Phase': QColor('#ffffff')},
        }

    def _capture_active_into_session(self):
        """Copy the live self.* scoring data back into the active snapshot."""
        if 0 <= self.active_session_index < len(self.sessions):
            s = self.sessions[self.active_session_index]
            s['behaviour_events'] = self.behaviour_events
            s['time_spent'] = self.time_spent
            s['frequency_counts'] = self.frequency_counts
            s['annotations'] = self.annotations
            s['undo_stack'] = self.undo_stack
            s['redo_stack'] = self.redo_stack
            s['current_phase'] = self.current_phase
            s['phase_colors'] = self.phase_colors

    def _apply_session(self, index):
        """Load a snapshot's data into the live self.* attributes and refresh UI."""
        if index < 0 or index >= len(self.sessions):
            return
        s = self.sessions[index]
        self.behaviour_events = s['behaviour_events']
        self.time_spent = s['time_spent']
        self.frequency_counts = s['frequency_counts']
        self.annotations = s['annotations']
        self.undo_stack = s['undo_stack']
        self.redo_stack = s['redo_stack']
        self.current_phase = s['current_phase']
        self.phase_colors = s['phase_colors']
        self.active_session_index = index
        self.update_behaviour_labels()
        self.update_frequency_controls()
        self.timeline_widget.update_events(self.get_all_behaviour_events())
        self.live_panel.set_session_name(s['name'])

    def _refresh_session_dropdown(self):
        self._suppress_session_switch = True
        try:
            self.session_dropdown.clear()
            for s in self.sessions:
                self.session_dropdown.addItem(s['name'])
            if 0 <= self.active_session_index < len(self.sessions):
                self.session_dropdown.setCurrentIndex(self.active_session_index)
        finally:
            self._suppress_session_switch = False

    def _init_first_session(self):
        """Create the initial session when a video is loaded."""
        self.sessions = []
        self.active_session_index = -1
        snap = self._make_session_snapshot(self._default_session_name())
        self.sessions.append(snap)
        self._apply_session(0)
        self._refresh_session_dropdown()

    def on_session_dropdown_changed(self, index):
        if self._suppress_session_switch:
            return
        if index < 0 or index >= len(self.sessions) or index == self.active_session_index:
            return
        try:
            if self.video_thread and self.video_thread.isRunning():
                self.video_thread.stop()
            self.scoring_timer.stop()
            self.scoring = False
            self.live_panel.set_status(False)
            self._capture_active_into_session()
            self._apply_session(index)
            self.paused_frame = 0
            self.video_slider.setValue(0)
            self.update_timestamp(0, self.total_duration)
            if self.video_path:
                self.update_video_display(0)
            self.feedback_label.setText(
                f"Viewing '{self.sessions[index]['name']}'. Press Play or Space to score."
            )
            logging.info(f"Switched to session: {self.sessions[index]['name']}")
        except Exception as e:
            logging.error(f'Error switching session: {e}')

    def create_frequency_controls(self):
        self.frequency_groupbox = QGroupBox("Frequency Display Options")
        self.frequency_groupbox.setToolTip('Choose which behaviours contribute to frequency counts')
        self.frequency_layout = QVBoxLayout()
        self.frequency_groupbox.setLayout(self.frequency_layout)
        self.global_frequency_checkbox = QCheckBox("Enable Frequency Counts")
        self.global_frequency_checkbox.setToolTip('Tick or untick every behaviour at once')
        self.global_frequency_checkbox.setChecked(True)
        self.global_frequency_checkbox.stateChanged.connect(self.toggle_global_frequency)
        self.frequency_layout.addWidget(self.global_frequency_checkbox)
        self.right_layout.addWidget(self.frequency_groupbox)

    def create_phase_manager(self):
        self.phase_manager_layout = QVBoxLayout()
        self.phase_button = QPushButton('Start New Phase')
        self.phase_button.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #555555;
                border: 2px solid #ffffff;
                border-radius: 10px;
                font-size: 14px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """)
        self.phase_button.clicked.connect(self.start_new_phase)
        self.phase_button.setToolTip('Begin a labelled phase with its own colour (shortcut: P)')
        self.phase_manager_layout.addWidget(self.phase_button)
        self.phase_color_button = QPushButton('Select Phase Colour')
        self.phase_color_button.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #555555;
                border: 2px solid #ffffff;
                border-radius: 10px;
                font-size: 14px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """)
        self.phase_color_button.setVisible(False)
        self.phase_color_button.setToolTip('Change the colour used for the current phase on the timeline')
        self.phase_color_button.clicked.connect(self.select_phase_color)
        self.phase_manager_layout.addWidget(self.phase_color_button)
        self.selected_color = QColor("#ffffff")
        self.right_layout.addLayout(self.phase_manager_layout)

        # On-screen tutorial button (in addition to Help -> Tutorial / F1).
        self.tutorial_button = QPushButton('\u2753  Tutorial')
        self.tutorial_button.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #2f5b9c;
                border: 2px solid #9ecbff;
                border-radius: 10px;
                font-size: 14px;
                padding: 7px;
            }
            QPushButton:hover { background-color: #3d6fb4; }
        """)
        self.tutorial_button.setToolTip('Open a step-by-step guide on how to use the scorer (F1)')
        self.tutorial_button.clicked.connect(self.show_tutorial)
        self.right_layout.addWidget(self.tutorial_button)

    def upload_video(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, 'Select Video File', '',
            'Video Files (*.avi *.mp4 *.mov *.mkv);;All Files (*)', options=options
        )
        if file_name:
            self.load_video(file_name)

    def load_video(self, file_name):
        try:
            if self.video_thread and self.video_thread.isRunning():
                self.video_thread.stop()
            self.scoring_timer.stop()
            self.scoring = False
            self.time_spent = {}
            self.frequency_counts = {}
            self.behaviour_events = []
            self.undo_stack = []
            self.redo_stack = []
            self.annotations = []
            self.paused_frame = None
            self.video_path = file_name
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                QMessageBox.critical(self, 'Error', 'Failed to open the video file.')
                logging.error('Failed to open the video file.')
                return
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.video_slider.setMaximum(total_frames if total_frames > 0 else 0)
            fps = get_fps(self.cap)
            if fps is None:
                fps_input, ok = QInputDialog.getDouble(
                    self, 'FPS Required', 'The video file does not report FPS. Please enter the FPS:',
                    decimals=2, min=1.0, value=30.0
                )
                if ok and fps_input > 0:
                    self.fps = float(fps_input)
                else:
                    QMessageBox.warning(self, 'Error', 'Valid FPS is required. Cannot proceed without FPS.')
                    logging.error('Invalid FPS input.')
                    self.cap.release()
                    return
            else:
                self.fps = float(fps)
            total_seconds = (total_frames / self.fps) if self.fps else 0.0
            self.total_duration = total_seconds
            self.timestamp_label.setText(f'00:00:00.000 / {self.format_time(total_seconds)}')
            self.cap.release()
            logging.info(f'Video loaded: {self.video_path}')
            self.feedback_label.setText('Video loaded. Assign keys and start scoring.')
            self.paused_frame = None
            self.video_slider.setValue(0)
            self.update_timestamp(0, total_seconds)
            self.video_widget.image = None
            self.video_widget.update()
            self.timeline_widget.total_duration = total_seconds
            # Begin a fresh session set for this video.
            self._init_first_session()
            self.live_panel.set_status(False)
            self.feedback_label.setText('Video loaded. Assign keys, then press Play or Space to score.')
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to load video: {e}')
            logging.error(f'Failed to load video: {e}')

    def play_video(self):
        try:
            if not self.video_path:
                QMessageBox.warning(self, 'No Video', 'Please load a video first.')
                return
            start_frame = self.paused_frame if self.paused_frame is not None else 0
            self.video_thread = VideoThread(self.video_path, self.playback_speed, self.fps, start_frame, self.annotations)
            self.video_thread.change_pixmap_signal.connect(self.update_image)
            self.video_thread.update_slider_signal.connect(self.update_slider)
            self.video_thread.video_ended_signal.connect(self.on_video_end)
            self.video_thread.start()
            self.scoring_timer.start(50)
            self.scoring = True
            self.live_panel.set_status(True)
            self.feedback_label.setText('Scoring in progress... hold a behaviour key to record.')
            logging.info('Video playback started.')
            self.paused_frame = None
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to start video: {e}')
            logging.error(f'Failed to start video: {e}')

    def pause_video(self):
        try:
            if self.video_thread:
                if self.video_thread.isRunning():
                    self.paused_frame = self.video_thread.current_frame
                    self.video_thread.stop()
                    self.scoring_timer.stop()
                    self.scoring = False
                    self.live_panel.set_status(False)
                    self.feedback_label.setText('Paused.')
                    logging.info('Video paused.')
                else:
                    self.play_video()
            else:
                self.play_video()
        except Exception as e:
            logging.error(f'Error pausing video: {e}')

    def stop_video(self):
        try:
            if self.video_thread:
                self.video_thread.stop()
                self.video_thread = None
            self.scoring_timer.stop()
            self.scoring = False
            self.live_panel.set_status(False)
            self.paused_frame = 0
            self.video_slider.setValue(0)
            self.update_timestamp(0, self.total_duration)
            self.update_video_display(0)
            self.feedback_label.setText('Stopped.')
            logging.info('Video stopped.')
        except Exception as e:
            logging.error(f'Error stopping video: {e}')

    def on_video_end(self):
        try:
            self.scoring_timer.stop()
            self.scoring = False
            self.live_panel.set_status(False)
            self.feedback_label.setText('Video ended.')
            logging.info('Video ended.')
        except Exception as e:
            logging.error(f'Error handling video end: {e}')

    def update_image(self, qt_image):
        try:
            self.video_widget.update_image(qt_image)
        except Exception as e:
            logging.error(f'Error updating image: {e}')

    def change_playback_speed(self):
        try:
            speed_text = self.speed_dropdown.currentText()
            self.playback_speed = float(speed_text.replace('x', ''))
            self.playback_speed = max(0.1, min(8.0, self.playback_speed))
            if self.video_thread and self.video_thread.isRunning():
                self.video_thread.set_speed(self.playback_speed)
            logging.info(f'Playback speed set to {self.playback_speed}x.')
        except Exception as e:
            logging.error(f'Error changing playback speed: {e}')

    def set_video_position(self, position):
        try:
            if not self.fps:
                return
            position = int(position)
            if self.video_thread and self.video_thread.isRunning():
                if 0 <= position <= self.video_slider.maximum():
                    self.video_thread.seek_signal.emit(position)
                    self.paused_frame = position
                    self.video_slider.setValue(position)
                    self.update_timestamp(position / self.fps)
                    self.timeline_widget.set_current_time(position / self.fps)
                    self.update_video_display(position)
                else:
                    QMessageBox.warning(self, 'Invalid Position', 'The selected position is out of range.')
                    logging.warning(f'Set video position out of range: {position}')
            else:
                if 0 <= position <= self.video_slider.maximum():
                    self.paused_frame = position
                    self.video_slider.setValue(position)
                    self.update_timestamp(position / self.fps)
                    self.timeline_widget.set_current_time(position / self.fps)
                    self.update_video_display(position)
                else:
                    QMessageBox.warning(self, 'Invalid Position', 'The selected position is out of range.')
                    logging.warning(f'Set video position out of range: {position}')
        except Exception as e:
            logging.error(f'Error setting video position: {e}')

    def update_video_display(self, frame_number=None):
        try:
            if not self.video_path:
                return
            if frame_number is None:
                frame_number = self.paused_frame or 0
            cap = cv2.VideoCapture(self.video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))
            ret, cv_img = cap.read()
            if ret:
                rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                frame_time = frame_number / self.fps if self.fps else 0.0
                for annotation in self.annotations:
                    if annotation['start_time'] <= frame_time <= annotation['end_time']:
                        behaviour = annotation['behaviour']
                        color = annotation.get('color', (255, 0, 0))
                        cv2.putText(rgb_image, behaviour, (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                                    1.5, color, 3, cv2.LINE_AA)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.video_widget.update_image(qt_image)
            self.video_widget.update()
            if self.fps:
                self.timeline_widget.set_current_time((frame_number or 0) / self.fps)
            cap.release()
        except Exception as e:
            logging.error(f'Error updating video display: {e}')

    def update_slider(self, position):
        try:
            self.video_slider.blockSignals(True)
            self.video_slider.setValue(int(position))
            self.video_slider.blockSignals(False)
            current_time = (int(position) / self.fps) if self.fps else 0.0
            total_time = (self.video_slider.maximum() / self.fps) if self.fps else 0.0
            self.update_timestamp(current_time, total_time)
            self.timeline_widget.set_current_time(current_time)
        except Exception as e:
            logging.error(f'Error updating slider: {e}')

    def update_timestamp(self, current_time, total_time=None):
        try:
            if total_time is None:
                total_time = (self.video_slider.maximum() / self.fps) if self.fps else 0.0
            self.timestamp_label.setText(f'{self.format_time(current_time)} / {self.format_time(total_time)}')
        except Exception as e:
            logging.error(f'Error updating timestamp: {e}')

    def _accurate_video_time(self):
        try:
            if self.video_thread and self.video_thread.isRunning() and self.fps:
                return self.video_thread.current_frame / self.fps
            return (self.video_slider.value() / self.fps) if self.fps else 0.0
        except Exception:
            return (self.video_slider.value() / self.fps) if self.fps else 0.0

    def format_time(self, seconds):
        try:
            seconds = float(seconds)
            millis = int((seconds - int(seconds)) * 1000)
            seconds = int(seconds)
            mins, secs = divmod(seconds, 60)
            hours, mins = divmod(mins, 60)
            return f'{hours:02}:{mins:02}:{secs:02}.{millis:03}'
        except Exception as e:
            logging.error(f'Error formatting time: {e}')
            return '00:00:00.000'

    def open_assign_dialog(self):
        try:
            dialog = AssignKeyDialog(self)
            if dialog.exec_():
                self.scoring_keys = dialog.behaviour_keys
                self.update_behaviour_labels()
                self.update_frequency_controls()
                self.config.save_settings(self.scoring_keys)
                logging.info('Scoring keys updated.')
        except Exception as e:
            logging.error(f'Error opening assign dialog: {e}')

    def update_behaviour_labels(self):
        try:
            self.live_panel.rebuild(
                self.scoring_keys, self.time_spent, self.frequency_counts, self.format_time
            )
        except Exception as e:
            logging.error(f'Error updating behaviour labels: {e}')

    def update_frequency_controls(self):
        try:
            for i in reversed(range(self.frequency_layout.count())):
                widget = self.frequency_layout.itemAt(i).widget()
                if widget and widget != self.global_frequency_checkbox:
                    self.frequency_layout.removeWidget(widget)
                    widget.deleteLater()
            self.frequency_checkboxes = {}
            for behaviour in self.scoring_keys.keys():
                checkbox = QCheckBox(behaviour)
                checkbox.setChecked(True)
                self.frequency_layout.addWidget(checkbox)
                self.frequency_checkboxes[behaviour] = checkbox
        except Exception as e:
            logging.error(f'Error updating frequency controls: {e}')

    def toggle_global_frequency(self, state):
        try:
            enabled = state == Qt.Checked
            for checkbox in getattr(self, 'frequency_checkboxes', {}).values():
                checkbox.setChecked(enabled)
        except Exception as e:
            logging.error(f'Error toggling global frequency: {e}')

    def start_new_phase(self):
        try:
            text, ok = QInputDialog.getText(self, 'New Phase', 'Enter the name of the new phase:')
            if ok and text:
                phase_name = text.strip()
                if phase_name in self.phase_colors:
                    QMessageBox.warning(self, 'Duplicate Phase', 'A phase with this name already exists.')
                    return
                color = QColorDialog.getColor(self.phase_colors.get(self.current_phase, QColor("#ffffff")), self, 'Select Phase Colour')
                if color.isValid():
                    self.phase_colors[phase_name] = color
                    self.current_phase = phase_name
                    self.history_panel.add_action(f'New phase started: {phase_name}')
                    logging.info(f'New phase started: {phase_name}')
                else:
                    QMessageBox.warning(self, 'Invalid Colour', 'Please select a valid colour.')
        except Exception as e:
            logging.error(f'Error starting new phase: {e}')

    def select_phase_color(self):
        try:
            color = QColorDialog.getColor(self.phase_colors.get(self.current_phase, QColor("#ffffff")), self, 'Select Phase Colour')
            if color.isValid():
                self.phase_colors[self.current_phase] = color
                logging.info(f'Phase colour updated for {self.current_phase}')
        except Exception as e:
            logging.error(f'Error selecting phase colour: {e}')

    def show_time_spent(self):
        try:
            if not self.time_spent:
                QMessageBox.information(self, 'No Data', 'No time has been recorded yet.')
                return
            total_seconds = sum(float(v) for v in self.time_spent.values())
            rows = []
            for behaviour, secs in sorted(self.time_spent.items(), key=lambda x: -x[1]):
                rows.append({
                    'behaviour': behaviour,
                    'seconds': float(secs),
                    'count': int(self.frequency_counts.get(behaviour, 0))
                })
            dlg = TimeSpentDialog(self, rows, total_seconds)
            dlg.exec_()
        except Exception as e:
            logging.error(f'Error showing time spent: {e}')
            QMessageBox.warning(self, 'Error', f'Failed to show time spent: {e}')

    def update_timers(self):
        try:
            now = self._accurate_video_time()
            # While a behaviour key is held, show its live elapsed time in the panel.
            for combined_key in list(self.key_states.keys()):
                start = self.last_key_times.get(combined_key)
                if start is None:
                    continue
                elapsed = max(0.0, now - start)
                for behaviour, assigned_key in self.scoring_keys.items():
                    if assigned_key == combined_key:
                        self.live_panel.set_live_elapsed(behaviour, elapsed)
                        break
        except Exception as e:
            logging.error(f'Error updating timers: {e}')

    def get_video_time(self):
        return self._accurate_video_time()

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)

    def undo_last_event(self):
        try:
            if not self.behaviour_events:
                QMessageBox.information(self, 'Undo', 'No scored behaviours to undo.')
                return
            ev = self.behaviour_events.pop()
            self.redo_stack.append(ev)
            b = ev['behaviour']
            dur = float(ev.get('duration', 0.0))
            self.time_spent[b] = max(0.0, self.time_spent.get(b, 0.0) - dur)
            if b in self.frequency_counts and self.frequency_counts[b] > 0:
                self.frequency_counts[b] -= 1
            self.update_behaviour_label(b)
            for i in range(len(self.annotations) - 1, -1, -1):
                a = self.annotations[i]
                if (a.get('behaviour') == b and
                    abs(a.get('start_time', -1) - ev['start_time']) < 1e-3 and
                    abs(a.get('end_time', -1) - ev['end_time']) < 1e-3):
                    self.annotations.pop(i)
                    break
            self.timeline_widget.update_events(self.get_all_behaviour_events())
            if self.video_thread and self.video_thread.isRunning():
                self.video_thread.stop()
            self.scoring_timer.stop()
            self.scoring = False
            start_frame = int(round(ev['start_time'] * self.fps)) if self.fps else 0
            self.paused_frame = start_frame
            self.video_slider.setValue(start_frame)
            self.update_timestamp(ev['start_time'])
            self.timeline_widget.set_current_time(ev['start_time'])
            self.update_video_display(start_frame)
            msg = f"Undid '{b}'. Rewound to {self.format_time(ev['start_time'])}."
            self.feedback_label.setText(msg)
            self.history_panel.add_action(f'UNDO {b} at {self.format_time(ev["start_time"])}')
            logging.info(msg)
        except Exception as e:
            logging.error(f'Error during undo: {e}')
            QMessageBox.warning(self, 'Error', f'Failed to undo: {e}')

    def redo_last_event(self):
        try:
            if not self.redo_stack:
                QMessageBox.information(self, 'Redo', 'Nothing to redo.')
                return
            ev = self.redo_stack.pop()
            b = ev['behaviour']
            self.behaviour_events.append(ev)
            self.time_spent[b] = self.time_spent.get(b, 0.0) + float(ev.get('duration', 0.0))
            self.frequency_counts[b] = self.frequency_counts.get(b, 0) + 1
            self.update_behaviour_label(b)
            self.annotations.append({
                'behaviour': b,
                'start_time': ev['start_time'],
                'end_time': ev['end_time'],
                'color': self.phase_colors.get(ev.get('phase', 'Default Phase'), QColor("#ffffff")).getRgb()[:3]
            })
            self.timeline_widget.update_events(self.get_all_behaviour_events())
            self.history_panel.add_action(f'REDO {b} at {self.format_time(ev["start_time"])}')
            self.feedback_label.setText(f"Redid '{b}'.")
            logging.info(f"Redid '{b}'.")
        except Exception as e:
            logging.error(f'Error during redo: {e}')
            QMessageBox.warning(self, 'Error', f'Failed to redo: {e}')

    def eventFilter(self, source, event):
        if self.focusWidget() and isinstance(self.focusWidget(), QLineEdit):
            return False
        if QApplication.activeModalWidget():
            return False
        if event.type() == QEvent.KeyPress:
            if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Z:
                self.undo_last_event()
                return True
            if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Y:
                self.redo_last_event()
                return True
            if event.key() == Qt.Key_Space:
                if self.video_thread and self.video_thread.isRunning():
                    self.pause_video()
                else:
                    self.play_video()
                return True
            if event.key() == Qt.Key_P:
                if self.scoring:
                    self.start_new_phase()
                return True
            if self.scoring:
                if event.isAutoRepeat():
                    return True
                key = event.key()
                modifiers = int(event.modifiers())
                combined_key = key + (modifiers << 16)
                if combined_key in self.scoring_keys.values() and combined_key not in self.key_states:
                    self.key_states[combined_key] = True
                    self.last_key_times[combined_key] = self._accurate_video_time()
                    self.highlight_behaviour_label(combined_key, True)
            return True
        elif event.type() == QEvent.KeyRelease:
            if self.scoring:
                if event.isAutoRepeat():
                    return True
                key = event.key()
                modifiers = int(event.modifiers())
                combined_key = key + (modifiers << 16)
                if combined_key in self.scoring_keys.values() and combined_key in self.key_states:
                    start_time = self.last_key_times.pop(combined_key)
                    end_time = self._accurate_video_time()
                    duration = max(0.0, end_time - start_time)
                    behaviour = None
                    for b, assigned_key in self.scoring_keys.items():
                        if assigned_key == combined_key:
                            behaviour = b
                            event_record = {
                                'phase': self.current_phase,
                                'behaviour': behaviour,
                                'start_time': start_time,
                                'end_time': end_time,
                                'duration': duration
                            }
                            self.behaviour_events.append(event_record)
                            self.undo_stack.append(event_record)
                            self.redo_stack.clear()
                            self.time_spent[behaviour] = self.time_spent.get(behaviour, 0.0) + duration
                            self.frequency_counts[behaviour] = self.frequency_counts.get(behaviour, 0) + 1
                            self.update_behaviour_label(behaviour)
                            self.history_panel.add_action(
                                f'Added {behaviour}: {self.format_time(start_time)} to {self.format_time(end_time)}'
                            )
                            break
                    if behaviour:
                        self.highlight_behaviour_label(combined_key, False)
                        self.timeline_widget.update_events(self.get_all_behaviour_events())
                        self.annotations.append({
                            'behaviour': behaviour,
                            'start_time': start_time,
                            'end_time': end_time,
                            'color': self.phase_colors.get(self.current_phase, QColor("#ffffff")).getRgb()[:3]
                        })
                    self.key_states.pop(combined_key, None)
            return True
        return super().eventFilter(source, event)

    def highlight_behaviour_label(self, combined_key, highlight):
        try:
            for behaviour, assigned_key in self.scoring_keys.items():
                if assigned_key == combined_key:
                    self.live_panel.set_active(behaviour, highlight)
                    break
        except Exception as e:
            logging.error(f'Error highlighting behaviour label: {e}')

    def update_behaviour_label(self, behaviour):
        try:
            if behaviour in self.scoring_keys:
                self.live_panel.update_stats(
                    behaviour,
                    self.scoring_keys[behaviour],
                    self.format_time(self.time_spent.get(behaviour, 0.0)),
                    self.frequency_counts.get(behaviour, 0)
                )
        except Exception as e:
            logging.error(f'Error updating behaviour label: {e}')

    def load_scoring_csv(self):
        try:
            options = QFileDialog.Options()
            file_name, _ = QFileDialog.getOpenFileName(self, 'Open Scoring CSV', '', 'CSV Files (*.csv);;All Files (*)', options=options)
            if file_name:
                df = pd.read_csv(file_name)
                self.behaviour_events = []
                self.time_spent = {}
                self.frequency_counts = {}
                for _, row in df.iterrows():
                    event = {
                        'phase': row.get('Phase', 'Default Phase'),
                        'behaviour': row['Behaviour'],
                        'start_time': self.parse_time_to_seconds(row['Start Time']),
                        'end_time': self.parse_time_to_seconds(row['End Time']),
                        'duration': float(row['Duration (s)'])
                    }
                    self.behaviour_events.append(event)
                    b = event['behaviour']
                    self.time_spent[b] = self.time_spent.get(b, 0.0) + event['duration']
                    self.frequency_counts[b] = self.frequency_counts.get(b, 0) + 1
                self.update_behaviour_labels()
                self.update_frequency_controls()
                self.timeline_widget.update_events(self.get_all_behaviour_events())
                QMessageBox.information(self, 'Loaded', 'Scoring CSV loaded successfully.')
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to load CSV: {e}')
            logging.error(f'Failed to load scoring CSV: {e}')

    def save_scoring_csv(self):
        try:
            options = QFileDialog.Options()
            file_name, _ = QFileDialog.getSaveFileName(self, 'Save Scoring CSV', '', 'CSV Files (*.csv);;All Files (*)', options=options)
            if file_name:
                if not file_name.lower().endswith('.csv'):
                    file_name += '.csv'
                self.write_csv(file_name)
                QMessageBox.information(self, 'Saved', f'Scoring CSV saved to {file_name}')
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to save CSV: {e}')
            logging.error(f'Failed to save scoring CSV: {e}')

    def write_csv(self, file_name):
        try:
            with open(file_name, 'w', newline='', encoding='utf-8') as csvfile:
                columns = ['Phase', 'Behaviour', 'Start Time', 'End Time', 'Duration (s)']
                csvfile.write(','.join(columns) + NL)
                for event in self.behaviour_events:
                    row = [
                        event.get('phase', 'Default Phase'),
                        event['behaviour'],
                        self.format_time(event['start_time']),
                        self.format_time(event['end_time']),
                        str(round(event['duration'], 3))
                    ]
                    csvfile.write(','.join(row) + NL)
        except Exception as e:
            logging.error(f'Error writing CSV: {e}')

    def export_excel(self):
        try:
            options = QFileDialog.Options()
            file_name, _ = QFileDialog.getSaveFileName(self, 'Export to Excel', '', 'Excel Files (*.xlsx);;All Files (*)', options=options)
            if not file_name:
                return
            if not file_name.lower().endswith('.xlsx'):
                file_name += '.xlsx'
            try:
                with pd.ExcelWriter(file_name, engine='xlsxwriter') as writer:
                    self._write_excel_sheets(writer)
            except Exception:
                with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
                    self._write_excel_sheets(writer)
            QMessageBox.information(self, 'Exported', f'Exported to {file_name}')
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to export Excel: {e}')
            logging.error(f'Failed to export Excel: {e}')

    def _write_excel_sheets(self, writer):
        summary_data = []
        for behaviour, t in self.time_spent.items():
            summary_data.append({
                'Behaviour': behaviour,
                'Time Spent (s)': round(t, 3),
                'Count': self.frequency_counts.get(behaviour, 0)
            })
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        event_data = []
        for event in self.behaviour_events:
            event_data.append({
                'Phase': event.get('phase', 'Default Phase'),
                'Behaviour': event['behaviour'],
                'Start Time': self.format_time(event['start_time']),
                'End Time': self.format_time(event['end_time']),
                'Duration (s)': round(event['duration'], 3)
            })
        events_df = pd.DataFrame(event_data)
        events_df.to_excel(writer, sheet_name='Detailed_Events', index=False)

    def get_all_behaviour_events(self):
        return self.behaviour_events

    def new_session(self):
        try:
            if not self.video_path:
                QMessageBox.warning(self, 'No Video', 'Please load a video before creating a session.')
                return
            dlg = NewSessionDialog(self, default_name=self._default_session_name())
            if not dlg.exec_():
                return
            name = dlg.session_name() or self._default_session_name()
            mode = dlg.mode()

            # Stop playback and preserve the current session.
            if self.video_thread and self.video_thread.isRunning():
                self.video_thread.stop()
            self.scoring_timer.stop()
            self.scoring = False
            self.live_panel.set_status(False)
            self._capture_active_into_session()

            snap = self._make_session_snapshot(name)
            if mode == 'copy' and 0 <= self.active_session_index < len(self.sessions):
                src = self.sessions[self.active_session_index]
                snap['behaviour_events'] = [dict(e) for e in src['behaviour_events']]
                snap['time_spent'] = dict(src['time_spent'])
                snap['frequency_counts'] = dict(src['frequency_counts'])
                snap['annotations'] = [dict(a) for a in src['annotations']]
                snap['current_phase'] = src['current_phase']
                snap['phase_colors'] = dict(src['phase_colors'])
                # A copied session keeps its scores but starts a clean undo history.

            self.sessions.append(snap)
            new_index = len(self.sessions) - 1
            self._apply_session(new_index)
            self._refresh_session_dropdown()

            # Rewind the video to the start for the new pass.
            self.paused_frame = 0
            self.video_slider.setValue(0)
            self.update_timestamp(0, self.total_duration)
            self.update_video_display(0)
            origin = 'copied from the previous session' if mode == 'copy' else 'empty, rewound to 0'
            self.feedback_label.setText(
                f"Started '{name}' ({origin}). Previous sessions remain in the dropdown."
            )
            self.history_panel.add_action(f'--- New session: {name} ({mode}) ---')
            logging.info(f"New session '{name}' created (mode={mode}).")
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Failed to create session: {e}')
            logging.error(f'Failed to create session: {e}')

    def parse_time_to_seconds(self, time_str):
        try:
            if isinstance(time_str, (int, float)):
                return float(time_str)
            hms, _, ms = str(time_str).partition('.')
            h, m, s = [int(x) for x in hms.split(':')]
            ms = int((ms + '000')[:3])
            return h * 3600 + m * 60 + s + ms / 1000.0
        except Exception as e:
            logging.error(f'Error parsing time: {e}')
            return 0.0

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in ['.avi', '.mp4', '.mov', '.mkv']:
                        self.load_video(file_path)
                        break
        except Exception as e:
            logging.error(f'Error handling drop event: {e}')

    def autosave_session(self):
        try:
            if self.behaviour_events:
                autosave_path = 'autosave_rms.csv'
                self.write_csv(autosave_path)
                logging.info(f'Autosaved {len(self.behaviour_events)} events to {autosave_path}.')
            else:
                logging.info('Autosave heartbeat — no events to save.')
        except Exception as e:
            logging.error(f'Autosave error: {e}')

    def closeEvent(self, event):
        try:
            if self.video_thread and self.video_thread.isRunning():
                self.video_thread.stop()
        except Exception:
            pass
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BehaviourScoringApp()
    window.show()
    sys.exit(app.exec_())
