# ------------------------------------------------------------------
# 1. IMPORTAR BIBLIOTECAS E VARIÁVEIS GLOBAIS
# ------------------------------------------------------------------

import requests
import time
import csv
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import math
import glob
import os


BASE_URL = "https://mesaquest.com.br"
LISTA_MESAS_URL = "https://mesaquest.com.br/mesas"
HEADERS = {"User-Agent": "Mozilla/5.0"}

data_hoje = datetime.now().strftime("%Y%m%d")

# ------------------------------------------------------------------
# 2. DEFINIR AS FUNÇṌES
# ------------------------------------------------------------------

# coleta as urls das mesas
def coletar_urls_mesas():
    urls = []
    page = 1

    while True:
        r = requests.get(
            f"{LISTA_MESAS_URL}?page={page}",
            headers=HEADERS,
        )
        soup = BeautifulSoup(r.text, "html.parser")

        encontrados = 0
        for a in soup.select('a[href^="/mesas/"]'):
            url = urljoin(BASE_URL, a["href"])
            if url not in urls:
                urls.append(url)
                encontrados += 1

        if encontrados == 0:
            break

        page += 1
        time.sleep(0.4)

    return urls

# extrai as informações das mesas
def extrair_detalhes_mesa(url):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    dados = {
        "url": url,
        "nome": "",
        "sistema": "",
        "softwares": "",
        "tags_superiores": "",
        "requisito": "",
        "tags": "",
        "modalidade": "",
        "inicio": "",
        "idioma": "",
        "periodicidade": "",
        "dias_jogo": "",
        "vagas": "",
        "preco": "",
        "mestre_nome": "",
        "mestre_url": "",
    }


    # Nome da mesa
    h1 = soup.find("h1")
    if h1:
        dados["nome"] = h1.get_text(strip=True)


    # Sistema
    p_sistema = None
    if h1:
        p_sistema = h1.find_next("p", class_="text-white/90")
        if p_sistema:
            dados["sistema"] = p_sistema.get_text(strip=True)

    # Tags superiores
    tags_sup = []
    if h1:
        container = h1.find_previous(
            "div",
            class_="flex flex-wrap gap-2 mb-4",
        )
        if container:
            for div in container.find_all("div", recursive=False):
                if div.find("svg"):
                    continue
                txt = div.get_text(strip=True)
                if txt:
                    tags_sup.append(txt)

    dados["tags_superiores"] = ", ".join(tags_sup)


    # Softwares
    softwares = []
    if p_sistema:
        bloco_soft = p_sistema.find_next(
            "div",
            class_="flex flex-wrap gap-2 mt-2",
        )
        if bloco_soft:
            for div in bloco_soft.find_all("div", recursive=False):
                txt = div.get_text(strip=True)
                if txt:
                    softwares.append(txt)

    dados["softwares"] = ", ".join(softwares)

    # Requisitos
    requisitos = []
    titulo_req = soup.find(
        "h3",
        string=lambda x: x and x.strip() == "Requisitos para participar",
    )
    if titulo_req:
        card = titulo_req.find_parent("div", class_="rounded-lg")
        if card:
            container = card.select_one(
                "div.p-6.pt-0 div.flex.flex-wrap.gap-2"
            )
            if container:
                itens = container.find_all(
                    "div",
                    class_="inline-flex",
                    recursive=False,
                )
                requisitos = [
                    i.get_text(strip=True) for i in itens
                ]

    dados["requisito"] = ", ".join(requisitos)

    # Tags
    tags_lista = []
    titulo_tags = soup.find(
        "h3",
        string=lambda x: x and x.strip() == "Tags",
    )
    if titulo_tags:
        card = titulo_tags.find_parent("div", class_="rounded-lg")
        if card:
            container = card.select_one(
                "div.p-6.pt-0 div.flex.flex-wrap.gap-2"
            )
            if container:
                itens = container.find_all(
                    "div",
                    class_="inline-flex",
                    recursive=False,
                )
                tags_lista = [
                    i.get_text(strip=True) for i in itens
                ]

    dados["tags"] = ", ".join(tags_lista)

    # Campos com label
    for span in soup.find_all("span"):
        label = span.get_text(strip=True)

        if label == "Preço":
            dados["preco"] = span.find_next(
                "span"
            ).get_text(" ", strip=True)

        elif label == "Modalidade":
            dados["modalidade"] = span.find_next(
                "span"
            ).get_text(" ", strip=True)

        elif label == "Início":
            dados["inicio"] = span.find_next(
                "span"
            ).get_text(" ", strip=True)

        elif label == "Idiomas":
            dados["idioma"] = span.find_next(
                "span"
            ).get_text(" ", strip=True)

        elif label == "Periodicidade":
            dados["periodicidade"] = span.find_next(
                "span"
            ).get_text(" ", strip=True)

        elif label == "Dias de Jogo":
            dados["dias_jogo"] = span.find_next(
                "span"
            ).get_text(" ", strip=True)

        elif label == "Jogadores":
            dados["vagas"] = span.find_next(
                "span"
            ).get_text(" ", strip=True)

    # Mestre
    h3_mestre = soup.select_one(
        "h3.font-semibold.text-foreground"
    )
    if h3_mestre:
        dados["mestre_nome"] = h3_mestre.get_text(strip=True)

        link_mestre = h3_mestre.find_parent("a")
        if link_mestre and link_mestre.has_attr("href"):
            dados["mestre_url"] = urljoin(
                BASE_URL,
                link_mestre["href"],
            )

    return dados

