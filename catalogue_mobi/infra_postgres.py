import csv
import io
import os
from pathlib import Path
from typing import Iterable

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2 import sql
from psycopg2.extras import execute_values

from catalogue_mobi.constants import (
    DATASET_TABLE,
    EMBEDDING_DIM,
    KEYWORD_TABLE,
    LEGAL_CATEGORY_TABLE,
    MATCH_TABLE,
    ONTOLOGY_TABLE,
    ORGANIZATION_TABLE,
    RULE_TABLE,
    SHORT_MAX_DISTANCE,
    SHORT_MAX_RANK,
    SIRENE_TABLE,
)
from catalogue_mobi.ports import Document, Vector

DOCUMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS {table} (
    id TEXT PRIMARY KEY,
    label TEXT,
    text TEXT NOT NULL,
    embedding vector({dim})
);
CREATE INDEX IF NOT EXISTS {index} ON {table}
    USING hnsw (embedding vector_cosine_ops);
"""

SCHEMA = """
ALTER TABLE dataset
    ADD COLUMN IF NOT EXISTS url TEXT,
    ADD COLUMN IF NOT EXISTS organization_id TEXT,
    ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS reuses BIGINT,
    ADD COLUMN IF NOT EXISTS views BIGINT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS last_modified TIMESTAMP,
    ADD COLUMN IF NOT EXISTS harvest_modified_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS last_update TIMESTAMP,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS formats TEXT,
    ADD COLUMN IF NOT EXISTS schemas TEXT,
    ADD COLUMN IF NOT EXISTS tags TEXT,
    ADD COLUMN IF NOT EXISTS description TEXT;

CREATE TABLE IF NOT EXISTS organization (
    id TEXT PRIMARY KEY,
    name TEXT,
    badges TEXT,
    is_certified BOOLEAN,
    is_public_service BOOLEAN,
    is_local_authority BOOLEAN,
    is_company BOOLEAN,
    is_association BOOLEAN,
    business_number_id TEXT,
    siren TEXT,
    datasets_count INTEGER,
    followers INTEGER
);

-- Cache des appels à l'API SIRENE : un SIREN n'est interrogé qu'une fois.
-- Les colonnes dérivées (famille...) sont recalculées à chaque `enrich`.
CREATE TABLE IF NOT EXISTS sirene (
    siren TEXT PRIMARY KEY,
    nom_sirene TEXT,
    nature_juridique TEXT,
    interroge_le DATE,
    famille TEXT,
    niveau TEXT,
    type_producteur TEXT,
    badges_acceptes TEXT
);

CREATE TABLE IF NOT EXISTS categorie_juridique (
    code TEXT PRIMARY KEY,
    libelle TEXT
);

