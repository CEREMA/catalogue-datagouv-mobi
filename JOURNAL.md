# Journal

## Règles de rédaction de l'ontologie

À appliquer à chaque évolution de `data/ontology/ontologie_v*.csv`.

- **Des phrases, pas des listes de termes** : décrire les données et leurs
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

## 17/11/2026 : ontologie v2

La structure du client (catégories, thèmes, sous-thèmes, mots-clés) est
considérée comme aboutie et n'est pas modifiée. Seuls les textes embeddés
évoluent. `ontologie_v1.csv` est gardée pour comparaison.

### Changements

- **Descriptions de thème** : phrase décrivant le thème, au lieu de la liste «
  Mots-clés thème ». Cette liste est conservée telle quelle dans une nouvelle
  colonne `mots_cles_theme`, utilisée par la baseline mots-clés.
- **Descriptions de sous-thème** : phrase reprenant les « Termes » du client,
  avec leur contexte (ex. « Comptages vélo » au lieu de « comptage »).
- **Thèmes `marche` et `marche_pieton` réunis** (« Marche » et « Marche, Piéton
  » dans la taxonomie : même thème, libellé différent).
- **7 contre-exemples** :

| Contre-exemple               | Raison                                                                           |
| ---------------------------- | -------------------------------------------------------------------------------- |
| `faune_flore`                | suivis de « stationnement » et « comptages » d'oiseaux (ancienne approche)       |
| `transport_maritime_fluvial` | « Trafic maritime » rattaché au trafic routier (v1) ; hors périmètre             |
| `transport_aerien`           | hors périmètre de la taxonomie                                                   |
| `urbanisme_risques`          | référentiels territoriaux (PLU, PPRN, cadastre), PPRN proches de la voirie en v1 |
| `reseaux_eau_energie`        | « réseau », « ligne » hors transport                                             |
| `finances_locales`           | « budget » : budgets des collectivités hors transport                            |
| `frequentation_equipements`  | « fréquentation » de musées, piscines, sites touristiques                        |

### Premiers effets (300 jeux, CPU)

- Rang 1 modifié pour 229 jeux sur 300. Contre-exemples au rang 1 :
  `urbanisme_risques` 188 (échantillon dominé par des PPRN de l'Ardèche),
  `reseaux_eau_energie` 8, `finances_locales` 7, `faune_flore` 7,
  `transport_maritime_fluvial` 1.
- Les vrais positifs restent en tête : IRVE (0.32), GTFS (0.34), standard CNIG
  accessibilité, cartes de bruit.
- Nouveau faux ami : « Zones forestières réglementées pour l'emploi du feu » →
  `voirie/signalisation` (« feux »).

### À vérifier après le calcul complet

- `urbanisme_risques` n'absorbe-t-il pas de vrais positifs (règles de
  stationnement des PLU, plans de déplacements) ?
- Bruit aérien (plans d'exposition au bruit) : `bruit` ou `transport_aerien` ?
- Faux ami « feu » : contre-exemple risques incendie ?
- Co-occurrences : vélos en libre service (mobilité partagée / vélo),
  accessibilité (transport collectif / voirie), comptages (trafic, vélo,
  piétons).
- Comparer v1 / v2 et baseline mots-clés / embeddings.

## 17/11/2026 : baseline mots-clés

Rattachement par mots-clés calculé à chaque `attach`, à côté des embeddings
(table `dataset_keyword`, export `rattachements_mots_cles.csv`). Il reproduit la
méthode du client (`old/pipelinecomplet.ipynb`) : mots-clés du thème cherchés
dans titre, description et tags, sans casse ni accents, en début de mot, avec
jusqu'à deux lettres de plus (pluriels).

Écarts avec la méthode d'origine :

- les tirets sont lus comme des espaces (tag `trafic-routier` = mot-clé « trafic
  routier ») ;
- tous les mots-clés présents sont trouvés, y compris imbriqués (« comptage »
  dans « comptage et flux ») ;
- en plus du thème, recherche par sous-thème avec ses mots-clés indicatifs
  (prévue mais non branchée dans la méthode d'origine) ;
- contre-exemples ignorés.

Faux positifs typiques observés sur 300 jeux : « marche » trouve « marchés
publics » (19 jeux), « budget » les budgets régionaux, « comptages » une
fréquentation en gares.
