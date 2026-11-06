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

from . import _client, _msg

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
    "up_perh": "Unidades de Planejamento do PERH (APAC; a UP de maior área no município)",
}


def _gpd():
    try:
        import geopandas
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "As funções de malha precisam do geopandas: pip install 'condepe[geo]'"
        ) from exc
    return geopandas


def _regions_bundled() -> pd.DataFrame:
    """A cópia que vai com o pacote."""
    with resources.files("condepe").joinpath("data/regioes.csv").open("rb") as f:
        r = pd.read_csv(f, dtype=str, keep_default_na=False, na_values=[""])
    r.attrs["version"] = "embutida"
    return r


def _regions_published(refresh: bool) -> pd.DataFrame | None:
    """A tabela publicada (catálogo → ``referencias`` → ``regioes``), ou ``None``
    quando o catálogo não a traz ou o Observatório não responde."""
    try:
        cat = _client.catalog_json(refresh=refresh)
        ref = next((x for x in cat.get("referencias") or [] if x.get("id") == "regioes"), None)
        arq = next(
            (a for a in (ref or {}).get("arquivos", []) if a.get("formato") == "parquet"), None
        )
        if arq is None:
            return None
        local = _client.cached_file(arq["caminho"], arq["sha256"], cat["versao"], refresh=refresh)
    except _client.HttpError:
        return None
    r = pd.read_parquet(local)
    esperado = list(_regions_bundled().columns)
    if not set(esperado) <= set(r.columns):
        return None  # formato diferente do que este pacote conhece: fica a embutida
    # Mesmos tipos da cópia embutida: texto, ausência como NaN.
    r = r[esperado + [c for c in r.columns if c not in esperado]].astype(object)
    r = r.mask(r.isna()).sort_values("cd_municipio_ibge").reset_index(drop=True)
    r.attrs["version"] = cat["versao"]
    return r


def condepe_regions(
    level: str | None = None, refresh: bool = False, offline: bool = False
) -> pd.DataFrame:
    """Regionalizações dos municípios de Pernambuco.

    A que região pertence cada município em doze regionalizações oficiais:
    ``rd`` (Regiões de Desenvolvimento da Condepe/Fidem), ``mesorregiao``,
    ``microrregiao``, ``regiao_intermediaria`` e ``regiao_imediata`` (IBGE),
    ``regiao_saude`` e ``macrorregiao_saude`` (SES-PE), ``gre`` (Gerências
    Regionais de Educação da SEE-PE; Recife Norte e Recife Sul ficam juntas,
    porque dividem o mesmo município), ``regiao_fiscal`` (SEFAZ-PE), ``dro``
    (Diretorias Regionais de Operações do DER-PE) e ``rm`` (regiões
    metropolitanas).

    A tabela é publicada pelo Observatório junto com os dados abertos
    (``referencia/regioes.parquet``, listada no catálogo) e é lida de lá como
    as fontes: endereço canônico, espelho como reserva, SHA-256 conferido e
    cache em disco por versão do catálogo. Sem rede, ou com ``offline=True``,
    vale a cópia que vai com o pacote.

    Parameters
    ----------
    level:
        ``None`` (todas, uma coluna por regionalização) ou uma delas.
    refresh:
        Baixa a tabela de novo mesmo que haja cópia conferida em cache.
    offline:
        Usa só a cópia embutida no pacote, sem rede.

    Returns
    -------
    pandas.DataFrame
        ``cd_municipio_ibge``, ``nm_municipio`` e as colunas de região (ou só
        ``regiao``, se ``level`` for dado). Municípios fora de uma região
        metropolitana ficam com ``NA`` em ``rm``. ``.attrs["version"]`` diz de
        onde veio: a versão do catálogo ou ``"embutida"``.

    Examples
    --------
    >>> condepe_regions("rd", offline=True)["regiao"].nunique()
    13
    """
    if level is not None and level not in LEVELS:
        raise ValueError(f"`level` must be one of {', '.join(LEVELS)}.")
    r = None if offline else _regions_published(refresh)
    if r is None:
        if not offline:
            _msg.step("Usando a tabela de regiões embutida no pacote.")
        r = _regions_bundled()
    if level is None:
        return r
    out = r[["cd_municipio_ibge", "nm_municipio", level]].rename(columns={level: "regiao"})
    out = out.reset_index(drop=True)
    out.attrs["version"] = r.attrs["version"]
    return out


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


ROAD_TYPES = ("estaduais", "federais", "vicinais", "acessos")


