from __future__ import annotations

import html
import math
import xml.etree.ElementTree as ET
from typing import Any

RENDERER_VERSION = "svg-2"


def render_svg(spec: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    for transformation in spec.get("transformations", ()):
        if transformation not in {"identity", "sort_x"}:
            raise ValueError(f"chart {spec['id']} has unsupported transformation")
    if "sort_x" in spec.get("transformations", ()):
        try:
            def sort_key(row: dict[str, Any]) -> float:
                value = float(row.get(spec["x_column"]))
                if not math.isfinite(value):
                    raise ValueError
                return value
            rows = sorted(rows, key=sort_key)
        except (TypeError, ValueError):
            raise ValueError(f"chart {spec['id']} cannot sort unsupported values")
    points = []
    unavailable = False
    for row in rows:
        x, y = row.get(spec["x_column"]), row.get(spec["y_column"])
        if x is None or y is None:
            if spec["missing_behavior"] == "fail":
                raise ValueError(f"chart {spec['id']} contains missing values")
            unavailable = True
            continue
        try:
            if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise ValueError
            point = (float(x), float(y))
            points.append(point)
        except (TypeError, ValueError):
            if spec["missing_behavior"] == "fail":
                raise ValueError(f"chart {spec['id']} contains unsupported values")
            unavailable = True
        else:
            if not all(math.isfinite(value) for value in point):
                raise ValueError(f"chart {spec['id']} contains non-finite values")
    if not points and spec["missing_behavior"] == "fail":
        raise ValueError(f"chart {spec['id']} has no renderable values")
    if not points and spec.get("annotations"):
        raise ValueError(f"chart {spec['id']} cannot apply annotations without renderable values")
    w, h = spec["width"], spec["height"]
    if isinstance(w, bool) or isinstance(h, bool) or not isinstance(w, int) or not isinstance(h, int) or not (320 <= w <= 4096 and 180 <= h <= 4096):
        raise ValueError(f"chart {spec['id']} has invalid dimensions")
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
        for annotation in spec.get("annotations", ()):
            if annotation.get("type") != "horizontal_line":
                raise ValueError(f"chart {spec['id']} has unsupported annotation")
            if not lo_y <= float(annotation["value"]) <= hi_y:
                raise ValueError(f"chart {spec['id']} annotation is outside the visible y range")
            ay = h - 50 - (float(annotation["value"]) - lo_y) / dy * (h - 100)
            body += (f'<line x1="60" x2="{w - 40}" y1="{ay:.3f}" y2="{ay:.3f}" '
                     f'stroke="#a01414" stroke-dasharray="4 2" />'
                     f'<text x="{w - 40}" y="{ay - 4:.3f}" text-anchor="end">'
                     f'{html.escape(str(annotation["label"]))} ({html.escape(str(annotation["source"]))})</text>')
        if unavailable:
            body += f'<text x="60" y="45">Unavailable observations omitted</text>'
    missing_state = "true" if unavailable or not points else "false"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" role="img" data-missing="{missing_state}" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}"><title>{title}</title><desc>{desc}</desc>'
            f'<text x="60" y="25">{html.escape(spec["y_column"])} ({html.escape(spec["y_unit"])})</text>'
            f'{body}<text x="60" y="{h-15}">{html.escape(spec["x_column"])} ({html.escape(spec["x_unit"])}) · '
            f'{html.escape(spec["source_attribution"])}</text></svg>')


def validate_accessibility(svg: str, spec: dict[str, Any]) -> None:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ValueError(f"chart {spec['id']} failed SVG structure validation") from exc
    ns = "{http://www.w3.org/2000/svg}"
    if root.tag != f"{ns}svg":
        raise ValueError(f"chart {spec['id']} failed SVG structure validation")
    title = root.find(f"{ns}title")
    desc = root.find(f"{ns}desc")
    nonfinite_attribute = any(
        not math.isfinite(float(value))
        for element in root.iter()
        for value in element.attrib.values()
        if _is_numeric(value)
    )
    point_data = root.find(f"{ns}polyline")
    malformed_points = False
    if point_data is not None:
        tokens = point_data.get("points", "").replace(",", " ").split()
        try:
            malformed_points = len(tokens) % 2 != 0 or any(not math.isfinite(float(token)) for token in tokens)
        except ValueError:
            malformed_points = True
    if (root.get("role") != "img" or title is None or not (title.text or "").strip() or
            desc is None or not (desc.text or "").strip() or
            not all(token in svg for token in (spec["y_unit"], spec["x_unit"], spec["source_attribution"])) or
            nonfinite_attribute or malformed_points or root.get("data-missing") not in {"true", "false"}):
        raise ValueError(f"chart {spec['id']} failed accessibility validation")


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
