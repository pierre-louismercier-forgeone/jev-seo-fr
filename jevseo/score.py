"""Turn rule findings and Jev judgments into category scores and a ranked action list.

Every number here is a transparent internal rubric, not a ranking or traffic
prediction. The formulas are printed in the report's method section.
"""
from __future__ import annotations

from statistics import mean
from urllib.parse import urlparse

from jevseo import fr
from jevseo.checks import CATEGORIES, SEVERITY_WEIGHT, SRC, html_pages

DEDUCT = {"critical": 25, "high": 12, "medium": 6, "low": 2, "info": 0}
CATEGORY_WEIGHT = {"crawl": 20, "onpage": 15, "content": 20, "links": 10, "structured": 8, "ai": 12, "performance": 10, "security": 5, "visibility": 15}
JUDGED_SHARE = 0.7  # content and AI readiness: 70% Jev judgment, 30% rules

# id: (category, severity, title, fix, source key, effort)
JEV_RULES = {
    "jev_value_prop": ("content", "high", "L'accueil ne rend pas l'offre claire", "Dites ce que vous proposez, a qui, et pourquoi vous choisir des le premier ecran de la page d'accueil.", "helpful", 2),
    "jev_entity_clarity": ("ai", "medium", "L'accueil ne dit pas clairement qui, quoi et ou", "Enoncez le nom de l'organisation, son activite et son marche ou sa zone en mots simples, pres du haut de page. Heuristique editoriale : Google indique qu'aucune optimisation particuliere n'est requise pour ses fonctionnalites IA.", "ai", 1),
    "jev_local_schema": ("structured", "medium", "Entreprise locale sans donnees structurees LocalBusiness", "Ajoutez un JSON-LD LocalBusiness avec le nom, l'adresse, le telephone et les horaires, coherents avec la page.", "sd", 2),
    "jev_helpfulness": ("content", "high", "Pages importantes qui ne satisfont pas le visiteur", "Etoffez ces pages avec ce dont le visiteur a besoin : reponses, details concrets, exemples et suite a donner.", "helpful", 3),
    "jev_specificity": ("content", "medium", "Contenu generique que n'importe quel concurrent pourrait publier", "Ajoutez du concret de premiere main : vos chiffres, vos process, vos exemples, vos lieux, vos noms et vos resultats.", "helpful", 3),
    "jev_trust": ("content", "medium", "Les pages cles montrent peu de preuves d'expertise ou de confiance", "Ajoutez des personnes nommees, des qualifications, des avis, des sources, des resultats et des coordonnees la ou cela aide le lecteur.", "helpful", 2),
    "jev_next_step": ("content", "medium", "Pages commerciales sans suite evidente", "Donnez a chaque page commerciale un appel a l'action unique, evident et pertinent.", "starter", 1),
    "jev_title_fit": ("onpage", "medium", "Titles qui decrivent mal la page", "Reecrivez ces titles en nommant ce que la page offre, dans les mots de l'internaute.", "title", 1),
    "jev_meta_fit": ("onpage", "low", "Meta descriptions faibles", "Reecrivez ces descriptions en resume precis de ce que la page apporte.", "snippet", 1),
    "jev_h1_fit": ("onpage", "low", "Titres principaux qui n'enoncent pas le sujet", "Faites du H1 le sujet de la page plutot qu'un slogan.", "starter", 1),
    "jev_answer_first": ("ai", "low", "Pages qui enterrent l'essentiel", "Ouvrez par une reponse ou une offre en une ou deux phrases, avant tout preambule. Heuristique editoriale pour les lecteurs et les moteurs de reponse, pas une exigence de Google.", "ai", 1),
    "jev_citable": ("ai", "medium", "Peu de faits autonomes et citables", "Ajoutez des enonces factuels clairs, des definitions et des chiffres qui se suffisent a eux-memes. Heuristique editoriale, pas une exigence de Google.", "ai", 2),
    "jev_rewrite": ("content", "medium", "Pages que Jev reecrirait ou regrouperait", "Passez chaque page en revue au regard de l'action suggeree. C'est un jugement editorial de Jev, pas une regle de moteur.", "helpful", 3),
    # FR: constats issus des deux questions locales ajoutees par le fork.
    # La preuve locale est le vrai discriminant d'une page ville : sans elle,
    # la page n'est qu'un nom de ville pose sur du texte generique, ce qui est
    # exactement ce que Google qualifie de page satellite.
    "jev_preuve_locale": ("content", "high", "Pages ville sans preuve d'activite sur place", "Ajoutez du concret local et verifiable : chantiers ou dossiers traites dans cette ville, quartiers desservis, delais d'intervention reels, avis de clients de la ville, equipe qui couvre le secteur. Le nom de la ville dans un texte generique ne suffit pas.", "doorway", 3),
    "jev_coordonnees_locales": ("content", "medium", "Pages ville dont le seul contact est le siege", "Donnez a chaque page ville un contact rattache a ce lieu : ligne locale, adresse de l'antenne, ou a defaut une mention explicite de la zone couverte depuis le siege. Un numero de siege sans rattachement local affaiblit le signal de proximite.", "starter", 1),
    # FR: constats issus de l'anatomie de page. La ou `jev_answer_first` dit
    # seulement « la page enterre l'essentiel », ceux-ci disent a quel endroit
    # la reponse arrive et ce qu'il y a a la place avant elle.
    "jev_reponse_enterree": ("content", "high", "Pages ou la reponse arrive trop tard", "Remontez en tete de page le passage qui repond reellement, puis gardez le contexte et les preuves apres. Un lecteur comme un moteur de reponse doivent obtenir l'essentiel avant de faire defiler.", "helpful", 2),
    "jev_sans_reponse": ("content", "high", "Pages ou aucun passage ne repond", "Ecrivez le passage qui manque : la reponse concrete a ce que la page promet. En l'etat, le texte tourne autour du sujet sans le traiter.", "helpful", 3),
    "jev_page_creuse": ("content", "medium", "Pages surtout composees de decor", "Remplacez le remplissage et les listes de liens par du contenu porteur : reponse, preuve verifiable, description d'offre, traitement d'objection.", "helpful", 3),
    "jev_cannibalization": ("content", "medium", "Pages qui se disputent les memes recherches", "Tranchez : une page par besoin de recherche. Fusionnez, differenciez, ou canonicalisez la plus faible.", "canonical", 2),
    # FR: maillage. Les regles deterministes de checks.py disent que le maillage
    # editorial manque ; celle-ci dit ou mettre les liens. Voir fr.cibles_maillage :
    # le code presélectionne 8 cibles, Jev juge l'utilite du lien pour le lecteur.
    "jev_maillage_manquant": ("links", "medium", "Liens de contenu manquants entre pages qui se repondent", "Ajoutez ces liens dans le corps du texte, a l'endroit ou le lecteur en a besoin, avec une ancre qui decrit la destination.", "links", 2),
}
LOW = 0.45  # normalised Score below this becomes a finding
# Jev findings whose advice is editorial rather than a documented search engine requirement
HEURISTIC_JEV = {"jev_entity_clarity", "jev_answer_first", "jev_citable", "jev_rewrite", "jev_h1_fit", "jev_next_step", "jev_preuve_locale", "jev_coordonnees_locales", "jev_reponse_enterree", "jev_sans_reponse", "jev_page_creuse", "jev_maillage_manquant"}
REACHABLE_KD = 30  # DataForSEO keyword difficulty treated as winnable without major authority (heuristic)
DFS_RULES = {
    "dfs_striking": ("visibility", "medium", "Mots cles pertinents aux portes de la premiere page", "Renforcez la page positionnee sur chaque mot cle : repondez plus completement a la recherche, ajoutez-lui des liens internes et resserrez son title.", "dfs_labs", 2),
    "dfs_existing_page": ("visibility", "medium", "Mots cles pertinents qu'une page existante pourrait gagner", "Etoffez la page indiquee pour couvrir le besoin de chaque mot cle, puis liez-la depuis les pages connexes.", "dfs_labs", 2),
    "dfs_new_page": ("visibility", "medium", "Mots cles pertinents sans page pour se positionner", "Prevoyez une page par besoin de recherche distinct ; commencez par les mots cles au volume le plus fort et a la difficulte la plus faible.", "dfs_labs", 3),
    "dfs_backlink_gap": ("visibility", "medium", "Bien moins de domaines referents que les sites positionnes sur les memes mots cles", "Gagnez des liens depuis les sites que votre audience lit deja : donnees originales, outils, expertise invitee et pages partenaires.", "dfs_backlinks", 4),
    # FR: l'absence d'opportunite etait notee comme l'absence de probleme.
    # Sur publi3.com, 11 mots cles positionnes mais tous hors sujet et au-dela
    # de la 20e place : aucune regle ne pouvait se declencher (dfs_striking
    # exige une position entre 4 et 20, les regles d'opportunite exigent une
    # pertinence jugee), donc rien n'etait deduit et la visibilite sortait a
    # 94/100 sur un site qui fait 5 visites estimees par mois. Un tel chiffre
    # dans un livrable client detruit la credibilite du rapport.
    "dfs_invisible": ("visibility", "critical", "Aucune requete metier dans le top 20", "Le site ne se positionne sur aucune recherche liee a son activite, en premiere ou deuxieme page. Avant toute optimisation, il faut creer les pages qui repondent aux intentions commerciales du metier : une page par prestation, puis une page par couple prestation x cible ou prestation x zone.", "dfs_labs", 4),
    # FR: constats issus de la Search Console. Seule source de CLICS REELS.
    # Le crawl decrit, DataForSEO estime, Jev juge ; aucun ne mesure.
    "gsc_cannibalisation_reelle": ("visibility", "high", "Plusieurs pages se disputent reellement la meme requete", "Choisissez la page qui doit porter chaque requete, puis desindexez, fusionnez ou reorientez les autres. Contrairement a une cannibalisation estimee, celle-ci est constatee : Google affiche deja plusieurs de vos URL sur ces recherches et n'en privilegie aucune.", "canonical", 2),
    "gsc_impressions_sans_clics": ("visibility", "medium", "Requetes ou le site est vu mais jamais choisi", "Le positionnement n'est pas le probleme sur ces requetes, la promesse l'est. Reecrivez le title et la meta description de la page qui ressort, en repondant a la recherche dans les mots de l'internaute.", "snippet", 1),
    "gsc_a_portee": ("visibility", "medium", "Requetes a portee de la premiere page", "Ces requetes ont des impressions reelles entre la 4e et la 20e place. Renforcez la page qui ressort : repondez plus completement, ajoutez-lui des liens internes, resserrez son title.", "dfs_labs", 2),
    "gsc_pages_motrices": ("visibility", "info", "Pages qui portent la majorite des clics", "A proteger avant toute refonte : conservez leurs URL, ou redirigez-les en permanent vers l'equivalent exact. Toute perte ici se paie immediatement en trafic.", "redirects", 1),
    "dfs_broken_backlinks": ("visibility", "medium", "Backlinks pointant vers des pages cassees", "Redirigez chaque cible cassee vers la page vivante la plus proche pour que ces liens comptent a nouveau.", "dfs_backlinks", 1),
    "dfs_aio_not_cited": ("ai", "low", "Apercus IA qui ne citent pas le site", "Regardez qui est cite aujourd'hui et assurez-vous que la page repond directement a la recherche. Google indique qu'aucune exigence supplementaire n'existe pour apparaitre dans les Apercus IA au-dela de l'eligibilite normale a la recherche.", "ai", 2),
}
LABEL = {"helpfulness": "utilite", "specificity": "specificite", "trust": "confiance", "clear_next_step": "P(suite evidente)", "title_fit": "adequation du title",
         "meta_fit": "adequation de la meta description", "h1_fit": "P(le H1 enonce le sujet)", "answer_first": "P(ouvre sur l'essentiel)", "citable": "citabilite", "preuve_locale": "preuve locale", "contact_local": "P(contact local)"}
