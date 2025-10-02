import os
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

print("Teste iniciado...")

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASS = os.getenv("MYSQL_PASS")
MYSQL_DB   = os.getenv("MYSQL_DB")

print("MYSQL_HOST =", MYSQL_HOST)
print("MYSQL_USER =", MYSQL_USER)

try:
    conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASS,
        db=MYSQL_DB,
        cursorclass=DictCursor
    )

    print("Conexão estabelecida com sucesso!")

    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM tbl_promocao LIMIT 5;")
        rows = cursor.fetchall()
        print("Resultados:", rows)

except Exception as e:
    print("❌ Erro ao conectar ou consultar:", e)
finally:
    if "conn" in locals() and conn:
        conn.close()
        print("Conexão encerrada.")
