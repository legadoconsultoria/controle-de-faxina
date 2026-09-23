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
                with st.container():
                    col_texto, col_botao_feito, col_botao_nao = st.columns([2, 1, 1])
                    col_texto.write(f"**{tarefa['descricao']}**")
                    
                    if col_botao_feito.button("✅ Feito", key=f"btn_{tarefa['id']}"):
                        supabase.table("tarefas").update({"status": "Concluído"}).eq("id", tarefa['id']).execute()
                        st.rerun()
                    
                    # Usa uma checkbox para mostrar o campo do motivo
                    marcar_nao_feita = col_botao_nao.checkbox("❌ Não Realizada", key=f"chk_{tarefa['id']}")
                    
                if marcar_nao_feita:
                    motivo = st.text_input("Motivo obrigatório para não realizar:", key=f"motivo_{tarefa['id']}")
                    if st.button("Confirmar Não Realizada", key=f"conf_{tarefa['id']}"):
                        if motivo.strip() == "":
                            st.error("É obrigatório digitar o motivo de não ter feito a faxina!")
                        else:
                            # Atualiza para Não Realizada e guarda o motivo na base de dados
                            supabase.table("tarefas").update({
                                "status": "Não Realizada", 
                                "motivo": motivo.strip()
                            }).eq("id", tarefa['id']).execute()
                            st.rerun()
                
                st.write("---")

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

    # Lógica para expandir a data escolhida para a semana completa (Domingo a Sábado)
    dias_do_domingo_inicio = (data_inicio.weekday() + 1) % 7
    data_inicio_semana = data_inicio - datetime.timedelta(days=dias_do_domingo_inicio)
    
    dias_do_domingo_fim = (data_fim.weekday() + 1) % 7
    data_fim_semana = data_fim + datetime.timedelta(days=6 - dias_do_domingo_fim)

    resposta_nomes = supabase.table("tarefas").select("funcionario").execute()
    todos_nomes = sorted(list(set([linha["funcionario"] for linha in resposta_nomes.data])))
    filtro_nome = col_filtro2.selectbox("Filtrar por funcionário:", ["Todos"] + todos_nomes)

    query = supabase.table("tarefas").select("*").gte("data", data_inicio_semana.isoformat()).lte("data", data_fim_semana.isoformat())
    
    if filtro_nome != "Todos":
        query = query.eq("funcionario", filtro_nome)
        
    dados = query.execute()

    # Informa o utilizador da semana exata que está a ser analisada
    st.write(f"**A exibir relatório da semana:** {data_inicio_semana.strftime('%d/%m/%Y')} a {data_fim_semana.strftime('%d/%m/%Y')}")

    if not dados.data:
        st.info("Nenhum serviço registado para estas semanas.")
    else:
        df = pd.DataFrame(dados.data)
        
        st.divider()
        
        st.subheader("Concluídos vs Pendentes vs Não Realizados")
        contagem = df['status'].value_counts()
        st.bar_chart(contagem)
        
        st.divider()
        
        st.subheader("Relatório Semanal de Serviços")
        
        # Converte a coluna 'data' para o padrão BR na hora de mostrar na tabela
        df['data'] = pd.to_datetime(df['data']).dt.strftime('%d/%m/%Y')
        
        # Exibe a tabela com as tarefas (Feitas, Não Realizadas e Pendentes)
        st.dataframe(
            df, 
            column_config={
                "id": None,
                "funcionario": "Responsável",
                "descricao": "Serviço",
                "data": "Data",
                "status": "Status",
                "motivo": None  # Escondemos da tabela para ficar mais limpa
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Secção para expandir os motivos clicando nas tarefas não realizadas
        # Usar .get para evitar erros caso a tabela original ainda não tenha a coluna 'motivo' criada
        if 'status' in df.columns:
            df_nao_realizadas = df[df['status'] == 'Não Realizada']
            
            if not df_nao_realizadas.empty:
                st.markdown("### Detalhes das Tarefas Não Realizadas")
                st.caption("Clique no item abaixo para ver o motivo da faxina não ter sido feita.")
                for _, linha in df_nao_realizadas.iterrows():
                    with st.expander(f"{linha['data']} - {linha['funcionario']} - {linha['descricao']}"):
                        motivo_texto = linha.get('motivo', 'Motivo não registado.') 
                        st.write(f"**Motivo:** {motivo_texto}")