def condepe_roads(type: str | list[str] | None = None, refresh: bool = False) -> gpd.GeoDataFrame:
    """Malha rodoviária de Pernambuco.

    Os trechos das rodovias de Pernambuco como ``GeoDataFrame`` de linhas
    (WGS 84): as estaduais, vicinais e acessos do Sistema Rodoviário Estadual
    do DER-PE e as federais em Pernambuco (SNV/DNIT), cada trecho com rodovia,
    denominação, início e fim, quilometragem, extensão, situação física
    (pavimentada, duplicada, implantada, leito natural, planejada, em obra),
    revestimento, Diretoria Regional de Operações do DER, Região de
    Desenvolvimento e municípios atravessados.

    A malha é publicada pelo Observatório junto com os dados abertos
    (``referencia/rodovias.parquet``, um GeoParquet listado no catálogo) e
    lida de lá como as fontes: endereço canônico, espelho como reserva,
    SHA-256 conferido e cache em disco por versão do catálogo. Diferente de
    :func:`condepe_regions`, não há cópia embutida no pacote. Precisa do
    geopandas (``pip install "condepe[geo]"``).

    Parameters
    ----------
    type:
        ``None`` (todos os trechos) ou um ou mais de ``"estaduais"``,
        ``"federais"``, ``"vicinais"`` e ``"acessos"``.
    refresh:
        Baixa a malha de novo mesmo que haja cópia conferida em cache.

    Returns
    -------
    geopandas.GeoDataFrame
        Uma linha por trecho (``codigo_sre``, ``rodovia``, ``tipo``,
        ``situacao``, ``revestimento``, ``extensao_km``, ``dro``,
        ``municipios``… e a geometria ``MultiLineString``), com
        ``.attrs["version"]`` igual à versão do catálogo.

    Raises
    ------
    CondepeError
        Se o catálogo publicado ainda não trouxer a malha rodoviária.

    Examples
    --------
    >>> rodovias = condepe_roads()                       # doctest: +SKIP
    >>> rodovias.plot(column="tipo", legend=True)        # doctest: +SKIP
    >>> pav = rodovias[rodovias["classificacao"] == "PAVIMENTADA"]   # doctest: +SKIP
    >>> pav.groupby("dro")["extensao_km"].sum()          # doctest: +SKIP
    """
    tipos = [type] if isinstance(type, str) else list(type or [])
    for t in tipos:
        if t not in ROAD_TYPES:
            raise ValueError(f"`type` must be one of {', '.join(ROAD_TYPES)}.")
    r = _geo_reference("rodovias", refresh, "a malha rodoviária")
    if tipos:
        versao = r.attrs["version"]
        r = r[r["tipo"].isin(tipos)].reset_index(drop=True)
        r.attrs["version"] = versao
    r.attrs["source"] = "DER-PE (SRE); DNIT (SNV)"
    return r


HYDRO_LAYERS = {
    "rios": "Rios e riachos (BHO da ANA, nível Otto 5)",
    "rios_principais": "Rios principais (BHO, nível Otto 3)",
    "massas_dagua": "Massas d'água: açudes, lagoas e reservatórios",
    "reservatorios": "Reservatórios do semiárido acompanhados pela ANA (pontos, com capacidade e demandas)",
    "uph": "Unidades de Planejamento Hídrico da ANA que alcançam Pernambuco",
}


def _geo_reference(id: str, refresh: bool, rotulo: str) -> gpd.GeoDataFrame:
    """Uma referência com geometria (GeoParquet) do catálogo, como GeoDataFrame."""
    gpd = _gpd()
    cat = _client.catalog_json(refresh=refresh)
    ref = next((x for x in cat.get("referencias") or [] if x.get("id") == id), None)
    arq = next((a for a in (ref or {}).get("arquivos", []) if a.get("formato") == "parquet"), None)
    if arq is None:
        raise _client.CondepeError(
            f"O catálogo do Observatório (versão {cat.get('versao')}) ainda não traz {rotulo}; "
            "as camadas com geometria entraram nos dados abertos em novembro de 2026 "
            "(tente refresh=True)."
        )
    local = _client.cached_file(arq["caminho"], arq["sha256"], cat["versao"], refresh=refresh)
    r = gpd.read_parquet(local)
    r.attrs["version"] = cat["versao"]
    return r


def condepe_hydrography(layer: str, refresh: bool = False) -> gpd.GeoDataFrame:
    """Hidrografia de Pernambuco.

    Camadas da Agência Nacional de Águas recortadas para Pernambuco, como
    ``GeoDataFrame`` (WGS 84): ``rios`` (rios e riachos, BHO nível Otto 5),
    ``rios_principais`` (nível 3), ``massas_dagua`` (açudes, lagoas e
    reservatórios), ``reservatorios`` (os acompanhados pela ANA no semiárido,
    pontos com capacidade e demandas) e ``uph`` (Unidades de Planejamento
    Hídrico que alcançam o Estado).

    As camadas são publicadas pelo Observatório junto com os dados abertos
    (``referencia/<camada>.parquet``, GeoParquet listado no catálogo) e lidas
    de lá como as fontes: endereço canônico, espelho como reserva, SHA-256
    conferido e cache em disco por versão do catálogo. Precisa do geopandas
    (``pip install "condepe[geo]"``).

    Parameters
    ----------
    layer:
        Uma das camadas acima.
    refresh:
        Baixa a camada de novo mesmo que haja cópia conferida em cache.

    Returns
    -------
    geopandas.GeoDataFrame
        As colunas publicadas e a geometria (linhas, polígonos ou pontos
        conforme a camada), com ``.attrs["version"]`` igual à versão do
        catálogo.

    Examples
    --------
    >>> rios = condepe_hydrography("rios_principais")            # doctest: +SKIP
    >>> acudes = condepe_hydrography("reservatorios")             # doctest: +SKIP
    >>> acudes.nlargest(5, "volume_maximo_m3")[["nome", "municipio"]]   # doctest: +SKIP
    """
    if layer not in HYDRO_LAYERS:
        raise ValueError(f"`layer` must be one of {', '.join(HYDRO_LAYERS)}.")
    r = _geo_reference(layer, refresh, f"a camada {layer!r} da hidrografia")
    r.attrs["source"] = "ANA — BHO e dados abertos do SNIRH"
    return r


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
