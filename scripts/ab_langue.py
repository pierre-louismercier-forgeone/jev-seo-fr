#!/usr/bin/env python3
"""A/B sur la langue des questions envoyees a Jev.

La doc TypeSafe donne l'anglais comme langue la plus forte du modele, alors
que le contenu juge est francais dans les deux cas. Traduire les questions
deplace donc les INSTRUCTIONS vers la langue faible sans rien changer a la
langue du contenu : cela peut degrader sans rien gagner. Aucune mesure
publique n'existe sur le francais, d'ou ce script.

Protocole : meme corpus, memes cles de reponse, meme modele. La seule
variable est la langue de l'enonce. On mesure deux choses :

  - la DECISIVITE : part des reponses qui tombent dans une bande d'action
    plutot qu'en « a verifier ». C'est la mesure que l'upstream utilise dans
    ses propres tests de formulation, et elle se suffit a elle-meme : une
    question qui laisse le modele indecis est une mauvaise question.

  - l'ACCORD entre les deux variantes, du cote du seuil qui declenche un
    constat. Un desaccord dit qu'au moins une des deux se trompe, sans dire
    laquelle.

Ce que ce script NE mesure PAS : l'exactitude. Il n'existe pas de corpus
francais etiquete a la main. Un accord eleve signifie que les deux variantes
lisent la meme chose, pas qu'elles lisent juste.

Usage :
    python scripts/ab_langue.py <dossier-audit> [--pages 30]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jevseo import fr, jev  # noqa: E402

# Seuil au-dela duquel une reponse devient un constat, par question.
# Repris de score.py : sous 0.45 pour les Score, sous 0.5 pour les Noul.
SEUIL = defaultdict(lambda: 0.45, {
    "answer_first": 0.5, "clear_next_step": 0.5, "h1_fit": 0.5, "contact_local": 0.5,
})
DECISIVES = {"act", "yes", "no"}


def cote(qid: str, reponse: dict) -> str | bool:
    """Le cote du seuil, c'est-a-dire ce qui declenche ou non un constat."""
    if reponse["type"] == "choice":
        return reponse["value"]
    return reponse["value"] >= SEUIL[qid]


def juger(client: jev.Jev, etat: dict, questions: dict) -> dict | None:
    return client.ask(etat, questions)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dossier")
    ap.add_argument("--pages", type=int, default=30)
    ap.add_argument("--budget", type=float, default=0.10)
    args = ap.parse_args()

    d = json.loads((Path(args.dossier) / "audit.json").read_text())
    pages = [p for p in d["pages"] if p.get("kind") == "page" and p.get("status") == 200 and p.get("text_excerpt")]
    pages = pages[: args.pages]
    site_ctx = (d["jev"].get("state") or {}).get("site") or {"domain": d["site"]["domain"]}

    client = jev.Jev(budget_usd=args.budget, log=print)
    if not client.available:
        sys.exit("aucune cle Jev")
    print(f"fournisseur {client.provider}, modele {jev.MODEL}, {len(pages)} pages\n")

    resultats = []

    def une_page(p):
        etat = jev.page_state(p, site_ctx)
        qs_en = jev.page_questions(p)
        qs_fr = fr.franciser_questions(qs_en)
        return p["url"], juger(client, etat, qs_en), juger(client, etat, qs_fr)

    with ThreadPoolExecutor(max_workers=4) as ex:
        for url, en, fr_ in ex.map(une_page, pages):
            if en and fr_:
                resultats.append((url, en, fr_))
            else:
                print(f"  page ignoree (requete en echec) : {url}")

    if not resultats:
        sys.exit("aucun couple de reponses exploitable")

    dec = {"en": Counter(), "fr": Counter()}
    total = Counter()
    accord, desaccord = Counter(), defaultdict(list)

    for url, en, fr_ in resultats:
        for qid in en:
            if qid not in fr_:
                continue
            total[qid] += 1
            dec["en"][qid] += en[qid]["band"] in DECISIVES
            dec["fr"][qid] += fr_[qid]["band"] in DECISIVES
            if cote(qid, en[qid]) == cote(qid, fr_[qid]):
                accord[qid] += 1
            else:
                desaccord[qid].append((url.rsplit("/", 1)[-1][:34], en[qid]["value"], fr_[qid]["value"]))

    n = len(resultats)
    print(f"\n{n} pages jugees deux fois, {sum(total.values())} couples de reponses\n")
    print(f"{'question':20} {'n':>4}  {'décisif EN':>11} {'décisif FR':>11}  {'accord':>8}")
    print("-" * 62)
    for qid in sorted(total, key=lambda q: -total[q]):
        t = total[qid]
        print(f"{qid:20} {t:4}  {dec['en'][qid]/t:>10.0%} {dec['fr'][qid]/t:>11.0%}  {accord[qid]/t:>7.0%}")

    te, tf, ta = sum(dec["en"].values()), sum(dec["fr"].values()), sum(accord.values())
    tt = sum(total.values())
    print("-" * 62)
    print(f"{'TOTAL':20} {tt:4}  {te/tt:>10.0%} {tf/tt:>11.0%}  {ta/tt:>7.0%}")

    if desaccord:
        print("\nDesaccords, par question (fichier, valeur EN, valeur FR) :")
        for qid, cas in sorted(desaccord.items(), key=lambda kv: -len(kv[1])):
            print(f"  {qid} ({len(cas)}) :")
            for f, ve, vf in cas[:4]:
                ve = f"{ve:.2f}" if isinstance(ve, float) else ve
                vf = f"{vf:.2f}" if isinstance(vf, float) else vf
                print(f"      {f:36} EN {ve:>8}   FR {vf:>8}")

    print(f"\ncout total : ${client.cost():.4f} sur {client.ledger['requests']} requetes, "
          f"{client.ledger['failed']} en echec")
    print("\nRappel : ceci mesure la decisivite et l'accord, pas l'exactitude. "
          "Il n'existe pas de corpus francais etiquete a la main.")


if __name__ == "__main__":
    main()
