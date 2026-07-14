"""Integration adapters.

Production-shaped interfaces with mock implementations. External writes are
disabled by default; official adapters are placeholders until credentials and
contractual scope are confirmed. No scraping or browser automation — ever.
"""

from .base import AdapterCapabilities, AdapterStatus, BaseAdapter
from .email import ManualInboxAdapter, MockEmailAdapter, get_email_adapter
from .timocom import (
    DisabledTimocomAdapter,
    MockTimocomAdapter,
    OfficialTimocomAdapter,
    get_timocom_adapter,
)
from .transeu import (
    DisabledTransEuAdapter,
    MockTransEuAdapter,
    OfficialTransEuAdapter,
    get_transeu_adapter,
)

__all__ = [
    "AdapterCapabilities",
    "AdapterStatus",
    "BaseAdapter",
    "MockTimocomAdapter",
    "DisabledTimocomAdapter",
    "OfficialTimocomAdapter",
    "get_timocom_adapter",
    "MockTransEuAdapter",
    "DisabledTransEuAdapter",
    "OfficialTransEuAdapter",
    "get_transeu_adapter",
    "MockEmailAdapter",
    "ManualInboxAdapter",
    "get_email_adapter",
]
