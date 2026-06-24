# services/transform.py
import pandas as pd

# ──────────────────────────────────────────────
# Mapeamentos de domínio
# ──────────────────────────────────────────────

STATUS_MAP_INCIDENTE = {
    0: "Novo",
    1: "Designado",
    2: "Em Progresso",
    3: "Pendente",
    4: "Resolvido",
    5: "Fechado",
    6: "Cancelado",
}

STATUS_MAP_WO = {
    0: "Designado",
    1: "Pendente",
    2: "Aguardando Aprovacao",
    3: "Planejamento",
    4: "Em Progresso",
    5: "Concluido",
    6: "Rejeitado",
    7: "Cancelado",
    8: "Fechado",
}

CRITICALITY_MAP = {
    1000: "Crítico",
    2000: "Alto",
    3000: "Médio",
    4000: "Baixo",
}

STATUS_MAP_SLA = {
    0:  "Inativo",
    1:  "Ativo",
    2:  "Suspendo",
    3:  "Concluído",
    4:  "Violado",
}

ORIGEM_MAP = {
    1000: "Direct Input",
    2000: "E-mail",
    3000: "External Escalation",
    4000: "Fax",
    5000: "Self Service",
    6000: "Systems Management",
    7000: "Phone",
    8000: "Voice Mail",
    9000: "Web",
    10000: "Chat",
}

# ──────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────

# Colunas de data presentes nos dois tipos de chamado
_COLUNAS_DATA = [
    "DATA_CRIACAO",
    "DATA_SISTEMA",
    "ULTIMA_MODIFICACAO",
    "DATA_RESOLUCAO",
    "DATA_RESPOSTA_RAW",
    "DATA_INICIO_ATENDIMENTO",
    "DATA_FIM_ATENDIMENTO",
    "DATA_PRAZO_SLA",
    "DATA_RESOLUCAO_ALVO",
    "DATA_REABERTURA",
]

_COLUNAS_DATA_SLA = [
    "SLA_DATA_INICIO",
    "SLA_DATA_PRAZO",
    "SLA_DATA_CONCLUSAO",
]


def _converter_timestamps(df: pd.DataFrame, colunas: list, offset_horas: int = -3) -> pd.DataFrame:
    """Converte colunas Unix-timestamp para datetime com offset de fuso horário."""
    for col in colunas:
        if col not in df.columns:
            continue
        serie = df[col]
        if serie.isna().all():
            continue
        # Se já for datetime, apenas aplica o offset
        if pd.api.types.is_datetime64_any_dtype(serie):
            df[col] = serie + pd.Timedelta(hours=offset_horas)
        else:
            df[col] = (
                pd.to_datetime(serie, unit="s", errors="coerce")
                + pd.Timedelta(hours=offset_horas)
            )
    return df


def _calcular_tempo_minutos(df: pd.DataFrame, col_inicio: str, col_fim: str, col_destino: str) -> pd.DataFrame:
    """Calcula diferença em minutos entre duas colunas datetime (inteiro, >= 0)."""
    if col_inicio not in df.columns or col_fim not in df.columns:
        return df
    tempo = (df[col_fim] - df[col_inicio]).dt.total_seconds() / 60
    df[col_destino] = tempo.where(tempo > 0, 0).fillna(0).astype(int)
    return df


# ──────────────────────────────────────────────
# Funções públicas
# ──────────────────────────────────────────────

