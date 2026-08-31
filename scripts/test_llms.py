import sys
from pathlib import Path

# Adiciona a raiz do projeto ao escopo de importação do Python
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from sentinel.core.llm_factory import LLMFactory

def run_smoke_test():
    print("Iniciando Smoke Test dos Motores de IA do SentinelOps...\n")
    
    try:
        # 1. Testando o SLM Local (Ollama / RTX 3070)
        print("--- 1. Testando SLM Local (Ollama Llama 3.2 3B) ---")
        slm = LLMFactory.get_local_slm()
        response_slm = slm.invoke("Diga exatamente 'Olá, Sentinel! Rodando 100% local.' e nada mais.")
        print(f"[SUCESSO] Retorno SLM: {response_slm.content}\n")
        
        # 2. Testando o LLM Cloud (Gemini Flash)
        print("--- 2. Testando Cloud LLM (Google Gemini) ---")
        cloud_llm = LLMFactory.get_cloud_model()
        response_cloud = cloud_llm.invoke("Diga exatamente 'Olá, Sentinel! Conectado à nuvem.' e nada mais.")
        print(f"[SUCESSO] Retorno Cloud: {response_cloud.content}\n")
        
        print("=== TESTE CONCLUÍDO: Todos os motores estão operacionais! ===")
        
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] Falha na integração: {e}")
        print("Verifique se o 'docker-compose up -d' está rodando e se sua GOOGLE_API_KEY está no .env.")

if __name__ == "__main__":
    run_smoke_test()