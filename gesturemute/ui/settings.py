"""Tabbed settings panel for GestureMute configuration."""

import sys

from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal

from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class NonScrollableComboBox(QComboBox):
    """QComboBox that ignores mouse wheel events to prevent accidental scrolling."""

    def wheelEvent(self, event):
        event.ignore()


class NonScrollableSlider(QSlider):
    """QSlider that ignores mouse wheel events to prevent accidental value changes."""

    def wheelEvent(self, event):
        event.ignore()


class NonScrollableSpinBox(QSpinBox):
    """QSpinBox that ignores mouse wheel events to prevent accidental value changes."""

    def wheelEvent(self, event):
        event.ignore()


from gesturemute.config import Config
from gesturemute.ui.theme import (
    ACCENT, ACCENT_LIGHT, BACKGROUND, SURFACE,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    COLOR_LIVE, BORDER_COLOR, INPUT_BG, FONT_FAMILY,
)

_STYLESHEET = f"""
    QWidget {{
        background-color: {SURFACE};
        color: {TEXT_SECONDARY};
        font-family: {FONT_FAMILY};
        font-size: 13px;
    }}
    QTabWidget::pane {{
        border: none;
        border-top: 1px solid {BORDER_COLOR};
        background-color: {SURFACE};
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {TEXT_DIM};
        padding: 10px 20px;
        border: none;
        border-bottom: 2px solid transparent;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        color: {TEXT_SECONDARY};
        border-bottom: 2px solid {ACCENT};
    }}
    QPushButton {{
        padding: 8px 18px;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.08);
        background-color: transparent;
        color: {TEXT_DIM};
        font-weight: 500;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {INPUT_BG};
        color: {TEXT_SECONDARY};
    }}
    QPushButton#cancelBtn {{
        background-color: {INPUT_BG};
        color: {TEXT_MUTED};
        border: 1px solid rgba(255,255,255,0.08);
    }}
    QPushButton#saveBtn {{
        background-color: {ACCENT};
        color: #FFFFFF;
        border: none;
        font-weight: 600;
        font-size: 13px;
    }}
    QPushButton#saveBtn:hover {{
        background-color: {ACCENT_LIGHT};
    }}
    QPushButton#previewBtn {{
        background-color: rgba(99, 102, 241, 0.12);
        color: {ACCENT_LIGHT};
        border: 1px solid rgba(99, 102, 241, 0.25);
        font-weight: 600;
        font-size: 13px;
    }}
    QPushButton#previewBtn:hover {{
        background-color: rgba(99, 102, 241, 0.22);
        color: #FFFFFF;
        border: 1px solid rgba(99, 102, 241, 0.4);
    }}
    QComboBox, QLineEdit {{
        background-color: {INPUT_BG};
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 8px 12px;
        color: {TEXT_SECONDARY};
    }}
    QSpinBox {{
        background: transparent;
        border: none;
        padding: 0px 4px;
        color: {TEXT_SECONDARY};
        font-size: 13px;
    }}
    QSpinBox QLineEdit {{
        selection-background-color: transparent;
        selection-color: {TEXT_SECONDARY};
        border: none;
        outline: none;
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        background-color: rgba(255,255,255,0.08);
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        width: 16px;
        height: 16px;
        margin: -5px 0;
        background-color: #FFFFFF;
        border-radius: 8px;
    }}
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {ACCENT}, stop:1 {ACCENT_LIGHT});
        border-radius: 3px;
    }}
    QToolButton {{
        border: none;
        font-weight: 600;
        font-size: 13px;
        text-align: left;
        padding: 12px 14px;
        color: {TEXT_SECONDARY};
        background-color: rgba(255,255,255,0.02);
        border-radius: 10px;
    }}
    QWidget#settingsCard {{
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 12px;
    }}
    QLabel#kbdBadge {{
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 600;
        font-family: 'Consolas', 'SF Mono', monospace;
        color: {TEXT_MUTED};
    }}
"""


