"""Markdown report: readable anywhere, with chart images and Mermaid pies for GitHub and Obsidian."""
from __future__ import annotations

from collections import Counter
from pathlib import Path


def cell(v) -> str:
    return str("" if v is None else v).replace("|", "\\|").replace("\n", " ")


def label(v) -> str:
    return cell((v or "").replace("_", " "))


WIDTH = {"gauge": 220, "severity": 320, "page_types": 360, "intents": 360, "positions": 380, "referring_domains": 380}


def img(vm: dict, name: str, alt: str) -> str:
    """HTML image tags so GitHub and Obsidian show charts at a readable size."""
    p = vm["charts"].png.get(name)
    return f'<img src="charts/{p.name}" alt="{alt}" width="{WIDTH.get(name, 640)}">\n' if p else ""


def pie(title: str, counts: dict) -> str:
    if not counts:
        return ""
    body = "\n".join(f'    "{k.replace("_", " ")}" : {v}' for k, v in counts.items() if v)
    return f"```mermaid\npie showData title {title}\n{body}\n```\n"


def write_md(vm: dict, path: Path) -> Path:
    d, s, n = vm["d"], vm["scores"], vm["narrative"]
    L = []
    add = L.append
    add(f"# Audit SEO : {vm['domain']}\n")
    add(f"Audit du {d['run']['finished_at']} · {vm['n_fetched']} URL explorees · {vm['n_pages']} pages HTML · {vm['n_judgments']} jugements Jev · cout Jev ${(vm['ledger'].get('cost_usd') or 0):.4f}\n")
    add(f"**Score global : {s['overall']}/100 (note {s['grade']})**" + (f". {'; '.join(s['caps'])}" if s["caps"] else "") + "\n")
    if s.get("partial"):
        add(f"> **Audit partiel :** {'; '.join(s['partial'])}. Le score global ne couvre que les domaines evalues.\n")
    add(img(vm, "gauge", "Score global"))
    add("| Domaine | Score | Poids | Mode de calcul |\n|---|---:|---:|---|")
    for c, name in s["category_names"].items():
        v = s["categories"][c]
        add(f"| {name} | {v if v is not None else 'n/a'} | {s['weights'][c]} | {s['notes'][c]} |")
    add("")
    add(img(vm, "categories", "Score par domaine"))

    toc = ["Synthese", "Comment cet audit a ete fait", "Actions prioritaires"] + (["Visibilite sur les moteurs (DataForSEO)"] if vm.get("dfs") else []) + ["Ce que l'exploration a trouve"] + (["Comment Jev lit le site"] if vm["jev_available"] else []) + ["Constats par domaine", "Acces des robots", "Inventaire des pages", "Methode et limites"]
    anchor = lambda h: "#" + "".join(c for c in h.lower().replace(" ", "-") if c.isalnum() or c == "-")  # noqa: E731
    add("**Sommaire :** " + " · ".join(f"[{h}]({anchor(h)})" for h in toc) + "\n")
    add("## Synthese\n")
    for para in n["executive_summary"]:
        add(para + "\n")
    add("**Ce qui fonctionne**\n")
    add("\n".join(f"- {x}" for x in n["strengths"]) + "\n")
    add("**Ce qui freine le site**\n")
    add("\n".join(f"- {x}" for x in n["risks"]) + "\n")
    add("### Plan d'action\n")
    for block in n["plan"]:
        add(f"**{block['horizon']}**\n")
        add("\n".join(f"- {x}" for x in block["items"]) + "\n")
    if n.get("closing"):
        add(n["closing"] + "\n")
    add(f"_Redige par : {n['author']}._\n")

    add("## Comment cet audit a ete fait\n")
    add("Les sources trouvent, le code tranche, Jev juge, Claude redige. Le code explore, compte et note. Jev, le modele System One de TypeSafe, repond a des questions fermees et typees sur le sens, avec des probabilites. Une donnee absente est affichee comme absente, jamais devinee.\n")
    add("```mermaid\nflowchart LR\n  A[Exploration<br/>" + f"{vm['n_fetched']} URL" + "] --> B[Regles<br/>" + f"{sum(1 for f in d['findings'] if f['origin'] == 'rule')} constats" + "] --> C[Jev juge<br/>" + f"{vm['n_judgments']} jugements" + "] --> D[PageSpeed<br/>" + f"{len(vm['perf_runs'])} mesures" + "] --> E[Notation et redaction<br/>" + f"{len(vm['actions'])} actions" + "]\n  style C fill:#d45bb6,color:#fff\n```\n")

    add("## Actions prioritaires\n")
    add(img(vm, "impact_effort", "Impact par rapport a l'effort"))
    add("| ID | Action | Priorite | Impact | Effort | Pages | Par | A verifier |\n|---|---|---|---:|---|---:|---|---:|")
    for a in vm["actions"]:
        add(f"| {a['action_id']} | {cell(a['title'])}{' (gain rapide)' if a['quick_win'] else ''} | {a['priority']} {a['priority_text']} | {a['impact']} | {a['effort_text']} | {a['count']} | {a['by']} | {a['needs_review'] or ''} |")
    add("")
    add(pie("Actions par gravite", {k: vm["sev_counts"].get(k, 0) for k in ("critical", "high", "medium", "low")}))
    add(img(vm, "severity_by_category", "Actions par domaine et gravite"))

    x = vm.get("dfs")
    if x:
        ov, bl = x["overview"], x["backlinks"]
        add("## Visibilite sur les moteurs (DataForSEO)\n")
        add(f"Zone {x['location_code']}, langue {x['language_code']}. Le trafic (ETV) est une estimation DataForSEO, pas une mesure de visites reelles.\n")
        add(f"| Mots cles positionnes | Visites/mois estimees | Domaines referents | Backlinks | Mentions dans les reponses IA |\n|---:|---:|---:|---:|---:|\n| {ov.get('count')} | {round(ov['etv']) if ov.get('etv') is not None else 'n/a'} | {bl.get('referring_domains')} | {bl.get('backlinks')} | {(x['mentions'] or {}).get('total')} |\n")
        add(img(vm, "positions", "Mots cles positionnes par rang"))
        add(img(vm, "referring_domains", "Domaines referents compares"))
        add("| Mot cle | Position | Recherches/mois | Page positionnee | Pertinence Jev |\n|---|---:|---:|---|---:|")
        for k in x["ranked"][:20]:
            add(f"| {cell(k['keyword'])} | {k.get('position')} | {k.get('volume')} | {k['page']} | {'' if k['relevance'] is None else format(k['relevance'], '.2f')} |")
        add("\n### Mots cles a aller chercher\n")
        add(img(vm, "opportunities", "Opportunites de mots cles"))
        add("| Mot cle | Recherches/mois | Difficulte | Intention | Pertinence Jev | Page qui doit le porter |\n|---|---:|---:|---|---:|---|")
        for k in x["opportunities"]:
            rel = "" if k.get("relevance") is None else f"{k['relevance']:.2f}"
            add(f"| {cell(k['keyword'])} | {k.get('volume')} | {k.get('difficulty') if k.get('difficulty') is not None else 'n/a'} | {cell(k.get('intent'))} | {rel} | {k['target']} |")
        add("")
        if x["serps"]:
            add("| Mot cle | Position du site | Apercu IA | Top 3 |\n|---|---:|---|---|")
            for sp in x["serps"]:
                aio = ("oui, cite le site" if sp["ai_overview_cites_site"] else "oui, site non cite") if sp["ai_overview"] else "aucun"
                add(f"| {cell(sp['keyword'])} | {sp['own_position'] or 'hors top 10'} | {aio} | {', '.join(t['domain'] for t in sp['top'][:3])} |")
            add("")

    add("## Ce que l'exploration a trouve\n")
    add(img(vm, "funnel", "Des URL decouvertes aux jugements Jev"))
    add(img(vm, "site_map", "Structure du site par profondeur de clic"))

    if vm["jev_available"]:
        add("## Comment Jev lit le site\n")
        for c in vm["site_cards"]:
            conf = f", confiance {c['confidence']:.2f}" if "confidence" in c else ""
            flag = "" if c["band"] in ("act", "yes", "no") else " _(a verifier)_"
            add(f"- **{c['question']}** {c['answer']}{conf}{flag}")
        add("")
        jp = d["jev"]["pages"]
        add(pie("Types de page (Jev)", dict(Counter(a["page_type"]["value"] for a in jp.values() if a).most_common())))
        add(pie("Intention de recherche (Jev)", dict(Counter(a["intent"]["value"] for a in jp.values() if a).most_common())))
        add(img(vm, "jev_heatmap", "Carte de qualite des pages (Jev)"))
        add(img(vm, "jev_confidence", "Niveau de certitude de Jev"))
        add("### Ou investir\n")
        add(img(vm, "invest", "Importance par rapport a la qualite jugee"))
        if vm["invest_pages"]:
            add("| Importante mais faible | Importance | Qualite | Jev suggere |\n|---|---:|---:|---|")
            for p in vm["invest_pages"]:
                add(f"| {p['short']} | {p['importance']:.2f} | {p['quality']:.2f} | {cell((p['action'] or '').replace('_', ' '))} |")
            add("")
        if vm["jev_pairs"]:
            add("**Pages susceptibles de se disputer les memes recherches**\n")
            add("| Page A | Page B | Recoupement des titres | P(concurrence) |\n|---|---|---:|---:|")
            for p in vm["jev_pairs"][:20]:
                add(f"| {p['a']} | {p['b']} | {p['title_overlap']} | {p['judgment']['value']:.2f} |")
            add("")

    add("## Constats par domaine\n")
    for c, name in s["category_names"].items():
        acts = vm["findings_by_cat"][c]
        if not acts:
            continue
        add(f"### {name} ({s['categories'][c] if s['categories'][c] is not None else 'n/a'})\n")
        if c == "performance":
            add(img(vm, "lighthouse", "Scores Lighthouse"))
            add(img(vm, "cwv", "Core Web Vitals, donnees terrain"))
        for a in acts:
            tags = [a["priority"], a["severity"], a["by"]]
            if a["needs_review"]:
                tags.append(f"{a['needs_review']} a verifier")
            if a["heuristic"]:
                tags.append("heuristique")
            add(f"**{a['action_id']} · {a['title']}** `{'` `'.join(tags)}`\n")
            add(f"- Preuve : {a['count']} concernees · {a['evidence']}")
            add(f"- Correctif : {a['fix']} ([source]({a['source']}))")
            add("- URL : " + ", ".join(a["urls"][:8]) + (f" et {a['count'] - 8} autres" if a["count"] > 8 else ""))
            add("")

    add("## Acces des robots\n")
    add("| User agent | Acces |\n|---|---|")
    for b, ok in {**vm["search_bots"], **vm["ai_bots"]}.items():
        add(f"| {b} | {'autorise' if ok else 'bloque'} |")
    add("")

    add("## Inventaire des pages\n")
    add("| Page | Profondeur | Mots | Liens entrants | Type (Jev) | Intention (Jev) | Importance | Action (Jev) |\n|---|---:|---:|---:|---|---|---:|---|")
    for p in vm["pages"]:
        imp = f"{p['importance']:.2f}" if p["importance"] is not None else ""
        add(f"| {p['url']} | {p['depth'] if p['depth'] != 99 else ''} | {p['words']} | {p['inlinks']} | {label(p['page_type'])} | {label(p['intent'])} | {imp} | {label(p['action'])} |")
    add("")

    add("## Methode et limites\n")
    add("- Score par domaine : 100 moins, par constat, un poids de gravite (critique 25, eleve 12, moyen 6, faible 2) × (0,5 + 0,5 × part des pages concernees). Le contenu et la visibilite IA melangent 70 % de jugement Jev et 30 % de regles. La performance melange 50 % Lighthouse mobile et 50 % observations d'exploration.")
    add("- Score global : moyenne ponderee des domaines evalues ; un domaine non evalue est exclu du calcul, jamais compte zero.")
    add("- Impact : poids de gravite × (0,6 + 0,4 × portee) × (0,6 + 0,8 × importance Jev la plus elevee des pages concernees), ramene sur 100.")
    add("- Une reponse Jev est decisive a partir de 0,80 de confiance (Choice, Score) ou d'un P(oui) superieur a 0,80 ou inferieur a 0,20 (Noul). Les autres sont marquees a verifier.")
    lg = vm["ledger"]
    add(f"- Jev : modele {lg.get('model_returned') or 'n/a'}, {lg.get('requests', 0)} requetes, {lg.get('input_tokens', 0)} jetons d'entree, {lg.get('failed', 0)} en echec, cout ${(lg.get('cost_usd') or 0):.4f}.")
    if vm.get("dfs"):
        x = vm["dfs"]
        add(f"- DataForSEO: {x['ledger']['requests']} requests, ${x['ledger']['cost_usd']:.4f}" + (f"; data reused from the collection at {x['reused_from']}" if x.get("reused_from") else "") + ". Rankings, volumes, difficulty and traffic (ETV) are DataForSEO estimates. No Search Console or analytics data was used.")
    else:
        add("- No Search Console, analytics, backlink or keyword data was used (run with --full for DataForSEO).")
    add("- Scores rank work; they do not predict rankings or traffic.")
    add(f"\n_Generated by jev-seo {d['tool']['version']}._\n")
    path.write_text("\n".join(L))
    return path
