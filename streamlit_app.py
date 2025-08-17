import streamlit as st
import requests
import re, time, pandas as pd
from io import StringIO
from datetime import datetime
from tools.simulator import TX_PRESETS, GAS_SPEED_PRESET, simulate_fee_table
from utils.fetchers import fetch_tx_raw, to_standard_row, CHAINIDS, fetch_tx_raw_any
from web3 import Web3

import streamlit as st
from utils.fetchers import fetch_eth_idr_rate

@st.cache_data(ttl=600)  # cache selama 10 menit
def get_eth_idr_rate_cached():
    from utils.fetchers import fetch_eth_idr_rate
    return fetch_eth_idr_rate()

from utils.fetchers import fetch_tx_raw_any
import os

# init session_state keys
if "tx_hash_input" not in st.session_state:
    st.session_state["tx_hash_input"] = ""

def _clear_single_hash():
    st.session_state["tx_hash_input"] = ""
    st.session_state.pop("single_raw", None)
    st.session_state.pop("single_row", None)
    st.session_state.pop("df_original", None)

# --- session_state init for multi mode ---
if "multi_hashes" not in st.session_state:
    st.session_state["multi_hashes"] = ""
if "multi_networks" not in st.session_state:
    st.session_state["multi_networks"] = ["sepolia"]

def _clear_multi_hashes():
    st.session_state["multi_hashes"] = ""
    st.session_state.pop("multi_rows", None)
    st.session_state.pop("multi_fails", None)

def _clear_multi_networks():
    st.session_state["multi_networks"] = []

def _fill_demo_hashes():
    st.session_state["multi_hashes"] = "\n".join([
        "0x41ed4bee1442238abcc81fac4abd40d3fb31ef647865ec8c81301238afd4b3e4",
        "0x54553269973eb4621924e6393ecac7fa71c4aadd69dbc3ecad92b9b4db7a40e4",
        "0x4e90e2a3d73af50cc92860fd14431c4ce5c836e62ab825ef51eca4e660e01cac",
    ])

@st.cache_data(ttl=300)
def fetch_tx_cached(network: str, tx_hash: str):
    API = st.secrets.get("ETHERSCAN_API_KEY") or os.getenv("ETHERSCAN_API_KEY")
    return fetch_tx_raw_any(tx_hash, API, network=network)

def format_rupiah(val: float | None) -> str:
    if val is None:
        return "—"
    try:
        x = float(val)
    except Exception:
        return "—"
    # kalau >= 1, tampil bulat; kalau < 1, pakai 2 desimal biar tidak jadi 0.00
    return (f"Rp {x:,.0f}" if x >= 1 else f"Rp {x:,.2f}").replace(",", ".")

HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")

def parse_hashes(s: str) -> list[str]:
    if not s: return []
    toks = re.split(r"[\s,;]+", s.strip())
    seen, out = set(), []
    for t in toks:
        if HASH_RE.fullmatch(t) and t not in seen:
            out.append(t); seen.add(t)
    return out

def format_rupiah_id(val: float, dec_ge1=2, dec_lt1=4):
    try: x = float(val)
    except: return "—"
    dec = dec_ge1 if x >= 1 else dec_lt1
    s = f"{x:,.{dec}f}"
    whole, frac = s.split(".")
    whole = whole.replace(",", ".")
    return f"Rp {whole},{frac}"

st.set_page_config(
    page_title="STC GasVision",
    page_icon="⛽",
    layout="wide"
)