CREATE TABLE IF NOT EXISTS dataset_ontology (
    dataset_id TEXT REFERENCES dataset (id) ON DELETE CASCADE,
    ontology_id TEXT REFERENCES ontology (id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,
    distance DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (dataset_id, ontology_id)
);
CREATE INDEX IF NOT EXISTS idx_dataset_ontology_distance
    ON dataset_ontology (ontology_id, distance);

-- Rattachement par mots-clés (baseline) : par thème (ontology_id NULL) et
-- par sous-thème, avec les mots-clés trouvés
CREATE TABLE IF NOT EXISTS dataset_keyword (
    dataset_id TEXT NOT NULL REFERENCES dataset (id) ON DELETE CASCADE,
    theme TEXT NOT NULL,
    ontology_id TEXT REFERENCES ontology (id) ON DELETE CASCADE,
    keywords TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dataset_keyword ON dataset_keyword (dataset_id);

-- Rattachement par règles : termes, mots du contexte requis et exclusions
-- trouvés
CREATE TABLE IF NOT EXISTS dataset_rule (
    dataset_id TEXT NOT NULL REFERENCES dataset (id) ON DELETE CASCADE,
    ontology_id TEXT NOT NULL REFERENCES ontology (id) ON DELETE CASCADE,
    termes TEXT,
    contexte TEXT,
    exclus TEXT,
    PRIMARY KEY (dataset_id, ontology_id)
);
"""

# Tables à importer dans Grist (une vue par table, colonnes en français).
# Supprimées puis recréées : CREATE OR REPLACE ne sait pas retirer une colonne.
GRIST_VIEWS = """
DROP VIEW IF EXISTS grist_organisations, grist_jeux_court, grist_jeux,
    grist_couples_court, grist_couples, grist_rattachements_court,
    grist_rattachements, grist_rattachements_mots_cles, grist_rattachements_regles;

CREATE VIEW grist_organisations AS
SELECT o.id AS id_organisation,
       o.name AS nom,
       'https://www.data.gouv.fr/organizations/' || o.id AS url,
       o.badges,
       o.is_certified::text AS certifiee,
       o.is_public_service::text AS service_public,
       o.is_local_authority::text AS autorite_locale,
       o.is_company::text AS entreprise,
       o.is_association::text AS association,
       o.siren,
       s.nom_sirene,
       s.nature_juridique,
       cj.libelle AS categorie_juridique,
       s.famille,
       s.niveau,
       s.type_producteur,
       s.badges_acceptes,
       o.datasets_count AS nb_jeux,
       o.followers AS abonnes
FROM organization o
LEFT JOIN sirene s ON s.siren = o.siren
LEFT JOIN categorie_juridique cj ON cj.code = s.nature_juridique
WHERE EXISTS (SELECT 1 FROM dataset d WHERE d.organization_id = o.id);

CREATE VIEW grist_jeux AS
SELECT d.id AS id_jeu,
       d.label AS titre,
       d.url,
       d.organization_id AS organisation,
       d.description,
       d.tags AS mots_cles,
       d.formats,
       d.schemas,
       d.created_at AS cree_le,
       d.last_modified AS fiche_modifiee_le,
       d.last_update AS donnees_maj_le,
       d.archived_at AS archive_le,
       d.quality_score AS score_qualite,
       d.reuses AS reutilisations,
       d.views AS vues
FROM dataset d;

-- Variante allégée pour l'import manuel (Grist limite un fichier à 30 Mo) :
-- description courte, pas d'url (formule Grist :
-- "https://www.data.gouv.fr/datasets/" + $id_jeu)
CREATE VIEW grist_jeux_court AS
SELECT id_jeu, titre, organisation, left(description, 50) AS description,
       mots_cles, formats, schemas, cree_le, fiche_modifiee_le, donnees_maj_le,
       archive_le, score_qualite, reutilisations, vues
FROM grist_jeux;

-- Distance arrondie à 3 décimales
CREATE VIEW grist_rattachements AS
SELECT m.dataset_id AS jeu,
       m.ontology_id AS sous_theme,
       m.rank AS rang,
       round(m.distance::numeric, 3) AS distance
FROM dataset_ontology m;

CREATE VIEW grist_rattachements_mots_cles AS
SELECT k.dataset_id AS jeu,
       k.theme,
       k.ontology_id AS sous_theme,
       k.keywords AS mots_trouves
FROM dataset_keyword k;

CREATE VIEW grist_rattachements_regles AS
SELECT g.dataset_id AS jeu,
       g.ontology_id AS sous_theme,
       g.termes,
       g.contexte,
       g.exclus
FROM dataset_rule g;
"""

# Variante allégée pour l'import manuel (mémoire de Grist) : rattachements de
# rang et de distance bornés, contre-exemples compris (pour savoir dans Grist
# si un contre-exemple est mieux classé)
GRIST_VIEWS += f"""
CREATE VIEW grist_rattachements_court AS
SELECT r.*
FROM grist_rattachements r
WHERE r.rang <= {int(SHORT_MAX_RANK)}
  AND r.distance < {float(SHORT_MAX_DISTANCE)};
"""

# Rattachements toutes méthodes : un couple (jeu, sous-thème) par ligne, proposé
# par au moins une méthode, colonnes vides pour une méthode qui ne le propose
# pas. Les mots-clés trouvés au seul niveau du thème n'ont pas de sous-thème.
COUPLES_VIEW = """
CREATE VIEW {name} AS
WITH k AS (SELECT dataset_id AS jeu, ontology_id AS sous_theme, keywords
           FROM dataset_keyword
           WHERE ontology_id IS NOT NULL),
     g AS (SELECT dataset_id AS jeu, ontology_id AS sous_theme,
                  termes, contexte, exclus
           FROM dataset_rule),
     couples AS (SELECT jeu, sous_theme FROM {embeddings}
                 UNION SELECT jeu, sous_theme FROM k
                 UNION SELECT jeu, sous_theme FROM g)
SELECT c.jeu,
       c.sous_theme,
       e.rang AS rang_embeddings,
       e.distance AS distance_embeddings,
       k.keywords AS mots_cles,
       g.termes AS regles_termes,
       g.contexte AS regles_contexte,
       g.exclus AS regles_exclus
FROM couples c
LEFT JOIN {embeddings} e USING (jeu, sous_theme)
LEFT JOIN k USING (jeu, sous_theme)
LEFT JOIN g USING (jeu, sous_theme);
"""
GRIST_VIEWS += COUPLES_VIEW.format(name="grist_couples", embeddings="grist_rattachements")
GRIST_VIEWS += COUPLES_VIEW.format(
    name="grist_couples_court", embeddings="grist_rattachements_court"
)


def connect():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


ALL_TABLES = (
    RULE_TABLE,
    KEYWORD_TABLE,
    MATCH_TABLE,
    ONTOLOGY_TABLE,
    DATASET_TABLE,
    ORGANIZATION_TABLE,
    SIRENE_TABLE,
    LEGAL_CATEGORY_TABLE,
)


def init_db(conn, reset: bool = False) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        if reset:
            for table in ALL_TABLES:
                print(f"Suppression de la table {table}...")
                cur.execute(
                    sql.SQL("DROP TABLE IF EXISTS {} CASCADE;").format(
                        sql.Identifier(table)
                    )
                )
        for table in (ONTOLOGY_TABLE, DATASET_TABLE):
            cur.execute(
                sql.SQL(DOCUMENT_SCHEMA).format(
                    table=sql.Identifier(table),
                    index=sql.Identifier(f"idx_{table}_embedding"),
                    dim=sql.Literal(EMBEDDING_DIM),
                )
            )
        cur.execute(SCHEMA)
        cur.execute(GRIST_VIEWS)
    conn.commit()
    register_vector(conn)


def _to_staging(cur, name: str, columns: list[str], rows) -> None:
    """Charge `rows` (listes de valeurs) dans une table temporaire aux
    colonnes TEXT, supprimée au commit. None devient chaîne vide : les
    requêtes convertissent avec NULLIF(col, '')."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    buf.seek(0)
    cur.execute(
        sql.SQL("CREATE TEMP TABLE {} ({}) ON COMMIT DROP;").format(
            sql.Identifier(name),
            sql.SQL(", ").join(
                sql.SQL("{} TEXT").format(sql.Identifier(c)) for c in columns
            ),
        )
    )
    cur.copy_expert(
        sql.SQL("COPY {} FROM STDIN WITH CSV").format(sql.Identifier(name)).as_string(
            cur
        ),
        buf,
    )


class PostgresDocumentStore:
    """Implémentation de `DocumentStore` sur une table PostgreSQL + pgvector."""

    def __init__(self, conn, table: str):
        self._conn = conn
        self._table = sql.Identifier(table)

    def sync(self, documents: list[Document]) -> None:
        """Ajoute les nouveaux documents et met à jour les modifiés : un texte
        changé perd son embedding, qui sera recalculé."""
        with self._conn.cursor() as cur:
            _to_staging(
                cur,
                "staging_documents",
                ["id", "label", "text"],
                ([d.id, d.label, d.text] for d in documents),
            )
            cur.execute(
                sql.SQL(
                    "INSERT INTO {table} AS t (id, label, text) "
                    "SELECT DISTINCT ON (id) id, label, text FROM staging_documents "
                    "ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label, "
                    "text = EXCLUDED.text, embedding = CASE "
                    "WHEN t.text = EXCLUDED.text THEN t.embedding END "
                    "WHERE t.text IS DISTINCT FROM EXCLUDED.text "
                    "OR t.label IS DISTINCT FROM EXCLUDED.label;"
                ).format(table=self._table)
            )
            changed = cur.rowcount
        self._conn.commit()
        print(f"{len(documents)} documents lus, {changed} nouveaux ou modifiés")

    def delete_except(self, ids: set[str]) -> int:
        """Supprime les documents dont l'id n'est pas dans `ids`."""
        with self._conn.cursor() as cur:
            _to_staging(cur, "staging_ids", ["id"], ([i] for i in ids))
            cur.execute(
                sql.SQL(
                    "DELETE FROM {} t WHERE NOT EXISTS "
                    "(SELECT 1 FROM staging_ids s WHERE s.id = t.id);"
                ).format(self._table)
            )
            deleted = cur.rowcount
        self._conn.commit()
        print(f"{deleted} documents supprimés")
        return deleted

    def pending(self, limit: int) -> list[Document]:
        with self._conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT id, label, text FROM {} "
                    "WHERE embedding IS NULL ORDER BY id LIMIT %s;"
                ).format(self._table),
                (limit,),
            )
            rows = cur.fetchall()
        return [Document(id=id, label=label, text=text) for id, label, text in rows]

    def save_embeddings(self, embeddings: dict[str, Vector]) -> None:
        with self._conn.cursor() as cur:
            execute_values(
                cur,
                sql.SQL(
                    "UPDATE {table} AS t SET embedding = v.embedding "
                    "FROM (VALUES %s) AS v(id, embedding) WHERE t.id = v.id;"
                )
                .format(table=self._table)
                .as_string(cur),
                [
                    (id, np.asarray(vec, dtype=np.float32))
                    for id, vec in embeddings.items()
                ],
                template="(%s, %s::vector)",
            )
        self._conn.commit()


