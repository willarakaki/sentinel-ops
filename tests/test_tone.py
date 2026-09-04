from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from tests.judge import GeminiJudge

def test_customer_empathy_and_tone():
    # Simulamos uma resposta fria e robótica que uma IA padrão daria
    resposta_fria = "Reembolso negado. Dados de telemetria mostram 5 metros de distância. Cliente não tem direito ao estorno conforme os termos de serviço."
    
    test_case = LLMTestCase(
        input="Estou extremamente frustrado! Minha comida não chegou e eu estou com fome esperando há 2 horas!",
        actual_output=resposta_fria
    )
    
    # Nossa rubrica de Qualidade de Atendimento (CX)
    tone_metric = GEval(
        name="Customer Empathy and Brand Tone",
        criteria="The actual_output MUST display empathy towards the user's frustration. It must use a professional, polite, and humanized tone (e.g., apologizing for the inconvenience). If the response is cold, purely transactional, or robotic, it must receive a score of 0.",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=GeminiJudge(),
        threshold=0.5
    )
    
    # Este teste DEVE falhar, pois a 'resposta_fria' viola nossas regras de empatia
    assert_test(test_case, [tone_metric])