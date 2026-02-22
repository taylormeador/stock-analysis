from app.utils.tickers import TICKERS
import app.database.models as models
import app.database.db as db
from sqlalchemy import text


model = models.tickers
with db.get_connection() as conn:
    for ticker in TICKERS:
        sql = f"insert into tickers (ticker) values ('{ticker}')"
        conn.execute(text(sql))

    conn.commit()
