import logging

from langchain_huggingface import HuggingFaceEmbeddings

from src.modules.preprocessor.schemas import ProcessedChunk

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE = 64


class EmbedderService:
    def __init__(self) -> None:
        self._embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    async def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)

    async def embed(self, chunks: list[ProcessedChunk]) -> list[list[float]]:
        texts = [chunk.content for chunk in chunks]

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            vectors = self._embeddings.embed_documents(batch)
            all_vectors.extend(vectors)
            logger.info(
                "Embedded batch %d/%d (%d texts)",
                i // BATCH_SIZE + 1,
                (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE,
                len(batch),
            )

        logger.info("Embedding complete: %d vectors", len(all_vectors))
        return all_vectors


embedder_service = EmbedderService()
