import json
from pathlib import Path

import duckdb
from langchain_core.tools import tool

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "sentinel.duckdb"


def get_customer_profile(customer_id: str) -> dict | None:
    """Carrega atributos estruturados usados pelas políticas de risco."""
    try:
        with duckdb.connect(str(DB_PATH), read_only=True) as conn:
            result = conn.execute(
                """
                SELECT account_age_days, total_orders, lifetime_value_brl,
                    account_type, previous_disputes, no_show_count, risk_score
                FROM customer_profiles
                WHERE customer_id = ?
                """,
                [customer_id],
            ).fetchone()

        if not result:
            return None

        age, orders, ltv, account_type, disputes, no_shows, risk = result
        return {
            "account_age_days": age,
            "total_orders": orders,
            "lifetime_value_brl": float(ltv),
            "account_type": account_type,
            "previous_disputes": disputes,
            "no_show_count": no_shows,
            "risk_score": str(risk),
        }
    except (duckdb.Error, OSError, TypeError, ValueError):
        return None

# ==========================================
# 1. FERRAMENTA: TELEMETRIA LOGÍSTICA
# ==========================================
@tool
def get_delivery_telemetry(ticket_id: str) -> str:
    """Busca os dados logísticos de uma entrega."""
    try:
        with duckdb.connect(str(DB_PATH), read_only=True) as conn:
            query = """
                SELECT 
                    driver_distance_meters, 
                    has_photo_proof, 
                    otp_validated, 
                    is_age_restricted, 
                    driver_waiting_time_minutes,
                    order_items_json
                FROM delivery_telemetry
                WHERE ticket_id = ?
            """
            result = conn.execute(query, [ticket_id]).fetchone()
            
            if not result:
                return f"Nenhuma telemetria encontrada para o ticket {ticket_id}."
            
            dist, photo, otp, age_restr, wait_time, order_json_str = result
            
            receipt_formatted = "\n[RECIBO DOS ITENS DO PEDIDO]:\n"
            try:
                items = json.loads(order_json_str) if order_json_str else []
                for item in items:
                    receipt_formatted += f"  - {item['item']}: R$ {item['price']:.2f}\n"
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                receipt_formatted += "  - Erro ao ler recibo.\n"
            
            return (
                f"[EVIDÊNCIAS DE TELEMETRIA LOGÍSTICA] Ticket: {ticket_id}\n"
                f"- Distância do entregador: {dist} metros.\n"
                f"- Foto anexada: {'Sim' if photo else 'Não'}\n"
                f"- OTP validado: {'Sim' if otp else 'Não'}\n"
                f"- Restrição de idade: {'Sim' if age_restr else 'Não'}\n"
                f"- Tempo de espera: {wait_time} min.\n"
                f"{receipt_formatted}"
            )
    except (duckdb.Error, OSError, TypeError, ValueError) as e:
        return f"Erro ao acessar banco de telemetria: {e!s}"

# ==========================================
# 2. FERRAMENTA: HISTÓRICO E PERFIL DO CLIENTE
# ==========================================
@tool
def get_customer_history(customer_id: str) -> str:
    """
    Busca o histórico completo, comportamento e valor (LTV) do cliente.
    USE ESTA FERRAMENTA para analisar risco de fraude, churn e reincidência.
    """
    try:
        profile = get_customer_profile(customer_id)
        if not profile:
            return f"Nenhum cliente encontrado com o ID {customer_id}."

        return (
            f"[PERFIL E HISTÓRICO DO CLIENTE] ID: {customer_id}\n"
            f"- Tipo de Conta: {profile['account_type']}\n"
            f"- Idade da conta: {profile['account_age_days']} dias\n"
            f"- Total de pedidos realizados: {profile['total_orders']}\n"
            f"- Lifetime Value (Total Gasto): R$ {profile['lifetime_value_brl']:.2f}\n"
            f"- Disputas/estornos anteriores: {profile['previous_disputes']}\n"
            f"- Ausências na entrega (No-Show): {profile['no_show_count']} vezes\n"
            f"- Score de Risco Algorítmico: {profile['risk_score']}"
        )
    except (duckdb.Error, OSError, TypeError, ValueError) as e:
        return f"Erro ao acessar banco de clientes: {e!s}"