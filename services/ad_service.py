# ad_service.py
import os
import sys
import hashlib
import unicodedata
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

# Carrega o .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configuracoes
AD_USER     = os.getenv('ADMIN_EMAIL')
AD_PASSWORD = os.getenv('ADMIN_PASSWORD')
AD_SERVER   = os.getenv('AD_SERVER', '10.138.100.100')
AD_PORT     = int(os.getenv('AD_PORT', 389))
AD_DOMAIN   = "gabriel.br"

# UAC considerados INATIVOS
UAC_INATIVOS = {514, 546, 66050, 4128}

EMPTY_DF = pd.DataFrame(columns=[
    'username', 'nome_completo', 'email',
    'categoria_usuario', 'status_ad', 'ativo_no_ad', 'canonical_name'
])

# ============================================================
# PATCH MD4
# ============================================================
def _patch_md4():
    try:
        import hashlib
        hashlib.new('md4')
        return True
    except ValueError:
        pass
    try:
        from impacket.crypto import MD4
        import hashlib
        class _MD4Wrapper:
            __slots__ = ['_h']
            def __init__(self, data=b''):
                self._h = MD4()
                if data:
                    self._h.update(data)
            def update(self, data):
                self._h.update(data)
                return self
            def digest(self):
                return self._h.digest()
            def hexdigest(self):
                return self._h.hexdigest()
            def copy(self):
                import copy
                return copy.copy(self)
        hashlib.register_hash('md4', _MD4Wrapper)
        print("[AD] MD4 registrado via impacket.")
        return True
    except Exception:
        pass
    print("[AD] MD4 nao disponivel. Usando SIMPLE authentication.")
    return False

_MD4_AVAILABLE = _patch_md4()

# ============================================================
# IMPORTA LDAP3
# ============================================================
from ldap3 import Server, Connection, ALL, SUBTREE, NTLM, SIMPLE


def _uac_is_active(uac_int: int) -> bool:
    return uac_int not in UAC_INATIVOS


def _capitalizar_categoria(categoria: str) -> str:
    if not categoria:
        return categoria
    if categoria in ["Service_Accounts", "Service_Account"]:
        return "Service_Accounts"
    if categoria.lower() in ["truly", "indra", "memora", "eds", "fokus", "very", "tarea", "redhat", "valid", "tecnisys", "chaintech", "zello", "simpress"]:
        return categoria.title()
    return categoria[0].upper() + categoria[1:].lower() if len(categoria) > 1 else categoria.upper()


# Lista de empresas conhecidas para identificar nos textos
EMPRESAS_CONHECIDAS = [
    "truly", "indra", "memora", "eds", "fokus", "very", "tarea",
    "redhat", "valid", "tecnisys", "chaintech", "zello", "simpress"
]

def _extrair_empresa_de_texto(texto: str) -> str:
    if not texto:
        return None
    texto_lower = texto.lower()
    for emp in EMPRESAS_CONHECIDAS:
        if emp in texto_lower:
            return emp.title()
    return None


def _extrair_empresa_de_lista(textos: list) -> str:
    if not textos:
        return None
    for t in textos:
        if t:
            emp = _extrair_empresa_de_texto(t)
            if emp:
                return emp
    return None


def _extrair_pastas_do_dn(dn: str) -> list:
    """Extrai as OUs do distinguishedName na ordem: [domínio, OU_mais_geral, ..., OU_mais_especifica]."""
    if not dn:
        return []
    partes = dn.split(',')
    ous = []
    for p in partes:
        p = p.strip()
        if p.startswith('OU='):
            ous.append(p[3:])
    ous.reverse()
    return [AD_DOMAIN] + ous


def _categoria_especial_por_username(username: str) -> str:
    if not username:
        return None
    username_lower = username.lower().strip()
    if username_lower.startswith('iusr_') or username_lower.startswith('iwam_'):
        return 'Service_Accounts'
    contas_servico = [
        'wiki doku', 'web', 'svnserve2', 'svnserve', 'renainf.job',
        'poc vistoria', 'openfiler admin', 'ocomon', 'nupre',
        'engebras', 'backup rsync linux', 'backup rsync',
        'vra admin', 'vra user', '___vmware_conv_sa___',
        'svc_', 'svc-', '_svc', '-svc', 'msol_',
        'rsync backup', 'linux backup', 'admin openfiler', 'openfiler',
        'wiki', 'doku', 'poc_vistoria', 'vistoria',
        'backup_rsync_linux', 'backup-rsync-linux', 'vra_admin', 'vra-admin', 'vrauser', 'vra_user'
    ]
    for conta in contas_servico:
        if conta in username_lower:
            return 'Service_Accounts'
    if username_lower in ['aspnet', 'defaultaccount', 'guest', 'tsinternetuser', 'prova'] or username_lower.startswith('krbtgt'):
        return 'Sistema'
    if username.endswith('$') or username_lower in ['Gabriel-df', 'Gabriel-sede']:
        return 'Servidor público'
    return None


