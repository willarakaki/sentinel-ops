from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from sentinel.core.llm_factory import LLMFactory
from sentinel.schemas.state import DisputeState

# ==========================================
# 1. CONTRATO DE SAÍDA (Native Tool Calling)
# ==========================================
class InvestigatorOutput(BaseModel):
    recommended_action: str = Field(
        description="Ação recomendada: 'aprovar_reembolso', 'negar_disputa', ou 'escalar_humano'."
    )
    justification: str = Field(
        description="Justificativa técnica e detalhada para a decisão, baseada nos dados fornecidos."
    )
    human_in_the_loop_required: bool = Field(
        description="True se a decisão for inconclusiva ou suspeita, exigindo auditoria manual."
    )

# ==========================================
# 2. LÓGICA DO NÓ DE INVESTIGAÇÃO (Cloud LLM)
# ==========================================
def investigator_node(state: DisputeState) -> dict:
    """
    Agente Cognitivo. Utiliza o Gemini (Nuvem) para analisar 
    o contexto completo e tomar a decisão financeira final.
    """
    print("--- [NÓ: INVESTIGADOR (Nuvem / Gemini)] ---")
    
    # 1. Extrai o contexto acumulado na prancheta
    customer_message = state["messages"][0].content # A queixa original
    intent = state.get("intent", "desconhecida")
    amount = state.get("dispute_amount", 0.0)
    telemetry = state.get("telemetry_data", {}) # Mock para a próxima Sprint (MCP)
    
    # 2. Instancia o LLM da Nuvem (Baixa temperatura para ser analítico, não criativo)
    cloud_llm = LLMFactory.get_cloud_model(temperature=0.1)
    
    # 3. Habilita o Native Structured Output
    # Isso substitui o json.loads() e a Engenharia de Prompt complexa
    structured_llm = cloud_llm.with_structured_output(InvestigatorOutput)
    
    # 4. Prompt Contextual
    system_prompt = f"""Você é um Investigador Sênior de Prevenção a Perdas (SentinelOps).
    Sua missão é analisar queixas de clientes e decidir de forma justa e implacável.

    [CONTEXTO DA DISPUTA]
    - Valor: R$ {amount}
    - Intenção Triada: {intent}
    - Dados de Telemetria: {telemetry if telemetry else "Nenhum dado externo anexado ainda."}

    Analise a queixa e retorne a ação recomendada, sua justificativa técnica e se precisa de revisão humana."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Queixa do cliente: {customer_message}")
    ]
    
    try:
        # A invocação já devolve o objeto Pydantic validado!
        result: InvestigatorOutput = structured_llm.invoke(messages)
        
        print(f"[VEREDITO] Ação: {result.recommended_action} | HITL: {result.human_in_the_loop_required}")
        print(f"[PARECER] {result.justification}")
        
        # 5. Atualiza o Estado
        return {
            "recommended_action": result.recommended_action,
            "human_in_the_loop_required": result.human_in_the_loop_required,
            # Usa o Reducer para registrar o pensamento da IA na auditoria do ticket
            "messages": [AIMessage(content=f"Parecer Investigativo: {result.justification}")]
        }
        
    except Exception as e:
        print(f"[ERRO NO INVESTIGADOR CLOUD] {e}")
        return {
            "recommended_action": "erro_api_nuvem",
            "human_in_the_loop_required": True
        }