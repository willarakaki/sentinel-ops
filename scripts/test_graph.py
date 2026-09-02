import sys
import warnings
from pathlib import Path
from langchain_core.messages import HumanMessage

# Suprime avisos de bibliotecas subjacentes para limpar o log
warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Importa o orquestrador principal compilado
from sentinel.graph import sentinel_app

def format_stream_output(stream):
    """Itera sobre os passos do LangGraph e imprime a jornada do estado."""
    for step in stream:
        for node_name, node_state in step.items():
            print(f"  🔄 [Passo Executado] Nó: '{node_name}'")
            print(f"  📝 [Estado Delta] {node_state}\n")

def run_graph_tests():
    print("Iniciando Testes de Integração do Orquestrador LangGraph...\n")
    
    # ==========================================
    # CASO 1: CAMINHO FINOPS (Auto Refund)
    # ==========================================
    print("--- [TESTE 1: Ticket Micro (R$ 15,00) - Baixo Risco] ---")
    input_1 = {
        "messages": [HumanMessage(content="Meu pedido atrasou um pouco, mas já chegou.")],
        "ticket_id": "TKT-1001",
        "customer_id": "CUST-ABC",
        "dispute_amount": 15.00
    }
    
    config = {"configurable": {"thread_id": "ticket-1001"}}
    # Executa o streaming passo a passo
    format_stream_output(sentinel_app.stream(input_1, config=config))
    
    # ==========================================
    # CASO 2: CAMINHO DEFENSIVO (Human Review / Falha)
    # ==========================================
    print("--- [TESTE 2: Ticket Alto (R$ 500,00) - Risco Elevado] ---")
    input_2 = {
        "messages": [HumanMessage(content="Sua plataforma é um lixo! Comida veio fria, faltou a bebida e a embalagem estava rasgada. Quero meus 500 reais de volta agora ou vou no PROCON!")],
        "ticket_id": "TKT-1002",
        "customer_id": "CUST-XYZ",
        "dispute_amount": 500.00
    }
    
    config = {"configurable": {"thread_id": "ticket-1002"}}
    
    format_stream_output(sentinel_app.stream(input_2, config=config))
    
    # ==========================================
    # CASO 3: CAMINHO HÍBRIDO (Triage Local -> Investigador Cloud)
    # ==========================================
    print("--- [TESTE 3: Ticket Moderado (R$ 80,00) - Necessita Arbitragem] ---")
    input_3 = {
        "messages": [HumanMessage(content="Comprei dois combos, mas um deles veio sem a batata grande e o molho extra. Gostaria de receber o reembolso parcial dos itens que faltaram.")],
        "ticket_id": "TKT-1003",
        "customer_id": "CUST-HBR",
        "dispute_amount": 80.00
    }
    
    config = {"configurable": {"thread_id": "ticket-1003"}}
    
    format_stream_output(sentinel_app.stream(input_3, config=config))
    
    print("=== TESTES DE INTEGRAÇÃO CONCLUÍDOS ===")

if __name__ == "__main__":
    run_graph_tests()