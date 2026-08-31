from langgraph.graph import StateGraph, START, END

from sentinel.schemas.state import DisputeState
from sentinel.agents.triage import triage_node

def build_graph():
    """
    Constrói e compila o Grafo de Estados (FSM) do SentinelOps.
    """
    print("⚙️ Construindo Orquestrador LangGraph...")
    
    # 1. Inicializa o grafo amarrado ao nosso contrato de dados
    workflow = StateGraph(DisputeState)
    
    # 2. Registra os Nós (Os "Agentes/Funcionários")
    workflow.add_node("triage", triage_node)
    
    # 3. Desenha as Arestas Iniciais (O fluxo de trabalho)
    workflow.add_edge(START, "triage")
    
    # IMPORTANTE: Por enquanto, mandamos a triagem direto para o FIM para testar o grafo.
    # Na próxima etapa, substituiremos essa linha por uma "Conditional Edge" (Roteamento).
    workflow.add_edge("triage", END)
    
    # 4. Compila o grafo em um aplicativo executável
    app = workflow.compile()
    
    return app

sentinel_app = build_graph()