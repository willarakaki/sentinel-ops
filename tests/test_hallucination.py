import pytest
import re
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
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
        """Extrator Regex à prova de balas para JSON e blindagem contra Silent Retries."""
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join([block.get("text", "") for block in content if isinstance(block, dict)])
        else:
            text = str(content)
            
        text = text.strip()
        
        # 1. OBSERVABILIDADE: Printa no terminal o que o Gemini respondeu
        # Usamos limitador de 300 caracteres para não poluir demais a tela
        print(f"\n🕵️‍♂️ [DEBUG JUIZ] Saída Bruta do Gemini:\n{text[:300]}...\n")
        
        # 2. CAÇADOR DE MARKDOWN (Regex)
        # Captura qualquer coisa entre ```json (ou só ```) e o fechamento ```
        match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
            
        # 3. FALLBACK DE CHAVES (Caso ele responda texto misturado com JSON)
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return text[start:end+1]
            
        return text

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