from pathlib import Path

DATA = Path("data")

# Ontologie (source éditée à la main, cf. data/ontology/)
ONTOLOGY_PATH = DATA / "ontology" / "ontologie_v3.csv"

# Exports du catalogue data.gouv.fr, téléchargés par `fetch` sous un nom stable
CATALOG_DIR = DATA / "catalog"
CATALOG_API_URL = (
    "https://www.data.gouv.fr/api/1/datasets/catalogue-des-donnees-de-data-gouv-fr/"
)
# préfixe du titre de la ressource data.gouv -> nom du fichier local
CATALOG_EXPORTS = {
    "export-dataset": "export-dataset.csv",
    "export-organization": "export-organization.csv",
    "export-resource": "export-resource.csv",
}
DATASET_PATH = CATALOG_DIR / "export-dataset.csv"
ORGANIZATION_PATH = CATALOG_DIR / "export-organization.csv"
RESOURCE_PATH = CATALOG_DIR / "export-resource.csv"

DATASET_COLUMNS = ["id", "title", "description", "tags", "archived"]
DATASET_METADATA_COLUMNS = [
    "url",
    "organization",
    "organization_id",
    "quality_score",
    "metric.reuses",
    "metric.views",
    "created_at",
    "last_modified",
    "harvest.modified_at",
    "resources_formats",
]

ORGANIZATION_COLUMNS = [
    "id",
    "name",
    "badges",
    "business_number_id",
    "metric.datasets",
    "metric.followers",
]

# Colonnes de l'export des ressources utilisées pour la fraîcheur et les schémas
RESOURCE_DATASET_ID = "dataset.id"
RESOURCE_MODIFIED = "modified"
RESOURCE_HARVEST_MODIFIED = "harvest.modified_at"
RESOURCE_EXTRAS = "extras"
RESOURCE_ANALYSIS_MODIFIED = "$['analysis:last-modified-at']"  # dans `extras`
RESOURCE_SCHEMA = "schema_name"

# Valeur des badges data.gouv
BADGE_CERTIFIED = "certified"
BADGE_PUBLIC_SERVICE = "public-service"
BADGE_LOCAL_AUTHORITY = "local-authority"
BADGE_COMPANY = "company"
BADGE_ASSOCIATION = "association"

# APIs SIRENE (sans clé)
SIRENE_API_URL = "https://recherche-entreprises.api.gouv.fr/search"
INSEE_CJ_API_URL = "https://api.insee.fr/metadonnees/V1/codes/cj/n3"
SIRENE_DELAY = 0.2  # secondes entre deux requêtes : l'API en accepte 7 par seconde
USER_AGENT = "catalogue-mobi (+https://github.com/CEREMA/catalogue-datagouv-mobi)"

# Tables PostgreSQL
ONTOLOGY_TABLE = "ontology"
DATASET_TABLE = "dataset"
ORGANIZATION_TABLE = "organization"
MATCH_TABLE = "dataset_ontology"
KEYWORD_TABLE = "dataset_keyword"
RULE_TABLE = "dataset_rule"
SIRENE_TABLE = "sirene"
LEGAL_CATEGORY_TABLE = "categorie_juridique"
EMBEDDING_DIM = 1024  # dimension de BAAI/bge-m3

# Tables à importer dans Grist : vue SQL -> fichier de data/grist/
# (plus ontologie.csv, copie de l'ontologie source avec son id)
GRIST_DIR = DATA / "grist"
GRIST_EXPORTS = {
    "grist_organisations": "organisations.csv",
    "grist_jeux": "jeux.csv",
    "grist_couples": "rattachements.csv",
    "grist_rattachements_mots_cles": "rattachements_mots_cles.csv",
    "grist_rattachements_regles": "rattachements_regles.csv",
    "grist_rattachements": "rattachements_embeddings.csv",
}
GRIST_DESCRIPTION_MAX_CHARS = 1000

# Modèle d'embeddings
DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_MAX_SEQ_LENGTH = 1024

# Instruction BGE pour le côté "requête courte" d'une recherche asymétrique
# requête courte / document long (recommandation BAAI, cf. README "Modèle").
# Appliquée uniquement au texte de l'ontologie, jamais à celui des jeux.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

# Valeurs par défaut de la ligne de commande
DEFAULT_K = 3
DEFAULT_ENCODE_BATCH_SIZE = 32
DEFAULT_DB_BATCH_SIZE = 1024
