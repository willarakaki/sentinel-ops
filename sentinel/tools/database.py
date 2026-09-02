import duckdb
from pathlib import Path
from langchain_core.tools import tool

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "telemetry.duckdb"

# ==========================================
# 1. FERRAMENTA: TELEMETRIA LOGÍSTICA
# ==========================================
@tool
def get_delivery_telemetry(ticket_id: str) -> str:
    """
    Busca os dados de telemetria de uma entrega usando o ticket_id.
    Retorna a distância do entregador até o cliente, uso de senha (OTP) e fotos.
    USE ESTA FERRAMENTA SEMPRE que o cliente reclamar que não recebeu o pedido 
    ou que itens vieram faltando/frios.
    """
    try:
        # read_only=True é um mecanismo de segurança em produção
        with duckdb.connect(str(DB_PATH), read_only=True) as conn:
            query = """
                SELECT delivery_distance_meters, photo_proof_uploaded, otp_code_used
                FROM delivery_telemetry
                WHERE ticket_id = ?
            """
            # Passagem segura de parâmetros (PreparedStatement), previne SQL Injection
            result = conn.execute(query, [ticket_id]).fetchone()
            
            if not result:
                return f"Nenhuma telemetria encontrada para o ticket {ticket_id}."
            
            distance, photo, otp = result
            return (
                f"[TELEMETRIA LOGÍSTICA] Ticket: {ticket_id}\n"
                f"- Distância do entregador ao dar baixa: {distance} metros.\n"
                f"- Foto anexada como prova: {'Sim' if photo else 'Não'}\n"
                f"- Código de segurança (OTP) validado: {'Sim' if otp else 'Não'}"
            )
    except Exception as e:
        return f"Erro ao acessar banco de telemetria: {str(e)}"

# ==========================================
# 2. FERRAMENTA: HISTÓRICO E RISCO DO CLIENTE
# ==========================================
@tool
def get_customer_history(customer_id: str) -> str:
    """
    Busca o histórico e o score de risco do cliente.
    Retorna a idade da conta, quantidade de disputas prévias e a classificação de risco (LOW, MEDIUM, HIGH).
    USE ESTA FERRAMENTA para analisar se o cliente tem perfil fraudador.
    """
    try:
        with duckdb.connect(str(DB_PATH), read_only=True) as conn:
            query = """
                SELECT account_age_days, previous_disputes, risk_score
                FROM customers
                WHERE customer_id = ?
            """
            result = conn.execute(query, [customer_id]).fetchone()
            
            if not result:
                return f"Nenhum cliente encontrado com o ID {customer_id}."
            
            age, disputes, risk = result
            return (
                f"[PERFIL DO CLIENTE] ID: {customer_id}\n"
                f"- Idade da conta: {age} dias\n"
                f"- Disputas/estornos anteriores: {disputes}\n"
                f"- Score de risco na plataforma: {risk}"
            )
    except Exception as e:
        return f"Erro ao acessar banco de clientes: {str(e)}"