import streamlit as st
from web3 import Web3
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
from tools.simulator import TX_PRESETS, GAS_SPEED_PRESET, simulate_fee_table

st.set_page_config(
    page_title="STC GasVision",
    page_icon="⛽",
    layout="wide"
)


st.markdown("""
    <style>
    /* === DARK MODE SIDEBAR === */
    section[data-testid="stSidebar"] {
        background-color: #111111;
        padding: 1.5rem;
        color: white;
        border-right: 1px solid #333;
    }

    /* === Box/frame styling like STC Analytics === */
    section[data-testid="stSidebar"] > div {
        background-color: #1a1a1a;
        padding: 16px;
        border-radius: 8px;
        border: 1px solid #333333;
        box-shadow: 0 0 10px rgba(0,0,0,0.3);
    }

    /* === Sidebar text and links === */
    section[data-testid="stSidebar"] * {
        color: white !important;
    }

    section[data-testid="stSidebar"] a {
        color: #1abfff !important;
        text-decoration: none;
    }

    section[data-testid="stSidebar"] a:hover {
        text-decoration: underline;
    }
    </style>
""", unsafe_allow_html=True)

# === Konversi format CSV ke format STC Analytics ===
def convert_to_stc_format(df_raw):
    df = df_raw.copy()

    df['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['contract'] = df.get('To', '')
    df['function_name'] = 'manual-entry'
    df['block_number'] = df['Block']
    df['gas_price_wei'] = df['Gas Price (Gwei)'] * 1e9
    df['cost_eth'] = df['Estimated Fee (ETH)']
    df['cost_idr'] = df['Estimated Fee (Rp)']
    df['meta_json'] = '{}'

    df.rename(columns={
        'Network': 'network',
        'Tx Hash': 'tx_hash',
        'Gas Used': 'gas_used'
    }, inplace=True)

    columns_needed = [
        'timestamp','network','tx_hash','contract','function_name',
        'block_number','gas_used','gas_price_wei','cost_eth','cost_idr','meta_json'
    ]
    return df[columns_needed]
    
# === Sidebar ===
st.sidebar.title("ℹ️ About")
st.sidebar.markdown("""
STC GasVision memantau biaya gas transaksi di berbagai testnet (Sepolia, Goerli,
Polygon Mumbai, Arbitrum Sepolia) dan mengonversinya ke Rupiah.

**Sumber data**
- 🔌 Realtime data jaringan: **Infura RPC**
- 💱 Kurs ETH → IDR via **Infura**, dengan fallback ke provider lain
- 🧠 Kurs dicache ±10 menit
- 📥 Export CSV untuk analisis

🧾 Upload hasil CSV ke [**STC Analytics**](https://stc-analytics.streamlit.app)
untuk eksplorasi lanjutan biaya transaksi.

---

#### 🙌 Dukungan & kontributor
- ⭐ **Star / Fork**: [GitHub repo](https://github.com/mrbrightsides/stc-gasvision/tree/main)
- Built with 💙 by [ELPEEF](https://elpeef.com)

Versi UI: v1.0 • Streamlit • Theme Dark
""")

# === Logo dan Header ===
LOGO_URL = "https://i.imgur.com/7j5aq4l.png"
col1, col2 = st.columns([1, 4])
with col1:
    st.image(LOGO_URL, width=60)
with col2:
    st.markdown("## STC GasVision")

# === RPC URLs ===
RPC_URLS = {
    "Sepolia": "https://sepolia.infura.io/v3/f8d248f838ec4f12b0f01efd2b238206",
    "Goerli": "https://goerli.infura.io/v3/f8d248f838ec4f12b0f01efd2b238206",
    "Polygon Mumbai": "https://polygon-mumbai.infura.io/v3/f8d248f838ec4f12b0f01efd2b238206",
    "Arbitrum Sepolia": "https://arbitrum-sepolia.infura.io/v3/f8d248f838ec4f12b0f01efd2b238206"
}

network = st.selectbox("🧭 Pilih Jaringan Testnet", list(RPC_URLS.keys()))
web3 = Web3(Web3.HTTPProvider(RPC_URLS[network]))

# === ETH to IDR ===
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
st.title("⛽ Gas Usage Tracker")
tx_hash = st.text_input("Masukkan Tx Hash", placeholder="Contoh: 0xabc123...")
st.markdown("""
🔎 **Tips**: Masukkan hash transaksi dari testnet explorer seperti [GoerliScan](https://goerli.etherscan.io), [SepoliaScan](https://sepolia.etherscan.io), atau [PolygonScan](https://mumbai.polygonscan.com) untuk melihat estimasi biaya gas.
""")

df_original = None  # Define globally for later use

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

        # === Show result
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

        # === DataFrame
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
        df_original = pd.DataFrame(data)

        # === Download original CSV
        csv = df_original.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Unduh CSV sesuai detail transaksi",
            data=csv,
            file_name=f"gas_tracker_{network.lower()}.csv",
            mime='text/csv'
        )

    except Exception as e:
        st.error(f"Gagal mengambil data transaksi: {e}")

# === Tips & link
st.markdown("""
### 🔍 Tips untuk Analisis Lanjutan
CSV ini hanya satu transaksi.  
Untuk melihat tren dan pola biaya:

- Coba input beberapa hash
- Gabungkan semua file
- Upload ke 👉 [**STC Analytics**](https://stc-analytics.streamlit.app)

Semakin banyak hash, semakin akurat analisismu. 🚀
""")

# === Export to STC Analytics format
if df_original is not None:
    df_converted = convert_to_stc_format(df_original)
    csv_converted = df_converted.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Unduh untuk analisa di STC Analytics",
        data=csv_converted,
        file_name="stc_analytics_ready.csv",
        mime="text/csv"
    )

# === Separator UI ===
st.markdown("---")
st.header("📟 Gas Fee Simulator")

st.markdown("""
Ingin tahu berapa biaya gas dari berbagai jaringan tanpa menunggu transaksi nyata?  
Gunakan simulasi berikut untuk membandingkan biaya berdasarkan jenis transaksi dan kecepatan.
""")

with st.expander("Simulasikan Biaya Gas Manual"):
    col1, col2 = st.columns(2)
    with col1:
        tx_type = st.selectbox("Jenis Transaksi", list(TX_PRESETS.keys()))
        gas_used = st.number_input("Gas Used", value=TX_PRESETS[tx_type])
        speed = st.selectbox("Kecepatan", list(GAS_SPEED_PRESET.keys()))

    with col2:
        selected_networks = st.multiselect(
            "Pilih Jaringan", list(RPC_URLS.keys()), default=["Sepolia"]
        )

    if st.button("🔍 Simulasikan Biaya"):
        df_simulasi = simulate_fee_table(tx_type, gas_used, speed, selected_networks)
        st.success("Simulasi berhasil dilakukan.")
        st.dataframe(df_simulasi, use_container_width=True)

        csv_simulasi = df_simulasi.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Unduh Hasil Simulasi", csv_simulasi, "simulasi_biaya_gas.csv", "text/csv")
