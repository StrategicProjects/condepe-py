"""Funções públicas: catálogo, indicadores, fontes inteiras, séries, localidades.

Toda fonte do Observatório é publicada no mesmo formato longo (uma observação
por linha, 15 colunas). Os nomes das colunas ficam em português, como
publicados, para que os resultados possam ser rastreados até os arquivos
oficiais.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from . import _client, _msg

# Os números são das fontes originais; a Condepe/Fidem os coleta, padroniza
# e organiza. A citação põe a fonte original primeiro.
CITATION = (
    "Fontes originais indicadas em cada série (coluna fonte_original); dados "
    "coletados, padronizados e organizados pela Condepe/Fidem no Observatório "
    "de Pernambuco, versão {version}, https://cf.pe.gov.br/observatorio."
)
SOURCE_CITATION = (
    "{fonte_original}. Dados organizados pela Condepe/Fidem no Observatório de "
    "Pernambuco (fonte {id_fonte}), versão {version}, "
    "https://cf.pe.gov.br/observatorio/fontes/{id_fonte}."
)

_CATALOG_COLUMNS = [
    "id_fonte",
    "eixo",
    "tema",
    "assunto",
    "descricao",
    "fonte_original",
    "linhas",
    "indicadores",
    "localidades",
    "ano_inicio",
    "ano_fim",
]


def condepe_catalog(refresh: bool = False) -> pd.DataFrame:
    """Fontes publicadas pelo Observatório.

    Parameters
    ----------
    refresh:
        Ignora o catálogo em cache (válido por 6 horas) e consulta o servidor.

    Returns
    -------
    pandas.DataFrame
        Uma linha por fonte (``id_fonte``), com eixo, tema, descrição, órgão
        de origem, número de linhas, de indicadores e de localidades, e os
        anos cobertos. ``attrs["version"]`` traz a versão do catálogo e
        ``attrs["citation"]``, a citação.
    """
    cat = _client.catalog_json(refresh=refresh)
    df = pd.DataFrame([{k: f.get(k) for k in _CATALOG_COLUMNS} for f in cat["fontes"]])
    df.attrs["version"] = cat["versao"]
    df.attrs["citation"] = CITATION.format(version=cat["versao"])
    return df


def _source_entry(source: str, cat: dict[str, Any]) -> dict[str, Any]:
    for f in cat["fontes"]:
        if f["id_fonte"] == source:
            return f
    raise ValueError(
        f"Unknown source {source!r}. See condepe_catalog() for the {len(cat['fontes'])} available."
    )


def condepe_data(source: str, refresh: bool = False) -> pd.DataFrame:
    """Uma fonte inteira (todos os indicadores, localidades e períodos).

    O arquivo Parquet fica no cache em disco para a versão corrente do
    catálogo e é conferido pelo SHA-256 publicado no catálogo.

    Parameters
    ----------
    source:
        Identificador da fonte, por exemplo ``"sidra_populacao_estimada"``
        (veja :func:`condepe_catalog`).
    refresh:
        Baixa de novo mesmo que haja cópia conferida em cache.

    Returns
    -------
    pandas.DataFrame
        As 15 colunas do formato longo do Observatório: ``cd_municipio_ibge``,
        ``nm_municipio``, ``ano``, ``mes``, ``indicador``, ``indicador_base``,
        ``valor``, ``unidade``, ``natureza``, ``id_fonte``, ``eixo``, ``tema``,
        ``assunto``, ``fonte_original``, ``arquivo_origem``. Séries mensais
        trazem o período em ``indicador`` (``"… [MM/AAAA]"``) e em ``mes``.
        ``attrs["citation"]`` traz a citação da fonte original, com o
        Observatório como organizador.
    """
    cat = _client.catalog_json(refresh=refresh)
    entry = _source_entry(source, cat)
    parquet = next((a for a in entry.get("arquivos", []) if a.get("formato") == "parquet"), None)
    if parquet is None:
        raise _client.CondepeError(f"Source {source!r} has no Parquet file in the catalogue.")
    path = _client.cached_file(
        parquet["caminho"], parquet["sha256"], cat["versao"], refresh=refresh
    )
    df = pq.read_table(path).to_pandas()
    df.attrs["version"] = cat["versao"]
    df.attrs["source"] = source
    df.attrs["citation"] = SOURCE_CITATION.format(
        fonte_original=entry.get("fonte_original", ""), id_fonte=source, version=cat["versao"]
    )
    _msg.success(f"{source}: {len(df):,} observations (version {cat['versao']}).")
    return df


def condepe_indicators(source: str, refresh: bool = False) -> pd.DataFrame:
    """Indicadores de uma fonte, com unidade, cobertura e periodicidade.

    Parameters
    ----------
    source:
        Identificador da fonte (veja :func:`condepe_catalog`).
    refresh:
        Baixa a fonte de novo mesmo que haja cópia conferida em cache.

    Returns
    -------
    pandas.DataFrame
        Uma linha por ``indicador_base``, com ``unidade``, ``natureza``,
        ``mensal`` (série mensal), número de observações e de localidades, e
        primeiro e último ano.
    """
    df = condepe_data(source, refresh=refresh)
    out = (
        df.groupby("indicador_base", sort=True)
        .agg(
            unidade=("unidade", "first"),
            natureza=("natureza", "first"),
            mensal=("mes", lambda s: bool(s.notna().any())),
            observacoes=("valor", "size"),
            localidades=("cd_municipio_ibge", "nunique"),
            ano_inicio=("ano", "min"),
            ano_fim=("ano", "max"),
        )
        .reset_index()
    )
    out.attrs = dict(df.attrs)
    return out


def _as_list(x: str | Iterable[str] | None) -> list[str] | None:
    if x is None:
        return None
    return [x] if isinstance(x, str) else [str(v) for v in x]


def condepe_series(
    source: str,
    indicator: str | Iterable[str],
    code: str | Iterable[str] | None = None,
    years: int | Iterable[int] | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Série de um ou mais indicadores, filtrada por localidade e ano se pedido.

    Parameters
    ----------
    source:
        Identificador da fonte (veja :func:`condepe_catalog`).
    indicator:
        Um ou mais valores de ``indicador_base``, exatamente como listados por
        :func:`condepe_indicators`.
    code:
        Códigos IBGE: 7 dígitos para municípios, ``"26"`` para o Estado.
        ``None`` mantém todas as localidades.
    years:
        Um ano ou uma coleção de anos; ``None`` mantém todos.
    refresh:
        Baixa a fonte de novo mesmo que haja cópia conferida em cache.

    Returns
    -------
    pandas.DataFrame
        As observações que atendem aos filtros, ordenadas por localidade, ano
        e mês.
    """
    df = condepe_data(source, refresh=refresh)
    wanted = _as_list(indicator) or []
    missing = sorted(set(wanted) - set(df["indicador_base"].unique()))
    if missing:
        raise ValueError(
            f"Indicator(s) not in {source!r}: {missing}. See condepe_indicators({source!r})."
        )
    keep = df["indicador_base"].isin(wanted)
    codes = _as_list(code)
    if codes is not None:
        keep &= df["cd_municipio_ibge"].isin(codes)
    if years is not None:
        ys = [years] if isinstance(years, int) else list(years)
        keep &= df["ano"].isin(ys)
    out = df[keep].sort_values(["cd_municipio_ibge", "ano", "mes"], na_position="first")
    out = out.reset_index(drop=True)
    out.attrs = dict(df.attrs)
    if out.empty:
        _msg.step("No observations match these filters.")
    return out


def condepe_localities(refresh: bool = False) -> pd.DataFrame:
    """Os 185 municípios de Pernambuco e o Estado, com código IBGE.

    Tirados da fonte de estimativas de população, que cobre todos os
    municípios (Fernando de Noronha incluído); o Estado (``"26"``) vem
    primeiro.

    Parameters
    ----------
    refresh:
        Baixa a fonte de novo mesmo que haja cópia conferida em cache.

    Returns
    -------
    pandas.DataFrame
        ``cd_municipio_ibge`` e ``nm_municipio``.
    """
    df = condepe_data("sidra_populacao_estimada", refresh=refresh)
    out = (
        df[["cd_municipio_ibge", "nm_municipio"]]
        .drop_duplicates()
        .sort_values("cd_municipio_ibge")
        .reset_index(drop=True)
    )
    if not (out["cd_municipio_ibge"] == "26").any():
        out = pd.concat(
            [pd.DataFrame({"cd_municipio_ibge": ["26"], "nm_municipio": ["Pernambuco"]}), out],
            ignore_index=True,
        )
    out.attrs = dict(df.attrs)
    return out
