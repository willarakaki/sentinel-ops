# sentinel/core/sandbox.py
import json
import logging
from config.settings import settings

logger = logging.getLogger(__name__)


def apply_sandbox_override(real_telemetry_text: str, sandbox_receipt_json: str, ticket_id: str) -> str:
    """Substitui (não anexa) a telemetria real por dados de teste — e SÓ
    se o modo sandbox estiver habilitado explicitamente por configuração.
    Nunca deve ativar em produção, independente do que vier no state."""
    if not sandbox_receipt_json:
        return real_telemetry_text

    if not settings.enable_sandbox_mode:
        logger.warning(
            "sandbox_receipt_json recebido para o ticket %s mas SENTINEL_ENABLE_SANDBOX "
            "está desligado — ignorando e usando dados reais.", ticket_id
        )
        return real_telemetry_text

    try:
        items = json.loads(sandbox_receipt_json)
    except Exception:
        logger.error("sandbox_receipt_json inválido para o ticket %s.", ticket_id)
        return real_telemetry_text

    logger.warning("MODO SANDBOX ATIVO para o ticket %s — usando recibo de teste.", ticket_id)
    receipt_lines = "\n".join(f"  - {i['item']}: R$ {i['price']:.2f}" for i in items)
    return (
        f"[EVIDÊNCIAS DE TELEMETRIA LOGÍSTICA - DADOS DE TESTE] Ticket: {ticket_id}\n"
        f"[RECIBO DOS ITENS DO PEDIDO]:\n{receipt_lines}\n"
    )