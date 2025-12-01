from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

DEFAULT_API_HOST = "https://gmgn.ai"


class GMGNError(Exception):
    """Raised when GMGN API returns an error or an unexpected payload."""


@dataclass
class RawTransaction:
    swap_transaction: str
    last_valid_block_height: int
    recent_blockhash: str
    prioritization_fee_lamports: Optional[int] = None


class GMGNSolanaClient:
    def __init__(self, api_key: str, api_host: str = DEFAULT_API_HOST, timeout: float = 15.0) -> None:
        self.api_key = api_key
        self.api_host = api_host.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_env(cls, env_var: str = "GMGN_API_KEY", api_host: str = DEFAULT_API_HOST) -> "GMGNSolanaClient":
        key = os.getenv(env_var)
        if not key:
            raise GMGNError(f"Missing API key in env var {env_var}")
        return cls(api_key=key, api_host=api_host)

    # ---------------- HTTP helpers ---------------- #
    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_host}{path}"
        headers = {"x-route-key": self.api_key, "accept": "application/json"}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise GMGNError(f"HTTP GET failed: {exc}") from exc
        if resp.status_code != 200:
            raise GMGNError(f"HTTP {resp.status_code}: {resp.text}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise GMGNError(f"Invalid JSON response: {exc}") from exc
        if data.get("code") != 0:
            raise GMGNError(f"GMGN error: code={data.get('code')} msg={data.get('msg')}")
        return data

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_host}{path}"
        headers = {
            "x-route-key": self.api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise GMGNError(f"HTTP POST failed: {exc}") from exc
        if resp.status_code != 200:
            raise GMGNError(f"HTTP {resp.status_code}: {resp.text}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise GMGNError(f"Invalid JSON response: {exc}") from exc
        if data.get("code") != 0:
            raise GMGNError(f"GMGN error: code={data.get('code')} msg={data.get('msg')}")
        return data

    # ---------------- Core API methods ---------------- #
    def get_swap_route(
        self,
        token_in_address: str,
        token_out_address: str,
        in_amount_lamports: int,
        from_address: str,
        slippage_pct: float,
        swap_mode: str = "ExactIn",
        fee: float | None = None,
        is_anti_mev: bool | None = None,
        partner: str | None = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "token_in_address": token_in_address,
            "token_out_address": token_out_address,
            "in_amount": str(int(in_amount_lamports)),
            "from_address": from_address,
            "slippage": slippage_pct,
            "swap_mode": swap_mode,
        }
        if fee is not None:
            params["fee"] = fee
        if is_anti_mev is not None:
            params["is_anti_mev"] = str(is_anti_mev).lower()
        if partner:
            params["partner"] = partner

        data = self._get("/defi/router/v1/sol/tx/get_swap_route", params).get("data") or {}
        raw_tx = (data.get("raw_tx") or {}) if isinstance(data, dict) else {}
        required = ["swapTransaction", "lastValidBlockHeight", "recentBlockhash"]
        if not all(k in raw_tx for k in required):
            raise GMGNError(f"Missing raw_tx fields: required {required}")

        return {
            "quote": data.get("quote") or {},
            "raw_tx": {
                "swapTransaction": raw_tx["swapTransaction"],
                "lastValidBlockHeight": raw_tx["lastValidBlockHeight"],
                "recentBlockhash": raw_tx["recentBlockhash"],
                "prioritizationFeeLamports": raw_tx.get("prioritizationFeeLamports"),
            },
        }

    def build_unsigned_transaction(self, raw_tx: Dict[str, Any]) -> RawTransaction:
        return RawTransaction(
            swap_transaction=raw_tx["swapTransaction"],
            last_valid_block_height=int(raw_tx["lastValidBlockHeight"]),
            recent_blockhash=str(raw_tx["recentBlockhash"]),
            prioritization_fee_lamports=raw_tx.get("prioritizationFeeLamports"),
        )

    def sign_transaction(self, swap_tx_base64: str, signer: Any) -> str:
        """
        Signing stub: decode base64 to bytes and sign with a Solana wallet.

        In Python, signing a VersionedTransaction may require a dedicated Solana SDK.
        If unavailable, perform this step with @solana/web3.js in JS:
            const tx = VersionedTransaction.deserialize(Buffer.from(swap_tx_base64, 'base64'));
            tx.sign([signer]);
            const signed = Buffer.from(tx.serialize()).toString('base64');
        """
        raise NotImplementedError("Signing not implemented in Python stub; use a Solana SDK or JS signer.")

    def submit_signed_transaction(self, signed_tx_base64: str, is_anti_mev: bool | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"chain": "sol", "signedTx": signed_tx_base64}
        if is_anti_mev is not None:
            payload["isAntiMev"] = is_anti_mev
        data = self._post("/txproxy/v1/send_transaction", payload).get("data") or {}
        if "hash" not in data:
            raise GMGNError("Missing hash in submit response.")
        return data

    def poll_transaction_status(
        self,
        hash: str,
        last_valid_block_height: int,
        poll_interval_sec: float = 1.0,
        timeout_sec: float = 60.0,
    ) -> Dict[str, Any]:
        start = time.time()
        params = {"hash": hash, "last_valid_height": last_valid_block_height}
        while True:
            data = self._get("/defi/router/v1/sol/tx/get_transaction_status", params).get("data") or {}
            success = bool(data.get("success"))
            expired = bool(data.get("expired"))
            failed = bool(data.get("failed"))
            if success:
                return {"state": "success", "raw": data}
            if expired and not success:
                return {"state": "expired", "raw": data}
            if failed and not success:
                return {"state": "failed", "raw": data}
            if (time.time() - start) > timeout_sec:
                return {"state": "timeout", "raw": data}
            time.sleep(poll_interval_sec)

    # ---------------- High-level helper ---------------- #
    def execute_swap(
        self,
        token_in_address: str,
        token_out_address: str,
        in_amount_lamports: int,
        from_address: str,
        slippage_pct: float,
        signer: Any,
        swap_mode: str = "ExactIn",
        fee: float | None = None,
        is_anti_mev: bool | None = None,
        partner: str | None = None,
    ) -> Dict[str, Any]:
        route = self.get_swap_route(
            token_in_address=token_in_address,
            token_out_address=token_out_address,
            in_amount_lamports=in_amount_lamports,
            from_address=from_address,
            slippage_pct=slippage_pct,
            swap_mode=swap_mode,
            fee=fee,
            is_anti_mev=is_anti_mev,
            partner=partner,
        )
        raw_tx = self.build_unsigned_transaction(route["raw_tx"])
        signed_b64 = self.sign_transaction(raw_tx.swap_transaction, signer)
        submit_resp = self.submit_signed_transaction(signed_b64, is_anti_mev=is_anti_mev)
        tx_hash = submit_resp.get("hash")
        status = self.poll_transaction_status(
            hash=tx_hash,
            last_valid_block_height=raw_tx.last_valid_block_height,
        )
        return {
            "request": {
                "token_in_address": token_in_address,
                "token_out_address": token_out_address,
                "in_amount_lamports": in_amount_lamports,
                "from_address": from_address,
                "slippage_pct": slippage_pct,
                "swap_mode": swap_mode,
                "fee": fee,
                "is_anti_mev": is_anti_mev,
                "partner": partner,
            },
            "quote": route.get("quote"),
            "tx_hash": tx_hash,
            "submit_response": submit_resp,
            "status": status,
        }
