from __future__ import annotations

import html
from typing import Any

RENDERER_VERSION = "svg-1"


def render_svg(spec: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    points = []
    unavailable = False
    for row in rows:
        x, y = row.get(spec["x_column"]), row.get(spec["y_column"])
        if x is None or y is None:
            unavailable = True
            continue
        try:
            points.append((float(x), float(y)))
        except (TypeError, ValueError):
            if spec["missing_behavior"] == "fail":
                raise ValueError(f"chart {spec['id']} contains unsupported values")
            unavailable = True
    if not points and rows and spec["missing_behavior"] == "fail":
        raise ValueError(f"chart {spec['id']} has no renderable values")
    w, h = spec["width"], spec["height"]
    title = html.escape(spec["id"])
    desc = html.escape(spec["alt_text"] + f" Source: {spec['source_attribution']}")
    if not points:
        body = '<text x="400" y="240" text-anchor="middle">No supported observations</text>'
    else:
        lo_x, hi_x = min(p[0] for p in points), max(p[0] for p in points)
        lo_y, hi_y = min(p[1] for p in points), max(p[1] for p in points)
        dx, dy = hi_x - lo_x or 1.0, hi_y - lo_y or 1.0
        coords = [(60 + (x - lo_x) / dx * (w - 100), h - 50 - (y - lo_y) / dy * (h - 100)) for x, y in points]
        body = f'<polyline fill="none" stroke="#1464a0" stroke-width="2" points="{" ".join(f"{x:.3f},{y:.3f}" for x,y in coords)}" />'
        if unavailable:
            body += f'<text x="60" y="45">Unavailable observations omitted</text>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" role="img" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}"><title>{title}</title><desc>{desc}</desc>'
            f'<text x="60" y="25">{html.escape(spec["y_column"])} ({html.escape(spec["y_unit"])})</text>'
            f'{body}<text x="60" y="{h-15}">{html.escape(spec["x_column"])} ({html.escape(spec["x_unit"])}) · '
            f'{html.escape(spec["source_attribution"])}</text></svg>')


def validate_accessibility(svg: str, spec: dict[str, Any]) -> None:
    if not all(token in svg for token in ('role="img"', "<title>", "<desc>", spec["y_unit"], spec["x_unit"], spec["source_attribution"])):
        raise ValueError(f"chart {spec['id']} failed accessibility validation")
