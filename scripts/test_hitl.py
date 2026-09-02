import sys
import warnings
from pathlib import Path
from langchain_core.messages import HumanMessage

warnings.filterwarnings("ignore")
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from sentinel.graph import sentinel_app

def run_hitl_simulation():
    print("Iniciando Simulação Human-in-the-Loop (HITL)...\n")
    
    # 1. IDENTIFICAÇÃO (A Chave de Idempotência)
    ticket_id = "TKT-9999"
    config = {"configurable": {"thread_id": ticket_id}}
    
    # 2. ENTRADA DE ALTO RISCO (Força o roteamento para a revisão humana)
    input_data = {
        "messages": [HumanMessage(content="Vocês são golpistas! Roubaram meu dinheiro, vou acionar a polícia agora! Devolvam meus R$ 1000,00")],
        "ticket_id": ticket_id,
        "customer_id": "CUST-ANGER",
        "dispute_amount": 1000.00
    }
    
    print("--- [Fase 1: Triagem e Roteamento] ---")
    for step in sentinel_app.stream(input_data, config=config):
        for node_name, node_state in step.items():
            print(f"  🔄 [Passo Executado] Nó: '{node_name}'")
            
    # 3. VERIFICAÇÃO DO CONGELAMENTO
    current_state = sentinel_app.get_state(config)
    print("\n--- [Fase 2: Grafo Congelado (Aguardando Humano)] ---")
    print(f"Próximo Nó Pendente: {current_state.next}")
    
    if "human_review" in current_state.next:
        print("\n⏳ ALERTA: Ticket bloqueado. Aguardando ação do Analista Sênior no Backoffice.")
        print(f"Dados na prancheta: Risco = {current_state.values.get('risk_level')}")
        
        # Simula o tempo passando... o humano loga no painel e clica em "Negar Disputa (Fraude)"
        input("\n[Simulação de Painel UI] Pressione ENTER para o analista negar a disputa...")
        
        # 4. INJEÇÃO DA DECISÃO HUMANA (Sobrescrevendo a prancheta)
        print(">> Injetando decisão humana no Checkpointer (SQLite)...")
        sentinel_app.update_state(
            config, 
            {"recommended_action": "negado_por_fraude_manual", "human_in_the_loop_required": False}
        )
        
        # 5. RETOMADA DO GRAFO (Resume)
        print("\n--- [Fase 3: Retomada do Orquestrador] ---")
        # Passar None faz o grafo acordar e processar os nós que estavam em "next"
        for step in sentinel_app.stream(None, config=config):
            for node_name, node_state in step.items():
                print(f"  🔄 [Passo Executado] Nó: '{node_name}'")
                print(f"  📝 [Veredito Final] Ação: {node_state.get('recommended_action')}")
                
    print("\n=== SIMULAÇÃO HITL CONCLUÍDA ===")

if __name__ == "__main__":
    run_hitl_simulation()