SITE_LEVEL = {
    "dfs_striking", "dfs_existing_page", "dfs_new_page", "dfs_backlink_gap", "dfs_broken_backlinks", "dfs_aio_not_cited",
    "robots_missing", "robots_blocks_site", "sitemap_missing", "sitemap_errors", "soft_404", "host_variant", "no_https",
    "no_structured_data", "ai_bots_blocked", "llms_txt_missing", "hsts_missing", "security_headers", "favicon_missing",
    "jev_value_prop", "jev_entity_clarity", "jev_local_schema",
}


def reach(f: dict, n_pages: int) -> float:
    return 1.0 if f["id"] in SITE_LEVEL else min(1.0, f["count"] / max(n_pages, 1))


def jev_finding(rule_id: str, urls: list[str], evidence: str, review: int, detail: dict | None = None, severity: str | None = None) -> dict:
    cat, sev, title, fix, src, effort = JEV_RULES[rule_id]
    sev = severity or sev
    return {"id": rule_id, "origin": "jev", "category": cat, "severity": sev, "title": title, "fix": fix, "source": SRC[src], "effort": effort, "heuristic": rule_id in HEURISTIC_JEV, "urls": urls, "count": len(urls), "evidence": evidence, "needs_review": review, "detail": detail or {}}


def jev_findings(crawl: dict, judged: dict) -> list[dict]:
    out = []
    site = judged.get("site") or {}
    pages = judged.get("pages") or {}
    home = crawl["final_url"]
    if site:
        vp = site["value_prop"]
        if vp["value"] < 0.6:
            # An undecided Jev answer is a signal to check, not a headline finding.
            out.append(jev_finding("jev_value_prop", [home], f"Jev value proposition {vp['value']:.2f} (confidence {vp['confidence']:.2f})", int(vp["band"] == "review"),
                                   severity=None if vp["band"] == "act" else "low"))
        ec = site["entity_clarity"]
        if ec["band"] == "no" or (ec["band"] == "review" and ec["value"] < 0.5):
            out.append(jev_finding("jev_entity_clarity", [home], f"Jev P(homepage states who, what and where) {ec['value']:.2f}", int(ec["band"] == "review"),
                                   severity=None if ec["band"] == "no" else "low"))
        local = site["serves_local_area"]
        home_types = " ".join(next((p.get("schema_types", []) for p in crawl["pages"] if p.get("url") == home), [])).lower()
        if local["value"] >= 0.5 and "localbusiness" not in home_types and not any(t in home_types for t in ("restaurant", "store", "dentist", "attorney", "plumber", "medical")):
            out.append(jev_finding("jev_local_schema", [home], f"Serves a local area P(yes) {local['value']:.2f}; homepage schema: {home_types or 'none'}", int(local["band"] == "review")))

    def collect(key, test, only=None):
        urls, review, ev = [], 0, []
        for url, ans in pages.items():
            if not ans or key not in ans or (only and not only(ans)):
                continue
            # Policy and contact pages are not expected to be citable, specific or answer-first.
            if key not in ("title_fit", "h1_fit") and ans["page_type"]["value"] in ("legal_or_policy", "contact_or_location") and ans["page_type"]["band"] == "act":
                continue
            a = ans[key]
            if test(a):
                urls.append(url)
                review += a["band"] == "review"
                ev.append(a["value"])
        return urls, review, ev

    # FR: anatomie. Trois lectures d'une meme sequence de roles.
    PORTEURS = {"reponse", "preuve"}  # v2 : deux roles porteurs, decor et navigation ne portent rien
    enterrees, sans, creuses = [], [], []
    for url, ans in pages.items():
        anat = (ans or {}).get("anatomie")
        if not anat or (ans["importance"]["value"] if "importance" in ans else 1) < 0.34:
            continue
        rep = next((x for x in anat if x["role"] == "reponse"), None)
        if rep is None:
            sans.append((url, anat))
        elif rep["debut"] >= fr.SEUIL_REPONSE_ENTERREE:
            enterrees.append((url, rep["debut"]))
        part = sum(x["part"] for x in anat if x["role"] in PORTEURS)
        if part < fr.SEUIL_PAGE_CREUSE:
            creuses.append((url, part))
    if enterrees:
        enterrees.sort(key=lambda t: -t[1])
        out.append(jev_finding("jev_reponse_enterree", [u for u, _ in enterrees],
                               "; ".join(f"{urlparse(u).path or '/'} : la reponse arrive a {d:.0%} de la page" for u, d in enterrees[:6]),
                               0, detail={"pages": [{"url": u, "debut": d} for u, d in enterrees]}))
    if sans:
        out.append(jev_finding("jev_sans_reponse", [u for u, _ in sans],
                               "; ".join(f"{urlparse(u).path or '/'} : que du " + ", ".join(sorted({x['role'] for x in a})) for u, a in sans[:5]), 0))
    if creuses:
        creuses.sort(key=lambda t: t[1])
        out.append(jev_finding("jev_page_creuse", [u for u, _ in creuses],
                               "; ".join(f"{urlparse(u).path or '/'} : {p:.0%} de passages porteurs" for u, p in creuses[:6]), 0))

    important = lambda ans: ans["importance"]["value"] >= 0.5  # noqa: E731
    commercial = lambda ans: ans["page_type"]["value"] in ("homepage", "product_or_service", "pricing") or ans["intent"]["value"] in ("commercial", "transactional", "local")  # noqa: E731
    specs = [
        ("jev_helpfulness", "helpfulness", lambda a: a["value"] < LOW, important),
        ("jev_specificity", "specificity", lambda a: a["value"] < LOW, None),
        ("jev_trust", "trust", lambda a: a["value"] < LOW, important),
        ("jev_next_step", "clear_next_step", lambda a: a["value"] < 0.5, commercial),
        ("jev_title_fit", "title_fit", lambda a: a["value"] < LOW, None),
        ("jev_meta_fit", "meta_fit", lambda a: a["value"] < LOW, None),
        ("jev_h1_fit", "h1_fit", lambda a: a["value"] < 0.5, None),
        ("jev_answer_first", "answer_first", lambda a: a["value"] < 0.5, None),
        # FR: ne s'appliquent qu'aux pages qui portent ces questions, donc aux
        # pages locales reperees par fr.page_locale().
        ("jev_preuve_locale", "preuve_locale", lambda a: a["value"] < LOW, None),
        ("jev_coordonnees_locales", "contact_local", lambda a: a["value"] < 0.5, None),
        ("jev_citable", "citable", lambda a: a["value"] < LOW, None),
        ("jev_rewrite", "action", lambda a: a["value"] in ("rewrite", "merge_or_remove"), None),
    ]
    words = {p["url"]: p.get("word_count", 0) for p in crawl["pages"] if p.get("kind") == "page"}
    for rule_id, key, test, only in specs:
        urls, review, vals = collect(key, test, only)
        if key == "action":
            # Code checks Jev against the evidence: a removal verdict on a substantial page is not acted on.
            keep = [i for i, u in enumerate(urls) if not (pages[u]["action"]["value"] in ("merge_or_remove", "noindex_or_remove") and words.get(u, 0) >= 600)]
            urls, vals = [urls[i] for i in keep], [vals[i] for i in keep]
            review = sum(1 for u in urls if pages[u]["action"]["band"] == "review")
        if urls:
            if key == "action":
                detail = {"actions": {u: pages[u]["action"]["value"] for u in urls}}
                evidence = f"{len(urls)} page{'s' if len(urls) != 1 else ''}: " + "; ".join(f"{urlparse(u).path or '/'} ({pages[u]['action']['value'].replace('_', ' ')})" for u in urls[:6])
            else:
                detail = {"values": {u: pages[u][key]["value"] for u in urls}}
                where = ": " + ", ".join(urlparse(u).path or "/" for u in urls) if len(urls) <= 3 else ""
                evidence = f"Jev {LABEL[key]} averaged {mean(vals):.2f} (0 worst, 1 best) on {len(urls)} page{'s' if len(urls) != 1 else ''}{where}"
            out.append(jev_finding(rule_id, urls, evidence, review, detail))
    pairs = [p for p in judged.get("pairs", []) if p["judgment"] and p["judgment"]["value"] >= 0.6]
    if pairs:
        urls = sorted({u for p in pairs for u in (p["a"], p["b"])})
        out.append(jev_finding("jev_cannibalization", urls, f"{len(pairs)} page pairs judged to compete (P(yes) at least 0.6)", sum(p["judgment"]["band"] == "review" for p in pairs), {"pairs": pairs}))
    return out


