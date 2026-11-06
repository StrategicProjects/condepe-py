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

O catálogo é versionado; a versão e a citação a usar acompanham o resultado:

```python
print(cat.attrs["version"])

print(cat.attrs["citation"])
```

```text
2026-11-06_182408
Fontes originais indicadas em cada série (coluna fonte_original); dados coletados, padronizados e organizados pela Condepe/Fidem no Observatório de Pernambuco, versão 2026-11-06_182408, https://cf.pe.gov.br/observatorio.
```

Quantas fontes há em cada eixo, e quantos indicadores:

```python
cat.groupby("eixo").agg(fontes=("id_fonte", "size"), indicadores=("indicadores", "sum"))
```

```text
                fontes  indicadores
eixo                               
Economia            26        89374
Infraestrutura       3           39
Social              45        15062
Território           9         9384
```

Para achar uma fonte por assunto, filtre o catálogo como qualquer tabela:

```python
cat.loc[cat["tema"] == "Saúde", ["id_fonte", "descricao"]]
```

```text
                        id_fonte                                        descricao
64                   datasus_sim  Óbitos por residência (total, infantis, por ...
65                datasus_sinasc  Nascidos vivos por residência (sexo, parto, ...
66  datasus_mortalidade_infantil  Taxa de mortalidade infantil (óbitos de meno...
67      datasus_estabelecimentos    Estabelecimentos de saúde por tipo de unidade
68         datasus_profissionais  Vínculos de profissionais de saúde por ocupa...
69                datasus_leitos  Leitos existentes, SUS e contratados por tip...
70          datasus_equipamentos  Equipamentos de saúde em uso: total e grupos...
71               datasus_equipes  Equipes de saúde ativas em dezembro, total e...
72           datasus_internacoes  Internações hospitalares do SUS: mensais por...
```

## Os indicadores de uma fonte

A coluna `natureza` diz como somar no tempo: `estoque` é uma foto
(população, leitos em dezembro) e não se soma entre anos; `fluxo` é o
que aconteceu no período (nascimentos, internações) e se soma.

```python
condepe.condepe_indicators("datasus_mortalidade_infantil")
```

```text
                                    indicador_base                 unidade natureza  mensal  \
0  Taxa de mortalidade infantil (por mil nascid...  Por mil nascidos vivos  estoque   False   

   observacoes  localidades  ano_inicio  ano_fim  
0         1480          185        2017     2024
```

## Uma série

`condepe_series()` filtra uma fonte por indicador e, se pedido, por
código IBGE — 7 dígitos para município, `"26"` para o Estado — e por
ano. A população do Recife (2611606):

```python
recife = condepe.condepe_series(
    "sidra_populacao_estimada",
    "Populacao residente estimada",
    code="2611606",
    years=range(2010, 2027),
)

recife[["nm_municipio", "ano", "valor", "unidade"]]
```

```text
   nm_municipio   ano      valor  unidade
0        Recife  2011  1546516.0  Pessoas
1        Recife  2012  1555039.0  Pessoas
2        Recife  2013  1599513.0  Pessoas
3        Recife  2014  1608488.0  Pessoas
4        Recife  2015  1617183.0  Pessoas
5        Recife  2016  1625583.0  Pessoas
6        Recife  2017  1633697.0  Pessoas
7        Recife  2018  1637834.0  Pessoas
8        Recife  2019  1645727.0  Pessoas
9        Recife  2020  1653461.0  Pessoas
10       Recife  2021  1661017.0  Pessoas
11       Recife  2024  1587707.0  Pessoas
12       Recife  2025  1588376.0  Pessoas
13       Recife  2026  1588983.0  Pessoas
```

O IBGE não publica estimativa municipal em ano de Censo nem no
seguinte (2010, 2022, 2023): esses anos simplesmente não aparecem —
ausência nunca vira zero.

Os códigos IBGE ficam em `condepe_localities()`:

```python
loc = condepe.condepe_localities()

loc[loc["nm_municipio"].str.contains("Petrolina|Caruaru|Garanhuns")]
```

```text
    cd_municipio_ibge nm_municipio
45            2604106      Caruaru
67            2606002    Garanhuns
126           2611101    Petrolina
```

## Séries mensais

Fontes mensais trazem o período duas vezes: em `mes` e no rótulo
completo, `indicador` (`"… [MM/AAAA]"`). Filtre por `indicador_base`,
o rótulo sem o período:

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

## Uma fonte inteira e as colunas

`condepe_data()` devolve a fonte completa. As 15 colunas mantêm os
nomes com que o Observatório publica, para que todo resultado possa
ser rastreado até os arquivos oficiais:

```python
nasc = condepe.condepe_data("datasus_sinasc")

list(nasc.columns)
```

```text
['cd_municipio_ibge', 'nm_municipio', 'ano', 'mes', 'indicador', 'indicador_base', 'valor', 'unidade', 'natureza', 'id_fonte', 'eixo', 'tema', 'assunto', 'fonte_original', 'arquivo_origem']
```

| Coluna | Significado |
|---|---|
| `cd_municipio_ibge`, `nm_municipio` | código IBGE (7 dígitos; `"26"` é o Estado) e nome |
| `ano`, `mes` | ano; mês nas séries mensais (vazio nas demais) |
| `indicador`, `indicador_base` | rótulo completo (com `[MM/AAAA]` se mensal) e rótulo sem o período |
| `valor`, `unidade`, `natureza` | valor, unidade, `estoque` ou `fluxo` |
| `id_fonte`, `eixo`, `tema`, `assunto` | a fonte e seu lugar no catálogo |
| `fonte_original`, `arquivo_origem` | órgão de origem e o arquivo ou a consulta de onde o valor veio |

Para passar ao formato largo (um indicador por coluna), use `pivot`:

```python
partos = nasc[(nasc["ano"] == 2024) & nasc["indicador_base"].str.contains("Total|Parto")]

partos.pivot(index="nm_municipio", columns="indicador_base", values="valor").head()
```

```text
indicador_base         Nascidos vivos por ocorrência - Total  \
nm_municipio                                                   
Abreu e Lima                                             8.0   
Afogados da Ingazeira                                 1913.0   
Afrânio                                                133.0   
Agrestina                                              500.0   
Alagoinha                                               14.0   

indicador_base         Nascidos vivos por residência - Parto cesáreo  \
nm_municipio                                                           
Abreu e Lima                                                   499.0   
Afogados da Ingazeira                                          348.0   
Afrânio                                                        143.0   
Agrestina                                                      221.0   
Alagoinha                                                       68.0   

indicador_base         Nascidos vivos por residência - Parto vaginal  \
nm_municipio                                                           
Abreu e Lima                                                   536.0   
Afogados da Ingazeira                                          164.0   
Afrânio                                                         86.0   
Agrestina                                                      113.0   
Alagoinha                                                       86.0   

indicador_base         Nascidos vivos por residência - Total  
nm_municipio                                                  
Abreu e Lima                                          1037.0  
Afogados da Ingazeira                                  512.0  
Afrânio                                                229.0  
Agrestina                                              334.0  
Alagoinha                                              154.0
```

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
