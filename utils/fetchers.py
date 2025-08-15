import os, requests
from datetime import datetime, timezone

def _etherscan_get(base, params, timeout=8):
    r = requests.get(base, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if "error" in data and data["error"]:
        raise RuntimeError(str(data["error"]))
    return data

def _hex_to_int(x): 
    try: return int(x, 16)
    except: return 0

def fetch_eth_idr_rate(timeout=6):
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids":"ethereum","vs_currencies":"idr"}, timeout=timeout)
        r.raise_for_status()
        return float(r.json()["ethereum"]["idr"])
    except: 
        return 0.0

def fetch_tx_raw_sepolia(tx_hash: str, api_key: str, eth_idr_rate: float|None=None) -> dict:
    base = "https://api-sepolia.etherscan.io/api"
    tx = _etherscan_get(base, {"module":"proxy","action":"eth_getTransactionByHash",
                               "txhash":tx_hash,"apikey":api_key})["result"]
    if not tx: raise RuntimeError("Transaksi tidak ditemukan")
    rcpt = _etherscan_get(base, {"module":"proxy","action":"eth_getTransactionReceipt",
                                "txhash":tx_hash,"apikey":api_key})["result"]
    blk = _etherscan_get(base, {"module":"proxy","action":"eth_getBlockByNumber",
                                "tag":tx["blockNumber"],"boolean":"true","apikey":api_key})["result"]

    ts_unix = _hex_to_int(blk["timestamp"])
    timestamp = datetime.fromtimestamp(ts_unix, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    gas_used = _hex_to_int(rcpt.get("gasUsed","0x0"))
    eff = rcpt.get("effectiveGasPrice") or tx.get("gasPrice") or "0x0"
    gas_price_wei = _hex_to_int(eff)
    gas_price_gwei = gas_price_wei / 1e9
    cost_eth = (gas_used * gas_price_wei) / 1e18

    if eth_idr_rate is None:
        eth_idr_rate = fetch_eth_idr_rate()
    cost_idr = cost_eth * float(eth_idr_rate or 0)

    input_data = tx.get("input","0x")
    method_id = input_data[:10] if input_data and input_data!="0x" else ""
    status = "Success" if _hex_to_int(rcpt.get("status","0x0"))==1 else "Failed"

    return {
        "timestamp": timestamp,
        "network": "Sepolia",
        "tx_hash": tx_hash,
        "contract": tx.get("to") or "",
        "function_name": method_id,  # step 3 akan kita upgrade decode
        "block_number": _hex_to_int(tx.get("blockNumber","0x0")),
        "gas_used": gas_used,
        "gas_price_gwei": gas_price_gwei,
        "cost_eth": cost_eth,
        "cost_idr": cost_idr,
        "status": status,
        "from_addr": tx.get("from") or "",
        "to_addr": tx.get("to") or ""
    }

def fetch_tx_raw(network: str, tx_hash: str) -> dict:
    import streamlit as st
    API = st.secrets.get("ETHERSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY")
    n = (network or "").lower().strip()
    if n in ["sepolia","ethereum sepolia"]:
        return fetch_tx_raw_sepolia(tx_hash, API)
    raise ValueError(f"Network belum didukung: {network}")

def to_standard_row(raw: dict) -> dict:
    def num(x, default=0):
        try: return float(x)
        except: return default
    return {
        "Timestamp": raw.get("timestamp",""),
        "Network": raw.get("network",""),
        "Tx Hash": raw.get("tx_hash",""),
        "Contract": raw.get("contract",""),
        "Function": raw.get("function_name",""),
        "Block": int(num(raw.get("block_number"))),
        "Gas Used": int(num(raw.get("gas_used"))),
        "Gas Price (Gwei)": num(raw.get("gas_price_gwei")),
        "Estimated Fee (ETH)": num(raw.get("cost_eth")),
        "Estimated Fee (Rp)": num(raw.get("cost_idr")),
        "Status": raw.get("status","Unknown"),
        "Wallet From": raw.get("from_addr",""),
        "Wallet To": raw.get("to_addr",""),
    }

