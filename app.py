import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd

# 1. Conexão com o Supabase
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

st.title("Controle de Faxinas e Serviços")

# 2. Divisão em Abas
aba_equipe, aba_gestao = st.tabs(["Área da Equipe", "Gestão (Análise)"])

# --- ABA DA EQUIPE ---
with aba_equipe:
    st.header("Qual é o seu nome?")
    resposta = supabase.table("tarefas").select("funcionario").execute()
    nomes = sorted(list(set([linha["funcionario"] for linha in resposta.data])))
    
    nome_escolhido = st.selectbox("Selecione seu nome:", [""] + nomes)

    if nome_escolhido:
        # Data formatada para a tela (BR) e para buscar no banco (ISO)
        hoje_obj = datetime.date.today()
        hoje_br = hoje_obj.strftime("%d/%m/%Y")
        hoje_iso = hoje_obj.isoformat()
        
        st.subheader(f"Suas tarefas para hoje ({hoje_br})")

        tarefas_hoje = supabase.table("tarefas").select("*").eq("funcionario", nome_escolhido).eq("data", hoje_iso).eq("status", "Pendente").execute()

        if not tarefas_hoje.data:
            st.success("Você não tem tarefas pendentes para hoje! 🎉")
        else:
            for tarefa in tarefas_hoje.data:
                col_texto, col_botao = st.columns([3, 1])
                col_texto.write(f"**{tarefa['descricao']}**")
                
                if col_botao.button("✅ Feito", key=f"btn_{tarefa['id']}"):
                    supabase.table("tarefas").update({"status": "Concluído"}).eq("id", tarefa['id']).execute()
                    st.rerun()

# --- ABA DE GESTÃO ---
with aba_gestao:
    st.header("Análise de Desempenho e Pendências")
    
    col_filtro1, col_filtro2 = st.columns(2)
    
    hoje = datetime.date.today()
    inicio_mes = hoje.replace(day=1)
    
    # Calendário forçado para o padrão brasileiro
    datas = col_filtro1.date_input("Período analisado:", [inicio_mes, hoje], format="DD/MM/YYYY")
    
    if len(datas) == 2:
        data_inicio, data_fim = datas
    else:
        data_inicio = datas[0]
        data_fim = datas[0]

    resposta_nomes = supabase.table("tarefas").select("funcionario").execute()
    todos_nomes = sorted(list(set([linha["funcionario"] for linha in resposta_nomes.data])))
    filtro_nome = col_filtro2.selectbox("Filtrar por funcionário:", ["Todos"] + todos_nomes)

    query = supabase.table("tarefas").select("*").gte("data", data_inicio.isoformat()).lte("data", data_fim.isoformat())
    
    if filtro_nome != "Todos":
        query = query.eq("funcionario", filtro_nome)
        
    dados = query.execute()

    if not dados.data:
        st.info("Nenhum serviço registrado para estes filtros.")
    else:
        df = pd.DataFrame(dados.data)
        
        st.divider()
        
        st.subheader("Concluídos vs Pendentes")
        contagem = df['status'].value_counts()
        st.bar_chart(contagem)
        
        st.divider()
        
        st.subheader("Lista de Serviços Pendentes")
        # Filtra só os pendentes
        df_pendentes = df[df['status'] == 'Pendente'].copy()
        
        if df_pendentes.empty:
            st.success("Tudo em dia para este período! Não há pendências.")
        else:
            # Converte a coluna 'data' para o padrão BR na hora de mostrar na tabela
            df_pendentes['data'] = pd.to_datetime(df_pendentes['data']).dt.strftime('%d/%m/%Y')
            
            st.dataframe(
                df_pendentes, 
                column_config={
                    "id": None,
                    "funcionario": "Responsável",
                    "descricao": "Serviço",
                    "data": "Data",
                    "status": "Status"
                },
                hide_index=True,
                use_container_width=True
            )