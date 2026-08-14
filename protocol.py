from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProtocolError(Exception):
    pass


def decode_wrbs(text: str) -> list[tuple[str, Any]]:
    """
    Strips the XSSI prefix from Google batchexecute responses
    and robustly decodes the nested JSON envelopes using raw_decode,
    ignoring arbitrary chunk length prefixes and newline normalization issues.
    """
    prefix = ")]}'\n"
    if text.startswith(prefix):
        text = text[len(prefix):]

    results = []
    decoder = json.JSONDecoder()
    idx = 0

    while idx < len(text):
        # Find the next possible start of a JSON array or object
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
            # raw_decode extracts exactly one valid JSON object and returns the end index
            data, end_idx = decoder.raw_decode(text, start_idx)
            _extract_envelopes(data, results)
            idx = end_idx
        except json.JSONDecodeError:
            # If parsing fails, advance by 1 character to search for the next valid block
            idx = start_idx + 1

    return results


def _extract_envelopes(data: Any, results: list[tuple[str, Any]]) -> None:
    """
    Recursively scans the decoded JSON structure for Google's ["wrb.fr", rpc_id, payload] envelopes.
    """
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
    """
    Builds a batchexecute f.req payload for multiple fDcn4b requests.
    """
    rpc_list = []
    
    for i, media_id in enumerate(media_ids):
        inner_arr = [media_id, None, share_key, None, None, [2]]
        inner_str = json.dumps(inner_arr, separators=(',', ':'))
        rpc_list.append(["fDcn4b", inner_str, None, str(i + 1)])
    
    return json.dumps([rpc_list], separators=(',', ':'))