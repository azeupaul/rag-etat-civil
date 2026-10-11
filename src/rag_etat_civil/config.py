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


def _default_data_dir() -> Path:
    # <repository root>/data, starting from src/rag_etat_civil/config.py
    return Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings. The defaults are suitable for tests."""

    debug: bool = False
    max_question_length: int = 500
    data_dir: Path = field(default_factory=_default_data_dir)

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
        )
