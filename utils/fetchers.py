import os
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def lookup_4byte(method_id: str, timeout=6) -> str:
    """Coba tebak nama fungsi dari 4byte.directory; fallback ke method_id."""
    if not method_id:
        return ""
    try:
        r = requests.get(
            "https://www.4byte.directory/api/v1/signatures/",
            params={"hex_signature": method_id},
            timeout=timeout,
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                # pilih entri terbaru
                results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                sig = results[0].get("text_signature", "")
                return (sig.split("(")[0] if sig else method_id)
    except Exception:
        pass
    return method_id

# ===== Helper API =====
def _etherscan_get(base, params, timeout=8):
    """Call Etherscan-compatible API endpoint."""
    try:
        r = requests.get(base, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if "error" in data and data["error"]:
            raise RuntimeError(str(data["error"]))
        return data
    except Exception as e:
        raise RuntimeError(f"Etherscan API error: {e}")

def _hex_to_int(x):
    """Convert hex string to integer."""
    try:
        return int(x, 16)
    except:
        return 0

# ===== Kurs ETH → IDR =====
def fetch_eth_idr_rate(timeout=6):
    """Ambil kurs ETH → IDR dari CoinGecko."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "ethereum", "vs_currencies": "idr"},
            timeout=timeout
        )
        r.raise_for_status()
        return float(r.json()["ethereum"]["idr"])
    except:
        return 0.0

# ===== Ambil transaksi dari Sepolia / jaringan lain =====
import time

def _take_result_or_fail(resp: dict, label: str):
    """Ambil field 'result' dari resp. Validasi harus dict."""
    if not isinstance(resp, dict):
        raise RuntimeError(f"{label}: response invalid type {type(resp)}")
    res = resp.get("result", None)
    # Etherscan kadang kirim string jika rate limit / error di proxy
    if res is None or isinstance(res, str):
        # tampilkan sedikit konteks agar mudah debug di UI
        msg = res if isinstance(res, str) else resp
        raise RuntimeError(f"{label}: invalid result -> {msg}")
    return res

def fetch_tx_raw_any(
    tx_hash: str,
    api_key: str,
    network: str = "sepolia",
    eth_idr_rate: float | None = None
) -> dict:
    network_key = (network or "sepolia").lower().strip()
    base_map = {
        "sepolia": "https://api-sepolia.etherscan.io/api",
        "mainnet": "https://api.etherscan.io/api",
    }
    if network_key not in base_map:
        raise ValueError(f"Network belum didukung: {network}")
    if not api_key:
        raise RuntimeError("ETHERSCAN_API_KEY belum diset di secrets/env")

    base = base_map[network_key]

    # --- helper retry ringan untuk proxy endpoints ---
    def call_proxy(action, params):
        backoff = 0.35
        last_err = None
        for _ in range(3):
            try:
                resp = _etherscan_get(base, {"module": "proxy", "action": action, "apikey": api_key, **params})
                return resp
            except Exception as e:
                last_err = e
                time.sleep(backoff)
                backoff *= 1.7
        raise last_err

    # --- TX data ---
    tx_resp = call_proxy("eth_getTransactionByHash", {"txhash": tx_hash.strip()})
    tx = _take_result_or_fail(tx_resp, "tx")

    # --- Receipt ---
    rcpt_resp = call_proxy("eth_getTransactionReceipt", {"txhash": tx_hash.strip()})
    rcpt = _take_result_or_fail(rcpt_resp, "receipt")

    # --- Block (untuk timestamp) ---
    blk_resp = call_proxy("eth_getBlockByNumber", {"tag": tx.get("blockNumber", "0x0"), "boolean": "true"})
    blk = _take_result_or_fail(blk_resp, "block")

    # === Waktu: UTC + WIB ===
    ts_unix = _hex_to_int(blk.get("timestamp"))
    ts_utc = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
    timestamp_utc = ts_utc.strftime("%Y-%m-%d %H:%M:%S")
    try:
        timestamp_wib = ts_utc.astimezone(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        timestamp_wib = ""

    # === Biaya ===
    gas_used = _hex_to_int(rcpt.get("gasUsed", "0x0"))
    eff_price = rcpt.get("effectiveGasPrice") or tx.get("gasPrice") or "0x0"
    gas_price_wei = _hex_to_int(eff_price)
    gas_price_gwei = gas_price_wei / 1e9
    cost_eth = (gas_used * gas_price_wei) / 1e18

    if eth_idr_rate is None:
        eth_idr_rate = fetch_eth_idr_rate()
    cost_idr = cost_eth * float(eth_idr_rate or 0)

    # === Function name ===
    input_data = tx.get("input", "0x")
    method_id = input_data[:10] if input_data and input_data != "0x" else ""
    function_name = lookup_4byte(method_id) if method_id else ""

    status = "Success" if _hex_to_int(rcpt.get("status", "0x0")) == 1 else "Failed"

    return {
        "timestamp": timestamp_utc,
        "timestamp_local": timestamp_wib,
        "network": network_key.capitalize(),
        "tx_hash": tx_hash,
        "contract": tx.get("to") or "",
        "function_name": function_name or method_id,
        "block_number": _hex_to_int(tx.get("blockNumber", "0x0")),
        "gas_used": gas_used,
        "gas_price_gwei": gas_price_gwei,
        "cost_eth": cost_eth,
        "cost_idr": cost_idr,
        "status": status,
        "from_addr": tx.get("from") or "",
        "to_addr": tx.get("to") or ""
    }

# ===== Wrapper untuk STC Analytics =====
def fetch_tx_raw(network: str, tx_hash: str) -> dict:
    """Ambil data transaksi dari network."""
    import streamlit as st
    API = st.secrets.get("ETHERSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY")
    return fetch_tx_raw_any(tx_hash, API, network=network)

def to_standard_row(raw: dict) -> dict:
    """Konversi raw tx menjadi row standar STC Analytics GasVision CSV."""
    def num(x, default=0):
        try:
            return float(x)
        except:
            return default
    return {
        "Timestamp": raw.get("timestamp", ""),
        "Network": raw.get("network", ""),
        "Tx Hash": raw.get("tx_hash", ""),
        "Contract": raw.get("contract", ""),
        "Function": raw.get("function_name", ""),
        "Block": int(num(raw.get("block_number"))),
        "Gas Used": int(num(raw.get("gas_used"))),
        "Gas Price (Gwei)": num(raw.get("gas_price_gwei")),
        "Estimated Fee (ETH)": num(raw.get("cost_eth")),
        "Estimated Fee (Rp)": num(raw.get("cost_idr")),
        "Status": raw.get("status", "Unknown"),
        "Wallet From": raw.get("from_addr", ""),
        "Wallet To": raw.get("to_addr", ""),
    }