class CollapsibleSection(QWidget):
    """A section with a clickable header that toggles content visibility."""

    def __init__(self, title: str, parent: QWidget | None = None, collapsed: bool = False) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "CollapsibleSection { background: rgba(255,255,255,0.02);"
            "border: 1px solid rgba(255,255,255,0.05);"
            "border-radius: 10px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toggle_btn = QToolButton()
        self._toggle_btn.setText(f"  \u25BC  {title}")
        self._toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self._toggle_btn)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(14, 4, 14, 14)
        layout.addWidget(self._content)

        self._expanded = True
        self._title = title

        if collapsed:
            self._expanded = False
            self._content.setVisible(False)
            self._toggle_btn.setText(f"  \u25B6  {title}")

    def content_layout(self) -> QVBoxLayout:
        """Return the layout for adding child widgets."""
        return self._content_layout

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        arrow = "\u25BC" if self._expanded else "\u25B6"
        self._toggle_btn.setText(f"  {arrow}  {self._title}")


class _CameraProbeWorker(QThread):
    """Background worker that probes webcam indices for available cameras."""

    cameras_found = pyqtSignal(list)

    def run(self) -> None:
        """Probe cameras and emit list of (opencv_index, name, unique_id) tuples.

        Uses fingerprinting to find the correct OpenCV index for each
        AVFoundation device, since the two APIs can enumerate in different orders.
        """
        import cv2
        from gesturemute.camera.enumerate import (
            find_opencv_index_for_device,
            is_iphone_camera,
            list_cameras_full,
        )

        cameras = list_cameras_full()

        # On macOS, AVFoundation gives us the real camera list.
        # On other platforms (empty list), fall back to probing indices 0-4.
        if cameras:
            available: list[tuple[int, str, str]] = []
            for _avf_idx, name, uid in cameras:
                if is_iphone_camera(name):
                    continue
                # Find the real OpenCV index via fingerprinting
                opencv_idx = find_opencv_index_for_device(uid)
                if opencv_idx is not None:
                    available.append((opencv_idx, name, uid))
            self.cameras_found.emit(available)
        else:
            available = []
            for i in range(5):
                try:
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        available.append((i, f"Camera {i}", ""))
                    cap.release()
                except Exception:
                    continue
            self.cameras_found.emit(available)