def opportunity_key(k: dict) -> tuple:
    """Tiers: reachable (difficulty 30 or less), difficulty unknown, then longer term. Within a tier,
    searches discounted by difficulty. Sort with reverse=True."""
    kd = k.get("difficulty")
    tier = 2 if kd is not None and kd <= REACHABLE_KD else 1 if kd is None else 0
    return (tier, (k.get("volume") or 0) * (1 - min(kd if kd is not None else 50, 100) / 100))


def maillage_findings(crawl: dict, judged: dict) -> list[dict]:
    """Liens proposes par Jev, regroupes en un seul constat.

    Un constat par lien noierait le rapport : ce qui compte est la liste, pas
    chaque ligne. Les urls du constat sont les pages SOURCES, celles ou il y a
    un geste a faire.
    """
    m = (judged or {}).get("maillage") or {}
    props = m.get("propositions") or []
    if not props:
        return []
    srcs = sorted({x["source"] for x in props})
    orphelines = sum(1 for x in props if x["entrants_ctx"] == 0)
    # `needs_review` reste a zero volontairement : sur cette question la bande
    # generique du noul (oui a partir de 0,80) est inadaptee et classerait tout
    # en « a verifier ». Le filtre est la valeur, mesuree stable a 0,05 pres sur
    # trois passages, avec un trou franc dans la distribution. Voir fr.SEUIL_LIEN.
    limites = sum(1 for x in props if x.get("limite"))
    ev = ("%d liens de contenu proposes depuis %d pages sur %d candidates, dont %d vers des pages qui n'en recoivent aucun aujourd'hui."
          % (len(props), len(srcs), m.get("n_candidats") or len(props), orphelines)
          + (" %d sont a la limite du seuil et demandent un oeil humain." % limites if limites else ""))
    return [jev_finding("jev_maillage_manquant", srcs, ev, 0, {"propositions": props[:200]})]


