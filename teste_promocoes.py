from tools import best_promotions

res = best_promotions(
    id_usuario=2,           # troque para seu id real
    radius_km=50,
    max_results=5,
    product_like="leite"
)

print(res.ok, res.status)
print(res.data)
