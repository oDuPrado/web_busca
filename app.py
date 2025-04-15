# --------------------------------------------------------------------------------
# Crhome driver 
# --------------------------------------------------------------------------------

import os
import platform
import zipfile
import requests
import shutil
import sys 

def get_chromedriver_path():
    """Retorna o caminho correto do ChromeDriver dentro da pasta do executável."""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))  # Suporte ao PyInstaller
    return os.path.join(base_path, "chromedriver.exe")

def get_latest_chromedriver_version():
    """Obtém a versão mais recente do ChromeDriver disponível."""
    url = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
    response = requests.get(url)
    if response.status_code != 200:
        print("[ERRO] Falha ao obter a versão mais recente do ChromeDriver.")
        return None
    data = response.json()
    return data.get("channels", {}).get("Stable", {}).get("version", None)

def download_chromedriver():
    """Baixa e extrai a versão correta do ChromeDriver automaticamente e move para o diretório correto."""
    latest_version = get_latest_chromedriver_version()
    if not latest_version:
        print("[ERRO] Não foi possível obter a versão mais recente do ChromeDriver.")
        return None

    system_os = platform.system().lower()
    download_urls = {
        "windows": f"https://storage.googleapis.com/chrome-for-testing-public/{latest_version}/win64/chromedriver-win64.zip",
        "linux": f"https://storage.googleapis.com/chrome-for-testing-public/{latest_version}/linux64/chromedriver-linux64.zip",
        "darwin": f"https://storage.googleapis.com/chrome-for-testing-public/{latest_version}/mac-x64/chromedriver-mac-x64.zip"
    }

    if system_os not in download_urls:
        print("[ERRO] Sistema operacional não suportado!")
        return None

    url = download_urls[system_os]
    zip_path = os.path.join(os.getcwd(), "chromedriver.zip")
    extract_path = os.path.join(os.getcwd(), "chromedriver_temp")

    print(f"Baixando ChromeDriver versão {latest_version} de {url}...")
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        print(f"[ERRO] Falha no download: {response.status_code}")
        return None

    with open(zip_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    # Verifica se o arquivo baixado é um ZIP válido
    if not zipfile.is_zipfile(zip_path):
        print("[ERRO] O arquivo baixado não é um ZIP válido. Possível erro na URL.")
        os.remove(zip_path)
        return None

    # Extrai o conteúdo
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_path)

    os.remove(zip_path)  # Remove o ZIP baixado

    # Encontra o caminho correto dentro da pasta extraída
    chromedriver_filename = "chromedriver.exe" if system_os == "windows" else "chromedriver"
    extracted_driver_path = os.path.join(extract_path, "chromedriver-win64", chromedriver_filename) if system_os == "windows" else os.path.join(extract_path, chromedriver_filename)
    final_path = os.path.join(os.getcwd(), chromedriver_filename)  # Caminho onde queremos mover o ChromeDriver

    if not os.path.exists(extracted_driver_path):
        print("[ERRO] ChromeDriver não encontrado após extração.")
        return None

    # Move o ChromeDriver para o diretório raiz do projeto
    shutil.move(extracted_driver_path, final_path)
    shutil.rmtree(extract_path)  # Remove a pasta temporária

    # Torna executável (necessário para Linux/macOS)
    if system_os in ["linux", "darwin"]:
        os.chmod(final_path, 0o755)

    print(f"ChromeDriver pronto para uso em: {final_path}")
    return final_path

# Verifica se o ChromeDriver já está no local esperado
chromedriver_path = get_chromedriver_path()
if not os.path.exists(chromedriver_path):
    chromedriver_path = download_chromedriver()

if not chromedriver_path or not os.path.exists(chromedriver_path):
    print("[ERRO] Falha ao obter o ChromeDriver corretamente.")
else:
    print(f"[INFO] ChromeDriver pronto para uso: {chromedriver_path}")

# --------------------------------------------------------------------------------
# IMPORTS
# --------------------------------------------------------------------------------

import sys
import os
import time
import random
import requests
from datetime import datetime
import threading
import base64
from io import BytesIO
from PyQt5.QtWidgets import QStyle

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QTableWidget, QTableWidgetItem, QProgressBar,
    QFileDialog, QTextEdit, QSpinBox, QSlider, QAbstractItemView,
    QScrollArea, QGridLayout, QFrame, QToolTip, QToolButton
)
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal, QObject, QSize, QPropertyAnimation,
    QPoint
)
from PyQt5.QtGui import QPixmap, QIcon
from selenium.common.exceptions import NoAlertPresentException

# --------------------------------------------------------------------------------
# CONFIG (simples, você pode colocar em config.py separado)
# --------------------------------------------------------------------------------
class Config:
    TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    WEBSITE_1 = "https://www.ligapokemon.com.br/"
    TIMEOUT_BUSCA_PRINCIPAL = 10
    TIMEOUT_EXIBIR_MAIS = 8
    TIMEOUT_SELECIONA_CARD = 8
    TIMEOUT_BOTAO_CARRINHO = 4
    ESPERA_BOTAO_COMPRAR = 1
    N_MAX_TENTATIVAS_PRECO = 16
    N_MAX_TENTATIVAS_COLECAO = 3
    TEMPO_ESPERA = 4
    DEBUG = False

    SAIDA_CSV = "resultados_final.csv"
    MONITOR_CSV = "monitor_registros.csv"

    MONITOR_INTERVALO_BASE = 60
    MONITOR_VARIACAO = 30
    PROGRESS_MAX = 100

    # Pasta de saída (pode ser configurável pelo usuário)
    OUTPUT_FOLDER = os.getcwd()

config = Config()

# --------------------------------------------------------------------------------
# DADOS (funções de csv, pdf, excel)
# --------------------------------------------------------------------------------
import csv
import pandas as pd
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import xlsxwriter

def carrega_lista_cards(caminho_csv, config_obj):
    try:
        separador = ";"
        with open(caminho_csv, "r", encoding="utf-8") as file_check:
            primeira_linha = file_check.readline()
        if "," in primeira_linha and ";" not in primeira_linha:
            separador = ","

        df = pd.read_csv(caminho_csv, sep=separador, dtype=str, encoding="utf-8")
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
    existe_arquivo = os.path.exists(caminho_saida)
    modo = "a" if existe_arquivo else "w"

    with open(caminho_saida, modo, newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=colunas, delimiter=";")
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

def limpar_csv(caminho_csv):
    if os.path.exists(caminho_csv):
        os.remove(caminho_csv)
        print(f"[INFO] CSV {caminho_csv} foi removido.")
    else:
        print(f"[INFO] CSV {caminho_csv} não existe para ser removido.")

def salvar_monitoramento(nome, colecao, numero, preco, data, caminho):
    colunas = ["nome","colecao","numero","preco_atual","data_atual","preco_inicial","data_inicial"]
    existe_arquivo = os.path.exists(caminho)
    modo = "a" if existe_arquivo else "w"

    df_existente = pd.DataFrame()
    if existe_arquivo:
        df_existente = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig")

    preco_float = float(preco) if preco else 0.0
    if not df_existente.empty:
        mascara = (
            (df_existente["nome"] == nome) &
            (df_existente["colecao"] == colecao) &
            (df_existente["numero"] == numero)
        )
        if mascara.any():
            idx = df_existente[mascara].index[0]
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

    with open(caminho, modo, newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=colunas, delimiter=";")
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
    if df.empty or "preco_atual" not in df.columns:
        return pd.DataFrame()

    df_copia = df.copy()
    df_copia["preco_atual"] = pd.to_numeric(df_copia["preco_atual"], errors="coerce").fillna(0.0)
    media = df_copia["preco_atual"].mean()
    if pd.isna(media):
        return pd.DataFrame()

    limite_inferior = media * (1 - limite_perc/100)
    oportunidades = df_copia[df_copia["preco_atual"] < limite_inferior]
    return oportunidades

def analisar_estoque(df):
    if df.empty or "quantidade" not in df.columns:
        return {}
    df_copia = df.copy()
    df_copia["quantidade"] = pd.to_numeric(df_copia["quantidade"], errors="coerce").fillna(0)
    total = df_copia["quantidade"].sum()
    media = df_copia["quantidade"].mean()
    minimo = df_copia["quantidade"].min()
    maximo = df_copia["quantidade"].max()
    return {"total": total, "media": media, "min": minimo, "max": maximo}

