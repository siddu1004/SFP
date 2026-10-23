"""Compatibility imports for the public neutral download representation registry.

The registry lives below the application layer so backend preparation and adapter
filename/Content-Type policy use the same representation definitions.
"""

from ..downloads import (
    DOWNLOAD_FORMAT_NAMES as DOWNLOAD_FORMAT_NAMES,
)
from ..downloads import (
    DOWNLOAD_REGISTRY as DOWNLOAD_REGISTRY,
)
from ..downloads import (
    DOWNLOAD_SPECS_BY_NAME as DOWNLOAD_SPECS_BY_NAME,
)
from ..downloads import (
    EXTENSION_MIME_TYPES as EXTENSION_MIME_TYPES,
)
from ..downloads import (
    FORMAT_EXTENSIONS as FORMAT_EXTENSIONS,
)
from ..downloads import (
    DownloadFormatSpec as DownloadFormatSpec,
)
from ..downloads import (
    DownloadRegistryEntry as DownloadRegistryEntry,
)
from ..downloads import (
    DownloadTypeSpec as DownloadTypeSpec,
)

__all__ = [
    "DOWNLOAD_FORMAT_NAMES",
    "DOWNLOAD_REGISTRY",
    "DOWNLOAD_SPECS_BY_NAME",
    "EXTENSION_MIME_TYPES",
    "FORMAT_EXTENSIONS",
    "DownloadFormatSpec",
    "DownloadRegistryEntry",
    "DownloadTypeSpec",
]
