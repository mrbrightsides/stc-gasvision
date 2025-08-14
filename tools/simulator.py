import streamlit as st
import pandas as pd
import requests

# === Preset Gas Used per Transaction Type ===
TX_PRESETS = {
    "Transfer ETH": 21000,
    "ERC20 Approve": 45000,
    "ERC20 Transfer": 65000,
    "Deploy Contract": 1500000,
    "Uniswap Swap": 150000,
    "Add Liquidity": 270000,
}

GAS_SPEED_PRESET = {
    "Standard": 20,
    "Fast": 50,
    "Instant": 100
}

SIMULATED_NETWORKS = {
    "Sepolia": "ETH",
    "Goerli": "ETH",
    "Polygon Mumbai": "ETH",
    "Arbitrum Sepolia": "ETH"
}

def get_eth_to_idr():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=idr"
        response = requests.get(url)
        return response.json()["ethereum"]["idr"]
    except:
        return 60000000  # fallback

def calculate_gas_fees(gas_used, gas_price_gwei, eth_to_idr):
    fee_eth = (gas_used * gas_price_gwei) * 1e-9
    fee_idr = fee_eth * eth_to_idr
    return fee_eth, fee_idr

def simulate_fee_table(tx_type, gas_used_input, speed_level, selected_networks):
    eth_to_idr = get_eth_to_idr()
    gas_price_gwei = GAS_SPEED_PRESET[speed_level]
    rows = []

    for network in selected_networks:
        token = SIMULATED_NETWORKS[network]
        fee_eth, fee_idr = calculate_gas_fees(gas_used_input, gas_price_gwei, eth_to_idr)
        rows.append({
            "Jaringan": network,
            "Token": token,
            "Gas Used": gas_used_input,
            "Gas Price (Gwei)": gas_price_gwei,
            "Fee (ETH)": round(fee_eth, 8),
            "Fee (Rp)": round(fee_idr, 2)
        })

    return pd.DataFrame(rows)
    csv_simulasi = df_simulasi.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Unduh Hasil Simulasi", csv_simulasi, "simulasi_biaya_gas.csv", "text/csv")

