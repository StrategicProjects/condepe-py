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
        municipal e fazer mapas. O pacote traz a malha (`condepe_geometry()`),
        a junção (`condepe_add_geometry()`) e as regionalizações do estado
        (`condepe_regions()`). As funções de malha usam `geopandas`, que é
        opcional; os gráficos usam `matplotlib`:

        ```bash
        pip install "condepe[geo]" matplotlib
        ```

        ## A malha municipal

        `condepe_geometry()` baixa a Malha Municipal de Pernambuco publicada
        pela Condepe/Fidem (a edição corrente, conferida pelo SHA-256 e
        guardada em cache). Com `source="ibge"`, a malha vem da API de malhas
        do IBGE. Fernando de Noronha (2605459) fica a 545 km da costa e, num
        mapa do estado inteiro, espreme o continente para a esquerda; os mapas
        abaixo o deixam de fora com `noronha=False`:
        """,
        """
        malha = condepe.condepe_geometry(noronha=False)

        print(len(malha), "municípios; edição", malha.attrs["version"], ";", malha.crs)

        malha.head(3)
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

        mapa = condepe.condepe_add_geometry(media, geometry=malha)

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

        mapa = condepe.condepe_add_geometry(w.reset_index(), geometry=malha)

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
        ## Regiões

        `condepe_regions()` diz a que região pertence cada município em onze
        regionalizações: Regiões de Desenvolvimento (RD) da Condepe/Fidem,
        meso e microrregiões e regiões imediatas e intermediárias do IBGE,
        regiões e macrorregiões de saúde, Gerências Regionais de Educação
        (GRE), regiões fiscais da SEFAZ, Diretorias Regionais de Operações (DRO) do DER e regiões
metropolitanas. A tabela vai
        com o pacote, sem rede:
        """,
        """
        reg = condepe.condepe_regions()

        reg["rd"].value_counts()
        """,
    ),
    (
        """
        Para mapear uma região, agregue os dados numa coluna `regiao` e passe
        `level` a `condepe_add_geometry()`: a malha municipal é dissolvida na
        regionalização pedida, com as mesmas divisas. População estimada de
        2025 por Região de Desenvolvimento:
        """,
        """
        pop = condepe.condepe_series("sidra_populacao_estimada",
                                     "Populacao residente estimada", years=2025)

        pop = pop.merge(condepe.condepe_regions("rd")[["cd_municipio_ibge", "regiao"]])

        por_rd = pop.groupby("regiao", as_index=False)["valor"].sum()

        mapa = condepe.condepe_add_geometry(por_rd, level="rd", noronha=False)

        ax = mapa.plot(column=mapa["valor"] / 1e6, cmap="Blues", edgecolor="white",
                       linewidth=0.6, legend=True, figsize=(9, 3.6),
                       legend_kwds={"label": "milhões de habitantes", "shrink": 0.6})

        ax.set_axis_off()

        ax.set_title("População estimada por Região de Desenvolvimento, 2025", loc="left")

        print(fig("mapa_rd"))

        por_rd.sort_values("valor", ascending=False)
        """,
    ),
    (
        """
        Os contornos das regiões também servem de camada sobre um mapa
        municipal: a mortalidade infantil por município e, por cima, as doze
        regiões de saúde (as Geres):
        """,
        """
        geres = condepe.condepe_geometry("regiao_saude", noronha=False)

        ax = condepe.condepe_add_geometry(media, geometry=malha).plot(
            column="valor", cmap="Blues", legend=True, figsize=(9, 3.6),
            legend_kwds={"label": "por mil nascidos vivos", "shrink": 0.6},
            missing_kwds={"color": "lightgrey"})

        geres.boundary.plot(ax=ax, color="white", linewidth=1.1)

        ax.set_axis_off()

        ax.set_title("Mortalidade infantil (2022 a 2024) e regiões de saúde", loc="left")

        print(fig("mapa_saude"))
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
        reg_rm = condepe.condepe_regions("rm")

        rmr = reg_rm.loc[reg_rm["regiao"] == "Região Metropolitana do Recife",
                         "cd_municipio_ibge"].tolist()

        uti = condepe.condepe_series("datasus_leitos", "Leitos de UTI - Total",
                                     code=rmr, years=2024)

        pop = condepe.condepe_series("sidra_populacao_estimada", "Populacao residente estimada",
                                     code=rmr, years=2024)

        d = pop[["cd_municipio_ibge", "nm_municipio", "valor"]].merge(
            uti[["cd_municipio_ibge", "valor"]], on="cd_municipio_ibge",
            how="left", suffixes=("_pop", "_uti")).fillna({"valor_uti": 0})

        d["por_100mil"] = 1e5 * d["valor_uti"] / d["valor_pop"]

        mapa = condepe.condepe_add_geometry(d, geometry=malha, how="inner")

        ax = mapa.plot(column="por_100mil", cmap="Blues", edgecolor="white", linewidth=0.4,
                       legend=True, figsize=(5.5, 6.5),
                       legend_kwds={"label": "por 100 mil hab.", "shrink": 0.5})

        for _, r in mapa[mapa["por_100mil"] >= 40].iterrows():  # nm_municipio vem da malha
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