# extrair a hora de término da mesa
def extrair_end_date_listagem():
    end_dates = {}
    page = 1

    while True:
        url = f"{LISTA_MESAS_URL}?page={page}"
        r = requests.get(url, headers=HEADERS)

        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("a[href^='/mesas/']")

        if not cards:
            break

        for link in cards:
            mesa_id = link["href"].split("/")[-1]

            card = link.find_parent("div", class_="p-4")
            if not card:
                continue

            spans = card.find_all(
                "span",
                class_="truncate",
            )
            if len(spans) < 2:
                continue

            data_txt = spans[-2].get_text(strip=True)
            horario_txt = spans[-1].get_text(strip=True)

            if "-" not in horario_txt:
                continue

            try:
                _, hora_fim = [
                    x.strip() for x in horario_txt.split("-")
                ]
                data = datetime.strptime(
                    data_txt,
                    "%d/%m/%Y",
                )
                hora, minuto = map(
                    int,
                    hora_fim.split(":"),
                )

                end_dates[mesa_id] = datetime(
                    year=data.year,
                    month=data.month,
                    day=data.day,
                    hour=hora,
                    minute=minuto,
                )

            except ValueError:
                continue

        page += 1

    return end_dates

# calcular o preço mensal da mesa com base no preço da sessão
def calcular_preco_mes(row):
    if pd.isna(row["preco_sessao"]):
        return np.nan

    if pd.isna(row["dias_jogo"]) or row["dias_jogo"] == "":
        qtd_dias = 1
    else:
        qtd_dias = len(
            [
                d
                for d in row["dias_jogo"].split(",")
                if d.strip()
            ]
        )

    if row["periodicidade"] == "Quinzenal":
        fator = 2
    elif row["periodicidade"] == "Semanal":
        fator = 4
    else:
        fator = 1

    preco_mes = row["preco_sessao"] * qtd_dias * fator

    return int(round(preco_mes, 0))

# converte hora decimais para hh:mm
def decimal_para_hhmm(valor):
    if not isinstance(valor, (int, float)):
        return pd.NA

    if math.isnan(valor):
        return pd.NA

    horas = int(valor)
    minutos = int(round((valor - horas) * 60))

    return f"{horas}:{minutos:02d}"

# apagar bases de dados antigas
def apagar_arquivos_anteriores(arquivos, data_hoje, n_dias):
    # Converter data_hoje para o tipo datetime
    data_atual = datetime.strptime(data_hoje, "%Y%m%d")

    # Calcular a data limite (N dias atrás)
    data_limite = data_atual - timedelta(days=n_dias)

    for arquivo in arquivos:
        try:
            # Extrair a data do nome do arquivo (primeiros 8 caracteres)
            nome_arquivo = os.path.basename(arquivo)
            data_arquivo_str = nome_arquivo.split("_")[0]
            data_arquivo = datetime.strptime(data_arquivo_str, '%Y%m%d')

            # Se a data do arquivo for menor ou igual à data limite, excluir o arquivo
            if data_arquivo <= data_limite:
                os.remove(arquivo)
                print(f"Arquivo {arquivo} removido.")
        except ValueError:
            print(f"Erro ao processar o arquivo {arquivo}. Ignorando.")

# ------------------------------------------------------------------
# 3. EXTRAIR OS DADOS DAS MESAS
# ------------------------------------------------------------------