def tratar_incidentes(df: pd.DataFrame, tipo: str = "incidente") -> pd.DataFrame:
    """
    Trata e enriquece o DataFrame de incidentes ou work orders.
    Mantém todos os aliases originais; apenas adiciona novas colunas derivadas.
    """
    if df is None or df.empty:
        return df

    # 1. Converter timestamps
    df = _converter_timestamps(df, _COLUNAS_DATA)

    # 2. Nome completo do cliente (original)
    if "CLIENTE_NOME" in df.columns and "CLIENTE_SOBRENOME" in df.columns:
        df["CLIENTE"] = (
            df["CLIENTE_NOME"].fillna("") + " " + df["CLIENTE_SOBRENOME"].fillna("")
        ).str.strip().replace("", "Nao Informado")

    # 3. Status descritivo (original)
    if "STATUS" in df.columns:
        mapa = STATUS_MAP_INCIDENTE if tipo == "incidente" else STATUS_MAP_WO
        df["STATUS_DESC"] = df["STATUS"].map(mapa).fillna("Nao Definido")

    # 4. Criticidade descritiva (original)
    if "CRITICIDADE_URGENCIA" in df.columns:
        df["CRITICIDADE_DESC"] = df["CRITICIDADE_URGENCIA"].map(CRITICALITY_MAP).fillna("Nao Definido")

    # 5. Tempo de solução em minutos (original)
    df = _calcular_tempo_minutos(df, "DATA_SISTEMA", "DATA_RESOLUCAO", "TEMPO_SOLUCAO_MIN")

    # ── Novos campos derivados ────────────────

    # 6. Tempo até primeiro atendimento (abertura → início atendimento)
    df = _calcular_tempo_minutos(
        df, "DATA_CRIACAO", "DATA_INICIO_ATENDIMENTO", "TEMPO_PRIMEIRO_ATEND_MIN"
    )

    # 7. Tempo de atendimento efetivo (início → fim atendimento)
    df = _calcular_tempo_minutos(
        df, "DATA_INICIO_ATENDIMENTO", "DATA_FIM_ATENDIMENTO", "TEMPO_ATENDIMENTO_MIN"
    )

    # 8. Violação de SLA: compara prazo com data de resolução
    if "DATA_PRAZO_SLA" in df.columns and "DATA_RESOLUCAO" in df.columns:
        prazo = pd.to_datetime(df["DATA_PRAZO_SLA"], errors="coerce")
        resolucao = pd.to_datetime(df["DATA_RESOLUCAO"], errors="coerce")
        df["SLA_VIOLADO_CALC"] = (resolucao > prazo).map(
            {True: "Sim", False: "Não"}
        ).where(prazo.notna() & resolucao.notna(), "Indefinido")

    # 9. Minutos de atraso em relação ao prazo (negativo = dentro do prazo)
    if "DATA_PRAZO_SLA" in df.columns and "DATA_RESOLUCAO" in df.columns:
        prazo = pd.to_datetime(df["DATA_PRAZO_SLA"], errors="coerce")
        resolucao = pd.to_datetime(df["DATA_RESOLUCAO"], errors="coerce")
        df["SLA_ATRASO_MIN"] = (
            (resolucao - prazo).dt.total_seconds() / 60
        ).where(prazo.notna() & resolucao.notna()).fillna(0).astype(int)

    # 10. Descrição da origem
    if "ORIGEM" in df.columns:
        df["ORIGEM_DESC"] = df["ORIGEM"].map(ORIGEM_MAP).fillna(df["ORIGEM"].astype(str))

    # 11. Tipo de chamado (original)
    df["TIPO_CHAMADO"] = tipo.upper()

    # 12. Remover colunas de índice sequencial (original)
    colunas_remover = ["INDEX", "LEVEL", "UNIQUE_ID", "SEQ_NUM", "ROW_NUM"]
    df = df.drop(columns=[c for c in colunas_remover if c in df.columns])

    return df


def tratar_sla(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trata o DataFrame retornado por executar_query_sla().
    """
    if df is None or df.empty:
        return df

    df = _converter_timestamps(df, _COLUNAS_DATA_SLA)

    # Status descritivo
    if "SLA_STATUS" in df.columns:
        df["SLA_STATUS_DESC"] = df["SLA_STATUS"].map(STATUS_MAP_SLA).fillna("Nao Definido")

    # Flag de violação legível
    if "SLA_VIOLADO" in df.columns:
        df["SLA_VIOLADO_DESC"] = df["SLA_VIOLADO"].map(
            {0: "Não", 1: "Sim", "0": "Não", "1": "Sim", True: "Sim", False: "Não"}
        ).fillna("Indefinido")

    # Meta em minutos (para facilitar comparações)
    if "SLA_META_SEGUNDOS" in df.columns:
        df["SLA_META_MIN"] = (df["SLA_META_SEGUNDOS"] / 60).fillna(0).astype(int)

    # Tempo gasto em minutos
    if "SLA_TEMPO_GASTO_SEG" in df.columns:
        df["SLA_TEMPO_GASTO_MIN"] = (df["SLA_TEMPO_GASTO_SEG"] / 60).fillna(0).astype(int)

    # Tempo restante em minutos
    if "SLA_TEMPO_RESTANTE_SEG" in df.columns:
        df["SLA_TEMPO_RESTANTE_MIN"] = (df["SLA_TEMPO_RESTANTE_SEG"] / 60).fillna(0).astype(int)

    return df


def combinar_dados(df_incidentes: pd.DataFrame, df_workorders: pd.DataFrame) -> pd.DataFrame:
    """Combina incidentes e work orders em um único DataFrame (original)."""
    if df_incidentes is None or df_incidentes.empty:
        return df_workorders
    if df_workorders is None or df_workorders.empty:
        return df_incidentes

    df_combinado = pd.concat([df_incidentes, df_workorders], ignore_index=True)

    if "CHAMADOS" in df_combinado.columns:
        df_combinado = df_combinado.sort_values("CHAMADOS", ascending=False)

    return df_combinado