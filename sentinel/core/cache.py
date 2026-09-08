import os
import threading

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langsmith import traceable

from sentinel.core.llm_factory import LLMFactory

CACHE_DIR = os.path.join(os.getcwd(), "data", "faiss_cache_v2")


class SemanticCache:
    def __init__(self):
        print("  🧠 [Cache] Inicializando Gerenciador de Banco Vetorial...")
        self.embeddings = LLMFactory.get_embeddings_model()
        self.distance_threshold = 0.15
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
                    normalize_L2=True,  # ESSENCIAL: sem isso, o índice recarregado
                    # do disco volta com normalize_L2=False (default da classe),
                    # e passa a comparar a query CRUA contra vetores normalizados
                    # já salvos — a distância L2 nunca mais cai perto do threshold,
                    # mesmo para texto idêntico. Isso é o que causava MISS eterno
                    # após o primeiro save+reload.
                )
                print(f"  🧠 [Cache] Banco FAISS carregado do disco ({CACHE_DIR}).")
            except (OSError, RuntimeError, ValueError) as e:
                # Protege contra diretório corrompido (ex.: processo morreu no meio
                # de um save_local anterior).
                print(f"  ⚠️ [Cache] Falha ao carregar cache do disco ({e}). Iniciando vazio.")
                self.vector_store = None
        else:
            print("  🧠 [Cache] Nenhum banco encontrado no disco. Iniciando vazio.")
            self.vector_store = None

    @traceable(run_type="retriever", name="Consultar_Semantic_Cache")
    def check_cache(self, query: str, ticket_id: str, current_amount: float | None = None, trust_signature: dict | None = None) -> dict | None:
        if self.vector_store is None:
            return None

        with self._lock:
            results = self.vector_store.similarity_search_with_score(query, k=1)
        if not results:
            return None

        doc, score = results[0]
        if score > self.distance_threshold:
            print(f"  🐢 [Semantic Cache] MISS. Distância {score:.4f} acima do limite.")
            return None

        if doc.metadata.get("ticket_id") != ticket_id:
            print(
                f"  🛡️ [Semantic Cache] MISS. Ticket incompatível "
                f"(cache: {doc.metadata.get('ticket_id')}, atual: {ticket_id})."
            )
            return None

        # Filtro rígido por bucket — defesa em profundidade além da distância
        # do embedding (que pode errar por imprecisão do modelo).
        if trust_signature:
            cached_sig = doc.metadata.get("trust_signature") or {}
            mismatched = [k for k in trust_signature if cached_sig.get(k) != trust_signature[k]]
            if mismatched:
                print(f"  🛡️ [Semantic Cache] MISS. Perfil de confiança incompatível em {mismatched} "
                    f"(cache: {cached_sig}, atual: {trust_signature}).")
                return None

        # Nunca reaproveita automaticamente um veredito que já pedia revisão
        # humana ou que veio de uma falha dupla de API — essas decisões são
        # inerentemente incertas e não deveriam virar precedente automático.
        if doc.metadata.get("recommended_action") in ("escalar_humano", "erro_api_duplo"):
            print("  🛡️ [Semantic Cache] MISS. Veredito em cache exige revisão humana, não reaproveitado.")
            return None

        cached_total = doc.metadata.get("dispute_amount_total")
        if current_amount and cached_total is not None and current_amount > 0:
            drift = abs(cached_total - current_amount) / current_amount
            if drift > self.amount_tolerance:
                print(f"  ⚠️ [Semantic Cache] MISS. Teto incoerente (cache: R$ {cached_total:.2f} vs atual: R$ {current_amount:.2f}).")
                return None

        print(f"  ⚡ [Semantic Cache] HIT! Distância L2: {score:.4f}.")
        return doc.metadata

    def build_cache_key(self, ticket_id: str, query_masked: str, telemetry_text: str, trust_signature_text: str) -> str:
        """Note: não recebe mais o texto cru do histórico do cliente — só a
        queixa mascarada, a telemetria (fatos do ticket) e a assinatura
        bucketizada de confiança."""
        return f"[Ticket]: {ticket_id}\n[Queixa]: {query_masked}\n{trust_signature_text}\n[Evidências Logísticas]: {telemetry_text}"

    @traceable(run_type="tool", name="Salvar_no_Semantic_Cache")
    def save_to_cache(self, query, ticket_id, action, justification, approved_refund_amount=None,
                    liability=None, dispute_amount_total=None, trust_signature=None):
        if action in ("escalar_humano", "erro_api_duplo"):
            print("  🛡️ [Semantic Cache] Não cacheando: decisão exige revisão humana / falha de API.")
            return

        metadata = {"ticket_id": ticket_id, "recommended_action": action, "justification": justification}
        if approved_refund_amount is not None:
            metadata["approved_refund_amount"] = approved_refund_amount
        if liability is not None:
            metadata["liability"] = liability
        if dispute_amount_total is not None:
            metadata["dispute_amount_total"] = dispute_amount_total
        if trust_signature is not None:
            metadata["trust_signature"] = trust_signature

        doc = Document(page_content=query, metadata=metadata)
        with self._lock:
            if self.vector_store is None:
                self.vector_store = FAISS.from_documents([doc], self.embeddings, normalize_L2=True)
            else:
                self.vector_store.add_documents([doc])
            self.vector_store.save_local(CACHE_DIR)
        print(f"  💾 [Semantic Cache] Padrão salvo em {CACHE_DIR}.")


# Instância global (Singleton) para ser importada pelos agentes
semantic_cache = SemanticCache()