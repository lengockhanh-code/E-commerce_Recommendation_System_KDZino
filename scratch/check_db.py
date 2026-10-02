import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
dsn = os.environ.get("DATABASE_URL")
if dsn:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'orders'")
            print("orders table columns:")
            for col in cur.fetchall():
                print(" ", col)
            
            cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'order_items'")
            print("\norder_items table columns:")
            for col in cur.fetchall():
                print(" ", col)