def _esc(x: str) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tabela_fontes_html(cat: pd.DataFrame, recolher: bool = False, nivel: int = 2) -> str:
    """Tabela das fontes no estilo das tabelas do Notion (classe fontes-notion,
    em assets/extra.css): uma por eixo, tema como etiqueta, linhas zebradas.
    Mesma marcação do site do pacote R."""
    temas = sorted(cat["tema"].unique())
    cor = {t: i % 9 for i, t in enumerate(temas)}
    out = []
    for eixo in sorted(cat["eixo"].unique()):
        d = cat[cat["eixo"] == eixo].sort_values(["tema", "id_fonte"])
        linhas = []
        for _, f in d.iterrows():
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
            linhas.append(
                f'<tr><td><span class="pill pill-{cor[f["tema"]]}">{_esc(f["tema"])}</span>'
                f"<br><code>{f['id_fonte'].replace('_', '_<wbr>')}</code></td>"
                f'<td>{_esc(f["descricao"])}<div class="origem">{_esc(f["fonte_original"])}'
                f"{abr}</div></td>"
                f'<td class="num">{periodo}</td>'
                f'<td class="num">{br(int(f["indicadores"]))}</td></tr>'
            )
        tabela = (
            '<div class="fontes-notion-wrap"><table class="fontes-notion">'
            "<thead><tr><th>Tema e fonte</th><th>Descrição e origem</th>"
            '<th class="num">Período</th><th class="num">Indicadores</th></tr></thead>'
            "<tbody>" + "".join(linhas) + "</tbody></table></div>"
        )
        n = len(d)
        resumo = (
            f"{n} {'fonte' if n == 1 else 'fontes'} · "
            f"{br(int(d['indicadores'].sum()))} indicadores"
        )
        if recolher:
            out.append(
                f'<details class="fontes-eixo"><summary><span class="eixo">{_esc(eixo)}</span> '
                f'<span class="resumo">{resumo}</span></summary>\n{tabela}\n</details>\n'
            )
        else:
            out.append(
                f"{'#' * nivel} {eixo}\n\n<p class=\"resumo-eixo\">{resumo}</p>\n\n{tabela}\n"
            )
    return "\n".join(out)


def resumo_catalogo(cat: pd.DataFrame) -> str:
    return (
        f"Versão **`{cat.attrs['version']}`** do catálogo: **{len(cat)} fontes**, "
        f"**{br(int(cat['indicadores'].sum()))} indicadores** e "
        f"**{br(int(cat['linhas'].sum()))} observações**."
    )


def pagina_fontes() -> None:
    """Relação das fontes, por eixo, gerada do catálogo."""
    cat = condepe.condepe_catalog()
    md = [
        "# Fontes do Observatório\n",
        resumo_catalogo(cat) + " A lista foi gerada com `condepe_catalog()`; o "
        "identificador (`id_fonte`) é o que se passa às demais funções. Cada fonte "
        "também tem uma ficha em <https://cf.pe.gov.br/observatorio>.\n",
        tabela_fontes_html(cat),
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

    # Página inicial: a mesma tabela, com os eixos recolhíveis, entre marcadores.
    ini, fim = "<!-- fontes:inicio -->", "<!-- fontes:fim -->"
    index = (DOCS / "index.md").read_text(encoding="utf-8")
    bloco = (
        f"{ini}\n## Fontes do Observatório\n\n"
        + resumo_catalogo(cat)
        + " O identificador da fonte é o que se passa às funções do pacote; clique num "
        "eixo para abrir a lista. A relação também está em "
        "[Fontes do Observatório](fontes.md).\n\n"
        + tabela_fontes_html(cat, recolher=True)
        + f"\n{fim}"
    )
    if ini in index:
        a, b = index.index(ini), index.index(fim) + len(fim)
        index = index[:a] + bloco + index[b:]
    else:
        marca = "## De onde vêm os dados"
        if marca not in index:
            raise SystemExit("index.md sem a seção '## De onde vêm os dados'")
        index = index.replace(marca, bloco + "\n\n" + marca, 1)
    (DOCS / "index.md").write_text(index, encoding="utf-8")
    print("gravado index.md (tabela das fontes)")


if __name__ == "__main__":
    page("primeiros-passos.md", PRIMEIROS_PASSOS)
    page("exemplos.md", EXEMPLOS)
    page("mapas.md", MAPAS)
    pagina_fontes()
