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
matplotlib.use("Agg")  # Evita conflitos de backend no PySimpleGUI
import matplotlib.pyplot as plt
from io import BytesIO

from utils.dados import (
    carrega_lista_cards,
    salvar_resultados_csv,
    salvar_monitoramento,
    limpar_csv
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

        # Tabela de Resultados
        col_tabela = [
            [sg.Text("Resultados (Raspagem/Monitoramento):")],
            [sg.Table(values=[],
                      headings=["Nome","Coleção","Número","Cond","Qtde","Preço","Total","Língua"],
                      key="-TABLE-RESULTS-",
                      auto_size_columns=True,
                      display_row_numbers=True,
                      justification="left",
                      num_rows=8,
                      size=(None,8))]
        ]

        # Barra de progresso + Cronômetro
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

        # Gráfico (opcional)
        col_grafico = [
            [sg.Button("Gerar Gráfico", key="-GERAR-GRAFICO-", disabled=True)],
            [sg.Image(key="-GRAFICO-")]
        ]

        # Layout final
        layout = [
            [sg.Frame("Cartas para Raspagem", col_cards), sg.VerticalSeparator(), sg.Frame("Tabela de Resultados", col_tabela)],
            [sg.HorizontalSeparator()],
            [sg.Frame("Progresso & Cronômetro", col_progress), sg.VerticalSeparator(), sg.Frame("Monitoramento Contínuo", col_monitor), sg.VerticalSeparator(), sg.Frame("Tendência de Preços", col_grafico)],
            [sg.Output(size=(120,10), key="-LOGS-")]
        ]

        self.window = sg.Window("Raspagem & Monitor - Completo", layout, finalize=True)

        self.progress_bar = self.window["-PROGRESS-"]

    def run(self):
        while True:
            event, values = self.window.read(timeout=500)
            if event in (sg.WIN_CLOSED, "Exit"):
                break

            # Carrega CSV de cartas
            if event == "-FILE_CARDS-":
                csv_path = values["-FILE_CARDS-"]
                if csv_path:
                    self.df_cards = carrega_lista_cards(csv_path, config)
                    if not self.df_cards.empty:
                        linhas_exibicao = [
                            f"Nome={row['nome']}, Coleção={row['colecao']}, Número={row['numero']}"
                            for _, row in self.df_cards.iterrows()
                        ]
                        self.window["-LIST_CARDS-"].update(linhas_exibicao)
                        self.window["-BUSCAR-"].update(disabled=False)

            # Botão "Buscar Preços"
            if event == "-BUSCAR-":
                if self.df_cards.empty:
                    self.log("Nenhum CSV de cartas carregado.")
                else:
                    self.raspagem_individual()

            # Botão "Limpar Histórico"
            if event == "-LIMPAR-HIST-":
                # Apaga CSV do SAIDA_CSV e limpa tabela
                from utils.dados import limpar_csv
                limpar_csv(config.SAIDA_CSV)
                self.window["-TABLE-RESULTS-"].update([])
                self.log("Histórico de raspagem foi removido.")

            # Carrega CSV de monitor
            if event == "-FILE_MONITOR-":
                csv_path = values["-FILE_MONITOR-"]
                if csv_path:
                    self.df_monitor = carrega_lista_cards(csv_path, config)
                    if not self.df_monitor.empty:
                        linhas_exibicao = [
                            f"Monitor => Nome={row['nome']}, Coleção={row['colecao']}, Número={row['numero']}"
                            for _, row in self.df_monitor.iterrows()
                        ]
                        self.window["-LIST_MONITOR-"].update(linhas_exibicao)
                        self.window["-MONITORAR-"].update(disabled=False)

            # Inicia monitoramento
            if event == "-MONITORAR-":
                if self.df_monitor.empty:
                    self.log("Nenhum CSV de monitor carregado.")
                else:
                    self.iniciar_monitoramento()

            # Botão "Pausar/Retomar"
            if event == "-PAUSAR-":
                self.monitor_paused = not self.monitor_paused
                if self.monitor_paused:
                    self.window["-PAUSAR-"].update("Retomar")
                    self.log("Monitoramento pausado.")
                else:
                    self.window["-PAUSAR-"].update("Pausar")
                    self.log("Monitoramento retomado.")

            # Botão "Gerar Gráfico"
            if event == "-GERAR-GRAFICO-":
                self.gerar_grafico()

            # Se o monitor estiver rodando e não estiver pausado, atualizamos cronômetro na interface
            if self.monitor_running and not self.monitor_paused:
                self.atualiza_cronometro()

        self.window.close()

    def raspagem_individual(self):
        """
        Faz raspagem única para as cartas em self.df_cards
        """
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
            self.progress_bar.Update(perc)

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
            from utils.dados import salvar_resultados_csv
            salvar_resultados_csv(resultados_locais, config.SAIDA_CSV)
            self.log("Raspagem finalizada. Resultados salvos.")
            self.mostra_resultados_tabela(resultados_locais)
        else:
            self.log("Nenhum resultado coletado na raspagem individual.")

    def iniciar_monitoramento(self):
        """
        Cria thread para monitorar as cartas sem travar a UI
        """
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
        """
        Loop infinito de monitoramento, rodando em thread separada
        """
        while self.monitor_running:
            # Se estiver pausado, aguarda um pouco e continua
            if self.monitor_paused:
                time.sleep(1)
                continue

            self.monitor_check_count += 1
            self.log(f"[MONITOR] Iniciando checagem #{self.monitor_check_count} ({len(self.df_monitor)} cartas).")

            # Faz a raspagem
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
                self.progress_bar.Update(perc)

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
                        # Se quiser, implementar variação de 10% (pode ler preco_inicial do CSV)
                    else:
                        self.log(f"[MONITOR] NM não encontrado para {nome}.")
                except Exception as e:
                    self.log(f"[MONITOR] ERRO monitor {nome}: {e}")

            scraper.fechar_driver()

            # Atualiza tabela com resultados
            if results_monitor:
                self.mostra_resultados_tabela(results_monitor)

            # Espera tempo
            tempo_base = config.MONITOR_INTERVALO_BASE
            variacao = config.MONITOR_VARIACAO
            espera = tempo_base + random.randint(0, variacao)
            # Zerar progresso e mostrar countdown
            self.progress_bar.Update(0)
            for seg in range(espera):
                if not self.monitor_running:
                    break
                if self.monitor_paused:
                    # Se pausado, congela contagem
                    time.sleep(1)
                    seg -= 1
                    continue
                restante = espera - seg
                self.window["-CRONOMETRO-"].update(self.segundos_para_minutos(restante))
                time.sleep(1)

        self.log("[MONITOR] Monitoramento finalizado.")
        self.window["-PAUSAR-"].update(disabled=True)
        self.window["-CRONOMETRO-"].update("00:00")

    def atualiza_cronometro(self):
        """
        Caso queira atualizar algo a cada loop do read()...
        (Não necessariamente precisamos se o countdown está no loop_monitor)
        """
        pass

    def parar_monitoramento(self):
        """
        Caso queira um botão para parar, podemos usar esse
        (Não solicitado explicitamente)
        """
        self.monitor_running = False

    def mostra_resultados_tabela(self, lista_resultados):
        """
        Preenche a sg.Table com dados
        """
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

    def gerar_grafico(self):
        """
        Gera um gráfico de exemplo (pode ser o histórico do SAIDA_CSV).
        """
        import matplotlib.pyplot as plt
        from io import BytesIO
        from utils.dados import pd, os

        if not os.path.exists(config.SAIDA_CSV):
            sg.popup("Nenhum CSV de resultados para gerar gráfico.")
            return

        df = pd.read_csv(config.SAIDA_CSV, sep=";", encoding="utf-8-sig")
        if df.empty:
            sg.popup("CSV de resultados vazio.")
            return
        if "preco" not in df.columns:
            sg.popup("CSV não contém a coluna 'preco'.")
            return

        df["preco"] = df["preco"].astype(float)
        plt.figure(figsize=(5,3))
        plt.plot(df["preco"], marker="o", label="Preço")
        plt.title("Tendência de Preços")
        plt.xlabel("Índice")
        plt.ylabel("Preço (R$)")
        plt.legend()

        buf = BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        self.window["-GRAFICO-"].update(data=buf.getvalue())

    def log(self, texto):
        """
        Mostra log no Output
        """
        self.window["-LOGS-"].print(texto)

    def segundos_para_minutos(self, s):
        """
        Converte número de segundos em mm:ss
        """
        mm = s // 60
        ss = s % 60
        return f"{mm:02}:{ss:02}"

def main():
    app = App()
    app.run()

if __name__ == "__main__":
    main()
