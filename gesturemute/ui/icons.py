"""Menu bar icon generation for GestureMute.

Draws microphone-shaped icons that adapt to light/dark mode,
with a small colored accent dot indicating mic state.
"""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import QApplication

from gesturemute.gesture.gestures import MicState
from gesturemute.ui.theme import (
    ICON_STROKE_LIGHT, ICON_STROKE_DARK,
    mic_state_color,
)

# Logical size in points — 16pt is standard for macOS menu bar icons.
_LOGICAL_SIZE = 16


def _get_device_pixel_ratio() -> float:
    screen = QApplication.primaryScreen()
    return screen.devicePixelRatio() if screen else 2.0


def _is_dark_mode() -> bool:
    hints = QApplication.styleHints()
    if hasattr(hints, "colorScheme"):
        return hints.colorScheme() == Qt.ColorScheme.Dark
    return False


def _stroke_color() -> QColor:
    return QColor(ICON_STROKE_DARK if _is_dark_mode() else ICON_STROKE_LIGHT)


# ── Mic shape primitives ─────────────────────────────────────────────

def _mic_body_path(cx: float, top: float, w: float, h: float, r: float) -> QPainterPath:
    """Capsule-shaped microphone body centred at *cx*."""
    path = QPainterPath()
    rect = QRectF(cx - w / 2, top, w, h)
    path.addRoundedRect(rect, r, r)
    return path


def _mic_stand_path(cx: float, arc_top: float, arc_w: float, stem_bottom: float, base_hw: float) -> QPainterPath:
    """Arc + stem + base below the mic body."""
    path = QPainterPath()
    # Arc (bottom half of an ellipse)
    arc_rect = QRectF(cx - arc_w / 2, arc_top - arc_w / 2, arc_w, arc_w)
    path.arcMoveTo(arc_rect, 0)
    path.arcTo(arc_rect, 0, -180)
    # Stem
    path.moveTo(cx, arc_top + arc_w / 2)
    path.lineTo(cx, stem_bottom)
    # Base
    path.moveTo(cx - base_hw, stem_bottom)
    path.lineTo(cx + base_hw, stem_bottom)
    return path


# ── Per-state drawing ────────────────────────────────────────────────

def _draw_mic(p: QPainter, sz: float, stroke: QColor) -> None:
    """Draw the base microphone shape (body + stand)."""
    pen = QPen(stroke, sz * 0.09)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    cx = sz / 2
    body_w = sz * 0.32
    body_h = sz * 0.44
    body_top = sz * 0.10
    body_r = body_w / 2

    p.drawPath(_mic_body_path(cx, body_top, body_w, body_h, body_r))
    p.drawPath(_mic_stand_path(
        cx,
        arc_top=body_top + body_h - sz * 0.04,
        arc_w=sz * 0.46,
        stem_bottom=sz * 0.78,
        base_hw=sz * 0.18,
    ))


def _draw_slash(p: QPainter, sz: float, stroke: QColor) -> None:
    """Diagonal slash across the icon."""
    pen = QPen(stroke, sz * 0.09)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    margin = sz * 0.12
    p.drawLine(QPointF(sz - margin, margin), QPointF(margin, sz - margin))


def _draw_lock(p: QPainter, sz: float, stroke: QColor) -> None:
    """Small lock glyph in bottom-right corner."""
    pen = QPen(stroke, sz * 0.06)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # Lock body
    lx = sz * 0.68
    ly = sz * 0.62
    lw = sz * 0.22
    lh = sz * 0.18
    p.drawRect(QRectF(lx, ly, lw, lh))

    # Shackle arc
    shackle_rect = QRectF(lx + lw * 0.15, ly - lh * 0.65, lw * 0.7, lh * 0.8)
    p.drawArc(shackle_rect, 0, 180 * 16)


def _draw_pause_bars(p: QPainter, sz: float, stroke: QColor) -> None:
    """Two vertical pause bars overlaid on the icon."""
    pen = QPen(stroke, sz * 0.09)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    bar_h = sz * 0.32
    top = sz * 0.34
    gap = sz * 0.12
    cx = sz / 2
    p.drawLine(QPointF(cx - gap, top), QPointF(cx - gap, top + bar_h))
    p.drawLine(QPointF(cx + gap, top), QPointF(cx + gap, top + bar_h))


def _draw_accent_dot(p: QPainter, sz: float, color_hex: str) -> None:
    """Small colored dot in the bottom-right corner."""
    radius = sz * 0.10
    cx = sz * 0.82
    cy = sz * 0.82
    # Background knockout ring (matches menu bar)
    bg = QColor(ICON_STROKE_DARK if not _is_dark_mode() else ICON_STROKE_LIGHT)
    bg.setAlpha(0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color_hex))
    p.drawEllipse(QPointF(cx, cy), radius, radius)


# ── Public API ───────────────────────────────────────────────────────

def generate_tray_icon(mic_state: MicState | None) -> QIcon:
    """Generate a menu-bar-appropriate icon for the given mic state.

    Returns a QIcon sized for the macOS menu bar (16pt logical) that
    adapts its stroke colour to the current system appearance.
    """
    ratio = _get_device_pixel_ratio()
    px = int(_LOGICAL_SIZE * ratio)

    pixmap = QPixmap(px, px)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    sz = float(_LOGICAL_SIZE)  # draw in logical coords
    stroke = _stroke_color()

    # Base mic shape
    _draw_mic(painter, sz, stroke)

    # State-specific overlays
    if mic_state == MicState.MUTED:
        _draw_slash(painter, sz, stroke)
    elif mic_state == MicState.LOCKED_MUTE:
        _draw_slash(painter, sz, stroke)
        _draw_lock(painter, sz, stroke)
    elif mic_state is None:
        _draw_pause_bars(painter, sz, stroke)

    # Colored accent dot
    _draw_accent_dot(painter, sz, mic_state_color(mic_state))

    painter.end()
    return QIcon(pixmap)
