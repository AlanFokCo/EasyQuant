"""EasyQuant / eqlib branding for HTML reports, charts, and docs."""

from __future__ import annotations

BRAND_NAME = "EasyQuant"
REPO_URL = "https://github.com/AlanFokCo/EasyQuant"
TAGLINE_EN = "A-share backtest"


def html_header_brand_lockup() -> str:
    """Inline SVG + name for HTML report header (GitHub link, unique gradient IDs)."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="4 4 56 56" '
        'aria-hidden="true" focusable="false">'
        "<defs>"
        '<linearGradient id="eqHdrBg" x1="12%" y1="88%" x2="88%" y2="12%">'
        '<stop offset="0%" stop-color="#0c1222"/><stop offset="100%" stop-color="#151b2e"/>'
        "</linearGradient>"
        '<linearGradient id="eqHdrSt" x1="0%" y1="100%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#64748b"/>'
        '<stop offset="55%" stop-color="#cbd5e1"/>'
        '<stop offset="100%" stop-color="#f8fafc"/>'
        "</linearGradient>"
        "</defs>"
        '<rect x="5" y="5" width="54" height="54" rx="16" fill="url(#eqHdrBg)"/>'
        '<path d="M 17 42 C 22 42 25 35 29 29 C 33 23 39 18 47 16" fill="none" '
        'stroke="url(#eqHdrSt)" stroke-width="2.25" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        '<circle cx="47" cy="16" r="1.85" fill="#f8fafc"/>'
        "</svg>"
    )
    return (
        f'<a class="eq-brand" href="{REPO_URL}" target="_blank" '
        f'rel="noopener noreferrer" title="{BRAND_NAME}">'
        f"{svg}"
        '<span class="eq-brand-text">'
        f'<span class="eq-brand-name">{BRAND_NAME}</span>'
        f'<span class="eq-brand-tag">{TAGLINE_EN}</span>'
        "</span></a>"
    )


def html_footer_brand_chip() -> str:
    """Small lockup for HTML report footer."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="4 4 56 56" '
        'aria-hidden="true" focusable="false">'
        "<defs>"
        '<linearGradient id="eqFtBg" x1="12%" y1="88%" x2="88%" y2="12%">'
        '<stop offset="0%" stop-color="#0c1222"/><stop offset="100%" stop-color="#151b2e"/>'
        "</linearGradient>"
        '<linearGradient id="eqFtSt" x1="0%" y1="100%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#64748b"/>'
        '<stop offset="100%" stop-color="#f8fafc"/>'
        "</linearGradient>"
        "</defs>"
        '<rect x="5" y="5" width="54" height="54" rx="16" fill="url(#eqFtBg)"/>'
        '<path d="M 17 42 C 22 42 25 35 29 29 C 33 23 39 18 47 16" fill="none" '
        'stroke="url(#eqFtSt)" stroke-width="2.25" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        '<circle cx="47" cy="16" r="1.85" fill="#f8fafc"/>'
        "</svg>"
    )
    return (
        f'<span class="eq-footer-brand" title="{BRAND_NAME}">{svg}'
        f'<span class="eq-footer-name">{BRAND_NAME}</span></span>'
    )


def apply_matplotlib_brand(fig) -> None:
    """Place logo + name in the top margin of a matplotlib Figure."""
    from io import BytesIO

    from matplotlib import image as mpimg

    try:
        from importlib.resources import files

        buf = files("eqlib").joinpath("static/logo-icon.png").read_bytes()
        arr = mpimg.imread(BytesIO(buf))
    except Exception:
        arr = None

    fw, fh = fig.get_figwidth(), fig.get_figheight()
    dpi = fig.dpi
    size_px = 32
    wf = size_px / (fw * dpi)
    hf = size_px / (fh * dpi)
    pad = 0.012
    y0 = 1.0 - pad - hf
    ax_i = fig.add_axes([pad, y0, wf, hf], anchor="NW", zorder=1000)
    ax_i.set_axis_off()
    if arr is not None:
        ax_i.imshow(arr, aspect="equal", interpolation="bilinear")
    tx = pad + wf + 0.01
    fig.text(
        tx,
        y0 + hf * 0.52,
        BRAND_NAME,
        ha="left",
        va="center",
        fontsize=11,
        fontweight="600",
        color="#0c1222",
        transform=fig.transFigure,
        zorder=1000,
    )


# ============================================================
# Dark theme color palette for reports (Bloomberg Terminal style)
# ============================================================

DARK_COLORS = {
    # Background layers
    "bg_primary": "#0c1222",
    "bg_card": "#131b2e",
    "bg_elevated": "#1a2438",
    "bg_input": "#0f1729",
    # Borders
    "border": "#1e2a3a",
    "border_light": "#253042",
    # Text
    "text_primary": "#e2e8f0",
    "text_secondary": "#8b98a9",
    "text_dim": "#4a5568",
    # Semantic
    "up": "#26a69a",
    "down": "#ef5350",
    "accent": "#5b8def",
    "warning": "#faad14",
    # Chart
    "chart_strategy": "#5b8def",
    "chart_hs300": "#f0b90b",
    "chart_sse": "#e2735a",
    "chart_ma5": "#f0b90b",
    "chart_ma20": "#5b8def",
    "chart_ma60": "#a855f7",
}


def apply_matplotlib_dark_theme(fig):
    """Apply dark theme styling to a matplotlib Figure for PNG report."""
    c = DARK_COLORS
    fig.patch.set_facecolor(c["bg_primary"])
    for ax in fig.axes:
        ax.set_facecolor(c["bg_card"])
        ax.tick_params(colors=c["text_secondary"], labelsize=8)
        ax.xaxis.label.set_color(c["text_secondary"])
        ax.yaxis.label.set_color(c["text_secondary"])
        ax.title.set_color(c["text_primary"])
        for spine in ax.spines.values():
            spine.set_color(c["border"])
        ax.grid(True, alpha=0.15, color=c["border_light"])
