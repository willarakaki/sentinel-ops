import re
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama

from sentinel.schemas.state import DisputeState

# ==========================================
# 1. CAMADA L1: HEURÍSTICA DE BLOQUEIO RÁPIDO
# ==========================================
# Lista de termos clássicos de engenharia social e jailbreaks
JAILBREAK_PATTERNS = [
    r"(?i)ignore (todas )?(as )?instruções",
    r"(?i)esqueça (o )?contexto",
    r"(?i)você (agora )?é (um )?",
    r"(?i)system prompt",
    r"(?i)desconsidere as regras",
    r"(?i)bypass",
    r"(?i)modo de desenvolvedor"
]

def check_heuristics(text: str) -> bool:
    """Retorna True se encontrar padrões maliciosos óbvios (Latência: 0ms)."""
    for pattern in JAILBREAK_PATTERNS:
        if re.search(pattern, text):
            print(f"  🛡️ [WAF L1] Padrão malicioso detectado via Regex: '{pattern}'")
            return True
    return False

# ==========================================
# 2. CAMADA L2: INFERÊNCIA SEMÂNTICA (LLaMA Guard)
# ==========================================
def check_semantics_llm(text: str) -> bool:
    """Usa Llama Guard 3 para avaliar ataques semânticos complexos."""
    try:
        # Usamos o modelo ultraleve da Meta focado apenas em Red Teaming
        llama_guard = ChatOllama(model="llama-guard3:1b", temperature=0.0)
        
        # O Llama Guard usa um formato de prompt específico, mas a integração do LangChain
        # lida bem com a estrutura de mensagens padrão.
        messages = [
            HumanMessage(content=text)
        ]
        
        print("  🛡️ [WAF L2] Analisando payload com Llama Guard 3...")
        response = llama_guard.invoke(messages)
        verdict = response.content.strip().lower()
        
        if verdict.startswith("unsafe"):
            print(f"  🛡️ [WAF L2] ALERTA: Semântica Insegura detectada!\nDetalhes: {verdict}")
            return True
            
        return False
    except Exception as e:
        print(f"  ⚠️ [WAF L2 Erro] Falha no Llama Guard: {e}. Aplicando bloqueio defensivo.")
        return True # Defense in Depth: Se o firewall falha, fechamos a porta.

# ==========================================
# 3. NÓ DO LANGGRAPH (O Escudo)
# ==========================================
def security_shield_node(state: DisputeState) -> dict:
    print("\n--- [NÓ: FIREWALL DE IA (Security Shield)] ---")
    customer_message = state["messages"][0].content
    
    # 1. Passa pela peneira de Regex (Custo $0)
    if check_heuristics(customer_message):
        return {
            "intent": "ataque_cibernetico",
            "risk_level": "critico",
            "recommended_action": "bloqueio_seguranca"
        }
        
    # 2. Passa pelo modelo de segurança local (LLaMA Guard)
    if check_semantics_llm(customer_message):
        return {
            "intent": "ataque_cibernetico",
            "risk_level": "critico",
            "recommended_action": "bloqueio_seguranca"
        }
        
    print("  ✅ [WAF] Tráfego limpo. Roteando para fluxo de negócios.")
    return {} # Se não retornar nada, o state mantém o que já tem e segue o fluxo normal