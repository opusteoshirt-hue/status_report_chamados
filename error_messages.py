# error_messages.py

# ==================== ERROS DO USUÁRIO (MENSAGENS AMIGÁVEIS) ====================
USER_ERROR_MESSAGES = {
    # Autenticação
    "AUTH_FAILED": "Usuário ou senha incorretos. Verifique suas credenciais e tente novamente.",
    "AUTH_DISABLED": "Usuário desativado no sistema. Contate o administrador.",
    "AUTH_NOT_AUTHORIZED": "Acesso não autorizado. Solicite autorização ao administrador.",
    "AUTH_AD_INACTIVE": "Usuário inativo no Active Directory. Contate o administrador.",
    "AUTH_SESSION_EXPIRED": "Sua sessão expirou. Faça login novamente.",
    
    # Permissões
    "PERMISSION_DENIED": "Você não tem permissão para acessar esta página.",
    "ADMIN_REQUIRED": "Acesso restrito a administradores.",
    "NO_FILAS": "Você não tem permissão para visualizar nenhuma fila.",
    
    # Dados
    "NO_DATA": "Nenhum dado disponível para os filtros selecionados.",
    "NO_SEARCH_RESULTS": "Nenhum usuário encontrado com o termo informado.",
    
    # Operações
    "USER_NOT_FOUND": "Usuário não encontrado no sistema.",
    "USER_ALREADY_AUTHORIZED": "Usuário já está autorizado no sistema.",
    "CANNOT_MODIFY_ADMIN": "Não é possível modificar o administrador padrão.",
}

# ==================== ERROS DO SISTEMA/BANCO (CÓDIGOS GENÉRICOS) ====================
SYSTEM_ERROR_CODES = {
    # Conexões
    "ERR_CONNECTION_001": "Erro de comunicação com o servidor. Tente novamente em alguns minutos.",
    "ERR_CONNECTION_002": "Tempo limite de conexão excedido. Verifique sua rede.",
    "ERR_CONNECTION_003": "Não foi possível estabelecer conexão com o serviço.",
    
    # Banco de dados
    "ERR_DB_001": "Erro ao processar sua solicitação. Tente novamente mais tarde.",
    "ERR_DB_002": "Limite de conexões simultâneas excedido. Aguarde alguns instantes.",
    "ERR_DB_003": "Erro ao carregar dados. Atualize a página e tente novamente.",
    "ERR_DB_004": "Comando de banco de dados mal formatado. Contate o suporte.",
    "ERR_DB_005": "Recurso temporariamente indisponível. Tente novamente.",
    
    # Active Directory
    "ERR_AD_001": "Erro de conexão com o serviço de diretório. Verifique sua VPN.",
    "ERR_AD_002": "Falha na autenticação com o Active Directory.",
    "ERR_AD_003": "Tempo limite na consulta ao Active Directory.",
    "ERR_AD_004": "Usuário não encontrado no Active Directory.",
    
    # Cache
    "ERR_CACHE_001": "Erro ao ler dados em cache. Recarregando informações...",
    "ERR_CACHE_002": "Cache corrompido. Sincronizando novamente.",
    
    # Arquivos
    "ERR_FILE_001": "Erro ao ler arquivo de configuração.",
    "ERR_FILE_002": "Erro ao salvar dados. Verifique as permissões.",
    
    # Operações
    "ERR_OP_001": "Operação não pôde ser concluída. Tente novamente.",
    "ERR_OP_002": "Falha ao processar sua solicitação. Contate o suporte.",
}

# ==================== Mapeamento de erros específicos para códigos ====================
ERROR_CODE_MAPPING = {
    # Oracle
    "ORA-02391": "ERR_DB_002",  # SESSIONS_PER_USER limit exceeded
    "ORA-12541": "ERR_CONNECTION_001",  # TNS:no listener
    "ORA-12170": "ERR_CONNECTION_002",  # TNS:Connect timeout occurred
    "ORA-12514": "ERR_CONNECTION_003",  # TNS:listener does not currently know of service
    "ORA-01017": "ERR_DB_001",  # invalid username/password
    "ORA-00942": "ERR_DB_004",  # table or view does not exist
    "ORA-04068": "ERR_DB_005",  # existing state of packages has been discarded
    "ORA-03135": "ERR_CONNECTION_002",  # connection lost contact
    "ORA-00054": "ERR_OP_001",  # resource busy
    "ORA-30006": "ERR_OP_002",  # resource busy
    
    # LDAP
    "LDAP_INVALID_CREDENTIALS": "ERR_AD_002",
    "LDAP_TIMEOUT": "ERR_AD_003",
    "LDAP_NOT_FOUND": "ERR_AD_004",
    
    # Python
    "KeyError": "ERR_CACHE_001",
    "FileNotFoundError": "ERR_FILE_001",
    "PermissionError": "ERR_FILE_002",
    "JSONDecodeError": "ERR_CACHE_002",
    "ConnectionError": "ERR_CONNECTION_001",
    "TimeoutError": "ERR_CONNECTION_002",
}

