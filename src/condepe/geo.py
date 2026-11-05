"""Malhas municipais (Condepe/Fidem e IBGE) e regionalizações de Pernambuco.

Espelha ``condepe_geometry()``, ``condepe_add_geometry()`` e
``condepe_regions()`` do pacote R. A tabela de regionalizações vai com o
pacote (``data/regioes.csv``, gerada pelo ``data-raw/regioes.R`` do
condepe-r a partir das fontes oficiais); as malhas são baixadas e ficam em
cache. ``geopandas`` é opcional (extra ``[geo]``) e só é exigido pelas
funções de malha.
"""

from __future__ import annotations

import hashlib
import io
import json
import warnings
from importlib import resources
from typing import TYPE_CHECKING, Any

import pandas as pd

from . import _client

if TYPE_CHECKING:  # pragma: no cover
    import geopandas as gpd

MALHA_URL = "https://cf.pe.gov.br/downloads/malha-municipal"
IBGE_MALHA_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/26"
NORONHA = "2605459"

LEVELS: dict[str, str] = {
    "rd": "Regiões de Desenvolvimento (Condepe/Fidem)",
    "mesorregiao": "Mesorregiões geográficas (IBGE)",
    "microrregiao": "Microrregiões geográficas (IBGE)",
    "regiao_intermediaria": "Regiões geográficas intermediárias (IBGE)",
    "regiao_imediata": "Regiões geográficas imediatas (IBGE)",
    "regiao_saude": "Regiões de saúde, as Geres (SES-PE, via base territorial do DATASUS)",
    "macrorregiao_saude": "Macrorregiões de saúde (SES-PE, via DATASUS)",
    "gre": "Gerências Regionais de Educação (SEE-PE; Recife Norte e Sul juntas)",
    "regiao_fiscal": "Regiões fiscais (SEFAZ-PE)",
    "dro": "Diretorias Regionais de Operações do DER-PE (Noronha é o 1º DOD)",
    "rm": "Regiões metropolitanas: RMR e RIDE Petrolina-Juazeiro",
}


def _gpd():
    try:
        import geopandas
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "As funções de malha precisam do geopandas: pip install 'condepe[geo]'"
        ) from exc
    return geopandas


