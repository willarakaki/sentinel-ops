from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from config.settings import settings

class LLMFactory:
    """
    Fábrica centralizada para instanciar Modelos de Linguagem (LLMs) e SLMs locais.
    Implementa o padrão Factory para facilitar a substituição de provedores e evitar Vendor Lock-in.
    """
    
    @staticmethod
    def get_cloud_model(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
        """
        Retorna o LLM de Nuvem (Gemini Flash) para raciocínio complexo.
        Utilizado para arbitragem final e geração do Dossiê A2UI.
        """
        
        return ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            google_api_key=settings.google_api_key
            temperature=temperature,
            max_tokens=2048,
            max_retries=3
        )
        
    @staticmethod
    def get_local_slm(temperature: float = 0.0) -> ChatOllama:
        """
        Retorna o SLM Local (Ollama Llama 3.2 3B) executando na GPU/Localhost.
        Utilizado para triage primária, roteamento e mascaramento de PII (zero cost).
        """
        return ChatOllama(
            model="llama3.2",
            base_url=settings.ollama_base_url,
            temperature=temperature,
            # Parâmetros otimizados para inferência rápida na minha máquina (laptop RTX 3070)
            num_predict=512,
            format="json" # Força o modelo a cuspir JSON para facilitar o roteamento
        )
        