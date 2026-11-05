"""Precompila as páginas da documentação que leem dados reais.

Mesma ideia das vignettes do pacote R (padrão rOpenSci): os exemplos rodam
aqui, contra os dados reais do Observatório, e o Markdown que o site publica
é gravado com a saída e os gráficos embutidos. O build do site, então, não
precisa de rede. Rode da raiz do repositório quando um exemplo mudar e
commite as páginas e figuras regeneradas:

    python docs/precompile.py
"""

from __future__ import annotations

import contextlib
import io
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import condepe  # noqa: E402

DOCS = Path(__file__).parent
pd.set_option("display.width", 100)
pd.set_option("display.max_columns", 8)
pd.set_option("display.max_colwidth", 48)
condepe.set_verbose(False)


def fig(name: str) -> str:
    """Grava a figura corrente em docs/assets e devolve o link Markdown."""
    plt.tight_layout()
    plt.savefig(DOCS / "assets" / f"{name}.png", dpi=110)
    plt.close("all")
    return f"![{name}](assets/{name}.png)"


def run(code: str, ns: dict) -> str:
    """Executa um bloco; devolve o que ele imprimiu mais o repr da última expressão."""
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
    ns: dict = {"condepe": condepe, "pd": pd, "plt": plt, "gpd": gpd, "fig": fig}
    md = []
    for prose, code in parts:
        if prose.strip():
            md.append(textwrap.dedent(prose).strip() + "\n")
        if code is None:
            continue
        md.append("```python\n" + textwrap.dedent(code).strip() + "\n```\n")
        out = run(code, ns)
        # Figuras saem como links Markdown de imagem: ficam fora do bloco de saída.
        imagens = [ln for ln in out.splitlines() if ln.startswith("![")]
        texto = "\n".join(ln for ln in out.splitlines() if not ln.startswith("![")).rstrip()
        if texto:
            md.append("```text\n" + texto + "\n```\n")
        md.extend(i + "\n" for i in imagens)
    (DOCS / path).write_text("\n".join(md), encoding="utf-8")
    print(f"gravado {path}")