print("Coletando URLs das mesas...")
urls = coletar_urls_mesas()
print(f"{len(urls)} mesas encontradas.")

dados_mesas = []
for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] {url}")
    dados_mesas.append(extrair_detalhes_mesa(url))
    time.sleep(0.4)

# Cria o DataFrame
mesas_df = pd.DataFrame(dados_mesas)

# ------------------------------------------------------------------
# 4. TRATAMENTO DOS DADOS
# ------------------------------------------------------------------

# Tratamento da coluna modalidade
mesas_df["modalidade"] = mesas_df["modalidade"].str.replace(
    " , ", ", ", regex=False
)

mesas_df["modalidade_tipo"] = np.where(
    mesas_df["modalidade"] == "Online",
    "Online",
    "Presencial",
)

# Tratamento da coluna preço
mesas_df["preco_sessao"] = (
    mesas_df["preco"]
    .str.replace(r"[^\d,]", "", regex=True)
    .str.replace(",", ".", regex=False)
    .replace("", np.nan)
    .astype(float)
    .round(2)
)

mesas_df = mesas_df.drop(columns=["preco"])

mesas_df["preco_mes"] = (
    mesas_df.apply(calcular_preco_mes, axis=1)
    .astype("float64")
    .round(2)
)

# Renomeações e normalizações
mesas_df.rename(columns={"nome": "mesa_nome"}, inplace=True)
mesas_df.rename(columns={"url": "mesa_id"}, inplace=True)

mesas_df["mesa_id"] = mesas_df["mesa_id"].str.replace(
    "https://mesaquest.com.br/mesas/",
    "",
    regex=False,
)

# Criação da coluna end_date
end_dates = extrair_end_date_listagem()

mesas_df["end_date"] = pd.to_datetime(
    mesas_df["mesa_id"].map(end_dates),
    errors="coerce",
)

# Normalização do ID do usuário
mesas_df.rename(columns={"mestre_url": "user_id"}, inplace=True)

mesas_df["user_id"] = mesas_df["user_id"].str.replace(
    "https://mesaquest.com.br/usuario/",
    "",
    regex=False,
)

# Separação das tags superiores
mesas_df[["mesa_tipo", "nivel_jogadores"]] = mesas_df[
    "tags_superiores"
].str.split(", ", n=1, expand=True)

mesas_df = mesas_df.drop(columns=["tags_superiores"])

# Conversão da coluna inicio
mesas_df["start_date"] = pd.to_datetime(
    mesas_df["inicio"],
    format="%d/%m/%Y às %H:%M",
)

mesas_df = mesas_df.drop(columns=["inicio"])

# Correção de virada de dia (obrigatória)
mask_virada = (
    mesas_df["end_date"].notna()
    & (mesas_df["end_date"] <= mesas_df["start_date"])
)

mesas_df.loc[mask_virada, "end_date"] += pd.Timedelta(days=1)

# Duração
mesas_df["duracao"] = (
    (mesas_df["end_date"] - mesas_df["start_date"])
    .dt.total_seconds()
    .div(3600)
    .round(2)
)

mesas_df["duracao_hhmm"] = mesas_df["duracao"].apply(
    decimal_para_hhmm
)

# Conversão das datas para ISO 8601
mesas_df["start_date"] = mesas_df["start_date"].dt.strftime(
    "%Y-%m-%d %H:%M:%S"
)

mesas_df["start_date"] = pd.to_datetime(
    mesas_df["start_date"],
    errors="coerce",
)

mesas_df["end_date"] = mesas_df["end_date"].dt.strftime(
    "%Y-%m-%d %H:%M:%S"
)

mesas_df["end_date"] = pd.to_datetime(
    mesas_df["end_date"],
    errors="coerce",
)

# Tratamento da coluna vagas
mesas_df["vagas"] = mesas_df["vagas"].str.replace(
    " vagas preenchidas",
    "",
    regex=False,
)

mesas_df[["vagas_preenchidas", "vagas_total"]] = mesas_df[
    "vagas"
].str.split(" / ", n=1, expand=True)

mesas_df = mesas_df.drop(columns=["vagas"])

mesas_df["vagas_preenchidas"] = mesas_df["vagas_preenchidas"].astype(
    int
)
mesas_df["vagas_total"] = mesas_df["vagas_total"].astype(int)

mesas_df["lotacao_mesa"] = (
    mesas_df["vagas_preenchidas"] / mesas_df["vagas_total"]
).round(2)

