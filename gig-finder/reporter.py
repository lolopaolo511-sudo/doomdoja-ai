"""Generator raportów Markdown + HTML ze zranking TOP N ogłoszeń."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Template

from sources import Gig
from scorer import GigScore


@dataclass
class RankedGig:
    gig: Gig
    score: GigScore

    @property
    def fit(self) -> int:
        return self.score.fit


_MD_TEMPLATE = """\
# Gig Finder Report — {{ date }}

**Źródła:** {{ sources_summary }}
**Przeskanowano:** {{ total }} ogłoszeń | **Próg fit:** {{ threshold }}/10 | **TOP {{ top_n }}**

---

{% for i, item in items %}
## {{ loop.index }}. {{ item.gig.title }} `[fit: {{ item.fit }}/10]`

| Pole | Wartość |
|------|---------|
| **Źródło** | {{ item.gig.source }} |
| **Budżet** | {{ item.gig.budget }} |
| **Link** | [{{ item.gig.url[:60] }}{{ '...' if item.gig.url|length > 60 else '' }}]({{ item.gig.url }}) |
| **Data** | {{ item.gig.posted_at or '—' }} |
| **Oceniono przez** | {{ item.score.scored_by }} |

**Dlaczego pasuje:** {{ item.score.why_fits }}

**Kąt oferty:** *{{ item.score.offer_angle }}*

{% if item.gig.tags %}_Tagi: {{ item.gig.tags[:8] | join(', ') }}_{% endif %}

---
{% endfor %}

_Wygenerowano: {{ datetime_now }}_
"""

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gig Finder Report — {{ date }}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 960px; margin: 0 auto; padding: 24px; background: #f8f9fa; color: #222; }
  h1 { color: #1a1a2e; border-bottom: 3px solid #0066cc; padding-bottom: 8px; }
  .meta { color: #555; font-size: 0.9em; margin-bottom: 24px; }
  .gig { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px;
         box-shadow: 0 1px 4px rgba(0,0,0,0.1); border-left: 4px solid #0066cc; }
  .gig.high { border-left-color: #00aa44; }
  .gig.medium { border-left-color: #ff9900; }
  .gig.low { border-left-color: #cc3300; }
  .rank { font-size: 0.8em; color: #888; float: right; }
  .title { font-size: 1.15em; font-weight: 600; margin: 0 0 8px 0; }
  .title a { color: #0066cc; text-decoration: none; }
  .title a:hover { text-decoration: underline; }
  .fit-badge { display: inline-block; padding: 2px 10px; border-radius: 12px;
               font-weight: 700; font-size: 0.9em; color: #fff; margin-left: 8px; }
  .fit-high { background: #00aa44; }
  .fit-med { background: #ff9900; }
  .fit-low { background: #cc3300; }
  .meta-row { display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.85em;
              color: #555; margin: 8px 0; }
  .why { background: #f0f4ff; padding: 8px 12px; border-radius: 4px;
         font-size: 0.9em; margin: 8px 0; }
  .angle { font-style: italic; color: #333; font-size: 0.9em; }
  .tags { margin-top: 8px; }
  .tag { display: inline-block; background: #e8edf0; padding: 2px 8px;
         border-radius: 10px; font-size: 0.78em; margin: 2px; color: #444; }
  .footer { text-align: center; color: #aaa; font-size: 0.8em; margin-top: 32px; }
</style>
</head>
<body>
<h1>Gig Finder Report</h1>
<div class="meta">
  <strong>Data:</strong> {{ date }} &nbsp;|&nbsp;
  <strong>Źródła:</strong> {{ sources_summary }} &nbsp;|&nbsp;
  <strong>Przeskanowano:</strong> {{ total }} &nbsp;|&nbsp;
  <strong>TOP {{ top_n }}</strong> (próg fit ≥ {{ threshold }}/10)
</div>

{% for item in items %}
{% set color = 'high' if item.fit >= 8 else ('medium' if item.fit >= 6 else 'low') %}
{% set badge = 'fit-high' if item.fit >= 8 else ('fit-med' if item.fit >= 6 else 'fit-low') %}
<div class="gig {{ color }}">
  <span class="rank">#{{ loop.index }} &bull; {{ item.score.scored_by }}</span>
  <div class="title">
    <a href="{{ item.gig.url }}" target="_blank" rel="noopener">{{ item.gig.title }}</a>
    <span class="fit-badge {{ badge }}">{{ item.fit }}/10</span>
  </div>
  <div class="meta-row">
    <span>📦 {{ item.gig.source }}</span>
    <span>💰 {{ item.gig.budget }}</span>
    {% if item.gig.posted_at %}<span>📅 {{ item.gig.posted_at[:10] }}</span>{% endif %}
  </div>
  <div class="why">🎯 <strong>Dopasowanie:</strong> {{ item.score.why_fits }}</div>
  {% if item.score.offer_angle != 'N/A' %}
  <div class="angle">✍️ <strong>Kąt oferty:</strong> {{ item.score.offer_angle }}</div>
  {% endif %}
  {% if item.gig.tags %}
  <div class="tags">{% for t in item.gig.tags[:8] %}<span class="tag">{{ t }}</span>{% endfor %}</div>
  {% endif %}
</div>
{% endfor %}

<div class="footer">Wygenerowano {{ datetime_now }} przez gig-finder (doomdoja-ai)</div>
</body>
</html>
"""


