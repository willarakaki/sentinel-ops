import sys
import warnings
from pathlib import Path

# Suprime avisos do SDK para manter o log limpo
warnings.filterwarnings("ignore")

# Garante a importação do pacote principal
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from langchain_core.messages import HumanMessage
from sentinel.agents.triage import triage_node

def run_triage_tests():
    print("Iniciando Validação do Agente de Triagem (SLM Local)...\n")
    
    # ==========================================
    # CASO 1: CENÁRIO DE BAIXO RISCO
    # ==========================================
    print("--- [TESTE 1: Atraso Simples] ---")
    mock_state_1 = {
        "messages": [
            HumanMessage(content="Meu pedido atrasou uns 15 minutos, mas já recebi e estava tudo certo. Só avisando para melhorarem o tempo.")
        ]
    }
    
    resultado_1 = triage_node(mock_state_1)
    print(f"-> Delta Gerado: {resultado_1}\n")
    
    # ==========================================
    # CASO 2: CENÁRIO DE RISCO ELEVADO
    # ==========================================
    print("--- [TESTE 2: Ameaça Legal / Item Faltante] ---")
    mock_state_2 = {
        "messages": [
            HumanMessage(content="Vocês são ridículos! O entregador foi super agressivo, faltou meu refrigerante e metade da comida veio revirada. Vou processar vocês e cancelar meu cartão se não devolverem meu dinheiro AGORA!")
        ]
    }
    
    resultado_2 = triage_node(mock_state_2) # type: ignore
    print(f"-> Delta Gerado: {resultado_2}\n")
    
    print("=== VALIDAÇÃO CONCLUÍDA ===")

if __name__ == "__main__":
    run_triage_tests()