"""
Same idea as android-client's CanonicalJson.kt: sorted keys, compact
separators, so the same transaction always signs to the same bytes.
Being Python, this can just reuse json.dumps directly - no need to
hand-roll a serializer the way the Kotlin side did.
"""
import json
from typing import Any


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
