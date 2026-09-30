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

### 7. Rapport entierement francais

Traduits : le squelette Markdown (`report/md.py`), les libelles partages
(`report/__init__.py`), les notes de calcul et les messages d'audit partiel
(`score.py`), les 16 regles Jev et les 6 regles DataForSEO, les en-tetes et
les noms d'onglets du classeur (`report/xlsx.py`), le gabarit HTML complet
(`templates/report.html.j2`) et les etiquettes des graphiques
(`report/charts.py`). Les dates passent par une table de mois plutot que par
la locale systeme, qui n'est pas garantie sur la machine de generation.

Verification : un balayage du HTML genere ne trouve plus aucun marqueur
anglais hors noms propres et termes techniques (Jev, DataForSEO, PageSpeed,
Lighthouse, Core Web Vitals, robots.txt).

### 8. Gabarit visuel ForgeOne

- Fond near-white `#FBFCFE`, filets 1px, un seul bleu `#075CD8` et son halo.
- **Figtree** (variable, OFL, embarquee) remplace Inter comme famille de texte
  et de titre ; **JetBrains Mono** porte les chiffres et les etiquettes
  techniques, en chiffres tabulaires.
- Sections numerotees (`01`, `02`...) en mono bleu.
- Le bleu est reserve a la marque et aux reperes : les gravites ont leur
  propre gamme, pour qu'un etat ne soit jamais confondu avec un accent.
- Les graphiques matplotlib sont recolores (palette categorielle, rampe de
  chaleur, couleurs de gravite) et passent eux aussi en Figtree, sinon le CSS
  seul laissait des graphiques magenta dans un rapport bleu.
- Une feuille de style ecran complete la feuille d'impression A4 : le HTML est
  le livrable tant que WeasyPrint n'est pas disponible. Le positionnement
  absolu de la couverture, concu pour le A4, est repasse en flux a l'ecran.

### 9. Deux fournisseurs pour le meme contrat

