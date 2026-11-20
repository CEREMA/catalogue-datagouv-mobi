"""Pipeline : catalogue data.gouv.fr -> embeddings -> rattachement à
l'ontologie (mots-clés, baseline, puis embeddings) -> enrichissement des
producteurs -> tables pour Grist.

Chaque étape est une sous-commande, rejouable et idempotente ; `update`
les enchaîne toutes (usage cron).
"""

import argparse

import polars as pl
from dotenv import load_dotenv

from catalogue_mobi.constants import (
    DATASET_TABLE,
    DEFAULT_DB_BATCH_SIZE,
    DEFAULT_ENCODE_BATCH_SIZE,
    DEFAULT_K,
    DEFAULT_MAX_SEQ_LENGTH,
    DEFAULT_MODEL,
    GRIST_DIR,
    GRIST_EXPORTS,
    ONTOLOGY_TABLE,
)
from catalogue_mobi.infra_catalog import fetch_catalog
from catalogue_mobi.infra_csv import (
    read_datasets,
    read_ontology,
    read_organizations,
    read_resource_stats,
)
from catalogue_mobi.infra_postgres import (
    PostgresDatasetMatcher,
    PostgresDocumentStore,
    connect,
    dataset_texts,
    export_view,
    init_db,
    legal_categories,
    missing_legal_category_labels,
    missing_sirens,
    save_classifications,
    save_keyword_matches,
    save_legal_category_labels,
    save_sirens,
    update_dataset_metadata,
    update_organization_metadata,
    update_organizations,
    update_resource_stats,
)
from catalogue_mobi.infra_sirene import lookup_legal_categories, lookup_sirens
from catalogue_mobi.mots_cles import KeywordIndex
from catalogue_mobi.pipeline import (
    dataset_documents,
    dataset_metadata,
    embed_pending,
    ontology_documents,
    ontology_id,
    organization_metadata,
    organizations,
)
from catalogue_mobi.producteurs import classification


def fetch(args):
    fetch_catalog()


def embed(args, conn):
    ontology_store = PostgresDocumentStore(conn, ONTOLOGY_TABLE)
    dataset_store = PostgresDocumentStore(conn, DATASET_TABLE)

    print("Chargement de l'ontologie...")
    ontology = ontology_documents(read_ontology())
    ontology_store.sync(ontology)
    ontology_store.delete_except({doc.id for doc in ontology})

    print("Chargement des jeux de données...")
    rows = read_datasets()
    if args.limit:
        rows = rows[: args.limit]
    dataset_store.sync(dataset_documents(rows, with_archived=args.with_archived))
    if not args.limit:
        # Supprimés de data.gouv. Les jeux archivés depuis restent en base
        # (avec leur date d'archivage) : utile pour un jeu déjà validé.
        dataset_store.delete_except({row["id"] for row in rows})

    if not args.skip_metadata:
        print("Mise à jour des organisations...")
        update_organizations(conn, organizations(rows))
        update_organization_metadata(conn, organization_metadata(read_organizations()))
        print("Mise à jour des métadonnées des jeux...")
        print(f"{update_dataset_metadata(conn, dataset_metadata(rows))} jeux mis à jour")
        print("Lecture des ressources (fraîcheur des données, schémas)...")
        print(f"{update_resource_stats(conn, read_resource_stats())} jeux mis à jour")

    from catalogue_mobi.infra_embedder import SentenceTransformerEmbedder

    embedder = SentenceTransformerEmbedder(
        args.model,
        max_seq_length=args.max_seq_length,
        batch_size=args.encode_batch_size,
    )
    print("Embeddings de l'ontologie...")
    embed_pending(ontology_store, embedder, batch_size=args.db_batch_size)
    print("Embeddings des jeux de données...")
    embed_pending(dataset_store, embedder, batch_size=args.db_batch_size)


