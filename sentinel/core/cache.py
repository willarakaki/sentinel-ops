import os
import threading
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langsmith import traceable
from sentinel.core.llm_factory import LLMFactory

CACHE_DIR = os.path.join(os.getcwd(), "data", "faiss_cache")


class SemanticCache:
    def __init__(self):
        print("  🧠 [Cache] Inicializando Gerenciador de Banco Vetorial...")
        self.embeddings = LLMFactory.get_embeddings_model()
        self.distance_threshold = 0.12
        # Tolerância de divergência de valor entre o veredito em cache e a disputa
        # atual, usada como guarda anti-poisoning (0.2 = 20%).
        self.amount_tolerance = 0.2
        # Protege contra escritas concorrentes vindas de sessões/threads diferentes
        # (ex.: várias sessões simultâneas do Streamlit no mesmo processo).
        # Não protege contra múltiplos PROCESSOS/workers escrevendo ao mesmo tempo —
        # nesse caso é necessário um lock de arquivo (ex.: pacote `filelock`).
        self._lock = threading.Lock()

        # Tenta carregar o cache do disco para sobreviver a restarts do processo,
        # múltiplos workers ou redeploys.
        if os.path.exists(CACHE_DIR):
            try:
                self.vector_store = FAISS.load_local(
                    CACHE_DIR,
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
                print(f"  🧠 [Cache] Banco FAISS carregado do disco ({CACHE_DIR}).")
            except Exception as e:
                # Protege contra diretório corrompido (ex.: processo morreu no meio
                # de um save_local anterior).
                print(f"  ⚠️ [Cache] Falha ao carregar cache do disco ({e}). Iniciando vazio.")
                self.vector_store = None
        else:
            print("  🧠 [Cache] Nenhum banco encontrado no disco. Iniciando vazio.")
            self.vector_store = None

    @traceable(run_type="retriever", name="Consultar_Semantic_Cache")
    def check_cache(self, query: str, current_amount: float | None = None) -> dict | None:
        """
        Calcula a similaridade geométrica da nova queixa+evidências.
        Retorna o veredito armazenado se for um Cache HIT E o valor aprovado
        em cache for coerente com o valor da disputa atual (guarda anti-poisoning).
        """
        if self.vector_store is None:
            return None  # O cache ainda está vazio

        with self._lock:
            results = self.vector_store.similarity_search_with_score(query, k=1)

        if not results:
            return None

        doc, score = results[0]

        if score > self.distance_threshold:
            print(f"  🐢 [Semantic Cache] CACHE MISS. Distância {score:.4f} é maior que o limite. Nuvem acionada.")
            return None

        # Guarda anti-poisoning: mesmo com texto parecido, um valor de estorno muito
        # diferente indica que são casos distintos (o texto templatizado das
        # evidências pode colapsar disputas diferentes no espaço vetorial).
        cached_amount = doc.metadata.get("approved_refund_amount")
        if current_amount and cached_amount is not None:
            drift = abs(cached_amount - current_amount) / current_amount
            if drift > self.amount_tolerance:
                print(
                    f"  ⚠️ [Semantic Cache] Similaridade textual OK (dist {score:.4f}) mas valor incoerente "
                    f"(cache: R$ {cached_amount:.2f} vs atual: R$ {current_amount:.2f}). Tratando como MISS."
                )
                return None

        print(f"  ⚡ [Semantic Cache] CACHE HIT! Distância L2: {score:.4f}. Reaproveitando inferência.")
        return doc.metadata

    def build_cache_key(self, query_masked: str, telemetry_data: str) -> str:
        """
        Monta uma Chave Composta. Isso previne o 'Cache Poisoning' baseado só em
        texto: a telemetria/evidências entram na chave, não só a queixa.
        """
        return f"[Queixa]: {query_masked}\n[Evidências]: {telemetry_data}"

    @traceable(run_type="tool", name="Salvar_no_Semantic_Cache")
    def save_to_cache(
        self,
        query: str,
        action: str,
        justification: str,
        approved_refund_amount: float | None = None,
        liability: str | None = None,
    ):
        """
        Salva a queixa+evidências (vetorizada) e o veredito completo para uso futuro,
        persistindo em disco para sobreviver a restarts do processo.
        """
        metadata = {"recommended_action": action, "justification": justification}
        if approved_refund_amount is not None:
            metadata["approved_refund_amount"] = approved_refund_amount
        if liability is not None:
            metadata["liability"] = liability

        doc = Document(page_content=query, metadata=metadata)

        with self._lock:
            if self.vector_store is None:
                self.vector_store = FAISS.from_documents(
                    [doc],
                    self.embeddings,
                    normalize_L2=True,
                )
            else:
                self.vector_store.add_documents([doc])

            self.vector_store.save_local(CACHE_DIR)

        print(f"  💾 [Semantic Cache] Padrão salvo e persistido em {CACHE_DIR}.")


# Instância global (Singleton) para ser importada pelos agentes
semantic_cache = SemanticCache()