L'acces anticipe TypeSafe a ete remis en pause le 22 septembre 2026, donc une
cle directe n'est pas garantie. **OpenRouter expose le meme contrat System One**
a `POST https://openrouter.ai/api/v1/systemone`, en inscription libre, au meme
prix (0,042 $ par million de jetons d'entree, sortie gratuite), avec TypeSafe
comme unique fournisseur derriere (donc aucune variance de routage).

Attention a ne pas confondre les deux surfaces OpenRouter :

| Surface | Schema | Verdict |
|---|---|---|
| `/api/v1/systemone` | identique a TypeSafe, presente par leur doc comme un simple changement de base URL | **c'est celle qu'on utilise** |
| `/api/alpha/decisions` | schema propre, endpoint alpha | non, surface instable pour un gain nul |

Les deux repondent 401 a une cle invalide, donc les URL sont confirmees.

Selection du fournisseur, par ordre de priorite :

1. `JEVSEO_PROVIDER=typesafe|openrouter` s'il est defini (une valeur inconnue leve) ;
2. sinon, la premiere cle trouvee, TypeSafe d'abord ;
3. sinon, TypeSafe par defaut, et les jugements sont ignores.

Le modele par defaut differe volontairement : `jev-latest` en direct, mais
**`typesafe/jev-1.13`, version figee, via OpenRouter**. Un audit client doit
rester reproductible : si le modele bouge sous nous, deux audits du meme site
divergent sans qu'une seule ligne du site ait change. `JEVSEO_MODEL` surcharge.

OpenRouter renvoie `usage.cost`, le cout reellement facture. Quand il est
present, il fait foi dans le registre ; sinon on garde le calcul par jetons.

### 10. Premier audit reel avec jugements Jev (27 septembre 2026)

Passe sur clw.fr via OpenRouter, 30 pages, **34 requetes, 162 363 jetons
d'entree, 0,0068 $, 0 echec**. Le contrat OpenRouter se comporte exactement
comme la doc TypeSafe : racine `answers` / `model` / `provider` / `usage`, et
`usage.cost` donne le cout reellement facture.

**Jev juge correctement du contenu francais avec des instructions anglaises.**
Premier test isole sur une page serrurier fictive : type de page `service`
a 1,00 de confiance, lieu cible a 0,98, preuve locale a 1,87/3 avec 0,87 de
probabilite sur « des details locaux concrets ». Lecture juste et nuancee.

Trois defauts trouves et corriges par ce run :

**a. 6 requetes sur 28 perdues en silence.** Toutes en HTTP 520, une erreur
transitoire du edge Cloudflare devant OpenRouter. L'upstream, ecrit pour
TypeSafe en direct, ne reessayait que sur 429/529/502/503. Consequence : 24
pages jugees sur 30, et un score **meilleur** (90 au lieu de 89) parce que les
pages perdues ne portaient aucun constat. Une perte de donnees qui flatte le
resultat est le pire type de bug. `RETRY_STATUS` couvre desormais les 52x.

**b. `coordonnees_visibles` avait raison pour une mauvaise raison.** La
question repondait « pas de contact » sur des pages qui en portaient un : les
coordonnees vivent dans le pied de page, donc **au-dela du plafond de 6 000
caracteres** envoye a Jev. Meme classe d'erreur que le bug du fil d'Ariane
documente dans l'evaluation upstream : regarder ce qu'on donne a lire avant
d'accuser la question.

Corrige selon la regle du repo, « le code ne demande jamais ce qu'il peut
voir » : `fr.signaux_contact()` extrait telephones, emails et adresses de la
page **entiere** par correspondance de chaine, les passe dans l'etat, et la
question devient un vrai jugement, `contact_local` : ces coordonnees
appartiennent-elles au lieu que la page vise, ou a un siege ailleurs ?

Effet mesure : de 0,14-0,17 en zone grise a **0,05-0,07 en bande decisive
« non »**. Meme conclusion, mais fondee. Sur clw.fr, les 22 pages ville ne
portent que le numero du siege de Villeurbanne.

**c. Les graphiques avaient perdu le gras.** matplotlib ne sait pas exploiter
l'axe de graisse d'une police variable et retombait sur 300 partout. Des
instances statiques Figtree-Regular et Figtree-Bold sont generees depuis la
variable avec `fontTools` ; le HTML garde la variable, que les navigateurs
gerent.

**Validation du filtre geographique, en conditions reelles :** 26 paires
soumises a Jev, **zero jugee concurrente**, aucun constat de cannibalisation.
C'est le comportement attendu sur une architecture ville x service correcte.
Sans le filtre, l'upstream aurait envoye 40 paires ville contre ville a un
modele qui, les titres etant quasi identiques, aurait repondu oui.

**Constats produits sur clw.fr** : `jev_preuve_locale` (severite elevee, le
seul constat eleve de l'audit), `jev_coordonnees_locales`, plus
`jev_local_schema`, `jev_specificity`, `jev_trust`, `jev_meta_fit` et
`jev_answer_first`. Score 89 (B, partiel), 15 actions.

## La langue des questions : tranche par la mesure

**Verdict : l'anglais, et l'ecart n'est pas marginal.**

A/B du 27 septembre 2026 sur clw.fr. Meme corpus, memes cles de reponse, meme
modele ; la seule variable est la langue de l'enonce. 30 pages jugees deux
fois, 434 couples de reponses, 60 requetes, 0,0126 $.

| Mesure | Anglais | Francais |
|---|---|---|
| Reponses decisives | **76 %** | 65 % |
| Accord entre les deux variantes | 92 % | |

**Le francais n'est plus decisif sur aucune question.** L'ecart se concentre
sur trois d'entre elles :

| Question | Decisif EN | Decisif FR | Accord |
|---|---|---|---|
| `page_type` | **93 %** | 27 % | 23 % |
| `specificity` | 40 % | 10 % | 90 % |
| `clear_next_step` | 77 % | 57 % | 100 % |
| `intent` | 80 % | 60 % | 90 % |

`page_type` s'effondre : en anglais le modele tranche `zone_intervention` sur
les pages ville, en francais il hesite et bascule sur `product_or_service`.
Les deux etiquettes se defendent (une page ville presente bien un service
dans un lieu), mais 27 % de decisivite dit que la version francaise ne
discrimine pas. La mesure ne dit pas laquelle a raison ; elle dit laquelle
tranche.

Ce protocole NE mesure PAS l'exactitude : il n'existe pas de corpus francais
etiquete a la main. Un accord de 92 % signifie que les deux variantes lisent
la meme chose, pas qu'elles lisent juste.

Le commutateur reste en place et fonctionne de bout en bout, pour rejouer la
mesure sur un autre corpus :

```sh
JEVSEO_QUESTIONS_LANG=fr        # defaut : en
python scripts/ab_langue.py <dossier-audit> --pages 30
```

La traduction complete vit dans `fr.QUESTIONS_FR`. Les **cles** des criteres
ne sont jamais traduites : elles sont lues par `score.py`, les rapports et le
classeur. Seuls les enonces changent, ce qui est exactement ce qui rend l'A/B
propre. Un test verrouille cette invariance.

### Un constat de bord

`answer_first` est indecis dans les deux langues (7 % et 3 %). Verification
faite, `opening()` extrait correctement le texte apres le H1 : ce sont les
ouvertures de clw.fr qui sont genuinement ambigues, un slogan suivi de
libelles de menu (« Notre objectif : la defense de vos interets economiques.
NOS SOLUTIONS Voir nos solutions »). La question n'est pas cassee, le contenu
l'est. Le constat `jev_answer_first` est d'ailleurs emis, avec raison.

Piste a creuser : les libelles de navigation qui bavent dans `text_excerpt`
degradent le signal sur plusieurs questions.

### 11. Explorateur interactif

`explorer.html`, un fichier autonome sans dependance externe, genere depuis
`audit.json` : aucun appel supplementaire, aucun cout. Les 12 jugements par
page, leurs distributions completes, leur confiance et leur bande etaient deja
stockes ; seul le rapport A4 les resumait.

Trois vues : pages filtrables et triables, actions par impact, notes avec le
registre Jev. Cliquer une page ouvre son dossier : chaque question, sa valeur,
sa bande, sa confiance, la distribution complete avec le libelle de chaque
niveau, les actions qui la touchent, son ouverture apres le H1, et le texte
que Jev a reellement lu.

Les colonnes portent un libelle court (`fr.LIBELLES_COURTS`), le detail garde
la phrase de critere entiere : un critere est ecrit pour que Jev tranche, pas
pour etre lu dans un tableau.

### 12. Anatomie de page (`--anatomy`)

Etiquette le role de chaque passage d'une page. La ou `jev_answer_first` dit
seulement « la page enterre l'essentiel », l'anatomie dit **a quel endroit la
reponse arrive** et ce qu'il y a a la place avant elle. C'est la difference
entre un constat et un brief de reecriture.

Desactivee par defaut : elle ajoute jusqu'a 24 questions par page, donc elle
change le cout d'un run. Mesure sur publi3.com, 43 pages : **0,0108 $ sans,
0,0172 $ avec**.

Trois constats en sortent : `jev_reponse_enterree` (la reponse arrive apres
35 % de la page), `jev_sans_reponse` (aucun passage ne repond),
`jev_page_creuse` (moins de 30 % de passages porteurs).

**La v1 ne marchait pas, et la mesure l'a dit.** Neuf roles, 37 % de
decisivite seulement, `reponse` et `offre` a **0 %** de decisions fermes :
plusieurs options se distinguaient par degre et non par nature, exactement le
travers que l'evaluation upstream documente. La v2 garde quatre roles sur un
axe disjoint (informe, prouve, decore, chrome) : 40 % de decisivite, confiance
mediane de 0,53 a 0,67.

**Ce qui restait n'etait pas la question, c'etait le texte.** Sur clw.fr, dont
les pages sont de la prose, le meme jeu de questions donne :

| | publi3.com (fil d'actualite) | clw.fr (pages de service) |
|---|---:|---:|
| Decisivite | 40 % | **54 %** |
| Confiance mediane | 0,67 | **0,84** |
| Passages `navigation` | 51 % | **10 %** |
| `reponse` decisif | 17 % | **65 %** |

L'instrument fonctionne. Le texte extrait de publi3.com est a moitie du chrome
(libelles de menu, titres d'articles mis bout a bout) et n'est pas segmentable
en passages a role unique. Une indecision de 40 % y est la bonne reponse.

Limite connue : le role `decor` reste faiblement decisif (10 %) sur les deux
sites. C'est le residu, celui qui attrape ce que les trois autres n'ont pas
pris ; il est a lire comme un signal, pas comme un verdict.

### 13. Search Console : la seule couche qui mesure

Le crawl decrit le site, DataForSEO estime un marche, Jev juge un contenu.
**Aucun des trois ne dit ce qui rapporte deja des clics.** Avant une refonte,
c'est pourtant la premiere question : qu'est-ce qu'on risque de casser ?

`jevseo/gsc.py`, lecture seule, gratuite, **active par defaut** : elle s'efface
d'elle-meme si le jeton manque ou si la propriete n'est pas accessible
(`--no-gsc` pour la couper, `--gsc-days` pour la fenetre, 28 jours par defaut).
Authentification par le jeton OAuth de `~/.config/lunae/gsc_token.json`,
surchargeable par `GSC_TOKEN_FILE`.

Quatre constats, tous fondes sur des clics reels :

| Regle | Ce qu'elle dit |
|---|---|
| `gsc_cannibalisation_reelle` (eleve) | Google affiche deja plusieurs de vos URL sur la meme requete. **Constate, pas estime** : la couche Jev demande a un modele si deux pages viseraient la meme intention, ici Google montre qu'il hesite deja. |
| `gsc_impressions_sans_clics` (moyen) | Le site est vu et jamais choisi. Le positionnement n'est pas le probleme, la promesse l'est. |
| `gsc_a_portee` (moyen) | Entre la 4e et la 20e place avec des impressions reelles. |
| `gsc_pages_motrices` (information) | Les pages qui portent 80 % des clics. **A produire avant toute refonte.** |

Les constats portent l'origine `gsc` et non `dataforseo` : dans un livrable,
une mesure et une estimation ne se defendent pas pareil devant un client.

**Un piege GSC que le module traite explicitement.** La dimension « requete »
est filtree, Google retire les requetes anonymisees, elle sous-compte donc
systematiquement. Sur clw.fr : **174 clics sur la dimension page, 56 seulement
sur la dimension requete**, soit une couverture de 32 %. Les totaux se lisent
donc sur la dimension page, et `totaux.couverture_requetes` dit quelle part du
trafic une lecture par requete couvre reellement.

Premiere mesure sur clw.fr, 28 jours : 174 clics pour 35 635 impressions, soit
un CTR de 0,49 %. **129 requetes en cannibalisation reelle**, dont « societe de
recouvrement » : 871 impressions, **zero clic**, quatre URL dont l'accueil en
14,5e place et un article de blog en 73e. Le constat devient la premiere action
du plan, impact 100.

**Regression corrigee au passage** : `rescore` ne relisait pas la Search
Console, les constats mesures disparaissaient donc silencieusement au premier
recalcul sans reseau.

## Ce qui n'est pas encore fait

- Un seul site teste, et il est bien construit. La regle `doorway_pages` n'a
  toujours pas ete vue se declencher sur un vrai site.
- L'A/B de langue n'a tourne que sur un corpus. Le verdict est net, mais il
  porte sur un site de service B2B national a pages ville ; un autre secteur
  pourrait donner un ecart different.
- Le PDF reste indisponible sur cette machine (Pango/GLib absents).
- Les captures d'ecran de `docs/assets/` sont encore celles de l'upstream.

## Etat des tests

`python -m unittest discover -s tests` : **57 tests, tous verts**, dont 19
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
