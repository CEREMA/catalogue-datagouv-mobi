import pytest

from catalogue_mobi.constants import (
    BGE_QUERY_INSTRUCTION,
    GRIST_DESCRIPTION_MAX_CHARS,
)
from catalogue_mobi.pipeline import (
    dataset_documents,
    dataset_metadata,
    embed_pending,
    ontology_documents,
    organization_metadata,
    organizations,
)
from catalogue_mobi.ports import Document
from tests.fakes import FakeEmbedder, InMemoryDocumentStore


def _docs(n):
    return [Document(id=f"d{i}", label=f"doc {i}", text="x" * i) for i in range(n)]


@pytest.mark.parametrize(
    "n_docs, already_embedded, batch_size, expected_batch_sizes",
    [
        (0, 0, 2, []),
        (5, 0, 2, [2, 2, 1]),
        (4, 0, 4, [4]),
        (5, 3, 2, [2]),
        (3, 3, 2, []),
    ],
    ids=["vide", "plusieurs_lots", "lot_exact", "reprise", "deja_fait"],
)
def test_embed_pending(n_docs, already_embedded, batch_size, expected_batch_sizes):
    docs = _docs(n_docs)
    store = InMemoryDocumentStore()
    store.sync(docs)
    store.save_embeddings({d.id: [0.0] for d in docs[:already_embedded]})
    embedder = FakeEmbedder()

    count = embed_pending(store, embedder, batch_size=batch_size)

    assert [len(b) for b in embedder.batches] == expected_batch_sizes
    assert count == sum(expected_batch_sizes)
    assert store.pending(limit=n_docs + 1) == []


def test_embed_pending_stores_the_vector_of_each_document():
    store = InMemoryDocumentStore()
    store.sync([Document("a", "A", "xx"), Document("b", "B", "xxxxx")])

    embed_pending(store, FakeEmbedder(), batch_size=10)

    assert store.embeddings == {"a": [2.0], "b": [5.0]}


def test_embed_pending_fails_if_embedder_returns_wrong_count():
    class BrokenEmbedder:
        def encode(self, texts):
            return []

    store = InMemoryDocumentStore()
    store.sync(_docs(2))

    with pytest.raises(ValueError):
        embed_pending(store, BrokenEmbedder(), batch_size=10)


def test_ontology_documents():
    rows = [
        {
            "theme": "elections",
            "theme_description": "Organisation et résultats des scrutins",
            "sous_theme": "procurations",
            "description": "Vote par procuration.",
            "mots_cles_indicatifs": "procuration",
        }
    ]

    assert ontology_documents(rows) == [
        Document(
            id="elections/procurations",
            label="procurations",
            text=BGE_QUERY_INSTRUCTION + "Organisation et résultats des scrutins. "
            "Vote par procuration. Mots-clés : procuration",
        )
    ]


@pytest.mark.parametrize(
    "with_archived, expected_ids",
    [(False, ["a", "c"]), (True, ["a", "b", "c"])],
    ids=["sans_archives", "avec_archives"],
)
def test_dataset_documents_archived(with_archived, expected_ids):
    def row(id, archived):
        return {
            "id": id,
            "title": f"Titre {id}",
            "description": "",
            "tags": "",
            "archived": archived,
        }

    rows = [row("a", "False"), row("b", "2024-03-21T12:26:15.234000"), row("c", "")]

    assert dataset_documents(rows, with_archived=with_archived) == [
        Document(id=i, label=f"Titre {i}", text=f"Titre {i}")
        for i in expected_ids
    ]


def test_dataset_metadata():
    def row(id, archived):
        return {
            "id": id,
            "url": f"https://www.data.gouv.fr/datasets/{id}",
            "organization": "Cerema",
            "organization_id": "534fff",
            "quality_score": "0.78",
            "metric.reuses": "3",
            "metric.views": "42",
            "created_at": "2020-01-01T00:00:00",
            "last_modified": "2026-07-28T00:00:00",
            "harvest.modified_at": "",
            "archived": archived,
            "resources_formats": "csv,json",
            "tags": "velo,comptage",
            "description": "**Comptages** vélo",
        }

    rows = [row("a", "False"), row("b", "2024-03-21T12:26:15.234000")]

    common = {
        "organization_id": "534fff",
        "quality_score": "0.78",
        "reuses": "3",
        "views": "42",
        "created_at": "2020-01-01T00:00:00",
        "last_modified": "2026-07-28T00:00:00",
        "harvest_modified_at": "",
        "formats": "csv,json",
        "tags": "velo,comptage",
        "description": "Comptages vélo",
    }
    assert dataset_metadata(rows) == [
        {
            "id": "a",
            "url": "https://www.data.gouv.fr/datasets/a",
            "archived_at": None,
            **common,
        },
        {
            "id": "b",
            "url": "https://www.data.gouv.fr/datasets/b",
            "archived_at": "2024-03-21T12:26:15.234000",
            **common,
        },
    ]


def test_dataset_metadata_truncates_description():
    row = {
        k: ""
        for k in [
            "id", "url", "organization_id", "quality_score", "metric.reuses",
            "metric.views", "created_at", "last_modified", "harvest.modified_at",
            "archived",
            "resources_formats", "tags",
        ]
    }
    row["description"] = "x" * (GRIST_DESCRIPTION_MAX_CHARS + 10)

    assert len(dataset_metadata([row])[0]["description"]) == GRIST_DESCRIPTION_MAX_CHARS


def test_organizations_excludes_rows_without_organization_id():
    rows = [
        {"organization_id": "534fff", "organization": "Cerema"},
        {"organization_id": "534fff", "organization": "Cerema"},
        {"organization_id": "", "organization": ""},
    ]

    assert organizations(rows) == [
        {"id": "534fff", "name": "Cerema"},
        {"id": "534fff", "name": "Cerema"},
    ]


def test_organization_metadata():
    rows = [
        {
            "id": "534fff",
            "name": "Cerema",
            "badges": "public-service,certified",
            "business_number_id": "130025265",
            "metric.datasets": "12",
            "metric.followers": "7",
        }
    ]

    assert organization_metadata(rows) == [
        {
            "id": "534fff",
            "name": "Cerema",
            "badges": "public-service,certified",
            "is_certified": True,
            "is_public_service": True,
            "is_local_authority": False,
            "is_company": False,
            "is_association": False,
            "business_number_id": "130025265",
            "siren": "130025265",
            "datasets_count": "12",
            "followers": "7",
        }
    ]


def test_sync_resets_embedding_when_text_changes():
    store = InMemoryDocumentStore()
    store.sync([Document("a", "A", "v1"), Document("b", "B", "v1")])
    embed_pending(store, FakeEmbedder(), batch_size=10)

    store.sync([Document("a", "A", "v2"), Document("b", "B bis", "v1")])

    assert [d.id for d in store.pending(limit=10)] == ["a"]


def test_ontology_documents_uses_human_label_when_present():
    row = {
        "theme": "velo",
        "theme_description": "Vélo",
        "sous_theme": "stationnement_velo",
        "sous_theme_label": "Stationnement vélo",
        "description": "Stationnement vélo : arceaux",
        "mots_cles_indicatifs": "arceau",
    }

    [doc] = ontology_documents([row])

    assert (doc.id, doc.label) == ("velo/stationnement_velo", "Stationnement vélo")