def gerar_pdf_relatorio(titulo, lista_dados, nome_pdf="relatorio.pdf"):
    can = canvas.Canvas(nome_pdf, pagesize=A4)
    largura_pagina, altura_pagina = A4
    y = altura_pagina - 50

    can.setFont("Helvetica-Bold", 14)
    can.drawString(50, y, titulo)
    y -= 30
    can.setFont("Helvetica", 10)

    colunas = []
    if lista_dados:
        colunas = list(lista_dados[0].keys())

    can.drawString(50, y, " | ".join(colunas))
    y -= 20

    for item in lista_dados:
        linha = []
        for col in colunas:
            valor = str(item.get(col, ""))
            linha.append(valor)
        texto = " | ".join(linha)
        can.drawString(50, y, texto)
        y -= 15
        if y < 50:
            can.showPage()
            y = altura_pagina - 50
            can.setFont("Helvetica", 10)

    can.showPage()
    can.save()
    print(f"[INFO] PDF '{nome_pdf}' gerado com sucesso.")

def gerar_pdf_relatorio_orcamento(titulo, lista_dados, nome_pdf="orcamento.pdf", global_discount=50):
    doc = SimpleDocTemplate(nome_pdf, pagesize=A4)
    story = []

    styles = getSampleStyleSheet()
    style_title = styles["Title"]
    style_normal = styles["Normal"]

    story.append(Paragraph(titulo, style_title))
    story.append(Spacer(1, 12))

    cabecalho = ["Nome", "Coleção", "Número", "Preço Unit (R$)", "Quantidade", "Compra (%)", "Preço Final (R$)"]
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
        
        desconto_raw = item.get("desconto_perc")
        if not desconto_raw or float(desconto_raw) == 0:
            desconto_perc = float(global_discount)
        else:
            desconto_perc = float(desconto_raw)
        
        preco_final = float(item.get("preco_final", 0.0))

        valor_original = preco_unit * quantidade
        total_original += valor_original
        total_final += preco_final

        linha_tabela = [
            nome,
            colecao,
            numero,
            f"{preco_unit:.2f}",
            str(quantidade),
            f"{desconto_perc:.2f}",
            f"{preco_final:.2f}"
        ]
        dados_tabela.append(linha_tabela)

    dados_tabela.append([
        "TOTAL", "", "", "", "", "Original:", f"{total_original:.2f}"
    ])
    dados_tabela.append([
        "", "", "", "", "", "Final:", f"{total_final:.2f}"
    ])

    tabela = Table(dados_tabela, colWidths=[80, 80, 60, 80, 60, 70, 80])
    tabela_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgray),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
        ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
        ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
        ('BACKGROUND', (0, -2), (5, -1), colors.whitesmoke),
        ('SPAN', (0, -2), (4, -2)),
        ('SPAN', (0, -1), (4, -1)),
        ('ALIGN', (0, -2), (0, -1), 'CENTER'),
        ('TEXTCOLOR', (0, -2), (0, -1), colors.red)
    ])
    tabela.setStyle(tabela_style)

    story.append(tabela)
    story.append(Spacer(1, 12))
    doc.build(story)
    print(f"[INFO] PDF '{nome_pdf}' gerado com estilo de tabela para Orçamento.")

def gerar_excel_orcamento(titulo, lista_dados, nome_excel, _percentual_desconto):
    workbook = xlsxwriter.Workbook(nome_excel)
    worksheet = workbook.add_worksheet("Orçamento")

    cabecalho = ["Nome", "Coleção", "Número", "Preço Unit (R$)", "Quantidade", "Desconto (%)", "Preço Final (R$)"]
    linha_atual = 0

    worksheet.write(linha_atual, 0, titulo)
    linha_atual += 2

    for index_col, texto_cab in enumerate(cabecalho):
        worksheet.write(linha_atual, index_col, texto_cab)
    linha_atual += 1

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

        worksheet.write(linha_atual, 0, nome)
        worksheet.write(linha_atual, 1, colecao)
        worksheet.write(linha_atual, 2, numero)
        worksheet.write(linha_atual, 3, preco_unit)
        worksheet.write(linha_atual, 4, quantidade)
        worksheet.write(linha_atual, 5, desconto_perc)
        worksheet.write(linha_atual, 6, preco_final)

        linha_atual += 1

    worksheet.write(linha_atual, 0, "TOTAL ORIGINAL")
    worksheet.write(linha_atual, 1, total_original)
    linha_atual += 1
    worksheet.write(linha_atual, 0, "TOTAL FINAL")
    worksheet.write(linha_atual, 1, total_final)

    workbook.close()
    print(f"[INFO] Excel '{nome_excel}' gerado com sucesso. Título: {titulo}")

# --------------------------------------------------------------------------------
# SCRAPER (para raspagem local)
# --------------------------------------------------------------------------------
import atexit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException
)
from selenium.webdriver.support.ui import WebDriverWait