PRIMEIROS_PASSOS = [
    (
        """
        # Primeiros passos

        O **Observatório de Pernambuco** é a base de dados estatísticos da
        Condepe/Fidem, a Agência Estadual de Planejamento e Pesquisas de
        Pernambuco. Ele reúne séries do IBGE, dos ministérios da Saúde, da
        Educação, do Trabalho e da Fazenda, da Justiça Eleitoral, de órgãos
        estaduais e de outras fontes, para os 185 municípios de Pernambuco e
        para o Estado. A consulta pelo navegador fica em
        <https://cf.pe.gov.br/observatorio>.

        Todas as fontes são publicadas no **mesmo formato longo** — uma
        observação por linha, 15 colunas —, e por isso meia dúzia de funções
        dá conta de todas:

        | Função | Para quê |
        |---|---|
        | `condepe_catalog()` | o que existe: as fontes, com tema, período e tamanho |
        | `condepe_indicators()` | os indicadores de uma fonte |
        | `condepe_series()` | a série de um indicador, filtrada por município e ano |
        | `condepe_data()` | uma fonte inteira |
        | `condepe_localities()` | os municípios e seus códigos IBGE |

        ## O que existe

        `condepe_catalog()` devolve uma linha por fonte. A relação completa,
        por eixo e tema, está em [Fontes do Observatório](fontes.md).
        """,
        """
        cat = condepe.condepe_catalog()

        cat[["id_fonte", "tema", "indicadores", "ano_inicio", "ano_fim"]].head(8)
        """,
    ),
    (
        "O catálogo é versionado; a versão e a citação a usar acompanham o resultado:",
        """
        print(cat.attrs["version"])

        print(cat.attrs["citation"])
        """,
    ),
    (
        "Quantas fontes há em cada eixo, e quantos indicadores:",
        """
        cat.groupby("eixo").agg(fontes=("id_fonte", "size"), indicadores=("indicadores", "sum"))
        """,
    ),
    (
        "Para achar uma fonte por assunto, filtre o catálogo como qualquer tabela:",
        """
        cat.loc[cat["tema"] == "Saúde", ["id_fonte", "descricao"]]
        """,
    ),
    (
        """
        ## Os indicadores de uma fonte

        A coluna `natureza` diz como somar no tempo: `estoque` é uma foto
        (população, leitos em dezembro) e não se soma entre anos; `fluxo` é o
        que aconteceu no período (nascimentos, internações) e se soma.
        """,
        """
        condepe.condepe_indicators("datasus_mortalidade_infantil")
        """,
    ),
    (
        """
        ## Uma série

        `condepe_series()` filtra uma fonte por indicador e, se pedido, por
        código IBGE — 7 dígitos para município, `"26"` para o Estado — e por
        ano. A população do Recife (2611606):
        """,
        """
        recife = condepe.condepe_series(
            "sidra_populacao_estimada",
            "Populacao residente estimada",
            code="2611606",
            years=range(2010, 2027),
        )

        recife[["nm_municipio", "ano", "valor", "unidade"]]
        """,
    ),
    (
        """
        O IBGE não publica estimativa municipal em ano de Censo nem no
        seguinte (2010, 2022, 2023): esses anos simplesmente não aparecem —
        ausência nunca vira zero.

        Os códigos IBGE ficam em `condepe_localities()`:
        """,
        """
        loc = condepe.condepe_localities()

        loc[loc["nm_municipio"].str.contains("Petrolina|Caruaru|Garanhuns")]
        """,
    ),
    (
        """
        ## Séries mensais

        Fontes mensais trazem o período duas vezes: em `mes` e no rótulo
        completo, `indicador` (`"… [MM/AAAA]"`). Filtre por `indicador_base`,
        o rótulo sem o período:
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
        ## Uma fonte inteira e as colunas

        `condepe_data()` devolve a fonte completa. As 15 colunas mantêm os
        nomes com que o Observatório publica, para que todo resultado possa
        ser rastreado até os arquivos oficiais:
        """,
        """
        nasc = condepe.condepe_data("datasus_sinasc")

        list(nasc.columns)
        """,
    ),
    (
        """
        | Coluna | Significado |
        |---|---|
        | `cd_municipio_ibge`, `nm_municipio` | código IBGE (7 dígitos; `"26"` é o Estado) e nome |
        | `ano`, `mes` | ano; mês nas séries mensais (vazio nas demais) |
        | `indicador`, `indicador_base` | rótulo completo (com `[MM/AAAA]` se mensal) e rótulo sem o período |
        | `valor`, `unidade`, `natureza` | valor, unidade, `estoque` ou `fluxo` |
        | `id_fonte`, `eixo`, `tema`, `assunto` | a fonte e seu lugar no catálogo |
        | `fonte_original`, `arquivo_origem` | órgão de origem e o arquivo ou a consulta de onde o valor veio |

        Para passar ao formato largo (um indicador por coluna), use `pivot`:
        """,
        """
        partos = nasc[(nasc["ano"] == 2024) & nasc["indicador_base"].str.contains("Total|Parto")]

        partos.pivot(index="nm_municipio", columns="indicador_base", values="valor").head()
        """,
    ),
    (
        """
        ## Cache, espelho e falhas

        Os arquivos são baixados uma vez por versão do catálogo e guardados em
        `condepe_cache_dir()`, conferidos pelo SHA-256 publicado no catálogo;
        quando sai uma versão nova, os arquivos antigos são apagados. O próprio
        catálogo vale por seis horas (`refresh=True` consulta de novo).

        Os dados vêm do endereço canônico,
        <https://cf.pe.gov.br/observatorio/dados/atual/>. Se ele não
        responder, o pacote lê os mesmos arquivos do espelho no Hugging Face,
        [`mlkwy/observatorio-pernambuco`](https://huggingface.co/datasets/mlkwy/observatorio-pernambuco).
        Se nenhum responder, levanta `condepe.HttpError`; um arquivo que não
        confere com o SHA-256 publicado levanta `condepe.IntegrityError`.

        ## Citação e licença

        Os dados são publicados sob
        [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br):
        cite a Condepe/Fidem e a versão (`condepe_catalog().attrs["citation"]`).
        """,
        None,
    ),
]

PALETA = ["#0c2856", "#0068ff", "#00b7ff", "#ff6700", "#ffce00"]

