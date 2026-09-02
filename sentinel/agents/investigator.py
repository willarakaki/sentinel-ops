from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from sentinel.core.llm_factory import LLMFactory
from sentinel.schemas.state import DisputeState
from sentinel.tools.database import get_delivery_telemetry, get_customer_history

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
# 2. LÓGICA DO NÓ DE INVESTIGAÇÃO (ReAct Loop)
# ==========================================
def investigator_node(state: DisputeState) -> dict:
    print("--- [NÓ: INVESTIGADOR (Nuvem / Gemini)] ---")

    cloud_llm = LLMFactory.get_cloud_model(temperature=0.1)
    db_tools = [get_delivery_telemetry, get_customer_history]
    
    # Vincula as ferramentas de busca e a ferramenta de decisão final
    llm_with_tools = cloud_llm.bind_tools(db_tools + [InvestigatorOutput])
    
    intent = state.get("intent", "desconhecida")
    amount = state.get("dispute_amount", 0.0)
    customer_id = state.get("customer_id")
    ticket_id = state.get("ticket_id")
    
    system_prompt = f"""Você é um Investigador de Prevenção a Perdas (SentinelOps).
        Valor em Disputa: R$ {amount} | Intenção: {intent} | Cliente: {customer_id} | Ticket: {ticket_id}

        SUA MISSÃO:
        1. USE as ferramentas de telemetria e histórico para investigar a queixa. NUNCA decida sem dados!
        2. Quando reunir as evidências, chame a ferramenta 'InvestigatorOutput' para emitir o laudo final.
        """
    
    # Garante que o system prompt seja injetado nas mensagens que vão para o modelo
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = llm_with_tools.invoke(messages)
        
        # Verifica se o modelo decidiu emitir o laudo final (chamou InvestigatorOutput)
        if response.tool_calls and response.tool_calls[0]["name"] == "InvestigatorOutput":
            print("[INVESTIGAÇÃO CONCLUÍDA] Veredito alcançado com base em dados.")
            args = response.tool_calls[0]["args"]
            return {
                "recommended_action": args["recommended_action"],
                "human_in_the_loop_required": args["human_in_the_loop_required"],
                "messages": [AIMessage(content=f"Parecer Baseado em Dados: {args['justification']}")]
            }
        
        # Se ele chamou ferramentas do DuckDB, apenas anexamos a mensagem para o ToolNode processar
        print(f"[AÇÃO DO AGENTE] Solicitando busca de dados: {[t['name'] for t in response.tool_calls]}")
        return {"messages": [response]}
        
    except Exception as e:
        print(f"[ERRO NO INVESTIGADOR] {e}")
        return {"recommended_action": "erro_api_nuvem", "human_in_the_loop_required": True}