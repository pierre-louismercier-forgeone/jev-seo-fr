# Fork ForgeOne de jev-seo

Fork de [AgriciDaniel/jev-seo](https://github.com/AgriciDaniel/jev-seo) (MIT),
francise pour le marche francophone et pour un portefeuille majoritairement
local (artisans, professions reglementees, services de proximite).

Tout le francais vit dans **`jevseo/fr.py`**. Les autres fichiers ne portent que
des appels vers ce module, signales par un commentaire `# FR:`. Objectif :
garder `git pull upstream main` possible.

## Ce qui a change, et pourquoi

### 1. Deux bugs qui rendaient l'outil muet en francais

| Upstream | Effet sur un site francais | Correctif |
|---|---|---|
| `GENERIC_ANCHORS` en anglais seul | La regle des ancres generiques ne trouvait **jamais rien**. « En savoir plus », « Lire la suite », « Decouvrir » passaient toutes. | `fr.ANCRES_GENERIQUES`, fusionne avec l'anglais |
| Mots vides anglais dans `overlap_candidates()` | « le / la / les / de / des / du / et / pour » non retires : la similarite de Jaccard etait gonflee par du bruit et la preselection des paires de cannibalisation remontait de fausses paires, **silencieusement**. | `fr.MOTS_VIDES` |

Mesure sur un site client reel (cabinet de recouvrement, 25 pages) :
l'upstream detecte 0 ancre generique, le fork en detecte une sur un lien
(« En savoir plus »). Sur la preselection des paires, 9 paires sur 240
changent.

### 2. Le vrai probleme : l'architecture ville x service

C'est le pattern local francais le plus courant, et l'upstream le traite mal.

Sur le meme site, 24 pages sur 25 sont « Societe de recouvrement [ville] ».
L'upstream preselectionne **232 paires candidates** a la cannibalisation et en
envoie **40** (son plafond) a Jev. Les titres etant quasi identiques, Jev
repondrait « oui, elles se cannibalisent » sur chacune. L'outil declarerait un
desastre de cannibalisation sur une architecture parfaitement voulue.

Le fork ajoute `fr.paire_geographique()`, qui deduit le gabarit **du corpus**,
sans liste de villes codee en dur : deux titres forment un gabarit geographique
s'ils partagent leur tete et ne different que par des noms propres ou des
reperes chiffres (arrondissement, departement). Ces paires sont retirees de la
preselection de cannibalisation.

Resultat sur le meme site : **de 40 paires (plafond sature) a 23**, et les 23
restantes sont la vraie question, la page pilier contre chaque page ville.

Leur risque reel est traite ailleurs, par une regle nouvelle :

- **`doorway_pages`** (severite `high`) : pages ville du meme gabarit dont le
  texte se recoupe a 60 % ou plus, mesure par Jaccard sur 4-grammes. C'est le
  risque de page satellite que Google sanctionne.

Sur le site teste la regle **ne se declenche pas** : similarite mediane 11 %,
maximum 30 %. Les pages ville y sont reellement differenciees. La regle est
couverte par un test unitaire dans les deux sens.

### 3. Taxonomies adaptees au marche

- **`BUSINESS_MODELS`** : les 9 categories upstream, pensees pour un marche
  SaaS americain, ecrasaient serrurier, chirurgien, architecte d'interieur,
  VTC et salle de sport dans un seul `local_service`. Remplacees par 13
  categories francaises separant artisan du batiment, profession reglementee
  (ordre et deontologie, donc contraintes de publicite), service pro local,
  commerce recevant du public, industrie et BTP.
- **`PAGE_TYPES`** : ajout de `realisations_ou_chantiers`, `zone_intervention`,
  `mentions_legales`, `recrutement`.
- **Questions locales** : une page qui vise un lieu (`fr.page_locale()`) porte
  deux questions de plus, `preuve_locale` (du nom de ville pose sur du texte
  generique jusqu'a la preuve de terrain nominative) et `coordonnees_visibles`.
  Sur le site teste, 22 pages sur 25 sont detectees comme locales, et les 3
  exclues sont bien le pilier, le contact et la page de procedure.

### 4. Seuils ajustes au francais

Le francais compte 15 a 20 % de mots en plus que l'anglais a contenu egal.

- Contenu mince : `150` -> `180` mots.
- Longueur de title : `15-65` -> `15-75` caracteres. Sans cet elargissement un
  site francais correct recolte des faux positifs en serie.
- Veto de suppression a 600 mots : **inchange**, il est deja conservateur en
  francais (une page FR atteint 600 mots plus vite, donc protege plus tot).

### 5. Libelles en francais

Les 52 titres et correctifs de regles, plus les 9 categories, sont traduits
(`fr.REGLES`, `fr.CATEGORIES`), appliques a l'import. Les identifiants, les
severites et les seuils restent ceux de l'upstream.

### 6. Robustesse

- `doctor` ne plante plus quand WeasyPrint est installe mais inutilisable
  (l'absence de Pango/GLib leve `OSError`, pas `ImportError`).
- Le rendu PDF degrade vers `report.html` au lieu de faire tomber tout le
  rendu. Le HTML est de toute facon le livrable ForgeOne.

## La langue des questions reste un point ouvert

La doc TypeSafe dit que **l'anglais est la langue la plus forte de Jev**, et le
contenu juge est francais dans les deux cas. Traduire les questions deplace
donc les *instructions* vers la langue faible du modele sans rien changer a la
langue du contenu : cela peut degrader sans rien gagner. Aucune mesure publique
n'existe sur le francais.

Les questions restent donc **en anglais par defaut**, avec un commutateur pour
que l'A/B ne coute qu'une variable d'environnement :

```sh
JEVSEO_QUESTIONS_LANG=fr
```

Protocole de test, des qu'une cle TypeSafe est disponible : prendre 30 pages
d'un site client deja audite, les etiqueter a la main, faire tourner les deux
variantes, comparer les taux d'accord. Cout estime : quelques centimes.

## Ce qui n'est pas encore fait

- Le squelette du rapport (titres de sections, phrases generees, chaines de
  preuve dans `run_checks`) est encore en anglais. Les regles et les categories
  sont traduites, pas le texte autour.
- Les noms d'onglets et d'en-tetes du classeur XLSX.
- Le gabarit visuel ForgeOne (near-white, #075CD8, Figtree) a la place du
  gabarit upstream.

## Etat des tests

`python -m unittest discover -s tests` : **43 tests, tous verts**, dont 5
nouveaux couvrant les correctifs francais. Les tests de rendu acceptent
desormais `report.html` quand WeasyPrint est indisponible, et exigent toujours
qu'un document soit produit.

## Environnement

Python 3.10 minimum ; la machine porte un Python 3.9 systeme, donc
l'environnement est cree avec `uv` :

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

WeasyPrint ne peut pas se charger sans Pango/GLib (Homebrew absent) : le PDF
est indisponible, le HTML, le Markdown et l'Excel fonctionnent.
