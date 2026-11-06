"""condepe_regions: tabela publicada no catálogo, com a embutida como reserva."""

from __future__ import annotations

import hashlib
import io
import json

import pytest
import responses

import condepe
from condepe import _client
from condepe.geo import _regions_bundled

CANON = "https://canon.test/atual"
MIRROR = "https://mirror.test/main"
VERSION = "2026-11-06_000000"


@pytest.fixture(autouse=True)
def _ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("CONDEPE_URL", CANON)
    monkeypatch.setenv("CONDEPE_MIRROR_URL", MIRROR)
    monkeypatch.setenv("CONDEPE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(_client.time, "sleep", lambda s: None)
    condepe.set_verbose(False)


def _parquet_publicado() -> bytes:
    r = _regions_bundled()
    r.loc[r["cd_municipio_ibge"] == "2611606", "rd"] = "RD publicada"
    buf = io.BytesIO()
    r.to_parquet(buf, index=False)
    return buf.getvalue()


def _servir(referencias: bool = True) -> None:
    raw = _parquet_publicado()
    cat = {"versao": VERSION, "fontes": []}
    if referencias:
        cat["referencias"] = [
            {
                "id": "regioes",
                "arquivos": [
                    {
                        "caminho": "referencia/regioes.parquet",
                        "formato": "parquet",
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                ],
            }
        ]
    responses.add(responses.GET, f"{CANON}/catalogo.json", body=json.dumps(cat))
    responses.add(responses.GET, f"{CANON}/referencia/regioes.parquet", body=raw)


def test_bundled_covers_185_municipalities():
    r = condepe.condepe_regions(offline=True)
    assert r.attrs["version"] == "embutida"
    assert len(r) == 185 and r["cd_municipio_ibge"].is_unique
    esperado = {
        "rd": 13,
        "mesorregiao": 5,
        "microrregiao": 19,
        "regiao_intermediaria": 4,
        "regiao_imediata": 18,
        "regiao_saude": 12,
        "macrorregiao_saude": 4,
        "gre": 15,
        "regiao_fiscal": 3,
        "dro": 9,
        "rm": 2,
        "up_perh": 16,
    }
    for nivel, n in esperado.items():
        assert r[nivel].dropna().nunique() == n, nivel
    assert (r["rm"] == "Região Metropolitana do Recife").sum() == 15
    rd = condepe.condepe_regions("rd", offline=True)
    assert list(rd.columns) == ["cd_municipio_ibge", "nm_municipio", "regiao"]
    with pytest.raises(ValueError):
        condepe.condepe_regions("ais")


@responses.activate
def test_reads_published_table():
    _servir()
    r = condepe.condepe_regions("rd")
    assert r.attrs["version"] == VERSION
    assert r.loc[r["cd_municipio_ibge"] == "2611606", "regiao"].item() == "RD publicada"
    todas = condepe.condepe_regions()
    assert todas.loc[todas["cd_municipio_ibge"] == "2600104", "rm"].isna().all()
    n = len(responses.calls)
    condepe.condepe_regions()  # catálogo e arquivo do cache
    assert len(responses.calls) == n


@responses.activate
def test_falls_back_without_reference_in_catalogue():
    _servir(referencias=False)
    assert condepe.condepe_regions("rd").attrs["version"] == "embutida"


@responses.activate
def test_falls_back_when_offline_network():
    for base in (CANON, MIRROR):
        responses.add(responses.GET, f"{base}/catalogo.json", status=503)
    r = condepe.condepe_regions("rd")
    assert r.attrs["version"] == "embutida" and len(r) == 185
