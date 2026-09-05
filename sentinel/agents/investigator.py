import json
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from tenacity import retry, stop_after_attempt, wait_random_exponential

from sentinel.core.llm_factory import LLMFactory
from sentinel.schemas.state import DisputeState
from sentinel.tools.database import get_delivery_telemetry, get_customer_history
from sentinel.core.privacy import mask_pii
from sentinel.core.cache import semantic_cache

# ==========================================
# 1. CONTRATO DE SAÍDA (EVOLUÇÃO FINOPS)
# ==========================================
class InvestigatorOutput(BaseModel):
    """Use esta ferramenta APENAS para submeter o veredito final após coletar evidências."""
    recommended_action: str = Field(description="'aprovar_reembolso', 'negar_disputa', ou 'escalar_humano'.")
    approved_refund_amount: float = Field(description="Valor exato a estornar. 0.0 se negado, valor parcial se faltou só um item, ou total se perda total.")
    liability: str = Field(description="Quem assume o prejuízo: 'restaurante', 'entregador', 'plataforma', ou 'nenhum' (se negado).")
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
    # EXTRAÇÃO DE CONTEXTO E INTERCEPTAÇÃO MIDDLEWARE
    # ---------------------------------------------------------
    masked_query = ""
    tool_responses = []
    sanitized_messages = []
    
    sandbox_receipt = state.get("sandbox_receipt_json", "")
    
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            # Limpa PII e guarda a queixa base para o Cache
            clean_text = mask_pii(msg.content)
            if not masked_query:
                masked_query = clean_text 
            sanitized_messages.append(HumanMessage(content=clean_text))
        elif msg.type == "tool":
            content = msg.content
            
            # 🚀 MIDDLEWARE DE INTERCEPTAÇÃO (Testes Livres sem sujar o DB)
            if msg.name == "get_delivery_telemetry" and sandbox_receipt:
                try:
                    items = json.loads(sandbox_receipt)
                    formatted_sandbox = "\n[⚠️ MODO SANDBOX ATIVO - RECIBO SOBRESCRITO EM MEMÓRIA PARA ESTE TESTE]:\n"
                    formatted_sandbox += "REGRA ABSOLUTA: Ignore o recibo de telemetria original acima. Calcule estornos baseados APENAS nos itens abaixo:\n"
                    for item in items:
                        formatted_sandbox += f"  - {item['item']}: R$ {item['price']:.2f}\n"
                    
                    # Anexa a ordem de sobrescrita diretamente na resposta da ferramenta!
                    content = content + f"\n\n{formatted_sandbox}"
                except:
                    print("Erro ao decodificar JSON do Sandbox no Middleware.")
            
            tool_responses.append(content)
            
            # Precisamos recriar o ToolMessage com o conteúdo alterado para o LLM
            if msg.content != content:
                sanitized_messages.append(ToolMessage(content=content, tool_call_id=msg.tool_call_id, name=msg.name))
            else:
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
    
    customer_id = state.get("customer_id")
    ticket_id = state.get("ticket_id")
    
    system_prompt = f"""Você é um Investigador Sênior de Prevenção a Perdas, Compliance e Risco Corporativo.
            Valor em Disputa: R$ {amount} | Intenção: {intent} | Cliente: {customer_id} | Ticket: {ticket_id}

            SUA MISSÃO INICIAL:
            1. USE as ferramentas de telemetria e histórico para investigar a queixa. NUNCA decida sem dados!
            2. IMPORTANTE: Utilize APENAS o Cliente ({customer_id}) e o Ticket ({ticket_id}) acima para consultar as ferramentas.

            ⚖️ CONSTITUIÇÃO DA EMPRESA (REGRAS DE ARBITRAGEM ABSOLUTAS):
            Ao receber os dados das ferramentas, cruze-os IMEDIATAMENTE com as regras abaixo:

            - REGRA 1 (COMPLIANCE E LEI): Se o pedido requer validação de idade (Álcool/Restritos) e a senha OTP NÃO foi validada, a entrega é ILEGAL. NEGUE a disputa sumariamente, não importa quem seja o cliente ou qual o seu LTV.
            - REGRA 2 (PROTEÇÃO AO TRABALHADOR): Se o tempo de espera do entregador for elevado (ex: > 5 a 10 min) e o pedido não foi entregue, a culpa é do cliente (No-Show). NEGUE o reembolso para proteger o tempo do motoboy.
            - REGRA 3 (ABUSO SISTEMÁTICO): Se o cliente possui um histórico de múltiplas "Ausências na entrega (No-Show)" ou alta taxa de estornos anteriores, trate como Fraude Sistêmica. NEGUE o reembolso mesmo que a evidência atual seja inconclusiva.
            - REGRA 4 (RETENÇÃO E LTV): Se o cliente possui um alto Lifetime Value (ex: LTV > R$ 5000), tipo de conta B2B ou baixo histórico de disputas, E o entregador não validou OTP ou há indícios de dano, priorize a experiência do cliente. APROVE o reembolso justificando o valor histórico do cliente.
            - REGRA 5 (REEMBOLSO PARCIAL EXATO E LIABILITY): Se o cliente reclama de UM item faltante (ex: batata, bebida), você OBRIGATORIAMENTE deve ler o [RECIBO DOS ITENS DO PEDIDO] na telemetria, localizar o item reclamado e aprovar APENAS o preço exato dele (ignorando o Valor Total). A culpa (liability) é do 'restaurante'. Se a queixa for erro na entrega inteira, a culpa é 'entregador' ou 'plataforma' (estorno total). Se negado, liability é 'nenhum' e valor 0.0.

            🛡️ ANCORAGEM ESTRITA (GROUNDING):
            Baseie sua justificativa EXCLUSIVAMENTE nos dados retornados pelas ferramentas. É PROIBIDO presumir, inventar ou mencionar evidências (fotos, assinaturas, conversas) que NÃO estejam explicitamente listadas no retorno do banco.

            Quando terminar de cruzar as evidências com as Regras de Arbitragem, chame a ferramenta 'InvestigatorOutput' para emitir o laudo final.
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
                # Opcional: No futuro você pode salvar o liability no cache também
                semantic_cache.save_to_cache(cache_key, args["recommended_action"], args["justification"])
            
            # Formatando a resposta rica para a Interface (A2UI)
            parecer_final = (
                f"Parecer Baseado em Dados: {args['justification']}\n\n"
                f"💰 **Valor Aprovado:** R$ {args['approved_refund_amount']:.2f}\n"
                f"⚖️ **Responsabilidade (Liability):** {args['liability'].upper()}"
            )

            return {
                "recommended_action": args["recommended_action"],
                "human_in_the_loop_required": args["human_in_the_loop_required"],
                "messages": [AIMessage(content=parecer_final)]
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