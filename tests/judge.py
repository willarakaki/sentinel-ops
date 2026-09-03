import re
from deepeval.models.base_model import DeepEvalBaseLLM
from sentinel.core.llm_factory import LLMFactory

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