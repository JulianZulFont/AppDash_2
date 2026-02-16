import requests
from datetime import datetime, timezone

from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go

# ---------- Config ----------
REFRESH_SECONDS = 60
HIST_REFRESH_SECONDS = 300

COINS = [
    {"label": "Bitcoin (BTC)", "value": "bitcoin"},
    {"label": "Ethereum (ETH)", "value": "ethereum"},
    {"label": "Solana (SOL)", "value": "solana"},
    {"label": "Dogecoin (DOGE)", "value": "dogecoin"},
    {"label": "Cardano (ADA)", "value": "cardano"},
]

DAYS_OPTIONS = [
    {"label": "1 día", "value": 1},
    {"label": "7 días", "value": 7},
    {"label": "30 días", "value": 30},
]

# ---------- Texto (Descripción del dashboard) ----------
DASHBOARD_DESC = """
Dashboard para la clase número 4 del curso de Visualización y Storytelling de Datos

Este dashboard fue desarrollado con Python utilizando la librería Dash con el objetivo de visualizar información
financiera en tiempo casi real proveniente de la API pública de CoinGecko. La aplicación permite monitorear el
comportamiento de distintas criptomonedas mediante una interfaz interactiva organizada en dos tableros principales.

El primer tablero muestra el precio actual de una criptomoneda seleccionada por el usuario, el cual se actualiza
automáticamente cada cierto intervalo de tiempo. Adicionalmente, se incluye un contador regresivo que indica cuándo
se realizará la siguiente actualización, lo que permite observar la dinámica de los datos en tiempo real y entender
el funcionamiento de sistemas basados en consultas periódicas a servicios externos.

El segundo tablero presenta el comportamiento histórico del precio de la criptomoneda seleccionada, permitiendo
visualizar su evolución en diferentes ventanas temporales. Esta visualización facilita el análisis de tendencias,
variaciones y patrones en los precios, lo cual es fundamental en aplicaciones de análisis financiero y toma de
decisiones basada en datos.

Desde el punto de vista técnico, el proyecto integra consultas HTTP a una API externa, procesamiento de datos en
formato JSON y actualización dinámica de componentes mediante callbacks reactivos. El desarrollo de este dashboard
permitió comprender la arquitectura de aplicaciones interactivas basadas en datos, el manejo de información en tiempo
real y la integración de servicios externos dentro de aplicaciones analíticas.
"""

# ---------- CoinGecko API ----------
def obtener_precio_crypto(coin_id):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd"}

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return float(data[coin_id]["usd"])
    except:
        return None


def obtener_historico(coin_id, days):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days}

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        prices = data.get("prices", [])

        xs = [datetime.fromtimestamp(p[0] / 1000, tz=timezone.utc) for p in prices]
        ys = [float(p[1]) for p in prices]

        return xs, ys
    except:
        return None


# ---------- Dash ----------
app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server

app.layout = html.Div(
    style={"fontFamily": "Arial", "maxWidth": "1100px", "margin": "24px auto"},
    children=[
        html.H1("Dashboard Crypto (CoinGecko + Dash)"),

        # ✅ Descripción del dashboard
        html.Details(
            open=False,
            children=[
                html.Summary("¿Qué significa este dashboard? (Descripción)"),
                dcc.Markdown(DASHBOARD_DESC, style={"marginTop": "10px", "lineHeight": "1.5"}),
            ],
            style={
                "background": "#f6f6f6",
                "padding": "12px 14px",
                "borderRadius": "10px",
                "border": "1px solid #e5e5e5",
                "marginBottom": "18px",
            },
        ),

        dcc.Tabs(id="tabs", value="tab-1", children=[
            dcc.Tab(label="Precio actual", value="tab-1"),
            dcc.Tab(label="Histórico", value="tab-2"),
        ]),

        html.Div(id="contenido")
    ]
)


# ---------- Layouts ----------
def layout_tab1():
    return html.Div([
        html.H3("Precio actual (USD)"),

        dcc.Dropdown(
            id="coin-dropdown",
            options=COINS,
            value="bitcoin",
            clearable=False,
            style={"width": "300px"}
        ),

        html.H2(id="precio", style={"marginTop": "12px"}),

        html.Div("Siguiente actualización en:"),
        html.H2(id="countdown"),

        dcc.Interval(id="tick-1s", interval=1000, n_intervals=0),
        dcc.Interval(id="tick-60s", interval=REFRESH_SECONDS * 1000, n_intervals=0),
    ])


def layout_tab2():
    return html.Div([
        html.H3("Histórico de precio"),

        html.Div([
            html.Div([
                html.Label("Moneda"),
                dcc.Dropdown(
                    id="coin-hist",
                    options=COINS,
                    value="bitcoin",
                    clearable=False,
                    style={"width": "250px"}
                ),
            ]),
            html.Div([
                html.Label("Periodo"),
                dcc.Dropdown(
                    id="days",
                    options=DAYS_OPTIONS,
                    value=7,
                    clearable=False,
                    style={"width": "150px"}
                ),
            ]),
        ], style={"display": "flex", "gap": "20px"}),

        dcc.Graph(id="hist-graph"),
        dcc.Interval(id="tick-hist", interval=HIST_REFRESH_SECONDS * 1000, n_intervals=0),
    ])


@app.callback(Output("contenido", "children"), Input("tabs", "value"))
def render_tab(tab):
    return layout_tab1() if tab == "tab-1" else layout_tab2()


# ---------- Precio actual ----------
@app.callback(
    Output("precio", "children"),
    Input("tick-60s", "n_intervals"),
    Input("coin-dropdown", "value"),
)
def actualizar_precio(_, coin):
    precio = obtener_precio_crypto(coin)
    if precio is None:
        return "No se pudo obtener el precio"
    return f"{coin.upper()} = ${precio:,.2f}"


@app.callback(
    Output("countdown", "children"),
    Input("tick-1s", "n_intervals"),
)
def actualizar_countdown(ticks):
    elapsed = ticks % REFRESH_SECONDS
    remaining = REFRESH_SECONDS - elapsed
    return f"{remaining}s"


# ---------- Histórico ----------
@app.callback(
    Output("hist-graph", "figure"),
    Input("coin-hist", "value"),
    Input("days", "value"),
    Input("tick-hist", "n_intervals"),
)
def actualizar_historico(coin, days, _):
    fig = go.Figure()
    hist = obtener_historico(coin, days)

    if hist:
        x, y = hist
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=coin.upper()))

    fig.update_layout(
        title=f"{coin.upper()} - últimos {days} días",
        xaxis_title="Tiempo",
        yaxis_title="Precio USD"
    )
    return fig


if __name__ == "__main__":
    app.run(debug=True)
