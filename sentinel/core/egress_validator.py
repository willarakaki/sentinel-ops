import math
from typing import Any

_ALLOWED_ACTIONS = {"aprovar_reembolso", "negar_disputa", "escalar_humano"}
_ALLOWED_LIABILITIES = {"restaurante", "entregador", "plataforma", "nenhum"}

class EgressValidationError(ValueError):
    """Indica que uma decisão gerada não respeita as invariantes de negócio."""

def validate_egress(
    decision: dict[str, Any],
    *,
    dispute_amount: float,
    receipt_total_amount: float | None = None,
) -> dict[str, Any]:
    """
    Valida e devolve uma decisão segura para sair do fluxo de IA.
    Opera 100% baseada em matemática pura (float) para prevenir Injeções Logísticas.
    """
    action = decision.get("recommended_action")
    amount = decision.get("approved_refund_amount")
    liability = str(decision.get("liability", "")).lower()

    # 1. Checagem Estrutural
    if action not in _ALLOWED_ACTIONS:
        raise EgressValidationError(f"Ação de saída inválida: {action!r}.")
    if not isinstance(amount, (int, float)) or not math.isfinite(float(amount)) or amount < 0:
        raise EgressValidationError("Valor de reembolso inválido ou negativo.")
    if not math.isfinite(float(dispute_amount)) or dispute_amount < 0:
        raise EgressValidationError("Valor da disputa (Teto Máximo) inválido.")
        
    # 2. Invariantes Financeiras Relativas
    if amount > dispute_amount:
        raise EgressValidationError(f"Reembolso (R$ {amount}) superior ao valor da disputa (R$ {dispute_amount}).")
        
    if liability not in _ALLOWED_LIABILITIES:
        raise EgressValidationError(f"Responsabilidade inválida: {liability!r}.")

    # 3. Validação Segura do Recibo (Fonte de Verdade do DuckDB/State)
    if receipt_total_amount is not None:
        if not math.isfinite(float(receipt_total_amount)) or receipt_total_amount < 0:
            raise EgressValidationError("Total do recibo fornecido é matematicamente inválido.")
        if amount > receipt_total_amount:
            raise EgressValidationError(f"Reembolso (R$ {amount}) superior ao total real do recibo (R$ {receipt_total_amount}).")

    # 4. Invariantes Lógicas de Negócio
    if action == "negar_disputa" and amount != 0:
        raise EgressValidationError("Disputa negada DEVE ter reembolso cravado em zero.")
    if action == "aprovar_reembolso" and amount <= 0:
        raise EgressValidationError("Reembolso aprovado DEVE ter valor positivo.")
    if action == "escalar_humano" and not decision.get("human_in_the_loop_required", False):
        raise EgressValidationError("Ação 'escalar_humano' exige flag human_in_the_loop_required=True.")

    # 5. Saída Sanitizada
    validated = dict(decision)
    validated["approved_refund_amount"] = float(amount)
    validated["liability"] = liability
    
    return validated