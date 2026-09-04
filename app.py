import os
import duckdb
import json
import uuid
import streamlit as st
from langchain_core.messages import HumanMessage

# Importa o nosso orquestrador compilado
from sentinel.graph import sentinel_app

def get_ticket_receipt_for_ui(ticket_id: str):
    """Busca o JSON do pedido diretamente no DuckDB para exibir na tela de testes."""
    db_path = os.path.join(os.getcwd(), "data", "sentinel.duckdb")
    try:
        with duckdb.connect(db_path, read_only=True) as conn:
            res = conn.execute("SELECT order_items_json FROM delivery_telemetry WHERE ticket_id = ?", [ticket_id]).fetchone()
            if res and res[0]:
                return json.loads(res[0])
    except Exception as e:
        st.sidebar.error(f"Erro ao ler recibo: {e}")
    return []

# --- FUNÇÃO HELPER PARA QA (Payload Injection) ---
def override_ticket_mock_value(ticket_id: str, raw_json_str: str):
    """Substitui o JSON do banco com a exata string fornecida pelo testador."""
    db_path = os.path.join(os.getcwd(), "data", "sentinel.duckdb")
    try:
        with duckdb.connect(db_path) as conn:
            conn.execute("UPDATE delivery_telemetry SET order_items_json = ? WHERE ticket_id = ?", [raw_json_str, ticket_id])
    except Exception as e:
        st.error(f"Erro ao mockar BD: {e}")

# ---------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA E ESTADO
# ---------------------------------------------------------
st.set_page_config(page_title="SentinelOps | AI Loss Prevention", page_icon="🛡️", layout="wide")
st.title("🛡️ SentinelOps: Resolução Autônoma")

# Inicializa o estado da sessão (Memória do Frontend)
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4()) # ID único para a sessão do LangGraph
    st.session_state.chat_history = []             # Histórico visual da tela

