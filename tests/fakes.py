from catalogue_mobi.ports import Document


class FakeEmbedder:
    """Encode un texte en [longueur du texte] et mémorise les lots reçus."""

    def __init__(self):
        self.batches: list[list[str]] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [[float(len(t))] for t in texts]


class InMemoryDocumentStore:
    def __init__(self):
        self.documents: dict[str, Document] = {}
        self.embeddings: dict[str, list[float]] = {}

    def sync(self, documents: list[Document]) -> None:
        for doc in documents:
            old = self.documents.get(doc.id)
            if old is not None and old.text != doc.text:
                self.embeddings.pop(doc.id, None)
            self.documents[doc.id] = doc

    def delete_except(self, ids: set[str]) -> int:
        removed = [i for i in self.documents if i not in ids]
        for i in removed:
            del self.documents[i]
            self.embeddings.pop(i, None)
        return len(removed)

    def pending(self, limit: int) -> list[Document]:
        todo = [d for d in self.documents.values() if d.id not in self.embeddings]
        return todo[:limit]

    def save_embeddings(self, embeddings: dict[str, list[float]]) -> None:
        self.embeddings.update(embeddings)
