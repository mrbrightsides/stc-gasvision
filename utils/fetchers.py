import os
import requests
from datetime import datetime, timezone

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
def fetch_tx_raw_any(tx_hash: str, api_key: str, network: str = "sepolia", eth_idr_rate: float | None = None) -> dict:
    """Ambil detail transaksi (raw) + biaya dalam ETH & IDR."""
    network = network.lower().strip()

    base_map = {
        "sepolia": "https://api-sepolia.etherscan.io/api",
        "mainnet": "https://api.etherscan.io/api",
    }
    if network not in base_map:
        raise ValueError(f"Network belum didukung: {network}")

    base = base_map[network]

    # --- TX data ---
    tx = _etherscan_get(base, {
        "module": "proxy",
        "action": "eth_getTransactionByHash",
        "txhash": tx_hash,
        "apikey": api_key
    }).get("result")

    if not tx:
        raise RuntimeError("Transaksi tidak ditemukan")

    # --- Receipt ---
    rcpt = _etherscan_get(base, {
        "module": "proxy",
        "action": "eth_getTransactionReceipt",
        "txhash": tx_hash,
        "apikey": api_key
    }).get("result", {})

    # --- Block ---
    blk = _etherscan_get(base, {
        "module": "proxy",
        "action": "eth_getBlockByNumber",
        "tag": tx["blockNumber"],
        "boolean": "true",
        "apikey": api_key
    }).get("result", {})

    # === Konversi data ===
    ts_unix = _hex_to_int(blk.get("timestamp"))
    timestamp = datetime.fromtimestamp(ts_unix, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    gas_used = _hex_to_int(rcpt.get("gasUsed", "0x0"))
    eff_price = rcpt.get("effectiveGasPrice") or tx.get("gasPrice") or "0x0"
    gas_price_wei = _hex_to_int(eff_price)
    gas_price_gwei = gas_price_wei / 1e9
    cost_eth = (gas_used * gas_price_wei) / 1e18

    if eth_idr_rate is None:
        eth_idr_rate = fetch_eth_idr_rate()
    cost_idr = cost_eth * float(eth_idr_rate or 0)

    input_data = tx.get("input", "0x")
    method_id = input_data[:10] if input_data and input_data != "0x" else ""
    status = "Success" if _hex_to_int(rcpt.get("status", "0x0")) == 1 else "Failed"

    return {
        "timestamp": timestamp,
        "network": network.capitalize(),
        "tx_hash": tx_hash,
        "contract": tx.get("to") or "",
        "function_name": method_id,  # nanti kita upgrade decode signature
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