def attach(args, conn):
    print("Rattachement par mots-clés (baseline)...")
    index = KeywordIndex(read_ontology())
    matches = [m for id, text in dataset_texts(conn) for m in index.matches(id, text)]
    print(f"{save_keyword_matches(conn, matches)} rattachements enregistrés")

    print(f"Rattachement par embeddings (k={args.k})...")
    count = PostgresDatasetMatcher(conn).attach(k=args.k)
    print(f"{count} rattachements enregistrés")


def enrich(args, conn):
    sirens = missing_sirens(conn)
    print(f"{len(sirens)} SIREN à interroger")
    if sirens:
        save_sirens(conn, lookup_sirens(sirens))
    save_classifications(
        conn,
        [{"siren": s, **classification(nj)} for s, nj in legal_categories(conn)],
    )
    codes = missing_legal_category_labels(conn)
    print(f"{len(codes)} libellés de catégorie juridique à interroger")
    if codes:
        save_legal_category_labels(conn, lookup_legal_categories(codes))


def export(args, conn):
    GRIST_DIR.mkdir(parents=True, exist_ok=True)
    ontology = pl.DataFrame(read_ontology())
    ontology = ontology.select(
        pl.Series("id", [ontology_id(r) for r in ontology.to_dicts()]), pl.all()
    )
    ontology.write_csv(GRIST_DIR / "ontologie.csv")
    print(f"ontologie.csv : {ontology.height} lignes")
    for view, filename in GRIST_EXPORTS.items():
        if view == "grist_jeux" and getattr(args, "short", False):
            view = "grist_jeux_court"
        count = export_view(conn, view, GRIST_DIR / filename)
        print(f"{filename} : {count} lignes")


def update(args, conn):
    fetch(args)
    embed(args, conn)
    attach(args, conn)
    enrich(args, conn)
    export(args, conn)


def reset_db(args, conn):
    init_db(conn, reset=True)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name, func, help, needs_db=True):
        sub = commands.add_parser(name, help=help)
        sub.set_defaults(func=func, needs_db=needs_db)
        return sub

    def embed_options(sub):
        sub.add_argument("--limit", type=int, help="Ne charge que N jeux (essai)")
        sub.add_argument(
            "--with-archived",
            action="store_true",
            help="Embedde aussi les jeux archivés (~56k de plus)",
        )
        sub.add_argument(
            "--skip-metadata",
            action="store_true",
            help="Ne met pas à jour organisations, métadonnées et ressources",
        )
        sub.add_argument("--model", default=DEFAULT_MODEL)
        sub.add_argument(
            "--max-seq-length", type=int, default=DEFAULT_MAX_SEQ_LENGTH
        )
        sub.add_argument(
            "--encode-batch-size",
            type=int,
            default=DEFAULT_ENCODE_BATCH_SIZE,
            help="Lot envoyé au modèle",
        )
        sub.add_argument(
            "--db-batch-size",
            type=int,
            default=DEFAULT_DB_BATCH_SIZE,
            help="Lot écrit en base (et point de reprise)",
        )

    def attach_options(sub):
        sub.add_argument(
            "--k", type=int, default=DEFAULT_K, help="Sous-thèmes retenus par jeu"
        )

    command("fetch", fetch, "Télécharge les exports data.gouv.fr", needs_db=False)
    embed_options(command("embed", embed, "Charge le catalogue et calcule les embeddings"))
    attach_options(
        command("attach", attach, "Rattache les jeux à l'ontologie (mots-clés, embeddings)")
    )
    command("enrich", enrich, "Catégorie juridique des producteurs (SIRENE)")
    command("export", export, "Écrit les tables pour Grist dans data/grist/").add_argument(
        "--short",
        action="store_true",
        help="jeux.csv allégé pour l'import manuel (description à 50 caractères, sans url)",
    )
    command("reset-db", reset_db, "Supprime et recrée les tables")
    sub = command("update", update, "Enchaîne toutes les étapes (cron)")
    embed_options(sub)
    attach_options(sub)
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    if not args.needs_db:
        args.func(args)
        return
    conn = connect()
    try:
        init_db(conn)
        args.func(args, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
