import os
import sqlite3
import duckdb
import json
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage

# Importações do nosso ecossistema
from sentinel.schemas.state import DisputeState
from sentinel.agents.triage import triage_node
from sentinel.agents.investigator import investigator_node
from config.settings import dispute_rules
from sentinel.tools.database import get_customer_profile, get_delivery_telemetry, get_customer_history
from sentinel.agents.security_shield import security_shield_node
from sentinel.core.cache import semantic_cache
from sentinel.core.privacy import mask_pii
from sentinel.core.cache_signature import build_trust_signature, signature_to_text
from sentinel.core.sandbox import apply_sandbox_override

os.makedirs("data", exist_ok=True)


# ==========================================
# 0. RESET DE ESTADO ENTRE DISPUTAS NO MESMO THREAD
# ==========================================
def reset_turn_node(state: DisputeState) -> dict:
    """
    Roda no início de TODA nova invocação a partir de START, garantindo que o
    veredito (recommended_action) de uma disputa ANTERIOR no mesmo thread_id
    não vaze pra disputa atual. Sem isso, route_after_cache/route_investigator
    ("if state.get('recommended_action'): return END") encerram o grafo
    prematuramente reaproveitando o veredito de outro ticket, porque nenhum nó
    limpava esse campo entre uma mensagem e outra no mesmo checkpoint.

    Seguro em relação ao HITL: quando o grafo está pausado em "human_review" e
    é retomado via sentinel_app.stream(None, config=config), a execução volta
    a partir do ponto pausado, sem passar por START de novo — então esse reset
    não interfere na retomada humana, só em invocações NOVAS (.stream(input, ...)).
    """
    return {"recommended_action": None, "human_in_the_loop_required": False}

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


def profile_allows_semantic_cache(profile: dict) -> bool:
    """Aplica a política comportamental antes de reutilizar uma decisão."""
    risk_score = profile.get("risk_score", "HIGH").upper()
    disputes = int(profile.get("previous_disputes", 0))
    no_shows = int(profile.get("no_show_count", 0))
    total_orders = max(int(profile.get("total_orders", 0)), 1)
    dispute_rate = disputes / total_orders

    # LTV alto melhora retenção, mas não compensa abuso ou reincidência.
    return (
        risk_score != "HIGH"
        and disputes < 10
        and no_shows < 3
        and dispute_rate < 0.15
    )

# ==========================================
# 1.1 HIDRATAÇÃO DETERMINÍSTICA + SEMANTIC CACHE
# ==========================================
def hydrate_and_check_cache_node(state: DisputeState) -> dict:
    print("--- [NÓ: HIDRATAÇÃO + SEMANTIC CACHE] ---")

    customer_id = state.get("customer_id")
    ticket_id = state.get("ticket_id")
    amount = state.get("dispute_amount", 0.0)

    if not state.get("messages"):
        return {}

    try:
        telemetry = get_delivery_telemetry.invoke({"ticket_id": ticket_id})
        profile = get_customer_profile(customer_id)
    except Exception as e:
        print(f" ⚠️ [Hidratação] Falha ao buscar dados diretamente ({e}). Delegando ao Investigador.")
        return {}

    if not profile or not profile_allows_semantic_cache(profile):
        print("  🛡️ [Semantic Cache] Perfil comportamental inelegível. Enviando ao Investigator.")
        return {}

    sandbox_receipt = state.get("sandbox_receipt_json", "")
    telemetry = apply_sandbox_override(telemetry, sandbox_receipt, ticket_id)

    trust_signature = build_trust_signature(profile)
    trust_text = signature_to_text(trust_signature)

    masked_query = mask_pii(state["messages"][-1].content)
    cache_key = semantic_cache.build_cache_key(masked_query, telemetry, trust_text)

    cached = semantic_cache.check_cache(cache_key, current_amount=amount, trust_signature=trust_signature)
    if not cached:
        return {}

    parecer_final = (
        f"Parecer Baseado em Dados (VIA CACHE): {cached.get('justification', '')}\n\n"
        f"💰 **Valor Aprovado:** R$ {cached.get('approved_refund_amount', 0.0):.2f}\n"
        f"⚖️ **Responsabilidade (Liability):** {str(cached.get('liability', 'não informado')).upper()}"
    )

    return {
        "recommended_action": cached["recommended_action"],
        "human_in_the_loop_required": cached["recommended_action"] == "escalar_humano",  # defensivo
        "messages": [AIMessage(content=parecer_final)],
    }

