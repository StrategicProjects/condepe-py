"""Malhas e regionalizações, com o manifesto e o GeoJSON servidos por ``responses``."""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest
import responses

import condepe
from condepe import _client
from condepe.geo import MALHA_URL

gpd = pytest.importorskip("geopandas")


def _quadrado(x: float, y: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[x, y], [x + 0.1, y], [x + 0.1, y - 0.1], [x, y - 0.1], [x, y]]],
    }


GEOJSON = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            # Recife e Olinda vizinhos (mesma RD), Noronha longe
            {
                "type": "Feature",
                "properties": {"cod_munici": "2611606", "nom_munici": "Recife"},
                "geometry": _quadrado(-35.0, -8.0),
            },
            {
                "type": "Feature",
                "properties": {"cod_munici": "2609600", "nom_munici": "Olinda"},
                "geometry": _quadrado(-34.9, -8.0),
            },
            {
                "type": "Feature",
                "properties": {"cod_munici": "2605459", "nom_munici": "Fernando de Noronha"},
                "geometry": _quadrado(-32.4, -3.8),
            },
        ],
    }
).encode()


@pytest.fixture(autouse=True)
def _ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("CONDEPE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(_client.time, "sleep", lambda s: None)
    condepe.set_verbose(False)


def _servir(sha: str | None = None) -> None:
    manifesto = {
        "atual": "2025-v3",
        "versoes": [
            {
                "id": "2025-v3",
                "formatos": [
                    {
                        "tipo": "geojson",
                        "arquivo": "malha.geojson",
                        "sha256": sha or hashlib.sha256(GEOJSON).hexdigest(),
                    }
                ],
            }
        ],
    }
    responses.add(responses.GET, f"{MALHA_URL}/manifest.json", json=manifesto)
    responses.add(responses.GET, f"{MALHA_URL}/2025-v3/malha.geojson", body=GEOJSON)


def test_regions_cover_185_municipalities():
    r = condepe.condepe_regions()
    assert len(r) == 185 and r["cd_municipio_ibge"].is_unique
    esperado = {
        "rd": 13,
        "mesorregiao": 5,
        "microrregiao": 19,
        "regiao_intermediaria": 4,
        "regiao_imediata": 18,
        "regiao_saude": 12,
        "macrorregiao_saude": 4,
        "rm": 2,
    }
    for nivel, n in esperado.items():
        assert r[nivel].dropna().nunique() == n, nivel
    assert (r["rm"] == "Região Metropolitana do Recife").sum() == 15
    assert list(condepe.condepe_regions("rd").columns) == [
        "cd_municipio_ibge",
        "nm_municipio",
        "regiao",
    ]
    with pytest.raises(ValueError):
        condepe.condepe_regions("ais")


@responses.activate
def test_geometry_condepe_cache_and_noronha():
    _servir()
    m = condepe.condepe_geometry()
    assert list(m["cd_municipio_ibge"]) == ["2605459", "2609600", "2611606"]
    assert m.attrs["version"] == "2025-v3"
    n = len(responses.calls)
    sem = condepe.condepe_geometry(noronha=False)
    assert "2605459" not in set(sem["cd_municipio_ibge"])
    assert len(responses.calls) == n + 1  # só o manifesto; o GeoJSON vem do cache


@responses.activate
def test_geometry_integrity():
    _servir(sha="0" * 64)
    with pytest.raises(condepe.IntegrityError):
        condepe.condepe_geometry()


@responses.activate
def test_dissolve_by_region():
    _servir()
    g = condepe.condepe_geometry("rd", noronha=False)
    assert list(g["regiao"]) == ["Região Metropolitana do Recife"]
    assert g["n_municipios"].tolist() == [2]
    assert g.geometry.iloc[0].geom_type == "Polygon"  # vizinhos viram um polígono só
    assert g.attrs["level"] == "rd"


@responses.activate
def test_add_geometry_by_code_and_region():
    _servir()
    d = pd.DataFrame(
        {"cd_municipio_ibge": ["2611606", "26"], "nm_municipio": ["x", "PE"], "valor": [1.0, 2.0]}
    )
    mp = condepe.condepe_add_geometry(d)
    assert "26" not in set(mp["cd_municipio_ibge"])
    assert mp.loc[mp["cd_municipio_ibge"] == "2611606", "valor"].item() == 1.0
    assert mp.loc[mp["cd_municipio_ibge"] == "2609600", "valor"].isna().all()
    assert len(condepe.condepe_add_geometry(d, how="inner")) == 1
    r = condepe.condepe_add_geometry(
        pd.DataFrame({"regiao": ["Região Metropolitana do Recife"], "valor": [3.0]}),
        level="rd",
        noronha=False,
    )
    assert r["valor"].tolist() == [3.0]
    with pytest.raises(ValueError):
        condepe.condepe_add_geometry(pd.DataFrame({"x": [1]}))
