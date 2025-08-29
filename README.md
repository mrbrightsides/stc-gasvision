# ⛽ GasVision by SmartTourismChain

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.16763535.svg)](https://doi.org/10.5281/zenodo.16763535)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://stc-gasvision.streamlit.app/)
![STC Module – GasVision](https://img.shields.io/badge/STC%20Module-GasVision-crimson)
![status: stable](https://img.shields.io/badge/status-stable-brightgreen)
[![Keep Alive](https://github.com/mrbrightsides/stc-gasvision/actions/workflows/ping.yml/badge.svg)](https://github.com/mrbrightsides/stc-gasvision/actions/workflows/ping.yml)

Pantau biaya gas transaksi blockchain testnet secara **real-time** dan transparan.  
Bagian dari ekosistem **SmartTourismChain (STC)**.

---

## ✨ Fitur

- 🔎 Tracking gas usage dari berbagai testnet (Sepolia, Goerli, Mumbai, Arbitrum)
- 💱 Konversi biaya ke ETH dan Rupiah
- 📥 Export transaksi ke CSV untuk analisis lanjutan
- 🖥️ UI ramah pengguna (dibangun dengan Streamlit)

---

## 📊 Demo UI

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/89cbcb10-5a52-49a7-8db0-819e2adeb7ea" /><p>

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/0889ba5f-2686-406f-a5ae-3add60550b18" /><p>


> Tampilan dashboard: pilih jaringan testnet, masukkan Tx Hash, dapatkan estimasi biaya gas realtime.

---

## 🪄 Arsitektur

```mermaid
flowchart TD
    A[User] -->|Input Tx Hash| B[GasVision UI]
    B -->|Query| C[Infura RPC / Explorer API]
    C -->|Gas Usage & ETH Price| D[GasVision Engine]
    D -->|Konversi ke IDR| E[Hasil ditampilkan di UI]
    D -->|Ekspor CSV| F[STC Analytics]
```

```mermaid
flowchart LR
  RPC["RPC / Explorer"] --> GV["STC GasVision"]
  GV --> CUR["Kurs & Konversi"]
  GV --> HEAT["Tren / Heatmap"]
  GV --> LOG["Logs / Metrics"]
```

---

## 📦 Instalasi Lokal
```bash
git clone https://github.com/mrbrightsides/stc-gasvision.git
cd stc-gasvision
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## 🚀 Integrasi dengan STC
Hasil CSV dari GasVision dapat langsung di-upload ke STC Analytics untuk eksplorasi lebih lanjut.
Cocok untuk:
- Analisis biaya transaksi lintas chain
- Benchmark performa smart contract
- Dokumentasi riset blockchain pariwisata

---

## 📜 Lisensi
MIT License © ELPEEF Dev Team
