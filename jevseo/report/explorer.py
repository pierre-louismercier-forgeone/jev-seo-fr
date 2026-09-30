"""Explorateur interactif : un fichier HTML autonome pour fouiller l'audit.

Le rapport A4 repond a « qu'est-ce qui ne va pas ». L'explorateur repond a
« pourquoi Jev a-t-il dit ca, sur quelle page, avec quelle certitude ».

Tout vient d'`audit.json`, deja ecrit et deja paye : aucun appel supplementaire,
aucun cout. Ce qui n'etait qu'une synthese figee devient une matiere fouillable.

Les criteres sont affiches en francais (fr.QUESTIONS_FR) quelle que soit la
langue d'interrogation, puisque le livrable est francais ; le bandeau indique
dans quelle langue les questions ont reellement tourne.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from jevseo import fr, jev
from jevseo.report.pdf import MOIS

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
FONTS = Path(__file__).resolve().parent.parent / "fonts"
EXCERPT = 2500  # de quoi juger sur piece sans faire exploser le fichier


def _chemin(url: str, domaine: str) -> str:
    p = urlparse(url)
    return (p.path or "/") + (f"?{p.query}" if p.query else "")


def _libelles() -> dict:
    """Intitule et criteres en francais, par question."""
    out = {}
    for qid, (instructions, criteres) in fr.QUESTIONS_FR.items():
        if qid == "business_model":
            criteres = {k: (v if isinstance(v, str) else v.get("what", "")) for k, v in fr.MODELES_ENTREPRISE.items()}
        if isinstance(criteres, dict):
            criteres = {k: (v if isinstance(v, str) else v.get("what", "")) for k, v in criteres.items()}
        out[qid] = {"question": instructions, "criteres": criteres,
                    "courts": fr.LIBELLES_COURTS.get(qid, {})}
    return out


def _maillage(d: dict) -> dict:
    m = (d.get("jev") or {}).get("maillage") or {}
    g = fr.graphe_maillage(d["pages"])
    return {
        "n_sources": g["n_sources"], "n_cibles": len(g["sources_par_cible"]),
        "n_sitewide": len(g["sitewide"]), "n_gabarit": len(g["gabarit"]),
        "part_gabarit": g["part_gabarit"],
        "liens_contextuels": sum(len(v) for v in g["contextuels"].values()),
        "sans_entrant": len([u for u, _ in g["sources_par_cible"].items() if not g["entrants_ctx"].get(u)]),
        "n_candidats": m.get("n_candidats") or 0,
        "seuil": fr.SEUIL_LIEN, "marge": fr.MARGE_LIEN,
        "propositions": m.get("propositions") or [],
    }


def payload(d: dict) -> dict:
    site, scores = d["site"], d["scores"]
    domaine = site["domain"]
    jp = d["jev"].get("pages") or {}
    registre = (d["jev"].get("questions") or {}).get("page_example") or {}

    # Quelles actions touchent quelle page : la jointure que le rapport A4 ne fait pas.
    par_url = {}
    for a in d["actions"]:
        for u in a.get("urls", []):
            par_url.setdefault(u, []).append(a["action_id"])

    pages = []
    for p in d["pages"]:
        if p.get("kind") != "page" or p.get("status") != 200 or "word_count" not in p:
            continue
        a = jp.get(p["url"]) or {}
        pages.append({
            "url": p["url"],
            "chemin": _chemin(p["url"], domaine),
            "titre": p.get("title"),
            "h1": (p.get("h1") or [None])[0],
            "meta": p.get("meta_description"),
            "mots": p.get("word_count"),
            "profondeur": p.get("depth") if p.get("depth", 99) < 99 else None,
            "liens_entrants": p.get("inlinks", 0),
            "ttfb": p.get("ttfb_ms"),
            "ko": round((p.get("bytes") or 0) / 1024),
            "sitemap": bool(p.get("in_sitemap")),
            "plan": (p.get("outline") or [])[:20],
            "extrait": (p.get("text_excerpt") or "")[:EXCERPT],
            "extrait_tronque": len(p.get("text_excerpt") or "") > EXCERPT,
            "ouverture": jev.opening(p)[:400] if p.get("text_excerpt") else "",
            "contact": (p.get("contact") or {}) if isinstance(p.get("contact"), dict) else {},
            "actions": par_url.get(p["url"], []),
            "jev": {k: v for k, v in a.items() if isinstance(v, dict) and "band" in v},
            "anatomie": a.get("anatomie") or [],
        })
    pages.sort(key=lambda x: (x["chemin"] != "/", -(x["jev"].get("importance", {}).get("value") or 0)))

    actions = [{
        "id": a["action_id"], "titre": a["title"], "priorite": a["priority"], "gravite": a["severity"],
        "origine": a["origin"], "impact": a["impact"], "pages": a["count"], "categorie": a["category"],
        "preuve": a["evidence"], "correctif": a["fix"], "source": a["source"],
        "heuristique": bool(a.get("heuristic")), "a_verifier": a.get("needs_review") or 0,
        "urls": a.get("urls", [])[:60],
    } for a in d["actions"]]

    fini = datetime.fromisoformat(d["run"]["finished_at"])
    return {
        "domaine": domaine,
        "url": site["final_url"],
        "date": f"{fini.day if fini.day > 1 else '1er'} {MOIS[fini.month - 1]} {fini.year}",
        "score": scores["overall"], "note": scores["grade"],
        "categories": scores["categories"], "noms": scores["category_names"],
        "poids": scores["weights"], "notes_calcul": scores["notes"],
        "plafonds": scores.get("caps") or [], "partiel": scores.get("partial") or [],
        "pages": pages, "actions": actions,
        # FR: le maillage n'est pas une propriete d'une page, c'est une propriete
        # du graphe. Il lui faut son propre onglet, avec le partage gabarit /
        # contextuel en tete, sinon le lecteur croit que `liens_entrants: 29`
        # veut dire quelque chose.
        "maillage": _maillage(d),
        "libelles": _libelles(),
        "roles": {k: (v if isinstance(v, str) else v.get("what", "")) for k, v in fr.ROLES_PASSAGE.items()},
        "roles_courts": {"reponse": "Réponse", "preuve": "Preuve", "decor": "Décor",
                         "navigation": "Navigation", "unclear": "Indécidable"},
        "registre": {k: {"type": v.get("type")} for k, v in registre.items()},
        "bandes": {"act": jev.ACT, "yes": jev.YES, "no": jev.NO},
        "langue_questions": fr.LANGUE_QUESTIONS,
        "ledger": {k: v for k, v in (d["jev"].get("ledger") or {}).items() if k != "errors"},
        "dfs": bool((d.get("dataforseo") or {}).get("available")),
        "outil": d.get("tool", {}),
    }


def write_explorer(d: dict, path: Path) -> Path:
    gabarit = (TEMPLATES / "explorer.html").read_text()
    police = ""
    for fam, f in (("Figtree", "Figtree.ttf"), ("JetBrains Mono", "JetBrainsMono-Medium.ttf")):
        if (FONTS / f).is_file():
            police += f"@font-face {{ font-family: '{fam}'; font-weight: 100 900; font-display: swap; src: url('{(FONTS / f).as_uri()}'); }}\n"
    html = gabarit.replace("/*__FONTS__*/", police).replace(
        '"__DATA__"', json.dumps(payload(d), ensure_ascii=False, separators=(",", ":")))
    path.write_text(html)
    return path
