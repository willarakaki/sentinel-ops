import json
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from tenacity import retry, stop_after_attempt, wait_random_exponential

from sentinel.core.llm_factory import LLMFactory
from sentinel.schemas.state import DisputeState
from sentinel.tools.database import get_delivery_telemetry, get_customer_history
from sentinel.core.privacy import mask_pii
from sentinel.core.cache import semantic_cache
from sentinel.tools.database import get_delivery_telemetry, get_customer_history, get_customer_profile
from sentinel.core.cache_signature import build_trust_signature, signature_to_text
from sentinel.core.sandbox import apply_sandbox_override

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
    stop=stop_after_attempt(3),
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
    sandbox_active = bool(sandbox_receipt)
    
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
            
    
    # ---------------------------------------------------------
    # 3. PREPARAÇÃO DA CHAMADA (CACHE MISS)
    # ---------------------------------------------------------
    intent = state.get("intent", "desconhecida")
    amount = state.get("dispute_amount", 0.0)
    
    customer_id = state.get("customer_id")
    ticket_id = state.get("ticket_id")
    
    evidence_text = "\n".join(tool_responses)
    
    system_prompt = f"""Você é um Investigador Sênior de Prevenção a Perdas, Compliance e Risco Corporativo.
            Valor Total do Pedido (Teto Máximo): R$ {amount} | Intenção: {intent} | Cliente: {customer_id} | Ticket: {ticket_id}
            
            SUA MISSÃO INICIAL:
            1. USE as ferramentas de telemetria e histórico para investigar a queixa. NUNCA decida sem dados!
            2. IMPORTANTE: Utilize APENAS o Cliente e o Ticket acima para consultar as ferramentas.

            ⚖️ CONSTITUIÇÃO DA EMPRESA (REGRAS DE ARBITRAGEM ABSOLUTAS):
            - REGRA 1 (COMPLIANCE E LEI): Sem OTP em item restrito? NEGUE. Liability: 'nenhum'.
            - REGRA 2 (PROTEÇÃO AO TRABALHADOR): Espera do entregador > 5 a 10 min? NEGUE (No-Show). Liability: 'nenhum'.
            - REGRA 3 (ABUSO SISTEMÁTICO): Cliente com histórico Alto de disputas/No-Show? NEGUE.
            - REGRA 4 (RETENÇÃO E LTV): Cliente LTV alto/B2B e erro logístico? APROVE justificando o LTV.
            - REGRA 5 (REEMBOLSO PARCIAL EXATO E LIABILITY): Falta de UM item (ex: batata)? Você OBRIGATORIAMENTE deve ler o [RECIBO DOS ITENS DO PEDIDO], localizar o item reclamado e aprovar APENAS o preço exato dele (ignorando o Teto Máximo). Liability: 'restaurante'. Erro na entrega inteira? Liability: 'entregador' ou 'plataforma'.

            🛡️ ANCORAGEM ESTRITA: Baseie-se APENAS nas ferramentas.
            Seja direto e conciso na justificativa para economizar tokens. Chame a ferramenta 'InvestigatorOutput' para concluir.
            """
    
    messages_to_cloud = [SystemMessage(content=system_prompt)] + sanitized_messages
    
    # --- FUNÇÃO INTERNA PARA PROCESSAR A SAÍDA (Evita repetição de código) ---
    def process_llm_response(response, is_fallback=False):
        if response.tool_calls and response.tool_calls[0]["name"] == "InvestigatorOutput":
            args = response.tool_calls[0]["args"]
            
            if tool_responses and not sandbox_active:
                # Reconstrói a mesma "forma" de chave que o hydrate usa, com os
                # mesmos dados de origem (perfil + telemetria real), nunca com
                # o histórico bruto do cliente.
                profile = get_customer_profile(customer_id)
                telemetry_only = get_delivery_telemetry.invoke({"ticket_id": ticket_id})
                if profile:
                    trust_signature = build_trust_signature(profile)
                    trust_text = signature_to_text(trust_signature)
                    cache_key = semantic_cache.build_cache_key(masked_query, telemetry_only, trust_text)
                    semantic_cache.save_to_cache(
                        query=cache_key,
                        action=args["recommended_action"],
                        justification=args["justification"],
                        approved_refund_amount=args.get("approved_refund_amount", 0.0),
                        liability=args.get("liability", "nenhum"),
                        dispute_amount_total=amount,
                        trust_signature=trust_signature,
                    )
            
            tag_modo = " (VIA SLM LOCAL)" if is_fallback else ""
            parecer_final = (
                f"Parecer Baseado em Dados{tag_modo}: {args['justification']}\n\n"
                f"💰 **Valor Aprovado:** R$ {args['approved_refund_amount']:.2f}\n"
                f"⚖️ **Responsabilidade (Liability):** {args['liability'].upper()}"
            )
            return {
                "recommended_action": args["recommended_action"],
                "human_in_the_loop_required": args["human_in_the_loop_required"],
                "messages": [AIMessage(content=parecer_final)]
            }
        
        print(f"[AÇÃO DO AGENTE] Buscando dados... Ferramentas: {[t['name'] for t in response.tool_calls]}")
        return {"messages": [response]}
    # -------------------------------------------------------------------------

    # TENTATIVA 1: NUVEM (Gemini) COM BACKOFF
    try:
        response = invoke_with_backoff(llm_with_tools, messages_to_cloud)
        return process_llm_response(response, is_fallback=False)
        
    except Exception as cloud_error:
        print(f"\n⚠️ [ALERTA FINOPS/REDE] LLM Cloud falhou ou excedeu cota: {cloud_error}")
        print("🔄 [CIRCUIT BREAKER] Acionando Graceful Degradation para SLM Local (Qwen 2.5)...")
        
        # TENTATIVA 2: FALLBACK LOCAL (Ollama na GPU)
        try:
            local_slm = LLMFactory.get_local_slm(temperature=0.1)
            local_llm_with_tools = local_slm.bind_tools(db_tools + [InvestigatorOutput])
            
            # Adicionamos um aviso para o SLM saber que está operando o roteamento principal
            fallback_prompt = SystemMessage(content="[MODO CONTINGÊNCIA] A API principal caiu. Assuma o controle da investigação.")
            messages_to_local = [fallback_prompt, SystemMessage(content=system_prompt)] + sanitized_messages
            
            # Invoca direto, sem backoff de rede
            response_local = local_llm_with_tools.invoke(messages_to_local)
            print("✅ [FALLBACK CONCLUÍDO] SLM Local assumiu a carga com sucesso.")
            
            return process_llm_response(response_local, is_fallback=True)
            
        except Exception as local_error:
            # TENTATIVA 3: FALHA CATASTRÓFICA (Ambos caíram)
            print(f"❌ [ERRO FATAL DUPLO] Falha na Nuvem e no Local: {local_error}")
            return {
                "recommended_action": "erro_api_duplo", 
                "human_in_the_loop_required": True,
                "messages": [AIMessage(content="🚨 Falha crítica de IA. Nuvem e Edge indisponíveis. Ticket escalado para Humano.")]
            }