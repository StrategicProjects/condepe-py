"""condepe_roads: o GeoParquet publicado no catálogo, lido como GeoDataFrame."""

from __future__ import annotations

import hashlib
import io
import json

import pytest
import responses

import condepe
from condepe import _client

gpd = pytest.importorskip("geopandas")
from shapely.geometry import MultiLineString  # noqa: E402

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


def _geoparquet() -> bytes:
    g = gpd.GeoDataFrame(
        {
            "codigo_sre": ["027EPE0010", "101BPE0350", "072VPE0010"],
            "rodovia": ["PE-027", "BR-101", "PE-072"],
            "tipo": ["estaduais", "federais", "vicinais"],
            "situacao": ["PAVIMENTADA", "DUPLICADA", "LEITO NATURAL"],
            "extensao_km": [14.25, 7.77, 3.0],
        },
        geometry=[
            MultiLineString([[(-35, -8), (-35.1, -8.1)]]),
            MultiLineString([[(-36, -8.5), (-36.2, -8.4)]]),
            MultiLineString([[(-38, -9), (-38.3, -9)]]),
        ],
        crs="EPSG:4326",
    ).rename_geometry("geom")
    buf = io.BytesIO()
    g.to_parquet(buf)
    return buf.getvalue()


def _servir(com_rodovias: bool = True) -> None:
    raw = _geoparquet()
    cat: dict = {"versao": VERSION, "fontes": []}
    if com_rodovias:
        cat["referencias"] = [
            {
                "id": id_,
                "arquivos": [
                    {
                        "caminho": f"referencia/{id_}.parquet",
                        "formato": "parquet",
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                ],
            }
            for id_ in ("rodovias", "reservatorios")
        ]
    responses.add(responses.GET, f"{CANON}/catalogo.json", body=json.dumps(cat))
    responses.add(responses.GET, f"{CANON}/referencia/rodovias.parquet", body=raw)
    responses.add(responses.GET, f"{CANON}/referencia/reservatorios.parquet", body=raw)


@responses.activate
def test_roads_reads_geoparquet_and_filters_by_type():
    _servir()
    r = condepe.condepe_roads()
    assert isinstance(r, gpd.GeoDataFrame)
    assert len(r) == 3 and r.crs.to_epsg() == 4326
    assert set(r.geometry.geom_type) == {"MultiLineString"}
    assert r.attrs["version"] == VERSION
    assert list(condepe.condepe_roads(type="federais")["rodovia"]) == ["BR-101"]
    assert len(condepe.condepe_roads(type=["estaduais", "vicinais"])) == 2
    with pytest.raises(ValueError):
        condepe.condepe_roads(type="municipais")


@responses.activate
def test_roads_without_reference_in_catalogue_raises():
    _servir(com_rodovias=False)
    with pytest.raises(_client.CondepeError, match="malha"):
        condepe.condepe_roads()


@responses.activate
def test_hydrography_reads_a_layer_and_rejects_unknown_ones():
    _servir()
    r = condepe.condepe_hydrography("reservatorios")
    assert isinstance(r, gpd.GeoDataFrame) and len(r) == 3
    assert r.attrs["version"] == VERSION
    with pytest.raises(_client.CondepeError, match="hidrografia"):
        condepe.condepe_hydrography("uph")
    with pytest.raises(ValueError):
        condepe.condepe_hydrography("lagos")
