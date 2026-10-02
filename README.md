# AdRadar Lite Desktop · Turbo DOM

Bot Python khusus **Meta Ads Library → URL tujuan + link iklan → CSV**. Tampilan desktop Tkinter; satu browser Firefox untuk scraper. Tidak menggunakan dashboard web, FastAPI, HTTPX, Shopee Bulk, AI, atau login Affiliate.

## Windows — cara pakai

1. Instal Python **3.11 atau lebih baru** dengan Python Launcher (`py`) dan komponen Tcl/Tk.
2. Ekstrak seluruh ZIP ke folder baru. Paket desktop ini terpisah dari versi web sebelumnya.
3. Jalankan `install_windows.bat` satu kali untuk memasang Playwright dan Firefox khusus Playwright.
4. Jalankan `start_windows.bat`.
5. Tempel URL pencarian Ads Library lengkap. Gunakan URL yang sudah memiliki filter `active_status=active`, negara, halaman, keyword, dan urutan yang dibutuhkan. Aplikasi mempertahankan filter URL yang dimasukkan.
6. Isi nama sesi, pilih mode browser, lalu **Start sesi baru**.
7. Pilih sesi di History, lalu **Export CSV** kapan saja. CSV selalu mengambil seluruh hasil tersimpan pada snapshot ekspor, bukan hanya halaman tabel.

File sumber saja, belum berupa EXE. Pengguna tidak perlu memasang ekstensi Chrome. Instalasi memerlukan internet. Firefox Playwright diunduh terpisah, sehingga ukuran ZIP source bukan ukuran total instalasi.

## Pengaturan ringan

- **Headless** aktif secara default: jendela Firefox disembunyikan. Jendela aplikasi tetap tampil.
- **Blokir gambar/video/font** aktif secara default; JavaScript dan CSS tetap dimuat agar halaman bisa bekerja. Jika tampilan atau pengambilan tidak sesuai, Stop, matikan blokir media, kemudian lanjutkan sesi.
- **Buka detail ringkasan** nonaktif secara default untuk mengurangi klik dan dialog. Iklan yang hanya muncul di dalam grup mungkin tidak terambil saat fitur ini mati. Aktifkan bila perlu cakupan grup tambahan.
- Jeda scroll default **2 detik**. Dapat diatur 0,5–30 detik; terlalu cepat bisa mendahului lazy loading Meta.
- Saat posisi scroll, tinggi halaman, dan ID kartu tidak berubah selama 12 putaran, bot menunggu di posisi terakhir tanpa reload. Jeda bertahap sampai 300 detik lalu mencoba scroll kecil. Kartu duplikat atau tanpa URL tidak memicu pengulangan dari atas.
- Tidak ada batas jumlah scroll atau jumlah hasil. Bot terus bekerja/menunggu sampai Stop atau aplikasi ditutup; komputer tidur/mati tetap menghentikan proses OS.
- Timeout operasi di dalam loop dicoba ulang di halaman yang sama. Error lain yang keluar dari loop (termasuk browser tertutup/crash) memicu pembukaan browser dan pencarian ulang setelah 30 detik. Ini tidak melewati login/CAPTCHA. Untuk melihat penyebabnya, Stop lalu lanjutkan dengan Headless dimatikan.

**Mode Turbo DOM:** extractor sekarang stateful/incremental. Scan penuh hanya dilakukan sekali saat mulai; sesudah itu MutationObserver mengantrekan bagian DOM yang baru/berubah. Ad ID lama tidak lagi dikirim ulang ke Python setiap putaran. Card yang terdeteksi diberi `content-visibility:auto` agar browser dapat melewati render card off-screen tanpa menghapus DOM React. SQLite memakai WAL + `synchronous=NORMAL`, write status didebounce, hasil disimpan per batch, tabel tetap manual 100 baris, dan ekspor bertahap 1.000 baris. Halaman Meta sendiri masih dapat bertambah besar selama scroll sangat panjang, tetapi biaya extractor tidak lagi tumbuh karena memindai seluruh dokumen pada setiap scroll.

## Hasil dan deduplikasi

CSV tepat dua kolom:

```csv
Destination URL,Link Iklan Aktif
https://s.shopee.co.id/AbCdE,https://www.facebook.com/ads/library/?id=123456789012345
```

