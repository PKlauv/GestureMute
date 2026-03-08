"""Tabbed settings panel for GestureMute configuration."""

import sys

from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

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
    QSpinBox, QComboBox, QLineEdit {{
        background-color: {INPUT_BG};
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 8px 12px;
        color: {TEXT_SECONDARY};
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
"""


class CollapsibleSection(QWidget):
    """A section with a clickable header that toggles content visibility."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
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

    def content_layout(self) -> QVBoxLayout:
        """Return the layout for adding child widgets."""
        return self._content_layout

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        arrow = "\u25BC" if self._expanded else "\u25B6"
        self._toggle_btn.setText(f"  {arrow}  {self._title}")


class SettingsPanel(QWidget):
    """Tabbed settings UI for GestureMute configuration.

    Signals:
        settings_saved: Emitted with a new Config when the user clicks Save.
    """

    settings_saved = pyqtSignal(object)

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._drag_pos: QPoint | None = None
        self.setWindowTitle("GestureMute Settings")
        self.setFixedSize(420, 540)
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

        for color in ["#EF4444", "#F59E0B", "#22C55E"]:
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(
                f"background-color: {color}; border-radius: 6px; border: none;"
            )
            header_layout.addWidget(dot)

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

    # -- Tab builders --

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Camera Index + Frame Skip side-by-side
        row = QHBoxLayout()
        row.setSpacing(12)

        cam_group = QVBoxLayout()
        cam_label = QLabel("Camera Index")
        cam_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: #CBD5E1;")
        cam_group.addWidget(cam_label)
        self._camera_index_spin = QSpinBox()
        self._camera_index_spin.setRange(0, 9)
        self._camera_index_spin.setToolTip("OpenCV camera device index (0 = default)")
        cam_group.addWidget(self._camera_index_spin)
        row.addLayout(cam_group)

        fs_group = QVBoxLayout()
        fs_label = QLabel("Frame Skip")
        fs_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: #CBD5E1;")
        fs_group.addWidget(fs_label)
        self._frame_skip_spin = QSpinBox()
        self._frame_skip_spin.setRange(1, 10)
        self._frame_skip_spin.setToolTip("Process every Nth frame (higher = less CPU)")
        fs_group.addWidget(self._frame_skip_spin)
        row.addLayout(fs_group)

        layout.addLayout(row)

        # Camera Backend
        backend_label = QLabel("Camera Backend")
        backend_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: #CBD5E1;")
        layout.addWidget(backend_label)
        self._camera_backend_combo = QComboBox()
        backends = ["auto"]
        if sys.platform == "win32":
            backends += ["dshow", "msmf"]
        elif sys.platform == "linux":
            backends += ["v4l2"]
        self._camera_backend_combo.addItems(backends)
        layout.addWidget(self._camera_backend_combo)

        # Toast Duration slider
        toast_row = QHBoxLayout()
        toast_label = QLabel("Toast Duration")
        toast_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: #CBD5E1;")
        self._toast_label = QLabel()
        self._toast_label.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {ACCENT};"
        )
        toast_row.addWidget(toast_label)
        toast_row.addStretch()
        toast_row.addWidget(self._toast_label)
        layout.addLayout(toast_row)
        self._toast_slider, self._toast_label = self._create_slider(
            500, 5000, 100, "ms"
        )
        layout.addWidget(self._toast_slider)

        # Overlay Style
        overlay_label = QLabel("Overlay Style")
        overlay_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: #CBD5E1;")
        layout.addWidget(overlay_label)
        self._overlay_style_combo = QComboBox()
        self._overlay_style_combo.addItems(["Minimal Dot", "Pill with Label"])
        layout.addWidget(self._overlay_style_combo)

        # Global Hotkey (read-only)
        hotkey_label = QLabel("Global Hotkey")
        hotkey_label.setStyleSheet(f"font-size: 12px; font-weight: 500; color: #CBD5E1;")
        layout.addWidget(hotkey_label)
        self._hotkey_display = QLineEdit("Ctrl + Shift + G")
        self._hotkey_display.setReadOnly(True)
        self._hotkey_display.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px;"
        )
        layout.addWidget(self._hotkey_display)

        layout.addStretch()
        return tab

    def _build_gestures_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Confidence section
        conf_section = CollapsibleSection("Confidence Thresholds")
        cl = conf_section.content_layout()

        self._conf_sliders: dict[str, tuple[QSlider, QLabel]] = {}
        for gesture_key, display in [
            ("Open_Palm", "\u270b Open Palm"),
            ("Closed_Fist", "\u270a Closed Fist"),
            ("Thumb_Up", "\U0001f44d Thumb Up"),
            ("Thumb_Down", "\U0001f44e Thumb Down"),
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
        timing_section = CollapsibleSection("Timing")
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
        vol_l.setContentsMargins(0, 4, 0, 4)
        vol_name = QLabel("Volume Step:")
        vol_name.setStyleSheet("font-size: 12px; font-weight: 500; color: #CBD5E1;")
        vol_name.setFixedWidth(120)
        self._volume_step_spin = QSpinBox()
        self._volume_step_spin.setRange(1, 20)
        self._volume_step_spin.setSuffix("%")
        vol_l.addWidget(vol_name)
        vol_l.addWidget(self._volume_step_spin)
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
            f'<a href="https://github.com/anthropics/gesturemute" '
            f'style="color: {ACCENT}; text-decoration: none;">View on GitHub</a>'
        )
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(link)

        layout.addStretch()
        return tab

    # -- Helpers --

    @staticmethod
    def _create_slider(
        min_val: int, max_val: int, step: int, suffix: str,
    ) -> tuple[QSlider, QLabel]:
        """Create a horizontal slider with a value label.

        Args:
            min_val: Minimum slider value.
            max_val: Maximum slider value.
            step: Single step size.
            suffix: Text appended to the displayed value (e.g. "ms", "%").

        Returns:
            Tuple of (QSlider, QLabel) with the label auto-updating on value changes.
        """
        slider = QSlider(Qt.Orientation.Horizontal)
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

    def _populate_from_config(self) -> None:
        """Set all widget values from the stored config."""
        self._populate_from_config_obj(self._config)

    def _populate_from_config_obj(self, config: Config) -> None:
        """Set all widget values from the given config object."""
        c = config

        # General
        self._camera_index_spin.setValue(c.camera_index)
        idx = self._camera_backend_combo.findText(c.camera_backend)
        self._camera_backend_combo.setCurrentIndex(max(idx, 0))
        self._frame_skip_spin.setValue(c.frame_skip)
        self._toast_slider.setValue(c.toast_duration_ms)

        # Overlay style
        style_idx = 1 if c.overlay_style == "pill" else 0
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

        overlay_style = "pill" if self._overlay_style_combo.currentIndex() == 1 else "dot"

        return Config(
            camera_index=self._camera_index_spin.value(),
            camera_backend=self._camera_backend_combo.currentText(),
            frame_skip=self._frame_skip_spin.value(),
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
            onboarding_completed=self._config.onboarding_completed,
        )

    def _on_save(self) -> None:
        new_config = self._collect_to_config()
        self._config = new_config
        self.settings_saved.emit(new_config)
        self.hide()

    def _on_cancel(self) -> None:
        self._populate_from_config()
        self.hide()

    def _on_reset_defaults(self) -> None:
        self._populate_from_config_obj(Config())

    def update_config(self, config: Config) -> None:
        """Update the stored config (e.g. after external save)."""
        self._config = config

    def closeEvent(self, event) -> None:
        """Treat window close as Cancel."""
        self._on_cancel()
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
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        super().show()
        self.raise_()
        self.activateWindow()
