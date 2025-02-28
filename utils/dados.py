import csv
import pandas as pd
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

def carrega_lista_cards(caminho_csv, config):
    """
    Lê um arquivo CSV que tenha no mínimo as colunas:
      - nome
      - colecao
      - numero
    Retorna um DataFrame com essas colunas.
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
    Salva os resultados em CSV, no formato:
      nome;colecao;numero;condicao;quantidade;preco;preco_total;lingua
    """
    if not lista_dicionarios:
        print("[AVISO] Nenhum resultado para salvar.")
        return

    colunas = ["nome", "colecao", "numero", "condicao", "quantidade",
               "preco", "preco_total", "lingua"]
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
                "quantidade": dic.get("quantidade_disponivel", 0),
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
    """
    Salva / atualiza um registro de monitoramento da carta no arquivo CSV
    contendo (nome; colecao; numero; preco_atual; data_atual; preco_inicial; data_inicial).
    """
    colunas = ["nome","colecao","numero","preco_atual","data_atual","preco_inicial","data_inicial"]
    existe = os.path.exists(caminho)
    modo = "a" if existe else "w"

    df_existente = pd.DataFrame()
    if existe:
        df_existente = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig")

    preco_float = float(preco) if preco else 0.0

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

    import csv
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
    print(f"[INFO] Monitoramento salvo para {nome} ({colecao} - {numero}): R$ {preco_float}")

def buscar_oportunidades(df, limite_perc=30):
    """
    Separa registros cujo preço_atual está abaixo de (média - limite_perc%).
    """
    if df.empty or "preco_atual" not in df.columns:
        return pd.DataFrame()

    df2 = df.copy()
    df2["preco_atual"] = pd.to_numeric(df2["preco_atual"], errors="coerce").fillna(0.0)
    media = df2["preco_atual"].mean()
    if pd.isna(media):
        return pd.DataFrame()

    limite_inferior = media * (1 - limite_perc/100)
    oportunidades = df2[df2["preco_atual"] < limite_inferior]
    return oportunidades

def analisar_estoque(df):
    """
    Considera a coluna 'quantidade' do CSV de resultados e gera estatísticas básicas.
    """
    if df.empty or "quantidade" not in df.columns:
        return {}
    df2 = df.copy()
    df2["quantidade"] = pd.to_numeric(df2["quantidade"], errors="coerce").fillna(0)
    total = df2["quantidade"].sum()
    media = df2["quantidade"].mean()
    mini = df2["quantidade"].min()
    maxi = df2["quantidade"].max()
    return {"total": total, "media": media, "min": mini, "max": maxi}

def gerar_pdf_relatorio(titulo, lista_dados, nome_pdf="relatorio.pdf"):
    """
    Gera um PDF simples de texto (usado na aba Análise).
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

def gerar_pdf_relatorio_orcamento(titulo, lista_dados, nome_pdf="orcamento.pdf"):
    """
    Gera um PDF com uma tabela estilizada (Orçamento).
    """
    doc = SimpleDocTemplate(nome_pdf, pagesize=A4)
    story = []

    styles = getSampleStyleSheet()
    style_title = styles["Title"]
    style_normal = styles["Normal"]

    story.append(Paragraph(titulo, style_title))
    story.append(Spacer(1, 12))

    cabecalho = ["Nome", "Coleção", "Número", "Preço Unit (R$)",
                 "Quantidade", "Desconto (%)", "Preço Final (R$)"]
    dados_tabela = []
    dados_tabela.append(cabecalho)

    total_original = 0.0
    total_final = 0.0

    for item in lista_dados:
        nome = str(item.get("nome", ""))
        colecao = str(item.get("colecao", ""))
        numero = str(item.get("numero", ""))
        preco_unit = float(item.get("preco_unit", 0.0))
        quantidade = int(item.get("quantidade", 0))
        desconto_perc = float(item.get("desconto_perc", 0.0))
        preco_final = float(item.get("preco_final", 0.0))

        valor_original = preco_unit * quantidade
        total_original += valor_original
        total_final += preco_final

        linha = [
            nome,
            colecao,
            numero,
            f"{preco_unit:.2f}",
            str(quantidade),
            f"{desconto_perc:.2f}",
            f"{preco_final:.2f}"
        ]
        dados_tabela.append(linha)

    # Linha de total
    dados_tabela.append(["TOTAL", "", "", "", "", "Original:", f"{total_original:.2f}"])
    dados_tabela.append(["", "", "", "", "", "Final:", f"{total_final:.2f}"])

    t = Table(dados_tabela, colWidths=[80,80,60,80,60,70,80])
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkgray),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (3,1), (3,-1), 'RIGHT'),
        ('ALIGN', (4,1), (4,-1), 'RIGHT'),
        ('ALIGN', (5,1), (5,-1), 'RIGHT'),
        ('ALIGN', (6,1), (6,-1), 'RIGHT'),
        ('BACKGROUND', (0, -2), (5, -1), colors.whitesmoke),
        ('SPAN', (0, -2), (4, -2)),
        ('SPAN', (0, -1), (4, -1)),
        ('ALIGN', (0, -2), (0, -1), 'CENTER'),
        ('TEXTCOLOR', (0, -2), (0, -1), colors.red)
    ])
    t.setStyle(t_style)

    story.append(t)
    story.append(Spacer(1, 12))
    doc.build(story)
    print(f"[INFO] PDF '{nome_pdf}' gerado com estilo de tabela para Orçamento.")

def gerar_excel_orcamento(titulo, lista_dados, nome_excel, perc):
    """
    Gera uma planilha Excel (xlsx) com os dados de orçamento.
    """
    import xlsxwriter

    workbook = xlsxwriter.Workbook(nome_excel)
    worksheet = workbook.add_worksheet("Orçamento")

    cabecalho = ["Nome", "Coleção", "Número",
                 "Preço Unit (R$)", "Quantidade", "Desconto (%)", "Preço Final (R$)"]
    row = 0

    worksheet.write(row, 0, titulo)
    row += 2

    for i, cab in enumerate(cabecalho):
        worksheet.write(row, i, cab)
    row += 1

    total_original = 0.0
    total_final = 0.0

    for item in lista_dados:
        nome = str(item.get("nome", ""))
        colecao = str(item.get("colecao", ""))
        numero = str(item.get("numero", ""))
        preco_unit = float(item.get("preco_unit", 0.0))
        quantidade = int(item.get("quantidade", 0))
        desconto_perc = float(item.get("desconto_perc", 0.0))
        preco_final = float(item.get("preco_final", 0.0))

        valor_original = preco_unit * quantidade
        total_original += valor_original
        total_final += preco_final

        worksheet.write(row, 0, nome)
        worksheet.write(row, 1, colecao)
        worksheet.write(row, 2, numero)
        worksheet.write(row, 3, preco_unit)
        worksheet.write(row, 4, quantidade)
        worksheet.write(row, 5, desconto_perc)
        worksheet.write(row, 6, preco_final)

        row += 1

    worksheet.write(row, 0, "TOTAL ORIGINAL")
    worksheet.write(row, 1, total_original)
    row += 1
    worksheet.write(row, 0, "TOTAL FINAL")
    worksheet.write(row, 1, total_final)

    workbook.close()
    print(f"[INFO] Excel '{nome_excel}' gerado com sucesso. Título: {titulo}")
