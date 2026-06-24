import pandas as pd
import duckdb
from ldap3 import Server, Connection, ALL, SUBTREE, NTLM
from datetime import datetime, timedelta
import re
import os
from pathlib import Path

env_path = Path(__file__).parent.parent / '.env'
from dotenv import load_dotenv
load_dotenv(dotenv_path=env_path)

# ============================================
# CONFIGURACOES
# ============================================
AD_USER     = os.getenv('ADMIN_EMAIL')
AD_PASSWORD = os.getenv('ADMIN_PASSWORD')
AD_SERVER   = os.getenv('AD_SERVER', '10.138.100.100')
AD_PORT     = int(os.getenv('AD_PORT', 389))
AD_DOMAIN   = "detran.df"

# ============================================
# UTILITARIOS
# ============================================

def convert_filetime_to_datetime(filetime):
    if filetime is None or filetime == 0 or filetime == 9223372036854775807:
        return None
    try:
        if isinstance(filetime, datetime):
            if filetime.tzinfo is not None:
                return filetime.replace(tzinfo=None)
            return filetime
        if isinstance(filetime, str):
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y%m%d%H%M%S', '%Y-%m-%d %H:%M:%S.%f']:
                try: return datetime.strptime(filetime, fmt)
                except: continue
            dt = pd.to_datetime(filetime, errors='coerce')
            if pd.notna(dt):
                return dt.tz_localize(None) if dt.tzinfo is not None else dt
            return None
        if isinstance(filetime, (int, float)):
            return datetime(1601, 1, 1) + timedelta(seconds=filetime / 10_000_000)
        return None
    except Exception as e:
        print(f"Erro ao converter filetime {filetime}: {e}")
        return None

def safe_int_conversion(value):
    if value is None or isinstance(value, datetime): return None
    if isinstance(value, (int, float)): return int(value)
    if isinstance(value, str):
        try:
            numbers = re.findall(r'\d+', value)
            return int(numbers[0]) if numbers else None
        except: return None
    try: return int(value)
    except: return None

def remove_timezone_from_df(df):
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if df[col].dt.tz is not None: df[col] = df[col].dt.tz_localize(None)
        elif df[col].dtype == 'object':
            try:
                df[col] = pd.to_datetime(df[col], errors='ignore')
                if pd.api.types.is_datetime64_any_dtype(df[col]) and df[col].dt.tz is not None:
                    df[col] = df[col].dt.tz_localize(None)
            except: pass
    return df

def get_status_from_uac(uac):
    inactive = {514, 546, 66050, 4128}
    return "INATIVO" if uac in inactive else "ATIVO"

def get_tipo_status_from_uac(uac):
    tipos = {
        512: "Conta de usuario normal", 514: "Conta de usuario desabilitada",
        544: "Conta normal com senha nao obrigatoria", 522: "Conta desabilitada com diretorio home exigido",
        66082: "Conta desabilitada com senha que nunca expira e usuario nao pode alterar senha",
        546: "Conta desabilitada com senha nao obrigatoria", 66048: "Conta normal com senha que nunca expira",
        66050: "Conta desabilitada com senha que nunca expira", 66080: "Conta normal com senha nao obrigatoria e senha nunca expira",
        4096: "Conta de computador", 4128: "Conta de computador desabilitada",
    }
    return tipos.get(uac, f"Outro status: {uac}")

def extract_cpf_from_description(description):
    if not description: return None
    patterns = [r'\d{3}\.\d{3}\.\d{3}-\d{2}', r'\d{11}', r'\d{3}\.\d{3}\.\d{3}\.\d{2}']
    for pattern in patterns:
        match = re.search(pattern, str(description))
        if match:
            cpf = match.group(0).replace('.', '').replace('-', '')
            if len(cpf) == 11: return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return None

# ============================================
# BUSCA NO AD
# ============================================

