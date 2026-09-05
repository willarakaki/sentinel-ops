import os
import sqlite3
import duckdb
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage

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

def out_of_scope_node(state: DisputeState) -> dict:
    """Nó de bloqueio para perguntas que não são sobre delivery. Custo zero."""
    print("--- [NÓ: GUARDRAIL TÓPICO (Fora de Escopo)] ---")
    return {
        "recommended_action": "bloqueio_topico",
        "human_in_the_loop_required": False,
        "messages": [AIMessage(content="🛡️ **Bloqueio de Escopo:** Sou o SentinelOps, um assistente exclusivo para resolução de disputas financeiras e logísticas de delivery. Não posso responder a perguntas sobre outros assuntos.")]
    }
# ==========================================
# 2. LÓGICA DE ROTEAMENTO (CORRIGIDA)
# ==========================================
def route_security(state: DisputeState) -> str:
    """
    Firewall de IA. Se houver ataque (Prompt Injection), bloqueia na hora.
    Se estiver limpo, manda para o SLM de Triagem.
    """
    print("--- [ROTEADOR: Firewall de IA] ---")
    if state.get("recommended_action") == "bloqueio_seguranca":
        print(">> 🚨 ALERTA: Ataque bloqueado! Enviando para a Equipe de Fraudes.")
        return "human_review"
    
    print(">> Tráfego seguro. Prosseguindo para Triagem de Negócios.")
    return "triage"

def route_after_triage(state: DisputeState) -> str:
    """
    Roteador Híbrido com Deep Data Hydration.
    """
    print("--- [ROTEADOR: Hidratação Profunda de Dados] ---")
    
    intent = state.get("intent", "").lower()
    
    # 0. REGRA DE GUARDRAIL TÓPICO (Interceptação imediata)
    if intent == "fora_de_escopo":
        print(" >> 🛡️ GUARDRAIL: Assunto fora de escopo. Bloqueando chamada para nuvem.")
        return "out_of_scope"
    
    customer_id = state.get("customer_id")
    ticket_id = state.get("ticket_id")
    amount = state.get("dispute_amount", 0.0)
    llm_risk = state.get("risk_level", "elevado").lower()
    
    db_path = os.path.join(os.getcwd(), "data", "sentinel.duckdb")
    db_risk = "high"
    is_age_restricted = False
    
    # 1. HYDRATION: Busca Risco e Compliance no Banco
    try:
        with duckdb.connect(db_path, read_only=True) as conn:
            # Busca risco
            res_risk = conn.execute("SELECT risk_score FROM customer_profiles WHERE customer_id = ?", [customer_id]).fetchone()
            if res_risk:
                db_risk = res_risk[0].lower()
            
            # Busca compliance (Bebida/Remédio)
            res_ticket = conn.execute("SELECT is_age_restricted FROM delivery_telemetry WHERE ticket_id = ?", [ticket_id]).fetchone()
            if res_ticket:
                is_age_restricted = res_ticket[0]
    except Exception as e:
        print(f" ⚠️ Erro ao hidratar dados: {e}")
        
    print(f" >> Risco LLM: {llm_risk} | Risco DB: {db_risk} | Compliance Restrito: {is_age_restricted}")
    
    # 2. REGRA DE COMPLIANCE (Soberana)
    if is_age_restricted:
        print(" >> ⚖️ COMPLIANCE: Item restrito detectado. Forçando envio para o Investigador.")
        return "investigator"

    # 3. REGRA DE EMERGÊNCIA (Defesa)
    if llm_risk in ["critico", "classificacao_falhou"]:
        print(" >> 🚨 EMERGÊNCIA: Risco crítico ou falha semântica. Escalando para Humano.")
        return "human_review"
        
    # 4. REGRA FINOPS (Auto-Refund)
    micro_max = dispute_rules.tiers["micro"].max_value
    if db_risk == "low" and amount <= micro_max:
        print(f" >> 💰 FINOPS: Risco Baixo e Valor Micro. Roteando para AUTO REFUND.")
        return "auto_refund"
        
    # 5. CAMINHO PADRÃO (Fraudes, Abusos e Casos Médios)
    # Mandamos os clientes 'High' para cá para o Gemini aplicar a regra do No-Show e negar automaticamente!
    print(" >> 🔍 INVESTIGAÇÃO: Roteando para análise profunda (Gemini).")
    return "investigator"

def route_investigator(state: DisputeState) -> str:
    """Continua no ReAct loop (tools) até que a ação final seja definida."""
    if state.get("recommended_action"):
        return END
    return "tools"

# ==========================================
# 3. ORQUESTRADOR LANGGRAPH
# ==========================================
def build_graph():
    print("⚙️ Construindo Orquestrador LangGraph Híbrido (Local + Cloud)...")
    workflow = StateGraph(DisputeState)
    
    workflow.add_node("security_shield", security_shield_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("investigator", investigator_node)
    workflow.add_node("auto_refund", auto_refund_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("out_of_scope", out_of_scope_node)
    
    db_tools = [get_delivery_telemetry, get_customer_history]
    workflow.add_node("tools", ToolNode(db_tools))
    
    # Redesenhando o Fluxo Corretamente
    workflow.add_edge(START, "security_shield")
    
    workflow.add_conditional_edges(
        "security_shield",
        route_security,
        {
            "human_review": "human_review",
            "triage": "triage"
        }
    )
    
    workflow.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "auto_refund": "auto_refund",
            "investigator": "investigator",
            "human_review": "human_review",
            "out_of_scope": "out_of_scope"
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
    workflow.add_edge("tools", "investigator")
    
    workflow.add_edge("auto_refund", END)
    workflow.add_edge("human_review", END)
    workflow.add_edge("out_of_scope", END)
    
    conn = sqlite3.connect("data/checkpoints.sqlite", check_same_thread=False)
    memory = SqliteSaver(conn)
    
    return workflow.compile(
        checkpointer=memory,
        interrupt_before=["human_review"]
    )

sentinel_app = build_graph()