def dfs_finding(rule_id: str, urls: list[str], count: int, evidence: str, detail: dict | None = None, review: int = 0, heuristic: bool = False) -> dict:
    cat, sev, title, fix, src, effort = DFS_RULES[rule_id]
    return {"id": rule_id, "origin": "dataforseo", "category": cat, "severity": sev, "title": title, "fix": fix, "source": SRC[src], "effort": effort,
            "heuristic": heuristic, "urls": urls, "count": count, "evidence": evidence, "needs_review": review, "detail": detail or {}}


def gsc_finding(rule_id: str, urls: list[str], count: int, evidence: str, detail: dict | None = None, review: int = 0) -> dict:
    """Comme dfs_finding, mais l'origine dit « Search Console ».

    La distinction compte dans un livrable : DataForSEO estime un marche,
    la Search Console mesure des clics. Les deux ne se defendent pas pareil
    devant un client.
    """
    return dfs_finding(rule_id, urls, count, evidence, detail, review) | {"origin": "gsc"}


def gsc_findings(crawl: dict, g: dict | None) -> list[dict]:
    """Constats fondes sur des clics reels, pas sur des estimations."""
    if not g or not g.get("available"):
        return []
    from jevseo import gsc as gsc_mod

    out, home = [], crawl["final_url"]
    court = lambda u: urlparse(u).path or "/"

    can = gsc_mod.cannibalisation_reelle(g["paires"])
    if can:
        urls = sorted({x["url"] for c in can for x in c["urls"]})
        out.append(gsc_finding(
            "gsc_cannibalisation_reelle", urls[:60], len(can),
            "; ".join(f"« {c['requete']} » : {len(c['urls'])} URL, {c['impressions']} impressions, {c['clics']} clics"
                      for c in can[:5]),
            {"requetes": can[:40]}, 0))

    isc = gsc_mod.impressions_sans_clics(g["requetes"])
    if isc:
        out.append(gsc_finding(
            "gsc_impressions_sans_clics", [home], len(isc),
            "; ".join(f"« {r['requete']} » : {r['impressions']} impressions, {r['clics']} clic"
                      + (f", position {r['position']}" if r["position"] else "") for r in isc[:6]),
            {"requetes": isc[:40]}, 0))

    ap = gsc_mod.a_portee(g["requetes"])
    if ap:
        out.append(gsc_finding(
            "gsc_a_portee", [home], len(ap),
            "; ".join(f"« {r['requete']} » : position {r['position']}, {r['impressions']} impressions" for r in ap[:6]),
            {"requetes": ap[:40]}, 0))

    pm = gsc_mod.pages_motrices(g["pages"])
    if pm:
        total = g["totaux"]["clics"] or 1
        out.append(gsc_finding(
            "gsc_pages_motrices", [p["url"] for p in pm], len(pm),
            f"{len(pm)} pages sur {len(g['pages'])} portent {sum(p['clics'] for p in pm) / total:.0%} des clics ; "
            + "; ".join(f"{court(p['url'])} : {p['clics']} clics" for p in pm[:5]),
            {"pages": pm}, 0))
    return out


