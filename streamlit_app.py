import streamlit as st
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
from tools.simulator import TX_PRESETS, GAS_SPEED_PRESET, simulate_fee_table
from utils.fetchers import fetch_tx_raw, to_standard_row
from web3 import Web3

import streamlit as st
from utils.fetchers import fetch_eth_idr_rate

@st.cache_data(ttl=600)  # cache selama 10 menit
def get_eth_idr_rate_cached():
    return fetch_eth_idr_rate()

from utils.fetchers import fetch_tx_raw_any
import os

@st.cache_data(ttl=300)
def fetch_tx_cached(network: str, tx_hash: str):
    API = st.secrets.get("ETHERSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY")
    return fetch_tx_raw_any(tx_hash, API, network=network)

with st.sidebar:
    if st.button("♻️ Refresh kurs (clear cache)"):
        get_eth_idr_rate_cached.clear()
        st.success("Kurs akan di-refresh pada request berikutnya.")

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
import pandas as pd
from datetime import datetime

COLUMNS_UPPER = [
    'Timestamp','Network','Tx Hash','Contract','Function','Block',
    'Gas Used','Gas Price (Gwei)','Estimated Fee (ETH)','Estimated Fee (Rp)','Status'
]

def convert_to_stc_format(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()

    # Normalisasi nama kolom berbagai kemungkinan
    rename_map = {
        'timestamp':'Timestamp', 'Timestamp':'Timestamp',
        'network':'Network', 'Network':'Network',
        'tx_hash':'Tx Hash', 'Tx Hash':'Tx Hash', 'TxHash':'Tx Hash', 'Hash':'Tx Hash',
        'contract':'Contract', 'Contract':'Contract', 'To':'Contract',
        'function_name':'Function', 'Function':'Function',
        'block_number':'Block', 'Block':'Block',
        'gas_used':'Gas Used', 'Gas Used':'Gas Used',
        'Gas Price (Gwei)':'Gas Price (Gwei)', 'gas_price_gwei':'Gas Price (Gwei)',
        'gas_price_wei':'gas_price_wei',  # kita konversi di bawah jika ada
        'cost_eth':'Estimated Fee (ETH)', 'Estimated Fee (ETH)':'Estimated Fee (ETH)',
        'cost_idr':'Estimated Fee (Rp)', 'Estimated Fee (Rp)':'Estimated Fee (Rp)',
        'status':'Status', 'Status':'Status'
    }
    df.rename(columns={k:v for k,v in rename_map.items() if k in df.columns}, inplace=True)

    # Isi kolom wajib yang belum ada
    if 'Timestamp' not in df.columns:
        df['Timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if 'Function' not in df.columns:
        df['Function'] = 'manual-entry'
    if 'Status' not in df.columns:
        df['Status'] = 'Unknown'

    # Gas Price: prioritas pakai kolom Gwei; kalau tidak ada tapi ada Wei -> konversi
    if 'Gas Price (Gwei)' not in df.columns:
        if 'gas_price_wei' in df.columns:
            df['Gas Price (Gwei)'] = pd.to_numeric(df['gas_price_wei'], errors='coerce').fillna(0) / 1e9
        else:
            df['Gas Price (Gwei)'] = 0

    # Pastikan numerik aman
    for col in ['Block','Gas Used','Gas Price (Gwei)','Estimated Fee (ETH)','Estimated Fee (Rp)']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Pastikan semua kolom ada, lalu urutkan sesuai target
    for c in COLUMNS_UPPER:
        if c not in df.columns:
            df[c] = '' if c in ['Network','Tx Hash','Contract','Function','Timestamp','Status'] else 0

    return df[COLUMNS_UPPER]
    
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
🔎 **Tips**: Masukkan hash transaksi dari testnet explorer seperti
[GoerliScan](https://goerli.etherscan.io), [SepoliaScan](https://sepolia.etherscan.io),
atau [PolygonScan](https://mumbai.polygonscan.com) untuk melihat estimasi biaya gas.
""")

df_original = None
raw = None
row = None

if tx_hash:
    try:
        # Ambil data via Etherscan (sudah termasuk WIB + decode function via 4byte)
        raw = fetch_tx_raw(network, tx_hash)
        row = to_standard_row(raw)

        # === Detail Transaksi
        st.subheader("📄 Detail Transaksi")
        st.write(f"**Network:** {row['Network']}")
        st.write(f"**From:** {raw.get('from_addr','')}")
        st.write(f"**To:** {raw.get('to_addr','')}")
        st.write(f"**Hash:** {row['Tx Hash']}")
        st.write(f"**Function:** {row['Function'] or '-'}")

        # === Receipt ringkas
        st.subheader("🧾 Receipt")
        st.write(f"**Block:** {row['Block']}")
        st.write(f"**Gas Used:** {row['Gas Used']}")
        st.write(f"**Status:** {'✅ Success' if row['Status']=='Success' else '❌ Failed'}")

        # === Ringkasan Biaya
        st.subheader("💰 Ringkasan Biaya")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Estimated Fee (ETH)", f"{row['Estimated Fee (ETH)']:.8f}")
        with c2:
            st.metric("Dalam Rupiah", f"Rp {row['Estimated Fee (Rp)']:,.2f}")
        with c3:
            st.metric("Gas Price (Gwei)", f"{row['Gas Price (Gwei)']:.2f}")

        # === Waktu blok (UTC & WIB)
        utc = raw.get("timestamp", "")
        wib = raw.get("timestamp_local", "")
        if wib:
            st.caption(f"🕒 Waktu blok — UTC: **{utc}** • WIB: **{wib}**")
        else:
            st.caption(f"🕒 Waktu blok (UTC): **{utc}**")

        # === DataFrame “detail transaksi” (apa adanya untuk user)
        data = {
            "Timestamp": [row["Timestamp"]],
            "Network": [row["Network"]],
            "Tx Hash": [row["Tx Hash"]],
            "From": [raw.get("from_addr","")],
            "To": [raw.get("to_addr","")],
            "Contract": [row["Contract"]],
            "Function": [row["Function"]],
            "Block": [row["Block"]],
            "Gas Used": [row["Gas Used"]],
            "Gas Price (Gwei)": [row["Gas Price (Gwei)"]],
            "Estimated Fee (ETH)": [row["Estimated Fee (ETH)"]],
            "Estimated Fee (Rp)": [row["Estimated Fee (Rp)"]],
            "Status": [row["Status"]],
        }
        df_original = pd.DataFrame(data)

        # === Download: CSV sesuai detail transaksi
        st.download_button(
            "⬇️ Unduh CSV sesuai detail transaksi",
            data=df_original.to_csv(index=False).encode("utf-8"),
            file_name=f"gas_tracker_{network.lower()}.csv",
            mime="text/csv",
            use_container_width=True
        )

        # === Download: CSV siap STC Analytics (kolom standar)
        df_converted = df_original[[
            'Timestamp','Network','Tx Hash','Contract','Function','Block',
            'Gas Used','Gas Price (Gwei)','Estimated Fee (ETH)','Estimated Fee (Rp)','Status'
        ]].copy()
        st.download_button(
            "⬇️ Unduh untuk analisa di STC Analytics",
            data=df_converted.to_csv(index=False).encode("utf-8"),
            file_name="stc_analytics_ready.csv",
            mime="text/csv",
            use_container_width=True
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
