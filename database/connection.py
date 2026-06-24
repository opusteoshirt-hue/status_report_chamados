# database/connection.py
import oracledb
import os
from dotenv import load_dotenv

# Carregar variaveis do arquivo .env
load_dotenv()

def get_connection():
    try:
        # Usar as variaveis corretas do .env
        user = os.getenv("ORACLE_USER")
        password = os.getenv("ORACLE_PASSWORD")
        dsn = os.getenv("ORACLE_DSN")
        
        print(f"Conectando com usuario: {user}")
        print(f"DSN: {dsn}")
        
        connection = oracledb.connect(
            user=user,
            password=password,
            dsn=dsn
        )
        return connection
    except oracledb.Error as e:
        print(f"Erro ao conectar: {e}")
        raise