import pytest
from deepeval import assert_test
from deepeval.metrics import HallucinationMetric
from deepeval.test_case import LLMTestCase

def test_investigator_grounding():
    """
    Simula o cenário do Ticket de R$ 80,00 onde o LLM inventou a foto.
    O objetivo é garantir que, dado um contexto sem menção a fotos, 
    qualquer resposta que mencione lacre ou foto seja REPROVADA.
    """
    
    # 1. O que o banco de dados (DuckDB) realmente devolveu
    contexto_do_banco = [
        "Distância do entregador ao dar baixa: 5 metros.",
        "Código de segurança (OTP) validado: Não"
    ]
    
    # 2. A resposta que o nosso agente gerou (Aqui injetamos a alucinação antiga para testar o juiz)
    resposta_do_agente = "Parecer Baseado em Dados: A entrega foi no local correto. A foto anexada mostra a sacola fechada com lacre. Reembolso negado."
    
    # 3. Montamos o caso de teste
    test_case = LLMTestCase(
        input="Meu pedido veio sem a batata.",
        actual_output=resposta_do_agente,
        context=contexto_do_banco
    )
    
    # 4. Configuramos a métrica de Alucinação
    # O threshold de 0.5 significa que somos rigorosos com invenções.
    metric = HallucinationMetric(threshold=0.5)
    
    # 5. Executamos a asserção. O DeepEval usará a API padrão configurada para julgar.
    assert_test(test_case, [metric])