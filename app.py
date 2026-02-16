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

DASHBOARD_DESC = """
Este dashboard fue desarrollado con Python utilizando Dash para visualizar información financiera en tiempo casi real
desde la API pública de CoinGecko. En el primer tablero se muestra el precio actual de una criptomoneda seleccionada,
con actualización automática y un contador regresivo. En el segundo tablero se presenta el histórico del precio para
analizar tendencias en distintas ventanas de tiempo. Técnicamente, el proyecto integra consumo de APIs externas,
procesamiento de JSON y actualización reactiva de componentes mediante callbacks.
"""

# ---------- CoinGecko API (con User-Agent + error visible) ----------
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "dash-coingecko-demo/1.0"
}

def obtener_precio_crypto(coin_id):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd"}

    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    # Si CoinGecko devuelve 403/429, lo mostramos
    if r.status_code != 200:
        return None, f"CoinGecko HTTP {r.status_code}: {r.text[:200]}"

    data = r.json()
    try:
        return float(data[coin_id]["usd"]), ""
    except Exception:
        return None, "Respuesta JSON inesperada"

def obtener_historico(coin_id, days):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days}

    r = requests.get(url, params=params, headers=HEADERS, timeout=25)
    if r.status_code != 200:
        return None, f"CoinGecko HTTP {r.status_code}: {r.text[:200]}"

    data = r.json()
    prices = data.get("prices", [])
    if not prices:
        return None, "Sin datos en 'prices'"

    xs = [datetime.fromtimestamp(p[0] / 1000, tz=timezone.utc) for p in prices]
    ys = [float(p[1]) for p in prices]
    return (xs, ys), ""

# ---------- Dash ----------
app = Dash(__name__)
server = app.server  # para Render + gunicorn

tab1_layout = html.Div([
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
    html.H2(id="countdown", style={"marginTop": "6px"}),

    html.Pre(id="error-precio", style={"color": "crimson", "whiteSpace": "pre-wrap"}),

    # Intervalos SIEMPRE presentes (no dinámicos)
    dcc.Interval(id="tick-1s", interval=1000, n_intervals=0),
    dcc.Interval(id="tick-60s", interval=REFRESH_SECONDS * 1000, n_intervals=0),
])

tab2_layout = html.Div([
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
    html.Pre(id="error-hist", style={"color": "crimson", "whiteSpace": "pre-wrap"}),

    dcc.Interval(id="tick-hist", interval=HIST_REFRESH_SECONDS * 1000, n_intervals=0),
])

app.layout = html.Div(
    style={"fontFamily": "Arial", "maxWidth": "1100px", "margin": "24px auto"},
    children=[
        html.H1("Dashboard Crypto (CoinGecko + Dash)"),

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

        dcc.Tabs(children=[
            dcc.Tab(label="Precio actual", children=tab1_layout),
            dcc.Tab(label="Histórico", children=tab2_layout),
        ]),
    ],
)

# ---------- Callbacks Tab 1 ----------
@app.callback(
    Output("precio", "children"),
    Output("error-precio", "children"),
    Input("tick-60s", "n_intervals"),
    Input("coin-dropdown", "value"),
)
def actualizar_precio(_, coin):
    precio, err = obtener_precio_crypto(coin)
    if precio is None:
        return "—", err or "No se pudo obtener el precio"
    return f"{coin.upper()} = ${precio:,.2f}", ""

@app.callback(
    Output("countdown", "children"),
    Input("tick-1s", "n_intervals"),
)
def actualizar_countdown(ticks):
    elapsed = ticks % REFRESH_SECONDS
    remaining = REFRESH_SECONDS - elapsed
    return f"{remaining}s"

# ---------- Callbacks Tab 2 ----------
@app.callback(
    Output("hist-graph", "figure"),
    Output("error-hist", "children"),
    Input("coin-hist", "value"),
    Input("days", "value"),
    Input("tick-hist", "n_intervals"),
)
def actualizar_historico(coin, days, _):
    fig = go.Figure()
    res, err = obtener_historico(coin, int(days))

    if res is None:
        fig.update_layout(
            title=f"{coin.upper()} - últimos {days} días",
            xaxis_title="Tiempo",
            yaxis_title="Precio USD"
        )
        return fig, err or "No se pudo cargar histórico"

    x, y = res
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=coin.upper()))
    fig.update_layout(
        title=f"{coin.upper()} - últimos {days} días",
        xaxis_title="Tiempo (UTC)",
        yaxis_title="Precio USD"
    )
    return fig, ""

if __name__ == "__main__":
    app.run(debug=True)

