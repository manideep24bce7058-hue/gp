from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProtocolError(Exception):
    pass


def decode_wrbs(text: str) -> list[tuple[str, Any]]:
    prefix = ")]}'\n"
    if text.startswith(prefix):
        text = text[len(prefix):]

    results = []
    decoder = json.JSONDecoder()
    idx = 0

    while idx < len(text):
        brace_idx = text.find('[', idx)
        curly_idx = text.find('{', idx)

        if brace_idx == -1 and curly_idx == -1:
            break
        elif brace_idx == -1:
            start_idx = curly_idx
        elif curly_idx == -1:
            start_idx = brace_idx
        else:
            start_idx = min(brace_idx, curly_idx)

        try:
            data, end_idx = decoder.raw_decode(text, start_idx)
            _extract_envelopes(data, results)
            idx = end_idx
        except json.JSONDecodeError:
            idx = start_idx + 1

    return results

def build_frGlJf_payload(album_id: str, cursor: str, share_key: str | None = None) -> str:
    inner_arr = [album_id, cursor, None, share_key]
    inner_str = json.dumps(inner_arr, separators=(',', ':'))
    rpc = ["frGlJf", inner_str, None, "1"]
    return json.dumps([[rpc]], separators=(',', ':'))

def build_wQ6iqd_payload(album_id: str, cursor: str, share_key: str | None = None) -> str:
    """Builds the exact nested array pagination request expected by Google."""
    inner_arr = [[album_id], cursor]
    inner_str = json.dumps(inner_arr, separators=(',', ':'))
    rpc = ["wQ6iqd", inner_str, None, "generic"]
    return json.dumps([[rpc]], separators=(',', ':'))

def _extract_envelopes(data: Any, results: list[tuple[str, Any]]) -> None:
    if not isinstance(data, list):
        return

    def search_list(lst: list) -> None:
        for item in lst:
            if isinstance(item, list):
                if len(item) >= 3 and item[0] == "wrb.fr":
                    rpc_id = item[1]
                    raw_payload = item[2]
                    try:
                        payload = json.loads(raw_payload)
                        results.append((rpc_id, payload))
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif len(item) > 0 and isinstance(item[0], list):
                    search_list(item)

    search_list(data)


def build_fDcn4b_batch(media_ids: list[str], share_key: str) -> str:
    rpc_list = []
    
    for i, media_id in enumerate(media_ids):
        inner_arr = [media_id, None, share_key, None, None, [2]]
        inner_str = json.dumps(inner_arr, separators=(',', ':'))
        rpc_list.append(["fDcn4b", inner_str, None, str(i + 1)])
    
    return json.dumps([rpc_list], separators=(',', ':'))