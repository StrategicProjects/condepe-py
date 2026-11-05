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

```python
url = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/26"
    "?formato=application/vnd.geo%2Bjson&intrarregiao=municipio&qualidade=intermediaria"
)

import io, requests

malha = gpd.read_file(io.BytesIO(requests.get(url, timeout=60).content))

print(len(malha), "municípios;", malha.crs)

malha.head(3)
```

```text
185 municípios; EPSG:4326
   codarea                                         geometry
0  2600054  POLYGON ((-35.031 -7.9298, -35.0254 -7.9258,...
1  2600104  POLYGON ((-37.7048 -7.6169, -37.7001 -7.6244...
2  2600203  POLYGON ((-41.3583 -8.7076, -41.3435 -8.722,...
```

Fernando de Noronha (2605459) fica a 545 km da costa; num mapa do
estado inteiro ele espreme o continente para a esquerda. Os mapas
abaixo o deixam de fora:

```python
malha = malha[malha["codarea"] != "2605459"]

len(malha)
```

```text
184
```

## Mortalidade infantil

A taxa é ruidosa nos municípios pequenos (poucos nascimentos por ano);
a média de três anos é mais estável:

```python
tmi = condepe.condepe_series(
    "datasus_mortalidade_infantil",
    "Taxa de mortalidade infantil (por mil nascidos vivos)",
    years=[2022, 2023, 2024],
)

media = tmi.groupby("cd_municipio_ibge", as_index=False)["valor"].mean()

mapa = malha.merge(media, left_on="codarea", right_on="cd_municipio_ibge", how="left")

ax = mapa.plot(
    column="valor",
    cmap="Blues",
    edgecolor="white",
    linewidth=0.15,
    legend=True,
    figsize=(9, 3.6),
    legend_kwds={"label": "por mil nascidos vivos", "shrink": 0.6},
    missing_kwds={"color": "lightgrey"},
)

ax.set_axis_off()

ax.set_title("Mortalidade infantil, média de 2022 a 2024", loc="left")

print(fig("mapa_tmi"))
```

![mapa_tmi](assets/mapa_tmi.png)

## Variação da população entre os Censos

Para uma variação, que tem sinal, classes com cores divergentes deixam
claro quem cresceu e quem encolheu. População dos Censos de 2010 e
2022 (as estimativas anuais não cobrem anos de Censo):

```python
pop = condepe.condepe_series(
    "sidra_censo_cor_raca", "IBGE - População residente - Total", years=[2010, 2022]
)

w = pop.pivot(index="cd_municipio_ibge", columns="ano", values="valor")

w["var"] = 100 * (w[2022] / w[2010] - 1)

rotulos = ["queda > 5%", "queda até 5%", "alta até 5%", "alta de 5 a 15%", "alta > 15%"]

w["classe"] = pd.cut(w["var"], [-1e9, -5, 0, 5, 15, 1e9], labels=rotulos)

mapa = malha.merge(w.reset_index(), left_on="codarea", right_on="cd_municipio_ibge")

cores = dict(zip(rotulos, ["#ff6700", "#ffc49a", "#bcd6f5", "#3d84df", "#0c2856"]))

ax = mapa.plot(
    color=mapa["classe"].map(cores).astype(str), edgecolor="white", linewidth=0.15, figsize=(9, 3.6)
)

from matplotlib.patches import Patch

ax.legend(
    handles=[Patch(color=c, label=r) for r, c in cores.items()],
    loc="lower center",
    ncol=5,
    frameon=False,
    fontsize=8,
    bbox_to_anchor=(0.5, -0.12),
)

ax.set_axis_off()

ax.set_title("Variação da população entre os Censos de 2010 e 2022", loc="left")

print(fig("mapa_populacao"))

mapa["classe"].value_counts().sort_index()
```

```text
classe
queda > 5%         48
queda até 5%       43
alta até 5%        34
alta de 5 a 15%    47
alta > 15%         12
Name: count, dtype: int64
```

![mapa_populacao](assets/mapa_populacao.png)

## Região Metropolitana do Recife

Para ver um recorte, filtre a malha antes de desenhar. Os 15
municípios da RMR (Goiana entrou em 2018) e os leitos de UTI por 100
mil habitantes em dezembro de 2024; município sem leito no CNES conta
como zero leitos de UTI:

```python
rmr = [
    "2600054",
    "2601052",
    "2602902",
    "2603454",
    "2606200",
    "2606804",
    "2607208",
    "2607604",
    "2607752",
    "2607901",
    "2609402",
    "2609600",
    "2610707",
    "2611606",
    "2613701",
]

uti = condepe.condepe_series("datasus_leitos", "Leitos de UTI - Total", code=rmr, years=2024)

pop = condepe.condepe_series(
    "sidra_populacao_estimada", "Populacao residente estimada", code=rmr, years=2024
)

d = (
    pop[["cd_municipio_ibge", "nm_municipio", "valor"]]
    .merge(
        uti[["cd_municipio_ibge", "valor"]],
        on="cd_municipio_ibge",
        how="left",
        suffixes=("_pop", "_uti"),
    )
    .fillna({"valor_uti": 0})
)

d["por_100mil"] = 1e5 * d["valor_uti"] / d["valor_pop"]

mapa = malha[malha["codarea"].isin(rmr)].merge(d, left_on="codarea", right_on="cd_municipio_ibge")

ax = mapa.plot(
    column="por_100mil",
    cmap="Blues",
    edgecolor="white",
    linewidth=0.4,
    legend=True,
    figsize=(5.5, 6.5),
    legend_kwds={"label": "por 100 mil hab.", "shrink": 0.5},
)

for _, r in mapa[mapa["por_100mil"] >= 40].iterrows():
    p = r.geometry.representative_point()
    ax.annotate(
        r["nm_municipio"], (p.x, p.y), ha="center", fontsize=8, color="white", weight="bold"
    )

ax.set_axis_off()

ax.set_title("RMR: leitos de UTI por 100 mil hab., dez/2024", loc="left", fontsize=10)

print(fig("mapa_rmr"))

d.sort_values("por_100mil", ascending=False)[["nm_municipio", "valor_uti", "por_100mil"]].round(1)
```

```text
               nm_municipio  valor_uti  por_100mil
13                   Recife     1627.0       102.5
11                   Olinda      155.0        42.4
10                   Moreno       20.0        34.7
4                    Goiana       20.0        23.5
2   Cabo de Santo Agostinho       50.0        23.0
14     São Lourenço da Mata       25.0        21.2
0              Abreu e Lima       22.0        21.2
12                 Paulista       72.0        19.8
9   Jaboatão dos Guararapes      124.0        18.1
1                 Araçoiaba        0.0         0.0
3                Camaragibe        0.0         0.0
5                  Igarassu        0.0         0.0
6                   Ipojuca        0.0         0.0
7         Ilha de Itamaracá        0.0         0.0
8                Itapissuma        0.0         0.0
```

![mapa_rmr](assets/mapa_rmr.png)

Os leitos concentram-se no Recife, que atende pacientes de toda a
região: o indicador mede oferta no município, não acesso de quem mora
nele.
