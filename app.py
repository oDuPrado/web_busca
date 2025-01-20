import PySimpleGUI as sg
import pandas as pd
import numpy as np
import random
import time
from datetime import datetime
from pathlib import Path
import threading

import config
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO

from utils.dados import (
    carrega_lista_cards,
    salvar_resultados_csv,
    salvar_monitoramento,
    limpar_csv,
    buscar_oportunidades,
    analisar_estoque,
    gerar_pdf_relatorio
)
from utils.scraper import LigaPokemonScraper

class App:
    def __init__(self):
        sg.theme(config.TEMA_INICIAL)
        self.layout_inicial()

    def layout_inicial(self):
        self.df_cards = pd.DataFrame()
        self.resultados = []
        self.df_monitor = pd.DataFrame()
        self.monitor_thread = None
        self.monitor_paused = False
        self.monitor_running = False
        self.monitor_check_count = 0
        self.resultados_analise = []  # Para armazenar dados a exibir na aba Análise

        # --------------------- Aba 1: Raspagem & Monitoramento ---------------------
        # Seção principal de Cards
        col_cards = [
            [sg.Text("Arquivo de Cartas (nome;colecao;numero):")],
            [
                sg.Input(key="-FILE_CARDS-", enable_events=True, size=(40,1)),
                sg.FileBrowse("Localizar CSV", file_types=(("CSV Files", "*.csv"),))
            ],
            [sg.Listbox(values=[], size=(60,6), key="-LIST_CARDS-")],
            [
                sg.Button("Buscar Preços", key="-BUSCAR-", size=(12,1), disabled=True),
                sg.Button("Limpar Histórico", key="-LIMPAR-HIST-", size=(14,1))
            ]
        ]

        col_tabela = [
            [sg.Text("Resultados (Raspagem/Monitoramento):")],
            [sg.Table(values=[],
                      headings=["Nome","Coleção","Número","Cond","Qtde","Preço","Total","Língua"],
                      key="-TABLE-RESULTS-",
                      auto_size_columns=True,
                      display_row_numbers=True,
                      justification="left",
                      num_rows=8)]
        ]

        col_progress = [
            [sg.Text("Progresso:")],
            [sg.ProgressBar(config.PROGRESS_MAX, orientation='h', size=(38, 20), key="-PROGRESS-")],
            [sg.Text("Tempo p/ próxima checagem:", size=(22,1)), sg.Text("00:00", key="-CRONOMETRO-")],
            [sg.Text("Total de checagens:", size=(22,1)), sg.Text("0", key="-CHECK-COUNT-")]
        ]

        # Monitor
        col_monitor = [
            [sg.Text("Arquivo Monitor (nome;colecao;numero):")],
            [
                sg.Input(key="-FILE_MONITOR-", enable_events=True, size=(40,1)),
                sg.FileBrowse("Localizar CSV", file_types=(("CSV Files", "*.csv"),))
            ],
            [sg.Listbox(values=[], size=(60,5), key="-LIST_MONITOR-")],
            [
                sg.Button("Iniciar Monitoramento", key="-MONITORAR-", size=(18,1), disabled=True),
                sg.Button("Pausar", key="-PAUSAR-", size=(10,1), disabled=True)
            ]
        ]

        aba1_layout = [
            [
                sg.Frame("Cartas para Raspagem", col_cards),
                sg.VerticalSeparator(),
                sg.Frame("Tabela de Resultados", col_tabela)
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Frame("Progresso & Cronômetro", col_progress),
                sg.VerticalSeparator(),
                sg.Frame("Monitoramento Contínuo", col_monitor)
            ],
            [sg.Multiline(size=(110,8), key="-LOGS-", autoscroll=True, disabled=True)]
        ]

        # --------------------- Aba 2: Análise ---------------------
        # Aqui podemos ter uma tabela extra, análises de estoque, oportunidades, e geração de relatório PDF
        col_analise_tabela = [
            [sg.Text("Resultados de Análise:")],
            [sg.Table(values=[],
                      headings=["Nome","Coleção","Número","Preço", "Outros?"],  # Exemplo
                      key="-TAB-ANALISE-TABLE-",
                      auto_size_columns=True,
                      display_row_numbers=True,
                      justification="left",
                      num_rows=8)]
        ]

        col_analise_botoes = [
            [sg.Button("Gerar Gráfico Tendência", key="-ANALISE-GRAF-", size=(20,1))],
            [sg.Button("Analisar Estoque", key="-ANALISE-ESTOQUE-", size=(20,1))],
            [sg.Button("Buscar Oportunidades", key="-ANALISE-OPORT-", size=(20,1))],
            [sg.Button("Gerar Relatório PDF", key="-ANALISE-PDF-", size=(20,1))]
        ]
        col_analise_result = [
            [sg.Text("Gráfico ou Mensagens de Análise:")],
            [sg.Image(key="-ANALISE-GRAFICO-")]
        ]

        aba2_layout = [
            [
                sg.Frame("Tabela de Análise", col_analise_tabela),
                sg.VerticalSeparator(),
                sg.Frame("Ações de Análise", col_analise_botoes),
                sg.VerticalSeparator(),
                sg.Frame("Resultados Visuais", col_analise_result)
            ]
        ]

        # Tabs
        tabs = [
            [sg.Tab("Raspagem & Monitoramento", aba1_layout, key="-TAB1-"),
             sg.Tab("Análise", aba2_layout, key="-TAB2-")]
        ]

        layout = [
            [sg.TabGroup(tabs, key="-TABGROUP-")]
        ]

        self.window = sg.Window("Raspagem & Monitor - Com Abas e Análise", layout, finalize=True)
        self.progress_bar = self.window["-PROGRESS-"]

    def run(self):
        while True:
            event, values = self.window.read(timeout=500)
            if event in (sg.WIN_CLOSED, "Exit"):
                break

            # ------------------------------------------------------------------------------------
            # ABA 1 - Raspagem & Monitor
            # ------------------------------------------------------------------------------------
            if event == "-FILE_CARDS-":
                csv_path = values["-FILE_CARDS-"]
                if csv_path:
                    self.df_cards = carrega_lista_cards(csv_path, config)
                    if not self.df_cards.empty:
                        linhas_exibicao = []
                        for idx, row in self.df_cards.iterrows():
                            texto = f"Nome={row['nome']}, Coleção={row['colecao']}, Número={row['numero']}"
                            linhas_exibicao.append(texto)
                        self.window["-LIST_CARDS-"].update(linhas_exibicao)
                        self.window["-BUSCAR-"].update(disabled=False)

            if event == "-BUSCAR-":
                if self.df_cards.empty:
                    self.log("Nenhum CSV de cartas carregado.")
                else:
                    self.raspagem_individual()

            if event == "-LIMPAR-HIST-":
                limpar_csv(config.SAIDA_CSV)
                self.window["-TABLE-RESULTS-"].update([])
                self.log("Histórico de raspagem foi removido.")

            if event == "-FILE_MONITOR-":
                csv_path = values["-FILE_MONITOR-"]
                if csv_path:
                    self.df_monitor = carrega_lista_cards(csv_path, config)
                    if not self.df_monitor.empty:
                        linhas_exibicao = []
                        for idx, row in self.df_monitor.iterrows():
                            texto = f"Monitor => Nome={row['nome']}, Coleção={row['colecao']}, Número={row['numero']}"
                            linhas_exibicao.append(texto)
                        self.window["-LIST_MONITOR-"].update(linhas_exibicao)
                        self.window["-MONITORAR-"].update(disabled=False)

            if event == "-MONITORAR-":
                if self.df_monitor.empty:
                    self.log("Nenhum CSV de monitor carregado.")
                else:
                    self.iniciar_monitoramento()

            if event == "-PAUSAR-":
                self.monitor_paused = not self.monitor_paused
                if self.monitor_paused:
                    self.window["-PAUSAR-"].update("Retomar")
                    self.log("Monitoramento pausado.")
                else:
                    self.window["-PAUSAR-"].update("Pausar")
                    self.log("Monitoramento retomado.")

            # ------------------------------------------------------------------------------------
            # ABA 2 - Análise
            # ------------------------------------------------------------------------------------
            if event == "-ANALISE-GRAF-":
                self.gerar_grafico_analise()

            if event == "-ANALISE-ESTOQUE-":
                # Ler do SAIDA_CSV ou do MONITOR_CSV?
                # Exemplo: usar o SAIDA_CSV
                df_local = self.carregar_resultados_saidas()
                if not df_local.empty:
                    from utils.dados import analisar_estoque
                    estoque_info = analisar_estoque(df_local)
                    msg = (f"Estoque Total: {estoque_info.get('total',0)}\n"
                           f"Estoque Médio: {estoque_info.get('media',0):.1f}\n"
                           f"Estoque Mín: {estoque_info.get('min',0)}\n"
                           f"Estoque Máx: {estoque_info.get('max',0)}")
                    sg.popup("Análise de Estoque", msg)
                else:
                    sg.popup("Nenhum dado para analisar estoque.")

            if event == "-ANALISE-OPORT-":
                # Buscar oportunidades no MONITOR_CSV
                df_opp = self.carregar_monitor_registros()
                if df_opp.empty:
                    sg.popup("Não há registros de monitoramento para analisar.")
                else:
                    from utils.dados import buscar_oportunidades
                    oportunidades = buscar_oportunidades(df_opp, limite_perc=30)
                    if oportunidades.empty:
                        sg.popup("Nenhuma oportunidade (abaixo da média) encontrada.")
                    else:
                        # Exibir na tabela da aba de análise
                        self.mostra_analise_tabela(oportunidades)

            if event == "-ANALISE-PDF-":
                # Gera PDF do monitor ou do SAIDA_CSV
                df_local = self.carregar_resultados_saidas()
                if not df_local.empty:
                    lista = df_local.to_dict(orient="records")
                    from utils.dados import gerar_pdf_relatorio
                    gerar_pdf_relatorio("Relatório de Busca/Monitor", lista, "relatorio_analise.pdf")
                    sg.popup("PDF gerado: relatorio_analise.pdf")
                else:
                    sg.popup("Nenhum dado para gerar PDF.")

        self.window.close()

    # ------------------------------------------------------------------------------------
    # Métodos Auxiliares - Raspagem & Monitor
    # ------------------------------------------------------------------------------------
    def raspagem_individual(self):
        self.log("[INFO] Iniciando raspagem individual...")
        scraper = LigaPokemonScraper(
            url_base=config.WEBSITE_1,
            debug=config.DEBUG,
            tesseract_cmd=config.TESSERACT_CMD,
            tempo_espera=config.TEMPO_ESPERA
        )
        resultados_locais = []
        total = len(self.df_cards)
        for i, row in self.df_cards.iterrows():
            perc = int((i+1)/total * 100)
            self.window["-PROGRESS-"].Update(perc)

            nome = row["nome"]
            col = row["colecao"]
            num = row["numero"]
            self.log(f"Buscando {nome} ({col} - {num})...")

            try:
                retorno = scraper.busca_carta_completa(nome, col, num)
                if retorno:
                    resultados_locais.extend(retorno)
                    self.log(f"Encontrado {len(retorno)} item(ns) NM para {nome}.")
                else:
                    self.log(f"Nada encontrado para {nome}.")
            except Exception as e:
                self.log(f"ERRO ao buscar {nome}: {e}")

        scraper.fechar_driver()
        if resultados_locais:
            salvar_resultados_csv(resultados_locais, config.SAIDA_CSV)
            self.log("Raspagem finalizada. Resultados salvos.")
            self.mostra_resultados_tabela(resultados_locais)
        else:
            self.log("Nenhum resultado coletado na raspagem individual.")

    def iniciar_monitoramento(self):
        if self.monitor_running:
            self.log("Monitor já está rodando.")
            return
        self.monitor_running = True
        self.monitor_paused = False
        self.monitor_check_count = 0
        self.window["-PAUSAR-"].update("Pausar")
        self.window["-PAUSAR-"].update(disabled=False)
        self.log("[MONITOR] Iniciando monitoramento em thread.")
        self.monitor_thread = threading.Thread(target=self.loop_monitor, daemon=True)
        self.monitor_thread.start()

    def loop_monitor(self):
        while self.monitor_running:
            if self.monitor_paused:
                time.sleep(1)
                continue

            self.monitor_check_count += 1
            self.log(f"[MONITOR] Checagem #{self.monitor_check_count} para {len(self.df_monitor)} cartas.")

            scraper = LigaPokemonScraper(
                url_base=config.WEBSITE_1,
                debug=config.DEBUG,
                tesseract_cmd=config.TESSERACT_CMD,
                tempo_espera=config.TEMPO_ESPERA
            )
            total = len(self.df_monitor)
            results_monitor = []
            for i, row in self.df_monitor.iterrows():
                perc = int((i+1)/total * 100)
                self.window["-PROGRESS-"].Update(perc)

                nome = row["nome"]
                col = row["colecao"]
                num = row["numero"]
                self.log(f"[MONITOR] Conferindo {nome} ({col} - {num})...")

                try:
                    retorno = scraper.busca_carta_completa(nome, col, num)
                    if retorno:
                        results_monitor.extend(retorno)
                        preco_atual = retorno[0].get("preco",0.0)
                        dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        salvar_monitoramento(nome, col, num, preco_atual, dt_str, config.MONITOR_CSV)
                        self.log(f"[MONITOR] {nome} preco {preco_atual}")
                    else:
                        self.log(f"[MONITOR] NM não encontrado p/ {nome}.")
                except Exception as e:
                    self.log(f"[MONITOR] ERRO monitor {nome}: {e}")

            scraper.fechar_driver()

            if results_monitor:
                self.mostra_resultados_tabela(results_monitor)

            tempo_base = config.MONITOR_INTERVALO_BASE
            variacao = config.MONITOR_VARIACAO
            espera = tempo_base + random.randint(0, variacao)
            self.window["-PROGRESS-"].Update(0)

            for seg in range(espera):
                if not self.monitor_running:
                    break
                if self.monitor_paused:
                    time.sleep(1)
                    seg -= 1
                    continue
                restante = espera - seg
                self.log_cronometro(restante)
                time.sleep(1)

        self.log("[MONITOR] Monitoramento finalizado.")
        self.window["-PAUSAR-"].update(disabled=True)
        self.log_cronometro(0)

    # ------------------------------------------------------------------------------------
    # Métodos Auxiliares - Análise
    # ------------------------------------------------------------------------------------
    def gerar_grafico_analise(self):
        """
        Tenta ler SAIDA_CSV e plotar. Exibe na aba "Análise".
        """
        import os
        from utils.dados import pd

        if not os.path.exists(config.SAIDA_CSV):
            sg.popup("Nenhum CSV de resultados para gerar gráfico.")
            return

        df = pd.read_csv(config.SAIDA_CSV, sep=";", encoding="utf-8-sig")
        if df.empty or "preco" not in df.columns:
            sg.popup("CSV vazio ou sem coluna 'preco'.")
            return

        df["preco"] = df["preco"].astype(float)
        plt.figure(figsize=(5,3))
        plt.plot(df["preco"], marker="o", label="Preço")
        plt.title("Tendência de Preços (Aba Análise)")
        plt.xlabel("Índice")
        plt.ylabel("Preço (R$)")
        plt.legend()

        buf = BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        self.window["-ANALISE-GRAFICO-"].update(data=buf.getvalue())

    def mostra_analise_tabela(self, df):
        """
        Exibe DataFrame 'df' na tabela da aba "Análise" (-TAB-ANALISE-TABLE-)
        """
        if df.empty:
            sg.popup("Nenhum dado para mostrar na tabela de Análise.")
            return
        df2 = df.copy()
        # Converte tudo para string
        df2 = df2.astype(str)
        table_values = df2.values.tolist()
        self.window["-TAB-ANALISE-TABLE-"].update(table_values)

    def carregar_resultados_saidas(self):
        """
        Lê SAIDA_CSV e retorna DataFrame
        """
        import os
        from utils.dados import pd

        if not os.path.exists(config.SAIDA_CSV):
            return pd.DataFrame()
        df = pd.read_csv(config.SAIDA_CSV, sep=";", encoding="utf-8-sig")
        return df

    def carregar_monitor_registros(self):
        """
        Lê MONITOR_CSV e retorna DataFrame
        """
        import os
        from utils.dados import pd

        if not os.path.exists(config.MONITOR_CSV):
            return pd.DataFrame()
        df = pd.read_csv(config.MONITOR_CSV, sep=";", encoding="utf-8-sig")
        return df

    # ------------------------------------------------------------------------------------
    # Funções de Interface e Logs
    # ------------------------------------------------------------------------------------
    def mostra_resultados_tabela(self, lista_resultados):
        table_values = []
        for dic in lista_resultados:
            table_values.append([
                dic.get("nome",""),
                dic.get("colecao",""),
                dic.get("numero",""),
                dic.get("condicao",""),
                dic.get("quantidade",0),
                dic.get("preco",0.0),
                dic.get("preco_total",0.0),
                dic.get("lingua","")
            ])
        self.window["-TABLE-RESULTS-"].update(table_values)

    def log_cronometro(self, s):
        mm = s // 60
        ss = s % 60
        tempo = f"{mm:02}:{ss:02}"
        self.window["-CRONOMETRO-"].update(tempo)

    def log(self, texto):
        """
        Print em -LOGS-
        """
        self.window["-LOGS-"].print(texto)

def main():
    app = App()
    app.run()

if __name__ == "__main__":
    main()
