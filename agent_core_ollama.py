# agent_core_ollama.py
import json, re, os
from typing import Dict, Any, Optional
import ollama
from tools import TOOL_REGISTRY, ToolResult
from memory import Memory

MODEL = os.getenv("MODEL", "phi4")

SYSTEM = """
Você é um agente especializado em PROMOÇÕES do InfoHub.
OBJETIVO: achar as MELHORES PROMOÇÕES considerando PREÇO e LOCALIZAÇÃO do usuário, e responder FAQs do sistema.
NUNCA peça coordenadas ao usuário. Se faltarem, use o id_usuario do CONTEXTO para obter a localização em tbl_enderecoUsuario.
NUNCA saia desse foco. Fora do escopo, recuse educadamente.

Ferramentas:
- best_promotions(user_lat?, user_lng?, id_usuario?, radius_km?, max_results?, max_price?, category_name?, product_like?)
- sql_query(query, params?)           # somente SELECT
- faq_answer(question)

REGRAS:
1) Para pedidos de promoções, priorize 'best_promotions'.
2) Mostre: produto, estabelecimento, cidade/UF, preço (R$), distância (km) e validade.
3) Nunca invente dados; use apenas o que vier das ferramentas.
4) Se a ferramenta avisar que falta endereço, oriente a cadastrar um endereço no perfil.
5) Respostas curtas e objetivas; para listas, use bullets.

FORMATO OBRIGATÓRIO:
- Usar ferramenta:
<tool>{"name":"NOME","args":{...}}</tool>
- Resposta final ao usuário:
<final>texto</final>
"""

TOOL_TAG = re.compile(r"<tool>(.*?)</tool>", re.S)
FINAL_TAG = re.compile(r"<final>(.*?)</final>", re.S)

def run_agent(user_msg: str, session_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    mem = Memory(session_id)
    messages = mem.load()

    if not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {"role":"system","content":SYSTEM})

    # contexto do usuário
    if user_id is not None and not any(m.get("role")=="system" and "Contexto do usuário" in m.get("content","") for m in messages):
        messages.insert(1, {"role":"system","content": f"Contexto do usuário: id_usuario={user_id}. Use esse id para obter latitude/longitude."})

    messages.append({"role":"user","content":user_msg})

    for _ in range(8):
        out = ollama.chat(model=MODEL, messages=messages, options={"temperature":0.2})
        text = out["message"]["content"]

        # resposta final?
        m_final = FINAL_TAG.search(text)
        if m_final:
            final_text = m_final.group(1).strip()
            messages.append({"role":"assistant","content":f"<final>{final_text}</final>"})
            mem.save(messages)
            return {"reply": final_text, "toolsUsed":[]}

        # pediu ferramenta?
        m_tool = TOOL_TAG.search(text)
        if m_tool:
            try:
                call = json.loads(m_tool.group(1))
                name = call["name"]
                args = call.get("args", {})
            except Exception as e:
                messages.append({"role":"tool","content":json.dumps({"error":f"JSON inválido: {e}"}, ensure_ascii=False)})
                continue

            # autocompletar id_usuario quando faltar
            if name == "best_promotions" and user_id is not None:
                has_coords = ("user_lat" in args and "user_lng" in args)
                if (not has_coords) and ("id_usuario" not in args):
                    args["id_usuario"] = user_id

            tool = TOOL_REGISTRY.get(name)
            if not tool:
                messages.append({"role":"tool","content":json.dumps({"error":f"Ferramenta desconhecida: {name}"}, ensure_ascii=False)})
                continue

            try:
                result: ToolResult = tool(**args)
                messages.append({"role":"tool","content":json.dumps({"name":name,"result":result.dict()}, ensure_ascii=False)})
            except Exception as e:
                messages.append({"role":"tool","content":json.dumps({"name":name,"error":str(e)}, ensure_ascii=False)})
            continue

        # fallback
        messages.append({"role":"assistant","content":text})
        mem.save(messages)
        return {"reply": text, "toolsUsed":[]}

    fail = "Não consegui concluir. Verifique se há endereço cadastrado no seu perfil para localizar promoções próximas."
    messages.append({"role":"assistant","content":f"<final>{fail}</final>"})
    mem.save(messages)
    return {"reply": fail, "toolsUsed":[]}