EXEMPLOS = [
    (
        """
        # Exemplos

        Os gráficos usam o matplotlib, que não é dependência do pacote
        (`pip install matplotlib`). As cores são as do Observatório: o azul
        institucional de Pernambuco e os acentos da paleta oficial.

        ## Mortalidade infantil nas maiores cidades

        Óbitos de menores de um ano por mil nascidos vivos, por município de
        residência:
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
        f"""
        ax = largo.plot(marker="o", color={PALETA[:4]!r}, figsize=(7, 4),
                        title="Mortalidade infantil")

        ax.set_xlabel("")

        ax.set_ylabel("por mil nascidos vivos")

        ax.legend(title=None, frameon=False)

        print(fig("tmi"))
        """,
    ),
    (
        """
        ## Carga movimentada no Porto de Suape

        Carga bruta mensal em Suape (Ipojuca), em milhões de toneladas. Janeiro
        de 2022 não foi publicado pelo porto e aparece como lacuna:
        """,
        """
        suape = condepe.condepe_series("porto_suape_carga", "Porto de Suape - Carga bruta total")

        suape["data"] = pd.to_datetime(dict(year=suape["ano"], month=suape["mes"], day=1))

        serie = suape.set_index("data")["valor"].asfreq("MS") / 1e6

        ax = serie.plot(color="#0c2856", figsize=(7, 4), title="Porto de Suape, carga bruta")

        ax.set_xlabel("")

        ax.set_ylabel("milhões de toneladas")

        print(fig("suape"))
        """,
    ),
    (
        """
        Carga por espécie em cada ano com os 12 meses publicados (2022, sem
        janeiro, e o ano corrente ficam de fora):
        """,
        f"""
        especies = ["Granel líquido", "Granel sólido",
                    "Carga conteinerizada (peso bruto)", "Carga geral solta"]

        d = condepe.condepe_series("porto_suape_carga",
                                   ["Porto de Suape - " + e for e in especies])

        meses = d.groupby("ano")["mes"].nunique()

        d = d[d["ano"].isin(meses[meses == 12].index)]

        anual = d.pivot_table(index="ano", columns="indicador_base", values="valor",
                              aggfunc="sum") / 1e6

        anual.columns = [c.replace("Porto de Suape - ", "") for c in anual.columns]

        ax = anual.plot.bar(stacked=True, color={PALETA[:4]!r}, figsize=(7, 4),
                            title="Suape, carga por espécie", rot=0)

        ax.set_xlabel("")

        ax.set_ylabel("milhões de toneladas")

        ax.legend(frameon=False, fontsize=8)

        print(fig("suape_especies"))
        """,
    ),
    (
        """
        ## IDEB das escolas municipais

        O Índice de Desenvolvimento da Educação Básica dos anos iniciais do
        ensino fundamental, rede municipal, no Recife:
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
        ## Todos os municípios num ano

        Nascidos vivos por município de residência em 2024, os dez maiores, e
        a proporção de partos cesáreos, cruzando dois indicadores da mesma
        fonte:
        """,
        """
        total = "Nascidos vivos por residência - Total"

        cesareo = "Nascidos vivos por residência - Parto cesáreo"

        d = condepe.condepe_series("datasus_sinasc", [total, cesareo], years=2024)

        w = d.pivot(index="nm_municipio", columns="indicador_base", values="valor")

        w["pct_cesareo"] = 100 * w[cesareo] / w[total]

        w.nlargest(10, total).round(1)
        """,
    ),
]


MAPAS = [
    (
        """
        # Mapas

        Toda observação do Observatório traz o código IBGE do município
        (`cd_municipio_ibge`), e isso basta para juntar os dados a uma malha
        municipal e fazer mapas. Esta página usa `geopandas` e `matplotlib`,
        que não são dependências do pacote:

        ```bash
        pip install geopandas matplotlib
        ```

        ## A malha municipal

        A malha vem da API de malhas do IBGE, em GeoJSON, com o código do
        município na propriedade `codarea` — o mesmo de `cd_municipio_ibge`. A
        qualidade intermediária é leve (cerca de 200 KB para Pernambuco):
        """,
        """
        url = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/26"
               "?formato=application/vnd.geo%2Bjson&intrarregiao=municipio&qualidade=intermediaria")

        import io, requests

        malha = gpd.read_file(io.BytesIO(requests.get(url, timeout=60).content))

        print(len(malha), "municípios;", malha.crs)

        malha.head(3)
        """,
    ),
    (
        """
        Fernando de Noronha (2605459) fica a 545 km da costa; num mapa do
        estado inteiro ele espreme o continente para a esquerda. Os mapas
        abaixo o deixam de fora:
        """,
        """
        malha = malha[malha["codarea"] != "2605459"]

        len(malha)
        """,
    ),
    (
        """
        ## Mortalidade infantil

        A taxa é ruidosa nos municípios pequenos (poucos nascimentos por ano);
        a média de três anos é mais estável:
        """,
        """
        tmi = condepe.condepe_series(
            "datasus_mortalidade_infantil",
            "Taxa de mortalidade infantil (por mil nascidos vivos)",
            years=[2022, 2023, 2024],
        )

        media = tmi.groupby("cd_municipio_ibge", as_index=False)["valor"].mean()

        mapa = malha.merge(media, left_on="codarea", right_on="cd_municipio_ibge", how="left")

        ax = mapa.plot(column="valor", cmap="Blues", edgecolor="white", linewidth=0.15,
                       legend=True, figsize=(9, 3.6),
                       legend_kwds={"label": "por mil nascidos vivos", "shrink": 0.6},
                       missing_kwds={"color": "lightgrey"})

        ax.set_axis_off()

        ax.set_title("Mortalidade infantil, média de 2022 a 2024", loc="left")

        print(fig("mapa_tmi"))
        """,
    ),
    (
        """
        ## Variação da população entre os Censos

        Para uma variação, que tem sinal, classes com cores divergentes deixam
        claro quem cresceu e quem encolheu. População dos Censos de 2010 e
        2022 (as estimativas anuais não cobrem anos de Censo):
        """,
        """
        pop = condepe.condepe_series(
            "sidra_censo_cor_raca", "IBGE - População residente - Total", years=[2010, 2022]
        )

        w = pop.pivot(index="cd_municipio_ibge", columns="ano", values="valor")

        w["var"] = 100 * (w[2022] / w[2010] - 1)

        rotulos = ["queda > 5%", "queda até 5%", "alta até 5%", "alta de 5 a 15%", "alta > 15%"]

        w["classe"] = pd.cut(w["var"], [-1e9, -5, 0, 5, 15, 1e9], labels=rotulos)

        mapa = malha.merge(w.reset_index(), left_on="codarea", right_on="cd_municipio_ibge")

        cores = dict(zip(rotulos, ["#ff6700", "#ffc49a", "#bcd6f5", "#3d84df", "#0c2856"]))

        ax = mapa.plot(color=mapa["classe"].map(cores).astype(str), edgecolor="white",
                       linewidth=0.15, figsize=(9, 3.6))

        from matplotlib.patches import Patch

        ax.legend(handles=[Patch(color=c, label=r) for r, c in cores.items()],
                  loc="lower center", ncol=5, frameon=False, fontsize=8,
                  bbox_to_anchor=(0.5, -0.12))

        ax.set_axis_off()

        ax.set_title("Variação da população entre os Censos de 2010 e 2022", loc="left")

        print(fig("mapa_populacao"))

        mapa["classe"].value_counts().sort_index()
        """,
    ),
    (
        """
        ## Região Metropolitana do Recife

        Para ver um recorte, filtre a malha antes de desenhar. Os 15
        municípios da RMR (Goiana entrou em 2018) e os leitos de UTI por 100
        mil habitantes em dezembro de 2024; município sem leito no CNES conta
        como zero leitos de UTI:
        """,
        """
        rmr = ["2600054", "2601052", "2602902", "2603454", "2606200", "2606804",
               "2607208", "2607604", "2607752", "2607901", "2609402", "2609600",
               "2610707", "2611606", "2613701"]

        uti = condepe.condepe_series("datasus_leitos", "Leitos de UTI - Total",
                                     code=rmr, years=2024)

        pop = condepe.condepe_series("sidra_populacao_estimada", "Populacao residente estimada",
                                     code=rmr, years=2024)

        d = pop[["cd_municipio_ibge", "nm_municipio", "valor"]].merge(
            uti[["cd_municipio_ibge", "valor"]], on="cd_municipio_ibge",
            how="left", suffixes=("_pop", "_uti")).fillna({"valor_uti": 0})

        d["por_100mil"] = 1e5 * d["valor_uti"] / d["valor_pop"]

        mapa = malha[malha["codarea"].isin(rmr)].merge(
            d, left_on="codarea", right_on="cd_municipio_ibge")

        ax = mapa.plot(column="por_100mil", cmap="Blues", edgecolor="white", linewidth=0.4,
                       legend=True, figsize=(5.5, 6.5),
                       legend_kwds={"label": "por 100 mil hab.", "shrink": 0.5})

        for _, r in mapa[mapa["por_100mil"] >= 40].iterrows():
            p = r.geometry.representative_point()
            ax.annotate(r["nm_municipio"], (p.x, p.y), ha="center", fontsize=8,
                        color="white", weight="bold")

        ax.set_axis_off()

        ax.set_title("RMR: leitos de UTI por 100 mil hab., dez/2024", loc="left", fontsize=10)

        print(fig("mapa_rmr"))

        d.sort_values("por_100mil", ascending=False)[["nm_municipio", "valor_uti", "por_100mil"]].round(1)
        """,
    ),
    (
        """
        Os leitos concentram-se no Recife, que atende pacientes de toda a
        região: o indicador mede oferta no município, não acesso de quem mora
        nele.
        """,
        None,
    ),
]


def br(n: int) -> str:
    """Número inteiro com ponto de milhar."""
    return f"{n:,}".replace(",", ".")


def pagina_fontes() -> None:
    """Relação das fontes, por eixo e tema, gerada do catálogo."""
    cat = condepe.condepe_catalog()
    md = [
        "# Fontes do Observatório\n",
        f"Relação das fontes publicadas pelo Observatório de Pernambuco na versão "
        f"**{cat.attrs['version']}** do catálogo: **{len(cat)} fontes** e "
        f"**{br(int(cat['indicadores'].sum()))} indicadores**, num total de "
        f"**{br(int(cat['linhas'].sum()))} observações**. A lista foi gerada com "
        "`condepe_catalog()`; o identificador (`id_fonte`) é o que se passa às demais "
        "funções. Cada fonte também tem uma ficha em <https://cf.pe.gov.br/observatorio>.\n",
    ]
    for eixo in sorted(cat["eixo"].unique()):
        md.append(f"## {eixo}\n")
        sub = cat[cat["eixo"] == eixo]
        for tema in sorted(sub["tema"].unique()):
            md.append(f"### {tema}\n")
            md.append("| Fonte | Descrição e origem | Período | Indicadores |")
            md.append("|---|---|:-:|--:|")
            for _, f in sub[sub["tema"] == tema].sort_values("id_fonte").iterrows():
                periodo = (
                    str(f["ano_inicio"])
                    if f["ano_inicio"] == f["ano_fim"]
                    else f"{f['ano_inicio']}–{f['ano_fim']}"
                )
                if f["localidades"] == 1:
                    abr = " · só Pernambuco"
                elif f["localidades"] >= 184:
                    abr = ""
                else:
                    abr = f" · {f['localidades']} municípios"
                md.append(
                    f"| `{f['id_fonte']}` | {f['descricao']}.<br><small>{f['fonte_original']}"
                    f"{abr}</small> | {periodo} | {br(int(f['indicadores']))} |"
                )
            md.append("")
    md += [
        "## Como usar\n",
        "```python",
        "import condepe",
        'condepe.condepe_indicators("datasus_sinasc")      # os indicadores de uma fonte',
        'condepe.condepe_series("datasus_sinasc",          # a série de um indicador',
        '    "Nascidos vivos por residência - Total", code="2611606")',
        "```\n",
    ]
    (DOCS / "fontes.md").write_text("\n".join(md), encoding="utf-8")
    print("gravado fontes.md")


if __name__ == "__main__":
    page("primeiros-passos.md", PRIMEIROS_PASSOS)
    page("exemplos.md", EXEMPLOS)
    page("mapas.md", MAPAS)
    pagina_fontes()