class PostgresDatasetMatcher:
    """Implémentation de `DatasetMatcher` : k plus proches voisins via pgvector.

    Recalcul complet à chaque appel (~50 sous-thèmes x ~75k jeux de données).
    """

    def __init__(self, conn):
        self._conn = conn

    def attach(self, k: int) -> int:
        with self._conn.cursor() as cur:
            cur.execute("TRUNCATE dataset_ontology;")
            cur.execute(
                """
                INSERT INTO dataset_ontology (dataset_id, ontology_id, rank, distance)
                SELECT d.id, m.id, m.rank, m.distance
                FROM dataset d
                CROSS JOIN LATERAL (
                    SELECT o.id,
                           o.embedding <=> d.embedding AS distance,
                           row_number() OVER (
                               ORDER BY o.embedding <=> d.embedding
                           ) AS rank
                    FROM ontology o
                    WHERE o.embedding IS NOT NULL
                    ORDER BY distance
                    LIMIT %s
                ) m
                WHERE d.embedding IS NOT NULL;
                """,
                (k,),
            )
            count = cur.rowcount
        self._conn.commit()
        return count


def dataset_texts(conn, batch_size: int = 5000):
    """(id, texte) de chaque jeu en base, lus par lots (curseur serveur)."""
    with conn.cursor(name="dataset_texts") as cur:
        cur.itersize = batch_size
        cur.execute("SELECT id, text FROM dataset ORDER BY id;")
        yield from cur


