import json
import os

import duckdb


def seed_database():
    print("🌱 Iniciando o Povoamento do Banco de Dados (DuckDB V4 - Itemized JSON)...")
    
    os.makedirs("data", exist_ok=True)
    db_path = "data/sentinel.duckdb"
    
    conn = duckdb.connect(db_path)
    
    # ---------------------------------------------------------
    # 1. TELEMETRIA LOGÍSTICA (Evolução Híbrida Relacional/JSON)
    # ---------------------------------------------------------
    print("  ⚙️ Recriando tabela de Telemetria com suporte a Recibos JSON...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delivery_telemetry (
            ticket_id VARCHAR PRIMARY KEY,
            driver_distance_meters DOUBLE,
            otp_validated BOOLEAN,
            has_photo_proof BOOLEAN,
            is_age_restricted BOOLEAN,
            driver_waiting_time_minutes INTEGER,
            order_items_json VARCHAR,            -- NOVO: Recibo detalhado em JSON
            delivery_timestamp TIMESTAMP
        );
        DELETE FROM delivery_telemetry;
    """)
    
    # ---------------------------------------------------------
    # 2. PERFIS DE CLIENTES (Mantido)
    # ---------------------------------------------------------
    print("  ⚙️ Criando tabela de Clientes...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_profiles (
            customer_id VARCHAR PRIMARY KEY,
            account_age_days INTEGER,
            total_orders INTEGER,
            lifetime_value_brl DOUBLE,
            account_type VARCHAR,
            previous_disputes INTEGER,
            no_show_count INTEGER,
            risk_score VARCHAR
        );
        DELETE FROM customer_profiles;
    """)
    
    print("  📦 Inserindo Massa de Dados com payloads JSON...")
    
    # --- DADOS DE TELEMETRIA ---
    # Payloads JSON convertidos em strings de forma segura
    json_tkt_001 = json.dumps([{"item": "Pizza Margherita", "price": 70.00}])
    json_tkt_002 = json.dumps([{"item": "Combo Sushi Premium", "price": 500.00}])
    json_tkt_003 = json.dumps([{"item": "Hambúrguer Artesanal Duplo", "price": 65.00}, {"item": "Batata Frita Grande", "price": 15.00}]) # Total 80
    json_tkt_004 = json.dumps([{"item": "Prato Vegano", "price": 50.00}])
    json_tkt_005 = json.dumps([{"item": "Marmita Executiva", "price": 60.00}])
    json_tkt_006 = json.dumps([{"item": "Frango Assado Completo", "price": 50.00}])
    json_tkt_007 = json.dumps([{"item": "Sopa de Capeletti (Contém Leite)", "price": 45.00}])
    json_tkt_008 = json.dumps([{"item": "Açaí 500ml", "price": 25.00}])
    json_tkt_009 = json.dumps([{"item": "Kit Churrasco", "price": 150.00}])
    json_tkt_010 = json.dumps([{"item": "Porção de Coxinhas", "price": 30.00}])
    json_tkt_011 = json.dumps([{"item": "Pack Cerveja Artesanal 6x", "price": 80.00}]) # Restrito

    conn.execute(f"""
        INSERT INTO delivery_telemetry VALUES 
        ('TKT-UI-001', 12.5, FALSE, FALSE, FALSE, 0, '{json_tkt_001}', '2026-09-03 10:00:00'),
        ('TKT-UI-002', 5400.0, FALSE, FALSE, FALSE, 0, '{json_tkt_002}', '2026-09-03 11:30:00'),
        ('TKT-UI-003', 2.1, TRUE, TRUE, FALSE, 0, '{json_tkt_003}', '2026-09-03 12:45:00'),
        ('TKT-UI-004', 0.0, TRUE, TRUE, FALSE, 0, '{json_tkt_004}', '2026-09-03 13:00:00'),
        ('TKT-UI-005', 0.0, TRUE, FALSE, FALSE, 0, '{json_tkt_005}', '2026-09-03 13:30:00'),
        ('TKT-UI-006', 50.0, FALSE, TRUE, FALSE, 0, '{json_tkt_006}', '2026-09-03 14:00:00'),
        ('TKT-UI-007', 0.0, FALSE, TRUE, FALSE, 0, '{json_tkt_007}', '2026-09-03 14:30:00'),
        ('TKT-UI-008', 5.0, FALSE, FALSE, FALSE, 12, '{json_tkt_008}', '2026-09-03 15:00:00'),
        ('TKT-UI-009', 2500.0, FALSE, FALSE, FALSE, 0, '{json_tkt_009}', '2026-09-03 15:30:00'),
        ('TKT-UI-010', 10.0, FALSE, FALSE, FALSE, 2, '{json_tkt_010}', '2026-09-03 16:00:00'),
        ('TKT-UI-011', 2.0, FALSE, FALSE, TRUE, 5, '{json_tkt_011}', '2026-09-03 16:30:00');
    """)
    
    # --- DADOS DE CLIENTES (Mantidos Intactos) ---
    conn.execute("""
        INSERT INTO customer_profiles VALUES 
        ('CUST-HBR', 120, 15, 600.00, 'B2C', 1, 0, 'MEDIUM'),
        ('CUST-FRAUD', 1, 0, 0.00, 'B2C', 0, 0, 'HIGH'),
        ('CUST-VIP', 1800, 450, 18500.00, 'B2C', 2, 0, 'LOW'),
        ('CUST-VIP-TEST', 1500, 300, 12000.00, 'B2C', 1, 0, 'LOW'),
        ('CUST-NEW', 15, 10, 850.00, 'B2C', 0, 0, 'LOW'),
        ('CUST-CHURN', 730, 180, 7200.00, 'B2C', 4, 1, 'MEDIUM'),
        ('CUST-ABUSER', 240, 80, 2400.00, 'B2C', 32, 6, 'HIGH'),
        ('CUST-B2B', 400, 300, 35000.00, 'B2B', 3, 0, 'LOW');
    """)

    conn.commit()
    conn.close()
    print("✅ Banco de Dados populado! Recibos JSON (Itemized Refund) adicionados com sucesso.")

if __name__ == "__main__":
    seed_database()