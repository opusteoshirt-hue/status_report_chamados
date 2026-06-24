import sys
import os
import pandas as pd
import pickle
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import unicodedata
import ftfy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
from services.oracle_service import executar_query_incidentes, executar_query_workorders
from services.transform import tratar_incidentes, combinar_dados
from auth_manager import AuthManager
from bmcview_styles import BMCVIEW_CSS
from error_messages import get_error_message

# == Configuração da página ==
st.set_page_config(page_title="BmcView", layout="wide")
st.markdown(BMCVIEW_CSS, unsafe_allow_html=True)

# == Session state ==
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_username" not in st.session_state:
    st.session_state.user_username = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "login_time" not in st.session_state:
    st.session_state.login_time = None

auth = AuthManager()

# == Persistência de sessão via cookie ==
SESSION_FILE = Path("data/sessions.pkl")
TOKEN_COOKIE_NAME = "bmcview_session"

def _load_sessions():
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return {}

def _save_sessions(sessions: dict):
    SESSION_FILE.parent.mkdir(exist_ok=True)
    with open(SESSION_FILE, "wb") as f:
        pickle.dump(sessions, f)

def create_session_token(username: str, user_name: str, login_time: datetime) -> str:
    token = str(uuid.uuid4())
    sessions = _load_sessions()
    sessions[token] = {
        "username": username,
        "user_name": user_name,
        "login_time": login_time,
    }
    _save_sessions(sessions)
    return token

def get_session_by_token(token: str):
    sessions = _load_sessions()
    return sessions.get(token)

def delete_session_token(token: str):
    sessions = _load_sessions()
    if token in sessions:
        del sessions[token]
        _save_sessions(sessions)

def set_session_cookie(token: str):
    components.html(f"""
        <script>
            document.cookie = "{TOKEN_COOKIE_NAME}={token}; path=/; max-age=86400; SameSite=Lax";
        </script>
    """, height=0)

def clear_session_cookie():
    components.html(f"""
        <script>
            document.cookie = "{TOKEN_COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        </script>
    """, height=0)

def restore_session_from_cookie():
    try:
        token = st.session_state.get("_session_token")
        if not token:
            try:
                token = st.query_params.get("session_token")
                if token:
                    st.query_params.clear()
            except Exception:
                pass
        if not token or st.session_state.authenticated:
            return
        session_data = get_session_by_token(token)
        if not session_data:
            return
        login_time = session_data["login_time"]
        if isinstance(login_time, datetime) and datetime.now() - login_time > timedelta(hours=24):
            delete_session_token(token)
            clear_session_cookie()
            return
        users = auth.listar_usuarios()
        username = session_data["username"]
        if username not in users:
            delete_session_token(token)
            clear_session_cookie()
            return
        user_data = users[username]
        if not user_data.get("ativo", False) or not user_data.get("autorizado", False):
            delete_session_token(token)
            clear_session_cookie()
            return
        st.session_state.authenticated = True
        st.session_state.user_username = username
        st.session_state.user_name = session_data["user_name"]
        st.session_state.login_time = login_time
        st.session_state._session_token = token
    except Exception:
        pass

restore_session_from_cookie()

def logout():
    token = st.session_state.get("_session_token")
    if token:
        delete_session_token(token)
    clear_session_cookie()
    st.session_state.authenticated = False
    st.session_state.user_username = None
    st.session_state.user_name = None
    st.session_state.login_time = None
    st.session_state._session_token = None
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.rerun()

# == Correção de texto ==
def corrigir_texto(texto):
    if not isinstance(texto, str):
        return texto
    try:
        corrigido = texto.encode('latin-1').decode('utf-8')
        return ftfy.fix_text(corrigido)
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return ftfy.fix_text(texto)

def remover_acentos(texto):
    if not isinstance(texto, str):
        return texto
    texto = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in texto if not unicodedata.combining(c))

