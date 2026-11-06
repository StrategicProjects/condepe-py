"""condepe — open data of the Pernambuco Observatory from Python.

Municipal series of Pernambuco, Brazil, published by Condepe/Fidem (the State
Agency for Planning and Research) in the Observatory of Pernambuco: population,
economy, public finance, labour, education, health, security, transport and
more, every source in the same long format.

Data come from https://cf.pe.gov.br/observatorio/dados/atual/, with a mirror
on Hugging Face as fallback, and are cached on disk per catalogue version.

Quick start
-----------
>>> import condepe
>>> condepe.condepe_catalog()                                   # doctest: +SKIP
>>> condepe.condepe_series("sidra_populacao_estimada",
...     "Populacao residente estimada", code="2611606")       # doctest: +SKIP
"""

from __future__ import annotations

from ._client import (
    CondepeError,
    HttpError,
    IntegrityError,
    set_timeout,
)
from ._client import cache_dir as condepe_cache_dir
from ._client import clear_cache as condepe_cache_clear
from ._msg import set_verbose
from .data import (
    condepe_catalog,
    condepe_data,
    condepe_indicators,
    condepe_localities,
    condepe_series,
)
from .cite import condepe_cite
from .geo import (
    condepe_add_geometry,
    condepe_geometry,
    condepe_hydrography,
    condepe_regions,
    condepe_roads,
)

__version__ = "0.1.1"

__all__ = [
    "CondepeError",
    "HttpError",
    "IntegrityError",
    "condepe_add_geometry",
    "condepe_cache_clear",
    "condepe_cache_dir",
    "condepe_catalog",
    "condepe_cite",
    "condepe_data",
    "condepe_geometry",
    "condepe_hydrography",
    "condepe_indicators",
    "condepe_localities",
    "condepe_regions",
    "condepe_roads",
    "condepe_series",
    "set_timeout",
    "set_verbose",
]
