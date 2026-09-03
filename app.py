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
        
        # 1. STREAMING DO RACIOCÍNIO (Fim da tela congelada)
        with st.status("Iniciando investigação autônoma...", expanded=True) as status:
            for event in sentinel_app.stream(input_data, config=config):
                # O LangGraph retorna um dicionário com o nome do nó que acabou de rodar
                for node_name, node_state in event.items():
                    st.write(f"⚙️ Passo concluído: **{node_name.upper()}**")
            
            # Atualiza o status quando o grafo terminar
            status.update(label="Investigação concluída!", state="complete", expanded=False)

        # 2. EXTRAÇÃO DO ESTADO FINAL
        final_state = sentinel_app.get_state(config).values
        action = final_state.get("recommended_action", "")
        
        final_response_text = ""
        
        # 3. RENDERIZAÇÃO VISUAL RICA (A2UI)
        if action == "bloqueio_seguranca":
            st.error("🚨 **ALERTA DE SEGURANÇA (AI WAF)**\n\nTentativa de manipulação semântica ou ataque cibernético detectado. O tráfego foi bloqueado e o incidente foi reportado à equipe de Fraudes.")
            final_response_text = "[Sistema]: Bloqueio de Segurança."
            
        elif action == "auto_refund":
            st.success("✅ **REEMBOLSO APROVADO IMEDIATAMENTE**\n\nA triagem classificou o caso como de baixo risco. O estorno foi processado sem necessidade de intervenção humana.")
            final_response_text = "[Sistema]: Reembolso automático aprovado."
            
        else:
            # Caso caia no Investigador (Gemini) ou Revisão Humana
            st.info(f"🔍 **PARECER DA INVESTIGAÇÃO (Ação recomendada: {action})**")
            if final_state.get("messages"):
                final_response_text = final_state["messages"][-1].content
                st.markdown(final_response_text)
            else:
                final_response_text = "Nenhuma justificativa textual gerada."
                st.markdown(final_response_text)

        # Salva o resumo no histórico visual para a tela não bugar ao dar refresh
        st.session_state.chat_history.append({"role": "assistant", "content": final_response_text})