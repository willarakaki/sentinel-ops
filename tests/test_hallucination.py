import pytest
from deepeval import assert_test
from deepeval.metrics import HallucinationMetric
from deepeval.test_case import LLMTestCase
from deepeval.models.base_model import DeepEvalBaseLLM
from dotenv import load_dotenv

# Importando nossa Fábrica Central
from sentinel.core.llm_factory import LLMFactory

load_dotenv()

# ---------------------------------------------------------
# 1. CONFIGURAÇÃO DO JUIZ (Injeção via Factory)
# ---------------------------------------------------------
# ---------------------------------------------------------
# 1. CONFIGURAÇÃO DO JUIZ (Injeção via Factory)
# ---------------------------------------------------------
class GeminiJudge(DeepEvalBaseLLM):
    """Wrapper corporativo integrando o DeepEval à nossa LLMFactory e blindando contra respostas multimodais."""
    def __init__(self):
        self.model = LLMFactory.get_evaluator_model()

    def load_model(self):
        return self.model

    def _extract_text(self, content) -> str:
        """Garante que a saída seja sempre uma string plana, lidando com listas de blocos multimodais do Gemini."""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Extrai o texto dos dicionários de conteúdo do LangChain
            return " ".join([block.get("text", "") for block in content if isinstance(block, dict)])
        return str(content)

    def generate(self, prompt: str) -> str:
        res = self.model.invoke(prompt)
        return self._extract_text(res.content)

    async def a_generate(self, prompt: str) -> str:
        res = await self.model.ainvoke(prompt)
        return self._extract_text(res.content)
    
    def get_model_name(self):
        return "SentinelOps-Central-Evaluator"

# ---------------------------------------------------------
# 2. SUÍTE DE TESTES SEMÂNTICOS
# ---------------------------------------------------------
def test_investigator_grounding():
    contexto_do_banco = [
        "Distância do entregador ao dar baixa: 5 metros.",
        "Código de segurança (OTP) validado: Não"
    ]
    
    resposta_do_agente = "Parecer Baseado em Dados: A entrega foi no local correto. A foto anexada mostra a sacola fechada com lacre. Reembolso negado."
    
    test_case = LLMTestCase(
        input="Meu pedido veio sem a batata.",
        actual_output=resposta_do_agente,
        context=contexto_do_banco
    )
    
    metric = HallucinationMetric(threshold=0.5, model=GeminiJudge())
    assert_test(test_case, [metric])