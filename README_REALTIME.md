Realtime AI Prototype (Redis Streams + Prophet)

Overview
- This prototype demonstrates a realtime pipeline where incoming visit events are
  published to a Redis Stream. A worker consumes the stream, stores history in
  SQLite, runs Prophet forecasts per faskes in batches, and writes forecast
  results to the DB and a Redis snapshot key for fast reads.

Files created
- `ARCHITECTURE.md`  : design document
- `producer_redis.py` : simulate/publish events to Redis Stream `visits`
- `worker_redis.py`   : consumer, training/inference, snapshot writer
- `db_models.py`      : SQLAlchemy models and DB init
- `requirements.txt`  : updated requirements

Quickstart (Windows PowerShell)
1) Install dependencies (prefer virtualenv)
```powershell
cd "c:\Users\DELL\OneDrive\Documents\Engineering\AI Engineering"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Start Redis (Docker recommended)
```powershell
# If you have Docker for Desktop
docker run --name redis-local -p 6379:6379 -d redis:7
```
Or install Redis locally and run it.

3) Initialize DB
```powershell
python db_models.py
```

4) Start worker (consumer + inference)
```powershell
python worker_redis.py
```

5) Produce demo data
```powershell
python producer_redis.py
# optionally uncomment produce_stream_forever in the file to produce continuous events
```

6) Verify
- Redis snapshot keys: use `redis-cli` or `redis` python client to `GET forecast_snapshot:<nama_faskes>`.
- Check SQLite `data.db` and `forecasts` table.

Notes & next steps
- For production, replace SQLite with Postgres, run multiple worker instances with consumer groups, and consider model persistence to avoid retraining heavy models from scratch.
- Consider using Redis Streams consumer groups with proper pending-message handling and retries.
- For heavy workloads, use Kafka and a dedicated model-serving layer.
