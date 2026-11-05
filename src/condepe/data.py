"""Public functions: catalogue, indicators, full sources, series, localities.

Every source of the Observatory is published in the same long format (one
observation per row, 15 columns). Column names are kept in Portuguese, as
published, so results stay traceable to the official files.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from . import _client, _msg

CITATION = (
    "Condepe/Fidem, Observatório de Pernambuco — Base de Dados do Estado, "
    "version {version}, https://cf.pe.gov.br/observatorio (CC BY 4.0)."
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
    """List the sources published by the Observatory.

    Parameters
    ----------
    refresh:
        Ignore the cached catalogue (trusted for 6 hours) and ask the server.

    Returns
    -------
    pandas.DataFrame
        One row per source (``id_fonte``) with axis, theme, description,
        original publisher, number of rows, indicators and localities, and the
        years covered. ``attrs["version"]`` holds the catalogue version.
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
    """Download a whole source (all indicators, localities and periods).

    The Parquet file is kept in the disk cache for the current catalogue
    version and verified against the sha256 published in the catalogue.

    Parameters
    ----------
    source:
        Source id, e.g. ``"sidra_populacao_estimada"`` (see
        :func:`condepe_catalog`).
    refresh:
        Download again even if a verified copy is cached.

    Returns
    -------
    pandas.DataFrame
        The 15 columns of the Observatory long format: ``cd_municipio_ibge``,
        ``nm_municipio``, ``ano``, ``mes``, ``indicador``, ``indicador_base``,
        ``valor``, ``unidade``, ``natureza``, ``id_fonte``, ``eixo``, ``tema``,
        ``assunto``, ``fonte_original``, ``arquivo_origem``.
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
    _msg.success(f"{source}: {len(df):,} observations (version {cat['versao']}).")
    return df


def condepe_indicators(source: str, refresh: bool = False) -> pd.DataFrame:
    """List the indicators of a source, with unit, coverage and periodicity.

    Parameters
    ----------
    source:
        Source id (see :func:`condepe_catalog`).
    refresh:
        Download the source again even if a verified copy is cached.

    Returns
    -------
    pandas.DataFrame
        One row per ``indicador_base`` with ``unidade``, ``natureza``,
        ``mensal`` (monthly series), number of observations and localities,
        and first/last year.
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
    """Series of one or more indicators, optionally filtered by place and year.

    Parameters
    ----------
    source:
        Source id (see :func:`condepe_catalog`).
    indicator:
        One or more ``indicador_base`` values, exactly as listed by
        :func:`condepe_indicators`.
    code:
        IBGE codes: 7 digits for municipalities, ``"26"`` for the State.
        ``None`` keeps every locality.
    years:
        A year or a collection of years; ``None`` keeps all.

    Returns
    -------
    pandas.DataFrame
        The matching observations, sorted by locality, year and month.
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
    """The 185 municipalities of Pernambuco and the State, with IBGE codes.

    Taken from the population estimates source, which covers every
    municipality (Fernando de Noronha included); the State (``"26"``) comes
    first.

    Parameters
    ----------
    refresh:
        Download the source again even if a verified copy is cached.

    Returns
    -------
    pandas.DataFrame
        ``cd_municipio_ibge`` and ``nm_municipio``.
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
