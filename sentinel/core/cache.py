from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from sentinel.core.llm_factory import LLMFactory

class SemanticCache:
    def __init__(self):
        print("  🧠 [Cache] Inicializando Banco Vetorial em Memória (FAISS)...")
        self.embeddings = LLMFactory.get_embeddings_model()
        self.vector_store = None
        # 0.2 é um bom ponto de partida para "mesmo significado".
        self.distance_threshold = 0.25 

    def check_cache(self, query: str) -> dict | None:
        """
        Calcula a similaridade geométrica da nova queixa.
        Retorna o veredito armazenado se for um Cache HIT.
        """
        if self.vector_store is None:
            return None # O cache ainda está vazio

        # Busca o vizinho mais próximo (k=1)
        results = self.vector_store.similarity_search_with_score(query, k=1)
        
        if not results:
            return None

        doc, score = results[0]
        
        # Avalia a distância
        if score <= self.distance_threshold:
            print(f"  ⚡ [Semantic Cache] CACHE HIT! Distância L2: {score:.4f}. Reaproveitando inferência.")
            return doc.metadata
            
        print(f"  🐢 [Semantic Cache] CACHE MISS. Distância {score:.4f} é maior que o limite. Nuvem acionada.")
        return None

    def save_to_cache(self, query: str, action: str, justification: str):
        """
        Salva a queixa (vetorizada) e a decisão (metadados) para uso futuro.
        """
        doc = Document(
            page_content=query, 
            metadata={"recommended_action": action, "justification": justification}
        )
        
        if self.vector_store is None:
            # Se for o primeiro item, inicializamos o FAISS
            self.vector_store = FAISS.from_documents([doc], self.embeddings)
        else:
            # Caso contrário, apenas adicionamos ao banco existente
            self.vector_store.add_documents([doc])
            
        print("  💾 [Semantic Cache] Novo padrão de resolução salvo na memória RAM.")

# Instância global (Singleton) para ser importada pelos agentes
semantic_cache = SemanticCache()