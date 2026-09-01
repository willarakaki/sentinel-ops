from langgraph.graph import StateGraph, START, END

# Importações do nosso ecossistema
from sentinel.schemas.state import DisputeState
from sentinel.agents.triage import triage_node
from sentinel.agents.investigator import investigator_node
from config.settings import dispute_rules

# ==========================================
# 1. NÓS SIMULADOS
# ==========================================
def auto_refund_node(state: DisputeState) -> dict:
    print("--- [NÓ: AUTO REFUND (Aprovação Imediata)] ---")
    return {"recommended_action": "auto_refund", "human_in_the_loop_required": False}

def human_review_node(state: DisputeState) -> dict:
    print("--- [NÓ: REVISÃO MANUAL (Analista Sênior)] ---")
    return {"human_in_the_loop_required": True}

# ==========================================
# 2. LÓGICA DE ROTEAMENTO
# ==========================================
def route_after_triage(state: DisputeState) -> str:
    """
    Lê o Estado após a triagem e decide o próximo nó baseado
    na nossa Matriz de Regras de Negócio (YAML).
    """
    print("--- [ROTEADOR: Avaliando Risco e Valor] ---")
    
    risk = state.get("risk_level")
    amount = state.get("dispute_amount", 0.0)
    
    # 1. Regra de Defesa (Risco Elevado/Crítico ou falha na classificação)
    if risk in ["elevado", "critico", "classificacao_falhou"]:
        print(">> Roteando para: REVISÃO HUMANA (Risco Crítico/Falha)")
        return "human_review"
        
    # 2. Regra FinOps (Auto-Refund)
    micro_max = dispute_rules.tiers["micro"].max_value
    if risk == "baixo" and amount <= micro_max:
        print(f">> Roteando para: AUTO REFUND (Valor {amount} <= Limite {micro_max})")
        return "auto_refund"
        
    # 3. Caminho Padrão (Investigação Profunda)
    print(">> Roteando para: INVESTIGADOR (Análise Complexa de Telemetria)")
    return "investigator"

# ==========================================
# 3. ORQUESTRADOR LANGGRAPH
# ==========================================
def build_graph():
    print("⚙️ Construindo Orquestrador LangGraph Híbrido (Local + Cloud)...")
    workflow = StateGraph(DisputeState)
    
    # Registra todos os nós
    workflow.add_node("triage", triage_node)         # SLM Local (Ollama)
    workflow.add_node("investigator", investigator_node) # Cloud LLM (Gemini)
    workflow.add_node("auto_refund", auto_refund_node)   # Código determinístico (Python)
    workflow.add_node("human_review", human_review_node) # Código determinístico (Python)
    
    # Desenha o fluxo
    workflow.add_edge(START, "triage")
    
    # A Mágica: Aresta Condicional
    workflow.add_conditional_edges(
        "triage",               # Nó de origem
        route_after_triage,     # Função que decide o destino
        {
            # Mapeamento: O que a função retorna -> Qual nó executar
            "auto_refund": "auto_refund",
            "investigator": "investigator",
            "human_review": "human_review"
        }
    )
    
    # Finaliza o fluxo dos nós de saída para o END
    workflow.add_edge("auto_refund", END)
    workflow.add_edge("investigator", END)
    workflow.add_edge("human_review", END)
    
    return workflow.compile()

sentinel_app = build_graph()