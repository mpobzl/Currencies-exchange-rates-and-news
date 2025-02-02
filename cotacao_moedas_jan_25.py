import streamlit as st
import pandas as pd
import yfinance as yf
import pytz
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from datetime import datetime, timedelta
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor

# Função para obter dados do dólar em tempo real
def get_dollar_data_real_time():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    data = yf.download("USDBRL=X", start=start_date.date(), end=end_date.date(), progress=False)

    if not data.empty and 'Close' in data.columns:
        last_close = float(data['Close'].iloc[-1].item()) if len(data['Close']) > 0 else None
        previous_close = float(data['Close'].iloc[-2].item()) if len(data['Close']) > 1 else None
        timestamp = datetime.now(pytz.timezone("America/Sao_Paulo"))

        return {
            "last_close": last_close,
            "previous_close": previous_close,
            "timestamp": timestamp
        }
    return None

# Função para buscar manchetes
def fetch_headline(site_name, url, title_selector, subtitle_selector=None, translate_from="en"):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Buscar título
        title_element = soup.select_one(title_selector)
        title_text = title_element.get_text(strip=True) if title_element else "Título não encontrado"
        translated_title = GoogleTranslator(source=translate_from, target="pt").translate(title_text)

        # Buscar subtítulo (opcional)
        translated_subtitle = None
        if subtitle_selector:
            subtitle_element = soup.select_one(subtitle_selector)
            subtitle_text = subtitle_element.get_text(strip=True) if subtitle_element else ""
            if subtitle_text:
                translated_subtitle = GoogleTranslator(source=translate_from, target="pt").translate(subtitle_text)

        return {
            "site_name": site_name,
            "translated_title": translated_title,
            "translated_subtitle": translated_subtitle
        }
    except Exception as e:
        return {
            "site_name": site_name,
            "error": str(e)
        }

# Função para baixar dados de câmbio
def download_currency_data(tickers, start_date, end_date):
    data = []
    columns = []
    for ticker in tickers:
        currency_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if not currency_data.empty:
            data.append(currency_data['Close'])
            columns.append(ticker)
    if data:
        return pd.concat(data, axis=1, keys=columns)
    else:
        return pd.DataFrame()

# Configuração inicial
ticker_labels = {
    'USDBRL=X': 'Real (BRL)',
    'USDARS=X': 'Peso Argentino (ARS)',
    'USDMXN=X': 'Peso Mexicano (MXN)',
    'USDCNY=X': 'Yuan Chinês (CNY)',
    'USDINR=X': 'Rúpia Indiana (INR)',
}
tickers = list(ticker_labels.keys())

# Interface do Streamlit
st.title("Dashboard de Taxas de Câmbio")

# Exibir dados do dólar em tempo real
dollar_data = get_dollar_data_real_time()
if dollar_data:
    st.subheader("Cotação Atual do Dólar")
    st.markdown(
        f"""
        <p style='font-size:24px; color:#003366; font-weight:bold;'>
            Cotação Atual (USD/BRL): R$ {dollar_data['last_close']:.2f} - Fonte: Yahoo Finance
        </p>
        """,
        unsafe_allow_html=True
    )
    st.write(f"Hora da coleta: {dollar_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} (Horário de Brasília)")
    if dollar_data['previous_close'] is not None:
        variation = dollar_data['last_close'] - dollar_data['previous_close']
        percentage_change = (variation / dollar_data['previous_close']) * 100
        direction = "↑" if variation > 0 else "↓"
        st.write(f"Variação: {direction} R$ {variation:.2f} ({percentage_change:.2f}%)")
    else:
        st.write("Não foi possível calcular a variação.")
else:
    st.write("Dados do dólar não estão disponíveis no momento.")

# Seleção de moedas
selected_tickers = st.multiselect("Selecione as moedas", tickers, default=tickers)
selected_labels = [ticker_labels[ticker] for ticker in selected_tickers]

# Seleção de linha do tempo
start_date = st.date_input("Data de início", pd.to_datetime('2023-01-01'))
end_date = st.date_input("Data de término", pd.Timestamp.today())

