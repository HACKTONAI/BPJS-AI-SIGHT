import redis
import time
import json
from datetime import datetime, timedelta
import random

r = redis.Redis(host='127.0.0.1', port=6379, db=0)
STREAM_KEY = 'visits'

FASKES = [
    {"nama": "Faskes A (Puskesmas Kota)", "kapasitas": 150, "jarak": 1.2},
    {"nama": "Faskes B (Klinik Sehat)", "kapasitas": 80, "jarak": 3.5},
    {"nama": "Faskes C (RSUD Tipe D)", "kapasitas": 200, "jarak": 5.0}
]

def produce_once(days_back=30):
    """Publikasikan beberapa record historis (hari demi hari) untuk demo."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=days_back-1)
    for f in FASKES:
        base = random.randint(20, 120)
        for i in range(days_back):
            d = start + timedelta(days=i)
            weekly = 30 if d.weekday() == 0 else 0
            noise = random.randint(-10, 15)
            y = max(5, base + weekly + noise)
            obj = {
                'ds': d.isoformat(),
                'y': int(y),
                'nama_faskes': f['nama'],
                'kapasitas': f['kapasitas'],
                'jarak': f['jarak']
            }
            r.xadd(STREAM_KEY, obj)
    print('Produced historical data to stream:', STREAM_KEY)


def produce_stream_forever(interval_seconds=5):
    """Secara terus menerus menghasilkan insiden baru setiap beberapa detik."""
    while True:
        f = random.choice(FASKES)
        now = datetime.utcnow().date().isoformat()
        noise = random.randint(-5, 10)
        y = max(1, f.get('base', 20) + noise) if 'base' in f else max(1, 20 + noise)
        obj = {
            'ds': now,
            'y': int(y),
            'nama_faskes': f['nama'],
            'kapasitas': f['kapasitas'],
            'jarak': f['jarak']
        }
        r.xadd(STREAM_KEY, obj)
        print('Produced event', obj)
        time.sleep(interval_seconds)

if __name__ == '__main__':
    produce_once()
    # uncomment to produce continuous events
    # produce_stream_forever()
