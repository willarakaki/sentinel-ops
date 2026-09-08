import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_ollama import OllamaEmbeddings
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
            google_api_key=settings.google_api_key,
            temperature=temperature,
            max_tokens=2048,
            max_retries=3
        )
        
    @staticmethod
    def get_local_slm(temperature: float = 0.0) -> ChatOllama:
        """
        Retorna o SLM Local (Qwen 2.5 7B) executando na GPU/Localhost isolado via Docker.
        Utilizado para triage semântica primária, roteamento híbrido e topical guardrails (zero cost).
        O Qwen foi escolhido pela superioridade em poliglotismo (PT-BR) e aderência ao JSON.
        """
        return ChatOllama(
            model="qwen2.5:7b",
            base_url=settings.ollama_base_url,
            temperature=temperature,
            # Parâmetros otimizados para inferência rápida (adequado para RTX 3070 8GB)
            num_predict=512,
            format="json" # Qwen 2.5 respeita nativamente a saída estruturada
        )
        
    @staticmethod
    def get_security_model(temperature: float = 0.0):
        """
        Retorna o modelo de Segurança Ofensiva (AI WAF).
        Otimizado para rodar junto com o Llama 3.2 na VRAM de 8GB.
        """
        print("  ⚙️ [Factory] Instanciando SLM de Segurança (Llama Guard 3 1B)...")
        return ChatOllama(model="llama-guard3:1b",
                            temperature=temperature,
                            base_url=settings.ollama_base_url
                            )
    
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
        
    @staticmethod
    def get_evaluator_model(temperature=0.0):
        """
        Retorna o modelo configurado estritamente para avaliação e auditoria (LLM-as-a-Judge).
        Temperatura forçada a 0 para garantir determinismo nas métricas do DeepEval.
        """
        print("  ⚙️ [Factory] Instanciando Modelo Juiz (Gemini 3 Flash Preview)...")
        # Substitua por "gemini-1.5-flash" se o 2.0 ainda não estiver disponível na sua key
        return ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=temperature)