class SettingsPanel(QWidget):
    """Tabbed settings UI for GestureMute configuration.

    Signals:
        settings_saved: Emitted with a new Config when the user clicks Save.
    """

    settings_saved = pyqtSignal(object)
    preview_requested = pyqtSignal()
    onboarding_requested = pyqtSignal()

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._drag_pos: QPoint | None = None
        self._dirty = False
        self.setWindowTitle("GestureMute Settings")
        self.setFixedSize(420, 720)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.setStyleSheet(_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Custom header with decorative dots
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(
            f"background-color: {SURFACE};"
            f"border-bottom: 1px solid {BORDER_COLOR};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        self._is_maximized = False

        close_btn = QPushButton()
        close_btn.setFixedSize(12, 12)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background-color: #EF4444; border-radius: 6px; border: none;"
            " padding: 0; min-width: 12px; min-height: 12px; }"
            "QPushButton:hover { background-color: #F87171; }"
        )
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        minimize_btn = QPushButton()
        minimize_btn.setFixedSize(12, 12)
        minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        minimize_btn.setStyleSheet(
            "QPushButton { background-color: #F59E0B; border-radius: 6px; border: none;"
            " padding: 0; min-width: 12px; min-height: 12px; }"
            "QPushButton:hover { background-color: #FBBF24; }"
        )
        minimize_btn.clicked.connect(self.showMinimized)
        header_layout.addWidget(minimize_btn)

        maximize_btn = QPushButton()
        maximize_btn.setFixedSize(12, 12)
        maximize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        maximize_btn.setStyleSheet(
            "QPushButton { background-color: #22C55E; border-radius: 6px; border: none;"
            " padding: 0; min-width: 12px; min-height: 12px; }"
            "QPushButton:hover { background-color: #4ADE80; }"
        )
        maximize_btn.clicked.connect(self._toggle_maximize)
        header_layout.addWidget(maximize_btn)

        header_layout.addStretch()
        title_label = QLabel("Settings")
        title_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {TEXT_MUTED};"
            " background: transparent; border: none;"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        # Spacer to balance the dots
        spacer = QWidget()
        spacer.setFixedWidth(44)
        spacer.setStyleSheet("background: transparent; border: none;")
        header_layout.addWidget(spacer)

        root.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_gestures_tab(), "Gestures")
        self._tabs.addTab(self._build_about_tab(), "About")
        root.addWidget(self._tabs)

        # Button row
        btn_container = QWidget()
        btn_container.setStyleSheet(
            f"border-top: 1px solid {BORDER_COLOR}; background: transparent;"
        )
        btn_row = QHBoxLayout(btn_container)
        btn_row.setContentsMargins(20, 12, 20, 12)

        reset_btn = QPushButton("Reset Defaults")
        reset_btn.clicked.connect(self._on_reset_defaults)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        root.addWidget(btn_container)

        # Track dirty state on all editable widgets
        self._connect_dirty_tracking()

    def _mark_dirty(self) -> None:
        """Mark the settings as having unsaved changes."""
        self._dirty = True

    def _connect_dirty_tracking(self) -> None:
        """Connect change signals on all editable widgets to _mark_dirty."""
        self._camera_combo.currentIndexChanged.connect(self._mark_dirty)
        self._frame_skip_spin.valueChanged.connect(self._mark_dirty)
        self._camera_backend_combo.currentIndexChanged.connect(self._mark_dirty)
        self._toast_slider.valueChanged.connect(self._mark_dirty)
        self._overlay_style_combo.currentIndexChanged.connect(self._mark_dirty)
        self._volume_step_spin.valueChanged.connect(self._mark_dirty)
        self._cooldown_slider.valueChanged.connect(self._mark_dirty)
        self._activation_slider.valueChanged.connect(self._mark_dirty)
        self._no_hand_slider.valueChanged.connect(self._mark_dirty)
        self._grace_slider.valueChanged.connect(self._mark_dirty)
        self._sound_cues_check.toggled.connect(self._mark_dirty)
        self._adaptive_check.toggled.connect(self._mark_dirty)
        for slider, _ in self._conf_sliders.values():
            slider.valueChanged.connect(self._mark_dirty)

    # -- Tab builders --

    def _make_card(self) -> tuple[QWidget, QVBoxLayout]:
        """Create a styled card container widget.

        Returns:
            Tuple of (card widget, card inner layout).
        """
        card = QWidget()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(10)
        return card, card_layout

    def _make_section_label(self, text: str) -> QLabel:
        """Create a small section header label."""
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {TEXT_SECONDARY};"
            " background: transparent; border: none;"
        )
        return label

    def _make_description(self, text: str, indent: int = 0) -> QLabel:
        """Create a dim description label with optional left indent."""
        label = QLabel(text)
        label.setWordWrap(True)
        margin = f"margin-left: {indent}px;" if indent else ""
        label.setStyleSheet(
            f"font-size: 11px; color: {TEXT_DIM};"
            f" background: transparent; border: none; {margin}"
        )
        return label

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        inner = QVBoxLayout(tab)
        inner.setContentsMargins(20, 20, 20, 20)
        inner.setSpacing(12)

        # --- Card 1: Camera ---
        card, cl = self._make_card()
        cl.addWidget(self._make_section_label("Camera"))

        cam_row = QHBoxLayout()
        cam_row.setSpacing(8)
        self._camera_combo = NonScrollableComboBox()
        self._camera_combo.setToolTip("Which webcam to use if you have more than one")
        cam_row.addWidget(self._camera_combo, 1)
        self._camera_refresh_btn = QPushButton("\u27F3")
        self._camera_refresh_btn.setFixedSize(36, 36)
        self._camera_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._camera_refresh_btn.setToolTip("Scan for cameras")
        self._camera_refresh_btn.clicked.connect(self._probe_cameras)
        cam_row.addWidget(self._camera_refresh_btn)
        cl.addLayout(cam_row)

        cl.addWidget(self._make_description(
            "Try a different backend if your camera isn't detected"
        ))
        self._camera_backend_combo = NonScrollableComboBox()
        backends = ["auto"]
        if sys.platform == "win32":
            backends += ["dshow", "msmf"]
        elif sys.platform == "linux":
            backends += ["v4l2"]
        self._camera_backend_combo.addItems(backends)
        cl.addWidget(self._camera_backend_combo)

        preview_btn = QPushButton("Open Camera Preview")
        preview_btn.setObjectName("previewBtn")
        preview_btn.setToolTip("Live camera feed with gesture annotations")
        preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        preview_btn.clicked.connect(self.preview_requested.emit)
        cl.addWidget(preview_btn)

        inner.addWidget(card)

        # --- Card 2: Appearance ---
        card, cl = self._make_card()
        cl.addWidget(self._make_section_label("Appearance"))

        cl.addWidget(self._make_description(
            "How the status indicator appears on screen"
        ))
        self._overlay_style_combo = NonScrollableComboBox()
        self._overlay_style_combo.addItems(["Minimal Dot", "Pill with Label", "Glass Bar"])
        cl.addWidget(self._overlay_style_combo)

        cl.addWidget(self._make_description(
            "How long gesture notifications stay visible"
        ))
        toast_header = QHBoxLayout()
        toast_name = QLabel("Toast Duration")
        toast_name.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: #CBD5E1;"
            " background: transparent; border: none;"
        )
        toast_header.addWidget(toast_name)
        toast_header.addStretch()
        self._toast_slider, self._toast_label = self._create_slider(
            500, 5000, 100, "ms"
        )
        toast_header.addWidget(self._toast_label)
        cl.addLayout(toast_header)
        cl.addWidget(self._toast_slider)

        inner.addWidget(card)

        # --- Card 3: Feedback ---
        card, cl = self._make_card()
        cl.addWidget(self._make_section_label("Feedback"))

        self._sound_cues_check = QCheckBox("Sound cues")
        self._sound_cues_check.setStyleSheet(
            f"QCheckBox {{ font-size: 12px; color: #CBD5E1;"
            f" background: transparent; border: none; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; }}"
        )
        cl.addWidget(self._sound_cues_check)
        cl.addWidget(self._make_description(
            "Play short audio tones when mic state changes", indent=22
        ))

        inner.addWidget(card)

        # --- Card 4: Performance ---
        card, cl = self._make_card()
        cl.addWidget(self._make_section_label("Performance"))
        cl.addWidget(self._make_description(
            "Skip frames to reduce CPU usage. Auto mode adjusts dynamically."
        ))

        perf_row = QHBoxLayout()
        perf_row.setSpacing(8)
        self._adaptive_check = QCheckBox("Automatic")
        self._adaptive_check.setStyleSheet(
            f"QCheckBox {{ font-size: 12px; color: #CBD5E1;"
            f" background: transparent; border: none; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; }}"
        )
        perf_row.addWidget(self._adaptive_check)
        perf_row.addStretch()
        fs_container = self._create_spinbox(1, 10)
        self._frame_skip_spin = fs_container.spinbox
        self._frame_skip_spin.setToolTip("Trade responsiveness for lower CPU usage")
        self._adaptive_check.toggled.connect(
            lambda checked: fs_container.setEnabled(not checked)
        )
        perf_row.addWidget(fs_container)
        cl.addLayout(perf_row)

        inner.addWidget(card)

        # --- Hotkey row (no card) ---
        hotkey_row = QHBoxLayout()
        hotkey_label = QLabel("Global Hotkey")
        hotkey_label.setStyleSheet(
            f"font-size: 12px; color: {TEXT_DIM};"
            " background: transparent; border: none;"
        )
        hotkey_row.addWidget(hotkey_label)
        hotkey_row.addStretch()
        hotkey_badge = QLabel("Ctrl + Shift + G")
        hotkey_badge.setObjectName("kbdBadge")
        hotkey_row.addWidget(hotkey_badge)
        inner.addLayout(hotkey_row)

        inner.addStretch()

        # Wrap in scroll area
        scroll = QScrollArea()
        scroll.setWidget(tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        return scroll

    def _build_gestures_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Confidence section
        conf_section = CollapsibleSection("Confidence Thresholds", collapsed=True)
        cl = conf_section.content_layout()

        self._conf_sliders: dict[str, tuple[NonScrollableSlider, QLabel]] = {}
        for gesture_key, display in [
            ("Open_Palm", "\u270b Open Palm"),
            ("Closed_Fist", "\u270a Closed Fist"),
            ("Thumb_Up", "\U0001f44d Thumb Up"),
            ("Thumb_Down", "\U0001f44e Thumb Down"),
            ("Two_Fists_Close", "\u270a\u270a Two Fists Close"),
        ]:
            slider, label = self._create_slider(30, 95, 1, "%")
            slider.setToolTip(f"Minimum confidence to recognize {display}")
            self._conf_sliders[gesture_key] = (slider, label)
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 4, 0, 4)
            name_label = QLabel(f"{display}:")
            name_label.setStyleSheet("font-size: 12px; font-weight: 500; color: #CBD5E1;")
            name_label.setFixedWidth(120)
            row_l.addWidget(name_label)
            row_l.addWidget(slider, 1)
            row_l.addWidget(label)
            cl.addWidget(row_w)

        layout.addWidget(conf_section)

        # Timing section
        timing_section = CollapsibleSection("Timing", collapsed=True)
        tl = timing_section.content_layout()

        self._cooldown_slider, self._cooldown_label = self._create_slider(
            200, 2000, 50, "ms"
        )
        self._activation_slider, self._activation_label = self._create_slider(
            100, 1000, 50, "ms"
        )
        self._no_hand_slider, self._no_hand_label = self._create_slider(
            1000, 10000, 500, "ms"
        )
        self._grace_slider, self._grace_label = self._create_slider(
            100, 1000, 50, "ms"
        )

        for name, slider, label in [
            ("Cooldown:", self._cooldown_slider, self._cooldown_label),
            ("Activation:", self._activation_slider, self._activation_label),
            ("No-Hand:", self._no_hand_slider, self._no_hand_label),
            ("Grace:", self._grace_slider, self._grace_label),
        ]:
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 4, 0, 4)
            name_label = QLabel(name)
            name_label.setStyleSheet("font-size: 12px; font-weight: 500; color: #CBD5E1;")
            name_label.setFixedWidth(120)
            row_l.addWidget(name_label)
            row_l.addWidget(slider, 1)
            row_l.addWidget(label)
            tl.addWidget(row_w)

        # Volume step
        vol_w = QWidget()
        vol_l = QHBoxLayout(vol_w)
        vol_l.setContentsMargins(0, 0, 0, 0)
        vol_name = QLabel("Volume Step:")
        vol_name.setStyleSheet("font-size: 12px; font-weight: 500; color: #CBD5E1;")
        vol_name.setFixedWidth(120)
        vol_container = self._create_spinbox(1, 20, suffix="%")
        self._volume_step_spin = vol_container.spinbox
        vol_l.addWidget(vol_name)
        vol_l.addWidget(vol_container)
        vol_l.addStretch()
        tl.addWidget(vol_w)

        layout.addWidget(timing_section)
        layout.addStretch()

        return tab

    def _build_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # App icon placeholder (painted square with gradient)
        icon_frame = QLabel()
        icon_frame.setFixedSize(64, 64)
        icon_frame.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 rgba(99,102,241,0.15), stop:1 rgba(139,92,246,0.1));"
            "border: 1px solid rgba(99,102,241,0.15);"
            "border-radius: 16px;"
        )
        icon_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_frame.setText("\U0001f3a4")
        icon_frame.setStyleSheet(
            icon_frame.styleSheet() + "font-size: 28px;"
        )
        layout.addWidget(icon_frame, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(16)

        name = QLabel("GestureMute")
        name.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {TEXT_PRIMARY};")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        layout.addSpacing(4)

        version = QLabel("Version 1.0.0")
        version.setStyleSheet(f"font-size: 12px; color: {TEXT_DIM};")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        layout.addSpacing(16)

        desc = QLabel(
            "Hands-free microphone control via webcam gesture recognition.\n"
            "Built with Python, MediaPipe, and PyQt6."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; line-height: 1.6;")
        layout.addWidget(desc)
        layout.addSpacing(20)

        # Privacy badge
        privacy = QLabel(
            "\U0001f6e1 Privacy first. All processing happens locally.\n"
            "No frames are stored or transmitted."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet(
            f"background: rgba(16,185,129,0.06);"
            f"border: 1px solid rgba(16,185,129,0.1);"
            f"border-radius: 10px; padding: 12px 16px;"
            f"color: {COLOR_LIVE}; font-size: 12px;"
        )
        layout.addWidget(privacy)
        layout.addSpacing(16)

        link = QLabel(
            f'<a href="https://github.com/PKlauv/GestureMute" '
            f'style="color: {ACCENT}; text-decoration: none;">View on GitHub</a>'
        )
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(link)
        layout.addSpacing(16)

        # Re-run onboarding
        onboarding_btn = QPushButton("Re-run Setup Wizard")
        onboarding_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        onboarding_btn.clicked.connect(self._on_rerun_onboarding)
        layout.addWidget(onboarding_btn)

        layout.addStretch()
        return tab

    # -- Helpers --

    @staticmethod
    def _create_slider(
        min_val: int, max_val: int, step: int, suffix: str,
    ) -> tuple[NonScrollableSlider, QLabel]:
        """Create a horizontal slider with a value label.

        Args:
            min_val: Minimum slider value.
            max_val: Maximum slider value.
            step: Single step size.
            suffix: Text appended to the displayed value (e.g. "ms", "%").

        Returns:
            Tuple of (QSlider, QLabel) with the label auto-updating on value changes.
        """
        slider = NonScrollableSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setSingleStep(step)
        slider.setPageStep(step * 5)

        label = QLabel()
        label.setFixedWidth(55)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {ACCENT};"
        )

        def _update(val: int) -> None:
            snapped = round(val / step) * step
            if snapped != val:
                slider.setValue(snapped)
                return
            label.setText(f"{val}{suffix}")

        slider.valueChanged.connect(_update)
        _update(slider.value())
        return slider, label

    @staticmethod
    def _create_spinbox(
        min_val: int, max_val: int, suffix: str = "",
    ) -> QWidget:
        """Create a styled spinbox with custom -/+ buttons.

        Args:
            min_val: Minimum value.
            max_val: Maximum value.
            suffix: Optional suffix (e.g. "%").

        Returns:
            Container QWidget with a `.spinbox` attribute for value access.
        """
        container = QWidget()
        container.setFixedHeight(36)
        container.setStyleSheet(
            f"QWidget#spinContainer {{"
            f"  background-color: {INPUT_BG};"
            f"  border: 1px solid rgba(255,255,255,0.08);"
            f"  border-radius: 8px;"
            f"}}"
        )
        container.setObjectName("spinContainer")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        btn_style = (
            f"QPushButton {{ background: transparent; border: none;"
            f" color: {TEXT_MUTED}; font-size: 16px; font-weight: 600;"
            f" min-width: 28px; min-height: 10px; border-radius: 6px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.08);"
            f" color: {TEXT_SECONDARY}; }}"
        )

        minus_btn = QPushButton("\u2212")
        minus_btn.setFixedSize(28, 28)
        minus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        minus_btn.setStyleSheet(btn_style)
        layout.addWidget(minus_btn)

        spinbox = NonScrollableSpinBox()
        spinbox.setRange(min_val, max_val)
        if suffix:
            spinbox.setSuffix(suffix)
        spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinbox.setFixedHeight(28)
        spinbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(spinbox, 1)

        plus_btn = QPushButton("+")
        plus_btn.setFixedSize(28, 28)
        plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plus_btn.setStyleSheet(btn_style)
        layout.addWidget(plus_btn)

        def _step_and_deselect(step_fn):
            step_fn()
            spinbox.lineEdit().deselect()

        minus_btn.clicked.connect(lambda: _step_and_deselect(spinbox.stepDown))
        plus_btn.clicked.connect(lambda: _step_and_deselect(spinbox.stepUp))

        container.spinbox = spinbox  # type: ignore[attr-defined]
        return container

    def _populate_from_config(self) -> None:
        """Set all widget values from the stored config."""
        self._populate_from_config_obj(self._config)

    def _populate_from_config_obj(self, config: Config) -> None:
        """Set all widget values from the given config object."""
        c = config

        # General — camera combo selection deferred to _on_cameras_found
        self._pending_camera_index = c.camera_index
        self._pending_camera_name = c.camera_name
        self._pending_camera_uid = c.camera_unique_id
        # Select matching item if combo is already populated
        for i in range(self._camera_combo.count()):
            data = self._camera_combo.itemData(i)
            idx = data.get("idx") if isinstance(data, dict) else data
            if idx == c.camera_index:
                self._camera_combo.setCurrentIndex(i)
                break
        idx = self._camera_backend_combo.findText(c.camera_backend)
        self._camera_backend_combo.setCurrentIndex(max(idx, 0))
        self._frame_skip_spin.setValue(c.frame_skip)
        self._adaptive_check.setChecked(c.adaptive_frame_skip)
        self._toast_slider.setValue(c.toast_duration_ms)

        self._sound_cues_check.setChecked(c.sound_cues_enabled)

        # Overlay style
        style_idx = {"dot": 0, "pill": 1, "bar": 2}.get(c.overlay_style, 1)
        self._overlay_style_combo.setCurrentIndex(style_idx)

        # Confidence
        for key, (slider, _) in self._conf_sliders.items():
            val = c.confidence_thresholds.get(key, 0.7)
            slider.setValue(int(val * 100))

        # Timing
        self._cooldown_slider.setValue(c.gesture_cooldown_ms)
        self._activation_slider.setValue(c.activation_delay_ms)
        self._no_hand_slider.setValue(c.no_hand_timeout_ms)
        self._grace_slider.setValue(c.transition_grace_ms)
        self._volume_step_spin.setValue(c.volume_step)

    def _collect_to_config(self) -> Config:
        """Read all widget values into a new Config instance."""
        thresholds = {}
        for key, (slider, _) in self._conf_sliders.items():
            thresholds[key] = slider.value() / 100.0

        overlay_style = {0: "dot", 1: "pill", 2: "bar"}.get(
            self._overlay_style_combo.currentIndex(), "pill"
        )

        # Extract camera index, name, and unique_id from combo data
        combo_data = self._camera_combo.currentData()
        if isinstance(combo_data, dict):
            cam_idx = combo_data.get("idx", 0)
            cam_uid = combo_data.get("uid", None) or None
        else:
            cam_idx = combo_data if combo_data not in (None, -1) else 0
            cam_uid = None
        # Extract camera name from combo text (format: "Camera N — Name")
        cam_name = None
        combo_text = self._camera_combo.currentText()
        if " \u2014 " in combo_text:
            cam_name = combo_text.split(" \u2014 ", 1)[1]
        elif cam_idx is not None and cam_idx >= 0:
            from gesturemute.camera.enumerate import get_camera_name
            name = get_camera_name(cam_idx)
            if not name.startswith("Camera "):
                cam_name = name
        # Mark override if the user explicitly changed the camera selection
        cam_override = self._config.camera_user_override or (cam_idx != self._config.camera_index)

        return Config(
            camera_index=cam_idx,
            camera_name=cam_name,
            camera_unique_id=cam_uid,
            camera_backend=self._camera_backend_combo.currentText(),
            frame_skip=self._frame_skip_spin.value(),
            adaptive_frame_skip=self._adaptive_check.isChecked(),
            toast_duration_ms=self._toast_slider.value(),
            confidence_threshold=self._config.confidence_threshold,
            confidence_thresholds=thresholds,
            gesture_cooldown_ms=self._cooldown_slider.value(),
            activation_delay_ms=self._activation_slider.value(),
            no_hand_timeout_ms=self._no_hand_slider.value(),
            transition_grace_ms=self._grace_slider.value(),
            volume_step=self._volume_step_spin.value(),
            model_path=self._config.model_path,
            overlay_style=overlay_style,
            overlay_x=self._config.overlay_x,
            overlay_y=self._config.overlay_y,
            onboarding_completed=self._config.onboarding_completed,
            sound_cues_enabled=self._sound_cues_check.isChecked(),
            camera_user_override=cam_override,
        )

    def _probe_cameras(self) -> None:
        """Start a background scan for available cameras."""
        from gesturemute.camera.enumerate import invalidate_cache
        invalidate_cache()
        self._camera_combo.blockSignals(True)
        self._camera_combo.clear()
        self._camera_combo.addItem("Scanning...", -1)
        self._camera_combo.blockSignals(False)
        self._camera_combo.setEnabled(False)
        self._camera_refresh_btn.setEnabled(False)
        self._probe_worker = _CameraProbeWorker()
        self._probe_worker.cameras_found.connect(self._on_cameras_found)
        self._probe_worker.start()

    def _on_cameras_found(self, available: list[tuple[int, str, str]]) -> None:
        """Populate camera combo with discovered cameras and their names."""
        self._camera_combo.blockSignals(True)
        self._camera_combo.clear()
        self._camera_combo.setEnabled(True)
        self._camera_refresh_btn.setEnabled(True)

        if not available:
            self._camera_combo.addItem("No cameras found", {"idx": -1, "uid": ""})
            self._camera_combo.blockSignals(False)
            return

        pending = getattr(self, "_pending_camera_index", 0)
        available_indices = set()
        for idx, name, uid in available:
            available_indices.add(idx)
            label = f"Camera {idx} — {name}" if name != f"Camera {idx}" else f"Camera {idx}"
            self._camera_combo.addItem(label, {"idx": idx, "uid": uid})

        # Add configured camera as unavailable if not discovered
        if pending not in available_indices:
            self._camera_combo.addItem(
                f"Camera {pending} (unavailable)", {"idx": pending, "uid": ""},
            )

        # Select by unique ID first, then name, then index
        selected = False
        pending_uid = getattr(self, "_pending_camera_uid", None)
        pending_name = getattr(self, "_pending_camera_name", None)
        if pending_uid:
            for i in range(self._camera_combo.count()):
                data = self._camera_combo.itemData(i)
                if isinstance(data, dict) and data.get("uid") == pending_uid:
                    self._camera_combo.setCurrentIndex(i)
                    selected = True
                    break
        if not selected and pending_name:
            for i in range(self._camera_combo.count()):
                if pending_name in self._camera_combo.itemText(i):
                    self._camera_combo.setCurrentIndex(i)
                    selected = True
                    break
        if not selected:
            for i in range(self._camera_combo.count()):
                data = self._camera_combo.itemData(i)
                idx = data.get("idx") if isinstance(data, dict) else data
                if idx == pending:
                    self._camera_combo.setCurrentIndex(i)
                    break

        self._camera_combo.blockSignals(False)

    def _on_save(self) -> None:
        new_config = self._collect_to_config()
        self._config = new_config
        self._dirty = False
        self.settings_saved.emit(new_config)
        self.hide()

    def _on_cancel(self) -> None:
        if self._dirty and not self._confirm_discard():
            return
        self._populate_from_config()
        self._dirty = False
        self.hide()

    def _confirm_discard(self) -> bool:
        """Show a confirmation dialog for unsaved changes. Returns True to discard."""
        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return result == QMessageBox.StandardButton.Discard

    def _on_reset_defaults(self) -> None:
        self._populate_from_config_obj(Config())

    def _on_rerun_onboarding(self) -> None:
        """Launch the onboarding wizard modally from settings."""
        from gesturemute.ui.onboarding import OnboardingWizard
        wizard = OnboardingWizard(self)
        wizard.exec()

    def _toggle_maximize(self) -> None:
        """Toggle between maximized and normal window size."""
        if self._is_maximized:
            self.showNormal()
            self.setFixedSize(420, 720)
            self._is_maximized = False
            # Re-center on screen
            screen = self.screen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.x() + (geo.width() - self.width()) // 2
                y = geo.y() + (geo.height() - self.height()) // 2
                self.move(x, y)
        else:
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.showMaximized()
            self._is_maximized = True

    def update_config(self, config: Config) -> None:
        """Update the stored config (e.g. after external save)."""
        self._config = config

    def closeEvent(self, event) -> None:
        """Treat window close as Cancel, with unsaved changes warning."""
        if self._dirty and not self._confirm_discard():
            event.ignore()
            return
        self._populate_from_config()
        self._dirty = False
        event.accept()

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts: Escape=Cancel, Ctrl+S=Save."""
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel()
        elif event.key() == Qt.Key.Key_S and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._on_save()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        """Start drag on header area."""
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 48:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        """Move window while dragging."""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        """End drag."""
        self._drag_pos = None

    def show(self) -> None:
        """Populate from config, center on screen, and show."""
        self._populate_from_config()
        self._dirty = False
        self._probe_cameras()
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        super().show()
        self.raise_()
        self.activateWindow()
