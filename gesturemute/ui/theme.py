"""Centralized design tokens for GestureMute UI."""

from gesturemute.gesture.gestures import MicState

# Backgrounds
BACKGROUND = "#0B0F1A"
SURFACE = "#111827"

# Accent
ACCENT = "#6366F1"
ACCENT_LIGHT = "#818CF8"

# Mic state colors
COLOR_LIVE = "#10B981"
COLOR_MUTED = "#EF4444"
COLOR_LOCKED = "#F59E0B"
COLOR_PAUSED = "#64748B"

# Text
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#E2E8F0"
TEXT_MUTED = "#94A3B8"
TEXT_DIM = "#64748B"

# Surfaces (for QSS)
BORDER_COLOR = "rgba(255,255,255,0.06)"
INPUT_BG = "rgba(255,255,255,0.04)"

# Menu bar icon strokes (#AARRGGBB — Qt puts alpha first)
ICON_STROKE_LIGHT = "#CC000000"  # dark stroke for light menu bar
ICON_STROKE_DARK = "#CCFFFFFF"   # white stroke for dark menu bar

# Font
FONT_FAMILY = "'Inter', 'Segoe UI', sans-serif"

_MIC_STATE_COLORS = {
    MicState.LIVE: COLOR_LIVE,
    MicState.MUTED: COLOR_MUTED,
    MicState.LOCKED_MUTE: COLOR_LOCKED,
}


def mic_state_color(state: MicState | None) -> str:
    """Return the hex color for a given mic state.

    Args:
        state: Current mic state, or None for paused/detection off.

    Returns:
        Hex color string.
    """
    if state is None:
        return COLOR_PAUSED
    return _MIC_STATE_COLORS.get(state, COLOR_PAUSED)
