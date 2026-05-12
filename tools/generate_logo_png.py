#!/usr/bin/env python3
"""Rasterize EasyQuant logo assets using matplotlib only (no libcairo)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"

TILE_DARK = "#0c1222"
TILE_DARK_EDGE = "#151b2e"


def _squircle(ax, x, y, w, h, r, face, edge=None, lw=0):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0,rounding_size={r}",
            facecolor=face,
            edgecolor=edge or "none",
            linewidth=lw or 0,
        )
    )


def draw_horizontal_logo(path: Path, width_px: int = 640) -> None:
    vb_w, vb_h = 280, 64
    dpi = 100
    fig_w = width_px / dpi
    fig_h = fig_w * (vb_h / vb_w)
    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=dpi)
    ax.set_xlim(0, vb_w)
    ax.set_ylim(0, vb_h)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ix, iy, iw, ih, ir = 4, 6, 52, 52, 16
    _squircle(ax, ix, iy, iw, ih, ir, TILE_DARK, TILE_DARK_EDGE, 0.35)

    t = np.linspace(0, 1, 120)
    x = ix + 13 + 30 * t
    y = iy + 40 - 26 * (t ** 0.85) * (1 - 0.08 * np.sin(np.pi * t))
    ax.plot(x, y, color="#cbd5e1", lw=2.0, solid_capstyle="round", zorder=2)
    ax.plot(x, y, color="#f8fafc", lw=0.85, solid_capstyle="round", zorder=3, alpha=0.95)
    ax.add_patch(Circle((ix + 43, iy + 14), 1.75, color="#f8fafc", zorder=4))

    ax.text(
        66, 40, "EasyQuant",
        fontsize=13.8, fontweight="600", color="#0c1222", va="center", ha="left",
        family="sans-serif",
    )

    fig.savefig(path, bbox_inches="tight", pad_inches=0.02, facecolor="white", transparent=False)
    plt.close(fig)


def draw_icon(path: Path, size_px: int = 512) -> None:
    dpi = 100
    s = size_px / dpi
    fig, ax = plt.subplots(1, 1, figsize=(s, s), dpi=dpi)
    ax.set_xlim(0, 64)
    ax.set_ylim(0, 64)
    ax.axis("off")
    ax.set_aspect("equal")
    fig.patch.set_facecolor("white")

    _squircle(ax, 5, 5, 54, 54, 16, TILE_DARK, TILE_DARK_EDGE, 0.35)

    t = np.linspace(0, 1, 120)
    x = 17 + 30 * t
    y = 42 - 26 * (t ** 0.85) * (1 - 0.08 * np.sin(np.pi * t))
    ax.plot(x, y, color="#cbd5e1", lw=2.05, solid_capstyle="round", zorder=2)
    ax.plot(x, y, color="#f8fafc", lw=0.9, solid_capstyle="round", zorder=3, alpha=0.95)
    ax.add_patch(Circle((47, 16), 1.85, color="#f8fafc", zorder=4))

    fig.savefig(path, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def draw_mono(path: Path, width_px: int = 640) -> None:
    vb_w, vb_h = 280, 64
    dpi = 100
    fig_w = width_px / dpi
    fig_h = fig_w * (vb_h / vb_w)
    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=dpi)
    ax.set_xlim(0, vb_w)
    ax.set_ylim(0, vb_h)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ix, iy = 4, 6
    _squircle(ax, ix, iy, 52, 52, 16, TILE_DARK)

    t = np.linspace(0, 1, 120)
    x = ix + 13 + 30 * t
    y = iy + 40 - 26 * (t ** 0.85) * (1 - 0.08 * np.sin(np.pi * t))
    ax.plot(x, y, color="#f1f5f9", lw=2.05, solid_capstyle="round", zorder=2)
    ax.add_patch(Circle((ix + 43, iy + 14), 1.75, color="#f1f5f9", zorder=3))

    ax.text(66, 40, "EasyQuant", fontsize=13.8, fontweight="600", color="#0c1222", va="center")

    fig.savefig(path, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    draw_horizontal_logo(OUT / "logo.png", 640)
    draw_horizontal_logo(OUT / "logo@2x.png", 1280)
    draw_icon(OUT / "logo-icon.png", 512)
    draw_icon(OUT / "favicon-32.png", 32)
    draw_mono(OUT / "logo-mono.png", 640)
    for p in sorted(OUT.glob("*.png")):
        print(p.name, p.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
