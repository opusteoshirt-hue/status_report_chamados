# pages/admin.py
import streamlit as st
import sys
import os
import pickle
import pandas as pd
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta
import unicodedata

# Ajusta o path do sistema
sys.path.insert(0, str(Path(__file__).parent.parent))
from auth_manager import AuthManager
from services.ad_service import ADService
from error_messages import get_error_message

# ==================== CORREÇÃO DE TEXTO ====================
def corrigir_texto(texto):
    """Corrige caracteres problemáticos no texto (mojibake)"""
    if not isinstance(texto, str):
        return texto
    
    # Dicionário de correções para caracteres comuns com problema de encoding
    correcoes = {
        'Ã£': 'ã', 'Ã¢': 'â', 'Ã¤': 'ä', 'Ã¡': 'á', 'Ã ': 'à',
        'Ã©': 'é', 'Ãª': 'ê', 'Ã¨': 'è', 'Ã«': 'ë', 'Ã­': 'í',
        'Ã®': 'î', 'Ã¬': 'ì', 'Ã¯': 'ï', 'Ã³': 'ó', 'Ã´': 'ô',
        'Ã¶': 'ö', 'Ã²': 'ò', 'Ãº': 'ú', 'Ã»': 'û', 'Ã¹': 'ù',
        'Ã¼': 'ü', 'Ã§': 'ç', 'Ãƒ': 'ã', 'Ã‚': 'â', 'Ã•': 'õ',
        'Ãµ': 'õ', 'Â': '', 'Ã': 'á', 'õ': 'õ', 'Ã£o': 'ão',
        'Ã§Ã£o': 'ção', 'Ã£o': 'ão', 'Ãµes': 'ões', 'Ã¡': 'á',
        'produÃ§Ã£o': 'produção', 'implantaÃ§Ã£o': 'implantação',
        'ÃƒÂ£': 'ã', 'ÃƒÂ¡': 'á', 'ÃƒÂ©': 'é', 'ÃƒÂ­': 'í',
        'ÃƒÂ³': 'ó', 'ÃƒÂº': 'ú', 'ÃƒÂ§': 'ç', 'ÃƒÂ£o': 'ão',
        'ÃƒÂ§ÃƒÂ£o': 'ção', 'ÃƒÂµes': 'ões', 'ÃƒÂ¡': 'á',
        'ÃƒÂ­': 'í', 'ÃƒÂ³': 'ó', 'ÃƒÂº': 'ú'
    }
    
    for problema, correcao in correcoes.items():
        texto = texto.replace(problema, correcao)
    
    return texto

# ==================== FUNÇÃO PARA CONVERTER CSV COM CORREÇÃO ====================
def converter_csv_com_correcao(df):
    """Converte DataFrame para CSV com correção de caracteres e encoding UTF-8"""
    if df.empty:
        return "".encode('utf-8-sig')
    
    df_copia = df.copy()
    # Aplica correção em todas as colunas de string
    for col in df_copia.select_dtypes(include=['object']).columns:
        df_copia[col] = df_copia[col].apply(lambda x: corrigir_texto(x) if isinstance(x, str) else x)
    
    return df_copia.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

# ==================== CONTROLE DE SESSAO ====================
auth = AuthManager()
ad_service = ADService()
admin_padrao = auth.get_admin_user()

# Inicializa chaves essenciais
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_username" not in st.session_state:
    st.session_state.user_username = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None

def verificar_sessao_admin():
    """Verifica se o usuario esta autenticado e e admin - SEM usar URL"""
    if not st.session_state.authenticated:
        return False
    if not st.session_state.user_username:
        return False
    if not auth.is_admin(st.session_state.user_username):
        return False
    return True

# ==================== BARREIRA DE SEGURANCA ====================
if not verificar_sessao_admin():
    st.set_page_config(page_title="Acesso Negado", layout="centered")
    st.error("Acesso negado. Esta pagina e restrita para administradores.")
    if st.button("Voltar para o Dashboard", use_container_width=True):
        st.switch_page("app.py")
    st.stop()

# ==================== CONFIGURAR PAGINA ====================
st.set_page_config(page_title="Admin - Gerenciamento de Usuarios", layout="wide")

# Oculta o menu de navegacao nativo do Streamlit
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none !important;}
    </style>
