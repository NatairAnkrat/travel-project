import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import psycopg2

app = FastAPI()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "traveldb"),
    "user": os.getenv("DB_USER", "appuser"),
    "password": os.getenv("DB_PASSWORD", ""),
}


@app.get("/health")
def health():
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=3)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": str(e)},
        )