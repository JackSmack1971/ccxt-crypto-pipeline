from __future__ import annotations

import html
from typing import Any


HTML_RENDERER_VERSION = "html-1"


def render_html(title: str, claims: list[dict[str, Any]], methodology: list[str],
                charts: list[dict[str, Any]]) -> str:
    """Render validated reporting structures into a self-contained HTML draft."""
    escaped_title = html.escape(title)
    claim_markup = "\n".join(f"<p>{html.escape(str(claim['text']))}</p>" for claim in claims)
    chart_markup = "\n".join(
        f"<figure><figcaption>{html.escape(str(chart['id']))}</figcaption>{chart['_svg']}</figure>"
        for chart in charts
    )
    methodology_markup = "\n".join(f"<li>{html.escape(line)}</li>" for line in methodology)
    return ("<!doctype html>\n"
            '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f"<title>{escaped_title}</title>\n"
            '<meta name="review-status" content="pending">\n'
            '<style>body{font-family:system-ui,sans-serif;line-height:1.5;max-width:72rem;margin:2rem auto;padding:0 1rem} '
            'figure{margin:2rem 0} figcaption{font-weight:600;margin-bottom:.5rem} svg{max-width:100%;height:auto}</style>\n'
            "</head>\n<body>\n<main>\n"
            f"<h1>{escaped_title}</h1>\n"
            '<p><strong>Review status:</strong> pending human review.</p>\n'
            f"<section aria-labelledby=\"claims-heading\"><h2 id=\"claims-heading\">Claims</h2>\n{claim_markup}</section>\n"
            f"<section aria-labelledby=\"charts-heading\"><h2 id=\"charts-heading\">Charts</h2>\n{chart_markup}</section>\n"
            f"<section aria-labelledby=\"methodology-heading\"><h2 id=\"methodology-heading\">Methodology and limitations</h2>\n<ul>\n{methodology_markup}\n</ul></section>\n"
            "</main>\n</body>\n</html>\n")
