import csv
import pandas as pd
import os

def carrega_lista_cards(caminho_csv, config):
    """
    Lê um CSV contendo colunas: nome; colecao; numero
    Retorna um DataFrame com as colunas necessárias.
    """
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
    """
    Recebe uma lista de dicionários e salva em CSV.
    Espera colunas: nome, colecao, numero, condicao, quantidade, preco, preco_total, lingua
    """
    if not lista_dicionarios:
        print("[AVISO] Nenhum resultado para salvar.")
        return

    colunas = ["nome","colecao","numero","condicao","quantidade","preco","preco_total","lingua"]
    existe = os.path.exists(caminho_saida)
    modo = "w"

    with open(caminho_saida, modo, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=colunas, delimiter=";")
        if not existe or modo == "w":
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
