import streamlit as st
from web3 import Web3
import requests
import pandas as pd

import streamlit as st
from simulator import simulate_fee_table, TX_PRESETS, GAS_SPEED_PRESET

# === Sidebar Info ===
st.sidebar.title("ℹ️ About")
st.sidebar.markdown("""
STC GasVision memantau biaya gas transaksi di berbagai testnet (Sepolia, Goerli,
Polygon Mumbai, Arbitrum Sepolia) dan mengonversi biaya gas ke Rupiah.

**Sumber data**
- 🔌 Realtime data jaringan & eksekusi transaksi: **Infura RPC**
- 💱 Kurs ETH → IDR diperbarui otomatis (realtime) via **Infura**,  
  dengan fallback penyedia harga eksternal bila endpoint utama tidak tersedia.
- 🧠 Cache kurs ±10 menit untuk stabilitas & rate-limit.

📥 Unduh CSV untuk setiap hash transaksi.

📊 Untuk visualisasi pola & tren biaya, unggah CSV Anda ke **[STC Analytics](https://stc-analytics.streamlit.app)**.
---
""")

LOGO_URL = "https://i.imgur.com/7j5aq4l.png"

col1, col2 = st.columns([1, 4])
with col1:
    st.image(LOGO_URL, width=60)
with col2:
    st.markdown("""
        ## STC GasVision
    """)

# === Daftar RPC URL dari berbagai testnet ===
RPC_URLS = {
    "Sepolia": "https://sepolia.infura.io/v3/f8d248f838ec4f12b0f01efd2b238206",
    "Goerli": "https://goerli.infura.io/v3/f8d248f838ec4f12b0f01efd2b238206",
    "Polygon Mumbai": "https://polygon-mumbai.infura.io/v3/f8d248f838ec4f12b0f01efd2b238206",
    "Arbitrum Sepolia": "https://arbitrum-sepolia.infura.io/v3/f8d248f838ec4f12b0f01efd2b238206"
}

# === Pilih jaringan ===
network = st.selectbox("🧭 Pilih Jaringan Testnet", list(RPC_URLS.keys()))
web3 = Web3(Web3.HTTPProvider(RPC_URLS[network]))

# === Kurs ETH ke IDR ===
@st.cache_data(ttl=600)
def get_eth_to_idr():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=idr")
        return response.json()['ethereum']['idr']
    except:
        return 60000000

ETH_TO_IDR = get_eth_to_idr()
st.write(f"💱 Kurs saat ini (ETH to IDR): Rp {ETH_TO_IDR:,}")

# === Input Tx Hash ===
st.title("📊 Gas Usage Tracker")
tx_hash = st.text_input("Masukkan Tx Hash", placeholder="Contoh: 0xabc123...")

# === Tampilkan hasil jika ada hash ===
if tx_hash:
    try:
        tx = web3.eth.get_transaction(tx_hash)
        receipt = web3.eth.get_transaction_receipt(tx_hash)

        gas_price_gwei = web3.from_wei(tx['gasPrice'], 'gwei')
        gas_used = receipt['gasUsed']
        estimated_fee_wei = tx['gasPrice'] * gas_used
        estimated_fee_eth = web3.from_wei(estimated_fee_wei, 'ether')
        estimated_fee_idr = float(estimated_fee_eth) * ETH_TO_IDR
        status = '✅ Success' if receipt['status'] == 1 else '❌ Failed'
        status_csv = 'Success' if receipt['status'] == 1 else 'Failed'

        # === Tampilan Streamlit ===
        st.subheader("📄 Detail Transaksi")
        st.write(f"**Network:** {network}")
        st.write(f"**From:** {tx['from']}")
        st.write(f"**To:** {tx['to']}")
        st.write(f"**Hash:** {tx['hash'].hex()}")
        st.write(f"**Gas Price:** {gas_price_gwei:.2f} Gwei")
        st.write(f"**Gas Limit:** {tx['gas']}")

        st.subheader("🧾 Receipt")
        st.write(f"**Block:** {receipt['blockNumber']}")
        st.write(f"**Gas Used:** {gas_used}")
        st.write(f"**Status:** {status}")

        st.subheader("🧮 Biaya Gas")
        st.write(f"**Estimated Fee:** {estimated_fee_eth:.8f} ETH")
        st.write(f"**Dalam Rupiah:** Rp {estimated_fee_idr:,.2f}")

        # === Export ke CSV ===
        data = {
            "Network": [network],
            "Tx Hash": [tx['hash'].hex()],
            "From": [tx['from']],
            "To": [tx['to']],
            "Block": [receipt['blockNumber']],
            "Gas Used": [gas_used],
            "Gas Price (Gwei)": [float(gas_price_gwei)],
            "Estimated Fee (ETH)": [float(estimated_fee_eth)],
            "Estimated Fee (Rp)": [float(estimated_fee_idr)],
            "Status": [status_csv]
        }
        df = pd.DataFrame(data)
        csv = df.to_csv(index=False).encode('utf-8')

        st.download_button(
            label="⬇️ Export ke CSV",
            data=csv,
            file_name=f"gas_tracker_{network.lower()}.csv",
            mime='text/csv'
        )

    except Exception as e:
        st.error(f"Gagal mengambil data transaksi: {e}")

st.markdown("""
    ### 🔍 Tips untuk Analisis Lanjutan
    File CSV yang Anda unduh hanya berisi satu transaksi.  
    Untuk mendapatkan visualisasi yang lebih komprehensif:

    - Lakukan beberapa kali input transaksi dengan hash berbeda
    - Gabungkan semua file CSV Anda
    - Lanjutkan analisis melalui dashboard 👉 [**STC Analytics**](https://stc-analytics.streamlit.app)

    Semakin banyak hash yang Anda kumpulkan, semakin jelas pola biaya dan efisiensinya. 🚀
    """)
