# Catalogage des données de mobilité de data gouv

Ce repo contient une documentation et des codes en vue de faire l'inventaire des
données open data du domaine Mobilité/Transport. Ce projet s'inscrit dans le
cadre du projet du projet MobSciDat Factory (contrat n°ANR-23-PEMO-0004). Ce
travail bénéficie d'une aide de l'Etat gérée par l'Agence Nationale de la
Recherche attribuée au project Mob Sci-Dat Factory au titre de France 2030
portant la référence ANR-23-PEMO-0004.

L'objectif final est de pouvoir créer un portail des données de mobilité,
complémentaire de transport data gouv, et de logistique data gouv, sur le
périmètre des données pour l'analyse des mobilités.

L'objectif technique à court terme est de pouvoir classer les données de
data.gouv en collections de données par thème métier (stationnement, voirie,
transport public, trafic routier, logistique et fret, vélo, marche,
accessibilité, mobilité partagée...) et par sous-thème dans chaque métier.

Le projet est
[documenté dans le wiki](https://github.com/CEREMA/catalogue-datagouv-mobi/wiki).

L'approche est de mettre en place un pipeline de traitement : sélection des jeux
de données du domaine mobilité/transport, puis, pour chaque thème :

1. sélection des jeux de données pertinents pour le thème
2. étiquetage des jeux de données par sous-thème
3. tests de la qualité des données pour quelques critères simples (date de mise
   à jour, etc.)
4. publication des collections de données par thème (dans un tableau Grist et/ou
   en tant que collection dans ecologie.data.gouv)
5. envoi de messages aux producteurs de données (retour sur la qualité des
   méta-données)

## Principe

Chaque jeu non archivé de data.gouv.fr (~75k) est rattaché à ses `k` sous-thèmes
les plus proches dans l'ontologie (`data/ontology/ontologie_v1.csv`), par
similarité d'embeddings ([bge-m3](https://huggingface.co/BAAI/bge-m3),
PostgreSQL + pgvector).

Pas de seuil ni de liste noire dans le code : l'ensemble du savoir-faire métier
se fait dans Grist, les faux amis s'écartent en enrichissant l'ontologie
(sous-thèmes de thème `contre_exemple`).

Tout ce dont Grist a besoin est calculé en amont : fraîcheur des données
(reconstruite depuis les exports, comme la date "Mis à jour le" de
data.gouv.fr), schémas déclarés, catégorie juridique des producteurs (API
SIRENE, en cache).

## Installation

```bash
cp .env.example .env
make db-up       # PostgreSQL + pgvector (docker, port 5435)
make install
make test
```

## Utilisation

```bash
make update      # tout, rejouable (cron)
```

| Étape         | Rôle                                                              |
| ------------- | ----------------------------------------------------------------- |
| `make fetch`  | télécharge les derniers exports data.gouv.fr dans `data/catalog/` |
| `make embed`  | synchronise ontologie, jeux, métadonnées ; embeddings manquants   |
| `make attach` | `k` sous-thèmes les plus proches par jeu                          |
| `make enrich` | catégorie juridique des producteurs (SIREN pas encore en cache)   |
| `make export` | tables pour Grist dans `data/grist/`                              |

Seuls les éléments nouveaux ou modifiés sont réembeddés.

Le premier calcul complet demande un GPU mais il ne dit avoir lieu qu'une fois.
Sur le serveur GPU : `make update` puis `make dump-db` ; en local : récupérer
`catalogue_mobi.dump` puis `make restore-db`.

## Données

| Dossier          | Contenu                                           | Versionné |
| ---------------- | ------------------------------------------------- | --------- |
| `data/catalog/`  | exports data.gouv.fr                              | non       |
| `data/ontology/` | ontologie (source éditée à la main)               | oui       |
| `data/grist/`    | tables à importer dans Grist                      | non       |
| `data/old/`      | sorties de l'ancienne approche (notebooks `old/`) | oui       |

## Inspiration de FlowDataGouv

<https://github.com/FLI-GCT/FlowDataGouv> est un démonstrateur développé en mars
2026 par Guillaume Clément à l'occasion de la publication du serveur MCP de
data.gouv.fr. L'idée est d'utiliser le serveur MCP pour classer, étiqueter et
nettoyer les 75k datasets de data.gouv et proposer un site alternatif à
data.gouv pour accéder. Le site a été fermé après 1 mois (PoC). Dans ce projet
(dont le code a été généré par claude), les principales données des datasets de
data.gouv sont récupérées via l'API et mises dans un dataframe (code en
typescript : src/lib/sync/catalog.ts), et enrichies par Mistral AI (catégorie,
sous-catégorie, zone géographique, résumé, score qualité — voir
enrichBatchMistral). Un contrôle qualité des datasets et ressources est
également effectué, avec calcul d'indicateurs de qualité (en python).
