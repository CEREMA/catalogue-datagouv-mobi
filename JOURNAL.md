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
