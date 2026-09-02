import sys
import warnings
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage

# Suprime avisos para manter o terminal limpo
warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Importa o orquestrador principal compilado
from sentinel.graph import sentinel_app

def format_stream_output(stream):
    """Itera sobre os passos do LangGraph e imprime a jornada com foco no ReAct."""
    for step in stream:
        for node_name, node_state in step.items():
            print(f"  🔄 [Passo Executado] Nó: '{node_name}'")
            
            if node_name == "tools":
                print(f"  🗄️  [DuckDB - Dados Extraídos]:\n{node_state['messages'][-1].content}\n")
            
            elif node_name == "investigator":
                # Usa .get e verifica se a lista não está vazia
                messages = node_state.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    if isinstance(last_message, AIMessage) and not getattr(last_message, 'tool_calls', True):
                        print(f"  ⚖️  [Veredito Gemini]: {last_message.content}\n")
                else:
                    print(f"  ⚠️ [Fallback Executado] Ação: {node_state.get('recommended_action')}\n")
            else:
                print(f"  📝 [Estado Delta] {node_state}\n")

def run_graph_tests():
    print("Iniciando Testes de Integração Híbrida (ReAct + DuckDB)...\n")
    
    # ==========================================
    # CASO 1: CAMINHO FINOPS (Auto Refund)
    # ==========================================
    print("--- [TESTE 1: Ticket Micro (R$ 15,00) - Baixo Risco] ---")
    config_1 = {"configurable": {"thread_id": "TKT-1001"}}
    input_1 = {
        "messages": [HumanMessage(content="Meu pedido atrasou um pouco, mas já chegou.")],
        "ticket_id": "TKT-1001",
        "customer_id": "CUST-ABC",
        "dispute_amount": 15.00
    }
    format_stream_output(sentinel_app.stream(input_1, config=config_1))
    
    # ==========================================
    # CASO 2: CAMINHO DEFENSIVO (Human Review direto via SLM)
    # ==========================================
    print("\n--- [TESTE 2: Ticket Alto (R$ 500,00) - Risco Elevado] ---")
    config_2 = {"configurable": {"thread_id": "TKT-1002"}}
    input_2 = {
        "messages": [HumanMessage(content="Sua plataforma é um lixo! Comida fria. Devolvam meus 500 reais agora ou vou no PROCON!")],
        "ticket_id": "TKT-1002",
        "customer_id": "CUST-XYZ",
        "dispute_amount": 500.00
    }
    format_stream_output(sentinel_app.stream(input_2, config=config_2))

    # ==========================================
    # CASO 3: CAMINHO HÍBRIDO (ReAct Loop + DuckDB)
    # ==========================================
    print("\n--- [TESTE 3: Ticket Moderado (R$ 80,00) - Necessita Arbitragem com Dados] ---")
    config_3 = {"configurable": {"thread_id": "TKT-1003"}}
    input_3 = {
        "messages": [HumanMessage(content="Comprei dois combos, mas um deles veio sem a batata grande e o molho extra. Gostaria de receber o reembolso parcial.")],
        "ticket_id": "TKT-1003",
        "customer_id": "CUST-HBR",
        "dispute_amount": 80.00
    }
    format_stream_output(sentinel_app.stream(input_3, config=config_3))
    
    print("=== TESTES DE INTEGRAÇÃO CONCLUÍDOS ===")

if __name__ == "__main__":
    run_graph_tests()