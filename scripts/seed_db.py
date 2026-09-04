import duckdb
import os

def seed_database():
    print("🌱 Iniciando o Povoamento do Banco de Dados (DuckDB V3 - No-Show Metrics)...")
    
    os.makedirs("data", exist_ok=True)
    db_path = "data/sentinel.duckdb"
    
    conn = duckdb.connect(db_path)
    
    # ---------------------------------------------------------
    # 1. TELEMETRIA LOGÍSTICA (Mantida igual, já possuía wait_time)
    # ---------------------------------------------------------
    print("  ⚙️ Recriando tabela de Telemetria...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delivery_telemetry (
            ticket_id VARCHAR PRIMARY KEY,
            driver_distance_meters DOUBLE,
            otp_validated BOOLEAN,
            has_photo_proof BOOLEAN,
            is_age_restricted BOOLEAN,
            driver_waiting_time_minutes INTEGER, 
            delivery_timestamp TIMESTAMP
        );
        DELETE FROM delivery_telemetry;
    """)
    
    # ---------------------------------------------------------
    # 2. PERFIS DE CLIENTES (Evolução de Schema)
    # ---------------------------------------------------------
    print("  ⚙️ Adicionando métrica 'no_show_count' na tabela de Clientes...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_profiles (
            customer_id VARCHAR PRIMARY KEY,
            account_age_days INTEGER,
            total_orders INTEGER,
            lifetime_value_brl DOUBLE,
            account_type VARCHAR,
            previous_disputes INTEGER,
            no_show_count INTEGER,               -- NOVO: Quantas vezes o cliente não foi buscar o pedido
            risk_score VARCHAR
        );
        DELETE FROM customer_profiles;
    """)
    
    print("  📦 Inserindo Massa de Dados de Alta Complexidade...")
    
    # --- DADOS DE TELEMETRIA ---
    # Ticket 008 e 010 são os que envolvem espera ou hostilidade na porta
    conn.execute("""
        INSERT INTO delivery_telemetry VALUES 
        ('TKT-UI-001', 12.5, FALSE, FALSE, FALSE, 0, '2026-09-03 10:00:00'),
        ('TKT-UI-002', 5400.0, FALSE, FALSE, FALSE, 0, '2026-09-03 11:30:00'),
        ('TKT-UI-003', 2.1, TRUE, TRUE, FALSE, 0, '2026-09-03 12:45:00'),
        ('TKT-UI-004', 0.0, TRUE, TRUE, FALSE, 0, '2026-09-03 13:00:00'),
        ('TKT-UI-005', 0.0, TRUE, FALSE, FALSE, 0, '2026-09-03 13:30:00'),
        ('TKT-UI-006', 50.0, FALSE, TRUE, FALSE, 0, '2026-09-03 14:00:00'),
        ('TKT-UI-007', 0.0, FALSE, TRUE, FALSE, 0, '2026-09-03 14:30:00'),
        ('TKT-UI-008', 5.0, FALSE, FALSE, FALSE, 12, '2026-09-03 15:00:00'),   -- 12 min de espera (Ausência real)
        ('TKT-UI-009', 2500.0, FALSE, FALSE, FALSE, 0, '2026-09-03 15:30:00'),
        ('TKT-UI-010', 10.0, FALSE, FALSE, FALSE, 2, '2026-09-03 16:00:00'),
        ('TKT-UI-011', 2.0, FALSE, FALSE, TRUE, 5, '2026-09-03 16:30:00');
    """)
    
    # --- DADOS DE CLIENTES ---
    # Colunas: id, age, orders, ltv, type, disputes, no_shows, risk
    conn.execute("""
        INSERT INTO customer_profiles VALUES 
        ('CUST-HBR', 120, 15, 600.00, 'B2C', 1, 0, 'MEDIUM'),
        ('CUST-FRAUD', 1, 0, 0.00, 'B2C', 0, 0, 'HIGH'),
        ('CUST-VIP', 1800, 450, 18500.00, 'B2C', 2, 0, 'LOW'),
        ('CUST-NEW', 15, 10, 850.00, 'B2C', 0, 0, 'LOW'),
        ('CUST-CHURN', 730, 180, 7200.00, 'B2C', 4, 1, 'MEDIUM'),
        ('CUST-ABUSER', 240, 80, 2400.00, 'B2C', 32, 6, 'HIGH'),          -- 6 No-shows (Reincidente Crônico)
        ('CUST-B2B', 400, 300, 35000.00, 'B2B', 3, 0, 'LOW');
    """)

    conn.commit()
    conn.close()
    print("✅ Banco de Dados populado! Métrica de No-Show adicionada com sucesso.")

if __name__ == "__main__":
    seed_database()