st.markdown("""
<style>
:root { --accent:#20c997; --accent2:#7c4dff; }
.block-container { padding-top: 1rem; }
section[data-testid="stSidebar"] .st-expander { border:1px solid #313131; border-radius:12px; }
div[data-testid="stMetric"]{
  background: linear-gradient(135deg, rgba(32,201,151,.08), rgba(124,77,255,.06));
  border: 1px solid rgba(128,128,128,.15);
  padding: 12px; border-radius: 12px;
}
.stButton>button, .stDownloadButton>button{
  border-radius:10px; border:1px solid rgba(255,255,255,.15);
}
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"]{
  background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.08);
  border-radius: 10px; padding: 6px 12px;
}
[data-testid="stHeader"] { background: transparent; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    if st.button("♻️ Refresh kurs (clear cache)"):
        get_eth_idr_rate_cached.clear()
        st.success("Kurs akan di-refresh pada request berikutnya.")

    st.sidebar.markdown("📘 **About**")
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

# === Input Tx Hash ===
st.title("⛽ Gas Usage Tracker")

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

# --- SINGLE HASH (satu input + tombol hapus) ---
c_inp, c_btn = st.columns([1, 0.18])

with c_inp:
    st.text_input(
        "Masukkan Tx Hash",
        key="tx_hash_input",
        placeholder="0x..."
    )

with c_btn:
    st.write("")  # spacer
    clear_disabled = not bool(st.session_state.get("tx_hash_input"))
    st.button(
        "🧽 Hapus",
        key="btn_clear_single",
        use_container_width=True,
        disabled=clear_disabled,
        on_click=_clear_single_hash,
    )

st.markdown("""
🔎 **Tips**: Masukkan hash transaksi dari testnet explorer seperti
[GoerliScan](https://goerli.etherscan.io), [SepoliaScan](https://sepolia.etherscan.io),
atau [PolygonScan](https://mumbai.polygonscan.com) untuk melihat estimasi biaya gas.
""")

tx_hash = (st.session_state.get("tx_hash_input") or "").strip()

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
        eth_idr_rate = get_eth_idr_rate_cached()
        cost_eth = float(raw.get("cost_eth", 0.0))
        cost_idr_val = (eth_idr_rate or 0) * cost_eth
        rupiah_str = format_rupiah(cost_idr_val)

        gwei = float(raw.get("gas_price_gwei", 0) or 0.0)
        wei  = int(raw.get("gas_price_wei", 0)  or 0)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Estimated Fee (ETH)", f"{cost_eth:.8f}")
        with c2:
            st.metric("Dalam Rupiah", rupiah_str)
        with c3:
            st.metric("Gas Price (Gwei)", f"{gwei:.4f}")  # naikkan presisi

        # Badge subsidi
        if wei == 0:
            st.info("🟢 Gasless / Sponsored Tx — `gasPrice = 0` (biaya gas disubsidi).")
        elif gwei < 0.001:
            st.warning(f"🟡 Near-zero gas price ({gwei:.4f} Gwei) — kemungkinan disubsidi/di-sponsor.")

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
            "Gasless?": "Ya" if (wei == 0 or gwei < 0.001) else "Tidak",
        }
        df_original = pd.DataFrame(data)

        # include_addr = st.checkbox("Sertakan alamat wallet di CSV standar", value=False)

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
### 💡 Analisis Lanjutan
CSV ini hanya satu transaksi.  
Untuk melihat tren dan pola biaya:

- Coba input beberapa hash
- Gunakan Mode Multi Hash / Multi Chain
- Upload hasilnya ke 👉 [**STC Analytics**](https://stc-analytics.streamlit.app)

Semakin banyak hash, semakin akurat analisismu. 🚀
""")

HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
def parse_hashes(s: str) -> list[str]:
    if not s: return []
    toks = re.split(r"[\s,;]+", s.strip())
    seen, out = set(), []
    for t in toks:
        if HASH_RE.fullmatch(t) and t not in seen:
            out.append(t); seen.add(t)
    return out

with st.expander("🧰 Mode Multi-Hash / Multi-Chain (Beta)", expanded=False):

    st.multiselect(
        "Pilih jaringan (bisa lebih dari satu)",
        options=list(CHAINIDS.keys()),
        key="multi_networks",
    )

    c_txt, c_actions = st.columns([1, 0.35])
    with c_txt:
        st.text_area(
            "Masukkan banyak Tx Hash (pisah koma atau baris baru)",
            key="multi_hashes",
            placeholder="0xabc..., 0xdef...\n0x123...",
            height=120,
        )
    with c_actions:
        st.write("")
        st.button(
            "🧽 Hapus hash",
            use_container_width=True,
            disabled=(len(st.session_state["multi_hashes"].strip()) == 0),
            on_click=_clear_multi_hashes,
            key="btn_clear_multi",
        )
        st.button(
            "🧪 Contoh demo",
            use_container_width=True,
            on_click=_fill_demo_hashes,
            key="btn_fill_demo",
        )

    # --- ambil nilai & PARSE hashes ---
    nets = st.session_state["multi_networks"]
    hashes_raw = st.session_state["multi_hashes"]
    hashes = parse_hashes(hashes_raw)  # <— ini yang sebelumnya hilang

    st.caption(f"Terbaca: **{len(hashes)} hash** di **{len(nets)} chain**")

    run = st.button(
        f"Proses ({len(hashes)}×{len(nets)})",
        use_container_width=True,
        key="run_multi",
        disabled=(len(hashes) == 0 or len(nets) == 0),
    )

    if run:
        rate = get_eth_idr_rate_cached()
        total = len(hashes) * len(nets)
        prog = st.progress(0.0)
        rows, fails = [], []
        i = 0

        for net in nets:
            for h in hashes:
                try:
                    raw = fetch_tx_cached(net, h)

                    gas_used = int(float(raw.get("gas_used", 0) or 0))
                    gwei     = float(raw.get("gas_price_gwei", 0) or 0.0)
                    fee_eth  = float(raw.get("cost_eth", 0.0) or 0.0)
                    fee_idr  = fee_eth * (rate or 0)

                    rows.append({
                        "Timestamp": raw.get("timestamp",""),
                        "Network": raw.get("network","").capitalize() or net,
                        "Tx Hash": h,
                        "Contract": raw.get("contract",""),
                        "Function": raw.get("function_name",""),
                        "Block": int(float(raw.get("block_number",0) or 0)),
                        "Gas Used": gas_used,
                        "Gas Price (Gwei)": gwei,
                        "Estimated Fee (ETH)": fee_eth,
                        "Estimated Fee (Rp)": fee_idr,
                        "Status": raw.get("status","Unknown"),
                        "Gasless?": ("Ya" if float(raw.get("gas_price_gwei",0) or 0) < 0.001 else "Tidak"),
                    })
                except Exception as e:
                    fails.append({"Network": net, "Tx Hash": h, "Error": str(e)})

                i += 1
                prog.progress(i / total)
                time.sleep(0.25)  # throttle biar gak ke-rate limit

        if rows:
            df = pd.DataFrame(rows)
            st.success(f"Selesai: {len(rows)} baris.")
            st.dataframe(df, use_container_width=True, height=320)

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Unduh gabungan (CSV)",
                data=csv_bytes,
                file_name="stc_gasvision_multi.csv",
                mime="text/csv",
                use_container_width=True,
                key="dl_multi_csv",
            )

        if fails:
            st.warning(f"{len(fails)} gagal diproses.")
            st.dataframe(pd.DataFrame(fails), use_container_width=True, height=200)

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
