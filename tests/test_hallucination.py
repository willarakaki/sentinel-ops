import pytest
import re
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from dotenv import load_dotenv

from tests.judge import GeminiJudge

load_dotenv()

def test_investigator_grounding():
    contexto_do_banco = [
        "Distância do entregador ao dar baixa: 5 metros.",
        "Código de segurança (OTP) validado: Não"
    ]
    
    resposta_do_agente = "Parecer Baseado em Dados: A entrega foi no local correto. A foto anexada mostra a sacola fechada com lacre. Reembolso negado."
    
    test_case = LLMTestCase(
        input="Meu pedido veio sem a batata.",
        actual_output=resposta_do_agente,
        retrieval_context=contexto_do_banco
    )
    
    # 2. DEFINIÇÃO DA RUBRICA CUSTOMIZADA (A Constituição da Empresa)
    strict_grounding_metric = GEval(
        name="Strict Grounding (Anti-Alucinação Estrita)",
        criteria="The actual_output MUST NOT contain any facts, objects, or claims (such as photos, signatures, or seals) that are not explicitly stated in the retrieval_context. If the actual_output invents or assumes ANY physical evidence not present in the context, it must receive a score of 0.",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.RETRIEVAL_CONTEXT],
        model=GeminiJudge(),
        threshold=0.5
    )
    
    # 3. Executa a asserção com a nossa métrica rigorosa
    assert_test(test_case, [strict_grounding_metric])