def save_rule_matches(conn, rows: Iterable[dict]) -> int:
    """Remplace les rattachements par règles."""
    fields = ["dataset_id", "ontology_id", "termes", "contexte", "exclus"]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE dataset_rule;")
        _to_staging(cur, "staging_rule", fields, ([r[f] for f in fields] for r in rows))
        cur.execute(
            "INSERT INTO dataset_rule (dataset_id, ontology_id, termes, contexte, exclus) "
            "SELECT * FROM staging_rule;"
        )
        count = cur.rowcount
    conn.commit()
    return count


def save_keyword_matches(conn, rows: Iterable[dict]) -> int:
    """Remplace les rattachements par mots-clés."""
    fields = ["dataset_id", "theme", "ontology_id", "keywords"]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE dataset_keyword;")
        _to_staging(cur, "staging_keyword", fields, ([r[f] for f in fields] for r in rows))
        cur.execute(
            "INSERT INTO dataset_keyword (dataset_id, theme, ontology_id, keywords) "
            "SELECT dataset_id, theme, NULLIF(ontology_id, ''), keywords "
            "FROM staging_keyword;"
        )
        count = cur.rowcount
    conn.commit()
    return count


DATASET_METADATA_FIELDS = [
    "id",
    "url",
    "organization_id",
    "quality_score",
    "reuses",
    "views",
    "created_at",
    "last_modified",
    "harvest_modified_at",
    "archived_at",
    "formats",
    "tags",
    "description",
]


