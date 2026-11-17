"""Interfaces vers les dépendances non pures (modèle, base de données)."""

from dataclasses import dataclass
from typing import Protocol, Sequence

Vector = Sequence[float]


@dataclass(frozen=True)
class Document:
    """Un élément à embedder : sous-thème de l'ontologie ou jeu de données."""

    id: str
    label: str
    text: str


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> Sequence[Vector]:
        """Un vecteur par texte, dans le même ordre."""
        ...


class DocumentStore(Protocol):
    def sync(self, documents: list[Document]) -> None:
        """Ajoute les nouveaux documents et met à jour les modifiés : un texte
        changé perd son embedding, qui sera recalculé."""
        ...

    def delete_except(self, ids: set[str]) -> int:
        """Supprime les documents dont l'id n'est pas dans `ids`."""
        ...

    def pending(self, limit: int) -> list[Document]:
        """Au plus `limit` documents sans embedding."""
        ...

    def save_embeddings(self, embeddings: dict[str, Vector]) -> None:
        """Enregistre les embeddings, indexés par id de document."""
        ...


class DatasetMatcher(Protocol):
    def attach(self, k: int) -> int:
        """(Re)calcule, pour chaque jeu de données embeddé, ses k sous-thèmes
        les plus proches (sans seuil). Retourne le nombre de rattachements."""
        ...
