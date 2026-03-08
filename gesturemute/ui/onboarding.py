"""First-launch onboarding wizard for GestureMute."""

from PyQt6.QtCore import Qt, QPoint, pyqtSignal

from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gesturemute.ui.theme import (
    ACCENT, ACCENT_LIGHT, BACKGROUND, SURFACE,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    COLOR_LIVE, BORDER_COLOR, FONT_FAMILY,
)

_WIDTH = 400
_HEIGHT = 520
_NUM_STEPS = 4

_STYLESHEET = f"""
    QDialog {{
        background: {SURFACE};
        color: {TEXT_SECONDARY};
        font-family: {FONT_FAMILY};
    }}
    QLabel {{
        background: transparent;
        border: none;
    }}
    QPushButton#skipBtn {{
        font-size: 13px;
        color: {TEXT_DIM};
        background: none;
        border: none;
        padding: 8px 12px;
    }}
    QPushButton#skipBtn:hover {{
        color: {TEXT_MUTED};
    }}
    QPushButton#nextBtn {{
        font-size: 14px;
        font-weight: 600;
        color: #FFFFFF;
        background: {ACCENT};
        border: none;
        border-radius: 10px;
        padding: 10px 24px;
    }}
    QPushButton#nextBtn:hover {{
        background: {ACCENT_LIGHT};
    }}
    QPushButton#startBtn {{
        font-size: 14px;
        font-weight: 600;
        color: #FFFFFF;
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
            stop:0 {ACCENT}, stop:1 #8B5CF6);
        border: none;
        border-radius: 10px;
        padding: 12px 32px;
    }}
    QPushButton#startBtn:hover {{
        background: {ACCENT_LIGHT};
    }}
"""


