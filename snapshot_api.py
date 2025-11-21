from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import redis
import json
from db_models import SessionLocal, Forecast
from datetime import datetime, date, timedelta

app = FastAPI(title="Forecast Snapshot API")

REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
SNAPSHOT_KEY_PREFIX = "forecast_snapshot:"

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

@app.get("/snapshots")
def list_snapshots():
    """List semua snapshot yang tersimpan di Redis (forecast_snapshot:*)."""
    try:
        keys = r.keys(SNAPSHOT_KEY_PREFIX + "*")
        out = []
        for k in keys:
            raw = r.get(k)
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                obj = {"raw": raw}
            # normalize: include key name
            obj['key'] = k
            out.append(obj)
        return JSONResponse(content=out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/snapshot/{nama_faskes}")
def get_snapshot(nama_faskes: str):
    """Ambil snapshot untuk satu faskes berdasarkan nama (case-sensitive).
    Nama faskes harus di-URL-encode jika mengandung spasi.
    """
    key = SNAPSHOT_KEY_PREFIX + nama_faskes
    try:
        raw = r.get(key)
        if not raw:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {"raw": raw}
        return JSONResponse(content=obj)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/forecasts/{nama_faskes}")
def get_forecasts(nama_faskes: str, days: int = 14):
    """Ambil barisan forecast dari DB untuk `nama_faskes` untuk `days` ke depan.
    Jika tidak ada data ditemukan, kembalikan 404.
    """
    session = SessionLocal()
    try:
        today = date.today()
        end = today + timedelta(days=days)
        q = session.query(Forecast).filter(Forecast.nama_faskes == nama_faskes, Forecast.ds >= today, Forecast.ds <= end).order_by(Forecast.ds)
        rows = q.all()
        if not rows:
            raise HTTPException(status_code=404, detail="No forecasts found for this faskes in the given range")
        out = []
        for rrow in rows:
            out.append({
                'nama_faskes': rrow.nama_faskes,
                'ds': rrow.ds.isoformat(),
                'yhat': rrow.yhat,
                'yhat_lower': rrow.yhat_lower,
                'yhat_upper': rrow.yhat_upper,
                'generated_at': rrow.generated_at.isoformat() if rrow.generated_at else None
            })
        return JSONResponse(content=out)
    finally:
        session.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9000)
