from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine

print("  🔒 [Privacy] Inicializando Microsoft Presidio (NLP Local)...")

# 1. Configura o analisador para usar o modelo em português do spaCy
analyzer = AnalyzerEngine(supported_languages=["pt"])
anonymizer = AnonymizerEngine()

# 2. Ensina o Presidio a identificar o CPF brasileiro via Regex
cpf_pattern = Pattern(
    name="cpf_pattern", 
    regex=r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b", 
    score=0.9
)
cpf_recognizer = PatternRecognizer(
    supported_entity="BR_CPF", 
    patterns=[cpf_pattern], 
    supported_language="pt"
)
analyzer.registry.add_recognizer(cpf_recognizer)

# 3. Função de Mascaramento Central
def mask_pii(text: str) -> str:
    """
    Escaneia o texto localmente buscando dados sensíveis e os substitui por tags.
    Execução: Latência quase zero, 100% off-grid.
    """
    if not text:
        return text
        
    # Analisa o texto em português
    results = analyzer.analyze(
        text=text,
        entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "BR_CPF"],
        language="pt"
    )
    
    # Executa a substituição (Anonimização)
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    
    return anonymized_result.text

# Teste rápido de sanidade se o arquivo for rodado diretamente
if __name__ == "__main__":
    texto_teste = "Meu nome é Carlos Silva, meu CPF é 123.456.789-00 e meu telefone é 11999998888."
    print("Original:", texto_teste)
    print("Mascarado:", mask_pii(texto_teste))