from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from tests.judge import GeminiJudge

def test_high_risk_policy_enforcement():
    contexto_do_banco = [
        "Risk Score do Cliente: HIGH",
        "Disputas Anteriores: 12",
        "Idade da Conta: 2 dias"
    ]
    
    resposta_do_agente = "Devido ao alto risco associado ao perfil e histórico recente, o reembolso automático foi negado. O ticket será escalado para análise manual."
    
    test_case = LLMTestCase(
        input="Por favor, meu pedido não chegou. Poderia me ajudar com o estorno?",
        actual_output=resposta_do_agente,
        retrieval_context=contexto_do_banco
    )
    
    policy_metric = GEval(
        name="Business Policy Adherence",
        criteria="If the retrieval_context indicates a 'HIGH' risk score, the actual_output MUST deny the automatic refund or escalate it to a human. If it approves the refund, it must receive a score of 0.",
        evaluation_params=[LLMTestCaseParams.RETRIEVAL_CONTEXT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=GeminiJudge(),
        threshold=0.5
    )
    
    assert_test(test_case, [policy_metric])