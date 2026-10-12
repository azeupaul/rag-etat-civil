"""Application settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_TRUE_VALUES = {"1", "true", "yes", "on"}

# Page of the official scanned PDF, on the website of the Presidency of the Republic.
OFFICIAL_SOURCE_URL = (
    "https://prc.cm/fr/multimedia/documents/10257-loi-n-2024-016-du-23-12-2024-web"
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    return _REPO_ROOT / "data"


def _default_model_cache_dir() -> Path:
    return _REPO_ROOT / ".cache" / "models"


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings. The defaults are suitable for tests."""

    debug: bool = False
    max_question_length: int = 500
    data_dir: Path = field(default_factory=_default_data_dir)
    embedder: str = "fastembed"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_cache_dir: Path = field(default_factory=_default_model_cache_dir)
    retrieval_candidates: int = 20  # passages taken from each search before merging
    retrieval_top_k: int = 5  # passages given to the answer step

    # Below this cosine similarity, a question that names no article is refused without calling
    # the language model. 0 disables the check until the evaluation has chosen a value.
    min_similarity: float = 0.0
    llm_provider: str = "gemini"  # the provider used for the answer step
    llm_timeout_seconds: float = 30.0  # timeout for the LLM request
    gemini_model: str = "gemini-3.5-flash-lite"  # the model used for the answer step
    gemini_api_key: str = field(default="", repr=False)  # a secret: never shown in logs

    @property
    def index_dir(self) -> Path:
        """Where the vector index is written (generated, not committed)."""
        return self.data_dir / "index"

    @classmethod
    def from_env(cls) -> Settings:
        """Build the settings from the environment (and from a .env file if present)."""
        load_dotenv()
        defaults = cls()
        return cls(
            debug=os.environ.get("APP_DEBUG", "").lower() in _TRUE_VALUES,
            max_question_length=int(
                os.environ.get("MAX_QUESTION_LENGTH", defaults.max_question_length)
            ),
            data_dir=Path(os.environ.get("DATA_DIR", defaults.data_dir)),
            embedder=os.environ.get("EMBEDDER", defaults.embedder),
            embedding_model=os.environ.get("EMBEDDING_MODEL", defaults.embedding_model),
            embedding_cache_dir=Path(
                os.environ.get("EMBEDDING_CACHE_DIR", defaults.embedding_cache_dir)
            ),
            retrieval_candidates=int(
                os.environ.get("RETRIEVAL_CANDIDATES", defaults.retrieval_candidates)
            ),
            retrieval_top_k=int(os.environ.get("RETRIEVAL_TOP_K", defaults.retrieval_top_k)),
            min_similarity=float(os.environ.get("MIN_SIMILARITY", defaults.min_similarity)),
            llm_provider=os.environ.get("LLM_PROVIDER", defaults.llm_provider),
            llm_timeout_seconds=float(
                os.environ.get("LLM_TIMEOUT_SECONDS", defaults.llm_timeout_seconds)
            ),
            gemini_model=os.environ.get("GEMINI_MODEL", defaults.gemini_model),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", defaults.gemini_api_key),
        )
