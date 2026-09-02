import duckdb
import os
from pathlib import Path

# Define o caminho absoluto para salvar o arquivo na pasta 'data'
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "telemetry.duckdb"

def seed_database():
    print("🌱 Iniciando a semeadura (seed) do Data Lake DuckDB...")
    
    # Garante que o diretório data existe
    os.makedirs(DB_PATH.parent, exist_ok=True)
    
    # Conecta ao DuckDB (cria o arquivo se não existir)
    conn = duckdb.connect(str(DB_PATH))
    
    try:
        # ==========================================
        # 1. TABELA DE CLIENTES (Histórico e Risco)
        # ==========================================
        print("Criando tabela 'customers'...")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id VARCHAR PRIMARY KEY,
                account_age_days INTEGER,
                previous_disputes INTEGER,
                risk_score VARCHAR
            )
        """)
        # Limpa para evitar duplicações se rodar o script 2x
        conn.execute("DELETE FROM customers") 
        conn.execute("""
            INSERT INTO customers VALUES 
            ('CUST-ABC', 450, 0, 'LOW'),     -- Cliente antigo, bom histórico (Teste 1)
            ('CUST-XYZ', 15, 3, 'HIGH'),     -- Conta nova, histórico de fraudes (Teste 2)
            ('CUST-HBR', 120, 1, 'MEDIUM')   -- Cliente comum (Teste 3)
        """)

        # ==========================================
        # 2. TABELA DE PEDIDOS
        # ==========================================
        print("Criando tabela 'orders'...")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                ticket_id VARCHAR PRIMARY KEY,
                customer_id VARCHAR,
                order_value DOUBLE,
                status VARCHAR
            )
        """)
        conn.execute("DELETE FROM orders")
        conn.execute("""
            INSERT INTO orders VALUES 
            ('TKT-1001', 'CUST-ABC', 15.00, 'DELIVERED'),
            ('TKT-1002', 'CUST-XYZ', 500.00, 'DELIVERED'),
            ('TKT-1003', 'CUST-HBR', 80.00, 'DELIVERED')
        """)

        # ==========================================
        # 3. TABELA DE TELEMETRIA (GPS e Provas)
        # ==========================================
        print("Criando tabela 'delivery_telemetry'...")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_telemetry (
                ticket_id VARCHAR PRIMARY KEY,
                delivery_distance_meters INTEGER,
                photo_proof_uploaded BOOLEAN,
                otp_code_used BOOLEAN
            )
        """)
        conn.execute("DELETE FROM delivery_telemetry")
        # Aqui está o "Ouro" para a IA investigar:
        conn.execute("""
            INSERT INTO delivery_telemetry VALUES 
            ('TKT-1001', 12, TRUE, TRUE),    -- Entregue a 12m da casa (Perfeito)
            ('TKT-1002', 4500, FALSE, FALSE),-- Entregue a 4.5km do cliente (Fraude do entregador!)
            ('TKT-1003', 5, TRUE, FALSE)     -- Entregue na porta, mas cliente alega item faltante
        """)

        print(f"✅ Data Lake populado com sucesso em: {DB_PATH}")
        
    except Exception as e:
        print(f"❌ Erro ao popular banco: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_database()