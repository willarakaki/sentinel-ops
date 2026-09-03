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
if prompt := st.chat_input("Descreva o seu problema com o pedido..."):
    # Renderiza a queixa do cliente na tela imediatamente
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepara o payload para o SentinelOps (Backend)
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    input_data = {
        "messages": [HumanMessage(content=prompt)],
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "dispute_amount": dispute_amount
    }

    # Aciona o Orquestrador e captura a resposta final
    with st.chat_message("assistant"):
        with st.spinner("Processando através da arquitetura SentinelOps..."):
            final_response = ""
            
            # Itera pelo stream do LangGraph para pegar o último delta de estado
            for event in sentinel_app.stream(input_data, config=config):
                # Podemos ler os nós passando por aqui futuramente para a UI
                pass
            
            # Quando o fluxo termina, extraímos o estado final do LangGraph
            final_state = sentinel_app.get_state(config).values
            
            # Pega a última mensagem gerada pelo sistema
            if final_state.get("messages"):
                final_response = final_state["messages"][-1].content
            else:
                final_response = "Fluxo interrompido ou sem resposta textual (ex: Bloqueio WAF)."

            st.markdown(final_response)
            st.session_state.chat_history.append({"role": "assistant", "content": final_response})