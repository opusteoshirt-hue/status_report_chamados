import sys
import os
import pandas as pd
import pickle
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from services.oracle_service import executar_query_incidentes, executar_query_workorders
from services.transform import tratar_incidentes, combinar_dados
from auth_manager import AuthManager

# ==================== VERIFICAÇÃO DE AUTENTICAÇÃO ====================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_username" not in st.session_state:
    st.session_state.user_username = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None

if not st.session_state.authenticated or st.session_state.user_username is None:
    st.set_page_config(page_title="Acesso Negado", layout="centered")
    st.warning("Sua sessão expirou ou você não está logado.")
    st.info("Por favor, volte à página inicial para acessar o sistema.")
    if st.button("Ir para a Tela de Login", use_container_width=True):
        st.switch_page("app.py")
    st.stop()

username = st.session_state.user_username
auth = AuthManager()

if not auth.get_user_by_username(username):
    st.warning("Usuário inválido ou revogado. Faça login novamente.")
    st.stop()

# ==================== CONFIGURAR PÁGINA ====================
st.set_page_config(page_title="Dashboard Analítico", layout="wide")
from bmcview_styles import BMCVIEW_CSS
st.markdown(BMCVIEW_CSS, unsafe_allow_html=True)

st.markdown("""
    <style>
        [data-testid="stImage"] img { pointer-events: none !important; }
        [data-testid="stImage"] a  { pointer-events: none !important; cursor: default !important; }
        button[title="View fullscreen"] { display: none !important; }
    </style>
""", unsafe_allow_html=True)

CORES = {
    "roxo":        "#6B3FA0",
    "roxo_claro":  "#6B3FA0",
    "verde":       "#4CAF50",
    "verde_escuro":"#1B5E20",
    "laranja":     "#FF9800",
    "vermelho":    "#F44336",
    "amarelo":     "#FFC107",
    "azul":        "#2196F3"
}

def carregar_logo_esquerda():
    for p in ["assets/logo_generico_2_df.png", "assets/logo_generico_2_df.jpg", "assets/logo_generico_1_df.svg"]:
        if Path(p).exists():
            return p
    return None

def carregar_logo_direita():
    for p in ["assets/logo_generico_1.png", "assets/logo_generico_1.jpg", "assets/logo_generica_2.svg"]:
        if Path(p).exists():
            return p
    return None

def mes_ptbr(mes_numero):
    meses = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
             7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}
    return meses.get(mes_numero, "")

st.markdown("""
    <style>
        div[data-testid="stHorizontalBlock"]:has(> div > div > [data-testid="stImage"]) {
            align-items: center !important;
        }
    </style>
""", unsafe_allow_html=True)

col_logo1, col_title, col_logo2 = st.columns([1, 3, 1])

with col_logo1:
    logo = carregar_logo_esquerda()
    if logo:
        st.image(logo, width=130, use_container_width=False)
    else:
        st.markdown("### ORGANIZAÇÃO")

with col_title:
    st.markdown("""
        <div style='text-align: center;'>
            <h1 style='color: #6B3FA0; margin: 0;'>Dashboard Analítico</h1>
            <p style='margin: 0;'>Incidentes, Ordens de trabalho e Requisições - Organização</p>
        </div>
    """, unsafe_allow_html=True)

