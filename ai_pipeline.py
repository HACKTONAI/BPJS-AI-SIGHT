"""
AI Pipeline (offline/demo)
- Generate dummy history for multiple faskes
- Save visits into SQLite (via db_models)
- Train Prophet per faskes, evaluate on holdout, forecast next N days
- Save forecasts into DB and serialize trained model to disk (models/)

Usage:
    python ai_pipeline.py --days-back 365 --forecast-days 14

"""
import os
import argparse
from datetime import datetime
import numpy as np
import pandas as pd
import pickle

from prophet import Prophet
from db_models import init_db, SessionLocal, Visit, Forecast

MODEL_DIR = "models"


def generate_dummy_data(days_back=365):
    dates = pd.date_range(end=datetime.today(), periods=days_back)
    faskes_list = [
        {"nama": "Faskes A (Puskesmas Kota)", "kapasitas": 150, "jarak": 1.2, "base": 100},
        {"nama": "Faskes B (Klinik Sehat)", "kapasitas": 80, "jarak": 3.5, "base": 40},
        {"nama": "Faskes C (RSUD Tipe D)", "kapasitas": 200, "jarak": 5.0, "base": 140}
    ]

    all_history = []
    for f in faskes_list:
        base_val = f['base']
        daily_pattern = np.random.randint(-20, 20, size=days_back)
        weekly_pattern = np.array([30 if i % 7 == 0 else 0 for i in range(days_back)])
        jumlah_pasien = base_val + daily_pattern + weekly_pattern
        jumlah_pasien = np.maximum(jumlah_pasien, 1)
        df = pd.DataFrame({'ds': dates, 'y': jumlah_pasien})
        df['nama_faskes'] = f['nama']
        df['kapasitas'] = f['kapasitas']
        df['jarak'] = f['jarak']
        all_history.append(df)
    return pd.concat(all_history).reset_index(drop=True), faskes_list


def save_visits_to_db(df):
    session = SessionLocal()
    try:
        # optionally clear previous visits for demo clarity
        # session.query(Visit).delete(); session.commit()
        for _, r in df.iterrows():
            v = Visit(ds=r['ds'].date(), y=int(r['y']), nama_faskes=r['nama_faskes'], kapasitas=int(r['kapasitas']), jarak=float(r['jarak']))
            session.add(v)
        session.commit()
    finally:
        session.close()


def train_and_forecast(nama_faskes, forecast_days=14, holdout_days=14):
    session = SessionLocal()
    try:
        # load history from DB
        rows = session.query(Visit).filter(Visit.nama_faskes == nama_faskes).order_by(Visit.ds).all()
        if not rows:
            print(f"No history for {nama_faskes}")
            return None
        df = pd.DataFrame([{'ds': r.ds, 'y': r.y} for r in rows])
        df['ds'] = pd.to_datetime(df['ds'])

        # define train/holdout
        if len(df) <= holdout_days:
            train_df = df
            holdout_df = pd.DataFrame(columns=df.columns)
        else:
            train_df = df.iloc[:-holdout_days]
            holdout_df = df.iloc[-holdout_days:]

        # train Prophet
        model = Prophet(daily_seasonality=True, yearly_seasonality=False)
        model.fit(train_df[['ds','y']])

        # forecast for the combined horizon (holdout + future)
        periods = holdout_days + forecast_days
        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)

        # evaluate on holdout (if available)
        metrics = {}
        if not holdout_df.empty:
            # join forecast with holdout by date
            merged = forecast.merge(holdout_df.rename(columns={'ds':'ds_hold','y':'y_actual'}), left_on='ds', right_on='ds_hold', how='inner')
            if not merged.empty:
                # compute MAE on the overlapping part
                merged['abs_err'] = (merged['yhat'] - merged['y_actual']).abs()
                mae = merged['abs_err'].mean()
                metrics['mae_holdout'] = float(mae)
            else:
                metrics['mae_holdout'] = None
        else:
            metrics['mae_holdout'] = None

        # Save forecast rows for next forecast_days (we take the tail)
        forecast_tail = forecast[['ds','yhat','yhat_lower','yhat_upper']].iloc[-forecast_days:]
        now = datetime.utcnow()
        for _, row in forecast_tail.iterrows():
            rec = Forecast(nama_faskes=nama_faskes, ds=row['ds'].date(), yhat=float(row['yhat']), yhat_lower=float(row['yhat_lower']), yhat_upper=float(row['yhat_upper']), generated_at=now)
            session.add(rec)
        session.commit()

        # persist model to disk
        os.makedirs(MODEL_DIR, exist_ok=True)
        model_path = os.path.join(MODEL_DIR, f"model_{sanitize_filename(nama_faskes)}.pkl")
        with open(model_path, 'wb') as fh:
            pickle.dump(model, fh)

        return {'nama_faskes': nama_faskes, 'metrics': metrics, 'model_path': model_path}
    finally:
        session.close()


def sanitize_filename(s: str) -> str:
    return ''.join(c if c.isalnum() else '_' for c in s)


def main(args):
    print('Initializing DB...')
    init_db()
    print('Generating dummy data...')
    df, faskes = generate_dummy_data(days_back=args.days_back)
    print('Saving visits to DB...')
    save_visits_to_db(df)

    results = []
    for f in faskes:
        print(f"Training + forecasting for {f['nama']}...")
        res = train_and_forecast(f['nama'], forecast_days=args.forecast_days, holdout_days=args.holdout_days)
        if res:
            results.append(res)
            print('Result:', res)

    print('\nSummary:')
    for r in results:
        print(r['nama_faskes'], r['metrics'], 'model:', r['model_path'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--days-back', type=int, default=365)
    parser.add_argument('--forecast-days', type=int, default=14)
    parser.add_argument('--holdout-days', type=int, default=14)
    args = parser.parse_args()
    main(args)
