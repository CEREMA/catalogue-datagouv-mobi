# Journal

## 17/11/2026

### Mise en place d'une ontologie v2

La structure du client (catégories, thèmes, sous-thèmes, mots-clés) est
considérée comme aboutie et n'est pas modifiée. Seuls les textes embeddés
évoluent. `ontologie_v1.csv` est gardée pour comparaison.

- **Descriptions de thème** : phrase décrivant le thème, au lieu de la liste «
  Mots-clés thème ». Cette liste est conservée telle quelle dans une nouvelle
  colonne `mots_cles_theme`, utilisée par la baseline mots-clés.
- **Descriptions de sous-thème** : phrase reprenant les « Termes » du client,
  avec leur contexte (ex. « Comptages vélo » au lieu de « comptage »).
- **Thèmes `marche` et `marche_pieton` réunis** (« Marche » et « Marche, Piéton
  » dans la taxonomie : même thème, libellé différent).
- **7 contre-exemples** :
  - `faune_flore` : suivis de « stationnement » et « comptages » d'oiseaux
    (ancienne approche) ;
  - `transport_maritime_fluvial` : « Trafic maritime » rattaché au trafic
    routier (v1) ; hors périmètre ;
  - `transport_aerien` : hors périmètre de la taxonomie ;
  - `urbanisme_risques` : référentiels territoriaux (PLU, PPRN, cadastre), PPRN
    proches de la voirie en v1 ;
  - `reseaux_eau_energie` : « réseau », « ligne » hors transport ;
  - `finances_locales` : « budget », budgets des collectivités hors transport ;
  - `frequentation_equipements` : « fréquentation » de musées, piscines, sites
    touristiques.

### Baseline mots-clés

Rattachement par mots-clés calculé à chaque `attach`. Il reproduit l'ancienne
méthode testée (`old/pipelinecomplet.ipynb`) : mots-clés du thème cherchés dans
titre, description et tags, sans casse ni accents, en début de mot, avec jusqu'à
deux lettres de plus (pluriels).

Écarts avec la méthode d'origine :

- les tirets sont lus comme des espaces (tag `trafic-routier` = mot-clé « trafic
  routier ») ;
- tous les mots-clés présents sont trouvés, y compris imbriqués (« comptage »
  dans « comptage et flux ») ;
