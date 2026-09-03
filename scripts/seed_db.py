import duckdb
import os

def seed_database():
    print("🌱 Iniciando o Povoamento do Banco de Dados (DuckDB)...")
    
    # Garante que a pasta data/ existe
    os.makedirs("data", exist_ok=True)
    db_path = "data/sentinel.duckdb"
    
    # Conecta e cria o banco (se já existir tabela, ele limpa e recria)
    conn = duckdb.connect(db_path)
    
    print("  ⚙️ Criando tabela de Telemetria (Logística)...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delivery_telemetry (
            ticket_id VARCHAR PRIMARY KEY,
            driver_distance_meters DOUBLE,
            otp_validated BOOLEAN,
            has_photo_proof BOOLEAN,
            delivery_timestamp TIMESTAMP
        );
        DELETE FROM delivery_telemetry;
    """)
    
    print("  ⚙️ Criando tabela de Clientes (Risco)...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_profiles (
            customer_id VARCHAR PRIMARY KEY,
            account_age_days INTEGER,
            previous_disputes INTEGER,
            risk_score VARCHAR
        );
        DELETE FROM customer_profiles;
    """)
    
    print("  📦 Inserindo Massa de Dados Realista...")
    
    # --- DADOS DE TELEMETRIA ---
    # TKT-UI-001: Cliente Honesto (Atraso simples, sem OTP, sem foto)
    # TKT-UI-002: Fraude Clássica (Entregador a 5km de distância fingindo que entregou)
    # TKT-UI-003: Item Faltante (Entregue na porta, com foto da sacola)
    conn.execute("""
        INSERT INTO delivery_telemetry VALUES 
        ('TKT-UI-001', 12.5, FALSE, FALSE, '2026-09-03 10:00:00'),
        ('TKT-UI-002', 5400.0, FALSE, FALSE, '2026-09-03 11:30:00'),
        ('TKT-UI-003', 2.1, TRUE, TRUE, '2026-09-03 12:45:00');
    """)
    
    # --- DADOS DE CLIENTES ---
    # CUST-HBR: Usuário normal
    # CUST-FRAUD: Conta criada ontem, já pedindo estorno
    # CUST-VIP: Cliente de 5 anos, zero problemas
    conn.execute("""
        INSERT INTO customer_profiles VALUES 
        ('CUST-HBR', 120, 1, 'MEDIUM'),
        ('CUST-FRAUD', 1, 0, 'HIGH'),
        ('CUST-VIP', 1800, 0, 'LOW');
    """)

    conn.commit()
    conn.close()
    print("✅ Banco de Dados populado com sucesso! Massa de dados pronta para testes de stress.")

if __name__ == "__main__":
    seed_database()