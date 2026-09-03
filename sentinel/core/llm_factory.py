from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
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
            model="gemini-3.5-flash",
            google_api_key=settings.google_api_key,
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
        
    @staticmethod
    def get_security_model(temperature: float = 0.0):
        """
        Retorna o modelo de Segurança Ofensiva (AI WAF).
        Otimizado para rodar junto com o Llama 3.2 na VRAM de 8GB.
        """
        print("  ⚙️ [Factory] Instanciando SLM de Segurança (Llama Guard 3 1B)...")
        return ChatOllama(model="llama-guard3:1b", temperature=temperature)
    
    @staticmethod
    def get_embeddings_model():
        """
        Retorna o modelo de Embeddings para vetorização de texto.
        Usamos o nomic-embed-text via Ollama (Custo $0, execução local).
        """
        print("  ⚙️ [Factory] Instanciando Modelo de Embeddings (Nomic)...")
        return OllamaEmbeddings(
            model="nomic-embed-text:latest",
            base_url=settings.ollama_base_url,
        )
        