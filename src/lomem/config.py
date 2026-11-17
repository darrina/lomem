import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = REPO_ROOT / "data" / "scenarios.json"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "lomem.db"


class Config:
    LOMEM_DATA_PATH = os.getenv("LOMEM_DATA_PATH", str(DEFAULT_DATA_PATH))
    LOMEM_DB_PATH = os.getenv("LOMEM_DB_PATH", str(DEFAULT_DB_PATH))
    LOMEM_DB_BACKEND = os.getenv("LOMEM_DB_BACKEND", "sqlite")
    LOMEM_DB_URL = os.getenv("LOMEM_DB_URL")
    LOMEM_MECHANISM_VERSION = os.getenv("LOMEM_MECHANISM_VERSION", "placeholder-v1")
