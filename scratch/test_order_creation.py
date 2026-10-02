import os
import json
import uuid
import psycopg
from dotenv import load_dotenv

load_dotenv()
dsn = os.environ.get("DATABASE_URL")
order_id = str(uuid.uuid4())
user_id = "0f006f3d-2124-4518-8c10-0f93aedc020e"
item_id = "123456"

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        # Ensure product exists
        cur.execute("""
            INSERT INTO products (item_id, name, price, is_active)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (item_id) DO NOTHING
        """, (item_id, "Áo thun nam", 75000.0))

        # Insert order
        cur.execute("""
            INSERT INTO orders (id, user_id, status, total_amount, shipping_address, payment_method)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            order_id, user_id, "pending", 150000.0,
            json.dumps({"receiver": "Nguyễn Văn A"}), "cod"
        ))

        # Insert order item
        cur.execute("""
            INSERT INTO order_items (order_id, item_id, product_name, quantity, unit_price)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id, item_id, "Áo thun nam", 2, 75000.0))

        conn.commit()

print("Order creation test passed successfully! Order ID:", order_id)
