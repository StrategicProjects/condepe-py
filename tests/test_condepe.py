"""Offline tests: a tiny catalogue and Parquet served by ``responses``."""

from __future__ import annotations

import hashlib
import io

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import responses

import condepe
from condepe import _client

CANON = "https://canon.test/atual"
MIRROR = "https://mirror.test/main"
VERSION = "2026-11-05_171049"


def _parquet() -> bytes:
    rows = {
        "cd_municipio_ibge": ["2611606", "2611606", "2607208", "26"],
        "nm_municipio": ["Recife", "Recife", "Ipojuca", "Pernambuco"],
        "ano": [2024, 2025, 2025, 2025],
        "mes": [None, None, None, None],
        "indicador": ["Pop", "Pop", "Pop", "Pop"],
        "indicador_base": ["Pop", "Pop", "Pop", "Pop"],
        "valor": [1587707.0, 1588376.0, 98000.0, 9.5e6],
        "unidade": ["Pessoas"] * 4,
        "natureza": ["estoque"] * 4,
        "id_fonte": ["sidra_populacao_estimada"] * 4,
        "eixo": ["Social"] * 4,
        "tema": ["Demografia"] * 4,
        "assunto": ["Demografia"] * 4,
        "fonte_original": ["IBGE"] * 4,
        "arquivo_origem": ["x"] * 4,
    }
    table = pa.Table.from_pydict(rows)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


PARQUET = _parquet()
PATH = "sidra_populacao_estimada/sidra_populacao_estimada.parquet"


def _catalog(sha: str | None = None) -> dict:
    return {
        "versao": VERSION,
        "gerado_em": "2026-11-05T17:16:30Z",
        "colunas": [],
        "fontes": [
            {
                "id_fonte": "sidra_populacao_estimada",
                "eixo": "Social",
                "tema": "Demografia",
                "assunto": "Demografia",
                "descricao": "Estimativas de população",
                "fonte_original": "IBGE",
                "linhas": 4,
                "indicadores": 1,
                "localidades": 3,
                "ano_inicio": 2024,
                "ano_fim": 2025,
                "arquivos": [
                    {
                        "caminho": PATH,
                        "formato": "parquet",
                        "sha256": sha or hashlib.sha256(PARQUET).hexdigest(),
                    }
                ],
            }
        ],
    }


@pytest.fixture(autouse=True)
def _ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("CONDEPE_URL", CANON)
    monkeypatch.setenv("CONDEPE_MIRROR_URL", MIRROR)
    monkeypatch.setenv("CONDEPE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(_client.time, "sleep", lambda s: None)
    condepe.set_verbose(False)


def _servir(base: str, catalog: dict | None = None) -> None:
    responses.add(responses.GET, f"{base}/catalogo.json", json=catalog or _catalog())
    responses.add(responses.GET, f"{base}/{PATH}", body=PARQUET)


@responses.activate
def test_catalog_has_version_and_citation():
    _servir(CANON)
    cat = condepe.condepe_catalog()
    assert list(cat["id_fonte"]) == ["sidra_populacao_estimada"]
    assert cat.attrs["version"] == VERSION
    assert "fonte_original" in cat.attrs["citation"]
    assert VERSION in cat.attrs["citation"]


@responses.activate
def test_data_and_series_cite_the_original_source_first():
    _servir(CANON)
    df = condepe.condepe_data("sidra_populacao_estimada")
    assert df.attrs["citation"].startswith("IBGE. Dados organizados pela Condepe/Fidem")
    assert "observatorio/fontes/sidra_populacao_estimada" in df.attrs["citation"]
    s = condepe.condepe_series("sidra_populacao_estimada", "Pop")
    assert s.attrs["citation"] == df.attrs["citation"]


@responses.activate
def test_data_is_verified_and_cached():
    _servir(CANON)
    df = condepe.condepe_data("sidra_populacao_estimada")
    assert len(df) == 4 and df.attrs["version"] == VERSION
    n = len(responses.calls)
    condepe.condepe_data("sidra_populacao_estimada")  # catalogue and file from cache
    assert len(responses.calls) == n


@responses.activate
def test_integrity_error_on_sha_mismatch():
    _servir(CANON, _catalog(sha="0" * 64))
    with pytest.raises(condepe.IntegrityError):
        condepe.condepe_data("sidra_populacao_estimada")


@responses.activate
def test_falls_back_to_mirror():
    responses.add(responses.GET, f"{CANON}/catalogo.json", status=503)
    responses.add(responses.GET, f"{CANON}/{PATH}", status=503)
    _servir(MIRROR)
    df = condepe.condepe_data("sidra_populacao_estimada")
    assert len(df) == 4


@responses.activate
def test_both_backends_down_raises_http_error():
    for base in (CANON, MIRROR):
        responses.add(responses.GET, f"{base}/catalogo.json", status=404)
    with pytest.raises(condepe.HttpError):
        condepe.condepe_catalog()


@responses.activate
def test_series_filters_and_validates():
    _servir(CANON)
    s = condepe.condepe_series("sidra_populacao_estimada", "Pop", code="2611606", years=2025)
    assert s["valor"].tolist() == [1588376.0]
    with pytest.raises(ValueError, match="not in"):
        condepe.condepe_series("sidra_populacao_estimada", "Nao existe")
    with pytest.raises(ValueError, match="Unknown source"):
        condepe.condepe_data("fonte_inexistente")


@responses.activate
def test_indicators_and_localities():
    _servir(CANON)
    ind = condepe.condepe_indicators("sidra_populacao_estimada")
    assert ind.loc[0, "indicador_base"] == "Pop"
    assert ind.loc[0, "localidades"] == 3 and not ind.loc[0, "mensal"]
    loc = condepe.condepe_localities()
    assert loc["cd_municipio_ibge"].tolist()[0] == "26"
    assert len(loc) == 3


@pytest.mark.live
def test_live_recife_population(tmp_path, monkeypatch):
    monkeypatch.delenv("CONDEPE_URL")
    monkeypatch.delenv("CONDEPE_MIRROR_URL")
    s = condepe.condepe_series(
        "sidra_populacao_estimada", "Populacao residente estimada", code="2611606", years=2025
    )
    assert len(s) == 1 and s.loc[0, "valor"] > 1_000_000
