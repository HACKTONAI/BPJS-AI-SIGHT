from fastapi import FastAPI
from datetime import datetime, timedelta
import random

app = FastAPI()

# Konfigurasi faskes sama seperti di aitester
FASKES = [
    {"nama": "Faskes A (Puskesmas Kota)", "kapasitas": 150, "jarak": 1.2},
    {"nama": "Faskes B (Klinik Sehat)", "kapasitas": 80, "jarak": 3.5},
    {"nama": "Faskes C (RSUD Tipe D)", "kapasitas": 200, "jarak": 5.0}
]

@app.get("/latest")
def latest(days: int = 30):
    """Mengembalikan data kunjungan terakhir untuk beberapa faskes.
    Format: list of {{ds, y, nama_faskes, kapasitas, jarak}}
    """
    end = datetime.utcnow().date()
    start = end - timedelta(days=days - 1)

    out = []
    for f in FASKES:
        base = random.randint(10, 140)
        for i in range(days):
            d = start + timedelta(days=i)
            # pola mingguan sederhana
            weekly = 30 if d.weekday() == 0 else 0
            noise = random.randint(-15, 20)
            y = max(5, base + weekly + noise)
            out.append({
                "ds": d.isoformat(),
                "y": int(y),
                "nama_faskes": f["nama"],
                "kapasitas": f["kapasitas"],
                "jarak": f["jarak"]
            })
    return out

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
