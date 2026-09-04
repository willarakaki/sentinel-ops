import uuid
import streamlit as st
from langchain_core.messages import HumanMessage

# Importa o nosso orquestrador compilado
from sentinel.graph import sentinel_app

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
    ticket_id = st.text_input("ID do Ticket", value="TKT-UI-001")
    customer_id = st.text_input("ID do Cliente", value="CUST-HBR")
    dispute_amount = st.number_input("Valor em Disputa (R$)", value=80.00, step=10.0)
    
    if st.button("🔄 Resetar Sessão"):
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