def fetch_users_from_ad():
    base_dn = "DC=" + ",DC=".join(AD_DOMAIN.split('.'))
    ports_to_try = [AD_PORT, 3268] if AD_PORT == 389 else [AD_PORT]
    conn = None
    for port in ports_to_try:
        try:
            server_obj = Server(AD_SERVER, port=port, get_info=ALL, connect_timeout=10)
            conn = Connection(server_obj, user=AD_USER, password=AD_PASSWORD, authentication=NTLM, auto_bind=True)
            break
        except Exception as e: print(f"Falha na porta {port}: {e}")

    if conn is None: return pd.DataFrame()

    attributes = [
        'cn', 'sAMAccountName', 'mail', 'userPrincipalName', 'userAccountControl', 
        'whenCreated', 'whenChanged', 'distinguishedName', 'canonicalName', 'title', 
        'description', 'logonCount', 'badPasswordTime', 'lastLogonTimestamp', 'pwdLastSet', 
        'accountExpires', 'lastLogon'
    ]
    search_filter = '(&(objectClass=user)(objectCategory=person))'
    conn.search(search_base=base_dn, search_filter=search_filter, search_scope=SUBTREE, attributes=attributes, size_limit=10000, time_limit=120)

    users = []
    for entry in conn.entries:
        def get_attr_value(attr):
            val = getattr(entry, attr, None)
            if val is None: return None
            return val.value if hasattr(val, 'value') else val
        
        users.append({
            'CN': str(get_attr_value('cn')) if get_attr_value('cn') else None,
            'NOME_CADASTRO': str(get_attr_value('sAMAccountName')) if get_attr_value('sAMAccountName') else None,
            'Email': str(get_attr_value('mail') or get_attr_value('userPrincipalName') or ''),
            'STATUS_RAW': safe_int_conversion(get_attr_value('userAccountControl')) or 512,
            'DESCRICAO_TIPO_DE_CONTA': str(get_attr_value('description')) if get_attr_value('description') else None,
            'Funcao': str(get_attr_value('title')) if get_attr_value('title') else None,
            'Quantas_vezes_logou': safe_int_conversion(get_attr_value('logonCount')) or 0,
            'ULTIMO_LOGON': convert_filetime_to_datetime(get_attr_value('lastLogonTimestamp')),
            'ULTIMA_ALTERACAO_SENHA': convert_filetime_to_datetime(get_attr_value('pwdLastSet')),
            'ULTIMA_VEZ_ERROU_LOGON': convert_filetime_to_datetime(get_attr_value('badPasswordTime')),
            'quando_expirara': convert_filetime_to_datetime(get_attr_value('accountExpires')),
            'Quando_foi_criado': convert_filetime_to_datetime(get_attr_value('whenCreated')),
            'Quando_foi_alterado': convert_filetime_to_datetime(get_attr_value('whenChanged')),
            'canonicalName': str(get_attr_value('canonicalName')) if get_attr_value('canonicalName') else None,
            'distinguishedName': str(get_attr_value('distinguishedName')) if get_attr_value('distinguishedName') else None,
            'Local_Pasta': str(get_attr_value('canonicalName')) if get_attr_value('canonicalName') else None,
        })
    conn.unbind()
    df = pd.DataFrame(users)
    if df.empty: return df
    df['STATUS'] = df['STATUS_RAW'].apply(get_status_from_uac)
    df['TIPO_DE_USUARIO'] = df['STATUS_RAW'].apply(get_tipo_status_from_uac)
    return remove_timezone_from_df(df)

# ============================================
# PROCESSAMENTO COM DUCKDB
# ============================================

