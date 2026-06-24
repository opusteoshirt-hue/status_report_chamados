# database/queries.py

INCIDENTES_SQL = """
SELECT
    Incident_Number              AS CHAMADOS,
    Description                  AS TITULO,
    Status                       AS STATUS,
    Submit_Date                  AS DATA_CRIACAO,
    Last_Modified_Date          AS ULTIMA_MODIFICACAO,
    Last_Resolved_Date          AS DATA_RESOLUCAO,
    Responded_Date              AS DATA_RESPOSTA_RAW,
    Assigned_Support_Organization AS GRUPO_SUPORTE,
    Assignee                    AS DESIGNADO,
    First_Name                  AS CLIENTE_NOME,
    Last_Name                   AS CLIENTE_SOBRENOME,
    Detailed_decription         AS DESCRICAO_DETALHADA,
    SRID                        AS REQ,
    Categorization_Tier_1      AS CATEGORIA_1,
    Categorization_Tier_2      AS CATEGORIA_2,
    Categorization_Tier_3      AS CATEGORIA_3,
    Urgency                    AS CRITICIDADE_URGENCIA,
    Impact                     AS CRITICIDADE_IMPACTO
FROM (SCHEMA_NAME).INCIDENT)
WHERE Submit_Date >= 1640995200
   OR Last_Resolved_Date >= 1640995200
"""