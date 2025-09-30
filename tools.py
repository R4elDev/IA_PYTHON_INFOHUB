# tools.py
from __future__ import annotations
from typing import Any, Dict, Optional, List, Tuple
from pydantic import BaseModel
import os, math
import pymysql
from pymysql.cursors import DictCursor
from datetime import date
from decimal import Decimal

# ========= CONFIG BANCO =========
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASS = os.getenv("MYSQL_PASS", "")
MYSQL_DB   = os.getenv("MYSQL_DB", "db_infohub")

def _conn():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
        password=MYSQL_PASS, db=MYSQL_DB, cursorclass=DictCursor
    )

# ========= MODELO RETORNO =========
class ToolResult(BaseModel):
    ok: bool
    status: int
    data: Any

# ========= GEO =========
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
    return 2*R*math.asin(math.sqrt(a))

def _to_float(x) -> float:
    if isinstance(x, Decimal):
        return float(x)
    return float(x)

def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ========= 1) sql_query: leitura segura =========
def sql_query(query: str, params: Optional[Dict[str, Any]] = None) -> ToolResult:
    """
    Apenas SELECT (leitura).
    Ex.: sql_query("SELECT nome FROM tbl_categoria WHERE id_categoria=%(id)s", {"id":1})
    """
    try:
        if not query.strip().lower().startswith("select"):
            return ToolResult(ok=False, status=400, data="Apenas SELECT é permitido nesta ferramenta.")
        with _conn() as cx, cx.cursor() as cur:
            cur.execute(query, params or {})
            rows = cur.fetchall()
        return ToolResult(ok=True, status=200, data=rows)
    except Exception as e:
        return ToolResult(ok=False, status=400, data=str(e))

# ========= helper: pegar lat/lng do usuário =========
def _user_coords(id_usuario: int) -> Optional[Tuple[float, float]]:
    try:
        with _conn() as cx, cx.cursor() as cur:
            cur.execute("""
                SELECT latitude, longitude
                FROM tbl_enderecoUsuario
                WHERE id_usuario=%s
                ORDER BY id_endereco DESC
                LIMIT 1
            """, (id_usuario,))
            row = cur.fetchone()
            if row and row["latitude"] is not None and row["longitude"] is not None:
                return float(row["latitude"]), float(row["longitude"])
            return None
    except Exception:
        return None

# ========= 2) best_promotions: preço + distância =========
def best_promotions(
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    id_usuario: Optional[int] = None,
    radius_km: float = 10.0,
    max_results: int = 10,
    max_price: Optional[float] = None,          # DECIMAL(10,2)
    category_name: Optional[str] = None,        # tbl_categoria.nome
    product_like: Optional[str] = None          # LIKE em tbl_produto.nome
) -> ToolResult:
    """
    Lê promoções ativas (data_inicio <= hoje <= data_fim),
    junta com produto/categoria/estabelecimento/endereço,
    filtra por raio (em Python) e ranqueia por preço e distância.
    """
    try:
        # Resolve localização do usuário
        if (user_lat is None or user_lng is None) and id_usuario is not None:
            coords = _user_coords(id_usuario)
            if coords:
                user_lat, user_lng = coords
        if user_lat is None or user_lng is None:
            return ToolResult(ok=False, status=400, data="Endereço não encontrado. Cadastre um endereço no seu perfil.")

        today = date.today().isoformat()
        sql = """
        SELECT 
            promo.id_promocao,
            prod.id_produto, prod.nome AS produto,
            cat.nome AS categoria,
            est.id_estabelecimento, est.nome AS estabelecimento,
            endest.cidade, endest.estado, endest.latitude, endest.longitude,
            promo.preco_promocional, promo.data_inicio, promo.data_fim
        FROM tbl_promocao AS promo
        JOIN tbl_produto AS prod ON prod.id_produto = promo.id_produto
        LEFT JOIN tbl_categoria AS cat ON cat.id_categoria = prod.id_categoria
        JOIN tbl_estabelecimento AS est ON est.id_estabelecimento = promo.id_estabelecimento
        JOIN tbl_enderecoEstabelecimento AS endest ON endest.id_estabelecimento = est.id_estabelecimento
        WHERE promo.data_inicio <= %s AND promo.data_fim >= %s
        """
        params: List[Any] = [today, today]

        if category_name:
            sql += " AND cat.nome = %s"
            params.append(category_name)

        if max_price is not None:
            sql += " AND promo.preco_promocional <= %s"
            params.append(max_price)

        if product_like:
            sql += " AND prod.nome LIKE %s"
            params.append(f"%{product_like}%")

        sql += " ORDER BY promo.preco_promocional ASC LIMIT 1000"

        with _conn() as cx, cx.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        candidatas: List[Dict[str, Any]] = []
        for r in rows:
            lat, lng = r["latitude"], r["longitude"]
            if lat is None or lng is None:
                continue
            d = _haversine_km(float(user_lat), float(user_lng), float(lat), float(lng))
            if d <= radius_km:
                item = dict(r)
                item["distance_km"] = round(d, 2)
                candidatas.append(item)

        # ranqueia por preço e distância
        candidatas.sort(key=lambda x: (_to_float(x["preco_promocional"]), x["distance_km"]))
        top = candidatas[:max_results]

        for r in top:
            r["preco_brl"] = _fmt_brl(_to_float(r["preco_promocional"]))
        return ToolResult(ok=True, status=200, data=top)

    except Exception as e:
        return ToolResult(ok=False, status=400, data=str(e))

# ========= 3) FAQ =========
_FAQ = {
    "o que é o sistema": "Encontramos promoções ativas perto de você e ranqueamos por preço e distância.",
    "como escolhem as promocoes": "Filtramos por validade, aplicamos raio a partir da sua localização e ordenamos por menor preço (desempate por distância).",
    "como informar minha localizacao": "Sua localização é obtida do seu endereço cadastrado. Cadastre um endereço no perfil para resultados locais.",
    "como filtrar por categoria": "Peça a categoria pelo nome (ex.: laticínios, bebidas, higiene).",
    "foco": "Sou um agente de promoções e dúvidas rápidas do sistema; não respondo fora desse tema."
}
def faq_answer(question: str) -> ToolResult:
    q = question.lower()
    for k, v in _FAQ.items():
        if k in q:
            return ToolResult(ok=True, status=200, data={"question": k, "answer": v})
    return ToolResult(ok=True, status=200, data={"answer": _FAQ["foco"]})

# ========= Registro =========
TOOL_REGISTRY = {
    "sql_query": sql_query,
    "best_promotions": best_promotions,
    "faq_answer": faq_answer,
}