def route_after_cache(state: DisputeState) -> str:
    """Se o cache resolveu (HIT), encerra. Senão, segue para o Investigador (ReAct)."""
    if state.get("recommended_action"):
        return END
    return "investigator"

# ==========================================
# 2. LÓGICA DE ROTEAMENTO
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
    Roteador Híbrido com Deep Data Hydration e Zero Trust.
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
    order_items_str = None

    # 1. HYDRATION: Busca Risco, Compliance e Recibo Real no Banco
    try:
        with duckdb.connect(db_path, read_only=True) as conn:
            res_risk = conn.execute("SELECT risk_score FROM customer_profiles WHERE customer_id = ?", [customer_id]).fetchone()
            if res_risk:
                db_risk = res_risk[0].lower()

            res_ticket = conn.execute("SELECT is_age_restricted, order_items_json FROM delivery_telemetry WHERE ticket_id = ?", [ticket_id]).fetchone()
            if res_ticket:
                is_age_restricted = res_ticket[0]
                order_items_str = res_ticket[1]
    except Exception as e:
        print(f" ⚠️ Erro ao hidratar dados: {e}")

    # 1.1 ZERO TRUST MATEMÁTICO (Cálculo do Valor Real)
    db_order_total = 0.0
    sandbox_receipt = state.get("sandbox_receipt_json", "")

    try:
        json_to_parse = sandbox_receipt if sandbox_receipt else order_items_str
        if json_to_parse:
            items = json.loads(json_to_parse)
            db_order_total = sum(float(i.get("price", 0.0)) for i in items)
    except Exception as e:
        print(f" ⚠️ Erro ao parsear JSON no Roteador: {e}")

    print(f" >> Risco LLM: {llm_risk} | Risco DB: {db_risk} | Restrito: {is_age_restricted} | Teto Solicitado: R$ {amount} | Teto Real: R$ {db_order_total}")

    # 2. REGRA DE COMPLIANCE (Soberana)
    if is_age_restricted:
        print(" >> ⚖️ COMPLIANCE: Item restrito detectado. Forçando envio para o Investigador.")
        return "investigator"

    # 3. REGRA DE EMERGÊNCIA (Defesa)
    if llm_risk in ["critico", "classificacao_falhou"]:
        print(" >> 🚨 EMERGÊNCIA: Risco crítico ou falha semântica. Escalando para Humano.")
        return "human_review"

    # 4. PERFIL HIGH: valores maiores exigem decisão humana; valores menores
    # seguem ao Investigator para uma análise baseada nas evidências das tools.
    medium_min = dispute_rules.tiers["medium"].min_value
    if db_risk == "high":
        if amount > medium_min:
            print(
                f" >> 🛡️ PERFIL HIGH + DISPUTA ACIMA DE R$ {medium_min:.2f}: "
                "Escalando diretamente para HITL."
            )
            return "human_review"

        print(" >> 🛡️ PERFIL HIGH: enviando ao Investigator para decisão baseada em evidências.")
        return "investigator"

    # 5. REGRA FINOPS (Auto-Refund) COM ZERO TRUST
    micro_max = dispute_rules.tiers["micro"].max_value

    if db_risk == "low" and amount <= micro_max:
        if amount <= db_order_total:
            print(f" >> 💰 FINOPS: Risco Baixo, Valor Micro e Coerente com Recibo. Roteando para AUTO REFUND.")
            return "auto_refund"
        else:
            print(f" >> 🚨 ANOMALIA FINANCEIRA: Tentativa de estorno (R$ {amount}) maior que o recibo real (R$ {db_order_total}). Interceptando Fraude de Front-end!")
            return "investigator"

    # 5. CAMINHO PADRÃO
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

    workflow.add_node("reset_turn", reset_turn_node)
    workflow.add_node("security_shield", security_shield_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("hydrate_and_check_cache", hydrate_and_check_cache_node)
    workflow.add_node("investigator", investigator_node)
    workflow.add_node("auto_refund", auto_refund_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("out_of_scope", out_of_scope_node)

    db_tools = [get_delivery_telemetry, get_customer_history]
    workflow.add_node("tools", ToolNode(db_tools))

    # Redesenhando o Fluxo Corretamente
    workflow.add_edge(START, "reset_turn")
    workflow.add_edge("reset_turn", "security_shield")

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
            "investigator": "hydrate_and_check_cache",  # <- antes ia direto pro investigator
            "human_review": "human_review",
            "out_of_scope": "out_of_scope"
        }
    )

    workflow.add_conditional_edges(
        "hydrate_and_check_cache",
        route_after_cache,
        {
            "investigator": "investigator",
            END: END,
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