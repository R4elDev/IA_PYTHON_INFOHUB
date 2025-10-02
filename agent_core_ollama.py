import json
import re
import os
from typing import Dict, Any, Optional
import ollama
from tools import TOOL_REGISTRY, ToolResult
from memory import Memory

MODEL = os.getenv("MODEL", "gemma")

SYSTEM = """
Você é um agente especializado em PROMOÇÕES do InfoHub.
OBJETIVO: achar as MELHORES PROMOÇÕES considerando PREÇO e LOCALIZAÇÃO do usuário, e responder FAQs do sistema.
NUNCA peça coordenadas ao usuário. Se faltarem, use o id_usuario do CONTEXTO.
NUNCA saia desse foco. Fora do escopo, recuse educadamente.

Importante: Para qualquer pergunta sobre promoções, você deve obrigatoriamente responder chamando a ferramenta:
<tool>{"name":"best_promotions","args":{}}</tool>

Ferramentas:
- best_promotions(user_lat?, user_lng?, id_usuario?, radius_km?, max_results?, max_price?, category_name?, product_like?)
- sql_query(query, params?)           # somente SELECT
- faq_answer(question)

REGRAS:
1) Para pedidos de promoções, use 'best_promotions'.
2) Mostre: produto, estabelecimento, cidade/UF, preço (R$), distância (km) e validade.
3) Nunca invente dados; use apenas o que vier das ferramentas.
4) Se faltar endereço, oriente o usuário a cadastrar um endereço no perfil.
5) Respostas curtas e objetivas; para listas, use bullets.

FORMATO OBRIGATÓRIO:
- Usar ferramenta:
<tool>{"name":"NOME","args":{...}}</tool>
- Resposta final ao usuário:
<final>texto</final>
"""

TOOL_TAG = re.compile(r"<tool>(.*?)</tool>", re.S)
FINAL_TAG = re.compile(r"<final>(.*?)</final>", re.S)

PROMO_KEYWORDS = ["promoção", "promocoes", "melhores promoções", "desconto", "preço", "oferta", "promo"]

def is_promo_request(msg: str) -> bool:
    return any(word in msg.lower() for word in PROMO_KEYWORDS)

def extract_product_name(user_msg: str) -> str:
    # Remove palavras irrelevantes e deixa só o nome do produto
    cleaned = re.sub(r"(quais são as melhores promoções de|promoções|preço|desconto|oferta|promo|para|de)", "", user_msg, flags=re.I)
    return cleaned.strip()

def run_agent(user_msg: str, session_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    mem = Memory(session_id)
    messages = mem.load()

    if not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": SYSTEM})

    if user_id is not None and not any(m.get("role") == "system" and "Contexto do usuário" in m.get("content", "") for m in messages):
        messages.insert(1, {"role": "system", "content": f"Contexto do usuário: id_usuario={user_id}. Use esse id para obter latitude/longitude."})

    messages.append({"role": "user", "content": user_msg})

    for _ in range(8):
        out = ollama.chat(model=MODEL, messages=messages, options={"temperature": 0.2})
        text = out["message"]["content"]

        # Se o usuário pediu promoções mas o modelo não colocou <tool>, injetar automaticamente
        if is_promo_request(user_msg) and not TOOL_TAG.search(text):
            product_name = extract_product_name(user_msg)
            tool_call = json.dumps({"name": "best_promotions", "args": {"product_like": product_name}})
            text = f"<tool>{tool_call}</tool>"

        m_final = FINAL_TAG.search(text)
        if m_final:
            final_text = m_final.group(1).strip()
            messages.append({"role": "assistant", "content": f"<final>{final_text}</final>"})
            mem.save(messages)
            return {"reply": final_text, "toolsUsed": []}

        m_tool = TOOL_TAG.search(text)
        if m_tool:
            try:
                call = json.loads(m_tool.group(1))
                name = call["name"]
                args = call.get("args", {})
            except Exception as e:
                messages.append({"role": "tool", "content": json.dumps({"error": f"JSON inválido: {e}"}, ensure_ascii=False)})
                continue

            if name == "best_promotions" and user_id is not None:
                has_coords = ("user_lat" in args and "user_lng" in args)
                if (not has_coords) and ("id_usuario" not in args):
                    args["id_usuario"] = user_id

            tool = TOOL_REGISTRY.get(name)
            if not tool:
                messages.append({"role": "tool", "content": json.dumps({"error": f"Ferramenta desconhecida: {name}"}, ensure_ascii=False)})
                continue

            try:
                result: ToolResult = tool(**args)
                messages.append({"role": "tool", "content": json.dumps({"name": name, "result": result.dict()}, ensure_ascii=False)})

                if name == "best_promotions":
                    if not result.ok or not result.data:
                        final_text = "Não encontrei promoções para sua busca."
                    else:
                        final_text = "As melhores promoções são:\n"
                        for r in result.data:
                            final_text += f"- {r['produto']} no {r['estabelecimento']} — {r['cidade']}/{r['estado']} — {r['preco_brl']} — {r['distance_km']} km — até {r['data_fim']}\n"
                    messages.append({"role": "assistant", "content": f"<final>{final_text}</final>"})
                    mem.save(messages)
                    return {"reply": final_text, "toolsUsed": [name]}

            except Exception as e:
                messages.append({"role": "tool", "content": json.dumps({"name": name, "error": str(e)}, ensure_ascii=False)})
            continue

        messages.append({"role": "assistant", "content": text})
        mem.save(messages)
        return {"reply": text, "toolsUsed": []}

    fail = "Não consegui concluir. Verifique se há endereço cadastrado no seu perfil para localizar promoções próximas."
    messages.append({"role": "assistant", "content": f"<final>{fail}</final>"})
    mem.save(messages)
    return {"reply": fail, "toolsUsed": []}
