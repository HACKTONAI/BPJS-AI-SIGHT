"""
Worker: baca Redis Stream `visits`, simpan ke SQLite, jalankan Prophet per faskes
Setiap kali batch_size event per faskes terkumpul (atau interval waktu), worker
akan membangun history DataFrame untuk faskes tersebut, melatih Prophet, dan
menyimpan forecast ke DB serta snapshot ke Redis.

Cara pakai:
- Pastikan Redis berjalan pada localhost:6379
- Jalankan `python db_models.py` sekali untuk membuat DB
- Jalankan worker: `python worker_redis.py`
- Jalankan producer untuk mengirim event (lihat `producer_redis.py`)
"""
import redis
import json
import time
from datetime import datetime, timedelta
import pandas as pd
from prophet import Prophet
from sqlalchemy.orm import Session
from db_models import Visit, Forecast, SessionLocal, init_db

# Konfigurasi
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
STREAM_KEY = 'visits'
GROUP_NAME = 'worker_group'
CONSUMER_NAME = 'worker_1'
BATCH_SIZE = 20  # jalankan forecast setelah batch size event per faskes
FORECAST_DAYS = 14
SNAPSHOT_KEY_PREFIX = 'forecast_snapshot:'

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


def ensure_group():
    try:
        r.xgroup_create(STREAM_KEY, GROUP_NAME, id='0', mkstream=True)
        print('Created group', GROUP_NAME)
    except redis.exceptions.ResponseError as e:
        # group probably exists
        print('Group exists or error:', e)


def parse_record(fields):
    # fields: dict of bytes -> bytes
    parsed = {}
    for k, v in fields.items():
        k = k.decode() if isinstance(k, bytes) else k
        if isinstance(v, bytes):
            try:
                parsed[k] = v.decode()
            except Exception:
                parsed[k] = v
        else:
            parsed[k] = v
    return parsed


def save_visit_to_db(session: Session, rec: dict):
    try:
        ds = datetime.fromisoformat(rec['ds']).date()
    except Exception:
        ds = datetime.utcnow().date()
    visit = Visit(ds=ds,
                  y=int(rec.get('y', 0)),
                  nama_faskes=rec.get('nama_faskes', 'unknown'),
                  kapasitas=int(rec.get('kapasitas', 100)),
                  jarak=float(rec.get('jarak', 1.0)))
    session.add(visit)
    session.commit()


def run_forecast_for_faskes(session: Session, nama_faskes: str):
    print('Running forecast for', nama_faskes)
    q = session.query(Visit).filter(Visit.nama_faskes == nama_faskes).order_by(Visit.ds)
    rows = q.all()
    if not rows:
        print('No history for', nama_faskes)
        return
    df = pd.DataFrame([{'ds': r.ds, 'y': r.y} for r in rows])
    df['ds'] = pd.to_datetime(df['ds'])

    # training
    try:
        model = Prophet(daily_seasonality=True, yearly_seasonality=False)
        model.fit(df)
    except Exception as e:
        print('Error training model:', e)
        return

    future = model.make_future_dataframe(periods=FORECAST_DAYS)
    forecast = model.predict(future)
    now = datetime.utcnow()

    # Simpan forecast ke DB (hapus forecast lama untuk faskes dan rentang ds?)
    # Simpel: insert forecast rows
    for _, row in forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].iterrows():
        rec = Forecast(nama_faskes=nama_faskes,
                       ds=row['ds'].date(),
                       yhat=float(row['yhat']),
                       yhat_lower=float(row['yhat_lower']),
                       yhat_upper=float(row['yhat_upper']),
                       generated_at=now)
        session.add(rec)
    session.commit()

    # Simpan snapshot ke Redis (mis: next 7-day summary)
    try:
        next_day = (datetime.utcnow().date() + timedelta(days=1)).isoformat()
        next_pred = forecast[forecast['ds'].dt.date == datetime.utcnow().date() + timedelta(days=1)]
        if not next_pred.empty:
            yhat = float(next_pred['yhat'].iloc[0])
        else:
            yhat = float(forecast['yhat'].iloc[0])
        snapshot = {
            'nama_faskes': nama_faskes,
            'next_date': next_day,
            'next_yhat': yhat,
            'generated_at': now.isoformat()
        }
        r.set(SNAPSHOT_KEY_PREFIX + nama_faskes, json.dumps(snapshot))
    except Exception as e:
        print('Failed to write snapshot to Redis:', e)


def main_loop():
    init_db()
    ensure_group()
    db = SessionLocal()

    # per-faskes counter
    counters = {}

    print('Worker started, listening to stream', STREAM_KEY)
    while True:
        try:
            # baca batch (blocking XREADGROUP)
            resp = r.xreadgroup(GROUP_NAME, CONSUMER_NAME, {STREAM_KEY: '>'}, count=10, block=5000)
            if not resp:
                # timeout, consider running scheduled forecasts? continue
                continue
            for stream_key, messages in resp:
                for msg_id, fields in messages:
                    parsed = parse_record(fields)
                    # simpan ke DB
                    save_visit_to_db(db, parsed)

                    name = parsed.get('nama_faskes', 'unknown')
                    counters[name] = counters.get(name, 0) + 1

                    # ack the message
                    try:
                        r.xack(STREAM_KEY, GROUP_NAME, msg_id)
                    except Exception as e:
                        print('xack error', e)

                    if counters[name] >= BATCH_SIZE:
                        # jalankan forecast untuk faskes ini
                        run_forecast_for_faskes(db, name)
                        counters[name] = 0
        except Exception as e:
            print('Worker loop error:', e)
            time.sleep(2)


if __name__ == '__main__':
    main_loop()
