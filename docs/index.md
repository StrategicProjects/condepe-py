# condepe <img src="assets/logo.svg" align="right" height="139" alt="logo do condepe" />

Acesso, pelo Python, aos dados abertos do **Observatório de Pernambuco**,
publicados pela [Condepe/Fidem](https://cf.pe.gov.br) (Agência Estadual de
Planejamento e Pesquisas de Pernambuco): séries municipais de população,
economia, finanças públicas, trabalho, educação, saúde, segurança, transporte e
meio ambiente para os 185 municípios de Pernambuco.

Todas as fontes são publicadas no mesmo formato longo (uma observação por
linha, 15 colunas), e por isso um único conjunto de funções atende a todas,
devolvendo `pandas.DataFrame`.

## Instalação

```bash
pip install condepe
# versão em desenvolvimento:
pip install git+https://github.com/StrategicProjects/condepe-py
```

## Uso

```python
import condepe

# Fontes disponíveis (uma por linha) e a versão do catálogo
cat = condepe.condepe_catalog()
cat.attrs["version"]

# Indicadores de uma fonte
condepe.condepe_indicators("sidra_populacao_estimada")

# Uma série: Recife (IBGE 2611606), de 2020 em diante
condepe.condepe_series(
    "sidra_populacao_estimada",
    "Populacao residente estimada",
    code="2611606",
    years=range(2020, 2027),
)

# Uma fonte inteira e a lista de municípios
condepe.condepe_data("datasus_sinasc")
condepe.condepe_localities()
```

Os nomes das colunas ficam em português, como publicados, para que todo
resultado possa ser rastreado até os arquivos oficiais: `cd_municipio_ibge`,
`nm_municipio`, `ano`, `mes`, `indicador`, `indicador_base`, `valor`,
`unidade`, `natureza`, `id_fonte`, `eixo`, `tema`, `assunto`, `fonte_original`,
`arquivo_origem`. Séries mensais trazem o período em `indicador`
(`"… [MM/AAAA]"`) e em `mes`; `indicador_base` é o rótulo sem ele.

Documentação: <https://strategicprojects.github.io/condepe-py/> — primeiros
passos, exemplos, mapas e a relação das fontes.

## De onde vêm os dados

- **Canônico:** <https://cf.pe.gov.br/observatorio/dados/atual/>
- **Espelho (reserva):** o dataset do Hugging Face
  [`mlkwy/observatorio-pernambuco`](https://huggingface.co/datasets/mlkwy/observatorio-pernambuco),
  com os mesmos caminhos.

Os arquivos ficam em cache em disco por versão do catálogo
(`condepe_cache_dir()`) e são conferidos pelo SHA-256 publicado no catálogo; o
catálogo vale por 6 horas. As variáveis `CONDEPE_URL`, `CONDEPE_MIRROR_URL` e
`CONDEPE_CACHE_DIR` substituem os padrões.

## Citação e licença

Dados: Condepe/Fidem, *Observatório de Pernambuco — Base de Dados do Estado*,
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br). A citação
com a versão em uso está em `condepe_catalog().attrs["citation"]`.

Código: MIT. Para ler ou gravar buckets *privados* do `s3.pe.gov.br` com chave
de acesso, veja o [`s3pe`](https://github.com/StrategicProjects/s3pe); o
`condepe` não precisa de chave, porque os dados abertos do Observatório são
públicos. Há um pacote R com as mesmas funções:
[`condepe` para R](https://github.com/StrategicProjects/condepe-r).