def _classificar_categoria(pastas: list, desc_list: list = None, company: str = None) -> tuple:
    """
    Classifica a categoria com base na estrutura de pastas, seguindo as regras:
    - Users → Service_Accounts/Sistema (já tratado por username)
    - Gabriel-SEDE → Serviço
    - Desabilitados → mantém categoria original (Servidor, Terceirizado, Estagiário, etc.)
    - Gabriel-DF/Usuarios → usa Pasta_3 para definir categoria
    - Fallback: Servidor público
    """
    if not pastas:
        return ('Servidor público', False)

    # Mapeia as pastas (p1 = domínio, p2, p3, p4, p5)
    p1 = pastas[0] if len(pastas) > 0 else ''
    p2 = pastas[1] if len(pastas) > 1 else ''
    p3 = pastas[2] if len(pastas) > 2 else ''
    p4 = pastas[3] if len(pastas) > 3 else ''
    p5 = pastas[4] if len(pastas) > 4 else ''

    p1_l = p1.lower()
    p2_l = p2.lower()
    p3_l = p3.lower()
    p4_l = p4.lower()
    p5_l = p5.lower()

    # Flag de desabilitado (se qualquer pasta contiver "Desabilitados")
    esta_desabilitado = any('desabilitados' in p.lower() for p in pastas)

    # ============================================================
    # REGRA 1: Users (estrutura antiga) – já tratado por username, mas mantemos fallback
    # ============================================================
    if p1_l == "users" or p2_l == "users":
        return ('Servidor público', esta_desabilitado)

    # ============================================================
    # REGRA 2: Gabriel-SEDE → Serviço
    # ============================================================
    if p1_l == "Gabriel-sede":
        return ('Serviço', esta_desabilitado)

    # ============================================================
    # REGRA 3: Desabilitados (em qualquer nível)
    # ============================================================
    if esta_desabilitado:
        if p3_l in ["servidores", "servidor"]:
            return ('Servidor público', esta_desabilitado)
        elif p3_l in ["estagiarios", "estagiários"]:
            return ('Estagiário', esta_desabilitado)
        elif p3_l == "convidados":
            return ('Convidado', esta_desabilitado)
        elif p3_l == "servico":
            return ('Serviço', esta_desabilitado)
        elif p3_l == "terceirizados":
            empresa = None
            if p4 and _extrair_empresa_de_texto(p4):
                empresa = _extrair_empresa_de_texto(p4)
            elif company and _extrair_empresa_de_texto(company):
                empresa = _extrair_empresa_de_texto(company)
            elif desc_list and _extrair_empresa_de_lista(desc_list):
                empresa = _extrair_empresa_de_lista(desc_list)
            if empresa:
                return (empresa, esta_desabilitado)
            else:
                return ('Terceirizados', esta_desabilitado)
        else:
            empresa = _extrair_empresa_de_texto(p3)
            if empresa:
                return (empresa, esta_desabilitado)
            return ('Terceirizados', esta_desabilitado)

    # ============================================================
    # REGRA 4: Gabriel-DF/Usuarios (estrutura principal)
    # ============================================================
    if p1_l == "Gabriel.df" and p2_l == "Gabriel-df":
        if p3_l == "usuarios":
            if p4_l == "servidores":
                return ('Servidor público', esta_desabilitado)
            elif p4_l in ["estagiarios", "estagiários"]:
                return ('Estagiário', esta_desabilitado)
            elif p4_l == "convidados":
                return ('Convidado', esta_desabilitado)
            elif p4_l == "servico":
                return ('Serviço', esta_desabilitado)
            elif p4_l == "aplicacoes":
                return ('Aplicações', esta_desabilitado)
            elif p4_l == "terceirizados":
                empresa = None
                if p5 and _extrair_empresa_de_texto(p5):
                    empresa = _extrair_empresa_de_texto(p5)
                elif company and _extrair_empresa_de_texto(company):
                    empresa = _extrair_empresa_de_texto(company)
                elif desc_list and _extrair_empresa_de_lista(desc_list):
                    empresa = _extrair_empresa_de_lista(desc_list)
                if empresa:
                    return (empresa, esta_desabilitado)
                else:
                    return ('Terceirizados', esta_desabilitado)
            else:
                empresa = _extrair_empresa_de_texto(p4)
                if empresa:
                    return (empresa, esta_desabilitado)
                if p4 and ' ' in p4 and len(p4.split()) > 1:
                    return ('Servidor público', esta_desabilitado)
                return (p4 if p4 else 'Servidor público', esta_desabilitado)
        else:
            empresa = _extrair_empresa_de_texto(p3)
            if empresa:
                return (empresa, esta_desabilitado)
            return (p3 if p3 else 'Servidor público', esta_desabilitado)

    # ============================================================
    # REGRA 5: Fallback final
    # ============================================================
    return ('Servidor público', esta_desabilitado)


