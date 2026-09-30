"""Search Console : la seule source qui mesure des clics reels.

Ce que les autres couches ne savent pas faire. Le crawl decrit le site,
DataForSEO estime un marche, Jev juge un contenu. Aucun des trois ne dit ce
qui rapporte deja des clics. Avant une refonte, c'est pourtant la premiere
question : qu'est-ce qu'on risque de casser ?

Lecture seule, gratuite, non plafonnee par un budget : il n'y a rien a
depenser. Le seul cout est le temps de reponse de l'API.

Authentification : jeton OAuth de rafraichissement dans
`~/.config/lunae/gsc_token.json` (surchargeable par GSC_TOKEN_FILE), le
format produit par les scripts GSC maison. Portee `webmasters.readonly`.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

API = "https://www.googleapis.com/webmasters/v3"
JETON = Path(os.environ.get("GSC_TOKEN_FILE") or Path.home() / ".config/lunae/gsc_token.json")
FENETRE = 28  # jours. Aligne sur la fenetre de recheck apres une action.
LIGNES = 5000


def _jeton() -> str | None:
    """Echange le jeton de rafraichissement contre un jeton d'acces."""
    if not JETON.is_file():
        return None
    try:
        t = json.loads(JETON.read_text())
        corps = urllib.parse.urlencode({
            "client_id": t["client_id"], "client_secret": t["client_secret"],
            "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode()
        with urllib.request.urlopen(urllib.request.Request(t["token_uri"], data=corps), timeout=30) as r:
            return json.load(r)["access_token"]
    except Exception:
        return None


def _appel(chemin: str, jeton: str, corps: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{API}/{chemin}",
        data=json.dumps(corps).encode() if corps is not None else None,
        headers={"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def propriete(domaine: str, jeton: str) -> str | None:
    """Trouve la propriete GSC qui correspond au domaine audite.

    Une propriete peut etre declaree en `sc-domain:` ou en prefixe d'URL, avec
    ou sans www. On prefere la propriete domaine, qui couvre tous les sous
    domaines et tous les protocoles.
    """
    nu = domaine.lower().removeprefix("www.")
    try:
        sites = _appel("sites", jeton).get("siteEntry", [])
    except Exception:
        return None
    candidats = []
    for s in sites:
        u = s["siteUrl"]
        hote = u.removeprefix("sc-domain:") if u.startswith("sc-domain:") else urllib.parse.urlparse(u).netloc
        if hote.lower().removeprefix("www.") == nu:
            candidats.append((0 if u.startswith("sc-domain:") else 1, u))
    return min(candidats)[1] if candidats else None


def _lignes(prop: str, jeton: str, dims: list[str], debut: str, fin: str) -> list[dict]:
    corps = {"startDate": debut, "endDate": fin, "dimensions": dims, "rowLimit": LIGNES}
    d = _appel(f"sites/{urllib.parse.quote(prop, safe='')}/searchAnalytics/query", jeton, corps)
    return d.get("rows", [])


def collect(domaine: str, jours: int = FENETRE, log=print) -> dict:
    """Clics, impressions et positions reels, par requete et par page."""
    out = {"available": False, "raison": None, "fenetre_jours": jours,
           "requetes": [], "pages": [], "paires": [], "totaux": {}}

    jeton = _jeton()
    if not jeton:
        out["raison"] = f"aucun jeton lisible ({JETON})"
        log("Search Console : ignoree, aucun jeton")
        return out

    prop = propriete(domaine, jeton)
    if not prop:
        out["raison"] = f"{domaine} absent des proprietes accessibles"
        log(f"Search Console : {domaine} ne figure pas dans les proprietes accessibles")
        return out

    # Google publie les donnees avec environ deux jours de retard.
    fin = date.today() - timedelta(days=3)
    debut = fin - timedelta(days=jours)
    d0, d1 = debut.isoformat(), fin.isoformat()
    out |= {"propriete": prop, "debut": d0, "fin": d1}

    try:
        req = _lignes(prop, jeton, ["query"], d0, d1)
        pages = _lignes(prop, jeton, ["page"], d0, d1)
        paires = _lignes(prop, jeton, ["query", "page"], d0, d1)
    except urllib.error.HTTPError as err:
        out["raison"] = f"HTTP {err.code}"
        log(f"Search Console : echec, HTTP {err.code}")
        return out
    except Exception as err:
        out["raison"] = type(err).__name__
        log(f"Search Console : echec, {type(err).__name__}")
        return out

    ligne = lambda r: {"clics": r["clicks"], "impressions": r["impressions"],
                       "ctr": round(r["ctr"], 4), "position": round(r["position"], 1)}
    out["requetes"] = sorted(({"requete": r["keys"][0], **ligne(r)} for r in req),
                             key=lambda x: (-x["clics"], -x["impressions"]))
    out["pages"] = sorted(({"url": r["keys"][0], **ligne(r)} for r in pages),
                          key=lambda x: (-x["clics"], -x["impressions"]))
    out["paires"] = [{"requete": r["keys"][0], "url": r["keys"][1], **ligne(r)} for r in paires]
    # Piege GSC : la dimension « requete » est filtree, Google retire les
    # requetes anonymisees. Elle sous-compte donc systematiquement. Les totaux
    # de trafic se lisent sur la dimension « page », qui est complete ; la
    # dimension requete ne sert qu'a savoir SUR QUOI le site est vu.
    out["totaux"] = {
        "clics": sum(p["clics"] for p in out["pages"]),
        "impressions": sum(p["impressions"] for p in out["pages"]),
        "clics_attribues_a_une_requete": sum(r["clics"] for r in out["requetes"]),
        "requetes": len(out["requetes"]),
        "pages": len(out["pages"]),
    }
    t = out["totaux"]
    out["totaux"]["ctr"] = round(t["clics"] / t["impressions"], 4) if t["impressions"] else 0.0
    # Part du trafic que Google rattache a une requete nommee. En dessous de
    # ~60 %, toute lecture par requete porte sur une minorite du trafic.
    out["totaux"]["couverture_requetes"] = (
        round(t["clics_attribues_a_une_requete"] / t["clics"], 3) if t["clics"] else None)
    out["available"] = True
    t = out["totaux"]
    log(f"Search Console : {prop}, {jours} jours, {t['clics']} clics et {t['impressions']} impressions "
        f"sur {t['pages']} pages ; {t['requetes']} requetes nommees couvrant "
        f"{(t['couverture_requetes'] or 0):.0%} des clics")
    return out


# ------------------------------------------------------------- lectures

def cannibalisation_reelle(paires: list[dict], mini_impressions: int = 30) -> list[dict]:
    """Requetes sur lesquelles plusieurs URL du site apparaissent reellement.

    C'est la cannibalisation mesuree, pas jugee. La couche Jev demande a un
    modele si deux pages viseraient la meme intention ; ici Google dit qu'il
    hesite deja entre elles, ce qui est une preuve et non une estimation.
    """
    par_requete = defaultdict(list)
    for p in paires:
        par_requete[p["requete"]].append(p)
    out = []
    for requete, lot in par_requete.items():
        vus = [x for x in lot if x["impressions"] >= 5]
        if len(vus) < 2:
            continue
        total = sum(x["impressions"] for x in vus)
        if total < mini_impressions:
            continue
        vus.sort(key=lambda x: -x["impressions"])
        out.append({"requete": requete, "urls": vus[:4], "impressions": total,
                    "clics": sum(x["clics"] for x in vus)})
    return sorted(out, key=lambda x: -x["impressions"])


def impressions_sans_clics(requetes: list[dict], mini: int = 100, ctr_max: float = 0.005) -> list[dict]:
    """Requetes vues mais jamais cliquees : le site apparait et n'est pas choisi."""
    return [r for r in requetes if r["impressions"] >= mini and r["ctr"] <= ctr_max]


def a_portee(requetes: list[dict], mini: int = 30) -> list[dict]:
    """Requetes entre la 4e et la 20e place avec des impressions reelles."""
    return sorted((r for r in requetes if 4 <= r["position"] <= 20 and r["impressions"] >= mini),
                  key=lambda r: -r["impressions"])


def pages_motrices(pages: list[dict], part: float = 0.8) -> list[dict]:
    """Les pages qui portent la part dominante des clics.

    A produire avant toute refonte : ce sont elles qu'on risque de casser.
    """
    total = sum(p["clics"] for p in pages) or 1
    cumul, out = 0, []
    for p in sorted(pages, key=lambda x: -x["clics"]):
        if p["clics"] == 0:
            break
        out.append(p)
        cumul += p["clics"]
        if cumul / total >= part:
            break
    return out
