from typing import Annotated, TypedDict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class DisputeState(TypedDict):
    """
    Contrato de Estado Global (Prancheta de Investigação) do SentinelOps.
    Este estado trafega por todos os nós do LangGraph e é salvo no Checkpointer (SQLite).
    """
    
    # 1. Memória do Grafo (Conversas, pensamentos e chamadas de ferramentas)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # 2. Dados Críticos de Entrada (Input do Ticket)
    ticket_id: str
    customer_id: str
    dispute_amount: float
    
    # 3. Metadados de Triagem (Preenchidos pelo SLM Local / Ollama)
    risk_level: str | None
    intent: str | None
    
    # 4. Contexto de Investigação (Preenchidos via MCP / DuckDB)
    # Ex: Histórico de fraudes do cliente, status do GPS do entregador, etc.
    telemetry_data: dict[str, Any] | None
    
    # 5. Veredito e Auditoria (Preenchidos pelo LLM Cloud / Gemini ou Regra de Negócio)
    recommended_action: str | None
    human_in_the_loop_required: bool