""", unsafe_allow_html=True)

# Botao voltar e Notificacoes
col_back, col_notif = st.columns([1, 4])
with col_back:
    if st.button("← Voltar ao Dashboard"):
        st.switch_page("app.py")

with col_notif:
    unread_count = auth.get_unread_count()
    if unread_count > 0:
        with st.popover(f"Notificacoes ({unread_count})"):
            notifications = auth.get_notifications(unread_only=True)
            for notif in notifications:
                with st.container():
                    tipo_texto = {
                        "success": "[OK]",
                        "warning": "[ATENCAO]",
                        "error": "[ERRO]",
                        "info": "[INFO]"
                    }.get(notif.get("type", "info"), "[NOTIF]")
                    st.markdown(f"**{tipo_texto}** `{notif['timestamp']}`")
                    st.write(notif['message'])
                    if st.button("Marcar como lida", key=f"read_{notif['id']}"):
                        auth.mark_notification_read(notif['id'])
                        st.rerun()
                    st.divider()
            if st.button("Marcar todas como lidas"):
                auth.mark_all_notifications_read()
                st.rerun()

st.title("Painel Administrativo")
st.markdown("---")

# ==================== CARREGA FILAS DO CACHE ====================
@st.cache_data(ttl=3600)
def load_filas_disponiveis():
    cache = Path("dados_cache.pkl")
    if cache.exists():
        with open(cache, "rb") as f:
            df = pickle.load(f)
        if 'FILA' in df.columns:
            return sorted(df['FILA'].dropna().unique().tolist())
    return []

filas_disponiveis = load_filas_disponiveis()

# ==================== TABS ====================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Autorizar Usuarios",
    "Usuarios Ativos",
    "Usuarios Inativos",
    "Permissoes de Filas",
    "Estatisticas AD",
    "Configuracoes"
])

# ==================== FUNCAO PARA FORMATAR DATA BRASILIA ====================
def formatar_data_brasilia(data_original):
    from datetime import timezone, timedelta
    if not data_original or data_original == 'Nunca' or data_original == 'N/A':
        return 'Nunca'
    
    try:
        if isinstance(data_original, str):
            formatos = [
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
                '%d/%m/%Y %H:%M:%S'
            ]
            for fmt in formatos:
                try:
                    data_original = datetime.strptime(data_original, fmt)
                    break
                except ValueError:
                    continue
        
        if isinstance(data_original, datetime):
            brasilia_offset = timezone(timedelta(hours=-3))
            if data_original.tzinfo is None:
                data_utc = data_original.replace(tzinfo=timezone.utc)
            else:
                data_utc = data_original.astimezone(timezone.utc)
            data_brasilia = data_utc.astimezone(brasilia_offset)
            return data_brasilia.strftime('%d/%m/%Y %H:%M:%S')
        
        return str(data_original)
    except Exception:
        return str(data_original) if data_original else 'Nunca'

# ==================== FUNCAO PARA SINCRONIZAR AD ====================
def sincronizar_ad():
    """Sincroniza todos os usuarios com o AD."""
    with st.spinner("Sincronizando com o Active Directory..."):
        users = auth.listar_usuarios()
        sincronizados = 0
        erros = 0
        
        for username in users:
            if username != admin_padrao:
                try:
                    success = auth.sync_ad_status_for_user(username)
                    if success:
                        sincronizados += 1
                    else:
                        erros += 1
                except Exception:
                    erros += 1
        
        st.success(f"Sincronizacao concluida: {sincronizados} atualizados, {erros} erros.")
        st.rerun()

# ==================== TAB 1 - AUTORIZAR USUARIOS ====================
with tab1:
    st.subheader("Autorizar Usuarios do Active Directory")
    st.caption("Pesquise usuarios no AD, selecione na tabela e autorize o acesso ao sistema.")

    # Estado para controlar a abertura do expander
    if "abrir_confirmacao" not in st.session_state:
        st.session_state.abrir_confirmacao = False
    if "dados_confirmacao" not in st.session_state:
        st.session_state.dados_confirmacao = None

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Sincronizar com Active Directory", use_container_width=True):
            with st.spinner("Buscando todos os usuarios do AD..."):
                df_ad = ad_service.get_all_users_from_ad(force_refresh=True)
                if df_ad.empty:
                    st.error("Nenhum usuario encontrado no AD. Verifique a conexao.")
                else:
                    st.success(f"Carregados {len(df_ad)} usuarios do AD")
                st.rerun()

    st.markdown("---")

    search_term = st.text_input(
        "Buscar usuario por nome, username ou email:",
        placeholder="Ex: nome, usuario.ad, ou email",
        key="search_user_ad"
    )

    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        mostrar_inativos_ad = st.checkbox("Mostrar usuarios inativos no AD", value=False)
    with col_filtro2:
        status_filtro = st.selectbox(
            "Status no Sistema", 
            ["Todos", "Nao Autorizados", "Ja Autorizados", "Inativos no AD (Bloqueados)"]
        )

    if search_term:
        with st.spinner("Buscando..."):
            df_results = ad_service.search_users(search_term)

        if df_results.empty:
            st.warning(f"Nenhum usuario encontrado com o termo '{search_term}'.")
        else:
            if not mostrar_inativos_ad:
                df_results = df_results[df_results['ativo_no_ad'] == True]

            users_sistema = auth.listar_usuarios()
            
            def calcular_status_sistema(row):
                username = row['username']
                if not row['ativo_no_ad']:
                    return "Inativo no AD"
                elif username in users_sistema and users_sistema[username].get('autorizado', False) and users_sistema[username].get('ativo', True):
                    return "Autorizado"
                else:
                    return "Nao Autorizado"

            df_results['status_sistema'] = df_results.apply(calcular_status_sistema, axis=1)

            if status_filtro == "Nao Autorizados":
                df_results = df_results[df_results['status_sistema'] == "Nao Autorizado"]
            elif status_filtro == "Ja Autorizados":
                df_results = df_results[df_results['status_sistema'] == "Autorizado"]
            elif status_filtro == "Inativos no AD (Bloqueados)":
                df_results = df_results[df_results['status_sistema'] == "Inativo no AD"]

            if df_results.empty:
                st.warning("Nenhum usuario encontrado com os filtros selecionados.")
            else:
                st.success(f"Encontrados {len(df_results)} usuarios:")

                df_exibicao = df_results.copy()
                
                if 'categoria_usuario' not in df_exibicao.columns:
                    df_exibicao['categoria_usuario'] = 'Servidor'

                df_exibicao['Selecionar'] = False

                colunas_exibir = {
                    'Selecionar': 'Selecionar',
                    'nome_completo': 'Nome Completo',
                    'username': 'Usuario AD',
                    'email': 'Email',
                    'categoria_usuario': 'Categoria',
                    'status_ad': 'Status AD',
                    'status_sistema': 'Status Sistema'
                }

                colunas_orig = [c for c in colunas_exibir if c in df_exibicao.columns]
                df_tabela = df_exibicao[colunas_orig].copy()
                df_tabela.columns = [colunas_exibir[c] for c in colunas_orig]

                edited_df = st.data_editor(
                    df_tabela,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn(
                            "Autorizar",
                            default=False,
                            help="Marque para autorizar este usuario"
                        ),
                        "Nome Completo": st.column_config.Column("Nome Completo", width="large"),
                        "Usuario AD": st.column_config.Column("Usuario AD", width="medium"),
                        "Email": st.column_config.Column("Email", width="large"),
                        "Categoria": st.column_config.Column("Categoria", width="medium"),
                        "Status AD": st.column_config.Column("Status AD", width="small"),
                        "Status Sistema": st.column_config.Column("Status Sistema", width="medium")
                    },
                    disabled=["Nome Completo", "Usuario AD", "Email", "Categoria", "Status AD", "Status Sistema"]
                )

                usuarios_selecionados = edited_df[
                    (edited_df['Selecionar'] == True) & 
                    (edited_df['Status Sistema'] == "Nao Autorizado")
                ]

                if not usuarios_selecionados.empty:
                    st.markdown("---")
                    st.subheader("Autorizar Usuarios Selecionados")
                    
                    st.write(f"**{len(usuarios_selecionados)} usuarios selecionados para autorizar:**")
                    
                    for _, row in usuarios_selecionados.iterrows():
                        st.write(f"- {row['Nome Completo']} ({row['Usuario AD']}) - {row['Categoria']}")

                    col_conf1, col_conf2 = st.columns(2)
                    with col_conf1:
                        tipo_acesso_lote = st.selectbox("Nivel de Acesso:", ["Usuario", "Admin"], key="tipo_acesso_autorizar")
                    with col_conf2:
                        if filas_disponiveis:
                            filas_lote = st.multiselect(
                                "Filas de Trabalho:",
                                options=filas_disponiveis,
                                default=[],
                                help="Selecione uma ou mais filas que este usuario podera visualizar",
                                key="filas_autorizar"
                            )
                            if tipo_acesso_lote == "Admin":
                                st.info("Administradores tem acesso a todas as filas automaticamente.")
                            elif not filas_lote:
                                st.warning("Selecione pelo menos uma fila para usuarios comuns.")
                        else:
                            filas_lote = []
                            st.warning("Nenhuma fila disponivel para selecao.")

                    # ============================================================
                    # BOTAO PARA INICIAR AUTORIZACAO
                    # ============================================================
                    if st.button("Autorizar Selecionados", type="primary", use_container_width=True):
                        if tipo_acesso_lote != "Admin" and not filas_lote:
                            st.error("Por favor, selecione pelo menos uma fila para usuarios comuns.")
                        else:
                            st.session_state.dados_confirmacao = {
                                "usuarios": usuarios_selecionados.to_dict('records'),
                                "tipo": tipo_acesso_lote,
                                "filas": filas_lote,
                                "df_results": df_results
                            }
                            st.session_state.abrir_confirmacao = True

                    # ============================================================
                    # EXPANDER DE CONFIRMACAO
                    # ============================================================
                    if st.session_state.abrir_confirmacao and st.session_state.dados_confirmacao:
                        dados = st.session_state.dados_confirmacao
                        qtde = len(dados["usuarios"])
                        
                        with st.expander("Confirmar Autorizacao", expanded=True):
                            st.warning(f"Voce tem certeza que deseja autorizar {qtde} usuario(s)?")
                            
                            col_confirm1, col_confirm2 = st.columns(2)
                            with col_confirm1:
                                if st.button("Sim, autorizar", use_container_width=True, key="executar_autorizacao_expander"):
                                    with st.spinner("Autorizando usuarios..."):
                                        for user_data in dados["usuarios"]:
                                            username = user_data['Usuario AD']
                                            user_row = dados["df_results"][dados["df_results"]['username'] == username].iloc[0]
                                            
                                            # 1. REMOVE DA LISTA DE PENDENTES (se existir)
                                            pending_users = auth.listar_usuarios_pendentes()
                                            if username in pending_users:
                                                del pending_users[username]
                                                auth._save_pending_users(pending_users)
                                            
                                            # 2. ADICIONA DIRETAMENTE AO USERS.JSON
                                            success, msg = auth.adicionar_usuario_manual(
                                                username=username,
                                                nome=user_row['nome_completo'],
                                                email=user_row['email'] if user_row['email'] else None,
                                                filas=dados["filas"] if dados["tipo"] != "Admin" else ["*"],
                                                categoria=user_row['categoria_usuario']
                                            )
                                            
                                            # 3. SE FOR ADMIN, ALTERA O TIPO
                                            if dados["tipo"] == "Admin" and success:
                                                auth.alterar_tipo_usuario(username, "admin")
                                            
                                            # 4. NOTIFICACAO
                                            if success:
                                                auth.add_notification("success", f"Usuario autorizado: {username} ({user_row['nome_completo']})")
                                            else:
                                                auth.add_notification("error", f"Falha ao autorizar {username}: {msg}")
                                            
                                    # Reseta o estado
                                    st.session_state.abrir_confirmacao = False
                                    st.session_state.dados_confirmacao = None
                                    st.success(f"{qtde} usuarios autorizados com sucesso!")
                                    st.rerun()
                            
                            with col_confirm2:
                                if st.button("Cancelar", use_container_width=True, key="cancelar_autorizacao_expander"):
                                    st.session_state.abrir_confirmacao = False
                                    st.session_state.dados_confirmacao = None
                                    st.info("Operacao cancelada.")
                                    st.rerun()

                else:
                    nao_autorizados_count = len(edited_df[edited_df['Status Sistema'] == "Nao Autorizado"])
                    if nao_autorizados_count > 0:
                        st.info(f"{nao_autorizados_count} usuarios nao autorizados disponiveis. Marque a coluna 'Selecionar' para autorizar.")
                    else:
                        st.info("Nenhum usuario nao autorizado encontrado com os filtros selecionados.")

                st.markdown("---")
                
                df_download = edited_df.drop(columns=['Selecionar'], errors='ignore')
                st.download_button(
                    "Download CSV com Resultados",
                    data=converter_csv_com_correcao(df_download),
                    file_name=f"usuarios_ad_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

    else:
        st.info("Digite um termo de busca para encontrar usuarios no Active Directory")

# ==================== TAB 2 - USUARIOS ATIVOS ====================
with tab2:
    st.subheader("Usuarios Ativos")
    st.caption("Usuarios autorizados que estao ativos no sistema.")

    all_users = auth.listar_usuarios()
    
    with st.spinner("Sincronizando dados com Active Directory..."):
        df_ad_all = ad_service.get_all_users_from_ad()
    
    ad_data = {}
    if not df_ad_all.empty:
        for _, row in df_ad_all.iterrows():
            ad_data[row['username']] = row

    usuarios_ativos = {
        k: v for k, v in all_users.items()
        if v.get("ativo", True) and v.get("autorizado", True)
    }

    if not usuarios_ativos:
        st.info("Nenhum usuario ativo.")
    else:
        dados_tabela = []
        for username, user_data in usuarios_ativos.items():
            ad_info = ad_data.get(username, {})
            categoria = ad_info.get('categoria_usuario', user_data.get('categoria_ad', 'Servidor'))
            status_ad = ad_info.get('status_ad', 'ATIVO')
            status_ad_texto = "Ativo" if status_ad == 'ATIVO' else "Inativo" if status_ad == 'INATIVO' else status_ad
            
            dados_tabela.append({
                "Nome": user_data.get('nome', username),
                "Usuario AD": username,
                "Email": ad_info.get('email', user_data.get('email', 'N/A')),
                "Tipo": "Admin" if user_data.get('tipo') == 'admin' else "Usuario",
                "Categoria": categoria,
                "Status AD": status_ad_texto,
                "Ultimo Acesso": formatar_data_brasilia(user_data.get('ultimo_acesso', 'Nunca')),
                "Qtd Filas": len(user_data.get('filas_autorizadas', []))
            })
        
        df_ativos = pd.DataFrame(dados_tabela)
        st.dataframe(df_ativos, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Gerenciar Usuario")

        usuario_selecionado = st.selectbox(
            "Selecione um usuario para gerenciar:",
            options=list(usuarios_ativos.keys()),
            format_func=lambda x: f"{usuarios_ativos[x].get('nome', x)} ({x})"
        )

        if usuario_selecionado:
            tipo_atual = usuarios_ativos[usuario_selecionado].get('tipo', 'usuario')
            novo_tipo = "usuario" if tipo_atual == "admin" else "admin"
            
            ad_info_atual = ad_data.get(usuario_selecionado, {})
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"Alterar tipo: {tipo_atual.upper()} -> {novo_tipo.upper()}", use_container_width=True):
                    st.warning(f"Voce tem certeza que deseja alterar o tipo de {usuario_selecionado} para {novo_tipo.upper()}?")
                    col_confirm1, col_confirm2 = st.columns(2)
                    with col_confirm1:
                        if st.button("Sim, alterar", use_container_width=True):
                            success, msg = auth.alterar_tipo_usuario(usuario_selecionado, novo_tipo)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_confirm2:
                        if st.button("Cancelar", use_container_width=True):
                            st.info("Operacao cancelada.")
                            st.rerun()
            with col2:
                if st.button("Inativar", use_container_width=True):
                    st.warning(f"Voce tem certeza que deseja inativar o usuario {usuario_selecionado}?")
                    col_confirm1, col_confirm2 = st.columns(2)
                    with col_confirm1:
                        if st.button("Sim, inativar", use_container_width=True):
                            success, msg = auth.inativar_usuario(usuario_selecionado)
                            if success:
                                st.warning(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_confirm2:
                        if st.button("Cancelar", use_container_width=True):
                            st.info("Operacao cancelada.")
                            st.rerun()
            with col3:
                if st.button("Sincronizar AD", use_container_width=True):
                    auth.sync_ad_status_for_user(usuario_selecionado)
                    st.success("Sincronizado com AD!")
                    st.rerun()
            
            with st.expander("Informacoes do Active Directory"):
                col_ad1, col_ad2 = st.columns(2)
                with col_ad1:
                    st.write(f"**Status AD:** {ad_info_atual.get('status_ad', 'N/A')}")
                    st.write(f"**Categoria:** {ad_info_atual.get('categoria_usuario', 'N/A')}")
                with col_ad2:
                    st.write(f"**Email:** {ad_info_atual.get('email', 'N/A')}")
                    st.write(f"**Nome no AD:** {ad_info_atual.get('nome_completo', 'N/A')}")

# ==================== TAB 3 - USUARIOS INATIVOS ====================
with tab3:
    st.subheader("Usuarios Inativos")

    all_users = auth.listar_usuarios()

    usuarios_inativos = {
        k: v for k, v in all_users.items()
        if not v.get("ativo", True) and k != admin_padrao
    }

    if not usuarios_inativos:
        st.info("Nenhum usuario inativo.")
    else:
        for username, user_data in usuarios_inativos.items():
            with st.container():
                col_info, col_acoes = st.columns([2, 1])
                with col_info:
                    st.markdown(f"**{user_data.get('nome', username)}**")
                    st.write(f"Usuario AD: `{username}`")
                    st.write(f"Inativado em: {user_data.get('inativado_em', 'N/A')}")
                    if user_data.get('inativado_por_ad', False):
                        st.warning("Inativado automaticamente por estar inativo no AD")

                    ad_status = auth.check_ad_status(username)
                    if ad_status['ativo_no_ad']:
                        st.success(f"Status AD atual: {ad_status['status_ad']}")
                    else:
                        st.error(f"Status AD atual: {ad_status['status_ad']}")

                with col_acoes:
                    if st.button("Reativar", key=f"reativar_{username}"):
                        st.warning(f"Voce tem certeza que deseja reativar o usuario {username}?")
                        col_confirm1, col_confirm2 = st.columns(2)
                        with col_confirm1:
                            if st.button("Sim, reativar", key=f"confirm_reativar_{username}", use_container_width=True):
                                success, msg = auth.ativar_usuario(username)
                                if success:
                                    st.success(msg)
                                else:
                                    st.error(msg)
                                st.rerun()
                        with col_confirm2:
                            if st.button("Cancelar", key=f"cancel_reativar_{username}", use_container_width=True):
                                st.info("Operacao cancelada.")
                                st.rerun()

                    if st.button("Excluir", key=f"excluir_inativo_{username}"):
                        st.warning(f"Voce tem certeza que deseja EXCLUIR PERMANENTEMENTE o usuario {username}? Esta acao nao pode ser desfeita.")
                        col_confirm1, col_confirm2 = st.columns(2)
                        with col_confirm1:
                            if st.button("Sim, excluir", key=f"confirm_excluir_{username}", use_container_width=True):
                                success, msg = auth.excluir_usuario(username)
                                if success:
                                    st.warning(msg)
                                else:
                                    st.error(msg)
                                st.rerun()
                        with col_confirm2:
                            if st.button("Cancelar", key=f"cancel_excluir_{username}", use_container_width=True):
                                st.info("Operacao cancelada.")
                                st.rerun()

                st.divider()

# ==================== TAB 4 - PERMISSOES DE FILAS ====================
with tab4:
    st.subheader("Permissoes de Filas")
    st.caption("Atribua quais filas cada usuario pode visualizar.")

    if "modo_confirmacao_filas" not in st.session_state:
        st.session_state.modo_confirmacao_filas = False
    if "usuario_filas" not in st.session_state:
        st.session_state.usuario_filas = None
    if "filas_selecionadas" not in st.session_state:
        st.session_state.filas_selecionadas = []
    if "acao_filas" not in st.session_state:
        st.session_state.acao_filas = None

    if not filas_disponiveis:
        st.warning("Nenhuma fila disponivel. Execute o dashboard principal primeiro para carregar o cache.")
    else:
        with st.spinner("Carregando dados do Active Directory..."):
            df_ad_all = ad_service.get_all_users_from_ad()
        
        ad_data = {}
        if not df_ad_all.empty:
            for _, row in df_ad_all.iterrows():
                ad_data[row['username']] = row

        all_users = auth.listar_usuarios()
        admin_padrao = auth.get_admin_user()

        usuarios_comuns = {}
        for k, v in all_users.items():
            if k != admin_padrao and v.get('autorizado', False):
                if not auth.is_admin(k):
                    usuarios_comuns[k] = v

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Filas disponiveis", len(filas_disponiveis))
        with col2:
            st.metric("Usuarios comuns", len(usuarios_comuns))

        admins_count = 0
        for k, v in all_users.items():
            if k != admin_padrao and auth.is_admin(k):
                admins_count += 1
        with col3:
            st.metric("Administradores", admins_count)

        st.markdown("---")

        if not usuarios_comuns:
            st.info("Nenhum usuario comum autorizado encontrado.")
        else:
            usuario_sel = st.selectbox(
                "Selecione o usuario:",
                options=list(usuarios_comuns.keys()),
                format_func=lambda x: f"{usuarios_comuns[x].get('nome', x)} ({x})"
            )

            if usuario_sel:
                user_data = usuarios_comuns[usuario_sel]
                filas_atuais = user_data.get("filas_autorizadas", [])
                
                if filas_atuais == ["*"]:
                    filas_atuais_exibicao = []
                else:
                    filas_atuais_exibicao = filas_atuais
                
                ad_info = ad_data.get(usuario_sel, {})
                categoria_ad = ad_info.get('categoria_usuario', user_data.get('categoria_ad', 'Servidor'))
                status_ad = ad_info.get('status_ad', 'ATIVO')
                status_ad_texto = "Ativo" if status_ad == "ATIVO" else "Inativo" if status_ad == "INATIVO" else status_ad

                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    st.info(f"**Nome:** {user_data.get('nome', usuario_sel)}")
                with col_info2:
                    st.info(f"**Categoria AD:** {categoria_ad}")
                with col_info3:
                    st.info(f"**Status AD:** {status_ad_texto}")

                st.markdown("---")

                if filas_atuais == ["*"]:
                    st.warning("Este usuario tem acesso a TODAS as filas (configuracao de administrador).")
                    st.info("Para editar, selecione filas especificas abaixo. O acesso a todas as filas sera removido.")
                elif filas_atuais:
                    st.success(f"Acesso a {len(filas_atuais)} fila(s)")
                    with st.expander(f"Filas atuais ({len(filas_atuais)})"):
                        for fila in sorted(filas_atuais):
                            st.write(f"- {fila}")
                else:
                    st.warning("Sem filas atribuidas")

                st.markdown("---")
                st.markdown("### Editar permissoes")
                
                filas_sel = st.multiselect(
                    "Selecione as filas autorizadas:",
                    options=filas_disponiveis,
                    default=filas_atuais_exibicao,
                    help="Selecione as filas que este usuario podera visualizar"
                )

                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button("Salvar", use_container_width=True, type="primary"):
                        st.session_state.modo_confirmacao_filas = True
                        st.session_state.usuario_filas = usuario_sel
                        st.session_state.filas_selecionadas = filas_sel
                        st.session_state.acao_filas = "salvar"
                        st.rerun()
                with col_btn2:
                    if st.button("Limpar Todas", use_container_width=True):
                        st.session_state.modo_confirmacao_filas = True
                        st.session_state.usuario_filas = usuario_sel
                        st.session_state.filas_selecionadas = []
                        st.session_state.acao_filas = "limpar"
                        st.rerun()
                with col_btn3:
                    if st.button("Selecionar Todas", use_container_width=True):
                        st.session_state.modo_confirmacao_filas = True
                        st.session_state.usuario_filas = usuario_sel
                        st.session_state.filas_selecionadas = filas_disponiveis
                        st.session_state.acao_filas = "selecionar_todas"
                        st.rerun()

                if st.session_state.modo_confirmacao_filas and st.session_state.usuario_filas:
                    st.markdown("---")
                    
                    if st.session_state.acao_filas == "salvar":
                        st.warning(f"Voce tem certeza que deseja salvar as permissoes de filas para {st.session_state.usuario_filas}?")
                    elif st.session_state.acao_filas == "limpar":
                        st.warning(f"Voce tem certeza que deseja REMOVER TODAS as permissoes de filas para {st.session_state.usuario_filas}?")
                    elif st.session_state.acao_filas == "selecionar_todas":
                        st.warning(f"Voce tem certeza que deseja selecionar TODAS as filas para {st.session_state.usuario_filas}?")
                    
                    col_confirm1, col_confirm2, col_confirm3 = st.columns([1, 1, 1])
                    with col_confirm1:
                        if st.button("Sim, confirmar", use_container_width=True, key="confirmar_filas_sim"):
                            if st.session_state.acao_filas == "salvar":
                                if st.session_state.filas_selecionadas:
                                    success, msg = auth.update_user_filas(st.session_state.usuario_filas, st.session_state.filas_selecionadas)
                                else:
                                    success, msg = auth.update_user_filas(st.session_state.usuario_filas, [])
                            elif st.session_state.acao_filas == "limpar":
                                success, msg = auth.update_user_filas(st.session_state.usuario_filas, [])
                            elif st.session_state.acao_filas == "selecionar_todas":
                                success, msg = auth.update_user_filas(st.session_state.usuario_filas, filas_disponiveis)
                            
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)
                            
                            st.session_state.modo_confirmacao_filas = False
                            st.session_state.usuario_filas = None
                            st.session_state.filas_selecionadas = []
                            st.session_state.acao_filas = None
                            st.rerun()
                    
                    with col_confirm2:
                        if st.button("Cancelar", use_container_width=True, key="confirmar_filas_cancelar"):
                            st.session_state.modo_confirmacao_filas = False
                            st.session_state.usuario_filas = None
                            st.session_state.filas_selecionadas = []
                            st.session_state.acao_filas = None
                            st.info("Operacao cancelada.")
                            st.rerun()

                if filas_sel:
                    st.markdown("---")
                    st.markdown("Preview das filas selecionadas")
                    df_preview = pd.DataFrame({"Fila": filas_sel, "Status": ["Autorizado"] * len(filas_sel)})
                    st.dataframe(df_preview, use_container_width=True, hide_index=True)

        st.markdown("---")
        
        with st.expander("Matriz de Permissoes Completa"):
            all_users = auth.listar_usuarios()
            admin_padrao = auth.get_admin_user()

            dados_matriz = []
            for k, v in all_users.items():
                if k != admin_padrao:
                    ad_info = ad_data.get(k, {})
                    categoria = ad_info.get('categoria_usuario', v.get('categoria_ad', 'Servidor'))
                    status_ad = ad_info.get('status_ad', 'ATIVO')
                    status_ad_texto = "Ativo" if status_ad == "ATIVO" else "Inativo" if status_ad == "INATIVO" else status_ad
                    
                    filas_usuario = v.get("filas_autorizadas", [])
                    if filas_usuario == ["*"]:
                        qtd_filas = "Todas"
                        filas_texto = "TODAS (Administrador)"
                    elif not filas_usuario:
                        qtd_filas = "Nenhuma"
                        filas_texto = "Nenhuma"
                    else:
                        qtd_filas = len(filas_usuario)
                        filas_texto = ", ".join(filas_usuario)
                    
                    dados_matriz.append({
                        "Nome": v.get("nome", k),
                        "Usuario AD": k,
                        "Tipo": "Admin" if auth.is_admin(k) else "Usuario",
                        "Categoria": categoria,
                        "Status Sistema": "Ativo" if v.get("ativo", True) else "Inativo",
                        "Autorizado": "Sim" if v.get("autorizado", False) else "Nao",
                        "Status AD": status_ad_texto,
                        "Qtd Filas": qtd_filas,
                        "Filas": filas_texto
                    })

            if dados_matriz:
                df_matriz = pd.DataFrame(dados_matriz)
                st.dataframe(df_matriz, use_container_width=True, hide_index=True)
                
                st.download_button(
                    "Exportar CSV",
                    data=converter_csv_com_correcao(df_matriz),
                    file_name=f"permissoes_filas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

# ==================== TAB 5 - ESTATISTICAS AD ====================
with tab5:
    st.subheader("Estatisticas do Active Directory")
    st.caption("Distribuicao detalhada de usuarios por categoria, com ativos e inativos.")

    col_sync1, col_empty = st.columns([1, 4])
    with col_sync1:
        if st.button("Atualizar Dados", use_container_width=True):
            with st.spinner("Atualizando cache do AD..."):
                df_ad_all = ad_service.get_all_users_from_ad(force_refresh=True)
                st.rerun()

    with st.spinner("Carregando dados do Active Directory..."):
        df_ad_all = ad_service.get_all_users_from_ad()

    if df_ad_all.empty:
        st.warning("Nenhum dado do AD disponivel. Clique em 'Atualizar Dados' para carregar.")
    else:
        total_usuarios = len(df_ad_all)
        ativos_ad = len(df_ad_all[df_ad_all['ativo_no_ad'] == True])
        inativos_ad = len(df_ad_all[df_ad_all['ativo_no_ad'] == False])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Usuarios", f"{total_usuarios:,}".replace(",", "."))
        with col2:
            st.metric("Usuarios Ativos", f"{ativos_ad:,}".replace(",", "."))
        with col3:
            st.metric("Usuarios Inativos", f"{inativos_ad:,}".replace(",", "."))
        with col4:
            st.metric("Categorias", len(df_ad_all['categoria_usuario'].unique()))

        st.markdown("---")

        st.subheader("Distribuicao por Categoria")

        df_categorias = df_ad_all.groupby('categoria_usuario').agg(
            Ativos=('ativo_no_ad', lambda x: (x == True).sum()),
            Inativos=('ativo_no_ad', lambda x: (x == False).sum()),
            Total=('ativo_no_ad', 'count')
        ).reset_index().rename(columns={'categoria_usuario': 'Categoria'})

        df_categorias = df_categorias[
            df_categorias['Categoria'].notna() & 
            (df_categorias['Categoria'] != 'N/A') & 
            (df_categorias['Categoria'] != '')
        ]

        df_categorias = df_categorias.sort_values('Total', ascending=False)

        st.dataframe(
            df_categorias,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Categoria": st.column_config.Column("Categoria", width="medium"),
                "Ativos": st.column_config.NumberColumn("Ativos", format="%d", width="small"),
                "Inativos": st.column_config.NumberColumn("Inativos", format="%d", width="small"),
                "Total": st.column_config.NumberColumn("Total", format="%d", width="small")
            }
        )

        st.download_button(
            "Download Relatorio CSV",
            data=converter_csv_com_correcao(df_categorias),
            file_name=f"estatisticas_categorias_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.markdown("---")

        st.subheader("Usuarios por Categoria")

        categorias_lista = ['Todas'] + df_categorias['Categoria'].tolist()
        
        col_cat1, col_cat2, col_cat3 = st.columns(3)
        with col_cat1:
            categoria_selecionada = st.selectbox(
                "Selecione uma categoria:",
                options=categorias_lista,
                key="categoria_selecionada"
            )
        with col_cat2:
            status_filtro_cat = st.selectbox(
                "Status AD:",
                ["Todos", "Ativos", "Inativos"],
                key="status_categoria"
            )
        with col_cat3:
            busca_nome_cat = st.text_input(
                "Buscar:",
                placeholder="Digite nome ou username...",
                key="busca_categoria"
            )

        if categoria_selecionada == "Todas":
            df_filtrado_cat = df_ad_all.copy()
        else:
            df_filtrado_cat = df_ad_all[df_ad_all['categoria_usuario'] == categoria_selecionada]

        if status_filtro_cat == "Ativos":
            df_filtrado_cat = df_filtrado_cat[df_filtrado_cat['ativo_no_ad'] == True]
        elif status_filtro_cat == "Inativos":
            df_filtrado_cat = df_filtrado_cat[df_filtrado_cat['ativo_no_ad'] == False]

        if busca_nome_cat:
            busca_nome_cat = busca_nome_cat.lower().strip()
            mask = (
                df_filtrado_cat['nome_completo'].str.lower().str.contains(busca_nome_cat, na=False) |
                df_filtrado_cat['username'].str.lower().str.contains(busca_nome_cat, na=False)
            )
            df_filtrado_cat = df_filtrado_cat[mask]

        st.markdown(f"**{len(df_filtrado_cat)} usuarios encontrados**")

        if not df_filtrado_cat.empty:
            colunas_exibir_cat = ['nome_completo', 'username', 'email', 'categoria_usuario', 'status_ad']
            colunas_renomeadas_cat = {
                'nome_completo': 'Nome',
                'username': 'Usuario AD',
                'email': 'Email',
                'categoria_usuario': 'Categoria',
                'status_ad': 'Status AD'
            }
            
            df_exibicao_cat = df_filtrado_cat[colunas_exibir_cat].copy()
            df_exibicao_cat = df_exibicao_cat.rename(columns=colunas_renomeadas_cat)
            
            st.dataframe(
                df_exibicao_cat,
                use_container_width=True,
                hide_index=True
            )
            
            st.download_button(
                "Download Usuarios CSV",
                data=converter_csv_com_correcao(df_exibicao_cat),
                file_name=f"usuarios_{categoria_selecionada}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("Nenhum usuario encontrado com os filtros selecionados.")

        st.markdown("---")
        
        with st.expander("Grafico de Distribuicao por Categoria"):
            fig = px.bar(
                df_categorias.head(20),
                x='Categoria',
                y='Total',
                color='Ativos',
                title='Top 20 Categorias - Total de Usuarios',
                labels={'Total': 'Quantidade', 'Categoria': 'Categoria'},
                text_auto=True
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

# ==================== TAB 6 - CONFIGURACOES ====================
with tab6:
    st.subheader("Configuracoes do Sistema")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Autenticacao")
        st.info("Modo: Active Directory (NTLM)")
        st.write(f"Servidor AD: `{os.getenv('AD_SERVER', 'N/A')}`")
        st.write(f"Porta: `{os.getenv('AD_PORT', '389')}`")
        st.markdown("### Cache")
        st.info("Validade: 2 horas")
        st.markdown("### Autorizacao")
        st.info("Novos usuarios precisam de autorizacao do administrador")

    with col2:
        st.markdown("### Estatisticas")
        all_users = auth.listar_usuarios()

        total = 0
        ativos = 0
        inativos = 0
        autorizados = 0
        admins = 0
        inativos_ad = 0

        for k, v in all_users.items():
            if k != admin_padrao:
                total += 1
                if v.get("ativo", True) and v.get("autorizado", False):
                    ativos += 1
                if not v.get("ativo", True):
                    inativos += 1
                if v.get("autorizado", False):
                    autorizados += 1
                if v.get("tipo") == "admin":
                    admins += 1
                if not v.get("ativo_no_ad", True):
                    inativos_ad += 1

        st.metric("Total Usuarios", total)
        st.metric("Ativos", ativos)
        st.metric("Inativos", inativos)
        st.metric("Autorizados", autorizados)
        st.metric("Admins", admins)

        if inativos_ad > 0:
            st.warning(f"Usuarios inativos no AD: {inativos_ad}")

        st.markdown("### Filas")
        usuarios_com_filas = 0
        total_filas_atribuidas = 0

        for k, v in all_users.items():
            if k != admin_padrao and not auth.is_admin(k) and v.get("autorizado", False):
                filas = v.get("filas_autorizadas", [])
                if filas:
                    usuarios_com_filas += 1
                    total_filas_atribuidas += len(filas)

        st.metric("Usuarios com filas", usuarios_com_filas)
        st.metric("Total de atribuicoes", total_filas_atribuidas)
        if usuarios_com_filas > 0:
            st.metric("Media filas/usuario", f"{total_filas_atribuidas / usuarios_com_filas:.1f}")

    st.markdown("---")
    st.markdown("### Administrador Padrao")
    st.write(f"**Usuario AD:** `{admin_padrao}`")
    st.write("**Tipo:** Super Admin (protegido)")
    st.info("Este usuario tem acesso total e nao pode ser modificado ou removido.")

    st.markdown("---")
    st.markdown("### Sincronizacao com AD")
    if st.button("Sincronizar todos os usuarios com AD", use_container_width=True):
        with st.spinner("Sincronizando todos os usuarios..."):
            all_users = auth.listar_usuarios()
            count = 0
            for username in all_users:
                if username != admin_padrao:
                    auth.sync_ad_status_for_user(username)
                    count += 1
            st.success(f"Sincronizacao concluida. {count} usuarios verificados.")
            st.rerun()

st.markdown("---")
st.caption(f"Ultima atualizacao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")