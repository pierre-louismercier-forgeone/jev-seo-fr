"""HTML report rendered to PDF with WeasyPrint. Charts are inline SVG, so the PDF stays vector."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from jevseo import jev
from jevseo.checks import RULES

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
FONTS = Path(__file__).resolve().parent.parent / "fonts"
# Bundled fonts (SIL Open Font License) so every machine renders the same design.
# FR: gabarit ForgeOne. Figtree (variable, OFL) remplace Inter comme famille
# de texte et de titre ; JetBrains Mono reste la famille des donnees.
# La variable couvre 100-900 pour le navigateur ; les instances statiques
# servent a matplotlib (voir charts.py) et de repli pour WeasyPrint.
FACES = [("Figtree", "100 900", "Figtree.ttf"), ("JetBrains Mono", "500", "JetBrainsMono-Medium.ttf"),
         ("Inter", "400", "Inter-Regular.otf"), ("Inter", "700", "Inter-Bold.otf")]


def font_css() -> str:
    return "".join(f"@font-face {{ font-family: '{fam}'; font-weight: {w}; font-display: swap; src: url('{(FONTS / f).as_uri()}'); }}\n" for fam, w, f in FACES if (FONTS / f).is_file())


# FR: les noms de mois passent par une table plutot que par la locale
# systeme, qui n'est pas garantie sur la machine qui genere le rapport.
MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre"]


def date_fr(dt) -> str:
    jour = "1er" if dt.day == 1 else str(dt.day)
    return f"{jour} {MOIS[dt.month - 1]} {dt.year}"


def context(vm: dict) -> dict:
    d = vm["d"]
    return vm | {
        "css": font_css() + (TEMPLATES / "report.css").read_text(),
        "date": date_fr(datetime.fromisoformat(d["run"]["finished_at"])),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rule_count": len(RULES),
        "rule_findings": sum(1 for f in d["findings"] if f["origin"] == "rule"),
        "act": jev.ACT,
        "yes": jev.YES,
        "no": jev.NO,
        "sources": sorted({a["source"] for a in vm["actions"]} | {"https://docs.typesafe.ai/primitives", "https://docs.typesafe.ai/confidence", "https://developers.google.com/speed/docs/insights/v5/about"}),
    }


def render_html(vm: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
    return env.get_template("report.html.j2").render(**context(vm))


def write_pdf(vm: dict, path: Path) -> Path:
    from weasyprint import HTML

    html = render_html(vm)
    path.with_suffix(".html").write_text(html)
    HTML(string=html, base_url=str(path.parent)).write_pdf(path)
    return path
