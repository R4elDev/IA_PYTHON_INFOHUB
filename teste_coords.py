import pymysql
from pymysql.cursors import DictCursor
import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASS = os.getenv("MYSQL_PASS", "")
MYSQL_DB   = os.getenv("MYSQL_DB", "db_infohub")

print("Conectando ao banco...")
conn = pymysql.connect(
    host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
    password=MYSQL_PASS, db=MYSQL_DB, cursorclass=DictCursor
)

with conn.cursor() as cursor:
    cursor.execute("""
        SELECT latitude, longitude, id_usuario
        FROM tbl_enderecoUsuario
        WHERE id_usuario = 1
        ORDER BY id_endereco DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    print("Resultado:", row)

conn.close()