class LigaPokemonScraper:
    drivers_abertos = []

    @classmethod
    def fechar_todos_os_drivers(cls):
        for driver in cls.drivers_abertos[:]:
            try:
                driver.quit()
                print("[INFO] Driver encerrado com sucesso.")
            except Exception as e:
                print(f"[ERRO] Falha ao encerrar driver: {e}")
            finally:
                cls.drivers_abertos.remove(driver)

    atexit.register(lambda: LigaPokemonScraper.fechar_todos_os_drivers())

    def __init__(self, url_base, debug, tesseract_cmd, tempo_espera):
        self.url_base = url_base
        self.debug = debug
        self.tempo_espera = tempo_espera
        self.driver = None
        self.inicializa_driver()

    def inicializa_driver(self):
        opcoes_chrome = Options()
        opcoes_chrome.add_argument("--disable-notifications")
        opcoes_chrome.add_argument("--disable-popup-blocking")

        if not self.debug:
            opcoes_chrome.add_argument("--headless")

        self.driver = webdriver.Chrome(options=opcoes_chrome)
        self.__class__.drivers_abertos.append(self.driver)
        self.espera_explicita = WebDriverWait(self.driver, timeout=15, poll_frequency=0.5)
        print("[INFO] Navegador Chrome inicializado com sucesso")

    def fechar_driver(self):
        try:
            self.driver.quit()
            print("[INFO] Driver fechado.")
        except:
            pass

    def fecha_banner_cookies(self):
        try:
            banner = self.driver.find_element(By.ID, "lgpd-cookie")
            botao_fechar = banner.find_element(By.TAG_NAME, "button")
            botao_fechar.click()
            print("[INFO] Banner de cookies fechado.")
            time.sleep(1)
        except NoSuchElementException:
            pass
        except Exception as e:
            print(f"[AVISO] Erro ao fechar banner de cookies: {e}")

    def monta_url_carta(self, nome, colecao, numero):
        nome_url = nome.replace(" ", "%20")
        return f"{self.url_base}?view=cards/card&card={nome_url}%20({numero})&ed={colecao}&num={numero}"

    def busca_carta_completa(self, nome, colecao, numero):
        url = self.monta_url_carta(nome, colecao, numero)
        self.driver.get(url)
        time.sleep(self.tempo_espera)
        self.fecha_banner_cookies()

        resultados = []
        try:
            marketplace = self.driver.find_element(By.ID, "marketplace-stores")
            stores = marketplace.find_elements(By.CLASS_NAME, "store")
        except NoSuchElementException:
            print("[AVISO] Sem marketplace-stores. Nenhum vendedor encontrado.")
            return resultados

        for store in stores:
            lingua, condicao = self.extrai_lingua_e_condicao(store)
            if "NM" in condicao.upper():
                botao_comprar = self.localiza_botao_comprar_nm(store)
                if botao_comprar:
                    self.fecha_banner_cookies()
                    botao_comprar.click()
                    time.sleep(1)
                    self.abre_modal_carrinho()
                    item_carrinho = self.localiza_item_no_carrinho(nome, numero)
                    if item_carrinho:
                        dados_item = self.extrai_dados_item_carrinho(item_carrinho)
                        dados_item["nome"] = nome
                        dados_item["colecao"] = colecao
                        dados_item["numero"] = numero
                        dados_item["lingua"] = lingua
                        dados_item["condicao"] = condicao
                        resultados.append(dados_item)
                        self.remove_item_carrinho(item_carrinho)
                        return resultados
        return resultados

    def extrai_lingua_e_condicao(self, store):
        try:
            infos = store.find_element(By.CLASS_NAME, "infos-quality-and-language.desktop-only")
            imagens = infos.find_elements(By.TAG_NAME, "img")
            lingua = ""
            for img in imagens:
                titulo = img.get_attribute("title") or ""
                if titulo:
                    lingua = titulo

            qualidades = infos.find_elements(By.CLASS_NAME, "quality")
            condicao = ""
            for c in qualidades:
                titulo_q = c.get_attribute("title") or ""
                if "NM" in titulo_q.upper():
                    condicao = titulo_q
                    break
            return (lingua, condicao)
        except NoSuchElementException:
            return ("","")

    def localiza_botao_comprar_nm(self, store):
        try:
            botao = store.find_element(By.CSS_SELECTOR, "div.btn-green.cursor-pointer")
            return botao
        except NoSuchElementException:
            return None

    def abre_modal_carrinho(self):
        try:
            icone_carrinho = self.driver.find_element(By.CSS_SELECTOR, "div.cart-icon-container.icon-container")
            icone_carrinho.click()
            time.sleep(1)
            meu_carrinho_btn = self.driver.find_element(By.CSS_SELECTOR, "a.btn-view-cart")
            meu_carrinho_btn.click()
            time.sleep(self.tempo_espera)
        except NoSuchElementException:
            pass

    def localiza_item_no_carrinho(self, nome, numero):
        try:
            itens_container = self.driver.find_element(By.CSS_SELECTOR, "div.itens")
            rows = itens_container.find_elements(By.CSS_SELECTOR, "div.row")
            for row in rows:
                try:
                    titulo_elem = row.find_element(By.CSS_SELECTOR, "p.cardtitle a")
                    texto_titulo = titulo_elem.text.strip()
                    if nome in texto_titulo and f"({numero})" in texto_titulo:
                        return row
                except NoSuchElementException:
                    pass
            return None
        except NoSuchElementException:
            return None

    def extrai_dados_item_carrinho(self, row):
        dados = {}
        try:
            estoque_elem = row.find_element(By.CSS_SELECTOR, "div.item-estoque")
            texto_est = estoque_elem.text.strip()
            qtd = 0
            for parte in texto_est.split():
                if parte.isdigit():
                    qtd = int(parte)
                    break
            dados["quantidade"] = qtd
        except NoSuchElementException:
            dados["quantidade"] = 0

        try:
            total_elem = row.find_element(By.CSS_SELECTOR, "div.preco-total.item-total")
            preco_total = self.converte_preco_para_float(total_elem.text.strip())
            dados["preco_total"] = preco_total
            dados["preco"] = preco_total
        except NoSuchElementException:
            dados["preco_total"] = 0.0
            dados["preco"] = 0.0

        return dados

    def remove_item_carrinho(self, row):
        try:
            botao_remover = row.find_element(By.CSS_SELECTOR, "div.btn-circle.remove.delete.item-delete")
            botao_remover.click()
            time.sleep(1)  # Aguarda um curto período para o alerta aparecer

            # Tenta lidar com o alerta JavaScript da página
            try:
                alert = self.driver.switch_to.alert  # Muda o foco para o alerta
                alert.accept()  # Confirma (clica em "OK")
                time.sleep(1)  # Dá um tempo para a página atualizar
                print("[INFO] Alerta de remoção fechado com sucesso.")
            except NoAlertPresentException:
                print("[INFO] Nenhum alerta encontrado após remover item do carrinho.")

        except NoSuchElementException:
            print("[ERRO] Botão de remover item do carrinho não encontrado.")
            
    def limpar_carrinho_completo(self):
        try:
            self.abre_modal_carrinho()
            itens_container = self.driver.find_element(By.CSS_SELECTOR, "div.itens")
            rows = itens_container.find_elements(By.CSS_SELECTOR, "div.row")

            for row in rows:
                try:
                    botao_remover = row.find_element(By.CSS_SELECTOR, "div.btn-circle.remove.delete.item-delete")
                    botao_remover.click()
                    time.sleep(1)
                    try:
                        alert = self.driver.switch_to.alert
                        alert.accept()
                        time.sleep(1)
                    except NoAlertPresentException:
                        pass
                except NoSuchElementException:
                    continue
            print("[INFO] Carrinho limpo com sucesso.")
        except Exception as e:
            print(f"[ERRO] Falha ao limpar carrinho: {e}")


    def converte_preco_para_float(self, texto_preco):
        valor = texto_preco.replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            return float(valor)
        except:
            return 0.0

# --------------------------------------------------------------------------------
# LOG EMITTER (para threads)
# --------------------------------------------------------------------------------
class LogEmitter(QObject):
    new_log = pyqtSignal(str)