# Barra lateral para simular os metadados do Ticket (Injetados pelo sistema na vida real)
with st.sidebar:
    st.header("Metadados do Ticket")
    
    # 1. Menu de Ajuda em Markdown para os Tickets
    help_ticket = """
    **Guia de Cenários de Telemetria:**
    - **TKT-UI-001:** Atraso simples (Honesto)
    - **TKT-UI-002:** Fraude de GPS (5km de distância)
    - **TKT-UI-003:** Item faltante (Com foto e OTP)
    - **TKT-UI-004:** Alergênico / Risco à saúde
    - **TKT-UI-005:** Assédio (Print no chat)
    - **TKT-UI-006:** Golpe da foto preta (Falso entregue)
    - **TKT-UI-007:** Produto danificado (Vazou tudo)
    - **TKT-UI-008:** Cliente Ausente (No-Show de 12min)
    - **TKT-UI-009:** Endereço Incorreto (Longe)
    - **TKT-UI-010:** Hostilidade na porta
    - **TKT-UI-011:** Restrição de Idade (Álcool sem OTP)
    """
    
    ticket_id = st.selectbox(
        "ID do Ticket (Telemetria)", 
        options=[
            "TKT-UI-001", "TKT-UI-002", "TKT-UI-003", "TKT-UI-004",
            "TKT-UI-005", "TKT-UI-006", "TKT-UI-007", "TKT-UI-008",
            "TKT-UI-009", "TKT-UI-010", "TKT-UI-011"
        ],
        help=help_ticket
    )
    
    # 2. Menu de Ajuda em Markdown para os Clientes
    help_customer = """
    **Perfis de Comportamento:**
    - **CUST-VIP:** 5 anos, LTV gigante, Risco Baixo
    - **CUST-HBR:** Cliente Normal, Risco Médio
    - **CUST-FRAUD:** Conta nova, Risco Alto
    - **CUST-NEW:** Conta nova promissora (Gasta bem)
    - **CUST-CHURN:** Reincidente insatisfeito (Risco de saída)
    - **CUST-ABUSER:** Caçador de reembolso (Alto No-Show)
    - **CUST-B2B:** Conta Corporativa (Alto volume)
    """
    
    customer_id = st.selectbox(
        "ID do Cliente (Risco)", 
        options=[
            "CUST-VIP", "CUST-HBR", "CUST-FRAUD", 
            "CUST-NEW", "CUST-CHURN", "CUST-ABUSER", "CUST-B2B"
        ],
        help=help_customer
    )
    
    # --- RENDERIZAÇÃO DINÂMICA DO CUPOM FISCAL ---
    receipt_items = get_ticket_receipt_for_ui(ticket_id)
    total_order_value = sum(item['price'] for item in receipt_items) if receipt_items else 0.0
    
    with st.expander("🧾 Cupom Fiscal (BD Atual)", expanded=True):
        if receipt_items:
            for item in receipt_items:
                st.write(f"- {item['item']}: **R$ {item['price']:.2f}**")
            st.markdown("---")
            st.write(f"**TOTAL DO PEDIDO:** R$ {total_order_value:.2f}")
        else:
            st.info("Nenhum item registrado neste ticket.")
    
    sandbox_mode = st.toggle("🧪 Modo Sandbox (Testes Livres)", value=False, help="Destrava a edição do Recibo JSON para testar cenários extremos de estorno parcial.")
    
    if sandbox_mode:
        st.warning("🔧 **Edite o Recibo (JSON)** para simular o pedido:")
        default_sandbox_json = """[
                {"item": "Combo Família Mega", "price": 390.00},
                {"item": "Refrigerante 2L", "price": 10.00}
            ]"""
        sandbox_json_str = st.text_area("Payload do Pedido", value=default_sandbox_json, height=150)
        
        try:
            # Tenta validar o JSON e somar os preços em tempo real
            receipt_items = json.loads(sandbox_json_str)
            total_order_value = sum(item.get('price', 0) for item in receipt_items)
            st.success(f"JSON Válido. Total Lido: **R$ {total_order_value:.2f}**")
        except json.JSONDecodeError:
            st.error("❌ Erro de sintaxe no JSON. Verifique as aspas e vírgulas.")
            total_order_value = 0.0
            receipt_items = []
            
    else:
        # Modo Normal (Golden Dataset - Leitura Direta do DuckDB)
        receipt_items = get_ticket_receipt_for_ui(ticket_id)
        total_order_value = sum(item['price'] for item in receipt_items) if receipt_items else 0.0
        
        with st.expander("🧾 Cupom Fiscal (BD Atual)", expanded=True):
            if receipt_items:
                for item in receipt_items:
                    st.write(f"- {item['item']}: **R$ {item['price']:.2f}**")
                st.markdown("---")
                st.write(f"**TOTAL DO PEDIDO:** R$ {total_order_value:.2f}")
            else:
                st.info("Nenhum item registrado neste ticket.")

    # O campo de Disputa agora é apenas visual (reflete a soma do JSON)
    dispute_amount = st.number_input(
        "Valor Total do Pedido (R$)", 
        value=float(total_order_value) if total_order_value > 0 else 80.00, 
        step=10.0,
        disabled=True
    )
    
    if st.button("🔄 Resetar Sessão", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.chat_history = []
        st.rerun()
# ---------------------------------------------------------
# 2. RENDERIZAÇÃO DO HISTÓRICO
# ---------------------------------------------------------
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------
# 3. INTERAÇÃO E INVOCAÇÃO DO LANGGRAPH
# ---------------------------------------------------------
config = {"configurable": {"thread_id": st.session_state.thread_id}}

if prompt := st.chat_input("Descreva o seu problema com o pedido..."):
    
    # SE o modo Sandbox estiver ligado e o JSON for válido, sobrescrevemos o banco AGORA
    if sandbox_mode and receipt_items:
        override_ticket_mock_value(ticket_id, sandbox_json_str)
    
    # Renderiza a queixa do cliente na tela
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    input_data = {
        "messages": [HumanMessage(content=prompt)],
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "dispute_amount": dispute_amount
    }

    # Aciona o Orquestrador
    with st.chat_message("assistant"):
        with st.status("Iniciando investigação autônoma...", expanded=True) as status:
            for event in sentinel_app.stream(input_data, config=config):
                for node_name, node_state in event.items():
                    st.write(f"⚙️ Passo concluído: **{node_name.upper()}**")
            status.update(label="Processamento pausado ou concluído.", state="complete", expanded=False)
        st.rerun() # Força a tela a recarregar para desenhar os botões de HITL se necessário

# ---------------------------------------------------------
# 4. GESTÃO DE ESTADO E HITL INTERATIVO (NOVO)
# ---------------------------------------------------------
# Lemos a "fotografia" atual da memória do LangGraph
snapshot = sentinel_app.get_state(config)

# Se a tupla 'next' tiver algo, o grafo está pausado aguardando o Humano
if snapshot.next:
    st.warning("⚠️ **INTERVENÇÃO HUMANA REQUERIDA**")
    st.info("O agente de IA escalou este ticket devido à complexidade, risco ou suspeita de fraude. Por favor, decida a ação final.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Aprovar Estorno Manualmente", use_container_width=True):
            # 1. Injeta a decisão na memória do grafo
            sentinel_app.update_state(config, {"recommended_action": "Aprovado por Operador Humano"})
            # 2. Manda o grafo continuar do ponto que parou (passando None)
            for event in sentinel_app.stream(None, config=config):
                pass
            st.rerun()
            
    with col2:
        if st.button("❌ Negar Estorno Manualmente", use_container_width=True):
            sentinel_app.update_state(config, {"recommended_action": "Negado por Operador Humano"})
            for event in sentinel_app.stream(None, config=config):
                pass
            st.rerun()

# Se não há mais nós na fila (snapshot.next está vazio) E temos mensagens no estado, o processo acabou.
elif snapshot.values.get("recommended_action"):
    action = snapshot.values.get("recommended_action", "")
    
    # Renderização visual rica baseada na ação final (Autônoma ou Humana)
    st.markdown("---")
    if action == "bloqueio_seguranca":
        st.error("🚨 **ALERTA DE SEGURANÇA (AI WAF)**\n\nTentativa de manipulação detectada. Tráfego bloqueado.")
    elif action == "auto_refund":
        st.success("✅ **REEMBOLSO APROVADO IMEDIATAMENTE (Autônomo)**\n\nCaso de baixo risco. Estorno processado sem intervenção humana.")
    elif "Operador Humano" in action:
        st.info(f"👤 **DECISÃO HUMANA EXECUTADA**\n\nResultado final: {action}")
    else:
        st.info(f"🔍 **PARECER DA INVESTIGAÇÃO AUTÔNOMA**\n\nAção recomendada: **{action}**")
        if snapshot.values.get("messages"):
            st.markdown(snapshot.values["messages"][-1].content)