"""Como citar: a fonte original primeiro, o Observatório como organizador."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from . import _client
from .data import CITATION, SOURCE_CITATION


def condepe_cite(x: pd.DataFrame | str | Iterable[str] | None = None) -> pd.Series | str:
    """Citação dos dados: a fonte original primeiro, o Observatório como organizador.

    Os números do Observatório são das fontes originais (IBGE, Ministério da
    Saúde, INEP, ...); a Condepe/Fidem os coleta, padroniza e organiza.

    Parameters
    ----------
    x:
        Um resultado de :func:`condepe_data` ou :func:`condepe_series` — também
        depois de filtrar ou concatenar: a citação sai das colunas
        ``id_fonte`` e ``fonte_original``, uma por fonte presente; ou um ou
        mais identificadores de fonte, procurados no catálogo; ou nada, para a
        citação do acervo inteiro.

    Returns
    -------
    pandas.Series | str
        Uma citação por fonte, indexada pelo ``id_fonte``; ou, sem ``x``, a
        citação do acervo.

    Examples
    --------
    >>> condepe_data("sidra_populacao_estimada").pipe(condepe_cite)  # doctest: +SKIP
    >>> condepe_cite("datasus_sinasc")                              # doctest: +SKIP
    >>> condepe_cite()                                              # doctest: +SKIP
    """
    if x is None:
        return CITATION.format(version=_client.catalog_json()["versao"])
    if isinstance(x, pd.DataFrame):
        if not {"id_fonte", "fonte_original"} <= set(x.columns):
            raise ValueError("`x` must have the columns `id_fonte` and `fonte_original`.")
        pares = x[["id_fonte", "fonte_original"]].drop_duplicates()
        versao = x.attrs.get("version") or (_client.catalog_json()["versao"] if len(pares) else "")
        entradas = pares.to_dict("records")
    else:
        ids = [x] if isinstance(x, str) else list(dict.fromkeys(x))
        cat = _client.catalog_json()
        por_id = {f["id_fonte"]: f for f in cat["fontes"]}
        desconhecidas = [i for i in ids if i not in por_id]
        if desconhecidas:
            raise ValueError(f"Unknown source(s): {', '.join(desconhecidas)}.")
        entradas = [por_id[i] for i in ids]
        versao = cat["versao"]
    return pd.Series(
        [
            SOURCE_CITATION.format(
                fonte_original=e["fonte_original"], id_fonte=e["id_fonte"], version=versao
            )
            for e in entradas
        ],
        index=pd.Index([e["id_fonte"] for e in entradas], name="id_fonte"),
        name="citacao",
        dtype=object,
    )
