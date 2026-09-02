from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tenacity import retry, stop_after_attempt, wait_random_exponential

from sentinel.core.llm_factory import LLMFactory
from sentinel.schemas.state import DisputeState
from sentinel.tools.database import get_delivery_telemetry, get_customer_history
from sentinel.core.privacy import mask_pii
from sentinel.core.cache import semantic_cache

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
    
    # ---------------------------------------------------------
    # 2. EXTRAÇÃO DE CONTEXTO PARA O CACHE
    # ---------------------------------------------------------
    masked_query = ""
    tool_responses = []
    sanitized_messages = []
    
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            # Limpa PII e guarda a queixa base para o Cache
            clean_text = mask_pii(msg.content)
            if not masked_query:
                masked_query = clean_text 
            sanitized_messages.append(HumanMessage(content=clean_text))
        elif msg.type == "tool":
            # Coleta as evidências devolvidas pelo banco de dados
            tool_responses.append(msg.content)
            sanitized_messages.append(msg)
        else:
            sanitized_messages.append(msg)
            
    # Se o ToolNode já devolveu dados, estamos prontos para checar o FAISS
    evidence_text = "\n".join(tool_responses)
    
    if tool_responses:
        print("  🔍 [Investigador] Evidências detectadas. Consultando Semantic Cache...")
        cache_key = semantic_cache.build_cache_key(masked_query, evidence_text)
        cached_result = semantic_cache.check_cache(cache_key)
        
        if cached_result:
            # CACHE HIT! O custo desta execução acabou de cair para R$ 0,00
            return {
                "recommended_action": cached_result["recommended_action"],
                "human_in_the_loop_required": False, # Assumimos a confiança do cache passado
                "messages": [AIMessage(content=f"Parecer Baseado em Dados (VIA CACHE): {cached_result['justification']}")]
            }
    
    # ---------------------------------------------------------
    # 3. PREPARAÇÃO DA CHAMADA (CACHE MISS)
    # ---------------------------------------------------------
    intent = state.get("intent", "desconhecida")
    amount = state.get("dispute_amount", 0.0)
    
    system_prompt = f"""Você é um Investigador de Prevenção a Perdas.
        Valor em Disputa: R$ {amount} | Intenção: {intent}

        SUA MISSÃO:
        1. USE as ferramentas para investigar. NUNCA decida sem dados!
        2. Quando reunir as evidências, chame a ferramenta 'InvestigatorOutput'.
        """
    
    messages_to_cloud = [SystemMessage(content=system_prompt)] + sanitized_messages
    
    try:
        response = invoke_with_backoff(llm_with_tools, messages_to_cloud)
        
        if response.tool_calls and response.tool_calls[0]["name"] == "InvestigatorOutput":
            print("[INVESTIGAÇÃO CONCLUÍDA] Veredito alcançado com base em dados.")
            args = response.tool_calls[0]["args"]
            
            # ---------------------------------------------------------
            # 4. SALVANDO NO CACHE PARA O FUTURO
            # ---------------------------------------------------------
            if tool_responses:
                cache_key = semantic_cache.build_cache_key(masked_query, evidence_text)
                semantic_cache.save_to_cache(cache_key, args["recommended_action"], args["justification"])
            
            return {
                "recommended_action": args["recommended_action"],
                "human_in_the_loop_required": args["human_in_the_loop_required"],
                "messages": [AIMessage(content=f"Parecer Baseado em Dados: {args['justification']}")]
            }
        
        print(f"[AÇÃO DO AGENTE] Solicitando busca de dados: {[t['name'] for t in response.tool_calls]}")
        return {"messages": [response]}
        
    except Exception as e:
        print(f"[ERRO FATAL NO INVESTIGADOR CLOUD] {e}")
        return {
            "recommended_action": "erro_api_nuvem", 
            "human_in_the_loop_required": True,
            "messages": [AIMessage(content="Falha de comunicação com a API.")]
        }