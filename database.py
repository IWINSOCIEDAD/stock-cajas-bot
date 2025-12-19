import sqlite3

DB_NAME = "stock.db"

def connect():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cajas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE,
        marca TEXT,
        color TEXT,
        cantidad INTEGER,
        ubicacion TEXT,
        fecha_actualizacion TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS historial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        accion TEXT,
        codigo TEXT,
        cantidad INTEGER,
        origen TEXT,
        destino TEXT,
        fecha TEXT
    )
    """)

    conn.commit()
    conn.close()
