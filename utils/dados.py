import csv
import pandas as pd
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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

def limpar_csv(caminho):
    if os.path.exists(caminho):
        os.remove(caminho)
        print(f"[INFO] CSV {caminho} foi removido.")
    else:
        print(f"[INFO] CSV {caminho} não existe para ser removido.")

def salvar_monitoramento(nome, colecao, numero, preco, data, caminho):
    colunas = ["nome","colecao","numero","preco_atual","data_atual","preco_inicial","data_inicial"]
    existe = os.path.exists(caminho)
    modo = "a" if existe else "w"

    import pandas as pd
    preco_float = float(preco) if preco else 0.0

    df_existente = pd.DataFrame()
    if existe:
        df_existente = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig")

    if not df_existente.empty:
        mask = (
            (df_existente["nome"] == nome) &
            (df_existente["colecao"] == colecao) &
            (df_existente["numero"] == numero)
        )
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
            print(f"[INFO] Monitoramento atualizado para {nome} ({colecao} - {numero}): R$ {preco_float}")
            return
    # Caso contrário, adiciona linha
    with open(caminho, modo, newline="", encoding="utf-8-sig") as f:
        import csv
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
    print(f"[INFO] Monitoramento salvo para {nome} ({colecao} - {numero}): R$ {preco_float}")

def buscar_oportunidades(df, limite_perc=30):
    """
    Identifica cartas com preço_atual muito abaixo da média.
    Recebe um DataFrame com colunas: [nome, colecao, numero, preco_atual, preco_inicial]
    Retorna df de 'oportunidades'
    Ex: limite_perc=30 => definimos como 'abaixo do normal' se preco_atual < media*(1 - 0.3)
    """
    if df.empty or "preco_atual" not in df.columns:
        return pd.DataFrame()

    df2 = df.copy()
    df2["preco_atual"] = df2["preco_atual"].astype(float)
    media = df2["preco_atual"].mean()
    if pd.isna(media):
        return pd.DataFrame()

    limite_inferior = media * (1 - limite_perc/100)
    # Pegamos apenas as NM?
    # Se quisesse filtrar condicao, precisaríamos ter a coluna
    oportunidades = df2[df2["preco_atual"] < limite_inferior]
    return oportunidades

def analisar_estoque(df):
    """
    Exemplo de análise de estoque:
    Recebe DataFrame de raspagem com colunas [quantidade].
    Retorna dicionário com total, média, min, max.
    """
    if df.empty or "quantidade" not in df.columns:
        return {}
    df2 = df.copy()
    df2["quantidade"] = df2["quantidade"].astype(float)
    total = df2["quantidade"].sum()
    media = df2["quantidade"].mean()
    mini = df2["quantidade"].min()
    maxi = df2["quantidade"].max()
    return {"total": total, "media": media, "min": mini, "max": maxi}

def gerar_pdf_relatorio(titulo, lista_dados, nome_pdf="relatorio.pdf"):
    """
    Gera um PDF simples usando reportlab, contendo os dados de 'lista_dados'.
    - titulo: Título do relatório
    - lista_dados: lista de dicionários com colunas específicas
    - nome_pdf: nome do arquivo pdf a ser criado
    Exemplo de colunas: nome, colecao, numero, preco, ...
    """
    c = canvas.Canvas(nome_pdf, pagesize=A4)
    largura, altura = A4
    y = altura - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, titulo)
    y -= 30
    c.setFont("Helvetica", 10)

    colunas = []
    if lista_dados:
        colunas = list(lista_dados[0].keys())

    # Cabeçalho
    c.drawString(50, y, " | ".join(colunas))
    y -= 20

    for item in lista_dados:
        linha = []
        for col in colunas:
            valor = str(item.get(col, ""))
            linha.append(valor)
        text = " | ".join(linha)
        c.drawString(50, y, text)
        y -= 15
        if y < 50:
            c.showPage()
            y = altura - 50
            c.setFont("Helvetica", 10)

    c.showPage()
    c.save()
    print(f"[INFO] PDF '{nome_pdf}' gerado com sucesso.")