with col_logo2:
    logo = carregar_logo_direita()
    if logo:
        st.image(logo, width=180, use_container_width=False)
    else:
        st.markdown("""
            <div style='text-align: right;'>
                <div style='background-color: #6B3FA0; color: white; padding: 8px;
                            border-radius: 8px; display: inline-block; text-align: center;'>
                    <strong>Empresa</strong><br>Tecnologia
                </div>
            </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ==================== SIDEBAR - IDENTIFICAÇÃO E LOGOUT ====================
user_name_display = st.session_state.get("user_name", "Usuário")
st.sidebar.markdown(f"**Usuário:** {user_name_display}")

if st.sidebar.button("Sair", use_container_width=True, type="secondary"):
    st.session_state.authenticated = False
    st.session_state.user_username = None
    st.session_state.user_name = None
    st.session_state.login_time = None
    st.session_state._session_token = None
    st.switch_page("app.py")

st.sidebar.markdown("---")
# =========================================================================

CACHE_FILE           = Path("dados_cache.pkl")
CACHE_TIMESTAMP_FILE = Path("dados_cache_timestamp.pkl")

status_resolvidos  = ['Concluido', 'Cancelado', 'Fechado', 'Resolvido', 'Rejeitado', 'Concluído']
status_finalizados = status_resolvidos.copy()

def is_cache_valid():
    if not CACHE_FILE.exists() or not CACHE_TIMESTAMP_FILE.exists():
        return False
    try:
        with open(CACHE_TIMESTAMP_FILE, "rb") as f:
            timestamp = pickle.load(f)
        return (datetime.now() - timestamp).total_seconds() < 7200
    except Exception:
        return False

def carregar_dados():
    if is_cache_valid():
        with st.spinner("Carregando dados do cache..."):
            with open(CACHE_FILE, "rb") as f:
                df = pickle.load(f)
            with open(CACHE_TIMESTAMP_FILE, "rb") as f:
                timestamp = pickle.load(f)
            return df, timestamp

    with st.spinner("Carregando dados do banco..."):
        progress_bar = st.progress(0)
        progress_bar.progress(25, text="Carregando incidentes...")
        df_incidentes = executar_query_incidentes()
        df_incidentes = tratar_incidentes(df_incidentes, tipo="incidente")
        progress_bar.progress(50, text="Carregando work orders...")
        df_workorders = executar_query_workorders()
        df_workorders = tratar_incidentes(df_workorders, tipo="wo")
        progress_bar.progress(75, text="Combinando dados...")
        df = combinar_dados(df_incidentes, df_workorders)
        progress_bar.progress(100, text="Concluído!")
        progress_bar.empty()
        now = datetime.now()
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(df, f)
        with open(CACHE_TIMESTAMP_FILE, "wb") as f:
            pickle.dump(now, f)
        return df, now

df, ultima_atualizacao = carregar_dados()

# ========== FILTRO POR PERMISSÕES DO USUÁRIO ==========
if 'FILA' in df.columns:
    user_filas = auth.get_user_filas(username)

    if "*" in user_filas:
        st.sidebar.success("Administrador - Acesso a todas as filas")
    elif user_filas:
        filas_validas = [f for f in user_filas if f in df['FILA'].unique()]
        if filas_validas:
            df = df[df['FILA'].isin(filas_validas)]
            st.sidebar.info(f"Filtrado: {len(filas_validas)} fila(s) autorizada(s)")
        else:
            st.sidebar.warning("Nenhuma das suas filas foi encontrada nos dados.")
            df = df.iloc[0:0]
    else:
        st.sidebar.error("Sem permissão de filas. Contate o administrador.")
        df = df.iloc[0:0]
# ========== FIM DO FILTRO ==========

if df.empty:
    st.warning("Nenhum dado disponível. Você não tem acesso a nenhuma fila.")
    st.stop()

with st.sidebar:
    st.markdown("### Controle")

    if st.button("Atualizar Dados", use_container_width=True):
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        if CACHE_TIMESTAMP_FILE.exists():
            CACHE_TIMESTAMP_FILE.unlink()
        st.cache_data.clear()
        st.rerun()

    if CACHE_TIMESTAMP_FILE.exists():
        try:
            with open(CACHE_TIMESTAMP_FILE, "rb") as f:
                ts = pickle.load(f)
            st.caption(f"Cache: {ts.strftime('%d/%m/%Y %H:%M')}")
        except Exception:
            pass

    st.markdown("---")
    st.markdown("### Filtros")
    somente_backlog = st.checkbox("Somente Backlog", value=False)
    st.markdown("---")

    designado_selecionado = []
    if 'DESIGNADO' in df.columns:
        designado_selecionado = st.multiselect("Designado", sorted(df['DESIGNADO'].dropna().unique()))

    fila_selecionado = []
    if 'FILA' in df.columns:
        fila_selecionado = st.multiselect("Fila", sorted(df['FILA'].dropna().unique()))

    cat1_selecionado = []
    if 'CATEGORIA_1' in df.columns:
        cat1_selecionado = st.multiselect("Categoria 1", sorted(df['CATEGORIA_1'].dropna().unique()))

    status_selecionado = []
    if 'STATUS_DESC' in df.columns:
        status_selecionado = st.multiselect("Status", sorted(df['STATUS_DESC'].dropna().unique()))

    tipo_selecionado = []
    if 'TIPO_CHAMADO' in df.columns:
        tipo_selecionado = st.multiselect("Tipo de Chamado", sorted(df['TIPO_CHAMADO'].unique()))

    criticidade_selecionado = []
    if 'CRITICIDADE_DESC' in df.columns:
        criticidade_selecionado = st.multiselect("Criticidade", sorted(df['CRITICIDADE_DESC'].dropna().unique()))

    # ==================== FILTRO DE DATA DE CRIAÇÃO (OPCIONAL) ====================
    st.markdown("### Data de Criação")
    aplicar_filtro_criacao = st.checkbox("Filtrar por data de criação", value=False, key="dashboard_aplicar_criacao")
    
    start_date = None
    end_date = None
    if aplicar_filtro_criacao and 'DATA_CRIACAO' in df.columns and not df.empty:
        datas_validas = df['DATA_CRIACAO'].dropna()
        if len(datas_validas) > 0:
            min_date = datas_validas.min().date()
            max_date = datas_validas.max().date()
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Inicial", min_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
            with col2:
                end_date = st.date_input("Final", max_date, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
            if start_date > end_date:
                st.error("Data Inicial não pode ser maior que Data Final")
                st.stop()

    # ==================== FILTRO DE DATA DE RESOLUÇÃO (OPCIONAL) ====================
    st.markdown("### Data de Resolução")
    aplicar_filtro_resolucao = st.checkbox("Filtrar por data de resolução", value=False, key="dashboard_aplicar_resolucao")
    
    start_date_resolucao = None
    end_date_resolucao = None
    if aplicar_filtro_resolucao and 'DATA_RESOLUCAO' in df.columns and not df.empty:
        datas_resolucao_validas = df['DATA_RESOLUCAO'].dropna()
        if len(datas_resolucao_validas) > 0:
            min_date_resolucao = datas_resolucao_validas.min().date()
            max_date_resolucao = datas_resolucao_validas.max().date()
            col1, col2 = st.columns(2)
            with col1:
                start_date_resolucao = st.date_input("Inicial", min_date_resolucao, min_value=min_date_resolucao, max_value=max_date_resolucao, format="DD/MM/YYYY")
            with col2:
                end_date_resolucao = st.date_input("Final", max_date_resolucao, min_value=min_date_resolucao, max_value=max_date_resolucao, format="DD/MM/YYYY")
            if start_date_resolucao and end_date_resolucao and start_date_resolucao > end_date_resolucao:
                st.error("Data Inicial não pode ser maior que Data Final")
                st.stop()
        else:
            st.caption("Nenhum chamado resolvido encontrado")

df_filtrado = df.copy()

if somente_backlog:
    df_filtrado = df_filtrado[~df_filtrado['STATUS_DESC'].isin(status_finalizados)]
if designado_selecionado:
    df_filtrado = df_filtrado[df_filtrado['DESIGNADO'].isin(designado_selecionado)]
if fila_selecionado:
    df_filtrado = df_filtrado[df_filtrado['FILA'].isin(fila_selecionado)]
if cat1_selecionado:
    df_filtrado = df_filtrado[df_filtrado['CATEGORIA_1'].isin(cat1_selecionado)]
if status_selecionado:
    df_filtrado = df_filtrado[df_filtrado['STATUS_DESC'].isin(status_selecionado)]
if tipo_selecionado:
    df_filtrado = df_filtrado[df_filtrado['TIPO_CHAMADO'].isin(tipo_selecionado)]
if criticidade_selecionado:
    df_filtrado = df_filtrado[df_filtrado['CRITICIDADE_DESC'].isin(criticidade_selecionado)]

# Aplicar filtro de data de criação (se ativo)
if aplicar_filtro_criacao and start_date and end_date and 'DATA_CRIACAO' in df_filtrado.columns and not df_filtrado.empty:
    df_filtrado = df_filtrado[
        (df_filtrado['DATA_CRIACAO'].dt.date >= start_date) &
        (df_filtrado['DATA_CRIACAO'].dt.date <= end_date)
    ]

# Aplicar filtro de data de resolução (se ativo)
if aplicar_filtro_resolucao and start_date_resolucao and end_date_resolucao and 'DATA_RESOLUCAO' in df_filtrado.columns and not df_filtrado.empty:
    df_filtrado['DATA_RESOLUCAO'] = pd.to_datetime(df_filtrado['DATA_RESOLUCAO'], errors='coerce')
    df_filtrado = df_filtrado[
        (df_filtrado['DATA_RESOLUCAO'].dt.date >= start_date_resolucao) &
        (df_filtrado['DATA_RESOLUCAO'].dt.date <= end_date_resolucao)
    ]

total_criados    = len(df_filtrado)
total_resolvidos = len(df_filtrado[df_filtrado['STATUS_DESC'].isin(status_resolvidos)])
backlogs_abertos = len(df_filtrado[~df_filtrado['STATUS_DESC'].isin(status_finalizados)])
taxa_absorcao    = (total_resolvidos / total_criados * 100) if total_criados > 0 else 0

st.subheader("Indicadores de Performance")
col1, col2, col3, col4 = st.columns(4)

def card_kpi(titulo, valor, cor):
    st.markdown(f"""
        <div style='background: linear-gradient(135deg, {cor}, {cor}cc);
                    padding: 20px; border-radius: 15px; text-align: center;
                    color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                    border: 1px solid rgba(255,255,255,0.2);'>
            <h2 style='margin: 0; font-size: 32px; font-weight: bold;'>{valor}</h2>
            <p style='margin: 8px 0 0 0; font-size: 14px; opacity: 0.9;'>{titulo}</p>
        </div>
    """, unsafe_allow_html=True)

with col1:
    card_kpi("Total Criados",    f"{total_criados:,}".replace(",", "."),    CORES["roxo"])
with col2:
    card_kpi("Total Resolvidos", f"{total_resolvidos:,}".replace(",", "."), CORES["roxo"])
with col3:
    card_kpi("Backlogs Abertos", f"{backlogs_abertos:,}".replace(",", "."), CORES["verde_escuro"])
with col4:
    card_kpi("Taxa de Absorção", f"{taxa_absorcao:.2f}%".replace('.', ','), CORES["roxo_claro"])

st.markdown("---")
st.subheader("Volumetria e Eficiência de Chamados")

if 'DATA_CRIACAO' in df_filtrado.columns and not df_filtrado.empty:
    df_filtrado['MES_ANO_CRIACAO'] = df_filtrado['DATA_CRIACAO'].dt.to_period('M')
    criados_mensal = df_filtrado.groupby('MES_ANO_CRIACAO').size().reset_index(name='Criados')

    df_resolvidos = df_filtrado[df_filtrado['STATUS_DESC'].isin(status_resolvidos)].copy()
    if not df_resolvidos.empty and 'DATA_RESOLUCAO' in df_resolvidos.columns:
        df_resolvidos['MES_ANO_RESOLUCAO'] = df_resolvidos['DATA_RESOLUCAO'].dt.to_period('M')
        resolvidos_mensal = df_resolvidos.groupby('MES_ANO_RESOLUCAO').size().reset_index(name='Resolvidos')
        resolvidos_mensal = resolvidos_mensal.rename(columns={'MES_ANO_RESOLUCAO': 'MES_ANO'})
    else:
        resolvidos_mensal = pd.DataFrame({'MES_ANO': [], 'Resolvidos': []})

    criados_mensal = criados_mensal.rename(columns={'MES_ANO_CRIACAO': 'MES_ANO'})
    mensal = criados_mensal.merge(resolvidos_mensal, on='MES_ANO', how='outer').fillna(0)
    mensal = mensal.sort_values('MES_ANO').tail(12)

    mensal['Rotulo']    = mensal['MES_ANO'].apply(lambda p: f"{mes_ptbr(p.month)} {p.year}" if pd.notna(p) else "")
    mensal['Criados']   = mensal['Criados'].astype(int)
    mensal['Resolvidos'] = mensal['Resolvidos'].astype(int)

    if not mensal.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=mensal['Rotulo'], y=mensal['Criados'], name='Criados',
                             marker_color=CORES["vermelho"],
                             text=mensal['Criados'].apply(lambda x: f'{x:,}'.replace(',', '.')),
                             textposition='outside'))
        fig.add_trace(go.Bar(x=mensal['Rotulo'], y=mensal['Resolvidos'], name='Resolvidos',
                             marker_color=CORES["verde"],
                             text=mensal['Resolvidos'].apply(lambda x: f'{x:,}'.replace(',', '.')),
                             textposition='outside'))
        fig.update_layout(
            title="Comparativo Mensal - Criados vs Resolvidos",
            xaxis_title="Mês/Ano", yaxis_title="Quantidade", barmode='group', height=450,
            yaxis=dict(range=[0, max(mensal['Criados'].max(), mensal['Resolvidos'].max()) * 1.2])
        )
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Top Categorias")

if 'CATEGORIA_1' in df_filtrado.columns and not df_filtrado.empty:
    top = df_filtrado['CATEGORIA_1'].value_counts().head(15).reset_index()
    top.columns = ['Categoria', 'Quantidade']
    fig = px.bar(top, x='Quantidade', y='Categoria', orientation='h',
                 color='Quantidade', color_continuous_scale='Purples',
                 title="Top 15 Categoria Operacional 1",
                 text=top['Quantidade'].apply(lambda x: f'{x:,}'.replace(',', '.')))
    fig.update_traces(textposition='outside')
    fig.update_layout(height=500, xaxis=dict(range=[0, top['Quantidade'].max() * 1.2]))
    st.plotly_chart(fig, use_container_width=True)

if 'FILA' in df_filtrado.columns and not df_filtrado.empty:
    top = df_filtrado['FILA'].value_counts().head(15).reset_index()
    top.columns = ['Fila', 'Quantidade']
    fig = px.bar(top, x='Quantidade', y='Fila', orientation='h',
                 color='Quantidade', color_continuous_scale='Oranges',
                 title="Top 15 Filas - Total de Chamados",
                 text=top['Quantidade'].apply(lambda x: f'{x:,}'.replace(',', '.')))
    fig.update_traces(textposition='outside')
    fig.update_layout(height=500, xaxis=dict(range=[0, top['Quantidade'].max() * 1.2]))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Representatividade de Status")

if not df_filtrado.empty:
    resolvidos_total = len(df_filtrado[df_filtrado['STATUS_DESC'].isin(status_resolvidos)])
    pendentes        = total_criados - resolvidos_total
    fig_donut = go.Figure(data=[go.Pie(
        labels=['Resolvido', 'Pendente'], values=[resolvidos_total, pendentes],
        hole=0.6, marker_colors=[CORES["verde"], CORES["laranja"]],
        textinfo='label+percent', textposition='outside'
    )])
    fig_donut.update_layout(
        title="Taxa de Resolução", height=380,
        annotations=[dict(text=f'{taxa_absorcao:.2f}%'.replace('.', ','),
                          x=0.5, y=0.5, font_size=28, showarrow=False)]
    )
    st.plotly_chart(fig_donut, use_container_width=True)

if 'STATUS_DESC' in df_filtrado.columns and not df_filtrado.empty:
    sc = df_filtrado['STATUS_DESC'].value_counts().reset_index()
    sc.columns = ['Status', 'Quantidade']
    fig = px.bar(sc, x='Quantidade', y='Status', orientation='h',
                 color='Quantidade', color_continuous_scale='Blues',
                 title="Distribuição por Status",
                 text=sc['Quantidade'].apply(lambda x: f'{x:,}'.replace(',', '.')))
    fig.update_traces(textposition='outside')
    fig.update_layout(height=380, xaxis=dict(range=[0, sc['Quantidade'].max() * 1.2]))
    st.plotly_chart(fig, use_container_width=True)
    resolvidos_qtd = len(df_filtrado[df_filtrado['STATUS_DESC'].isin(status_resolvidos)])
    st.caption(f"Resolvidos: {resolvidos_qtd:,} | Pendentes: {total_criados - resolvidos_qtd:,}")

st.markdown("---")
st.subheader("Top Ofensores por Categoria Operacional 2")

if 'CATEGORIA_2' in df_filtrado.columns and not df_filtrado.empty:
    top = df_filtrado['CATEGORIA_2'].value_counts().head(15).reset_index()
    top.columns = ['Categoria', 'Quantidade']
    fig = px.bar(top, x='Quantidade', y='Categoria', orientation='h',
                 color='Quantidade', color_continuous_scale='Reds',
                 title="Top 15 Categorias Operacionais Nível 2",
                 text=top['Quantidade'].apply(lambda x: f'{x:,}'.replace(',', '.')))
    fig.update_traces(textposition='outside')
    fig.update_layout(height=600, xaxis=dict(range=[0, top['Quantidade'].max() * 1.2]))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Empresa por Fila - Chamados Pendentes")

if 'FILA' in df_filtrado.columns and not df_filtrado.empty:
    df_pendentes = df_filtrado[~df_filtrado['STATUS_DESC'].isin(status_finalizados)]
    if not df_pendentes.empty:
        def extrair_nome_base(nome):
            if pd.isna(nome):
                return "Não Identificado"
            s = str(nome)
            return s.split('-')[0].strip() if '-' in s else s

        df_p = df_pendentes.copy()
        df_p['FILA_AGRUPADA'] = df_p['FILA'].apply(extrair_nome_base)
        ef = df_p['FILA_AGRUPADA'].value_counts().head(10).reset_index()
        ef.columns = ['Empresa/Fila', 'Chamados Pendentes']
        fig = px.bar(ef, x='Chamados Pendentes', y='Empresa/Fila', orientation='h',
                     color='Chamados Pendentes', color_continuous_scale='Blues',
                     title="Top 10 Filas com Mais Chamados Pendentes",
                     text=ef['Chamados Pendentes'].apply(lambda x: f'{x:,}'.replace(',', '.')))
        fig.update_traces(textposition='outside')
        fig.update_layout(height=500, xaxis=dict(range=[0, ef['Chamados Pendentes'].max() * 1.2]))
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Detalhes do Agrupamento"):
            st.markdown("**Regra:** Nomes agrupados pelo prefixo antes do primeiro hífen")
            st.info(f"Nomes originais: {df_pendentes['FILA'].nunique()} | Após agrupamento: {df_p['FILA_AGRUPADA'].nunique()}")
    else:
        st.info("Nenhum chamado pendente com os filtros atuais")

st.markdown("---")
st.subheader("Chamados em Aberto por Criticidade")

if 'CRITICIDADE_DESC' in df_filtrado.columns and not df_filtrado.empty:
    df_aberto = df_filtrado[~df_filtrado['STATUS_DESC'].isin(status_finalizados)]
    if not df_aberto.empty:
        criticidade_limpa = df_aberto['CRITICIDADE_DESC'].dropna()
        if not criticidade_limpa.empty:
            cc = criticidade_limpa.value_counts().reset_index()
            cc.columns = ['Criticidade', 'Quantidade']
            cc['Criticidade'] = cc['Criticidade'].astype(str)
            for crit in ['Crítico', 'Alto', 'Médio', 'Baixo']:
                if crit not in cc['Criticidade'].values:
                    cc = pd.concat([cc, pd.DataFrame({'Criticidade': [crit], 'Quantidade': [0]})], ignore_index=True)
            cc['Criticidade'] = pd.Categorical(cc['Criticidade'], categories=['Crítico','Alto','Médio','Baixo'], ordered=True)
            cc = cc.sort_values('Criticidade')
            fig = px.bar(cc, x='Criticidade', y='Quantidade',
                         color='Criticidade',
                         color_discrete_sequence=[CORES["vermelho"], CORES["laranja"], CORES["amarelo"], CORES["verde"]],
                         title="Volume de Chamados Abertos por Criticidade",
                         text=cc['Quantidade'].apply(lambda x: f'{int(x):,}'.replace(',', '.')))
            fig.update_traces(textposition='outside')
            fig.update_layout(height=400, yaxis=dict(range=[0, cc['Quantidade'].max() * 1.2]))
            st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("Histórico Taxa de Absorção Anual")

if 'DATA_CRIACAO' in df_filtrado.columns and not df_filtrado.empty:
    anos = sorted(set(df_filtrado['DATA_CRIACAO'].dt.year.dropna().unique()) |
                  set(df_filtrado['DATA_RESOLUCAO'].dt.year.dropna().unique()))
    taxa_anual = []
    for ano in anos:
        criados_ano    = len(df_filtrado[df_filtrado['DATA_CRIACAO'].dt.year == ano])
        resolvidos_ano = len(df_filtrado[(df_filtrado['DATA_RESOLUCAO'].dt.year == ano) &
                                         (df_filtrado['STATUS_DESC'].isin(status_resolvidos))])
        taxa = (resolvidos_ano / criados_ano * 100) if criados_ano > 0 else 0
        taxa_anual.append({'Ano': int(ano), 'Taxa (%)': round(taxa),
                           'Criados': criados_ano, 'Resolvidos': resolvidos_ano})

    if taxa_anual:
        df_taxa = pd.DataFrame(taxa_anual)
        df_taxa['Ano_str'] = df_taxa['Ano'].astype(str)
        fig = px.line(df_taxa, x='Ano_str', y='Taxa (%)', markers=True,
                      title="Evolução da Taxa de Absorção por Ano",
                      category_orders={'Ano_str': df_taxa['Ano_str'].tolist()})
        fig.update_layout(
            yaxis_title="Taxa de Absorção (%)", xaxis_title="Ano", height=400,
            yaxis_tickformat='.0f', yaxis_range=[0, df_taxa['Taxa (%)'].max() * 1.15],
            xaxis=dict(type='category')
        )
        fig.update_traces(
            line_color=CORES["roxo"], marker_color=CORES["roxo"], marker_size=10,
            text=df_taxa['Taxa (%)'].apply(lambda x: f'{x:.0f}%'.replace('.', ',')),
            textposition='top center', mode='lines+markers+text'
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Detalhes por Ano"):
            for _, row in df_taxa.iterrows():
                c1, c2, c3 = st.columns(3)
                with c1: st.metric(f"Ano {int(row['Ano'])}", f"{row['Taxa (%)']:.0f}%")
                with c2: st.metric("Criados",    f"{int(row['Criados']):,}".replace(",", "."))
                with c3: st.metric("Resolvidos", f"{int(row['Resolvidos']):,}".replace(",", "."))

st.markdown("---")
st.caption(f"Última atualização: {ultima_atualizacao.strftime('%d/%m/%Y %H:%M:%S')}")