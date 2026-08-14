from __future__ import annotations

from typing import Any

import httpx

from config import (
    BATCH_EXECUTE_URL,
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT,
)
from protocol import build_f_req, extract_rpc


class GooglePhotosClient:
    """
    Thin HTTP client for Google Photos batchexecute.

    Responsibilities:
      - send requests
      - manage HTTP session
      - return decoded RPC payloads

    This class intentionally knows nothing about album structure,
    media items, or parser indices.
    """

    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self._client = httpx.Client(
            http2=True,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers=headers or DEFAULT_HEADERS,
            cookies=cookies or {},
        )

    def close(self) -> None:
        self._client.close()

    def call_rpc(
        self,
        *,
        rpc_id: str,
        params: Any,
        query_params: dict[str, str] | None = None,
        form_fields: dict[str, str] | None = None,
    ) -> str:
        """
        Execute a batchexecute RPC.

        Parameters
        ----------
        rpc_id
            RPC identifier (e.g. frGlJf)

        params
            Python object that becomes the JSON payload inside f.req.

        query_params
            Optional URL query parameters.

            Example:
                rpcids
                source-path
                rt
                _reqid
                bl
                hl

            These are deliberately supplied by the caller because we
            have not yet fully reverse engineered which ones are
            mandatory.

        form_fields
            Additional POST form fields (e.g. "at") if required.
        """

        data = {
            "f.req": build_f_req(rpc_id, params),
        }

        if form_fields:
            data.update(form_fields)

        response = self._client.post(
            BATCH_EXECUTE_URL,
            params=query_params,
            data=data,
        )

        response.raise_for_status()

        return response.text

    def execute_rpc(
        self,
        *,
        rpc_id: str,
        params: Any,
        query_params: dict[str, str] | None = None,
        form_fields: dict[str, str] | None = None,
    ) -> Any:
        """
        Execute an RPC and return its decoded payload.
        """

        response = self.call_rpc(
            rpc_id=rpc_id,
            params=params,
            query_params=query_params,
            form_fields=form_fields,
        )

        return extract_rpc(response, rpc_id)

    def __enter__(self) -> "GooglePhotosClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()