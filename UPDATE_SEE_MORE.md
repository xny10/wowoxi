# Perbaikan See more — 23 September 2026

- Otomatis klik See more / Lihat lainnya pada tombol lebar di bawah hasil yang terlihat dan tidak tertutup.
- Hindari tombol dalam artikel/dialog, tautan tujuan, tombol nonaktif, dan teks See more kecil di kartu iklan.
- Tunggu 15 detik sebelum mencoba klik berikutnya; ekstraksi tetap berjalan saat menunggu.
- Saat macet: cek ulang maksimal setiap 5 detik, coba scroll naik–turun tanpa reload.
- Periksa ulang node ID saat memasuki area layar melalui IntersectionObserver.
- Stop tetap membatalkan proses; format database dan CSV tetap kompatibel.

## Memasang pada instalasi lama

1. Export CSV sebagai cadangan, tekan Stop, lalu tutup aplikasi lama.
2. Cadangkan seluruh folder data di instalasi lama.
3. Ekstrak ZIP ini, lalu salin folder lite dari ZIP ke instalasi lama dan pilih replace files.
4. Jangan hapus atau timpa folder data. Jalankan start_windows.bat seperti biasa.
5. Pilih sesi lama dan klik Lanjutkan sesi terpilih.

Data tersimpan tetap ada dan pasangan URL–ID yang sama tidak dihitung ulang.
Browser yang dibuka kembali akan memuat halaman dari awal; ini bukan resume cursor Meta.
Jika memakai folder hasil ekstraksi sebagai instalasi baru, salin folder data lama ke folder AdRadar_Lite baru sebelum menjalankannya.

## Batas validasi

15 unit test Python lulus (database, ekspor, scroll, cooldown, Stop), 8 kasus seleksi tombol JavaScript sintetis lulus, kompilasi Python lulus.
Belum diuji pada sesi Meta langsung atau 3.000+ kartu. Seleksi tombol sengaja konservatif; perubahan layout Meta mungkin membutuhkan penyesuaian.
