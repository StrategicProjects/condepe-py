"""Precompile the documentation pages that read live data.

Same idea as the R package vignettes (rOpenSci pattern): the examples run
here, against the real Observatory data, and the Markdown that the site
publishes is written with their output and figures baked in. The site build
then needs no network. Run from the repository root whenever an example
changes, and commit the regenerated pages and figures:

    python docs/precompile.py
"""

from __future__ import annotations

import contextlib
import io
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import condepe  # noqa: E402

DOCS = Path(__file__).parent
pd.set_option("display.width", 100)
pd.set_option("display.max_columns", 8)
pd.set_option("display.max_colwidth", 48)
condepe.set_verbose(False)


def run(code: str, ns: dict) -> str:
    """Execute a block; return what it printed plus the repr of a final expression."""
    code = textwrap.dedent(code).strip()
    *body, last = code.split("\n\n")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for block in body:
            exec(block, ns)
        try:
            value = eval(last, ns)
        except SyntaxError:
            exec(last, ns)
            value = None
    text = out.getvalue()
    if value is not None:
        text += repr(value) + "\n"
    return text


def page(path: str, parts: list[tuple[str, str | None]]) -> None:
    ns: dict = {"condepe": condepe, "pd": pd, "plt": plt, "fig": fig}
    md = []
    for prose, code in parts:
        md.append(textwrap.dedent(prose).strip() + "\n")
        if code is None:
            continue
        md.append("```python\n" + textwrap.dedent(code).strip() + "\n```\n")
        out = run(code, ns)
        # Figures are printed as Markdown image links: they go outside the
        # output block.
        imagens = [l for l in out.splitlines() if l.startswith("![")]
        texto = "\n".join(l for l in out.splitlines() if not l.startswith("![")).rstrip()
        if texto:
            md.append("```text\n" + texto + "\n```\n")
        md.extend(i + "\n" for i in imagens)
    (DOCS / path).write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {path}")


GETTING_STARTED = [
    (
        """
        # Getting started

        The **Observatório de Pernambuco** is the statistical database of
        Condepe/Fidem, the planning and research agency of the State of
        Pernambuco, Brazil. It gathers series from IBGE, the ministries of
        health, education, labour and finance, the electoral court, state
        agencies and others, for the 185 municipalities of Pernambuco and the
        State as a whole. Every source is published in the **same long
        format**, so a handful of functions covers all of them.

        ## What is there

        `condepe_catalog()` lists the sources: one row each, with the theme,
        the original publisher, how many rows, indicators and localities, and
        the years covered.
        """,
        """
        cat = condepe.condepe_catalog()

        cat[["id_fonte", "tema", "indicadores", "ano_inicio", "ano_fim"]].head(8)
        """,
    ),
    (
        "The catalogue is versioned; the version and the citation travel with it:",
        """
        print(cat.attrs["version"])

        print(cat.attrs["citation"])
        """,
    ),
    (
        "Filter it like any data frame to find a subject:",
        """
        cat.loc[cat["tema"] == "Saúde", ["id_fonte", "descricao"]]
        """,
    ),
    (
        "## The indicators of a source",
        """
        condepe.condepe_indicators("datasus_mortalidade_infantil")
        """,
    ),
    (
        """
        ## A series

        `condepe_series()` filters a source by indicator and, optionally, by
        IBGE code (7 digits for municipalities, `"26"` for the State) and by
        year. The population of Recife (2611606):
        """,
        """
        recife = condepe.condepe_series(
            "sidra_populacao_estimada",
            "Populacao residente estimada",
            code="2611606",
            years=range(2015, 2027),
        )

        recife[["nm_municipio", "ano", "valor", "unidade"]]
        """,
    ),
    (
        "Look up codes with `condepe_localities()`:",
        """
        loc = condepe.condepe_localities()

        loc[loc["nm_municipio"].str.contains("Petrolina|Caruaru")]
        """,
    ),
    (
        """
        ## Monthly series

        Monthly sources carry the period twice: in `mes`, and in the full
        label `indicador` (`"… [MM/YYYY]"`). Filter by `indicador_base`, the
        label without the period:
        """,
        """
        suape = condepe.condepe_series(
            "porto_suape_carga", "Porto de Suape - Carga bruta total", years=2026
        )

        suape[["ano", "mes", "indicador", "valor", "unidade"]]
        """,
    ),
    (
        """
        ## Whole sources and the columns

        `condepe_data()` returns a source in full. The 15 columns keep the
        Portuguese names under which the Observatory publishes them, so a
        result can always be traced back to the official files:
        """,
        """
        nasc = condepe.condepe_data("datasus_sinasc")

        list(nasc.columns)
        """,
    ),
    (
        """
        | Column | Meaning |
        |---|---|
        | `cd_municipio_ibge`, `nm_municipio` | IBGE code (7 digits; `"26"` is the State) and name |
        | `ano`, `mes` | year; month for monthly series (missing otherwise) |
        | `indicador`, `indicador_base` | full label (with `[MM/YYYY]` when monthly) and label without the period |
        | `valor`, `unidade`, `natureza` | value, unit, `estoque` (stock) or `fluxo` (flow) |
        | `id_fonte`, `eixo`, `tema`, `assunto` | source and its place in the catalogue |
        | `fonte_original`, `arquivo_origem` | original publisher and the file or API call the value came from |

        A missing value never becomes zero: what the original source does not
        publish is simply absent.

        ## Cache, mirror and failures

        Files are downloaded once per catalogue version and kept in
        `condepe_cache_dir()`, checked against the SHA-256 published in the
        catalogue; when a new version comes out, the old files are dropped.
        The catalogue itself is trusted for six hours (`refresh=True` asks
        again).

        Data come from the canonical endpoint,
        <https://cf.pe.gov.br/observatorio/dados/atual/>. If it does not
        answer, the package reads the same files from the Hugging Face mirror
        [`mlkwy/observatorio-pernambuco`](https://huggingface.co/datasets/mlkwy/observatorio-pernambuco).
        If neither answers, `condepe.HttpError` is raised; a file that does
        not match its published SHA-256 raises `condepe.IntegrityError`.

        ## Citation and license

        The data are published under
        [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): cite
        Condepe/Fidem and the version (`condepe_catalog().attrs["citation"]`).
        """,
        None,
    ),
]


