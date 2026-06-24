# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# ==================== CONFIGURAÇÕES DO ACTIVE DIRECTORY ====================
# FALLBACK: Se não ler do .env, usa valores diretos (como funcionava antes)
AD_SERVER = os.getenv('AD_SERVER') or '0.0.0.0.0.0.'
AD_PORT = int(os.getenv('AD_PORT', 2222))
AD_DOMAIN = 'detran'
AD_USER = os.getenv('ADMIN_EMAIL') or 'gabriel.powerbi'
AD_PASSWORD = os.getenv('ADMIN_PASSWORD') or 'OCULTA'

# ==================== CONFIGURAÇÕES DO ORACLE ====================
ORACLE_USER = os.getenv('ORACLE_USER')
ORACLE_PASSWORD = os.getenv('ORACLE_PASSWORD')
ORACLE_DSN = os.getenv('ORACLE_DSN')

# ==================== CONFIGURAÇÕES DE EMAIL ====================
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_HOST = os.getenv('SMTP_HOST', 'gabriel.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 2222))

# ==================== ADMIN PADRÃO ====================
# CORRIGIDO: Define admin_email antes de usar
admin_email = AD_USER  # Usa o AD_USER que já foi definido

if admin_email and '\\' in admin_email:
    ADMIN_USER = admin_email.split('\\')[-1].lower()
else:
    ADMIN_USER = admin_email.lower() if admin_email else 'admin'

# ==================== MAPEAMENTO DE STATUS ====================
STATUS_MAP = {
    0: "Novo",
    1: "Designado",
    2: "Em Progresso",
    3: "Pendente",
    4: "Resolvido",
    5: "Fechado",
    6: "Cancelado"
}

# ==================== MAPEAMENTO DE CRITICIDADE ====================
CRITICALITY_MAP = {
    1000: "Crítico",
    2000: "Alto",
    3000: "Médio",
    4000: "Baixo"
}

# Debug: imprime as configurações (remove depois)
print(f"✅ Config carregada: AD_SERVER={AD_SERVER}, AD_USER={AD_USER}")