- en plus du thème, recherche par sous-thème avec ses mots-clés indicatifs
  (prévue mais non branchée dans la méthode d'origine) ;
- contre-exemples ignorés.

Premiers résultats : quelques faux positifs typiques sont déjà observés sur 300
jeux : « marche » trouve « marchés publics » (19 jeux), « budget » les budgets
régionaux, « comptages » une fréquentation en gares.

## Méthode par embeddings

Chaque jeu (titre, description nettoyée, tags) et chaque sous-thème de
l'ontologie (descriptions du thème et du sous-thème, mots-clés) est embeddé avec
le modèle multilingue `BAAI/bge-m3`. Pour chaque jeu, les 3 sous-thèmes les plus
proches (contre-exemples compris) sont retenus avec leur distance sans seuil (le
seuil sera calibré dans Grist).

Les bonnes pratiques suivantes ont été constatées sur un projet précédent et
sont à appliquer dans les ontologies :

- **Usage de phrases, pas des listes de termes** : décrire les données et leurs
  producteurs (« Comptages routiers de véhicules, débits, vitesses moyennes »)
  plutôt qu'aligner des mots-clés.
- **Contextualiser les mots ambigus** : comptage, stationnement, réseau, budget,
  fréquentation, tarif, travaux, entrepôt, feux… Un mot dominant écrase le reste
  de la description : l'accompagner de son contexte transport, et donner au sens
  concurrent son propre contre-exemple.
- **Pas de négation** (« hors X ») : elle ne fonctionne pas sur un embedding.
  Pour écarter un sens, créer un contre-exemple.
- **Pas de sous-thème par échelle** (national, local) : l'embedding la distingue
  mal, le type de producteur (SIRENE) la donne.
- **Contre-exemples** à partir des faux amis observés, et pour les référentiels
  territoriaux (urbanisme, cadastre, risques), très nombreux sur data.gouv.fr et
  proches de tout ce qui est local.
- **Fusionner deux sous-thèmes** seulement si leur co-occurrence (rangs 1 à 3)
  est mesurée, et avec l'accord du client.

## Paramétrage Github

Mise en place des premières bonnes pratiques :

- Protection de la branche main (obligation passage par PR) et forçage des
  "squash and merge"
- Suppression auto des branches post merge

## 20/11/2026

### Export allégé pour Grist

L'import manuel de Grist sur l'instance gouv est limité à 30 Mo par fichier. Le
fichier `jeux.csv` complet pèse 70 Mo dont 40 Mo environ de descriptions, même
nettoyée. `make short-export` le raccourcit, la description est coupée à 50
caractères et `url` est retirée (formule Grist
`"https://www.data.gouv.fr/datasets/" + $id_jeu`). C'est une option :
`make export` reste complet. La vraie solution reste de réduire le nombre de
jeux poussés, par le pré-filtre « candidats mobilité ».

Le document Grist a ensuite saturé la mémoire du serveur (`MemoryError`, ~370k
lignes). `make short-export` filtre donc aussi les rattachements par embeddings
: 2 par jeu (contre-exemples compris), seulement pour les jeux ayant un
rattachement hors contre-exemple à moins de 0,5 ou un mot-clé trouvé. Tous les
jeux restent dans `jeux.csv`. Rattachements : 226 764 → 81 558 lignes.

### Table des rattachements toutes méthodes

Grist ne sait pas créer de lignes par formule, donc pas d'union des tables par
méthode. `rattachements.csv` la calcule (`FULL JOIN`) : une ligne par couple
(jeu, sous-thème) proposé par au moins une méthode, avec rang et distance
embeddings et mots-clés trouvés (vides si la méthode ne le propose pas). La
validation manuelle est une colonne ajoutée dans Grist, conservée au réimport
(_Update existing records_ sur `jeu` + `sous_theme`). Dans Grist, cette table
remplace les tables par méthode.

## 25/11/2026

### Ontologie v3 et méthode par règles

Premiers retours : la baseline ne trouve une expression (« tarification
stationnement ») que si ses mots se suivent, et n'a ni mots contextuels ni mots
à exclure. Le wiki du projet décrivait déjà deux types de mots-clés :
discriminants (leur présence suffit) et contextuels (à associer à d'autres
mots-clés). Tableau initial à retrouver

La baseline reste inchangée Une troisième méthode, **règles**, s'appuie sur
trois colonnes ajoutées dans `ontologie_v3.csv` (colonnes v2 inchangées, donc
pas de réembedding) :

- `mots_cles_discriminants` : rattachent seuls ;
- `mots_cles_contextuels` : rattachent si un mot-clé du thème
  (`mots_cles_theme`), autre qu'eux-mêmes, est aussi trouvé ;
- `mots_exclus` : signalés dans une colonne, sans filtrage.

Une expression est trouvée si tous ses mots sont présents, dans n'importe quel
ordre. Les méthodes ne sont pas agrégées : `rattachements.csv` met côte à côte
mots-clés, règles (`regles_discriminants`, `regles_contextuels`,
`regles_exclus`) et embeddings, pour trouver la règle métier dans Grist.

Les colonnes sont à compléter par le tableau : mots indicatifs v2 répartis entre
discriminants et contextuels, faux amis connus en exclus. Premiers faux amis vus
sur le catalogue complet :

- « zone bleue » : zonage des PPR (2 486 jeux), en contextuel, `ppr` exclu ;
- jeux IRVE (schéma avec « paiement », « tarification », « parking ») dans le
  stationnement : `irve, recharge` exclus ;
- `stationnement` en contextuel revenait à tout le thème : retiré.

### Réembedding de la seule ontologie

`make embed-ontology` (`embed --ontology-only`) ne traite que l'ontologie : une
vingtaine de secondes sur CPU, essentiellement le chargement du modèle. C'est la
commande à lancer après une modification de l'ontologie (cf. README).

### Tableau de classification du client dans la v3

On réutilise le tableau comprenant des contre exemples afin d'alimenter la v3 de
l'ontologie. Les termes forts et expressions ont le même rôle et sont réunis
dans `termes`. Un terme rattache si un mot de `contexte_requis` est trouvé,
lui-même compris (« horodateur » est terme et contexte du stationnement) ; sans
contexte requis (socio-économie, environnement), il suffit seul. `exclusions`
sont signalées, sans filtrer.

**Structure** : 60 sous-catégories dans le tableau.

- 36 rattachées à un sous-thème v2, id conservé. Fusions : `offre_planifiee` ←
  Réseaux et lignes, Arrêts et stations, Horaires théoriques ;
  `amenagements_cyclables` ← Aménagement cyclable, Pistes et bandes ;
  `trafic_historique…` ← Comptages et débit, Vitesse et temps de parcours ;
  `transport_collectif/accessibilite` ← TC › Accessibilité et Accessibilité ›
  Accessibilité des transports (doublon du tableau).
- 23 nouveaux sous-thèmes, dont 7 dans 4 nouveaux thèmes : `accessibilite` (les
  deux sous-thèmes d'accessibilité existants restent dans leur thème, ids
  conservés), `population_menages`, `territoire_equipements`, `qualite_air`.
  Slugs, descriptions et `mots_cles_indicatifs` (termes forts du tableau)
  rédigés par nous, **à relire par le client**.
- 1 ligne vide ignorée : Stationnement › Places réservées PMR.
- 8 sous-thèmes v2 absents du tableau gardés tels quels (piétons, trottinettes,
  véhicules, IRVE, entrepôts, GES, accidentologie), contexte requis =
  `mots_cles_theme`.

**Provenance** : `termes` et `exclusions` sont repris du tableau et complétés
(faux amis constatés : `ppr`, `irve, recharge`, `oiseaux`).

**Contre-exemples** : tous leurs champs sont remplis. `theme_description` est
embeddée : c'est une description neutre de leurs domaines, sans négation. Les
autres champs sont ignorés par la baseline et les règles : `termes` reprend les
mots indicatifs, `mots_cles_theme`, `contexte_requis` et `exclusions` valent «
Contre-exemple » (un contexte introuvable, qui les neutraliserait si les règles
les prenaient un jour en compte). Effet : les 7 contre-exemples sont réembeddés,
les rattachements par embeddings de l'export allégé passent de 97 094 à 96 586.