def update_dataset_metadata(conn, rows: list[dict]) -> int:
    """Rafraîchit les métadonnées data.gouv des jeux déjà présents en base.
    N'affecte jamais `text` ni `embedding`."""
    with conn.cursor() as cur:
        _to_staging(
            cur,
            "staging_metadata",
            DATASET_METADATA_FIELDS,
            ([r[f] for f in DATASET_METADATA_FIELDS] for r in rows),
        )
        cur.execute(
            "UPDATE dataset AS d SET "
            "url = NULLIF(s.url, ''), "
            "organization_id = NULLIF(s.organization_id, ''), "
            "quality_score = NULLIF(s.quality_score, '')::double precision, "
            "reuses = NULLIF(s.reuses, '')::bigint, "
            "views = NULLIF(s.views, '')::bigint, "
            "created_at = NULLIF(s.created_at, '')::timestamp, "
            "last_modified = NULLIF(s.last_modified, '')::timestamp, "
            "harvest_modified_at = NULLIF(s.harvest_modified_at, '')::timestamp, "
            "archived_at = NULLIF(s.archived_at, '')::timestamp, "
            "formats = NULLIF(s.formats, ''), "
            "tags = NULLIF(s.tags, ''), "
            "description = NULLIF(s.description, '') "
            "FROM staging_metadata s WHERE d.id = s.id;"
        )
        updated = cur.rowcount
    conn.commit()
    return updated


def update_resource_stats(conn, rows: list[dict]) -> int:
    """Date de mise à jour des données et schémas, issus des ressources.

    `last_update` reproduit la date « Mis à jour le » de data.gouv.fr : pour
    un jeu moissonné, la date de modification déclarée par le catalogue
    source (`harvest_modified_at`) ; sinon, la plus récente des dates de ses
    ressources ; sans ressource, la date de la fiche (`last_modified`).
    Métadonnées des jeux à charger avant. Vérifié contre l'API sur un
    échantillon (écarts de quelques secondes possibles : fiche retouchée
    après la publication de l'export)."""
    with conn.cursor() as cur:
        _to_staging(
            cur,
            "staging_resources",
            ["id", "last_update", "schemas"],
            ([r["id"], r["last_update"], r["schemas"]] for r in rows),
        )
        cur.execute(
            "UPDATE dataset AS d SET "
            "last_update = COALESCE(d.harvest_modified_at, "
            "NULLIF(s.last_update, '')::timestamp, d.last_modified), "
            "schemas = NULLIF(s.schemas, '') "
            "FROM dataset AS d2 "
            "LEFT JOIN staging_resources s ON s.id = d2.id "
            "WHERE d.id = d2.id;"
        )
        updated = cur.rowcount
    conn.commit()
    return updated


def update_organizations(conn, rows: list[dict]) -> int:
    """Upsert des organisations (id, nom) référencées par les jeux de
    données, y compris celles absentes de l'export des organisations."""
    with conn.cursor() as cur:
        _to_staging(
            cur, "staging_organization", ["id", "name"], ([r["id"], r["name"]] for r in rows)
        )
        cur.execute(
            "INSERT INTO organization (id, name) "
            "SELECT DISTINCT ON (id) id, NULLIF(name, '') FROM staging_organization "
            "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;"
        )
        upserted = cur.rowcount
    conn.commit()
    return upserted


ORGANIZATION_FIELDS = [
    "id",
    "name",
    "badges",
    "is_certified",
    "is_public_service",
    "is_local_authority",
    "is_company",
    "is_association",
    "business_number_id",
    "siren",
    "datasets_count",
    "followers",
]


def update_organization_metadata(conn, rows: list[dict]) -> int:
    """Enrichit les organisations (badges, SIREN, envergure) depuis l'export
    data.gouv des organisations."""
    with conn.cursor() as cur:
        _to_staging(
            cur,
            "staging_organization_metadata",
            ORGANIZATION_FIELDS,
            ([r[f] for f in ORGANIZATION_FIELDS] for r in rows),
        )
        cur.execute(
            "INSERT INTO organization "
            "(id, name, badges, is_certified, is_public_service, "
            "is_local_authority, is_company, is_association, "
            "business_number_id, siren, datasets_count, followers) "
            "SELECT DISTINCT ON (id) id, NULLIF(name, ''), NULLIF(badges, ''), "
            "is_certified::boolean, is_public_service::boolean, "
            "is_local_authority::boolean, is_company::boolean, "
            "is_association::boolean, NULLIF(business_number_id, ''), "
            "NULLIF(siren, ''), NULLIF(datasets_count, '')::integer, "
            "NULLIF(followers, '')::integer "
            "FROM staging_organization_metadata "
            "ON CONFLICT (id) DO UPDATE SET "
            "name = EXCLUDED.name, badges = EXCLUDED.badges, "
            "is_certified = EXCLUDED.is_certified, "
            "is_public_service = EXCLUDED.is_public_service, "
            "is_local_authority = EXCLUDED.is_local_authority, "
            "is_company = EXCLUDED.is_company, "
            "is_association = EXCLUDED.is_association, "
            "business_number_id = EXCLUDED.business_number_id, "
            "siren = EXCLUDED.siren, "
            "datasets_count = EXCLUDED.datasets_count, "
            "followers = EXCLUDED.followers;"
        )
        upserted = cur.rowcount
    conn.commit()
    return upserted