class OnboardingWizard(QDialog):
    """Modal 4-step onboarding wizard shown on first launch.

    Signals:
        completed: Emitted when the user finishes or skips onboarding.
    """

    completed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_step = 0
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(_WIDTH, _HEIGHT)
        self.setStyleSheet(_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header with decorative dots
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background: transparent;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 16, 20, 0)
        for color in ["#EF4444", "#F59E0B", "#22C55E"]:
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
            hl.addWidget(dot)
        hl.addStretch()
        root.addWidget(header)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_welcome())
        self._stack.addWidget(self._build_gestures())
        self._stack.addWidget(self._build_camera())
        self._stack.addWidget(self._build_ready())
        root.addWidget(self._stack, 1)

        # Footer: progress dots + buttons
        self._footer = QWidget()
        self._footer.setFixedHeight(64)
        self._footer.setStyleSheet("background: transparent;")
        fl = QHBoxLayout(self._footer)
        fl.setContentsMargins(32, 0, 32, 24)

        self._progress_dots: list[QLabel] = []
        progress = QHBoxLayout()
        progress.setSpacing(6)
        for i in range(_NUM_STEPS):
            dot = QLabel()
            dot.setFixedSize(8, 8)
            progress.addWidget(dot)
            self._progress_dots.append(dot)
        fl.addLayout(progress)
        fl.addStretch()

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setObjectName("skipBtn")
        self._skip_btn.clicked.connect(self._on_skip)
        fl.addWidget(self._skip_btn)

        self._next_btn = QPushButton("Next")
        self._next_btn.setObjectName("nextBtn")
        self._next_btn.clicked.connect(self._on_next)
        fl.addWidget(self._next_btn)

        root.addWidget(self._footer)

        self._update_ui()

    # -- Step builders --

    def _build_welcome(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(0)

        # Icon placeholder
        icon = QLabel("\U0001f3a4")
        icon.setFixedSize(120, 120)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            "font-size: 56px;"
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 rgba(99,102,241,0.15), stop:1 rgba(139,92,246,0.08));"
            "border: 1px solid rgba(99,102,241,0.15);"
            "border-radius: 24px;"
        )
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(28)

        welcome_label = QLabel("WELCOME")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet(
            f"font-size: 10px; font-weight: 600; letter-spacing: 2px;"
            f"color: {ACCENT};"
        )
        layout.addWidget(welcome_label)
        layout.addSpacing(12)

        title = QLabel("GestureMute")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        layout.addSpacing(12)

        desc = QLabel(
            "Hands-free microphone control via webcam\n"
            "gesture recognition. No more fumbling\nfor the mute button."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED}; line-height: 1.6;")
        layout.addWidget(desc)

        return page

    def _build_gestures(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 0, 40, 0)
        layout.setSpacing(0)

        # 2x2 gesture grid
        grid_frame = QWidget()
        grid_frame.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 rgba(16,185,129,0.12), stop:1 rgba(6,182,212,0.08));"
            "border: 1px solid rgba(16,185,129,0.12);"
            "border-radius: 16px;"
        )
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setSpacing(10)

        gestures = [
            ("\u270b", "Open Palm", "Hold to mute"),
            ("\u270a", "Palm to Fist", "Lock mute"),
            ("\U0001f44d", "Thumbs Up", "Volume +3%"),
            ("\U0001f44e", "Thumbs Down", "Volume -3%"),
        ]
        for i, (emoji, name, action) in enumerate(gestures):
            cell = QWidget()
            cell.setStyleSheet(
                "background: rgba(255,255,255,0.04);"
                "border-radius: 10px;"
                "border: 1px solid rgba(255,255,255,0.04);"
            )
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(10, 8, 10, 8)
            cl.setSpacing(10)

            icon = QLabel(emoji)
            icon.setFixedSize(36, 36)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet(
                "font-size: 20px;"
                "background: rgba(255,255,255,0.06);"
                "border-radius: 8px;"
            )
            cl.addWidget(icon)

            text = QVBoxLayout()
            text.setSpacing(2)
            nl = QLabel(name)
            nl.setStyleSheet("font-size: 11px; color: #CBD5E1;")
            text.addWidget(nl)
            al = QLabel(action)
            al.setStyleSheet(f"font-size: 10px; color: {TEXT_DIM};")
            text.addWidget(al)
            cl.addLayout(text)

            grid.addWidget(cell, i // 2, i % 2)

        layout.addWidget(grid_frame)
        layout.addSpacing(24)

        title = QLabel("Your Gestures")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        layout.addSpacing(8)

        desc = QLabel("Simple hand gestures control your\nmicrophone. Each maps to an action.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED};")
        layout.addWidget(desc)

        return page

    def _build_camera(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 0, 40, 0)
        layout.setSpacing(0)

        icon = QLabel("\U0001f4f7")
        icon.setFixedSize(120, 120)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            "font-size: 56px;"
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 rgba(251,191,36,0.12), stop:1 rgba(245,158,11,0.08));"
            "border: 1px solid rgba(251,191,36,0.12);"
            "border-radius: 24px;"
        )
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(28)

        perm_label = QLabel("PERMISSIONS")
        perm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        perm_label.setStyleSheet(
            f"font-size: 10px; font-weight: 600; letter-spacing: 2px;"
            f"color: {ACCENT};"
        )
        layout.addWidget(perm_label)
        layout.addSpacing(12)

        title = QLabel("Camera Access")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        layout.addSpacing(12)

        desc = QLabel(
            "GestureMute needs your webcam to detect\n"
            "gestures. Frames are processed locally and\n"
            "never stored or transmitted."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED};")
        layout.addWidget(desc)
        layout.addSpacing(20)

        # Privacy shield badge
        badge = QLabel(
            "\U0001f6e1  100% local processing. Zero data leaves your device."
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: rgba(16,185,129,0.08);"
            f"border: 1px solid rgba(16,185,129,0.15);"
            f"border-radius: 10px; padding: 10px 16px;"
            f"font-size: 12px; color: {COLOR_LIVE};"
        )
        layout.addWidget(badge)

        return page

    def _build_ready(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 0, 40, 0)
        layout.setSpacing(0)

        icon = QLabel("\u2714")
        icon.setFixedSize(120, 120)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            "font-size: 56px;"
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 rgba(16,185,129,0.15), stop:1 rgba(52,211,153,0.08));"
            "border: 1px solid rgba(16,185,129,0.15);"
            "border-radius: 24px;"
            f"color: #34D399;"
        )
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(28)

        title = QLabel("You're All Set")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        layout.addSpacing(12)

        desc = QLabel(
            "GestureMute is ready. Raise your hand in\n"
            "front of the webcam to control your\n"
            "microphone instantly."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"font-size: 14px; color: {TEXT_MUTED};")
        layout.addWidget(desc)
        layout.addSpacing(24)

        start_btn = QPushButton("Get Started")
        start_btn.setObjectName("startBtn")
        start_btn.setFixedHeight(44)
        start_btn.clicked.connect(self._on_finish)
        layout.addWidget(start_btn)

        return page

    # -- Navigation --

    def _update_ui(self) -> None:
        """Update progress dots and button visibility for the current step."""
        self._stack.setCurrentIndex(self._current_step)

        for i, dot in enumerate(self._progress_dots):
            if i == self._current_step:
                dot.setFixedSize(24, 8)
                dot.setStyleSheet(
                    f"background: {ACCENT}; border-radius: 4px;"
                )
            else:
                dot.setFixedSize(8, 8)
                dot.setStyleSheet(
                    "background: rgba(255,255,255,0.12); border-radius: 4px;"
                )

        is_last = self._current_step == _NUM_STEPS - 1
        self._skip_btn.setVisible(not is_last)
        self._next_btn.setVisible(not is_last)

    def _on_next(self) -> None:
        if self._current_step < _NUM_STEPS - 1:
            self._current_step += 1
            self._update_ui()

    def _on_skip(self) -> None:
        self._on_finish()

    def _on_finish(self) -> None:
        self.completed.emit()
        self.accept()

    # -- Drag to move --

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 48:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