# Normalização de dias_jogo
mesas_df["dias_jogo"] = (
    mesas_df["dias_jogo"]
    .fillna("")
    .str.lower()
)

mapa_dias = {
    "seg": "segunda",
    "ter": "terça",
    "qua": "quarta",
    "qui": "quinta",
    "sex": "sexta",
    "sáb": "sábado",
    "sab": "sábado",
    "dom": "domingo",
}

mapa_weekday = {
    0: "segunda",
    1: "terça",
    2: "quarta",
    3: "quinta",
    4: "sexta",
    5: "sábado",
    6: "domingo",
}

for dia in mapa_weekday.values():
    mesas_df[f"dias_jogo_{dia}"] = False

for idx, row in mesas_df.iterrows():

    if row["dias_jogo"].strip():
        for abrev, dia in mapa_dias.items():
            if abrev in row["dias_jogo"]:
                mesas_df.at[idx, f"dias_jogo_{dia}"] = True

    elif pd.notna(row["start_date"]):
        weekday = row["start_date"].weekday()
        dia = mapa_weekday.get(weekday)
        if dia:
            mesas_df.at[idx, f"dias_jogo_{dia}"] = True

mesas_df = mesas_df.drop(columns=["dias_jogo"])

# Limpeza de textos
mesas_df["mesa_nome"] = (
    mesas_df["mesa_nome"]
    .str.replace(r"[^\w\s]", "", regex=True)
    .str.strip()
)

mesas_df["mestre_nome"] = (
    mesas_df["mestre_nome"]
    .str.replace(r"[^\w\s]", "", regex=True)
    .str.strip()
)

# Criação da coluna dia da semana
mesas_df["dia_semana_mesa"] = mesas_df["start_date"].dt.day_name()

# Cria a coluna com a fonte dos dados
mesas_df['source'] = 'mesaquest'

# Criando faixas de ocupação das mesas
mesas_df["faixa_lotacao_mesa"] = pd.cut(
    mesas_df["lotacao_mesa"],
    bins=[0, 0.25, 0.5, 0.75, 1],
    labels=["0–25%", "25–50%", "50–75%", "75–100%"]
    )

# Criando faixas de duração
mesas_df["faixa_duracao"] = pd.cut(
    mesas_df["duracao"],
    bins=[0, 2, 3, 4, 6, 12],
    labels=["0-2h", "2–3h", "3–4h", "4–6h", "6h+"]
)

# Reorganização final das colunas
mesas_df = mesas_df[['source', 'mesa_id', 'user_id', 'mesa_nome', 'mesa_tipo',
                     'mestre_nome', 'sistema', 'start_date', 'end_date',
                     'dia_semana_mesa', 'duracao', 'duracao_hhmm',
                     'faixa_duracao', 'modalidade', 'modalidade_tipo',
                     'nivel_jogadores', 'idioma', 'periodicidade',
                     'preco_sessao', 'preco_mes', 'vagas_preenchidas', 'vagas_total',
                     'lotacao_mesa', 'faixa_lotacao_mesa', 'dias_jogo_segunda',
                     'dias_jogo_terça', 'dias_jogo_quarta', 'dias_jogo_quinta',
                     'dias_jogo_sexta', 'dias_jogo_sábado', 'dias_jogo_domingo',
                     'softwares', 'requisito', 'tags']]

print("DataFrame gerado com sucesso.")

# ------------------------------------------------------------------
# 5. Leitura do arquivo anterior e atualização da base de dados
# ------------------------------------------------------------------

# Ler CSV antigo

# Definindo o dicionário com nome_da_coluna: tipo_de_dado
schema = {
    "source": "object",
    "mesa_id": "object",
    "user_id": "object",
    "mesa_nome": "object",
    "mesa_tipo": "object",
    "mestre_nome": "object",
    "sistema": "object",
    "dia_semana_mesa": "object",
    "dia_semana_num": "int64",
    "duracao": "float64",
    "duracao_hhmm": "object",
    "duracao_sem_outliers": "float64",
    "faixa_duracao": "category",
    "modalidade": "object",
    "modalidade_tipo": "object",
    "nivel_jogadores": "object",
    "idioma": "object",
    "periodicidade": "object",
    "preco_sessao": "float64",
    "preco_sessao_sem_outliers": "float64",
    "preco_mes": "float64",
    "preco_mes_sem_outliers": "float64",
    "vagas_preenchidas": "int64",
    "vagas_total": "int64",
    "lotacao_mesa": "float64",
    "faixa_lotacao_mesa": "category",
    "dias_jogo_segunda": "boolean",
    "dias_jogo_terça": "boolean",
    "dias_jogo_quarta": "boolean",
    "dias_jogo_quinta": "boolean",
    "dias_jogo_sexta": "boolean",
    "dias_jogo_sábado": "boolean",
    "dias_jogo_domingo": "boolean",
    "softwares": "object",
    "requisito": "object",
    "tags": "object"
}