def formatar_tempo_resolucao(minutos):
    if pd.isna(minutos):
        return 'N/A'
    try:
        if isinstance(minutos, str):
            minutos = float(minutos.strip().replace(',', '.'))
        minutos = int(float(minutos))
    except Exception:
        return 'N/A'
    if minutos <= 0:
        return 'N/A'
    if minutos < 60:
        return f"{minutos} minuto(s)"
    elif minutos < 1440:
        h = minutos // 60
        m = minutos % 60
        return f"{h} hora(s) e {m} minuto(s)" if m else f"{h} hora(s)"
    else:
        d = minutos // 1440
        h = (minutos % 1440) // 60
        m = minutos % 60
        if h and m:
            return f"{d} dia(s), {h} hora(s) e {m} minuto(s)"
        elif h:
            return f"{d} dia(s) e {h} hora(s)"
        elif m:
            return f"{d} dia(s) e {m} minuto(s)"
        return f"{d} dia(s)"

def limpar_dados(df):
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].apply(lambda x: corrigir_texto(x) if isinstance(x, str) else x)
    if 'TITULO' in df.columns:
        df['TITULO'] = df['TITULO'].apply(
            lambda x: x.replace(';', '-').replace(',', '-').replace('|', '-').strip()
            if isinstance(x, str) else x
        )
    if 'TEMPO_SOLUCAO_MIN' in df.columns:
        df['TEMPO_SOLUCAO'] = df['TEMPO_SOLUCAO_MIN'].apply(formatar_tempo_resolucao)
    return df

# == Tela de login ==
def show_login():
    st.markdown("""
        <style>
            [data-testid="stSidebarNav"] { display: none !important; }
            .stSidebar { display: none !important; }
            header { visibility: hidden !important; }
            [data-testid="stMainBlockContainer"] {
                padding: 0 !important; margin: 0 !important; max-width: 100% !important;
            }
            .main .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
            .stApp { margin-top: -2.5rem !important; padding-top: 0 !important; }
            .stAppViewContainer { padding-top: 0 !important; margin-top: 0 !important; }
            [data-testid="stHorizontalBlock"] {
                gap: 20px !important; height: 100vh !important; margin: 0 !important; padding: 0 !important;
            }
            [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
                height: 100vh !important; padding: 0 !important; margin: 0 !important;
            }
            [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child {
                display: flex !important; flex-direction: column !important;
                justify-content: center !important; align-items: center !important;
            }
            [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child > div {
                width: 100% !important; display: flex !important; flex-direction: column !important;
                justify-content: center !important; align-items: center !important;
            }
            [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child {
                background-color: var(--background-color) !important;
            }
            .login-card {
                width: 100%;
                max-width: 380px;
                margin: 0 auto;
                padding: 0 32px;
                box-sizing: border-box;
            }
        </style>
    """, unsafe_allow_html=True)

    col_esquerda, col_direita = st.columns(2)

    with col_esquerda:
        st.markdown("""
            <div style="
                background: linear-gradient(135deg, #4b2aad 0%, #7a4fc9 45%, #d48fbe 100%);
                height: 100vh; display: flex; align-items: center; justify-content: center;
                flex-direction: column; text-align: center; padding: 0 40px; box-sizing: border-box;
            ">
                <h1 style="font-size: 64px; color: white; margin: 0; font-family: sans-serif; font-weight: bold;">
                    BEM-VINDO!
                </h1>
                <p style="font-size: 20px; color: white; margin-top: 20px; font-family: sans-serif;">
                    Dashboard de Chamados - Gabriel/DF
                </p>
            </div>
        """, unsafe_allow_html=True)

    with col_direita:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown("### Acesso ao Sistema")
        st.caption("Use seu usuário e senha do Windows (rede Gabriel)")

        with st.form(key="login_form"):
            username = st.text_input("Usuário", placeholder="ex: joao.silva", key="login_username_input")
            password = st.text_input("Senha", type="password", key="login_password_input")

            if st.form_submit_button("Entrar", use_container_width=True):
                if username and password:
                    with st.spinner("Autenticando..."):
                        success, message = auth.login(username, password)
                    if success:
                        user_data = auth.get_user_by_username(username.strip().lower())
                        login_time = datetime.now()
                        uname = username.strip().lower()
                        uname_display = user_data.get('nome', username) if user_data else username

                        token = create_session_token(uname, uname_display, login_time)

                        st.session_state.authenticated = True
                        st.session_state.user_username = uname
                        st.session_state.user_name = uname_display
                        st.session_state.login_time = login_time
                        st.session_state._session_token = token

                        set_session_cookie(token)
                        
                        try:
                            st.query_params.clear()
                        except Exception:
                            pass
                        
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Preencha o usuário e a senha.")

        st.markdown('</div>', unsafe_allow_html=True)

