from typing import Sequence

from catalogue_mobi.constants import DEFAULT_MAX_SEQ_LENGTH, DEFAULT_MODEL
from catalogue_mobi.ports import Vector


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH,
        batch_size: int = 32,
    ):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers n'est pas installé : make install"
            ) from e

        self._model = SentenceTransformer(model_name)
        self._model.max_seq_length = max_seq_length
        if self._model.device.type == "cuda":
            self._model.half()
        self._batch_size = batch_size
        print(f"Modèle {model_name} chargé sur {self._model.device}")

    def encode(self, texts: list[str]) -> Sequence[Vector]:
        return self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
