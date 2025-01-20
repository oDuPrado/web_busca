import csv
import pandas as pd
import os
from datetime import datetime

def carrega_lista_cards(caminho_csv, config):
    try:
        sep = ";"
        with open(caminho_csv, "r", encoding="utf-8") as f:
            linha = f.readline()
        if "," in linha and ";" not in linha:
            sep = ","

        df = pd.read_csv(caminho_csv, sep=sep, dtype=str, encoding="utf-8")
        df.columns = df.columns.str.strip()
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        colunas_necessarias = ["nome", "colecao", "numero"]
        for col in colunas_necessarias:
            if col not in df.columns:
                print(f"[ERRO] Coluna ausente: {col}")
                return pd.DataFrame()

        df = df[colunas_necessarias].fillna("")
        df = df[df["nome"] != ""]
        df = df[df["colecao"] != ""]
        df = df[df["numero"] != ""]
        df = df.reset_index(drop=True)
        print(f"[INFO] CSV carregado com {df.shape[0]} linhas.")
        return df

    except Exception as e:
        print(f"[ERRO] Falha ao carregar CSV: {e}")
        return pd.DataFrame()

def salvar_resultados_csv(lista_dicionarios, caminho_saida):
    if not lista_dicionarios:
        print("[AVISO] Nenhum resultado para salvar.")
        return

    colunas = ["nome","colecao","numero","condicao","quantidade","preco","preco_total","lingua"]
    existe = os.path.exists(caminho_saida)
    modo = "a" if existe else "w"

    with open(caminho_saida, modo, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=colunas, delimiter=";")
        if modo == "w":
            writer.writeheader()
        for dic in lista_dicionarios:
            linha = {
                "nome": dic.get("nome", ""),
                "colecao": dic.get("colecao", ""),
                "numero": dic.get("numero", ""),
                "condicao": dic.get("condicao", ""),
                "quantidade": dic.get("quantidade", 0),
                "preco": dic.get("preco", 0.0),
                "preco_total": dic.get("preco_total", 0.0),
                "lingua": dic.get("lingua", "")
            }
            writer.writerow(linha)

    print(f"[INFO] CSV salvo em: {caminho_saida}")

def salvar_monitoramento(nome, colecao, numero, preco, data, caminho):
    colunas = ["nome","colecao","numero","preco_atual","data_atual","preco_inicial","data_inicial"]
    existe = os.path.exists(caminho)
    modo = "a" if existe else "w"

    import pandas as pd

    df_existente = pd.DataFrame()
    if os.path.exists(caminho):
        df_existente = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig")

    mask = None
    if not df_existente.empty:
        mask = (
            (df_existente["nome"] == nome) &
            (df_existente["colecao"] == colecao) &
            (df_existente["numero"] == numero)
        )
    else:
        mask = pd.Series([False])

    preco_float = float(preco) if preco else 0.0

    if mask.any():
        idx = df_existente[mask].index[0]
        preco_inicial_str = df_existente.loc[idx, "preco_inicial"]
        preco_inicial_float = float(preco_inicial_str) if preco_inicial_str else 0.0
        if preco_inicial_float == 0:
            df_existente.loc[idx, "preco_inicial"] = str(preco_float)
            df_existente.loc[idx, "data_inicial"] = data
        df_existente.loc[idx, "preco_atual"] = str(preco_float)
        df_existente.loc[idx, "data_atual"] = data
        df_existente.to_csv(caminho, sep=";", index=False, encoding="utf-8-sig")
    else:
        with open(caminho, modo, newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=colunas, delimiter=";")
            if modo == "w":
                writer.writeheader()

            linha = {
                "nome": nome,
                "colecao": colecao,
                "numero": numero,
                "preco_atual": str(preco_float),
                "data_atual": data,
                "preco_inicial": str(preco_float),
                "data_inicial": data
            }
            writer.writerow(linha)

    print(f"[INFO] Monitoramento salvo/atualizado para {nome} ({colecao} - {numero}): R$ {preco_float} em {data}")

def carrega_historico_raspagem(path):
    """
    Lê o arquivo de resultados e retorna um DataFrame para plotar gráficos.
    """
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    return df
