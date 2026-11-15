"""Tiny server-side SVG charts (no JS chart library, works offline).

Only numbers and fixed labels are interpolated into SVG; any text is escaped.
"""
from __future__ import annotations

from markupsafe import Markup, escape


def line_chart(series: dict[str, list[float | None]], colors: dict[str, str], width: int = 400, height: int = 210,
               x_label: str = "", y_fmt: str = "{:.1f}") -> Markup:
    pts = [v for vals in series.values() for v in vals if v is not None]
    n = max((len(v) for v in series.values()), default=0)
    if not pts or n == 0:
        return Markup('<p class="muted">No data yet.</p>')
    pad_l, pad_r, pad_t, pad_b = 44, 12, 12, 26
    lo, hi = min(pts), max(pts)
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    w, h = width - pad_l - pad_r, height - pad_t - pad_b

    def x(i: int) -> float:
        return pad_l + (w * i / (n - 1) if n > 1 else w / 2)

    def y(v: float) -> float:
        return pad_t + h - (v - lo) / (hi - lo) * h

    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                     f'<text x="{pad_l - 6}" y="{y(v) + 4:.1f}" class="tick" text-anchor="end">{escape(y_fmt.format(v))}</text>')
    for name, vals in series.items():
        coords = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals) if v is not None)
        parts.append(f'<polyline points="{coords}" fill="none" stroke="{colors[name]}" stroke-width="2" '
                     f'stroke-linejoin="round" stroke-linecap="round"><title>{escape(name)}</title></polyline>')
        if n <= 40:
            parts += [f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.5" fill="{colors[name]}"/>'
                      for i, v in enumerate(vals) if v is not None]
    parts.append(f'<text x="{pad_l + w / 2:.0f}" y="{height - 6}" class="tick" text-anchor="middle">{escape(x_label)}</text>')
    parts.append("</svg>")
    return Markup("".join(parts))
