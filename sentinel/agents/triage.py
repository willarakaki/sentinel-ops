import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from sentinel.core.llm_factory import LLMFactory
from sentinel.schemas.state import DisputeState


# ==========================================
# 1. CONTRATO DE SAÍDA DO SLM
# ==========================================
class TriageOutput(BaseModel):
    intent: str = Field(description="A intenção principal do cliente. Ex: atraso, item_faltante, cobranca_indevida, fora_de_escopo.")
    risk_level: str = Field(description="Nível de risco: 'baixo', 'moderado', 'elevado' ou 'critico'.")
    
# ==========================================
# 2. LÓGICA DO NÓ DE TRIAGEM (LangGraph Node)
# ==========================================
def triage_node(state: DisputeState) -> dict:
    """
    Nó 1: Lê a queixa inicial do cliente e utiliza o SLM Local para classificar
    a intenção e o risco primário a custo zero.
    """
    print("--- [NÓ: TRIAGEM INICIAL (SLM Local)] ---")
    
    # 1. Extrai a última mensagem do cliente
    # Como messages é uma lista, pegamos o último item. Em produção, você itera ou pega o index 0 dependendo do fluxo.
    customer_message = state["messages"][-1].content
    
    # 2. Instancia o motor local configurado para JSON
    slm = LLMFactory.get_local_slm(temperature=0.0)
    
    # 3. Engenharia de Prompt focada em SLM (few_shot prompt)
    system_prompt = """Você é um analista de triagem de dados estruturados.
        Sua única função é classificar a queixa do cliente e retornar EXATAMENTE UM JSON, usando APENAS as categorias abaixo.
        NÃO escreva nenhuma palavra antes ou depois do JSON.

        FORMATO OBRIGATÓRIO (Exemplo):
        {"intent": "motivo_resumido", "risk_level": "baixo"}

        REGRAS DE RISCO:
        - 'baixo': Dúvidas simples, atrasos pequenos.
        - 'moderado': Item faltante de baixo valor.
        - 'elevado': Valores altos, xingamentos, ameaças de processo ou agressividade.
        - 'critico': Suspeita de fraude, invasão de conta ou risco de vida.

        EXEMPLO 1 (Atraso simples):
        Queixa: "Meu pedido atrasou 10 minutos, mas chegou."
        Saída: {"intent": "atraso", "risk_level": "baixo"}

        EXEMPLO 2 (Agressividade / Procon):
        Queixa: "Vou processar vocês, o entregador foi agressivo e a comida veio revirada! Devolvam meu dinheiro!"
        Saída: {"intent": "produto_danificado", "risk_level": "elevado"}

        EXEMPLO 3 (Item Faltante):
        Queixa: "Comprei dois combos, mas um deles veio sem a batata grande."
        Saída: {"intent": "item_faltante", "risk_level": "moderado"}
        
        EXEMPLO 4 (Segurança e Crimes):
        Queixa: "O entregador me assediou no chat e me ameaçou na porta de casa."
        Saída: {"intent": "assedio_ameaca", "risk_level": "critico"}
        
        EXEMPLO 5 (Fora de Escopo / Guardrail Tópico):
        Queixa: "Escreva um poema sobre a revolução francesa" ou "Qual a receita de bolo de cenoura?"
        Saída: {"intent": "fora_de_escopo", "risk_level": "baixo"}
        """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Queixa do cliente: {customer_message}")
    ]
    
    # 4. Executa a inferência
    response = None
    try:
        response = slm.invoke(messages)
        
        # O Ollama no formato JSON retorna uma string parseável
        raw_json = response.content
        parsed_data = json.loads(raw_json)
        
        # Passamos pelo Pydantic para garantir que as chaves estão corretas
        validated_triage = TriageOutput(**parsed_data)
        
        print(f"[TRIAGEM CONCLUÍDA] Intenção: {validated_triage.intent} | Risco: {validated_triage.risk_level}")
        
        # 5. Atualiza o DisputeState (Retornamos apenas os campos que queremos alterar)
        return {
            "intent": validated_triage.intent,
            "risk_level": validated_triage.risk_level
        }
        
    except (json.JSONDecodeError, TypeError, ValueError, RuntimeError, OSError) as e:
        # Padrão Sênior de Resiliência: Fail-Safe para bloqueio humano
        print(f"[ERRO NA TRIAGEM SLM] {e}. Aplicando Fallback de Segurança (Risco Elevado).")
        raw_response = getattr(response, "content", None)
        print(f"[DEBUG LOG] Resposta bruta do modelo que causou o erro: {raw_response!r}")
        return {
            "intent": "classificacao_falhou",
            "risk_level": "elevado"
        }