# Função para exibir dados e gráficos
def display_currency_data():
    if selected_tickers:
        try:
            currency_data = download_currency_data(selected_tickers, start_date, end_date)
            if currency_data.empty:
                st.write("Nenhum dado disponível para o intervalo selecionado.")
                return

            currency_data.columns = selected_labels

            # Garantir que os índices estejam no formato datetime
            currency_data.index = pd.to_datetime(currency_data.index)

            # Trabalhar com os dados diários
            processed_data = currency_data

            # Gráfico Interativo com Plotly
            st.subheader("Gráfico de Linha Interativo: Valores Selecionados")
            if not processed_data.empty:
                fig = go.Figure()

                # Adicionar moedas no eixo principal
                for column in processed_data.columns:
                    if column != 'Peso Argentino (ARS)':
                        fig.add_trace(
                            go.Scatter(
                                x=processed_data.index,
                                y=processed_data[column],
                                mode='lines',
                                name=column,
                                yaxis="y1"
                            )
                        )

                # Adicionar Peso Argentino (ARS) no eixo secundário
                if 'Peso Argentino (ARS)' in processed_data.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=processed_data.index,
                            y=processed_data['Peso Argentino (ARS)'],
                            mode='lines',
                            name='Peso Argentino (ARS)',
                            yaxis="y2"
                        )
                    )

                # Configuração do layout do gráfico
                fig.update_layout(
                    title="Taxas de Câmbio Diárias",
                    xaxis=dict(title="Data"),
                    yaxis=dict(
                        title="Taxas de Câmbio",
                        side="left"
                    ),
                    yaxis2=dict(
                        title="Peso Argentino (ARS)",
                        overlaying="y",
                        side="right",
                        showgrid=False  # Remover as linhas de grade do eixo secundário
                    ),
                    legend=dict(
                        title="Moedas",
                        x=0,
                        y=1
                    ),
                    hovermode="x unified",  # Mostrar valores ao passar o cursor
                    template="plotly_white"
                )

                st.plotly_chart(fig)
            else:
                st.write("Nenhum dado disponível para o gráfico.")
        except Exception as e:
            st.write("Erro ao baixar os dados: ", str(e))
    else:
        st.write("Por favor, selecione pelo menos uma moeda.")

# Exibir dados
display_currency_data()

# Lista de sites para buscar manchetes
sites = [
    {
        "name": "ABC News",
        "url": "https://abcnews.go.com/",
        "title_selector": "h2.PFoxV.eBpQD.rcQBv.bQtjQ.lQUdN.GpQCA.mAkiF.FvMyr.WvoqU.nPLLM.tuAKv.ZfQkn.GdxUi",
        "subtitle_selector": None
    },
    {
        "name": "Capital and Main",
        "url": "https://capitalandmain.com",
        "title_selector": "h2",
        "subtitle_selector": "p"
    },
    {
        "name": "CNN Business",
        "url": "https://www.cnn.com/business",
        "title_selector": "span.container__headline-text",
        "subtitle_selector": None
    },
    {
        "name": "Europe - BBC Business",
        "url": "https://www.bbc.com/news/business",
        "title_selector": "h2[data-testid='card-headline']",
        "subtitle_selector": "p[data-testid='card-description']"
    },
    {
        "name": "China - South China Morning Post",
        "url": "https://www.scmp.com",
        "title_selector": "span[data-qa='ContentHeadline-Headline']",
        "subtitle_selector": "h3[data-qa='ContentSummary-ContainerWithTag']"
    },
    {
        "name": "Argentina - Clarín",
        "url": "https://www.clarin.com/",
        "title_selector": "h2.title",
        "subtitle_selector": "div.bottomSummary p.bajada",
        "translate_from": "es"
    }
]

# Buscar manchetes de forma paralela
st.subheader("Manchetes Internacionais")
with ThreadPoolExecutor() as executor:
    results = executor.map(
        lambda site: fetch_headline(
            site_name=site["name"],
            url=site["url"],
            title_selector=site["title_selector"],
            subtitle_selector=site.get("subtitle_selector"),
            translate_from=site.get("translate_from", "en")
        ),
        sites
    )

for result in results:
    if "error" in result:
        st.write(f"Erro ao buscar manchetes de {result['site_name']}: {result['error']}")
    else:
        st.write(f"### Manchete de {result['site_name']} ###")
        st.write(f"**Título:** {result['translated_title']}")
        if result['translated_subtitle']:
            st.write(f"**Subtítulo:** {result['translated_subtitle']}")
        st.write("\n")
