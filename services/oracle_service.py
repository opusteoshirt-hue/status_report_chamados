# services/oracle_service.py
from database.connection import get_connection
import pandas as pd

def executar_query_incidentes():
    """
    Consulta de Incidentes
    """
    conn = get_connection()
    
    sql = """
    SELECT 
        INCIDENT_NUMBER AS CHAMADOS,
        DESCRIPTION AS TITULO,
        STATUS AS STATUS,
        SUBMIT_DATE AS DATA_SISTEMA,
        REPORTED_DATE AS DATA_CRIACAO,
        LAST_MODIFIED_DATE AS ULTIMA_MODIFICACAO,
        LAST_RESOLVED_DATE AS DATA_RESOLUCAO,
        RESPONDED_DATE AS DATA_RESPOSTA_RAW,
        FIRSTWIPDATE AS DATA_INICIO_ATENDIMENTO,
        LASTWIPDATE AS DATA_FIM_ATENDIMENTO,
        LAST__ASSIGNED_DATE AS DATA_DESIGNACAO,
        ASSIGNED_SUPPORT_ORGANIZATION AS GRUPO_SUPORTE,
        ASSIGNEE AS DESIGNADO,
        FIRST_NAME AS CLIENTE_NOME,
        LAST_NAME AS CLIENTE_SOBRENOME,
        SRID AS REQ,
        ASSIGNED_GROUP AS FILA,
        CATEGORIZATION_TIER_1 AS CATEGORIA_1,
        CATEGORIZATION_TIER_2 AS CATEGORIA_2,
        CATEGORIZATION_TIER_3 AS CATEGORIA_3,
        URGENCY AS CRITICIDADE_URGENCIA,
        IMPACT AS CRITICIDADE_IMPACTO,
        TOTAL_TIME_SPENT,
        EFFORT_TIME_SPENT_MINUTES,
        TOTAL_TRANSFERS,
        GROUP_TRANSFERS,
        INDIVIDUAL_TRANSFERS,
        KICKBACK_COUNT,
        RE_OPENED_DATE,
        NEXT_TARGET_DATE AS SLA_PRAZO_LIMITE,
        DETRAN_QTD_ATIV_EXEC
    FROM (schema_name).INCIDENT
    WHERE SUBMIT_DATE >= 1640995200
       OR LAST_RESOLVED_DATE >= 1640995200
    """
    
    try:
        df = pd.read_sql(sql, conn)
        print(f"✅ Incidentes carregados: {len(df)}")
        return df
    except Exception as e:
        print(f"❌ Erro ao carregar incidentes: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def executar_query_workorders():
    """
    Consulta de Work Orders
    """
    conn = get_connection()
    
    sql = """
    SELECT 
        WORK_ORDER_ID AS CHAMADOS,
        SUMMARY AS TITULO,
        STATUS AS STATUS,
        SUBMIT_DATE AS DATA_SISTEMA,
        SUBMIT_DATE AS DATA_CRIACAO,
        LAST_MODIFIED_DATE AS ULTIMA_MODIFICACAO,
        COMPLETED_DATE AS DATA_RESOLUCAO,
        ACTUAL_START_DATE AS DATA_INICIO_ATENDIMENTO,
        ACTUAL_END_DATE AS DATA_FIM_ATENDIMENTO,
        SUPPORT_GROUP_NAME AS GRUPO_SUPORTE,
        REQUEST_ASSIGNEE AS DESIGNADO,
        FIRST_NAME AS CLIENTE_NOME,
        LAST_NAME AS CLIENTE_SOBRENOME,
        SRID AS REQ,
        ASGRP AS FILA,
        CATEGORIZATION_TIER_1 AS CATEGORIA_1,
        CATEGORIZATION_TIER_2 AS CATEGORIA_2,
        CATEGORIZATION_TIER_3 AS CATEGORIA_3,
        CASE PRIORITY
            WHEN 0 THEN 1000
            WHEN 1 THEN 2000
            WHEN 2 THEN 3000
            WHEN 3 THEN 4000
            ELSE 3000
        END AS CRITICIDADE_URGENCIA,
        NULL AS CRITICIDADE_IMPACTO,
        ACTIVE_TASKS,
        ABYDOS_TASKS_GENERATED,
        NEXT_TARGET_DATE AS SLA_PRAZO_LIMITE,
        DETRAN_QTD_ATIV_EXEC
    FROM (schema_name).WORK_ORDER
    WHERE SUBMIT_DATE >= 1640995200
    """
    
    try:
        df = pd.read_sql(sql, conn)
        print(f"✅ Work Orders carregados: {len(df)}")
        return df
    except Exception as e:
        print(f"❌ Erro ao carregar work orders: {e}")
        return pd.DataFrame()
    finally:
        conn.close()