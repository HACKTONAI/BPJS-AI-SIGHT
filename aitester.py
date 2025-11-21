import streamlit as st
import pandas as pd
from prophet import Prophet
import numpy as np
from datetime import timedelta, datetime
import requests

# ==========================================
# 1. FASE DATA ENGINEERING (Simulasi Data)
# ==========================================
@st.cache_data # Cache agar tidak meload ulang terus menerus
def generate_dummy_data():
    """
    Membuat data palsu kunjungan pasien selama 1 tahun ke belakang
    untuk 3 Faskes berbeda.
    """
    dates = pd.date_range(end=datetime.today(), periods=365)
    
    data_faskes = []
    
    # Konfigurasi Faskes (Nama, Kapasitas, Jarak dari User, Base Load)
    faskes_list = [
        {"nama": "Faskes A (Puskesmas Kota)", "kapasitas": 150, "jarak": 1.2, "base": 100},
        {"nama": "Faskes B (Klinik Sehat)", "kapasitas": 80, "jarak": 3.5, "base": 40},
        {"nama": "Faskes C (RSUD Tipe D)", "kapasitas": 200, "jarak": 5.0, "base": 140}
    ]
    
    all_history = []

    for f in faskes_list:
        # Buat pola acak tapi realistis (ada tren mingguan)
        base_val = f['base']
        daily_pattern = np.random.randint(-20, 20, size=365) # Fluktuasi harian
        # Tambahkan lonjakan di hari Senin (index % 7 == 0)
        weekly_pattern = [30 if i % 7 == 0 else 0 for i in range(365)]
        
        jumlah_pasien = base_val + daily_pattern + weekly_pattern
        # Pastikan tidak ada nilai negatif
        jumlah_pasien = np.maximum(jumlah_pasien, 10) 
        
        # Simpan data historis
        df = pd.DataFrame({'ds': dates, 'y': jumlah_pasien})
        df['nama_faskes'] = f['nama']
        df['kapasitas'] = f['kapasitas']
        df['jarak'] = f['jarak']
        
        all_history.append(df)
        
    return pd.concat(all_history), faskes_list

# ==========================================
# 2. FASE MACHINE LEARNING (Forecasting)
# ==========================================
def get_prediction(df_history, days_ahead=7):
    """
    Melatih model Prophet untuk satu Faskes dan memprediksi masa depan.
    """
    model = Prophet(daily_seasonality=True, yearly_seasonality=False)
    model.fit(df_history[['ds', 'y']])
    
    future = model.make_future_dataframe(periods=days_ahead)
    forecast = model.predict(future)
    
    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]

st.set_page_config(page_title="BPJS-AI SIGHT", layout="wide")
st.title("🏥 BPJS-AI SIGHT Prototype")
st.markdown("Platform Analitik Cerdas untuk Distribusi Beban Faskes")
st.divider()

# --- Load Data (pilihan sumber) ---
st.sidebar.write("**Sumber Data**")
data_source = st.sidebar.selectbox("Pilih sumber data:", ["Simulasi Lokal", "Realtime API (polling)"])
api_url = st.sidebar.text_input("API URL (jika pilih Realtime)", value="http://127.0.0.1:8000/latest")

@st.cache_data(ttl=5)
def fetch_latest_data_from_api(url: str):
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data)
        if 'ds' in df.columns:
            df['ds'] = pd.to_datetime(df['ds'])
        else:
            # fallback: no ds column
            df['ds'] = pd.to_datetime(datetime.today())
        # infer faskes list
        faskes = []
        if 'nama_faskes' in df.columns:
            for name in df['nama_faskes'].unique():
                row = df[df['nama_faskes'] == name].iloc[0]
                kap = int(row['kapasitas']) if 'kapasitas' in row else 100
                jar = float(row['jarak']) if 'jarak' in row else 1.0
                faskes.append({"nama": name, "kapasitas": kap, "jarak": jar})
        return df, faskes
    except Exception as e:
        st.sidebar.error(f"Gagal ambil data dari API: {e}")
        return pd.DataFrame(columns=['ds','y','nama_faskes','kapasitas','jarak']), []

if data_source == "Realtime API (polling)":
    df_total, list_faskes = fetch_latest_data_from_api(api_url)
else:
    df_total, list_faskes = generate_dummy_data()

# --- Sidebar (Input User) ---
st.sidebar.header("Menu Peserta")
selected_date = st.sidebar.date_input("Rencana Tanggal Kunjungan", datetime.today() + timedelta(days=1))
user_lat_long = "Monas, Jakarta" # Simulasi lokasi user

if st.sidebar.button("Cari Faskes Cerdas"):
    st.subheader(f"🔍 Hasil Analisis untuk Tanggal: {selected_date}")
    
    results = []
    
    # Kolom untuk menampilkan grafik
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("### 📈 Tren & Prediksi Beban Pasien")
        
    # --- PROSES UTAMA: Looping setiap Faskes untuk Prediksi ---
    progress_bar = st.progress(0)
    
    for i, faskes in enumerate(list_faskes):
        # 1. Ambil data historis khusus faskes ini
        history_faskes = df_total[df_total['nama_faskes'] == faskes['nama']]
        
        # 2. Lakukan Prediksi (AI Running...)
        forecast = get_prediction(history_faskes, days_ahead=14)
        
        # 3. Ambil nilai prediksi pada tanggal yang dipilih user
        target_date = pd.to_datetime(selected_date)
        prediksi_hari_ini = forecast[forecast['ds'] == target_date]['yhat'].values[0]
        prediksi_hari_ini = int(prediksi_hari_ini)
        
        # 4. Hitung Status Kepadatan
        persen_isi = (prediksi_hari_ini / faskes['kapasitas']) * 100
        
        if persen_isi > 100:
            status = "OVERLOAD 🔴"
            skor_kepadatan = 10 # Hukuman besar untuk skor
        elif persen_isi > 80:
            status = "Padat 🟠"
            skor_kepadatan = 5
        else:
            status = "Longgar 🟢"
            skor_kepadatan = 1
            
        # 5. Hitung SKOR REKOMENDASI (Smart Finder Logic)
        # Rumus: (Bobot Jarak * Jarak) + (Bobot Kepadatan * Skor Kepadatan)
        skor_akhir = (1.5 * faskes['jarak']) + (3.0 * skor_kepadatan)
        
        results.append({
            "nama_faskes": faskes['nama'],
            "prediksi": int(prediksi_hari_ini),
            "persen_isi": round(persen_isi, 1),
            "status": status,
            "skor_kepadatan": skor_kepadatan,
            "skor_akhir": round(skor_akhir, 2),
            "kapasitas": faskes['kapasitas'],
            "jarak": faskes['jarak']
        })

        # Update progress
        progress = int(((i + 1) / len(list_faskes)) * 100)
        progress_bar.progress(progress)

    # Setelah loop: susun dan tampilkan hasil
    if results:
        df_results = pd.DataFrame(results).sort_values("skor_akhir")

        with col2:
            st.write("### 🔎 Rekomendasi Faskes")
            st.table(df_results)

        with col1:
            st.write("### 📊 Total Historis (Semua Faskes)")
            try:
                totals = df_total.groupby('ds')['y'].sum()
                st.line_chart(totals)
            except Exception:
                st.write("Tidak dapat menampilkan grafik historis.")
    else:
        st.warning("Tidak ada hasil yang dihasilkan. Periksa input atau data historis.")