Arsitektur Realtime AI (Prototype)

Tujuan
- Menyediakan pipeline realtime/near-realtime untuk data kunjungan faskes.
- Menjalankan inference (forecast) secara terotomatis saat data baru masuk.
- Menyediakan snapshot hasil prediksi yang cepat diambil oleh konsumen (UI / service lain).

Komponen
1. Producer (data source)
   - Mempublish event kunjungan ke Redis Stream `visits`.
   - Event: {ds, y, nama_faskes, kapasitas, jarak}

2. Message broker: Redis Streams
   - Menyediakan transport sederhana untuk events.
   - Pilihan mudah untuk prototipe; mudah diganti ke Kafka/Redis Streams production.

3. Worker / Consumer (Inference)
   - Membaca events dari Redis Stream.
   - Menyimpan event ke database historis (SQLite untuk prototipe; ganti ke Postgres di produksi).
   - Men-trigger proses training/inference (Prophet) secara batch (mis. tiap N event atau tiap T detik).
   - Menyimpan hasil forecast ke tabel `forecasts` dan menulis snapshot singkat ke Redis key `forecast_snapshot:<nama_faskes>`.

4. Storage
   - Historical: SQLite (file `data.db`) pada prototipe.
   - Forecast results: tabel `forecasts` di SQLite + Redis snapshot untuk akses cepat.

5. Konsumen
   - UI atau service lain membaca snapshot Redis untuk menampilkan rekomendasi/alert atau membaca tabel `forecasts` untuk detail.

Alur (high level)
- Producer -> Redis Stream `visits` -> Worker (XREAD / XREADGROUP) -> simpan Visit -> jika batch terpenuhi -> ambil history -> fit Prophet -> tulis Forecasts -> update Redis snapshot

Keputusan desain
- Redis digunakan karena simple dan cepat; untuk durability/throughput tinggi gunakan Kafka.
- SQLite dipilih untuk kemudahan demo; pada produksi gunakan Postgres.
- Prophet untuk forecasting time-series harian (sudah dipakai di `aitester.py`), worker menjadwalkan retrain per-faskes.

Pertimbangan
- Jaga ukuran history saat training (windowing) untuk performa.
- Gunakan batching/time-based triggers agar tidak melatih model untuk setiap event.
- Simpan model (pickle) bila training mahal, gunakan incremental retraining atau warm-start.