def dfs_findings(crawl: dict, judged: dict, dfs: dict | None) -> list[dict]:
    """Keyword and authority findings. Jev relevance decides which keywords matter to this business."""
    if not dfs or not dfs.get("available"):
        return []
    out = []
    home = crawl["final_url"]
    kj = judged.get("keywords") or {}

    def rel(kw):
        if not kj:
            return 0.5  # no Jev: keep ranked keywords, but opportunities need a relevance judgment
        a = kj.get(kw)
        return a["relevance"]["value"] if a else None

    def fmt(k):
        hard = k.get("difficulty") is not None and k["difficulty"] > REACHABLE_KD
        return ("longer term: " if hard else "difficulty unknown: " if k.get("difficulty") is None else "") + f"{k['keyword']}" + (f" (+{k['variants']} rewordings)" if k.get("variants") else "") + f" ({k.get('volume') or 0:,}/mo" + (f", position {k['position']}" if k.get("position") else "") + (f", difficulty {k['difficulty']}" if k.get("difficulty") is not None else "") + ")"

    def other_brand(kw):
        a = kj.get(kw) or {}
        return (a.get("other_brand") or {}).get("value", 0) >= 0.5

    def opportunity(k):
        return opportunity_key(k)

    # FR: mesure de la visibilite REELLE, avant toute regle d'amelioration.
    # Une requete ne vaut que si elle est dans le top 20, pertinente pour le
    # metier, et pas une recherche de marque tierce.
    ranked_all = dfs.get("ranked") or []
    visibles = [k for k in ranked_all
                if k.get("position") and k["position"] <= 20
                and (rel(k["keyword"]) or 0) >= 0.5 and not other_brand(k["keyword"])]
    if ranked_all and not visibles:
        pertinents = [k for k in ranked_all if (rel(k["keyword"]) or 0) >= 0.5 and not other_brand(k["keyword"])]
        meilleure = min((k["position"] for k in pertinents if k.get("position")), default=None)
        etv = (dfs.get("overview") or {}).get("etv")
        preuve = (f"{len(ranked_all)} requetes positionnees, dont {len(pertinents)} jugees pertinentes par Jev et hors marque tierce ; "
                  + (f"la meilleure est en position {meilleure}" if meilleure else "aucune n'est positionnee")
                  + (f" ; trafic organique estime {round(etv)} visites/mois" if etv is not None else ""))
        out.append(dfs_finding("dfs_invisible", [home], len(ranked_all), preuve,
                               {"ranked_total": len(ranked_all), "pertinents": len(pertinents),
                                "meilleure_position": meilleure, "etv": etv}, 0))

    striking = [k for k in ranked_all if k.get("position") and 4 <= k["position"] <= 20 and (rel(k["keyword"]) or 0) >= 0.5 and not other_brand(k["keyword"])]
    if striking:
        striking.sort(key=opportunity, reverse=True)
        out.append(dfs_finding("dfs_striking", sorted({k["url"] for k in striking if k.get("url")}) or [home], len(striking),
                               "; ".join(fmt(k) for k in striking[:6]), {"keywords": striking},
                               sum(1 for k in striking if kj.get(k["keyword"]) and kj[k["keyword"]]["relevance"]["band"] == "review")))
    ranked_kw = {k["keyword"] for k in dfs.get("ranked") or []}
    from jevseo.dfs import norm_kw

    seen_norm, unique, variants = {norm_kw(k) for k in ranked_kw}, [], {}
    for k in sorted(dfs.get("opportunities") or [], key=lambda k: -(k.get("volume") or 0)):
        key = norm_kw(k["keyword"])
        if key in seen_norm:
            variants[key] = variants.get(key, 0) + 1
            continue
        seen_norm.add(key)
        unique.append(dict(k))
    for k in unique:
        n = variants.get(norm_kw(k["keyword"]), 0)
        if n:
            k["variants"] = n
    opps = [k for k in unique if k["keyword"] not in ranked_kw and (k.get("volume") or 0) > 0
            and (rel(k["keyword"]) or 0) >= 0.66 and not other_brand(k["keyword"])]
    existing = [k | {"page_url": kj[k["keyword"]]["page_url"]} for k in opps if kj[k["keyword"]]["page"]["value"] != "none_fit" and kj[k["keyword"]]["page_url"]]
    new = [k for k in opps if kj[k["keyword"]]["page"]["value"] == "none_fit"]
    for rule, rows in (("dfs_existing_page", existing), ("dfs_new_page", new)):
        if rows:
            rows.sort(key=opportunity, reverse=True)
            urls = sorted({k["page_url"] for k in rows}) if rule == "dfs_existing_page" else [home]
            review = sum(1 for k in rows if kj[k["keyword"]]["relevance"]["band"] == "review" or kj[k["keyword"]]["page"]["band"] == "review")
            out.append(dfs_finding(rule, urls, len(rows), "; ".join(fmt(k) + (f" -> {urlparse(k['page_url']).path or '/'}" if k.get("page_url") else "") for k in rows[:6]), {"keywords": rows}, review))
    rd = {r["domain"]: r["referring_domains"] for r in dfs.get("referring_domains") or [] if r.get("referring_domains") is not None}
    own = rd.get(crawl["domain"])
    rivals = sorted(v for d, v in rd.items() if d != crawl["domain"])
    if own is not None and len(rivals) >= 2:
        median = rivals[len(rivals) // 2]
        if own < median / 4:
            others = ", ".join(f"{d} {v:,}" for d, v in sorted(rd.items(), key=lambda kv: -kv[1]) if d != crawl["domain"])
            out.append(dfs_finding("dfs_backlink_gap", [home], 1, f"{own:,} referring domains against a median of {median:,} across {len(rivals)} domains ranking for the same keywords ({others})", {"referring_domains": rd}, heuristic=True))
    bl = dfs.get("backlinks") or {}
    if (bl.get("broken_backlinks") or 0) > 0:
        out.append(dfs_finding("dfs_broken_backlinks", [home], bl["broken_backlinks"], f"{bl['broken_backlinks']} backlinks point at {bl.get('broken_pages') or 'some'} broken pages"))
    # Only searches that matter to this business: relevant, and not someone else's brand.
    pos = {k["keyword"]: k.get("position") for k in dfs.get("ranked") or []}
    aio = [s for s in dfs.get("serps") or [] if s["ai_overview"] and not s["ai_overview_cites_site"]
           and (rel(s["keyword"]) or 0) >= 0.5 and not other_brand(s["keyword"])]
    if aio:
        out.append(dfs_finding("dfs_aio_not_cited", [home], len(aio), "; ".join(f"{s['keyword']} (site " + (f"at position {pos[s['keyword']]}" if pos.get(s["keyword"]) else "not ranking") + f"; AI Overview cites {', '.join(s['ai_overview_domains'][:3]) or 'no domains'})" for s in aio[:5]), {"serps": aio}, heuristic=True))
    return out


def importance_of(url: str, judged: dict) -> float | None:
    ans = (judged.get("pages") or {}).get(url)
    return ans["importance"]["value"] if ans and "importance" in ans else None


def rule_component(findings: list[dict], cat: str, n_pages: int) -> float:
    total = 0.0
    for f in findings:
        if f["category"] != cat:
            continue
        total += DEDUCT[f["severity"]] * (0.5 + 0.5 * reach(f, n_pages))
    return max(0.0, 100.0 - total)


def weighted_mean(pairs: list[tuple[float, float]]) -> float | None:
    w = sum(x for _, x in pairs)
    return sum(v * x for v, x in pairs) / w if w else None


def score(crawl: dict, findings: list[dict], judged: dict, perf: dict | None, dfs: dict | None = None) -> dict:
    pages = html_pages(crawl)
    n = len(pages)
    jp = judged.get("pages") or {}
    cats = {}
    notes = {}
    for cat in CATEGORIES:
        cats[cat] = rule_component(findings, cat, n)
    # Jev-judged components, weighted by page importance
    def judged_mean(keys):
        vals = []
        for url, ans in jp.items():
            if not ans:
                continue
            present = [ans[k]["value"] for k in keys if k in ans]
            if present:
                vals.append((mean(present), 0.5 + (ans["importance"]["value"] if "importance" in ans else 0.5)))
        return weighted_mean(vals)

    content_j = judged_mean(["helpfulness", "specificity", "trust"])
    ai_j = judged_mean(["citable", "answer_first"])
    if content_j is not None:
        cats["content"] = JUDGED_SHARE * content_j * 100 + (1 - JUDGED_SHARE) * cats["content"]
        notes["content"] = "70 % de jugement Jev (utilite, specificite, confiance), 30 % de regles"
    else:
        cats["content"] = None
        notes["content"] = "Non evalue : jugements Jev indisponibles"
    if ai_j is not None:
        site = judged.get("site") or {}
        ent = [site["entity_clarity"]["value"]] if site else []
        cats["ai"] = JUDGED_SHARE * mean([ai_j] + ent) * 100 + (1 - JUDGED_SHARE) * cats["ai"]
        notes["ai"] = "70 % de jugement Jev (citabilite, reponse en tete, clarte de l'entite), 30 % de regles"
    else:
        notes["ai"] = "Regles seules : jugements Jev indisponibles"
    runs = [r for r in (perf or {}).get("runs", []) if "error" not in r and r["strategy"] == "mobile" and "performance" in r.get("scores", {})]
    if runs:
        lab = mean(r["scores"]["performance"] for r in runs)
        cats["performance"] = 0.5 * lab + 0.5 * cats["performance"]
        notes["performance"] = "50 % performance Lighthouse mobile, 50 % observations d'exploration"
    else:
        notes["performance"] = "Observations d'exploration seules : PageSpeed Insights indisponible"
    if dfs and dfs.get("available") and dfs.get("overview") is not None:
        notes["visibility"] = "Positions, mots cles et backlinks DataForSEO, filtres par la pertinence Jev"
    else:
        cats["visibility"] = None
        notes["visibility"] = "Non evalue : relancer avec --full (DataForSEO)"
    jev_hit = {f["category"] for f in findings if f.get("origin") == "jev"}
    dfs_hit = {f["category"] for f in findings if f.get("origin") == "dataforseo"}
    for cat in cats:
        if cat not in notes:
            extra = [n for n, hit in (("constats Jev", jev_hit), ("constats DataForSEO", dfs_hit)) if cat in hit]
            notes[cat] = "Regles" + (" plus " + " et ".join(extra) if extra else " seules")
    notes["ai"] += " ; heuristiques editoriales, Google indiquant qu'aucune optimisation particuliere n'est requise pour ses fonctionnalites IA"

    available = {c: v for c, v in cats.items() if v is not None}
    overall = sum(v * CATEGORY_WEIGHT[c] for c, v in available.items()) / sum(CATEGORY_WEIGHT[c] for c in available)
    caps = []
    ids = {f["id"] for f in findings}
    if "robots_blocks_site" in ids or any(f["id"] == "noindex" and f["severity"] == "critical" for f in findings):
        overall = min(overall, 20)
        caps.append("Capped at 20: the homepage or whole site is blocked from search")
    elif "no_https" in ids:
        overall = min(overall, 60)
        caps.append("Capped at 60: the site is not reliably served over HTTPS")
    # FR: la note de visibilite est une deduction a partir de 100, donc un site
    # sans aucune visibilite la conserve faute de constat a deduire. On plafonne
    # la categorie elle-meme, pas seulement le score global.
    if "dfs_invisible" in ids and cats.get("visibility") is not None:
        cats["visibility"] = min(cats["visibility"], 15)
        caps.append("Visibilite plafonnee a 15 : aucune requete metier dans le top 20")
        available = {c: v for c, v in cats.items() if v is not None}
        overall = sum(v * CATEGORY_WEIGHT[c] for c, v in available.items()) / sum(CATEGORY_WEIGHT[c] for c in available)
    overall = round(overall)
    # A score built without Jev or PageSpeed leaves whole areas unassessed; say so wherever it appears.
    partial = [reason for missing, reason in ((not any(jp.values()), "jugements Jev indisponibles, la qualite du contenu n'a donc pas ete evaluee"),
                                              (not runs, "PageSpeed Insights indisponible, la performance repose donc sur les seuls temps d'exploration")) if missing]
    return {
        "partial": partial,
        "overall": overall,
        "grade": "A" if overall >= 90 else "B" if overall >= 75 else "C" if overall >= 60 else "D" if overall >= 40 else "F",
        "categories": {c: (round(v) if v is not None else None) for c, v in cats.items()},
        "category_names": CATEGORIES,
        "weights": CATEGORY_WEIGHT,
        "notes": notes,
        "caps": caps,
        "completeness": {"categories_scored": len(available), "categories_total": len(cats), "jev": any(jp.values()), "jev_pages_not_judged": sum(1 for a in jp.values() if a is None), "pagespeed": bool(runs), "dataforseo": bool(dfs and dfs.get("available"))},
    }


def actions(findings: list[dict], judged: dict, n_pages: int) -> list[dict]:
    rows = []
    for f in findings:
        if f["severity"] == "info":
            continue
        imps = [i for i in (importance_of(u, judged) for u in f["urls"]) if i is not None]
        importance = max(imps) if imps else None
        share = reach(f, n_pages)
        impact = SEVERITY_WEIGHT[f["severity"]] * (0.6 + 0.4 * share) * (0.6 + 0.8 * importance if importance is not None else 1.0)
        rows.append({"finding": f, "impact_raw": impact, "importance": importance, "reach": share})
    top = max((r["impact_raw"] for r in rows), default=1) or 1
    out = []
    for r in rows:
        f = r["finding"]
        impact = round(100 * r["impact_raw"] / top)
        if f["severity"] == "critical" or (f["severity"] == "high" and impact >= 40):
            pri = "P1"
        elif impact >= 30 or f["severity"] == "high":
            pri = "P2"
        else:
            pri = "P3"
        out.append({
            "priority": pri,
            "impact": impact,
            "effort": f["effort"],
            "quick_win": impact >= 35 and f["effort"] <= 1,
            "importance": None if r["importance"] is None else round(r["importance"], 2),
            **{k: f[k] for k in ("id", "origin", "category", "severity", "title", "fix", "source", "count", "evidence", "heuristic")},
            "needs_review": f.get("needs_review", 0),
            "urls": f["urls"],
        })
    out.sort(key=lambda a: (a["priority"], -a["impact"], a["effort"]))
    for i, a in enumerate(out, 1):
        a["action_id"] = f"JEV-{i:03d}"
        a["status"] = "to_do"
    return out
