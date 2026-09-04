import os
import sqlite3
import duckdb
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode

# Importações do nosso ecossistema
from sentinel.schemas.state import DisputeState
from sentinel.agents.triage import triage_node
from sentinel.agents.investigator import investigator_node
from config.settings import dispute_rules
from sentinel.tools.database import get_delivery_telemetry, get_customer_history
from sentinel.agents.security_shield import security_shield_node

os.makedirs("data", exist_ok=True)

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
    Roteador Híbrido: Cruza a Intenção Semântica (LLM) 
    com o Score de Risco Determinístico (DuckDB).
    """
    print("--- [ROTEADOR: Hidratação de Dados e Avaliação] ---")
    
    customer_id = state.get("customer_id")
    amount = state.get("dispute_amount", 0.0)
    
    # O risco que o LLM "achou" lendo apenas o texto (Probabilístico)
    llm_risk = state.get("risk_level", "elevado").lower()
    
    # 1. DATA HYDRATION: Busca o Risco Real (Determinístico) no DuckDB
    db_path = os.path.join(os.getcwd(), "data", "sentinel.duckdb")
    db_risk = "high" # Fail-safe: Se falhar a conexão, assumimos risco alto por segurança
    
    try:
        with duckdb.connect(db_path, read_only=True) as conn:
            result = conn.execute("SELECT risk_score FROM customer_profiles WHERE customer_id = ?", [customer_id]).fetchone()
            if result:
                db_risk = result[0].lower() # Pega 'low', 'medium' ou 'high' do banco
    except Exception as e:
        print(f" ⚠️ Erro ao buscar risco no banco: {e}")
        
    print(f" >> Risco Semântico (LLM): {llm_risk} | Risco Real (DB): {db_risk}")
    
    # 2. Regra de Defesa em Profundidade
    # Se o banco diz que o cliente é HIGH, ou o LLM percebeu uma intenção crítica (ex: ameaça de processo)
    if db_risk == "high" or llm_risk in ["critico", "classificacao_falhou"]:
        print(" >> Roteando para: REVISÃO HUMANA (Defesa Acionada)")
        return "human_review"
        
    # 3. Regra FinOps e CX (Customer Experience)
    # Se o banco garante que o cliente é LOW (VIP) e o valor é baixo, não importa o que o LLM achou.
    micro_max = dispute_rules.tiers["micro"].max_value
    if db_risk == "low" and amount <= micro_max:
        print(f" >> Roteando para: AUTO REFUND (Cliente VIP: Valor {amount} <= Limite {micro_max})")
        return "auto_refund"
        
    # 4. Caminho Padrão (Score Medium ou Valores mais altos)
    print(" >> Roteando para: INVESTIGADOR (Análise Complexa de Telemetria)")
    return "investigator"

def route_after_security(state: DisputeState) -> str:
    """Aplica regras determinísticas elegíveis antes de chamar o SLM de triagem."""
    if state.get("recommended_action") == "bloqueio_seguranca":
        print(">> Roteando para: REVISÃO HUMANA (Bloqueio de segurança)")
        return "human_review"

    customer_id = state.get("customer_id", "").strip().upper()
    amount = state.get("dispute_amount", 0.0)
    micro_max = dispute_rules.tiers["micro"].max_value

    if customer_id == "CUST-VIP" and amount <= micro_max:
        print(">> Roteando para: AUTO REFUND (Cliente VIP e valor micro)")
        return "auto_refund"

    return "triage"

def route_investigator(state: DisputeState) -> str:
    """
    Se o Gemini pedir dados do DuckDB, roteia para o 'tools'.
    Se ele já chamou o InvestigatorOutput e atualizou a ação, roteia para o 'END'.
    """
    if state.get("recommended_action"):
        return END
    return "tools"

def route_security(state: DisputeState) -> str:
    """
    Se o WAF identificar um ataque, roteia direto para a revisão humana
    de fraudes e congela o fluxo. Caso contrário, segue para a Triagem.
    """
    print("--- [ROTEADOR: Firewall de IA] ---")
    if state.get("recommended_action") == "bloqueio_seguranca":
        print(">> 🚨 ALERTA: Ataque bloqueado! Enviando para a Equipe de Fraudes.")
        return "human_review"
    
    print(">> Tráfego seguro. Prosseguindo para Triagem de Negócios.")
    return "triage"

# ==========================================
# 3. ORQUESTRADOR LANGGRAPH
# ==========================================
def build_graph():
    print("⚙️ Construindo Orquestrador LangGraph Híbrido (Local + Cloud)...")
    workflow = StateGraph(DisputeState)
    
    # Registra todos os nós
    workflow.add_node("security_shield", security_shield_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("investigator", investigator_node)
    workflow.add_node("auto_refund", auto_refund_node)
    workflow.add_node("human_review", human_review_node)
    
    db_tools = [get_delivery_telemetry, get_customer_history]
    workflow.add_node("tools", ToolNode(db_tools))
    
    # Desenha o fluxo
    workflow.add_edge(START, "security_shield")
    
    workflow.add_conditional_edges(
        "security_shield",
        route_after_security,
        {
            "auto_refund": "auto_refund",
            "triage": "triage",
            "human_review": "human_review"
        }
    )
    
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
    
    workflow.add_conditional_edges(
        "investigator",
        route_investigator,
        {
            "tools": "tools",
            END: END
        }
    )
    # Devolve o texto do db para o Gemini
    workflow.add_edge("tools", "investigator")
    
    workflow.add_edge("auto_refund", END)
    workflow.add_edge("human_review", END)
    
    conn = sqlite3.connect("data/checkpoints.sqlite", check_same_thread=False)
    
    memory = SqliteSaver(conn)
    
    return workflow.compile(
        checkpointer=memory,
        interrupt_before=["human_review"]
        )

sentinel_app = build_graph()