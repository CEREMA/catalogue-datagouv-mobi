from pathlib import Path

import polars as pl

from catalogue_mobi.constants import (
    DATASET_COLUMNS,
    DATASET_METADATA_COLUMNS,
    DATASET_PATH,
    ONTOLOGY_PATH,
    ORGANIZATION_COLUMNS,
    ORGANIZATION_PATH,
    RESOURCE_ANALYSIS_MODIFIED,
    RESOURCE_DATASET_ID,
    RESOURCE_EXTRAS,
    RESOURCE_HARVEST_MODIFIED,
    RESOURCE_MODIFIED,
    RESOURCE_PATH,
    RESOURCE_SCHEMA,
)


def read_ontology(path: Path = ONTOLOGY_PATH) -> list[dict]:
    return pl.read_csv(path, infer_schema=False).to_dicts()


def read_datasets(path: Path = DATASET_PATH) -> list[dict]:
    df = pl.read_csv(
        path,
        separator=";",
        columns=DATASET_COLUMNS + DATASET_METADATA_COLUMNS,
        infer_schema=False,
    )
    return df.to_dicts()


def read_organizations(path: Path = ORGANIZATION_PATH) -> list[dict]:
    df = pl.read_csv(
        path,
        separator=";",
        columns=ORGANIZATION_COLUMNS,
        infer_schema=False,
    )
    return df.to_dicts()


def _datetime(expr: pl.Expr) -> pl.Expr:
    """Date ISO (avec ou sans fraction de seconde / fuseau) -> datetime."""
    return expr.str.slice(0, 19).str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False)


def read_resource_stats(path: Path = RESOURCE_PATH) -> list[dict]:
    """Par jeu de données, à partir de l'export des ressources (~1 Go, lu en
    flux sur quelques colonnes) :

    - `last_update` : la plus récente des dates de ses ressources. Date d'une
      ressource comme dans udata (`Resource.last_modified`) : date du
      moissonnage, sinon date détectée par l'analyse du fichier distant
      (en-tête Last-Modified), sinon dernière modification sur data.gouv ;
    - `schemas` : schémas schema.data.gouv.fr déclarés par ses ressources
      (ex. etalab/schema-irve-statique), triés, séparés par une virgule.
    """
    df = (
        pl.scan_csv(path, separator=";", infer_schema=False)
        .select(
            pl.col(RESOURCE_DATASET_ID).alias("id"),
            pl.coalesce(
                _datetime(pl.col(RESOURCE_HARVEST_MODIFIED)),
                _datetime(
                    pl.col(RESOURCE_EXTRAS).str.json_path_match(
                        RESOURCE_ANALYSIS_MODIFIED
                    )
                ),
                _datetime(pl.col(RESOURCE_MODIFIED)),
            ).alias("modified"),
            pl.col(RESOURCE_SCHEMA).replace("", None).alias("schema"),
        )
        .group_by("id")
        .agg(
            pl.col("modified").max().dt.strftime("%Y-%m-%dT%H:%M:%S").alias(
                "last_update"
            ),
            pl.col("schema").drop_nulls().unique().sort().str.join(",").alias(
                "schemas"
            ),
        )
        .with_columns(pl.col("schemas").replace("", None))
        .collect()
    )
    return df.to_dicts()