- URL tujuan mempertahankan query, kapitalisasi path, dan fragment yang dibaca browser. Link redirect Facebook dibuka parameternya; bot tidak mengunjungi URL tujuan.
- Deduplikasi berdasarkan pasangan **Ad ID + URL tujuan**. URL sama milik dua iklan tetap dua baris.
- Header `Link Iklan Aktif` dipertahankan sesuai kebutuhan export. Link adalah link detail iklan; header tidak membuktikan iklan masih aktif. Pilih filter active di URL sumber. Bot ini tidak melakukan pengecekan status ulang untuk setiap hasil lama.
- Konten publik yang tidak terbaca, grup yang tidak dibuka, atau selector yang berubah dapat menyebabkan hasil tidak lengkap. Nol tambahan hasil bukan bukti seluruh iklan sudah terambil.

## History, Stop, dan melanjutkan

- Hasil otomatis disimpan di `data/lite.sqlite3`.
- Stop membatalkan task, menutup Firefox, dan mempertahankan hasil. Penutupan bisa membutuhkan beberapa detik.
- **Lanjutkan sesi terpilih** memakai URL sesi lama dan pengaturan yang sekarang terlihat di form. Pencarian diulang dari atas, hasil lama dideduplikasi. Posisi scroll tidak disimpan.
- Perubahan pengaturan berlaku saat Start/Lanjutkan berikutnya.
- History menampilkan 100 sesi per halaman. Gunakan tombol panah untuk sesi lainnya.
- Tab **Lihat hasil** hanya memuat data saat tombol Muat hasil/panah diklik. Tidak ada render tabel penuh tiap detik.
- Hapus hanya sesi terpilih; sesi yang masih berjalan harus di-Stop lebih dulu.
- Untuk backup, tutup aplikasi lalu salin seluruh folder `data`.
- Satu aplikasi per folder data; instance kedua ditolak dengan file lock OS. Sesudah crash, hasil yang sudah commit tetap tersimpan.
- Database versi web `adradar.sqlite3` tidak kompatibel langsung dengan database Lite desktop; jangan menimpanya. Hasil versi web tetap dapat diekspor memakai aplikasi web lama.

## Linux / macOS

Butuh Python 3.11+, Tkinter dan desktop/display (meskipun browser headless, GUI aplikasi tetap membutuhkan display).

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install firefox
.venv/bin/python run.py
```

Linux mungkin memerlukan paket Tkinter dari distribusi serta dependensi browser melalui `.venv/bin/python -m playwright install --with-deps firefox`.

Opsional: environment variable `ADRADAR_LITE_DATA` mengubah folder database.

## Pengujian

Dari folder paket dengan virtual environment aktif:

```bash
python -m unittest discover -s tests -v
```

Tes memakai database sementara dan browser mock, tidak mengakses akun atau mengambil iklan live. Rincian pengujian terdapat pada `VALIDASI.md`.

## Struktur

- `run.py`: launcher dan single-instance lock.
- `lite/gui.py`: antarmuka desktop.
- `lite/bot.py`: thread scraper, loop async, retry, cancel, Firefox.
- `lite/storage.py`: SQLite, history, deduplikasi dan streaming CSV.
- `lite/extract_meta.js`: pembacaan DOM, diadaptasi dari ekstensi pengguna dan dipangkas untuk Lite.
- `lite/summary.py`: pembukaan grup opsional dengan penanganan timeout.

Referensi: [Playwright Python browsers](https://playwright.dev/python/docs/browsers). Mesin browser masih dibutuhkan karena Ads Library dirender secara dinamis.

## Perbaikan reload
Auto-reload karena stagnasi telah dihapus. Mode menunggu tidak menyatakan semua iklan berhasil diambil; loading, dialog, atau verifikasi bisa menghalangi progres. Stop tetap membatalkan waktu tunggu. Tidak ada jaminan memperoleh seluruh angka hasil yang ditampilkan Meta.

Pembaruan: Stop dan tutup aplikasi lama, cadangkan folder `data`, lalu timpa file program dengan isi ZIP ini. Jangan hapus folder `data` agar history tetap ada. Memulai ulang aplikasi/sesi masih membuka pencarian dari atas; perbaikan ini mempertahankan posisi selama halaman yang sama masih terbuka, bukan resume posisi lintas restart.


## Turbo update 2026-09-22

- Extractor incremental dengan `MutationObserver`; tidak lagi `TreeWalker(document.body)` setiap putaran.
- Cache pasangan Ad ID + destination URL berada di halaman dan hanya baris baru yang dikirim ke Python.
- Deteksi stagnasi memakai counter generasi kartu, bukan daftar seluruh Ad ID.
- Update count UI ditahan maksimal sekitar 1 kali/detik saat burst.
- Status database hanya ditulis bila berubah.
- Optimasi render off-screen memakai `content-visibility:auto`; tidak melakukan reload atau menghapus card React.
