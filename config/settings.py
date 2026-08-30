import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Definimos o caminho absoluto do projeto para não haver erro de "arquivo não encontrado"
BASE_DIR = Path(__file__).resolve().parent.parent
YAML_PATH = BASE_DIR / "rules" / "dispute_matrix.yaml"

# ==========================================
# MODELOS DE VALIDAÇÃO DO YAML (REGRAS DE NEGÓCIO)
# ==========================================
class TierConfig(BaseModel):
    min_value: float
    max_value: float
    risk_level: str
    action: str
    human_in_the_loop_required: bool
    description: str
    
class DisputeMatrixConfig(BaseModel):
    version: str
    last_updated: str
    tiers: dict[str, TierConfig]
    
# ==========================================
# MODELO PRINCIPAL DE VARIÁVEIS DE AMBIENTE
# ==========================================
class Settings(BaseSettings):
    
    google_api_key: str = Field(..., alias="GOOGLE_APÌ_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    
    # LangSmith (Observabilidade)
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str | None = Field(default=None, alias="LANGCHAIN_API_KEY")
    langchain_project: str | None = Field(default=None, alias="LANGCHAIN_PROJECT")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    def load_dispute_matrix(self) -> DisputeMatrixConfig:
        """Lê o arquivo YAML e retorna validado pelo Pydantic."""
        if not YAML_PATH.exists():
            raise FileNotFoundError(f"Arquivo de regras não encontrado: {YAML_PATH}")
        
        with open(YAML_PATH, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
            
        return DisputeMatrixConfig(**yaml_data)
    
settings = Settings()
dispute_rules = settings.load_dispute_matrix()