# Lista todos os arquivos no padrão
arquivos = glob.glob("raw/mesaquest/*_mesas_mesaquest.csv")

# Filtra apenas arquivos com data menor que hoje
arquivos_validos = []

for arquivo in arquivos:
    # Extrai a parte da data (AAAAMMDD)
    nome_arquivo = os.path.basename(arquivo)
    data_arquivo = nome_arquivo.split("_")[0]

    if data_arquivo.isdigit() and data_arquivo < data_hoje:
        arquivos_validos.append(arquivo)

if not arquivos_validos:
    raise FileNotFoundError("Nenhum arquivo antigo encontrado.")

# Pega o mais recente entre os anteriores
arquivo_antigo = max(arquivos_validos)

print(f"Arquivo antigo selecionado: {arquivo_antigo}")

# Lê o CSV encontrado
mesas_antigo_df = pd.read_csv(
    arquivo_antigo,
    dtype=schema,
    parse_dates=["start_date", "end_date"],
    encoding="utf-8"
)


# Separar mesas novas
mesas_novas_df = mesas_df[
    ~mesas_df["mesa_id"].isin(mesas_antigo_df["mesa_id"])
]

# Comparar mesas existentes
df_merge = mesas_df.merge(
    mesas_antigo_df[
        ["mesa_id", "vagas_preenchidas", "vagas_total", "lotacao_mesa"]
    ],
    on="mesa_id",
    how="inner",
    suffixes=("_novo", "_antigo")
)

# Filtrar mesas que: NÃO estão lotadas e tiveram mudança em vagas
df_mesas_alteradas = df_merge[
    (df_merge["vagas_preenchidas_novo"] != df_merge["vagas_preenchidas_antigo"]) &
    (df_merge["lotacao_mesa_antigo"] < 1)
]

# Atualizar vagas_preenchidas
df_final = mesas_antigo_df.copy()

df_final = df_final.merge(
    df_mesas_alteradas[["mesa_id", "vagas_preenchidas_novo"]],
    on="mesa_id",
    how="left"
)

df_final["vagas_preenchidas"] = (
    df_final["vagas_preenchidas_novo"]
    .combine_first(df_final["vagas_preenchidas"])
)

df_final.drop(columns=["vagas_preenchidas_novo"], inplace=True)

# Recalcular lotacao_mesa (SOMENTE se < 1)

mask_recalcula = df_final["lotacao_mesa"] < 1

df_final.loc[mask_recalcula, "lotacao_mesa"] = (
    df_final.loc[mask_recalcula, "vagas_preenchidas"]
    .div(df_final.loc[mask_recalcula, "vagas_total"])
    .replace([np.inf, -np.inf], 0)
    .fillna(0)
    .round(2)
)

# Concatenar mesas novas e remover duplicados
df_final = pd.concat(
    [df_final, mesas_novas_df],
    ignore_index=True
)

df_final = df_final.drop_duplicates(
    subset="mesa_id",
    keep="last"
)

# ------------------------------------------------------------------
# 6. GERAR O ARQUIVO ATUALIZADO
# ------------------------------------------------------------------

# Nome do arquivo
nome_arquivo = f"raw/mesaquest/{data_hoje}_mesas_mesaquest.csv"

#### 9. Gerar o csv
df_final.to_csv(
    nome_arquivo,
    index=False,
    encoding="utf-8-sig"
)

# Caminho de uma cópia na raiz do repositório
copia_raiz = "mesas_comissionadas.csv"

# Se já existir na raiz do repositório, remove antes de recriar
if os.path.exists(copia_raiz):
    os.remove(copia_raiz)

# Cria a nova cópia na raiz do repositório
df_final.to_csv(
    copia_raiz,
    index=False,
    encoding="utf-8-sig"
)

# Apaga os arquivos anteriores
n_dias = 7
apagar_arquivos_anteriores(arquivos, data_hoje, n_dias)