def process_with_dax_rules(df_ad_users):
    if df_ad_users.empty: return df_ad_users

    con = duckdb.connect()
    con.register('ad_users', df_ad_users)

    # Note as funções nativas de UPPER(STRIP()) removendo acentuações e plurais nos CASE WHEN lógicos do SQL
    query = """
    WITH pasta_split AS (
        SELECT
            *,
            string_split(COALESCE(Local_Pasta, ''), '/') AS pasta_array,
            CASE WHEN len(pasta_array) >= 1 THEN upper(trim(pasta_array[1])) ELSE NULL END AS Caminho_Pasta_1,
            CASE WHEN len(pasta_array) >= 2 THEN upper(trim(pasta_array[2])) ELSE NULL END AS Caminho_Pasta_2,
            CASE WHEN len(pasta_array) >= 3 THEN upper(trim(pasta_array[3])) ELSE NULL END AS Caminho_Pasta_3,
            CASE WHEN len(pasta_array) >= 4 THEN upper(trim(pasta_array[4])) ELSE NULL END AS Caminho_Pasta_4,
            CASE WHEN len(pasta_array) >= 5 THEN upper(trim(pasta_array[5])) ELSE NULL END AS Caminho_Pasta_5,
            CASE WHEN len(pasta_array) >= 6 THEN upper(trim(pasta_array[6])) ELSE NULL END AS Caminho_Pasta_6,
            -- Preservação dos nomes originais caso seja o nome da empresa terceirizada
            CASE WHEN len(pasta_array) >= 2 THEN pasta_array[2] ELSE NULL END AS Orig_Pasta_2,
            CASE WHEN len(pasta_array) >= 3 THEN pasta_array[3] ELSE NULL END AS Orig_Pasta_3,
            CASE WHEN len(pasta_array) >= 4 THEN pasta_array[4] ELSE NULL END AS Orig_Pasta_4,
            CASE WHEN len(pasta_array) >= 5 THEN pasta_array[5] ELSE NULL END AS Orig_Pasta_5
        FROM ad_users
        WHERE CN IS NOT NULL
    ),
    regras_base AS (
        SELECT
            *,
            -- Verifica se o marcador de Desabilitados consta em qualquer parte da hierarquia estrutural inicial
            CASE WHEN 'DESABILITADOS' IN (Caminho_Pasta_1, Caminho_Pasta_2, Caminho_Pasta_3) THEN 'SIM' ELSE 'NAO' END AS na_pasta_desabilitados,
            
            -- Descobre de forma dinâmica qual o índice real após a pasta Desabilitados
            CASE 
                WHEN Caminho_Pasta_1 = 'DESABILITADOS' THEN Caminho_Pasta_2
                WHEN Caminho_Pasta_2 = 'DESABILITADOS' THEN Caminho_Pasta_3
                WHEN Caminho_Pasta_3 = 'DESABILITADOS' THEN Caminho_Pasta_4
                ELSE NULL 
            END AS pasta_pos_desabilitados,

            CASE 
                WHEN Caminho_Pasta_1 = 'DESABILITADOS' THEN Orig_Pasta_3
                WHEN Caminho_Pasta_2 = 'DESABILITADOS' THEN Orig_Pasta_4
                WHEN Caminho_Pasta_3 = 'DESABILITADOS' THEN Orig_Pasta_5
                ELSE NULL 
            END AS subpasta_pos_desabilitados
        FROM pasta_split
    )
    SELECT
        CN                          AS "NOME COMPLETO",
        NOME_CADASTRO               AS "NOME CADASTRO",
        Email,
        COALESCE(DESCRICAO_TIPO_DE_CONTA, '') AS DESCRICAO_TIPO_DE_CONTA,
        TIPO_DE_USUARIO,
        CPF,
        COALESCE(Funcao, '')        AS "Funcao",
        Quantas_vezes_logou         AS "Quantas vezes logou",
        ULTIMO_LOGON,
        ULTIMA_ALTERACAO_SENHA      AS "ULTIMA ALTERACAO DA SENHA",
        ULTIMA_VEZ_ERROU_LOGON      AS "ULTIMA VEZ QUE ERROU LOGON",
        quando_expirara             AS "quando expirara",
        Quando_foi_criado           AS "Quando foi criado",
        Quando_foi_alterado         AS "Quando foi alterado",
        COALESCE(Local_Pasta, 'Sem pasta definida') AS Local_Pasta,
        COALESCE(distinguishedName, '') AS "Caminho_DN",

        -- FORÇA DO STATUS: Se contiver Desabilitados, vira obrigatoriamente INATIVO
        CASE 
            WHEN na_pasta_desabilitados = 'SIM' THEN 'INATIVO'
            ELSE STATUS 
        END AS STATUS,

        -- DETERMINAÇÃO DA CATEGORIA TRATANDO AS INCERTEZAS DE TEXTO
        CASE
            -- 1. Se veio de uma pasta de Desabilitados
            WHEN na_pasta_desabilitados = 'SIM' THEN
                CASE
                    WHEN pasta_pos_desabilitados IN ('SERVIDOR', 'SERVIDORES') THEN 'maquina'
                    WHEN pasta_pos_desabilitados IN ('TERCEIRIZADO', 'TERCEIRIZADOS') THEN COALESCE(subpasta_pos_desabilitados, 'Terceirizado')
                    WHEN pasta_pos_desabilitados IN ('USUARIO', 'USUARIOS') THEN 'Usuario'
                    WHEN pasta_pos_desabilitados IN ('CONVIDADO', 'CONVIDADOS') THEN 'Convidado'
                    WHEN pasta_pos_desabilitados IN ('SERVICO', 'SERVICOS') THEN 'Serviço'
                    WHEN pasta_pos_desabilitados IN ('APLICACAO', 'APLICACOES') THEN 'Aplicações'
                    ELSE COALESCE(pasta_pos_desabilitados, 'N/A')
                END

            -- 2. Raiz DETRAN-DF padrão
            WHEN Caminho_Pasta_2 = 'DETRAN-DF' THEN
                CASE
                    WHEN Caminho_Pasta_3 IN ('USUARIO', 'USUARIOS') THEN
                        CASE
                            WHEN Caminho_Pasta_4 IN ('SERVIDOR', 'SERVIDORES') THEN 'maquina'
                            WHEN Caminho_Pasta_4 IN ('TERCEIRIZADO', 'TERCEIRIZADOS') THEN COALESCE(Orig_Pasta_5, 'Terceirizado')
                            WHEN Caminho_Pasta_4 IN ('CONVIDADO', 'CONVIDADOS') THEN 'Convidado'
                            WHEN Caminho_Pasta_4 IN ('ESTAGIARIO', 'ESTAGIARIOS') THEN 'Estagiário'
                            WHEN Caminho_Pasta_4 IN ('SERVICO', 'SERVICOS') THEN 'Serviço'
                            WHEN Caminho_Pasta_4 IN ('APLICACAO', 'APLICACOES') THEN 'Aplicações'
                            ELSE 'Usuario'
                        END
                    WHEN Caminho_Pasta_3 = 'GRUPOS' THEN
                        CASE WHEN Caminho_Pasta_4 IN ('APLICACAO', 'APLICACOES') THEN 'Aplicações' ELSE 'Grupos' END
                    WHEN Caminho_Pasta_3 = 'SERVICE_ACCOUNTS' THEN 'Service_Account'
                    ELSE COALESCE(Orig_Pasta_3, 'N/A')
                END

            -- 3. DETRAN-SEDE
            WHEN Caminho_Pasta_2 = 'DETRAN-SEDE' THEN 'Serviço'

            -- 4. Computadores Gerais (Mapeado uniformemente como maquina)
            WHEN Caminho_Pasta_2 IN ('USERS', 'COMPUTERS') THEN 'maquina'

            ELSE COALESCE(Orig_Pasta_3, Orig_Pasta_4, 'N/A')
        END AS Categoria_usuario

    FROM regras_base
    ORDER BY "NOME COMPLETO"
    """

    result_df = con.execute(query).df()
    con.close()
    
    # Replica na Categoria_filtro o valor consolidado
    result_df['Categoria_filtro'] = result_df['Categoria_usuario']
    return remove_timezone_from_df(result_df)

def main():
    print("Conectando ao Active Directory...")
    df_raw = fetch_users_from_ad()
    if df_raw.empty: return None

    df_processed = process_with_dax_rules(df_raw)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_file   = f"usuarios_ad_detran_{timestamp}.xlsx"
    df_processed.to_excel(xlsx_file, index=False, engine='openpyxl')
    print(f"📁 Arquivo Excel salvo: {xlsx_file}")
    return df_processed

if __name__ == "__main__":
    main()