# == Dashboard principal ==
def show_dashboard():
    # == Estilo da sidebar ==
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                display: block !important;
                min-width: 300px !important;
            }
        </style>
    """, unsafe_allow_html=True)

    CORES = {
        "roxo": "#6B3FA0",
        "roxo_claro": "#6B3FA0",
        "verde": "#4CAF50",
        "verde_escuro": "#1B5E20",
        "laranja": "#FF9800",
        "vermelho": "#F44336",
        "amarelo": "#FFC107",
        "azul": "#2196F3"
    }

    # == Função auxiliar para logos ==
    def carregar_logo(paths):
        for p in paths:
            if Path(p).exists():
                return p
        return None

    # == Cabeçalho com logos ==
    st.markdown("""
        <style>
            div[data-testid="stHorizontalBlock"]:has(> div > div > [data-testid="stImage"]) {
                align-items: center !important;
            }
        </style>
    """, unsafe_allow_html=True)

    col_logo1, col_title, col_logo2 = st.columns([1, 3, 1])
    with col_logo1:
        logo = carregar_logo(["assets/logo_Gabriel_df.png", "assets/logo_Gabriel_df.jpg", "assets/logo_Gabriel_df.svg"])
        if logo:
            st.image(logo, width=130, use_container_width=False)
        else:
            st.markdown("### Gabriel")

    with col_title:
        st.markdown("""
            <div style='text-align: center;'>
                <h1 style='color: #6B3FA0; margin: 0;'>Dashboard</h1>
                <p style='margin: 0;'>Incidentes, Ordens de trabalho e Requisições - Gabriel/DF</p>
            </div>
        """, unsafe_allow_html=True)

    with col_logo2:
        logo = carregar_logo(["assets/logo_truly.png", "assets/logo_truly.jpg", "assets/logo_truly.svg"])
        if logo:
            st.image(logo, width=180, use_container_width=False)
        else:
            st.markdown("""
                <div style='text-align: right;'>
                    <div style='background-color: #6B3FA0; color: white; padding: 8px;
                                border-radius: 8px; display: inline-block; text-align: center;'>
                        <strong>Truly</strong><br>Tecnologia
                    </div>
                </div>
            """, unsafe_allow_html=True)

    # == Bloqueio de expansão de imagens ==
    st.markdown("""
        <style>
            [data-testid="stImage"] img { pointer-events: none !important; }
            [data-testid="stImage"] a  { pointer-events: none !important; cursor: default !important; }
            button[title="View fullscreen"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # == Sidebar: usuário e logout ==
    st.sidebar.markdown(f"**Usuário:** {st.session_state.user_name}")
    if st.sidebar.button("Sair", use_container_width=True):
        logout()
    st.sidebar.markdown("---")

    # == Sidebar: admin ==
    if auth.is_admin(st.session_state.user_username):
        unread_count = auth.get_unread_count()
        notif_text = "Admin - Gerenciar Usuários"
        if unread_count > 0:
            notif_text = f"Admin - Gerenciar Usuários ({unread_count})"
        if st.sidebar.button(notif_text, use_container_width=True):
            st.switch_page("pages/admin.py")

    # == Cache e carregamento de dados ==
    CACHE_FILE = Path("dados_cache.pkl")
    CACHE_TIMESTAMP_FILE = Path("dados_cache_timestamp.pkl")

    status_resolvidos = ['Concluido', 'Cancelado', 'Fechado', 'Resolvido', 'Rejeitado', 'Concluído']
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
            df = limpar_dados(df)
            progress_bar.progress(100, text="Concluído!")
            progress_bar.empty()
            now = datetime.now()
            with open(CACHE_FILE, "wb") as f:
                pickle.dump(df, f)
            with open(CACHE_TIMESTAMP_FILE, "wb") as f:
                pickle.dump(now, f)
            return df, now

    df, ultima_atualizacao = carregar_dados()

    # == Filtro por filas do usuário ==
    if 'FILA' in df.columns:
        user_filas = auth.get_user_filas(st.session_state.user_username)

        if "*" in user_filas:
            st.sidebar.success("Administrador - Acesso a todas as filas")
        elif user_filas:
            filas_validas = [f for f in user_filas if f in df['FILA'].unique()]
            if filas_validas:
                original_size = len(df)
                df = df[df['FILA'].isin(filas_validas)]
                if len(df) < original_size:
                    st.sidebar.info(f"Filtrado: {len(filas_validas)} fila(s) autorizada(s)")
                    with st.sidebar.expander("Suas filas autorizadas:"):
                        for fila in sorted(filas_validas):
                            qtd = len(df[df['FILA'] == fila])
                            st.markdown(f"- {fila} ({qtd} chamados)")
            else:
                st.sidebar.warning("Nenhuma das suas filas foi encontrada nos dados.")
                df = df.iloc[0:0]
        else:
            st.sidebar.error("Sem permissão de filas. Contate o administrador.")
            df = df.iloc[0:0]

    # == Sidebar: controles e filtros ==
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
        
        # == Filtros de pesquisa ==
        st.markdown("### Pesquisa")
        search_id = st.text_input("ID do Chamado", placeholder="Digite o número do chamado...")
        search_title = st.text_input("Título", placeholder="Pesquisar no título...")
        st.markdown("---")

        somente_backlog = st.checkbox("Somente Backlog", value=False)
        st.markdown("---")

        # == Filtros por colunas ==
        designado_selecionado = []
        if 'DESIGNADO' in df.columns and not df.empty:
            designado_selecionado = st.multiselect("Designado", sorted(df['DESIGNADO'].dropna().unique()))

        cliente_selecionado = []
        if 'CLIENTE' in df.columns and not df.empty:
            cliente_selecionado = st.multiselect("Cliente", sorted(df['CLIENTE'].dropna().unique()))

        fila_selecionado = []
        if 'FILA' in df.columns and not df.empty:
            fila_selecionado = st.multiselect("Fila", sorted(df['FILA'].dropna().unique()))

        cat1_selecionado = []
        if 'CATEGORIA_1' in df.columns and not df.empty:
            cat1_selecionado = st.multiselect("Categoria 1", sorted(df['CATEGORIA_1'].dropna().unique()))
        
        cat2_selecionado = []
        if 'CATEGORIA_2' in df.columns and not df.empty:
            cat2_selecionado = st.multiselect("Categoria 2", sorted(df['CATEGORIA_2'].dropna().unique()))
        
        cat3_selecionado = []
        if 'CATEGORIA_3' in df.columns and not df.empty:
            cat3_selecionado = st.multiselect("Categoria 3", sorted(df['CATEGORIA_3'].dropna().unique()))

        status_selecionado = []
        if 'STATUS_DESC' in df.columns and not df.empty:
            status_selecionado = st.multiselect("Status", sorted(df['STATUS_DESC'].dropna().unique()))

        tipo_selecionado = []
        if 'TIPO_CHAMADO' in df.columns and not df.empty:
            tipo_selecionado = st.multiselect("Tipo de Chamado", sorted(df['TIPO_CHAMADO'].unique()))

        criticidade_selecionado = []
        if 'CRITICIDADE_DESC' in df.columns and not df.empty:
            criticidade_selecionado = st.multiselect("Criticidade", sorted(df['CRITICIDADE_DESC'].dropna().unique()))

        # == Filtros de data com checkbox ==
        st.markdown("### Data de Criação")
        aplicar_criacao = st.checkbox("Filtrar por data de criação", value=False, key="aplicar_criacao")
        start_date_criacao = None
        end_date_criacao = None
        if aplicar_criacao and 'DATA_CRIACAO' in df.columns and not df.empty:
            df['DATA_CRIACAO'] = pd.to_datetime(df['DATA_CRIACAO'], errors='coerce')
            min_date_criacao = df['DATA_CRIACAO'].min().date()
            max_date_criacao = df['DATA_CRIACAO'].max().date()
            col1, col2 = st.columns(2)
            with col1:
                start_date_criacao = st.date_input("Inicial", min_date_criacao,
                                                   min_value=min_date_criacao,
                                                   max_value=max_date_criacao,
                                                   format="DD/MM/YYYY", key="criacao_inicio")
            with col2:
                end_date_criacao = st.date_input("Final", max_date_criacao,
                                                 min_value=min_date_criacao,
                                                 max_value=max_date_criacao,
                                                 format="DD/MM/YYYY", key="criacao_fim")
            if start_date_criacao and end_date_criacao and start_date_criacao > end_date_criacao:
                st.error("Data Inicial não pode ser maior que Data Final")
                st.stop()

        st.markdown("### Data de Resolução")
        aplicar_resolucao = st.checkbox("Filtrar por data de resolução", value=False, key="aplicar_resolucao")
        start_date_resolucao = None
        end_date_resolucao = None
        if aplicar_resolucao and 'DATA_RESOLUCAO' in df.columns and not df.empty:
            df['DATA_RESOLUCAO'] = pd.to_datetime(df['DATA_RESOLUCAO'], errors='coerce')
            datas_resolucao_validas = df['DATA_RESOLUCAO'].dropna()
            if not datas_resolucao_validas.empty:
                min_date_resolucao = datas_resolucao_validas.min().date()
                max_date_resolucao = datas_resolucao_validas.max().date()
                col1, col2 = st.columns(2)
                with col1:
                    start_date_resolucao = st.date_input("Inicial", min_date_resolucao,
                                                         min_value=min_date_resolucao,
                                                         max_value=max_date_resolucao,
                                                         format="DD/MM/YYYY", key="resolucao_inicio")
                with col2:
                    end_date_resolucao = st.date_input("Final", max_date_resolucao,
                                                       min_value=min_date_resolucao,
                                                       max_value=max_date_resolucao,
                                                       format="DD/MM/YYYY", key="resolucao_fim")
                if start_date_resolucao and end_date_resolucao and start_date_resolucao > end_date_resolucao:
                    st.error("Data Inicial não pode ser maior que Data Final")
                    st.stop()
            else:
                st.caption("Nenhum chamado resolvido encontrado")

    # == Verifica se há dados ==
    if df.empty:
        st.warning(get_error_message("NO_DATA"))
        st.stop()

    # == Aplicação dos filtros ==
    df_filtrado = df.copy()

    # Pesquisa por ID e Título
    if search_id:
        df_filtrado = df_filtrado[df_filtrado['CHAMADOS'].astype(str).str.contains(search_id, case=False, na=False)]
    
    if search_title:
        termo_normalizado = remover_acentos(search_title.lower().strip())
        mask = df_filtrado['TITULO'].astype(str).apply(
            lambda x: termo_normalizado in remover_acentos(x.lower()) if pd.notna(x) else False
        )
        df_filtrado = df_filtrado[mask]

    # Demais filtros
    if somente_backlog:
        df_filtrado = df_filtrado[~df_filtrado['STATUS_DESC'].isin(status_finalizados)]
    if designado_selecionado:
        df_filtrado = df_filtrado[df_filtrado['DESIGNADO'].isin(designado_selecionado)]
    if cliente_selecionado:
        df_filtrado = df_filtrado[df_filtrado['CLIENTE'].isin(cliente_selecionado)]
    if fila_selecionado:
        df_filtrado = df_filtrado[df_filtrado['FILA'].isin(fila_selecionado)]
    if cat1_selecionado:
        df_filtrado = df_filtrado[df_filtrado['CATEGORIA_1'].isin(cat1_selecionado)]
    if cat2_selecionado:
        df_filtrado = df_filtrado[df_filtrado['CATEGORIA_2'].isin(cat2_selecionado)]
    if cat3_selecionado:
        df_filtrado = df_filtrado[df_filtrado['CATEGORIA_3'].isin(cat3_selecionado)]
    if status_selecionado:
        df_filtrado = df_filtrado[df_filtrado['STATUS_DESC'].isin(status_selecionado)]
    if tipo_selecionado:
        df_filtrado = df_filtrado[df_filtrado['TIPO_CHAMADO'].isin(tipo_selecionado)]
    if criticidade_selecionado:
        df_filtrado = df_filtrado[df_filtrado['CRITICIDADE_DESC'].isin(criticidade_selecionado)]

    # Filtros de data
    if aplicar_criacao and start_date_criacao and end_date_criacao and 'DATA_CRIACAO' in df_filtrado.columns:
        df_filtrado['DATA_CRIACAO'] = pd.to_datetime(df_filtrado['DATA_CRIACAO'], errors='coerce')
        mask_criacao = (
            (df_filtrado['DATA_CRIACAO'].dt.date >= start_date_criacao) &
            (df_filtrado['DATA_CRIACAO'].dt.date <= end_date_criacao)
        )
        df_filtrado = df_filtrado[mask_criacao]

    if aplicar_resolucao and start_date_resolucao and end_date_resolucao and 'DATA_RESOLUCAO' in df_filtrado.columns:
        df_filtrado['DATA_RESOLUCAO'] = pd.to_datetime(df_filtrado['DATA_RESOLUCAO'], errors='coerce')
        mask_resolucao = (
            (df_filtrado['DATA_RESOLUCAO'].dt.date >= start_date_resolucao) &
            (df_filtrado['DATA_RESOLUCAO'].dt.date <= end_date_resolucao)
        )
        df_filtrado = df_filtrado[mask_resolucao]

    if df_filtrado.empty:
        st.warning(get_error_message("NO_DATA"))
        st.stop()

    # == Cálculo dos KPIs ==
    total_criados = len(df_filtrado)
    total_resolvidos = len(df_filtrado[df_filtrado['STATUS_DESC'].isin(status_resolvidos)])
    backlogs_abertos = len(df_filtrado[~df_filtrado['STATUS_DESC'].isin(status_finalizados)])
    taxa_absorcao = (total_resolvidos / total_criados * 100) if total_criados > 0 else 0

    # == Exibição dos KPIs ==
    st.subheader("Indicadores de Performance")

    st.markdown("""
        <style>
            [data-testid="stMetric"] svg,
            [data-testid="stMetricValue"] svg,
            [data-testid="stMetricLabel"] svg { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    def card_kpi(titulo, valor, cor):
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, {cor}, {cor}cc);
                        padding: 20px; border-radius: 15px; text-align: center;
                        color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);'>
                <h2 style='margin: 0; font-size: 32px;'>{valor}</h2>
                <p style='margin: 8px 0 0 0;'>{titulo}</p>
            </div>
        """, unsafe_allow_html=True)

    with col1:
        card_kpi("Total Criados", f"{total_criados:,}".replace(",", "."), CORES["roxo"])
    with col2:
        card_kpi("Total Resolvidos", f"{total_resolvidos:,}".replace(",", "."), CORES["roxo"])
    with col3:
        card_kpi("Backlogs Abertos", f"{backlogs_abertos:,}".replace(",", "."), CORES["verde_escuro"])
    with col4:
        card_kpi("Taxa de Absorção", f"{taxa_absorcao:.2f}%".replace('.', ','), CORES["roxo_claro"])

    st.markdown("---")
    st.markdown(f"### Registros encontrados: {total_criados:,}".replace(",", "."))

    # == Preparação da tabela ==
    colunas_exibir = {
        'CHAMADOS': 'Chamado',
        'TITULO': 'Título',
        'STATUS_DESC': 'Status',
        'TIPO_CHAMADO': 'Tipo',
        'CLIENTE': 'Cliente',
        'DESIGNADO': 'Designado',
        'FILA': 'Fila',
        'REQ': 'Requisição',
        'CATEGORIA_1': 'Categoria 1',
        'CATEGORIA_2': 'Categoria 2',
        'CATEGORIA_3': 'Categoria 3',
        'CRITICIDADE_DESC': 'Criticidade',
        'DATA_CRIACAO': 'Data Criação',
        'DATA_INICIO_ATENDIMENTO': 'Início Atendimento',
        'DATA_RESOLUCAO': 'Data Resolução',
        'TEMPO_SOLUCAO': 'Tempo Solução',
        'QTDE_ATIVIDADES': 'Qtd Atividades'
    }

    colunas_orig = [c for c in colunas_exibir if c in df_filtrado.columns]
    df_exibicao = df_filtrado[colunas_orig].copy()

    # == Adiciona Categoria 3 se não existir ==
    if 'CATEGORIA_3' not in df_exibicao.columns:
        if 'CATEGORIZATION_TIER_3' in df_filtrado.columns:
            df_exibicao['CATEGORIA_3'] = df_filtrado['CATEGORIZATION_TIER_3']
        elif 'CAT_OPERACIONAL_3' in df_filtrado.columns:
            df_exibicao['CATEGORIA_3'] = df_filtrado['CAT_OPERACIONAL_3']

    # == Calcula Qtd Atividades ==
    if 'QTDE_ATIVIDADES' not in df_exibicao.columns:
        if 'Gabriel_QTD_ATIV_EXEC' in df_filtrado.columns:
            df_exibicao['QTDE_ATIVIDADES'] = (
                pd.to_numeric(df_filtrado['Gabriel_QTD_ATIV_EXEC'], errors='coerce')
                .fillna(0)
                .astype(int)
            )
        elif 'ABYDOS_TASKS_GENERATED' in df_filtrado.columns:
            df_exibicao['QTDE_ATIVIDADES'] = (
                pd.to_numeric(df_filtrado['ABYDOS_TASKS_GENERATED'], errors='coerce')
                .fillna(0)
                .astype(int)
            )
        else:
            df_exibicao['QTDE_ATIVIDADES'] = 0
            campos_eventos = [
                'DATA_RESPOSTA_RAW',
                'DATA_INICIO_ATENDIMENTO',
                'ULTIMA_MODIFICACAO',
                'DATA_RESOLUCAO',
                'DATA_DESIGNACAO'
            ]
            for campo in campos_eventos:
                if campo in df_filtrado.columns:
                    df_exibicao['QTDE_ATIVIDADES'] += df_filtrado[campo].notna().astype(int)
            
            if 'TIPO_CHAMADO' in df_exibicao.columns:
                mask_wo = df_exibicao['TIPO_CHAMADO'] == 'WO'
                if mask_wo.any():
                    if 'ACTUAL_START_DATE' in df_filtrado.columns:
                        df_exibicao.loc[mask_wo, 'QTDE_ATIVIDADES'] += df_filtrado.loc[mask_wo, 'ACTUAL_START_DATE'].notna().astype(int)
                    if 'ACTUAL_END_DATE' in df_filtrado.columns:
                        df_exibicao.loc[mask_wo, 'QTDE_ATIVIDADES'] += df_filtrado.loc[mask_wo, 'ACTUAL_END_DATE'].notna().astype(int)

    # == Garante DATA_INICIO_ATENDIMENTO ==
    if 'DATA_INICIO_ATENDIMENTO' in df_exibicao.columns:
        if 'DATA_CRIACAO' in df_exibicao.columns:
            mask = df_exibicao['DATA_INICIO_ATENDIMENTO'] == df_exibicao['DATA_CRIACAO']
            if mask.any():
                if 'FIRSTWIPDATE' in df_filtrado.columns:
                    df_exibicao.loc[mask, 'DATA_INICIO_ATENDIMENTO'] = df_filtrado.loc[mask, 'FIRSTWIPDATE']
                elif 'DATA_SISTEMA' in df_filtrado.columns:
                    df_exibicao.loc[mask, 'DATA_INICIO_ATENDIMENTO'] = df_filtrado.loc[mask, 'DATA_SISTEMA']

    # == Formatação das datas ==
    for col in ['DATA_CRIACAO', 'DATA_RESOLUCAO', 'DATA_INICIO_ATENDIMENTO']:
        if col in df_exibicao.columns:
            df_exibicao[col] = pd.to_datetime(df_exibicao[col], errors='coerce')
            df_exibicao[col] = df_exibicao[col].dt.strftime('%d/%m/%Y %H:%M:%S')
            df_exibicao[col] = df_exibicao[col].fillna('N/A')

    # == Renomeia colunas ==
    novos_nomes = []
    for col in df_exibicao.columns:
        if col in colunas_exibir:
            novos_nomes.append(colunas_exibir[col])
        else:
            novos_nomes.append(col)
    df_exibicao.columns = novos_nomes

    # == Ordena colunas ==
    ordem_desejada = [
        'Chamado', 'Título', 'Status', 'Tipo', 'Cliente', 'Designado',
        'Fila', 'Requisição', 'Categoria 1', 'Categoria 2', 'Categoria 3',
        'Criticidade', 'Data Criação', 'Início Atendimento', 'Data Resolução',
        'Tempo Solução', 'Qtd Atividades'
    ]
    colunas_existentes = [col for col in ordem_desejada if col in df_exibicao.columns]
    df_exibicao = df_exibicao[colunas_existentes]

    # == Exibição da tabela com paginação ==
    page_size = 100
    total_pages = max(1, (len(df_exibicao) - 1) // page_size + 1)
    page_number = st.number_input("Página", min_value=1, max_value=total_pages, value=1)
    start_idx = (page_number - 1) * page_size
    st.dataframe(df_exibicao.iloc[start_idx:start_idx + page_size], use_container_width=True)
    st.caption(f"Página {page_number} de {total_pages}")

    # == Download CSV ==
    if not df_exibicao.empty:
        try:
            csv_data = df_exibicao.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            nome_arquivo = f"BMCVIEW_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            st.download_button(
                label="⬇ Download CSV",
                data=csv_data,
                file_name=nome_arquivo,
                mime="text/csv",
                use_container_width=True
            )
            st.caption(f"Exportando {len(df_exibicao):,} registros".replace(",", "."))
        except Exception as e:
            st.error(f"Erro ao gerar CSV: {str(e)}")
    else:
        st.info("Não há dados para exportar com os filtros atuais.")

    st.markdown("---")
    st.caption(f"Dados atualizados em: {ultima_atualizacao.strftime('%d/%m/%Y %H:%M:%S')}")

# == Verificação de validade do usuário ==
def is_user_still_valid():
    if not st.session_state.authenticated:
        return False
    if not st.session_state.user_username:
        return False
    users = auth.listar_usuarios()
    if st.session_state.user_username not in users:
        return False
    user_data = users[st.session_state.user_username]
    if not user_data.get('ativo', False):
        return False
    if not user_data.get('autorizado', False):
        return False
    if st.session_state.login_time:
        try:
            if datetime.now() - st.session_state.login_time > timedelta(hours=24):
                return False
        except Exception:
            return False
    return True

# == Execução principal ==
if st.session_state.authenticated:
    if is_user_still_valid():
        show_dashboard()
        st.stop()
    else:
        token = st.session_state.get("_session_token")
        if token:
            delete_session_token(token)
        st.session_state.authenticated = False
        st.session_state.user_username = None
        st.session_state.user_name = None
        st.session_state.login_time = None
        st.session_state._session_token = None
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.warning("Sua sessão expirou ou você foi desativado. Faça login novamente.")
        show_login()
else:
    show_login()