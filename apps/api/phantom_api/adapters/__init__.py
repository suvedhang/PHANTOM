"""Pipeline adapters (mock and real PipeGen boundary)."""

from .base import (
    AdapterError,
    AdapterMetadata,
    AdapterStatus,
    NotConfiguredError,
    PipelineAdapter,
)
from .mock import MockPipelineAdapter
from .pipegen import EXPECTED_METADATA_FILENAME, PipeGenAdapter, PreflightCheck

__all__ = [
    "AdapterError",
    "AdapterMetadata",
    "AdapterStatus",
    "NotConfiguredError",
    "PipelineAdapter",
    "MockPipelineAdapter",
    "PipeGenAdapter",
    "PreflightCheck",
    "EXPECTED_METADATA_FILENAME",
]