# ==================== MENSAGENS GENÉRICAS ====================
GENERIC_MESSAGES = {
    "SUCCESS_LOAD": "Dados carregados com sucesso!",
    "SUCCESS_SAVE": "Dados salvos com sucesso!",
    "SUCCESS_DELETE": "Registro removido com sucesso!",
    "SUCCESS_UPDATE": "Atualização realizada com sucesso!",
    "LOADING": "Carregando, aguarde...",
    "PROCESSING": "Processando sua solicitação...",
    "DEFAULT_ERROR": "Ocorreu um erro inesperado. Nossa equipe já foi notificada.",
    "DEVELOPER_ERROR": "Erro interno. Código: {code} - Contate o suporte.",
}

# ==================== FUNÇÃO PRINCIPAL ====================
def get_error_message(error_key_or_code, default=None):
    """
    Retorna a mensagem de erro apropriada.
    
    Args:
        error_key_or_code: Pode ser:
            - Chave de erro do usuário (ex: "AUTH_FAILED")
            - Código do sistema (ex: "ERR_DB_002")
            - Erro específico do banco (ex: "ORA-02391")
            - Exceção Python (ex: "KeyError")
        default: Mensagem padrão caso não encontre
    
    Returns:
        Mensagem de erro amigável
    """
    # 1. Verifica se é erro do usuário
    if error_key_or_code in USER_ERROR_MESSAGES:
        return USER_ERROR_MESSAGES[error_key_or_code]
    
    # 2. Verifica se é código de sistema
    if error_key_or_code in SYSTEM_ERROR_CODES:
        return SYSTEM_ERROR_CODES[error_key_or_code]
    
    # 3. Verifica se é erro mapeado (ORA-XXXXX, LDAP_XXX, etc)
    if error_key_or_code in ERROR_CODE_MAPPING:
        mapped_code = ERROR_CODE_MAPPING[error_key_or_code]
        if mapped_code in SYSTEM_ERROR_CODES:
            return SYSTEM_ERROR_CODES[mapped_code]
    
    # 4. Verifica se é um erro conhecido pelo prefixo
    if isinstance(error_key_or_code, str):
        # Erros Oracle
        if error_key_or_code.startswith("ORA-"):
            return SYSTEM_ERROR_CODES.get("ERR_DB_001", "Erro no banco de dados. Tente novamente.")
        # Erros LDAP
        if error_key_or_code.startswith("LDAP_"):
            return SYSTEM_ERROR_CODES.get("ERR_AD_001", "Erro no Active Directory.")
    
    # 5. Retorna mensagem padrão
    return default or GENERIC_MESSAGES["DEFAULT_ERROR"]

# ==================== FUNÇÃO PARA LOG DE ERROS (DESENVOLVEDOR) ====================
def log_error_for_developer(error_code, exception, context=None):
    """
    Registra erro detalhado para debug do desenvolvedor.
    Não exibe para o usuário final.
    """
    import traceback
    from datetime import datetime
    
    error_log = {
        "timestamp": datetime.now().isoformat(),
        "error_code": error_code,
        "error_type": type(exception).__name__,
        "error_message": str(exception),
        "context": context,
        "traceback": traceback.format_exc()
    }
    
    # Aqui você pode salvar em arquivo de log
    # ou enviar para um serviço de monitoramento
    print(f"[DEV_ERROR] {error_log}")
    
    return error_log

# ==================== FUNÇÃO PARA EXIBIR ERRO AO USUÁRIO ====================
def show_user_error(error_key_or_code, exception=None, context=None):
    """
    Retorna erro amigável para o usuário e registra erro detalhado para o dev.
    """
    # Se tem exceção, registra para o desenvolvedor
    if exception:
        log_error_for_developer(error_key_or_code, exception, context)
    
    # Retorna mensagem amigável para o usuário
    return get_error_message(error_key_or_code)

# ==================== DICIONÁRIO COMPLETO DE ERROS ====================
ERRORS_DICTIONARY = {
    # Categoria: Autenticação
    "authentication": {
        "AUTH_FAILED": USER_ERROR_MESSAGES["AUTH_FAILED"],
        "AUTH_DISABLED": USER_ERROR_MESSAGES["AUTH_DISABLED"],
        "AUTH_NOT_AUTHORIZED": USER_ERROR_MESSAGES["AUTH_NOT_AUTHORIZED"],
        "AUTH_AD_INACTIVE": USER_ERROR_MESSAGES["AUTH_AD_INACTIVE"],
        "AUTH_SESSION_EXPIRED": USER_ERROR_MESSAGES["AUTH_SESSION_EXPIRED"],
    },
    # Categoria: Permissões
    "permissions": {
        "PERMISSION_DENIED": USER_ERROR_MESSAGES["PERMISSION_DENIED"],
        "ADMIN_REQUIRED": USER_ERROR_MESSAGES["ADMIN_REQUIRED"],
        "NO_FILAS": USER_ERROR_MESSAGES["NO_FILAS"],
    },
    # Categoria: Dados
    "data": {
        "NO_DATA": USER_ERROR_MESSAGES["NO_DATA"],
        "NO_SEARCH_RESULTS": USER_ERROR_MESSAGES["NO_SEARCH_RESULTS"],
    },
    # Categoria: Sistema
    "system": SYSTEM_ERROR_CODES,
    # Categoria: Mapeamento de erros específicos
    "mapping": ERROR_CODE_MAPPING,
    # Categoria: Mensagens genéricas
    "generic": GENERIC_MESSAGES,
}