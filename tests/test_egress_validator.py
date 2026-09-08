import pytest

from sentinel.core.egress_validator import EgressValidationError, validate_egress


# 1. Teste do Caminho Feliz (Happy Path)
def test_validacao_sucesso_reembolso_parcial():
    decision_mock = {
        "recommended_action": "aprovar_reembolso",
        "approved_refund_amount": 15.00,
        "liability": "restaurante"
    }
    
    # Simulamos um pedido de R$ 50, onde o cliente disputa R$ 15
    result = validate_egress(
        decision_mock,
        dispute_amount=15.00,
        receipt_total_amount=50.00
    )
    
    assert result["approved_refund_amount"] == 15.00
    assert result["liability"] == "restaurante"

# 2. Teste de Alucinação Financeira (Reembolso Maior que o Recibo)
def test_falha_reembolso_maior_que_recibo_real():
    decision_mock = {
        "recommended_action": "aprovar_reembolso",
        "approved_refund_amount": 100.00, # IA enlouqueceu e deu 100 reais
        "liability": "plataforma"
    }
    
    # O Pydantic/Pytest verifica se o erro exato foi disparado
    with pytest.raises(EgressValidationError, match="superior ao total real do recibo"):
        validate_egress(
            decision_mock,
            dispute_amount=100.00,
            receipt_total_amount=50.00 # Mas o recibo só tinha 50 reais
        )

# 3. Teste de Invariante Lógica (Negar Disputa dando dinheiro)
def test_falha_negar_disputa_com_valor():
    decision_mock = {
        "recommended_action": "negar_disputa",
        "approved_refund_amount": 10.00, # Erro lógico: negou, mas estornou dinheiro
        "liability": "nenhum"
    }
    
    with pytest.raises(EgressValidationError, match="DEVE ter reembolso cravado em zero"):
        validate_egress(
            decision_mock,
            dispute_amount=10.00,
            receipt_total_amount=50.00
        )