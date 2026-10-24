import streamlit as st
import cv2
import easyocr
import re
import numpy as np
import pandas as pd
from datetime import datetime

# Mengatur konfigurasi halaman web
st.set_page_config(page_title="OCR Laporan KTP & KK", layout="centered")

st.title("📝 Pindai Dokumen & Pengisian Laporan Otomatis")
st.write("Unggah 2 KTP (Pemohon & Penjamin) serta 1 KK untuk membuat laporan instan.")

# Inisialisasi EasyOCR secara otomatis (menggunakan cache agar tidak meload ulang setiap klik)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['id'], gpu=False)

reader = load_ocr()

def perbaiki_posisi_ktp(img):
    """Memutar gambar KTP 90 derajat searah jarum jam karena posisi foto miring ke kiri"""
    return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

def ekstrak_data_ktp(uploaded_file, role="Data"):
    if uploaded_file is None:
        return {"nama": "-", "alamat": "-", "umur": "-"}
    
    # Konversi file upload streamlit ke format OpenCV image
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    
    # Putar gambar KTP agar tegak lurus
    img_ready = perbaiki_posisi_ktp(img)
    result = reader.readtext(img_ready, detail=0)
    
    nama = "-"
    alamat_komponen = []
    umur = "-"
    
    for i, teks in enumerate(result):
        teks_clean = teks.upper().strip()
        
        # Ekstrak Nama
        if 'NAMA' in teks_clean and i + 1 < len(result):
            nama_mentah = result[i + 1].replace(':', '').strip()
            nama = re.sub(r'[^A-Z\s]', '', nama_mentah.upper()).strip()
            
        # Ekstrak Komponen Alamat
        if any(kwd in teks_clean for kwd in ['ALAMAT', 'RT/', 'KEL/', 'KECAMATAN']):
            text_val = teks.split(':')[-1].strip()
            if text_val and not any(k in text_val.upper() for k in ['SEUMUR', 'KAWIN', 'ISLAM', 'KERJA', 'DARAH', 'WARGA']):
                alamat_komponen.append(text_val.upper())

        # Ekstrak Umur dari Tanggal Lahir
        if 'LAHIR' in teks_clean or 'TGL' in teks_clean:
            match_tgl = re.search(r'(\d{2})[-/\s](\d{2})[-/\s](\d{4})', teks_clean)
            if match_tgl:
                tahun_lahir = int(match_tgl.group(3))
                tahun_sekarang = datetime.now().year
                umur = f"{tahun_sekarang - tahun_lahir} TH"

    alamat_final = " ".join(alamat_komponen)
    alamat_final = re.sub(r'\s+', ' ', alamat_final).strip()
    
    return {"nama": nama, "alamat": alamat_final, "umur": umur}

def cek_hubungan_dari_kk(uploaded_file_kk):
    if uploaded_file_kk is None:
        return "SUAMI ISTRI (Prediksi KTP)"
        
    file_bytes = np.asarray(bytearray(uploaded_file_kk.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    
    # KK diproses normal tanpa diputar
    result = reader.readtext(img, detail=0)
    teks_kk = " ".join(result).upper()
    
    if "ISTERI" in teks_kk or "ISTRI" in teks_kk:
        return "SUAMI ISTRI"
    elif "ANAK" in teks_kk and ("AYAH" in teks_kk or "IBU" in teks_kk or "KEPALA KELUARGA" in teks_kk):
        return "ORANG TUA / ANAK"
    elif "MERTUA" in teks_kk:
        return "MERTUA / MENANTU"
    
    return "KELUARGA"

# =====================================================================
# BAGIAN WIDGET UPLOAD PADA BROWSER
# =====================================================================
col1, col2 = st.columns(2)

with col1:
    uploaded_ktp_pemohon = st.file_uploader("📤 Upload KTP Pemohon", type=["png", "jpg", "jpeg"])

with col2:
    uploaded_ktp_penjamin = st.file_uploader("📤 Upload KTP Penjamin", type=["png", "jpg", "jpeg"])

uploaded_kk = st.file_uploader("📤 Upload Kartu Keluarga (KK) - Opsional", type=["png", "jpg", "jpeg"])

# Tombol untuk memulai proses analisis teks
if st.button("🚀 Proses & Buat Laporan", type="primary"):
    if uploaded_ktp_pemohon and uploaded_ktp_penjamin:
        with st.spinner("Sedang membaca dokumen dengan OCR... Mohon tunggu..."):
            
            # Jalankan fungsi ekstraksi data
            data_pemohon = ekstrak_data_ktp(uploaded_ktp_pemohon, "Pemohon")
            data_penjamin = ekstrak_data_ktp(uploaded_ktp_penjamin, "Penjamin")
            status_hubungan = cek_hubungan_dari_kk(uploaded_kk)
            
            # Formulasi format teks laporan
            laporan_text = f"""• Pemohon : {data_pemohon['nama']}
• Penjamin : {data_penjamin['nama']}
• Alamat Survey / tinggal : {data_pemohon['alamat']}
• Alamat KTP : {data_pemohon['alamat']}
• Umur pemohon : {data_pemohon['umur']}
• Umur penjamin : {data_penjamin['umur']}
• Stts hubungan : {status_hubungan}"""
            
            st.success("Analisis Selesai!")
            
            # 1. TAMPILAN FORMAT TEKS (Bisa langsung di-copy paste)
            st.subheader("📋 Format Teks Laporan")
            st.text_area("Klik kanan/blok untuk salin teks di bawah:", laporan_text, height=200)
            
            # 2. TAMPILAN DATA TABEL
            st.subheader("📊 Preview Tabel Data")
            data_excel = {
                "Kategori Laporan": ["Pemohon", "Penjamin", "Alamat Survey", "Alamat KTP", "Umur Pemohon", "Umur Penjamin", "Status Hubungan"],
                "Isi Data": [
                    data_pemohon['nama'], 
                    data_penjamin['nama'], 
                    data_pemohon['alamat'], 
                    data_pemohon['alamat'], 
                    data_pemohon['umur'], 
                    data_penjamin['umur'], 
                    status_hubungan
                ]
            }
            df = pd.DataFrame(data_excel)
            st.dataframe(df, use_container_width=True)
            
            # 3. TOMBOL DOWNLOAD EXCEL OTOMATIS
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer_excel:
                df.to_excel(writer_excel, index=False)
            
            st.download_button(
                label="📥 Download Laporan Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Laporan_Survey_{data_pemohon['nama'].replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    else:
        st.error("⚠️ Mohon upload kedua file KTP terlebih dahulu sebelum memproses!")