def fig(name: str) -> str:
    plt.tight_layout()
    plt.savefig(DOCS / "assets" / f"{name}.png", dpi=110)
    plt.close()
    return f"![{name}](assets/{name}.png)"


EXAMPLES = [
    (
        """
        # Worked examples

        Plots use matplotlib, which is not a dependency of the package
        (`pip install matplotlib`).

        ## Infant mortality in the largest cities

        Deaths under one year per thousand live births, by municipality of
        residence, for Recife, Jaboatão dos Guararapes, Caruaru and Petrolina:
        """,
        """
        cidades = ["2611606", "2607901", "2604106", "2611101"]

        tmi = condepe.condepe_series(
            "datasus_mortalidade_infantil",
            "Taxa de mortalidade infantil (por mil nascidos vivos)",
            code=cidades,
        )

        largo = tmi.pivot(index="ano", columns="nm_municipio", values="valor")

        largo
        """,
    ),
    (
        "",
        """
        ax = largo.plot(marker="o", color=["#0c2856", "#0068ff", "#00b7ff", "#ff6700"],
                        figsize=(7, 4), title="Infant mortality")

        ax.set_xlabel("")

        ax.set_ylabel("per 1,000 live births")

        print(fig("tmi"))
        """,
    ),
    (
        """
        ## Cargo at the port of Suape

        Monthly gross cargo handled at Suape (Ipojuca), in million tonnes:
        """,
        """
        suape = condepe.condepe_series("porto_suape_carga", "Porto de Suape - Carga bruta total")

        suape["data"] = pd.to_datetime(dict(year=suape["ano"], month=suape["mes"], day=1))

        ax = (suape.set_index("data")["valor"] / 1e6).plot(
            color="#0c2856", figsize=(7, 4), title="Port of Suape, gross cargo")

        ax.set_xlabel("")

        ax.set_ylabel("million t")

        print(fig("suape"))
        """,
    ),
    (
        """
        ## IDEB of the municipal schools

        The Basic Education Development Index of the early years of elementary
        school, municipal network, in Recife:
        """,
        """
        ideb = condepe.condepe_series(
            "inep_ideb_anos_iniciais", "IDEB observado - Municipal", code="2611606"
        )

        ideb[["ano", "valor"]]
        """,
    ),
    (
        """
        ## All municipalities in one year

        Live births by municipality of residence in 2024, the ten largest:
        """,
        """
        nasc = condepe.condepe_series(
            "datasus_sinasc", "Nascidos vivos por residência - Total", years=2024
        )

        nasc.nlargest(10, "valor")[["nm_municipio", "valor"]]
        """,
    ),
]


if __name__ == "__main__":
    page("getting-started.md", GETTING_STARTED)
    page("examples.md", EXAMPLES)
