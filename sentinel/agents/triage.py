import json
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from sentinel.core.llm_factory import LLMFactory
from sentinel.schemas.state import DisputeState

# ==========================================
# 1. CONTRATO DE SAÍDA DO SLM
# ==========================================
class TriageOutput(BaseModel):
    intent: str = Field(description="A intenção principal do cliente. Ex: atraso, item_faltante, cobranca_indevida.")
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
    
    # Extrai o schema como dict e converte para string formatada
    schema_string = json.dumps(TriageOutput.model_json_schema(), indent=2)
    
    # 3. Engenharia de Prompt focada em SLM (Direta e com Schema explícito)
    system_prompt = f"""Você é um analista de triagem de primeira linha.
        Sua única função é ler a queixa do cliente e retornar EXATAMENTE um objeto JSON válido.
        Não inclua nenhum texto adicional antes ou depois do JSON.

        Esquema JSON obrigatório:
        {schema_string}

        Regras de Risco:
        - 'baixo': Dúvidas simples, atrasos pequenos.
        - 'moderado': Item faltante de baixo valor.
        - 'elevado': Valores altos, xingamentos, ameaças de processo.
        - 'critico': Suspeita clara de fraude ou invasão de conta.
        """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Queixa do cliente: {customer_message}")
    ]
    
    # 4. Executa a inferência
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
        
    except Exception as e:
        # Padrão Sênior de Resiliência: Fail-Safe para bloqueio humano
        print(f"[ERRO NA TRIAGEM SLM] {e}. Aplicando Fallback de Segurança (Risco Elevado).")
        return {
            "intent": "classificacao_falhou",
            "risk_level": "elevado"
        }