class ADService:
    def __init__(self):
        Path("data").mkdir(exist_ok=True)
        self.cache_file = Path("data/ad_users_cache.pkl")
        self.cache_timestamp = Path("data/ad_users_cache_timestamp.pkl")

    def authenticate(self, username: str, password: str) -> tuple:
        try:
            if '\\' in username:
                domain, uname = username.split('\\', 1)
                user = f"{uname}@{AD_DOMAIN}"
            elif '@' in username:
                user = username
            else:
                user = f"{username}@{AD_DOMAIN}"
            print(f"[AD] Autenticando: {user} (SIMPLE)")
            server_obj = Server(AD_SERVER, port=AD_PORT, get_info=ALL, connect_timeout=10)
            conn = Connection(server_obj, user=user, password=password, authentication=SIMPLE, auto_bind=True)
            conn.unbind()
            return True, "Autenticado com sucesso"
        except Exception as e:
            return False, f"Falha na autenticacao: {str(e)}"

    def get_user_info(self, username: str) -> dict:
        try:
            base_dn = "DC=" + ",DC=".join(AD_DOMAIN.split('.'))
            search_filter = f"(&(objectClass=user)(sAMAccountName={username}))"
            conn = self._connect()
            if conn is None:
                return None
            conn.search(
                search_base=base_dn, search_filter=search_filter, search_scope=SUBTREE,
                attributes=['sAMAccountName', 'displayName', 'mail', 'userPrincipalName',
                           'userAccountControl', 'canonicalName', 'description', 'company', 'distinguishedName']
            )
            if len(conn.entries) == 0:
                conn.unbind()
                return None
            entry = conn.entries[0]
            def get_val(attr):
                val = getattr(entry, attr, None)
                if val is None:
                    return None
                return val.value if hasattr(val, 'value') else val

            uac = get_val('userAccountControl')
            uac_int = int(uac) if uac is not None else 512
            is_active = _uac_is_active(uac_int)

            canonical = get_val('canonicalName')
            canonical_str = str(canonical) if canonical else ''

            dn = get_val('distinguishedName')
            dn_str = str(dn) if dn else ''

            desc_attr = getattr(entry, 'description', None)
            desc_list = []
            if desc_attr and hasattr(desc_attr, 'values') and desc_attr.values:
                desc_list = [str(v) for v in desc_attr.values]
            elif desc_attr and hasattr(desc_attr, 'value') and desc_attr.value:
                desc_list = [str(desc_attr.value)]

            company = get_val('company')
            company_str = str(company) if company else None

            if canonical_str:
                pastas = [p.strip() for p in canonical_str.split('/') if p.strip()]
            elif dn_str:
                pastas = _extrair_pastas_do_dn(dn_str)
            else:
                pastas = []

            if username:
                cat_esp = _categoria_especial_por_username(username)
                if cat_esp:
                    categoria = cat_esp
                    esta_desabilitado = False
                else:
                    categoria, esta_desabilitado = _classificar_categoria(pastas, desc_list, company_str)
            else:
                categoria, esta_desabilitado = _classificar_categoria(pastas, desc_list, company_str)

            if esta_desabilitado:
                is_active = False

            info = {
                'username': str(get_val('sAMAccountName') or '').lower(),
                'nome_completo': str(get_val('displayName') or '').upper(),
                'email': str(get_val('mail') or get_val('userPrincipalName') or ''),
                'categoria_usuario': categoria,
                'status_ad': 'ATIVO' if is_active else 'INATIVO',
                'ativo_no_ad': is_active,
                'canonical_name': canonical_str
            }
            conn.unbind()
            return info
        except Exception as e:
            print(f"Erro ao buscar usuario {username}: {e}")
            return None

    def get_all_users_from_ad(self, force_refresh=False) -> pd.DataFrame:
        if not force_refresh and self.cache_file.exists() and self.cache_timestamp.exists():
            import pickle
            try:
                with open(self.cache_timestamp, "rb") as f:
                    timestamp = pickle.load(f)
                if (datetime.now() - timestamp).total_seconds() < 86400:
                    with open(self.cache_file, "rb") as f:
                        cached = pickle.load(f)
                    print(f"Cache carregado: {len(cached)} usuarios")
                    if 'canonical_name' not in cached.columns:
                        force_refresh = True
                    else:
                        return cached
            except Exception as e:
                print(f"Erro ao ler cache: {e}")
                force_refresh = True

        print("\n" + "=" * 60)
        print("BUSCANDO USUARIOS DO AD")
        print("=" * 60)

        df = self._fetch_all_users()
        if not df.empty:
            ativos = int(df['ativo_no_ad'].sum())
            inativos = len(df) - ativos
            print(f"\nRESUMO: {len(df)} usuarios | Ativos: {ativos} | Inativos: {inativos}")

        if len(df) > 0:
            import pickle
            with open(self.cache_file, "wb") as f:
                pickle.dump(df, f)
            with open(self.cache_timestamp, "wb") as f:
                pickle.dump(datetime.now(), f)
        return df

    def _connect(self):
        auth_mode = os.getenv('AD_AUTH', 'SIMPLE').upper()
        if auth_mode == 'SIMPLE' or not _MD4_AVAILABLE:
            auth_method = SIMPLE
            auth_name = "SIMPLE"
            user = AD_USER
            if '\\' in (user or ''):
                domain, uname = user.split('\\', 1)
                user = f"{uname}@{AD_DOMAIN}"
        else:
            auth_method = NTLM
            auth_name = "NTLM"
            user = AD_USER

        ports_to_try = [AD_PORT, 3268] if AD_PORT == 389 else [AD_PORT]
        for port in ports_to_try:
            try:
                print(f"Conectando: {AD_SERVER}:{port} ({auth_name}) usuario={user}")
                server_obj = Server(AD_SERVER, port=port, get_info=ALL, connect_timeout=10)
                conn = Connection(server_obj, user=user, password=AD_PASSWORD,
                                  authentication=auth_method, auto_bind=True)
                return conn
            except Exception as e:
                print(f"Falha na porta {port}: {type(e).__name__}: {e}")
        return None

    def _fetch_all_users(self) -> pd.DataFrame:
        base_dn = "DC=" + ",DC=".join(AD_DOMAIN.split('.'))
        conn = self._connect()
        if conn is None:
            return EMPTY_DF.copy()

        attributes = ['sAMAccountName', 'displayName', 'mail', 'userPrincipalName',
                      'userAccountControl', 'canonicalName', 'description', 'company', 'distinguishedName']
        search_filter = '(&(objectClass=user)(objectCategory=person))'
        all_rows = []
        cookie = None
        page = 1

        print("Iniciando varredura paginada por lotes de 1000...")
        try:
            while True:
                conn.search(
                    search_base=base_dn, search_filter=search_filter, search_scope=SUBTREE,
                    attributes=attributes, paged_size=1000, paged_cookie=cookie
                )
                for entry in conn.entries:
                    def get_val(attr, _e=entry):
                        val = getattr(_e, attr, None)
                        if val is None:
                            return None
                        return val.value if hasattr(val, 'value') else val

                    username = get_val('sAMAccountName')
                    if not username:
                        continue
                    username = str(username).lower()

                    nome_completo = str(get_val('displayName') or username).upper()
                    email = str(get_val('mail') or get_val('userPrincipalName') or '')

                    uac = get_val('userAccountControl')
                    uac_int = int(uac) if uac is not None else 512
                    is_active = _uac_is_active(uac_int)

                    canonical_str = str(get_val('canonicalName') or '')
                    dn_str = str(get_val('distinguishedName') or '')

                    desc_attr = getattr(entry, 'description', None)
                    desc_list = []
                    if desc_attr and hasattr(desc_attr, 'values') and desc_attr.values:
                        desc_list = [str(v) for v in desc_attr.values]
                    elif desc_attr and hasattr(desc_attr, 'value') and desc_attr.value:
                        desc_list = [str(desc_attr.value)]

                    company = get_val('company')
                    company_str = str(company) if company else None

                    if canonical_str:
                        pastas = [p.strip() for p in canonical_str.split('/') if p.strip()]
                    elif dn_str:
                        pastas = _extrair_pastas_do_dn(dn_str)
                    else:
                        pastas = []

                    cat_esp = _categoria_especial_por_username(username)
                    if cat_esp:
                        categoria = cat_esp
                        esta_desabilitado = False
                    else:
                        categoria, esta_desabilitado = _classificar_categoria(pastas, desc_list, company_str)

                    if esta_desabilitado:
                        is_active = False

                    if not desc_list:
                        desc_list = [None]

                    for desc in desc_list:
                        all_rows.append({
                            'username': username,
                            'nome_completo': nome_completo,
                            'email': email,
                            'categoria_usuario': categoria,
                            'status_ad': 'ATIVO' if is_active else 'INATIVO',
                            'ativo_no_ad': is_active,
                            'canonical_name': canonical_str,
                            'descricao_tipo_de_conta': desc
                        })

                controls = conn.result.get('controls', {})
                paging = controls.get('1.2.840.113556.1.4.319', {})
                cookie = paging.get('value', {}).get('cookie', None) if isinstance(paging.get('value'), dict) else None
                if not cookie:
                    break
                page += 1
        except Exception as e:
            print(f"Erro na pagina {page}: {e}")
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

        if not all_rows:
            return EMPTY_DF.copy()
        df = pd.DataFrame(all_rows)
        return df

    def search_users(self, search_term: str) -> pd.DataFrame:
        """
        Busca usuarios no AD por username, nome ou email.
        Retorna TODOS os resultados (sem limite).
        """
        # Usa o cache existente (não força refresh para não sobrecarregar)
        df = self.get_all_users_from_ad(force_refresh=False)
        
        if df.empty:
            return EMPTY_DF.copy()
        
        search_term = search_term.lower().strip()
        if not search_term:
            return df.head(100)
        
        def remover_acentos(texto):
            if not texto:
                return texto
            return ''.join(c for c in unicodedata.normalize('NFKD', str(texto)) if not unicodedata.combining(c)).lower()
        
        termo_sem_acento = remover_acentos(search_term)
        
        # Cria colunas temporárias normalizadas
        df_busca = df.copy()
        df_busca['username_clean'] = df_busca['username'].apply(remover_acentos)
        df_busca['nome_clean'] = df_busca['nome_completo'].apply(remover_acentos)
        df_busca['email_clean'] = df_busca['email'].apply(lambda x: remover_acentos(x) if pd.notna(x) else '')
        
        # Busca em todas as colunas (SEM LIMITE)
        mask = (df_busca['username_clean'].str.contains(termo_sem_acento, na=False) |
                df_busca['nome_clean'].str.contains(termo_sem_acento, na=False) |
                df_busca['email_clean'].str.contains(termo_sem_acento, na=False))
        
        resultados = df[mask].copy()
        
        # Remove colunas temporárias
        resultados = resultados.drop(columns=['username_clean', 'nome_clean', 'email_clean'], errors='ignore')
        
        # Ordena por relevância
        termo_exato = search_term
        resultados['_rel'] = 0
        resultados.loc[resultados['username'] == termo_exato, '_rel'] = 100
        resultados.loc[resultados['username'].str.startswith(termo_exato), '_rel'] = 50
        resultados.loc[resultados['nome_completo'].str.lower().str.startswith(termo_exato, na=False), '_rel'] = 25
        
        resultados = resultados.sort_values('_rel', ascending=False).drop('_rel', axis=1)
        
        return resultados

    def gerar_relatorio_categorias(self) -> pd.DataFrame:
        df = self.get_all_users_from_ad()
        if df.empty:
            return pd.DataFrame(columns=['Categoria', 'Ativos', 'Inativos', 'Total'])
        df_unicos = df.drop_duplicates(subset=['username', 'categoria_usuario', 'ativo_no_ad'])
        relatorio = df_unicos.groupby('categoria_usuario').agg(
            Ativos=('ativo_no_ad', lambda x: (x == True).sum()),
            Inativos=('ativo_no_ad', lambda x: (x == False).sum()),
            Total=('ativo_no_ad', 'count')
        ).reset_index().rename(columns={'categoria_usuario': 'Categoria'})
        relatorio = relatorio[relatorio['Categoria'].notna() & (relatorio['Categoria'] != 'N/A')]
        return relatorio.sort_values('Total', ascending=False)


if __name__ == "__main__":
    ad = ADService()
    df = ad.get_all_users_from_ad(force_refresh=True)
    if not df.empty:
        relatorio = ad.gerar_relatorio_categorias()
        print(relatorio.to_string(index=False))
        truly_count = len(df[df['categoria_usuario'].str.lower() == 'truly'])
        print(f"\nTotal de usuários com categoria 'Truly' (case-insensitive): {truly_count}")