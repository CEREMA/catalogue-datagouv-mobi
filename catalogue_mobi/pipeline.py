"""Lignes CSV -> documents et métadonnées, embedding par lots (logique pure)."""

from typing import Iterable

from catalogue_mobi.constants import (
    BADGE_ASSOCIATION,
    BADGE_CERTIFIED,
    BADGE_COMPANY,
    BADGE_LOCAL_AUTHORITY,
    BADGE_PUBLIC_SERVICE,
    GRIST_DESCRIPTION_MAX_CHARS,
)
from catalogue_mobi.ports import Document, DocumentStore, Embedder
from catalogue_mobi.producteurs import siren
from catalogue_mobi.texts import (
    archived_at,
    clean_description,
    dataset_text,
    is_archived,
    ontology_text,
)


def ontology_id(row: dict) -> str:
    return f"{row['theme']}/{row['sous_theme']}"


def ontology_documents(rows: Iterable[dict]) -> list[Document]:
    return [
        Document(
            id=ontology_id(row),
            label=row.get("sous_theme_label") or row["sous_theme"],
            text=ontology_text(row),
        )
        for row in rows
    ]


def dataset_documents(
    rows: Iterable[dict], with_archived: bool = False
) -> list[Document]:
    """Jeux de données à embedder. Les archivés sont exclus par défaut ; avec
    `with_archived`, ils sont embeddés comme les autres et repérables par
    `archived_at`."""
    return [
        Document(id=row["id"], label=row["title"], text=dataset_text(row))
        for row in rows
        if with_archived or not is_archived(row)
    ]


def dataset_metadata(rows: Iterable[dict]) -> list[dict]:
    """Métadonnées data.gouv d'un jeu de données (organisation par id,
    popularité, dates...), indépendantes du texte embeddé. La description
    nettoyée et tronquée sert à la lecture dans Grist."""
    return [
        {
            "id": row["id"],
            "url": row["url"],
            "organization_id": row["organization_id"],
            "quality_score": row["quality_score"],
            "reuses": row["metric.reuses"],
            "views": row["metric.views"],
            "created_at": row["created_at"],
            "last_modified": row["last_modified"],
            "harvest_modified_at": row["harvest.modified_at"],
            "archived_at": archived_at(row),
            "formats": row["resources_formats"],
            "tags": row["tags"],
            "description": clean_description(row["description"])[
                :GRIST_DESCRIPTION_MAX_CHARS
            ],
        }
        for row in rows
    ]


def organizations(rows: Iterable[dict]) -> list[dict]:
    """Organisations (id, nom) référencées par les jeux de données, à
    dédupliquer côté SQL (un id apparaît autant de fois que ses jeux)."""
    return [
        {"id": row["organization_id"], "name": row["organization"]}
        for row in rows
        if row["organization_id"]
    ]


def _badge_set(badges: str | None) -> set[str]:
    return {b.strip() for b in (badges or "").split(",") if b.strip()}


def organization_metadata(rows: Iterable[dict]) -> list[dict]:
    """Métadonnées du catalogue data.gouv des organisations (badges, SIREN,
    envergure), plus complet que ce qu'on tire des seules lignes dataset.

    `badges` est gardé tel quel (texte brut) en plus des booléens dérivés,
    pour ne rien perdre si data.gouv introduit un jour un nouveau badge."""
    result = []
    for row in rows:
        badges = _badge_set(row["badges"])
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "badges": row["badges"],
                "is_certified": BADGE_CERTIFIED in badges,
                "is_public_service": BADGE_PUBLIC_SERVICE in badges,
                "is_local_authority": BADGE_LOCAL_AUTHORITY in badges,
                "is_company": BADGE_COMPANY in badges,
                "is_association": BADGE_ASSOCIATION in badges,
                "business_number_id": row["business_number_id"],
                "siren": siren(row["business_number_id"]),
                "datasets_count": row["metric.datasets"],
                "followers": row["metric.followers"],
            }
        )
    return result


def embed_pending(store: DocumentStore, embedder: Embedder, batch_size: int) -> int:
    """Embedde par lots les documents sans embedding.

    Interruptible : une relance reprend là où le traitement s'est arrêté.
    Retourne le nombre de documents embeddés.
    """
    done = 0
    while batch := store.pending(limit=batch_size):
        vectors = embedder.encode([doc.text for doc in batch])
        if len(vectors) != len(batch):
            raise ValueError(
                f"{len(vectors)} embeddings reçus pour {len(batch)} documents"
            )
        store.save_embeddings({doc.id: vec for doc, vec in zip(batch, vectors)})
        done += len(batch)
        print(f"{done} documents embeddés")
    return done
