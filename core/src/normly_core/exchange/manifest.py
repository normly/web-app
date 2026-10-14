# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

#: Version of the dump layout, independent of the Alembic revision. Bump when
#: manifest or Parquet column semantics change incompatibly.
EXCHANGE_SCHEMA_VERSION = 1
EMBEDDING_DIMENSION = 1024


@dataclass(frozen=True)
class FileEntry:
    path: str
    sha256: str
    rows: int


@dataclass(frozen=True)
class DeliveryEntry:
    delivery_id: str
    publisher: str
    legal_basis_category: str


@dataclass(frozen=True)
class Manifest:
    exchange_schema_version: int
    dump_version: str
    created_at: str
    embedding_models: list[str]
    embedding_model_revision: str
    embedding_dimension: int
    deliveries: list[DeliveryEntry]
    tables: dict[str, list[FileEntry]]

    def to_bytes(self) -> bytes:
        return (json.dumps(asdict(self), sort_keys=True, indent=2) + "\n").encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "Manifest":
        raw = json.loads(data.decode("utf-8"))
        return cls(
            exchange_schema_version=raw["exchange_schema_version"],
            dump_version=raw["dump_version"],
            created_at=raw["created_at"],
            embedding_models=list(raw["embedding_models"]),
            embedding_model_revision=raw["embedding_model_revision"],
            embedding_dimension=raw["embedding_dimension"],
            deliveries=[DeliveryEntry(**d) for d in raw["deliveries"]],
            tables={
                name: [FileEntry(**f) for f in files]
                for name, files in raw["tables"].items()
            },
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
