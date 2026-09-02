from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tenacity import retry, stop_after_attempt, wait_random_exponential

from sentinel.core.llm_factory import LLMFactory
from sentinel.schemas.state import DisputeState
from sentinel.tools.database import get_delivery_telemetry, get_customer_history

# ==========================================
# 1. CONTRATO DE SAÍDA
# ==========================================
class InvestigatorOutput(BaseModel):
    """Use esta ferramenta APENAS para submeter o veredito final após coletar evidências."""
    recommended_action: str = Field(description="'aprovar_reembolso', 'negar_disputa', ou 'escalar_humano'.")
    justification: str = Field(description="Justificativa técnica baseada na telemetria.")
    human_in_the_loop_required: bool = Field(description="True se a decisão for inconclusiva ou suspeita.")

# ==========================================
# 2. FUNÇÃO RESILIENTE DE CHAMADA À API
# ==========================================
# Se a chamada falhar (503, 429, timeout), tenta até 4 vezes.
# Espera 2s, depois 4s, depois 8s...
@retry(
    stop=stop_after_attempt(4),
    wait=wait_random_exponential(multiplier=1, min=2, max=15), # Adiciona aleatoriedade entre 2s e 15s
    reraise=True
)
def invoke_with_backoff(llm_with_tools, messages):
    print("  🌐 [REDE] Invocando LLM Cloud...")
    return llm_with_tools.invoke(messages)

# ==========================================
# 3. LÓGICA DO NÓ DE INVESTIGAÇÃO (ReAct Loop)
# ==========================================
def investigator_node(state: DisputeState) -> dict:
    print("--- [NÓ: INVESTIGADOR (Nuvem / Gemini)] ---")
    
    cloud_llm = LLMFactory.get_cloud_model(temperature=0.1)
    db_tools = [get_delivery_telemetry, get_customer_history]
    llm_with_tools = cloud_llm.bind_tools(db_tools + [InvestigatorOutput])
    
    intent = state.get("intent", "desconhecida")
    amount = state.get("dispute_amount", 0.0)
    customer_id = state.get("customer_id")
    ticket_id = state.get("ticket_id")
    
    system_prompt = f"""Você é um Investigador de Prevenção a Perdas.
        Valor em Disputa: R$ {amount} | Intenção: {intent} | Cliente: {customer_id} | Ticket: {ticket_id}

        SUA MISSÃO:
        1. USE as ferramentas de telemetria e histórico para investigar a queixa. NUNCA decida sem dados!
        2. Quando reunir as evidências, chame a ferramenta 'InvestigatorOutput' para emitir o laudo final.
        """
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    try:
        response = invoke_with_backoff(llm_with_tools, messages)
        
        if response.tool_calls and response.tool_calls[0]["name"] == "InvestigatorOutput":
            print("[INVESTIGAÇÃO CONCLUÍDA] Veredito alcançado com base em dados.")
            args = response.tool_calls[0]["args"]
            return {
                "recommended_action": args["recommended_action"],
                "human_in_the_loop_required": args["human_in_the_loop_required"],
                "messages": [AIMessage(content=f"Parecer Baseado em Dados: {args['justification']}")]
            }
        
        print(f"[AÇÃO DO AGENTE] Solicitando busca de dados: {[t['name'] for t in response.tool_calls]}")
        return {"messages": [response]}
        
    except Exception as e:
        print(f"[ERRO FATAL NO INVESTIGADOR CLOUD após retentativas] {e}")
        return {
            "recommended_action": "erro_api_nuvem", 
            "human_in_the_loop_required": True,
            "messages": [AIMessage(content="Falha de comunicação com a API. Ticket enviado para revisão humana.")] # <- Correção do KeyError
        }