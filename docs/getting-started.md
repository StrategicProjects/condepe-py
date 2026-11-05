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

```python
cat = condepe.condepe_catalog()

cat[["id_fonte", "tema", "indicadores", "ano_inicio", "ano_fim"]].head(8)
```

```text
                           id_fonte                tema  indicadores  ano_inicio  ano_fim
0          sidra_populacao_estimada          Demografia            1        2001     2026
1               sidra_pib_municipal                 PIB            7        2002     2023
2                  sidra_censo_2022          Demografia            3        2022     2022
3              sidra_area_densidade  Posição e Extensão            2        2010     2010
4                         sidra_pam        Agropecuária          243        2020     2025
5                 sidra_ppm_rebanho        Agropecuária           10        2020     2025
6           sidra_ppm_origem_animal        Agropecuária            9        2020     2025
7  sidra_registro_civil_nascimentos          Demografia            1        2020     2024
```

The catalogue is versioned; the version and the citation travel with it:

```python
print(cat.attrs["version"])

print(cat.attrs["citation"])
```

```text
2026-11-05_171049
Condepe/Fidem, Observatório de Pernambuco — Base de Dados do Estado, version 2026-11-05_171049, https://cf.pe.gov.br/observatorio (CC BY 4.0).
```

Filter it like any data frame to find a subject:

```python
cat.loc[cat["tema"] == "Saúde", ["id_fonte", "descricao"]]
```

```text
                        id_fonte                                        descricao
63                   datasus_sim  Óbitos por residência (total, infantis, por ...
64                datasus_sinasc  Nascidos vivos por residência (sexo, parto, ...
65  datasus_mortalidade_infantil  Taxa de mortalidade infantil (óbitos de meno...
66      datasus_estabelecimentos    Estabelecimentos de saúde por tipo de unidade
67         datasus_profissionais  Vínculos de profissionais de saúde por ocupa...
68                datasus_leitos  Leitos existentes, SUS e contratados por tip...
69          datasus_equipamentos  Equipamentos de saúde em uso: total e grupos...
70               datasus_equipes  Equipes de saúde ativas em dezembro, total e...
71           datasus_internacoes  Internações hospitalares do SUS: mensais por...
```

## The indicators of a source

```python
condepe.condepe_indicators("datasus_mortalidade_infantil")
```

```text
                                    indicador_base                 unidade natureza  mensal  \
0  Taxa de mortalidade infantil (por mil nascid...  Por mil nascidos vivos  estoque   False   

   observacoes  localidades  ano_inicio  ano_fim  
0         1480          185        2017     2024
```

## A series

`condepe_series()` filters a source by indicator and, optionally, by
IBGE code (7 digits for municipalities, `"26"` for the State) and by
year. The population of Recife (2611606):

```python
recife = condepe.condepe_series(
    "sidra_populacao_estimada",
    "Populacao residente estimada",
    code="2611606",
    years=range(2015, 2027),
)

recife[["nm_municipio", "ano", "valor", "unidade"]]
```

```text
  nm_municipio   ano      valor  unidade
0       Recife  2015  1617183.0  Pessoas
1       Recife  2016  1625583.0  Pessoas
2       Recife  2017  1633697.0  Pessoas
3       Recife  2018  1637834.0  Pessoas
4       Recife  2019  1645727.0  Pessoas
5       Recife  2020  1653461.0  Pessoas
6       Recife  2021  1661017.0  Pessoas
7       Recife  2024  1587707.0  Pessoas
8       Recife  2025  1588376.0  Pessoas
9       Recife  2026  1588983.0  Pessoas
```

Look up codes with `condepe_localities()`:

```python
loc = condepe.condepe_localities()

loc[loc["nm_municipio"].str.contains("Petrolina|Caruaru")]
```

```text
    cd_municipio_ibge nm_municipio
45            2604106      Caruaru
126           2611101    Petrolina
```

## Monthly series

Monthly sources carry the period twice: in `mes`, and in the full
label `indicador` (`"… [MM/YYYY]"`). Filter by `indicador_base`, the
label without the period:

```python
suape = condepe.condepe_series(
    "porto_suape_carga", "Porto de Suape - Carga bruta total", years=2026
)

suape[["ano", "mes", "indicador", "valor", "unidade"]]
```

```text
    ano  mes                                     indicador       valor unidade
0  2026    1  Porto de Suape - Carga bruta total [01/2026]  2193515.44       t
1  2026    2  Porto de Suape - Carga bruta total [02/2026]  2084475.15       t
2  2026    3  Porto de Suape - Carga bruta total [03/2026]  2223491.77       t
3  2026    4  Porto de Suape - Carga bruta total [04/2026]  2360768.32       t
4  2026    5  Porto de Suape - Carga bruta total [05/2026]  2403537.67       t
5  2026    6  Porto de Suape - Carga bruta total [06/2026]  2445490.37       t
6  2026    7  Porto de Suape - Carga bruta total [07/2026]  2363978.30       t
7  2026    8  Porto de Suape - Carga bruta total [08/2026]  2726020.02       t
8  2026    9  Porto de Suape - Carga bruta total [09/2026]  2453353.05       t
```

## Whole sources and the columns

`condepe_data()` returns a source in full. The 15 columns keep the
Portuguese names under which the Observatory publishes them, so a
result can always be traced back to the official files:

```python
nasc = condepe.condepe_data("datasus_sinasc")

list(nasc.columns)
```

```text
['cd_municipio_ibge', 'nm_municipio', 'ano', 'mes', 'indicador', 'indicador_base', 'valor', 'unidade', 'natureza', 'id_fonte', 'eixo', 'tema', 'assunto', 'fonte_original', 'arquivo_origem']
```

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
