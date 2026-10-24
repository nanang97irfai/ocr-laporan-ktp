import streamlit as st
import cv2
import easyocr
import re
import numpy as np
import pandas as pd
from datetime import datetime

# Konfigurasi Halaman Web
st.set_page_config(page_title="OCR Kamera Langsung KTP & KK", layout="centered")

st.title("📝 OCR KTP & KK + Kamera Langsung Android")
st.write("Ambil foto dokumen langsung dari kamera HP atau unggah dari galeri untuk mengisi laporan otomatis.")

# Inisialisasi EasyOCR (Cached agar hemat RAM)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['id'], gpu=False)

reader = load_ocr()

def auto_rotate_ocr(img):
    """
    Memutar gambar ke 4 sudut untuk mencari posisi terbaik 
    yang memiliki pembacaan kata kunci KTP terbanyak.
    """
    sudut_rotasi = [
        (0, img),                                      # Normal
        (90, cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)), # Miring Kiri
        (180, cv2.rotate(img, cv2.ROTATE_180)),         # Terbalik
        (270, cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)) # Miring Kanan
    ]
    
    skor_terbaik = -1
    hasil_terbaik = []
    gambar_terbaik = img
    
    for sudut, img_uji in sudut_rotasi:
        result = reader.readtext(img_uji, detail=0)
        teks_gabung = " ".join(result).upper()
        
        skor = 0
        kata_kunci = ['NAMA', 'NIK', 'ALAMAT', 'LAHIR', 'AGAMA', 'KAWIN', 'PROVINSI', 'KABUPATEN', 'KECAMATAN']
        for kw in kata_kunci:
            if kw in teks_gabung:
                skor += 1
                
        if skor > skor_terbaik:
            skor_terbaik = skor
            hasil_terbaik = result
            gambar_terbaik = img_uji
            
    return hasil_terbaik, gambar_terbaik

def ekstrak_data_ktp(uploaded_file):
    if uploaded_file is None:
        return {"nama": "-", "alamat": "-", "umur": "-"}
    
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    
    # Jalankan Auto Rotate
    result, _ = auto_rotate_ocr(img)
    
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

        # Ekstrak Umur dari Tanggal Lahir (Menggunakan Tahun Berjalan: 2026)
        if 'LAHIR' in teks_clean or 'TGL' in teks_clean:
            match_tgl = re.search(r'(\d{2})[-/\s](\d{2})[-/\s](\d{4})', teks_clean)
            if match_tgl:
                tahun_lahir = int(match_tgl.group(3))
                umur = f"{2026 - tahun_lahir} TH"

    alamat_final = " ".join(alamat_komponen)
    alamat_final = re.sub(r'\s+', ' ', alamat_final).strip()
    
    return {"nama": nama, "alamat": alamat_final, "umur": umur}

def cek_hubungan_dari_kk(uploaded_file_kk):
    if uploaded_file_kk is None:
        return "SUAMI ISTRI (Prediksi KTP)"
        
    file_bytes = np.asarray(bytearray(uploaded_file_kk.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    
    result, _ = auto_rotate_ocr(img)
    teks_kk = " ".join(result).upper()
    
    if "ISTERI" in teks_kk or "ISTRI" in teks_kk:
        return "SUAMI ISTRI"
    elif "ANAK" in teks_kk and ("AYAH" in teks_kk or "IBU" in teks_kk or "KEPALA KELUARGA" in teks_kk):
        return "ORANG TUA / ANAK"
    elif "MERTUA" in teks_kk:
        return "MERTUA / MENANTU"
    
    return "KELUARGA"

# =====================================================================
# ANTARMUKA SELEKSI INPUT (GALERI / KAMERA)
# =====================================================================
input_method = st.radio("Pilih Metode Input Dokumen:", ["📸 Kamera HP Langsung", "📁 Unggah File/Galeri"], horizontal=True)

file_pemohon = None
file_penjamin = None
file_kk = None

if input_method == "📸 Kamera HP Langsung":
    st.subheader("1. Ambil Foto KTP Pemohon")
    file_pemohon = st.camera_input("Foto KTP Pemohon", key="cam_pemohon")
    
    st.subheader("2. Ambil Foto KTP Penjamin")
    file_penjamin = st.camera_input("Foto KTP Penjamin", key="cam_penjamin")
    
    st.subheader("3. Ambil Foto KK (Opsional)")
    file_kk = st.camera_input("Foto KK", key="cam_kk")

else:
    col1, col2 = st.columns(2)
    with col1:
        file_pemohon = st.file_uploader("📤 File KTP Pemohon", type=["png", "jpg", "jpeg"], key="file_pemohon")
    with col2:
        file_penjamin = st.file_uploader("📤 File KTP Penjamin", type=["png", "jpg", "jpeg"], key="file_penjamin")
        
    file_kk = st.file_uploader("📤 File Kartu Keluarga (KK) - Opsional", type=["png", "jpg", "jpeg"], key="file_kk")

# =====================================================================
# TOMBOL PROSES LAPORAN
# =====================================================================
if st.button("🚀 Proses & Buat Laporan", type="primary"):
    if file_pemohon and file_penjamin:
        with st.spinner("Sistem sedang menganalisis foto & mengekstrak data..."):
            
            data_pemohon = ekstrak_data_ktp(file_pemohon)
            data_penjamin = ekstrak_data_ktp(file_penjamin)
            status_hubungan = cek_hubungan_dari_kk(file_kk)
            
            laporan_text = f"""• Pemohon : {data_pemohon['nama']}
• Penjamin : {data_penjamin['nama']}
• Alamat Survey / tinggal : {data_pemohon['alamat']}
• Alamat KTP : {data_pemohon['alamat']}
• Umur pemohon : {data_pemohon['umur']}
• Umur penjamin : {data_penjamin['umur']}
• Stts hubungan : {status_hubungan}"""
            
            st.success("Proses Ekstraksi Berhasil!")
            
            # Output Teks Siap Copy
            st.subheader("📋 Format Teks Laporan")
            st.text_area("Salin teks di bawah ini:", laporan_text, height=200)
            
            # Pembuatan Tabel & Tombol Unduh Excel
            data_excel = {
                "Kategori Laporan": ["Pemohon", "Penjamin", "Alamat Survey", "Alamat KTP", "Umur Pemohon", "Umur Penjamin", "Status Hubungan"],
                "Isi Data": [data_pemohon['nama'], data_penjamin['nama'], data_pemohon['alamat'], data_pemohon['alamat'], data_pemohon['umur'], data_penjamin['umur'], status_hubungan]
            }
            df = pd.DataFrame(data_excel)
            
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer_excel:
                df.to_excel(writer_excel, index=False)
            
            st.download_button(
                label="📥 Download Laporan Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"Laporan_{data_pemohon['nama'].replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.error("⚠️ Mohon ambil foto atau unggah KTP Pemohon dan Penjamin terlebih dahulu!")