# --------------------------------------------------------------------------------
# APLICAÇÃO PRINCIPAL
# --------------------------------------------------------------------------------
class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ho Hub - Scrapper")
        self.setGeometry(50, 50, 1300, 800)

        # Controle de dados
        self.df_cards = pd.DataFrame()
        self.df_monitor = pd.DataFrame()
        self.df_raspados = pd.DataFrame()

        # Variáveis de monitoramento
        self.monitor_running = False
        self.monitor_paused = False
        self.monitor_check_count = 0
        self.monitor_thread = None

        # Emitter para logs (evita problemas de thread)
        self.log_emitter = LogEmitter()
        self.log_emitter.new_log.connect(self.append_log)

        # Guarda se estamos em modo escuro ou claro
        self.modo_escuro = True

        # ---------- CRIAÇÃO DAS ABAS ----------
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Criamos as abas na ordem solicitada:
        # 1) Cartas
        # 2) Scrapper
        # 3) Análise
        # 4) Orçamento

        self.tab_cartas = QWidget()
        self.tabs.addTab(self.tab_cartas, "Cartas")

        self.tab_rasp_monitor = QWidget()
        self.tabs.addTab(self.tab_rasp_monitor, "Scrapper")

        self.tab_analise = QWidget()
        self.tabs.addTab(self.tab_analise, "Análise")

        self.tab_orcamento = QWidget()
        self.tabs.addTab(self.tab_orcamento, "Orçamento")

        # Constrói cada aba (layouts e widgets)
        self.setup_tab_cartas()
        self.setup_tab_rasp_monitor()
        self.setup_tab_analise()
        self.setup_tab_orcamento()

        # ---------- CRIAR BOTÃO DE TOGGLE DO TEMA ----------
        self.toggle_tema_button = QToolButton(self)
        self.toggle_tema_button.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
        self.toggle_tema_button.setToolTip("Alternar entre Modo Claro e Modo Escuro")
        self.toggle_tema_button.clicked.connect(self.on_toggle_tema)

        # Adicionando o botão de toggle tema ao layout superior
        # Você pode posicioná-lo onde quiser. Aqui, vamos colocar num layout horizontal no topo da janela.
        topo_layout = QHBoxLayout()
        topo_layout.addWidget(self.toggle_tema_button)
        topo_layout.addStretch()

        # Cria um widget container para o topo e atribui ao layout
        topo_widget = QWidget()
        topo_widget.setLayout(topo_layout)

        # Precisamos inserir esse topo_widget acima do self.tabs
        layout_geral = QVBoxLayout()
        layout_geral.addWidget(topo_widget)
        layout_geral.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(layout_geral)
        self.setCentralWidget(container)

        # Timer para o cronômetro de monitoramento
        self.timer = QTimer()
        self.timer.timeout.connect(self.monitor_cronometro_tick)
        self.timer.start(1000)

        # Ajusta a fonte inicial maior
        self.aplicar_estilos_iniciais()

    # --------------------------------------------------------------------------------
    # ABA 1 - CARTAS (reordenada como solicitada)
    # --------------------------------------------------------------------------------
    def setup_tab_cartas(self):
        layout = QVBoxLayout(self.tab_cartas)

        label_explicacao = QLabel(
            "Nesta aba, você pode pesquisar cartas.\n"
            'Digite algo como "SFA 78 " ou "nome da carta". Os resultados aparecerão abaixo.'
        )
        layout.addWidget(label_explicacao)

        # Botão para escolher a pasta de saída
        row_output_path = QHBoxLayout()
        label_path = QLabel("Pasta de Saída:")
        self.input_output_folder = QLineEdit(config.OUTPUT_FOLDER)
        botao_browse_folder = QPushButton("Selecionar Pasta")
        botao_browse_folder.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        botao_browse_folder.setToolTip("Selecione a pasta onde serão salvos arquivos gerados")
        botao_browse_folder.clicked.connect(self.on_browse_output_folder)

        row_output_path.addWidget(label_path)
        row_output_path.addWidget(self.input_output_folder)
        row_output_path.addWidget(botao_browse_folder)
        layout.addLayout(row_output_path)

        # Campo de busca
        row_search = QHBoxLayout()
        label_search = QLabel("Buscar Carta:")
        self.input_search_card = QLineEdit()
        botao_search_card = QPushButton("Pesquisar")
        botao_search_card.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        botao_search_card.setToolTip("Clique para pesquisar as cartas de pokemon")
        botao_search_card.clicked.connect(self.on_search_cards_api)

        row_search.addWidget(label_search)
        row_search.addWidget(self.input_search_card)
        row_search.addWidget(botao_search_card)
        layout.addLayout(row_search)

        # ScrollArea + Grid para mosaico
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid_mosaico = QGridLayout(self.scroll_content)
        self.scroll_content.setLayout(self.grid_mosaico)
        self.scroll_area.setWidget(self.scroll_content)

        layout.addWidget(self.scroll_area)

        # Lista de cartas selecionadas
        self.selected_cards = []
        label_selecionadas = QLabel("Cartas Selecionadas para Scrapper:")
        layout.addWidget(label_selecionadas)

        self.list_selected_cards = QListWidget()
        layout.addWidget(self.list_selected_cards)

        botao_criar_scrapper = QPushButton("Criar arquivo Scrapper ")
        botao_criar_scrapper.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        botao_criar_scrapper.setToolTip("Gera um arquivo para Scrapper, usando as cartas selecionadas")
        botao_criar_scrapper.clicked.connect(self.on_criar_scrapper_csv)
        layout.addWidget(botao_criar_scrapper)

        layout.addStretch()

    # --------------------------------------------------------------------------------
    # ABA 2 - RASPAGEM & MONITORAMENTO
    # --------------------------------------------------------------------------------
    def setup_tab_rasp_monitor(self):
        layout = QVBoxLayout(self.tab_rasp_monitor)

        # Carregar CSV de Cartas
        row_cards = QHBoxLayout()
        label_cards = QLabel("Arquivo Scrapper:")
        self.input_file_cards = QLineEdit()
        botao_file_cards = QPushButton("Localizar arquivo")
        botao_file_cards.setIcon(self.style().standardIcon(QStyle.SP_FileDialogStart))
        botao_file_cards.setToolTip("Selecione o arquivo CSV contendo as cartas que deseja raspar")
        botao_file_cards.clicked.connect(self.on_browse_cards)

        self.list_cards = QListWidget()
        self.list_cards.setToolTip("Lista de cartas carregadas do CSV")

        self.btn_buscar = QPushButton("Buscar Preços")
        self.btn_buscar.setEnabled(False)
        self.btn_buscar.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.btn_buscar.setToolTip("Inicia a raspagem de preços para as cartas carregadas")
        self.btn_buscar.clicked.connect(self.on_buscar_precos)

        btn_limpar_hist = QPushButton("Limpar Histórico")
        btn_limpar_hist.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        btn_limpar_hist.setToolTip("Limpa o histórico de raspagem (CSV de resultados) e tabela de resultados")
        btn_limpar_hist.clicked.connect(self.on_limpar_historico)

        row_cards.addWidget(label_cards)
        row_cards.addWidget(self.input_file_cards)
        row_cards.addWidget(botao_file_cards)

        self.table_results = QTableWidget()
        self.table_results.setColumnCount(8)
        self.table_results.setHorizontalHeaderLabels([
            "Nome", "Coleção", "Número", "Cond", "Qtde",
            "Preço", "Total", "Língua"
        ])
        self.table_results.setToolTip("Resultados da raspagem serão exibidos aqui")

        row_progress = QHBoxLayout()
        lbl_progress = QLabel("Progresso:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(config.PROGRESS_MAX)
        self.progress_bar.setToolTip("Progresso da raspagem ou monitoramento")

        lbl_cron = QLabel("Tempo p/ próxima checagem:")
        self.lbl_cron_val = QLabel("00:00")

        lbl_checks = QLabel("Total de checagens:")
        self.lbl_check_count = QLabel("0")

        row_progress.addWidget(lbl_progress)
        row_progress.addWidget(self.progress_bar)
        row_progress.addSpacing(20)
        row_progress.addWidget(lbl_cron)
        row_progress.addWidget(self.lbl_cron_val)
        row_progress.addSpacing(20)
        row_progress.addWidget(lbl_checks)
        row_progress.addWidget(self.lbl_check_count)
        row_progress.addStretch()

        row_monitor = QHBoxLayout()
        label_monitor = QLabel("Arquivo Monitor:")
        self.input_file_monitor = QLineEdit()
        botao_file_monitor = QPushButton("Localizar Arquivo")
        botao_file_monitor.setIcon(self.style().standardIcon(QStyle.SP_FileDialogStart))
        botao_file_monitor.setToolTip("Selecione o arquivo contendo as cartas que deseja monitorar")
        botao_file_monitor.clicked.connect(self.on_browse_monitor)

        self.list_monitor = QListWidget()
        self.list_monitor.setToolTip("Lista de cartas em monitoramento")

        self.btn_monitorar = QPushButton("Iniciar Monitoramento")
        self.btn_monitorar.setEnabled(False)
        self.btn_monitorar.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_monitorar.setToolTip("Inicia o monitoramento periódico das cartas")
        self.btn_monitorar.clicked.connect(self.on_iniciar_monitoramento)

        self.btn_pausar = QPushButton("Pausar")
        self.btn_pausar.setEnabled(False)
        self.btn_pausar.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.btn_pausar.setToolTip("Pausa ou retoma o monitoramento")
        self.btn_pausar.clicked.connect(self.on_pausar_monitoramento)

        row_monitor.addWidget(label_monitor)
        row_monitor.addWidget(self.input_file_monitor)
        row_monitor.addWidget(botao_file_monitor)

        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFixedHeight(120)
        self.txt_logs.setToolTip("Logs e mensagens informativas são mostrados aqui")

        # Layout final da aba
        layout.addLayout(row_cards)
        layout.addWidget(self.list_cards)

        row_buscar = QHBoxLayout()
        row_buscar.addWidget(self.btn_buscar)
        row_buscar.addWidget(btn_limpar_hist)
        row_buscar.addStretch()
        layout.addLayout(row_buscar)

        layout.addWidget(self.table_results)
        layout.addLayout(row_progress)

        layout.addLayout(row_monitor)
        layout.addWidget(self.list_monitor)

        row_mon_btns = QHBoxLayout()
        row_mon_btns.addWidget(self.btn_monitorar)
        row_mon_btns.addWidget(self.btn_pausar)
        row_mon_btns.addStretch()
        layout.addLayout(row_mon_btns)

        layout.addWidget(self.txt_logs)

    # --------------------------------------------------------------------------------
    # ABA 3 - ANÁLISE
    # --------------------------------------------------------------------------------
    def setup_tab_analise(self):
        layout = QVBoxLayout(self.tab_analise)

        self.table_analise = QTableWidget()
        self.table_analise.setColumnCount(5)
        self.table_analise.setHorizontalHeaderLabels(["Nome","Coleção","Número","Preço","Outros?"])
        self.table_analise.setToolTip("Resultados de análise, oportunidades, etc")

        row_botoes = QHBoxLayout()
        btn_grafico = QPushButton("Gerar Gráfico Tendência")
        btn_grafico.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        btn_grafico.setToolTip("Gera um gráfico simples mostrando a tendência de preços")
        btn_grafico.clicked.connect(self.on_analise_grafico)

        btn_estoque = QPushButton("Analisar Estoque")
        btn_estoque.setIcon(self.style().standardIcon(QStyle.SP_DriveHDIcon))
        btn_estoque.setToolTip("Analisa informações de estoque (quantidades)")
        btn_estoque.clicked.connect(self.on_analise_estoque)

        btn_oport = QPushButton("Buscar Oportunidades")
        btn_oport.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        btn_oport.setToolTip("Verifica oportunidades abaixo da média de preço")
        btn_oport.clicked.connect(self.on_analise_oportunidades)

        btn_pdf = QPushButton("Gerar Relatório PDF")
        btn_pdf.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        btn_pdf.setToolTip("Gera um PDF de relatório contendo os dados de buscas/monitor")
        btn_pdf.clicked.connect(self.on_analise_pdf)

        row_botoes.addWidget(btn_grafico)
        row_botoes.addWidget(btn_estoque)
        row_botoes.addWidget(btn_oport)
        row_botoes.addWidget(btn_pdf)
        row_botoes.addStretch()

        layout.addWidget(self.table_analise)
        layout.addLayout(row_botoes)

    # --------------------------------------------------------------------------------
    # ABA 4 - ORÇAMENTO
    # --------------------------------------------------------------------------------
    def setup_tab_orcamento(self):
        layout = QVBoxLayout(self.tab_orcamento)

        label_info = QLabel(
            "Gere dois arquivos de orçamento (PDF, Excel) com as cartas do arquivo Scrapper.\n"
            "Edite quantidade, desconto e gere o arquivo final."
        )
        layout.addWidget(label_info)

        row_global_discount = QHBoxLayout()
        label_global_discount = QLabel("Desconto Global (%):")
        self.slider_global_discount = QSlider(Qt.Horizontal)
        self.slider_global_discount.setRange(0, 100)
        self.slider_global_discount.setValue(50)
        self.slider_global_discount.setSingleStep(1)
        self.slider_global_discount.setToolTip("Defina um desconto global (porcentagem) a aplicar em todos os itens")

        self.spin_global_discount = QSpinBox()
        self.spin_global_discount.setRange(0, 100)
        self.spin_global_discount.setValue(50)
        self.spin_global_discount.setToolTip("Desconto global atual")

        self.slider_global_discount.valueChanged.connect(self.spin_global_discount.setValue)
        self.spin_global_discount.valueChanged.connect(self.slider_global_discount.setValue)
        self.spin_global_discount.valueChanged.connect(self.on_update_table_orcamento)

        row_global_discount.addWidget(label_global_discount)
        row_global_discount.addWidget(self.slider_global_discount)
        row_global_discount.addWidget(self.spin_global_discount)
        row_global_discount.addStretch()

        layout.addLayout(row_global_discount)

        self.table_orcamento = QTableWidget()
        self.table_orcamento.setColumnCount(7)
        self.table_orcamento.setHorizontalHeaderLabels([
            "Nome", "Coleção", "Número", "Preço Unit (R$)",
            "Quantidade", "Desconto (%)", "Preço Final (R$)"
        ])
        self.table_orcamento.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table_orcamento.setToolTip("Edite as quantidades e descontos individualmente")

        layout.addWidget(self.table_orcamento)

        row_totals = QHBoxLayout()
        self.lbl_total_original = QLabel("Total Original: 0.00")
        self.lbl_total_final = QLabel("Total Final: 0.00")
        row_totals.addWidget(self.lbl_total_original)
        row_totals.addSpacing(30)
        row_totals.addWidget(self.lbl_total_final)
        row_totals.addStretch()

        layout.addLayout(row_totals)

        self.btn_gerar_orcamento = QPushButton("Gerar Orçamento (PDF + Excel)")
        self.btn_gerar_orcamento.setIcon(self.style().standardIcon(QStyle.SP_DialogOkButton))
        self.btn_gerar_orcamento.setToolTip("Gera arquivos de orçamento baseados nos valores da tabela acima")
        self.btn_gerar_orcamento.clicked.connect(self.on_gerar_orcamento)

        layout.addWidget(self.btn_gerar_orcamento)
        layout.addStretch()

    # --------------------------------------------------------------------------------
    # MÉTODOS DE TEMA (CLARO/ESCURO) - MELHORADOS
    # --------------------------------------------------------------------------------
    def aplicar_estilos_iniciais(self):
        """Configura o tema inicial (escuro) e ajusta o botão de toggle."""
        self.aplicar_tema_escuro()
        self.toggle_tema_button.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
        self.toggle_tema_button.setText("Modo: Escuro")

    def on_toggle_tema(self):
        """Alterna entre modo claro e escuro com animação suave no botão."""
        from PyQt5.QtCore import QSequentialAnimationGroup, QEasingCurve
        pos_inicial = self.toggle_tema_button.pos()
        if self.modo_escuro:
            self.aplicar_tema_claro()
            self.modo_escuro = False
            self.toggle_tema_button.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
            self.toggle_tema_button.setText("Modo: Claro")
        else:
            self.aplicar_tema_escuro()
            self.modo_escuro = True
            self.toggle_tema_button.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
            self.toggle_tema_button.setText("Modo: Escuro")

        # Cria uma animação sequencial: primeiro sobe o botão, depois desce de forma suave
        anim_group = QSequentialAnimationGroup(self)
        anim_up = QPropertyAnimation(self.toggle_tema_button, b"pos")
        anim_up.setDuration(150)
        anim_up.setStartValue(pos_inicial)
        anim_up.setEndValue(QPoint(pos_inicial.x(), pos_inicial.y() - 10))
        anim_up.setEasingCurve(QEasingCurve.OutQuad)

        anim_down = QPropertyAnimation(self.toggle_tema_button, b"pos")
        anim_down.setDuration(150)
        anim_down.setStartValue(QPoint(pos_inicial.x(), pos_inicial.y() - 10))
        anim_down.setEndValue(pos_inicial)
        anim_down.setEasingCurve(QEasingCurve.InQuad)

        anim_group.addAnimation(anim_up)
        anim_group.addAnimation(anim_down)
        anim_group.start(QSequentialAnimationGroup.DeleteWhenStopped)

    def aplicar_tema_escuro(self):
        estilo_escuro = """
            QMainWindow {
                background-color: #1c1c1c;
            }
            QWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                font-size: 12pt;
                font-family: "Segoe UI", sans-serif;
            }
            QLineEdit, QSpinBox, QTableWidget, QTextEdit, QProgressBar, QSlider, QListWidget {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555555;
                font-size: 12pt;
            }
            QPushButton {
                background-color: #444444;
                color: #ffffff;
                border: 1px solid #666666;
                padding: 5px;
                font-size: 12pt;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
            }
            QTabBar::tab {
                background: #444444;
                color: #e0e0e0;
                padding: 8px;
                font-size: 12pt;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #555555;
                font-weight: bold;
            }
            QTableWidget QHeaderView::section {
                background-color: #444444;
                color: #e0e0e0;
                border: 1px solid #555555;
                font-size: 12pt;
            }
            QToolTip {
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #333333;
            }
        """
        self.setStyleSheet(estilo_escuro)

    def aplicar_tema_claro(self):
        estilo_claro = """
            QMainWindow {
                background-color: #f0f0f0;
            }
            QWidget {
                background-color: #ffffff;
                color: #333333;
                font-size: 12pt;
                font-family: "Segoe UI", sans-serif;
            }
            QLineEdit, QSpinBox, QTableWidget, QTextEdit, QProgressBar, QSlider, QListWidget {
                background-color: #fafafa;
                color: #333333;
                border: 1px solid #cccccc;
                font-size: 12pt;
            }
            QPushButton {
                background-color: #e0e0e0;
                color: #333333;
                border: 1px solid #bbbbbb;
                padding: 5px;
                font-size: 12pt;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
            }
            QTabBar::tab {
                background: #dddddd;
                color: #333333;
                padding: 8px;
                font-size: 12pt;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #cccccc;
                font-weight: bold;
            }
            QTableWidget QHeaderView::section {
                background-color: #dddddd;
                color: #333333;
                border: 1px solid #cccccc;
                font-size: 12pt;
            }
            QToolTip {
                background-color: #f9f9f9;
                color: #333333;
                border: 1px solid #bbbbbb;
            }
        """
        self.setStyleSheet(estilo_claro)

    # --------------------------------------------------------------------------------
    # LÓGICA DA ABA DE CARTAS
    # --------------------------------------------------------------------------------
    def on_browse_output_folder(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecione a pasta de saída")
        if pasta:
            config.OUTPUT_FOLDER = pasta
            self.input_output_folder.setText(pasta)

    def on_search_cards_api(self):
        query = self.input_search_card.text().strip()
        if not query:
            self.log("Por favor, digite algo para pesquisar (aba Cartas).")
            return

        for i in reversed(range(self.grid_mosaico.count())):
            item_grid = self.grid_mosaico.itemAt(i)
            if item_grid:
                widget = item_grid.widget()
                if widget:
                    widget.deleteLater()

        self.search_and_display_cards(query)

    def search_and_display_cards(self, query):
        try:
            self.log(f"Buscando cartas para: {query}")
            url_sets = "https://api.pokemontcg.io/v2/sets"
            resp_sets = requests.get(url_sets)
            data_sets = resp_sets.json()
            sets_list = data_sets.get("data", [])

            parts = query.split()
            if len(parts) == 2:
                set_code = parts[0].upper()
                card_number = parts[1]
                matched_set = None
                for cset in sets_list:
                    ptcgo_code = (cset.get("ptcgoCode") or "").upper()
                    if ptcgo_code == set_code:
                        matched_set = cset
                        break
                if matched_set:
                    set_id = matched_set["id"]
                    url_search = f'https://api.pokemontcg.io/v2/cards?q=set.id:"{set_id}" number:"{card_number}"'
                    resp_cards = requests.get(url_search)
                    data_cards = resp_cards.json()
                    cards_found = data_cards.get("data", [])
                    self.display_cards_mosaic(cards_found)
                    return

            if len(parts) == 1:
                up = parts[0].upper()
                matched_set2 = None
                for cset in sets_list:
                    ptcgo_code = (cset.get("ptcgoCode") or "").upper()
                    if ptcgo_code == up:
                        matched_set2 = cset
                        break
                if matched_set2:
                    set_id = matched_set2["id"]
                    url_search = f'https://api.pokemontcg.io/v2/cards?q=set.id:"{set_id}"'
                    resp_cards = requests.get(url_search)
                    data_cards = resp_cards.json()
                    cards_found = data_cards.get("data", [])
                    self.display_cards_mosaic(cards_found)
                    return

            url_name = f'https://api.pokemontcg.io/v2/cards?q=name:"{query}"'
            resp_cards2 = requests.get(url_name)
            data_cards2 = resp_cards2.json()
            cards_found2 = data_cards2.get("data", [])
            self.display_cards_mosaic(cards_found2)

        except Exception as e:
            self.log(f"Erro ao buscar cartas: {e}")

    def display_cards_mosaic(self, cards_list):
        if not cards_list:
            self.log("Nenhuma carta encontrada para o critério fornecido.")
            return

        row = 0
        col = 0
        max_cols = 4

        for card in cards_list:
            frame_card = QFrame()
            frame_card.setFrameShape(QFrame.StyledPanel)
            layout_vertical = QVBoxLayout(frame_card)

            img_url = card.get("images", {}).get("small", "")
            pix = None
            if img_url:
                try:
                    resp_img = requests.get(img_url, stream=True)
                    if resp_img.status_code == 200:
                        pix = QPixmap()
                        pix.loadFromData(resp_img.content)
                except:
                    pass
            label_img = QLabel()
            if pix:
                label_img.setPixmap(pix.scaled(QSize(120, 200), Qt.KeepAspectRatio, Qt.SmoothTransformation))

            layout_vertical.addWidget(label_img, alignment=Qt.AlignCenter)

            card_name = card.get("name", "")
            lbl_card_name = QLabel(card_name)
            lbl_card_name.setStyleSheet("font-weight: bold;")
            lbl_card_name.setAlignment(Qt.AlignCenter)
            layout_vertical.addWidget(lbl_card_name)

            card_set = card.get("set", {})
            set_name = card_set.get("name", "")
            card_number = card.get("number", "")
            lbl_card_set = QLabel(f"{set_name} - {card_number}")
            lbl_card_set.setAlignment(Qt.AlignCenter)
            layout_vertical.addWidget(lbl_card_set)

            btn_add = QPushButton("Adicionar")
            btn_add.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            btn_add.clicked.connect(lambda _, c=card: self.on_adicionar_carta(c))
            layout_vertical.addWidget(btn_add)

            self.grid_mosaico.addWidget(frame_card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def on_adicionar_carta(self, card):
        nome = card.get("name", "")
        numero = card.get("number", "")
        set_obj = card.get("set", {})
        colecao_sigla = set_obj.get("ptcgoCode", "UNK")

        for c in self.selected_cards:
            if (c.get("name", "") == nome and
                c.get("set", {}).get("id", "") == set_obj.get("id", "") and
                c.get("number", "") == numero):
                self.log("Esta carta já foi adicionada.")
                return

        self.selected_cards.append(card)
        self.list_selected_cards.addItem(f"{nome} | {colecao_sigla} | {numero}")

    def on_criar_scrapper_csv(self):
        if not self.selected_cards:
            self.log("Nenhuma carta selecionada para criar CSV de Scrapper.")
            return

        csv_path = os.path.join(config.OUTPUT_FOLDER, "cartas_para_scrapper.csv")
        colunas = ["nome", "colecao", "numero"]

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as arquivo:
            writer = csv.DictWriter(arquivo, fieldnames=colunas, delimiter=";")
            writer.writeheader()

            for card in self.selected_cards:
                nome = card.get("name", "")
                set_obj = card.get("set", {})
                colecao_sigla = set_obj.get("ptcgoCode", "UNK")

                numero_carta = card.get("number", "").zfill(3)
                total_cartas = str(set_obj.get("printedTotal", "000")).zfill(3)
                numero_formatado = f"{numero_carta}/{total_cartas}"

                writer.writerow({
                    "nome": nome,
                    "colecao": colecao_sigla,
                    "numero": numero_formatado
                })

        self.log(f"CSV criado com sucesso em: {csv_path}")

    # --------------------------------------------------------------------------------
    # EVENTOS - RASPAGEM
    # --------------------------------------------------------------------------------
    def on_browse_cards(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecione CSV de Cartas", "", "CSV Files (*.csv);;All Files (*)"
        )
        if caminho:
            self.input_file_cards.setText(caminho)
            self.df_cards = carrega_lista_cards(caminho, config)
            self.list_cards.clear()
            if not self.df_cards.empty:
                for idx, row in self.df_cards.iterrows():
                    texto_list = f"Nome={row['nome']}, Coleção={row['colecao']}, Número={row['numero']}"
                    self.list_cards.addItem(texto_list)
                self.btn_buscar.setEnabled(True)
            else:
                self.log("Nenhuma carta carregada (CSV vazio ou colunas inválidas).")

    def on_buscar_precos(self):
        if self.df_cards.empty:
            self.log("Nenhum CSV de cartas carregado para raspagem.")
            return
        self.log("[INFO] Iniciando raspagem individual...")
        threading.Thread(target=self.raspagem_individual, daemon=True).start()

    def raspagem_individual(self):
        resultados_locais = []
        total = len(self.df_cards)

        # 🔁 Cria o driver uma vez só
        scraper = LigaPokemonScraper(
            url_base=config.WEBSITE_1,
            debug=config.DEBUG,
            tesseract_cmd=config.TESSERACT_CMD,
            tempo_espera=config.TEMPO_ESPERA
        )
        
        scraper.limpar_carrinho_completo()

        for i, row in self.df_cards.iterrows():
            perc = int((i + 1) / total * 100)
            self.update_progress(perc)
            nome = row["nome"]
            colecao = row["colecao"]
            numero = row["numero"]
            self.log(f"Buscando {nome} ({colecao} - {numero})...")

            try:
                retorno = scraper.busca_carta_completa(nome, colecao, numero)
                if retorno:
                    resultados_locais.extend(retorno)
                    self.log(f"Encontrado {len(retorno)} item(ns) NM para {nome}.")
                else:
                    self.log(f"Nada encontrado para {nome}.")
            except Exception as e:
                self.log(f"ERRO ao buscar {nome}: {e}")

        # 🔚 Fecha o driver no final
        scraper.limpar_carrinho_completo()
        scraper.fechar_driver()

        if resultados_locais:
            csv_path = os.path.join(config.OUTPUT_FOLDER, config.SAIDA_CSV)
            salvar_resultados_csv(resultados_locais, csv_path)
            self.log(f"Raspagem finalizada. Resultados salvos em {csv_path}")
            self.mostra_resultados_tabela(resultados_locais)
            self.carregar_e_exibir_orcamento_data()
        else:
            self.log("Nenhum resultado coletado na raspagem individual.")

    def on_limpar_historico(self):
        csv_path = os.path.join(config.OUTPUT_FOLDER, config.SAIDA_CSV)
        limpar_csv(csv_path)
        self.table_results.setRowCount(0)
        self.log("Histórico de raspagem foi removido.")
        self.df_raspados = pd.DataFrame()
        self.carregar_e_exibir_orcamento_data()

    # --------------------------------------------------------------------------------
    # EVENTOS - MONITORAMENTO
    # --------------------------------------------------------------------------------
    def on_browse_monitor(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecione CSV de Monitor", "", "CSV Files (*.csv);;All Files (*)"
        )
        if caminho:
            self.input_file_monitor.setText(caminho)
            self.df_monitor = carrega_lista_cards(caminho, config)
            self.list_monitor.clear()
            if not self.df_monitor.empty:
                for idx, row in self.df_monitor.iterrows():
                    texto_list = f"Monitor => Nome={row['nome']}, Coleção={row['colecao']}, Número={row['numero']}"
                    self.list_monitor.addItem(texto_list)
                self.btn_monitorar.setEnabled(True)
            else:
                self.log("Nenhum CSV de monitor carregado ou colunas inválidas.")

    def on_iniciar_monitoramento(self):
        if self.monitor_running:
            self.log("Monitor já está em execução.")
            return
        if self.df_monitor.empty:
            self.log("Nenhum CSV de monitor carregado.")
            return

        self.monitor_running = True
        self.monitor_paused = False
        self.monitor_check_count = 0
        self.btn_pausar.setText("Pausar")
        self.btn_pausar.setEnabled(True)
        self.btn_pausar.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

        self.log("[MONITOR] Iniciando monitoramento em thread.")
        self.monitor_thread = threading.Thread(target=self.loop_monitor, daemon=True)
        self.monitor_thread.start()

    def on_pausar_monitoramento(self):
        if not self.monitor_running:
            return
        self.monitor_paused = not self.monitor_paused
        if self.monitor_paused:
            self.btn_pausar.setText("Retomar")
            self.btn_pausar.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.log("Monitoramento pausado.")
        else:
            self.btn_pausar.setText("Pausar")
            self.btn_pausar.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.log("Monitoramento retomado.")

    def loop_monitor(self):
        while self.monitor_running:
            if self.monitor_paused:
                time.sleep(1)
                continue

            self.monitor_check_count += 1
            self.log(f"[MONITOR] Checagem #{self.monitor_check_count} para {len(self.df_monitor)} cartas.")

            # Roda o monitor para cada carta do df_monitor
            total = len(self.df_monitor)
            results_monitor = []

            for i, row in self.df_monitor.iterrows():
                perc = int((i + 1) / total * 100)
                self.update_progress(perc)

                nome = row["nome"]
                colecao = row["colecao"]
                numero = row["numero"]
                self.log(f"[MONITOR] Conferindo {nome} ({colecao} - {numero})...")

                try:
                    scraper = LigaPokemonScraper(
                        url_base=config.WEBSITE_1,
                        debug=config.DEBUG,
                        tesseract_cmd=config.TESSERACT_CMD,
                        tempo_espera=config.TEMPO_ESPERA
                    )
                    retorno = scraper.busca_carta_completa(nome, colecao, numero)
                    if retorno:
                        results_monitor.extend(retorno)
                        preco_atual = retorno[0].get("preco", 0.0)
                        dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        mon_path = os.path.join(config.OUTPUT_FOLDER, config.MONITOR_CSV)
                        salvar_monitoramento(nome, colecao, numero, preco_atual, dt_str, mon_path)
                        self.log(f"[MONITOR] {nome} preco {preco_atual}")
                    else:
                        self.log(f"[MONITOR] NM não encontrado p/ {nome}.")
                except Exception as e:
                    self.log(f"[MONITOR] ERRO monitor {nome}: {e}")

            if results_monitor:
                self.mostra_resultados_tabela(results_monitor)

            tempo_base = config.MONITOR_INTERVALO_BASE
            variacao = config.MONITOR_VARIACAO
            espera = tempo_base + random.randint(0, variacao)
            self.update_progress(0)

            for seg in range(espera):
                if not self.monitor_running:
                    break
                if self.monitor_paused:
                    time.sleep(1)
                    seg -= 1
                    continue
                restante = espera - seg
                self.update_cronometro(restante)
                time.sleep(1)

        self.log("[MONITOR] Monitoramento finalizado.")
        self.btn_pausar.setEnabled(False)
        self.update_cronometro(0)

    # --------------------------------------------------------------------------------
    # ABA DE ANÁLISE (EVENTOS)
    # --------------------------------------------------------------------------------
    def on_analise_grafico(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df_local = self.carregar_resultados_saidas()
        if df_local.empty or "preco" not in df_local.columns:
            self.log("CSV vazio ou sem coluna 'preco' para gerar gráfico.")
            return

        df_local["preco"] = pd.to_numeric(df_local["preco"], errors="coerce").fillna(0.0)
        plt.figure(figsize=(5, 3))
        plt.plot(df_local["preco"], marker="o", label="Preço")
        plt.title("Tendência de Preços (Aba Análise)")
        plt.xlabel("Índice")
        plt.ylabel("Preço (R$)")
        plt.legend()

        buffer_ = BytesIO()
        plt.savefig(buffer_, format="png")
        plt.close()

        out_path = os.path.join(config.OUTPUT_FOLDER, "grafico_analise.png")
        with open(out_path, "wb") as fimg:
            fimg.write(buffer_.getvalue())

        self.log(f"Gráfico gerado e salvo em {out_path}")

    def on_analise_estoque(self):
        df_local = self.carregar_resultados_saidas()
        if df_local.empty:
            self.log("Nenhum dado para analisar estoque.")
            return
        estoque_info = analisar_estoque(df_local)
        if not estoque_info:
            self.log("Não foi possível analisar estoque (falta coluna 'quantidade'?)")
            return

        msg = (
            f"Estoque Total: {estoque_info.get('total', 0)}\n"
            f"Estoque Médio: {estoque_info.get('media', 0):.1f}\n"
            f"Estoque Mín: {estoque_info.get('min', 0)}\n"
            f"Estoque Máx: {estoque_info.get('max', 0)}"
        )
        self.log(f"[ESTOQUE]\n{msg}")

    def on_analise_oportunidades(self):
        df_opp = self.carregar_monitor_registros()
        if df_opp.empty:
            self.log("Não há registros de monitoramento para analisar oportunidades.")
            return
        oportunidades = buscar_oportunidades(df_opp, limite_perc=30)
        if oportunidades.empty:
            self.log("Nenhuma oportunidade encontrada (abaixo da média).")
        else:
            self.mostra_analise_tabela(oportunidades)
            self.log("Oportunidades exibidas na tabela de Análise.")

    def on_analise_pdf(self):
        df_local = self.carregar_resultados_saidas()
        if df_local.empty:
            self.log("Nenhum dado para gerar PDF de análise.")
            return
        lista_dict = df_local.to_dict(orient="records")
        out_pdf = os.path.join(config.OUTPUT_FOLDER, "relatorio_analise.pdf")
        gerar_pdf_relatorio("Relatório de Busca/Monitor", lista_dict, out_pdf)
        self.log(f"PDF gerado: {out_pdf}")

    # --------------------------------------------------------------------------------
    # ORÇAMENTO
    # --------------------------------------------------------------------------------
    def carregar_e_exibir_orcamento_data(self):
        self.df_raspados = self.carregar_resultados_saidas()
        df_local = self.df_raspados.copy()
        self.table_orcamento.setRowCount(0)
        if df_local.empty or "preco" not in df_local.columns:
            return

        df_local["preco"] = pd.to_numeric(df_local["preco"], errors="coerce").fillna(0.0)

        for i in range(len(df_local)):
            row_idx = self.table_orcamento.rowCount()
            self.table_orcamento.insertRow(row_idx)

            nome = df_local.loc[i, "nome"]
            colecao = df_local.loc[i, "colecao"]
            numero = df_local.loc[i, "numero"]
            preco_unit = df_local.loc[i, "preco"]

            item_nome = QTableWidgetItem(str(nome))
            item_nome.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table_orcamento.setItem(row_idx, 0, item_nome)

            item_colecao = QTableWidgetItem(str(colecao))
            item_colecao.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table_orcamento.setItem(row_idx, 1, item_colecao)

            item_numero = QTableWidgetItem(str(numero))
            item_numero.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table_orcamento.setItem(row_idx, 2, item_numero)

            item_preco = QTableWidgetItem(f"{preco_unit:.2f}")
            item_preco.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table_orcamento.setItem(row_idx, 3, item_preco)

            item_qtd = QTableWidgetItem("1")
            self.table_orcamento.setItem(row_idx, 4, item_qtd)

            item_desc = QTableWidgetItem("")
            self.table_orcamento.setItem(row_idx, 5, item_desc)

            item_final = QTableWidgetItem("0.00")
            item_final.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table_orcamento.setItem(row_idx, 6, item_final)

        self.table_orcamento.itemChanged.connect(self.on_update_table_orcamento)
        self.recalcular_orcamento()

    def on_update_table_orcamento(self, _value=None):
        self.recalcular_orcamento()

    def recalcular_orcamento(self):
        row_count = self.table_orcamento.rowCount()
        if row_count == 0:
            self.lbl_total_original.setText("Total Original: 0.00")
            self.lbl_total_final.setText("Total Final: 0.00")
            return

        desconto_global = self.spin_global_discount.value()
        total_original = 0.0
        total_final = 0.0

        self.table_orcamento.blockSignals(True)
        for row_idx in range(row_count):
            preco_item = self.get_float_value(self.table_orcamento.item(row_idx, 3))
            quantidade_item = self.get_int_value(self.table_orcamento.item(row_idx, 4))
            desconto_item = self.get_float_value(self.table_orcamento.item(row_idx, 5))

            if desconto_item == 0.0:
                desconto_item = float(desconto_global)

            valor_original = preco_item * quantidade_item
            valor_com_desconto = valor_original * (1 - (desconto_item / 100.0))

            item_final = self.table_orcamento.item(row_idx, 6)
            if item_final is not None:
                item_final.setText(f"{valor_com_desconto:.2f}")

            total_original += valor_original
            total_final += valor_com_desconto

        self.table_orcamento.blockSignals(False)
        self.lbl_total_original.setText(f"Total Original: {total_original:.2f}")
        self.lbl_total_final.setText(f"Total Final: {total_final:.2f}")

    def on_gerar_orcamento(self):
        row_count = self.table_orcamento.rowCount()
        if row_count == 0:
            self.log("Nenhuma carta para gerar orçamento.")
            return

        dados_orc = []
        for row_idx in range(row_count):
            nome = self.table_orcamento.item(row_idx, 0).text() if self.table_orcamento.item(row_idx, 0) else ""
            colecao = self.table_orcamento.item(row_idx, 1).text() if self.table_orcamento.item(row_idx, 1) else ""
            numero = self.table_orcamento.item(row_idx, 2).text() if self.table_orcamento.item(row_idx, 2) else ""
            preco_unit = self.get_float_value(self.table_orcamento.item(row_idx, 3))
            quantidade = self.get_int_value(self.table_orcamento.item(row_idx, 4))
            desconto = self.get_float_value(self.table_orcamento.item(row_idx, 5))
            preco_final = self.get_float_value(self.table_orcamento.item(row_idx, 6))

            dic_item = {
                "nome": nome,
                "colecao": colecao,
                "numero": numero,
                "preco_unit": preco_unit,
                "quantidade": quantidade,
                "desconto_perc": desconto,
                "preco_final": preco_final
            }
            dados_orc.append(dic_item)

        pdf_path = os.path.join(config.OUTPUT_FOLDER, "orcamento.pdf")
        gerar_pdf_relatorio_orcamento("Orçamento de Cartas", dados_orc, pdf_path)

        excel_path = os.path.join(config.OUTPUT_FOLDER, "orcamento.xlsx")
        gerar_excel_orcamento("Orçamento de Cartas", dados_orc, excel_path, 0)

        self.log(f"Arquivos gerados:\nPDF: {pdf_path}\nExcel: {excel_path}")

    # --------------------------------------------------------------------------------
    # AUXILIARES GERAIS
    # --------------------------------------------------------------------------------
    def mostra_resultados_tabela(self, lista_resultados):
        self.table_results.setRowCount(0)
        for dic in lista_resultados:
            row_idx = self.table_results.rowCount()
            self.table_results.insertRow(row_idx)

            valores = [
                dic.get("nome", ""),
                dic.get("colecao", ""),
                dic.get("numero", ""),
                dic.get("condicao", ""),
                str(dic.get("quantidade", 0)),
                f"{dic.get('preco', 0.0):.2f}",
                f"{dic.get('preco_total', 0.0):.2f}",
                dic.get("lingua", "")
            ]
            for col, val in enumerate(valores):
                item_table = QTableWidgetItem(val)
                self.table_results.setItem(row_idx, col, item_table)

    def mostra_analise_tabela(self, df):
        self.table_analise.setRowCount(0)
        if df.empty:
            return
        df_str = df.astype(str)
        rows = df_str.values.tolist()
        cols = df_str.columns.tolist()
        self.table_analise.setColumnCount(len(cols))
        self.table_analise.setHorizontalHeaderLabels(cols)

        for row_data in rows:
            row_idx = self.table_analise.rowCount()
            self.table_analise.insertRow(row_idx)
            for col_idx, val in enumerate(row_data):
                item_table = QTableWidgetItem(val)
                self.table_analise.setItem(row_idx, col_idx, item_table)

    def carregar_resultados_saidas(self):
        csv_path = os.path.join(config.OUTPUT_FOLDER, config.SAIDA_CSV)
        if not os.path.exists(csv_path):
            return pd.DataFrame()
        df_res = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig")
        return df_res

    def carregar_monitor_registros(self):
        mon_path = os.path.join(config.OUTPUT_FOLDER, config.MONITOR_CSV)
        if not os.path.exists(mon_path):
            return pd.DataFrame()
        df_mon = pd.read_csv(mon_path, sep=";", encoding="utf-8-sig")
        return df_mon

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_cronometro(self, seconds):
        mm = seconds // 60
        ss = seconds % 60
        tempo = f"{mm:02}:{ss:02}"
        self.lbl_cron_val.setText(tempo)

    def append_log(self, text):
        """Exibe mensagens no painel de logs."""
        self.txt_logs.append(text)

    def log(self, text):
        """Método para gerar logs vindos de threads."""
        self.log_emitter.new_log.emit(text)

    def monitor_cronometro_tick(self):
        self.lbl_check_count.setText(str(self.monitor_check_count))

    def closeEvent(self, event):
        """Intercepta fechamento da janela para encerrar monitor."""
        self.monitor_running = False
        super().closeEvent(event)

    def get_float_value(self, item_widget):
        if item_widget is None:
            return 0.0
        try:
            return float(item_widget.text().replace(",", "."))
        except:
            return 0.0

    def get_int_value(self, item_widget):
        if item_widget is None:
            return 0
        try:
            return int(item_widget.text())
        except:
            return 0

# --------------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    # Carrega e exibe dados para Orçamento (caso existam)
    window.carregar_e_exibir_orcamento_data()
    try:
        sys.exit(app.exec_())
    finally:
        LigaPokemonScraper.fechar_todos_os_drivers()

if __name__ == "__main__":
    main()