def condepe_regions(level: str | None = None) -> pd.DataFrame:
    """Regionalizações dos municípios de Pernambuco.

    A que região pertence cada município em onze regionalizações oficiais:
    ``rd`` (Regiões de Desenvolvimento da Condepe/Fidem), ``mesorregiao``,
    ``microrregiao``, ``regiao_intermediaria`` e ``regiao_imediata`` (IBGE),
    ``regiao_saude`` e ``macrorregiao_saude`` (SES-PE), ``gre`` (Gerências
    Regionais de Educação da SEE-PE; Recife Norte e Recife Sul ficam juntas,
    porque dividem o mesmo município), ``regiao_fiscal`` (SEFAZ-PE), ``dro`` (Diretorias Regionais de
    Operações do DER-PE) e ``rm``
    (regiões metropolitanas). A tabela vai com o pacote, sem rede.

    Parameters
    ----------
    level:
        ``None`` (todas, uma coluna por regionalização) ou uma delas.

    Returns
    -------
    pandas.DataFrame
        ``cd_municipio_ibge``, ``nm_municipio`` e as colunas de região (ou só
        ``regiao``, se ``level`` for dado). Municípios fora de uma região
        metropolitana ficam com ``NA`` em ``rm``.

    Examples
    --------
    >>> condepe_regions("rd")["regiao"].nunique()
    13
    """
    with resources.files("condepe").joinpath("data/regioes.csv").open("rb") as f:
        r = pd.read_csv(f, dtype=str, keep_default_na=False, na_values=[""])
    if level is None:
        return r
    if level not in LEVELS:
        raise ValueError(f"`level` must be one of {', '.join(LEVELS)}.")
    out = r[["cd_municipio_ibge", "nm_municipio", level]].rename(columns={level: "regiao"})
    return out.reset_index(drop=True)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _malha_condepe(refresh: bool) -> gpd.GeoDataFrame:
    gpd = _gpd()
    manifesto = json.loads(_client._get(f"{MALHA_URL}/manifest.json"))
    atual = manifesto["atual"]
    versao = next((v for v in manifesto["versoes"] if v.get("id") == atual), None)
    arq = next((f for f in (versao or {}).get("formatos", []) if f.get("tipo") == "geojson"), None)
    if arq is None:
        raise _client.CondepeError(f"O manifesto da malha não traz o GeoJSON da edição {atual}.")
    dest = _client.cache_dir() / "malha" / atual / arq["arquivo"]
    if refresh or not dest.exists() or _sha256(dest.read_bytes()) != arq["sha256"]:
        raw = _client._get(f"{MALHA_URL}/{atual}/{arq['arquivo']}")
        if _sha256(raw) != arq["sha256"]:
            raise _client.IntegrityError(
                f"A malha {arq['arquivo']} não confere com o SHA-256 do manifesto."
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    m = gpd.read_file(io.BytesIO(dest.read_bytes()))
    out = gpd.GeoDataFrame(
        {
            "cd_municipio_ibge": m["cod_munici"].astype(str),
            "nm_municipio": m["nom_munici"].astype(str),
        },
        geometry=m.geometry.values,
        crs=m.crs,
    )
    out = out.sort_values("cd_municipio_ibge").reset_index(drop=True)
    out.attrs["version"] = atual
    out.attrs["source"] = "Condepe/Fidem, Malha Municipal de Pernambuco"
    return out


def _malha_ibge(quality: str, refresh: bool) -> gpd.GeoDataFrame:
    gpd = _gpd()
    from .data import condepe_localities

    dest = _client.cache_dir() / "malha" / f"ibge-{quality}.geojson"
    if refresh or not dest.exists():
        url = (
            f"{IBGE_MALHA_URL}?formato=application/vnd.geo%2Bjson"
            f"&intrarregiao=municipio&qualidade={quality}"
        )
        raw = _client._get(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    m = gpd.read_file(io.BytesIO(dest.read_bytes()))
    nomes = condepe_localities().set_index("cd_municipio_ibge")["nm_municipio"]
    cod = m["codarea"].astype(str)
    out = gpd.GeoDataFrame(
        {"cd_municipio_ibge": cod, "nm_municipio": cod.map(nomes)},
        geometry=m.geometry.values,
        crs=m.crs,
    )
    out = out.sort_values("cd_municipio_ibge").reset_index(drop=True)
    out.attrs["version"] = f"IBGE, qualidade {quality}"
    out.attrs["source"] = "IBGE, API de malhas"
    return out


def _dissolve(malha: gpd.GeoDataFrame, level: str) -> gpd.GeoDataFrame:
    gpd = _gpd()
    reg = condepe_regions(level).set_index("cd_municipio_ibge")["regiao"]
    m = malha.assign(regiao=malha["cd_municipio_ibge"].map(reg)).dropna(subset=["regiao"])
    geoms, nomes, n = [], [], []
    with warnings.catch_warnings():
        # buffer em graus numa malha geográfica: proposital (ver abaixo)
        warnings.simplefilter("ignore")
        for nome, g in m.groupby("regiao", sort=True):
            # Buffer de ~1 m (1e-5 grau) antes da união e desfeito depois:
            # fecha vãos milimétricos entre vizinhos, que deixariam riscos.
            u = g.geometry.make_valid().buffer(1e-5).union_all().buffer(-1e-5)
            geoms.append(u.buffer(0) if not u.is_valid else u)
            nomes.append(nome)
            n.append(len(g))
    out = gpd.GeoDataFrame({"regiao": nomes, "n_municipios": n}, geometry=geoms, crs=malha.crs)
    out.attrs = dict(malha.attrs)
    out.attrs["level"] = level
    return out


def condepe_geometry(
    level: str = "municipio",
    source: str = "condepe",
    quality: str = "intermediaria",
    noronha: bool = True,
    refresh: bool = False,
) -> gpd.GeoDataFrame:
    """Malha municipal de Pernambuco, ou dissolvida numa regionalização.

    Duas origens: ``"condepe"`` (padrão), a Malha Municipal de Pernambuco
    publicada pela Condepe/Fidem em https://cf.pe.gov.br/dados, na edição
    corrente do manifesto (conferida pelo SHA-256 e guardada em cache; a
    versão fica em ``.attrs["version"]``); ou ``"ibge"``, a API de malhas do
    IBGE na qualidade pedida. Com ``level``, os municípios são dissolvidos na
    regionalização pedida (veja :func:`condepe_regions`), com as mesmas divisas.

    Parameters
    ----------
    level:
        ``"municipio"`` (padrão) ou uma regionalização de
        :func:`condepe_regions`.
    source:
        ``"condepe"`` ou ``"ibge"``.
    quality:
        Só para ``source="ibge"``: ``"intermediaria"``, ``"minima"`` ou ``"maxima"``.
    noronha:
        Se ``False``, deixa de fora Fernando de Noronha (2605459), que fica a
        545 km da costa e espreme o continente nos mapas do estado.
    refresh:
        Baixa de novo mesmo que haja cópia em cache.

    Returns
    -------
    geopandas.GeoDataFrame
        ``cd_municipio_ibge``, ``nm_municipio`` e a geometria (WGS 84); com
        ``level``, ``regiao``, ``n_municipios`` e a geometria.

    Examples
    --------
    >>> malha = condepe_geometry(noronha=False)          # doctest: +SKIP
    >>> rd = condepe_geometry("rd", noronha=False)       # doctest: +SKIP
    >>> rd.plot(column="regiao")                         # doctest: +SKIP
    """
    if level != "municipio" and level not in LEVELS:
        raise ValueError(f"`level` must be 'municipio' or one of {', '.join(LEVELS)}.")
    if source not in ("condepe", "ibge"):
        raise ValueError("`source` must be 'condepe' or 'ibge'.")
    if quality not in ("intermediaria", "minima", "maxima"):
        raise ValueError("`quality` must be 'intermediaria', 'minima' or 'maxima'.")
    malha = _malha_condepe(refresh) if source == "condepe" else _malha_ibge(quality, refresh)
    if not noronha:
        attrs = dict(malha.attrs)
        malha = malha[malha["cd_municipio_ibge"] != NORONHA].reset_index(drop=True)
        malha.attrs = attrs
    if level == "municipio":
        return malha
    return _dissolve(malha, level)


def condepe_add_geometry(
    x: pd.DataFrame,
    level: str = "municipio",
    geometry: Any = None,
    how: str = "left",
    **kwargs: Any,
) -> gpd.GeoDataFrame:
    """Junta dados do Observatório à malha, pronta para mapear.

    Recebe qualquer resultado do pacote com ``cd_municipio_ibge``
    (:func:`condepe_series`, :func:`condepe_data` ou uma agregação) e devolve
    um ``GeoDataFrame`` com uma linha por observação. Linhas do Estado
    (``"26"``) são descartadas. Para mapear regiões, agregue os dados numa
    coluna ``regiao`` (juntando :func:`condepe_regions`) e passe ``level``.

    Parameters
    ----------
    x:
        DataFrame com ``cd_municipio_ibge`` (ou ``regiao``, com ``level``).
    level:
        Como em :func:`condepe_geometry`.
    geometry:
        A malha; por padrão ``condepe_geometry(level, **kwargs)``.
    how:
        ``"left"`` (padrão) mantém as áreas sem dado, com ``NaN``;
        ``"inner"`` as descarta.
    **kwargs:
        Repassados a :func:`condepe_geometry` quando ``geometry`` não é dada
        (por exemplo, ``source="ibge"`` ou ``noronha=False``).

    Examples
    --------
    >>> tmi = condepe_series("datasus_mortalidade_infantil",
    ...     "Taxa de mortalidade infantil (por mil nascidos vivos)", years=2024)  # doctest: +SKIP
    >>> condepe_add_geometry(tmi, noronha=False).plot(column="valor")  # doctest: +SKIP
    """
    chave = "cd_municipio_ibge" if level == "municipio" else "regiao"
    if not isinstance(x, pd.DataFrame) or chave not in x.columns:
        raise ValueError(f"`x` must be a DataFrame with a `{chave}` column.")
    if how not in ("left", "inner"):
        raise ValueError("`how` must be 'left' or 'inner'.")
    if geometry is None:
        geometry = condepe_geometry(level, **kwargs)
    dados = pd.DataFrame(x)
    if chave == "cd_municipio_ibge":
        dados = dados[dados["cd_municipio_ibge"] != "26"].drop(
            columns=["nm_municipio"], errors="ignore"
        )
    attrs = dict(geometry.attrs)
    out = geometry.merge(dados, on=chave, how=how)
    out.attrs = attrs
    return out