# --- Cache SIRENE ---------------------------------------------------------


def missing_sirens(conn) -> list[str]:
    """SIREN des producteurs de jeux en base, absents du cache."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT o.siren FROM organization o "
            "WHERE o.siren IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM dataset d WHERE d.organization_id = o.id) "
            "AND NOT EXISTS (SELECT 1 FROM sirene s WHERE s.siren = o.siren) "
            "ORDER BY o.siren;"
        )
        return [row[0] for row in cur.fetchall()]


def save_sirens(conn, rows: list[dict]) -> None:
    fields = ["siren", "nom_sirene", "nature_juridique", "interroge_le"]
    with conn.cursor() as cur:
        _to_staging(cur, "staging_sirene", fields, ([r[f] for f in fields] for r in rows))
        cur.execute(
            "INSERT INTO sirene (siren, nom_sirene, nature_juridique, interroge_le) "
            "SELECT siren, NULLIF(nom_sirene, ''), NULLIF(nature_juridique, ''), "
            "interroge_le::date FROM staging_sirene "
            "ON CONFLICT (siren) DO UPDATE SET nom_sirene = EXCLUDED.nom_sirene, "
            "nature_juridique = EXCLUDED.nature_juridique, "
            "interroge_le = EXCLUDED.interroge_le;"
        )
    conn.commit()


def legal_categories(conn) -> list[tuple[str, str | None]]:
    """(siren, nature_juridique) de tout le cache."""
    with conn.cursor() as cur:
        cur.execute("SELECT siren, nature_juridique FROM sirene;")
        return cur.fetchall()


def save_classifications(conn, rows: list[dict]) -> None:
    """Colonnes dérivées de la catégorie juridique (cf. producteurs.py)."""
    fields = ["siren", "famille", "niveau", "type_producteur", "badges_acceptes"]
    with conn.cursor() as cur:
        _to_staging(cur, "staging_classif", fields, ([r[f] for f in fields] for r in rows))
        cur.execute(
            "UPDATE sirene AS t SET famille = NULLIF(s.famille, ''), "
            "niveau = NULLIF(s.niveau, ''), "
            "type_producteur = NULLIF(s.type_producteur, ''), "
            "badges_acceptes = NULLIF(s.badges_acceptes, '') "
            "FROM staging_classif s WHERE t.siren = s.siren;"
        )
    conn.commit()


def missing_legal_category_labels(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT s.nature_juridique FROM sirene s "
            "WHERE s.nature_juridique IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM categorie_juridique c WHERE c.code = s.nature_juridique) "
            "ORDER BY 1;"
        )
        return [row[0] for row in cur.fetchall()]


def save_legal_category_labels(conn, labels: dict[str, str]) -> None:
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO categorie_juridique (code, libelle) VALUES %s "
            "ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;",
            [(code, libelle or None) for code, libelle in labels.items()],
        )
    conn.commit()


# --- Export vers Grist ----------------------------------------------------


def export_view(conn, view: str, dest: Path) -> int:
    """Écrit le contenu d'une vue dans un CSV (avec en-tête). Retourne le
    nombre de lignes."""
    with conn.cursor() as cur, open(dest, "w", encoding="utf-8", newline="") as f:
        cur.copy_expert(
            sql.SQL("COPY (SELECT * FROM {} ORDER BY 1) TO STDOUT WITH CSV HEADER")
            .format(sql.Identifier(view))
            .as_string(cur),
            f,
        )
        return cur.rowcount