def generate(
    ranked: list[RankedGig],
    total_scanned: int,
    sources_used: list[str],
    cfg: dict,
    output_dir: Path,
) -> dict[str, Path]:
    """Generuj raport MD + HTML. Zwraca dict {format: path}."""
    top_n = cfg.get("top_n", 15)
    threshold = cfg.get("fit_threshold", 6) if "fit_threshold" in cfg else 6
    items = ranked[:top_n]
    date_str = datetime.now().strftime("%Y-%m-%d")
    datetime_now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sources_summary = ", ".join(sorted(set(sources_used))) or "—"

    ctx = {
        "date": date_str,
        "datetime_now": datetime_now,
        "total": total_scanned,
        "top_n": min(top_n, len(items)),
        "threshold": threshold,
        "sources_summary": sources_summary,
        "items": items,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    formats = cfg.get("formats", ["markdown", "html"])

    if "markdown" in formats:
        md_path = output_dir / f"report_{date_str}.md"
        # Jinja2 z enumerate
        md_ctx = {**ctx, "items": list(enumerate(items, 1))}
        md_content = _render_md(items, total_scanned, sources_summary, top_n, threshold, date_str, datetime_now)
        md_path.write_text(md_content, encoding="utf-8")
        paths["markdown"] = md_path

    if "html" in formats:
        html_path = output_dir / f"report_{date_str}.html"
        html_content = Template(_HTML_TEMPLATE).render(**ctx)
        html_path.write_text(html_content, encoding="utf-8")
        paths["html"] = html_path

    return paths


def _render_md(
    items: list[RankedGig],
    total: int,
    sources: str,
    top_n: int,
    threshold: int,
    date_str: str,
    datetime_now: str,
) -> str:
    lines = [
        f"# Gig Finder Report — {date_str}",
        "",
        f"**Źródła:** {sources}  ",
        f"**Przeskanowano:** {total} ogłoszeń | **Próg fit:** {threshold}/10 | **TOP {top_n}**",
        "",
        "---",
        "",
    ]

    for i, item in enumerate(items, 1):
        g = item.gig
        s = item.score
        fit_bar = "█" * item.fit + "░" * (10 - item.fit)
        lines += [
            f"## {i}. {g.title}",
            "",
            f"**Fit:** `{item.fit}/10` `{fit_bar}`  ",
            f"**Źródło:** {g.source}  ",
            f"**Budżet:** {g.budget}  ",
            f"**Link:** <{g.url}>  ",
            f"**Data:** {g.posted_at or '—'}  ",
            f"**Oceniono:** {s.scored_by}  ",
            "",
            f"**Dlaczego pasuje:** {s.why_fits}",
            "",
            f"**Kąt oferty:** _{s.offer_angle}_",
            "",
        ]
        if g.tags:
            lines.append(f"_Tagi: {', '.join(g.tags[:8])}_")
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"_Wygenerowano: {datetime_now} przez gig-finder_")
    return "\n".join(lines)
