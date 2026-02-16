import time
import requests
from datetime import datetime, timezone

from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go


REFRESH_SECONDS = 60          # precio actual
HIST_REFRESH_SECONDS = 300    # histórico (cada 5 min)


BINANCE_BASE = "https://data-api.binance.vision"  # :contentReference[oaicite:3]{index=3}


COINS = [
    {"label": "Bitcoin (BTC)", "value": "BTCUSDT"},
    {"label": "Ethereum (ETH)", "value": "ETHUSDT"},
    {"label": "Solana (SOL)", "value": "SOLUSDT"},
    {"label": "Dogecoin (DOGE)", "value": "DOGEUSDT"},
    {"label": "Cardano (ADA)", "value": "ADAUSDT"},
]

DAYS_OPTIONS = [
    {"label": "1 día", "value": 1},
    {"label": "7 días", "value": 7},
    {"label": "30 días", "value": 30},
]

DASHBOARD_DESC = """


Este dashboard fue desarrollado con Python utilizando Dash para visualizar información financiera en tiempo casi real
desde una API pública. En el primer tablero se muestra el precio actual de una criptomoneda seleccionada, con
actualización automática y un contador regresivo. En el segundo tablero se presenta el histórico del precio para
analizar tendencias en distintas ventanas de tiempo. Técnicamente, el proyecto integra consumo de APIs externas,
procesamiento de JSON y actualización reactiva de componentes mediante callbacks.
"""

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "dash-binance-demo/1.0"
}

_price_cache = {}   # symbol -> {"ts": float, "price": float}
_klines_cache = {}  # (symbol, days) -> {"ts": float, "data": (xs, ys)}

def _now():
    return time.time()

def get_price(symbol: str, ttl: int = 20):
    c = _price_cache.get(symbol)
    if c and (_now() - c["ts"] < ttl):
        return c["price"], ""

    url = f"{BINANCE_BASE}/api/v3/ticker/price"
    params = {"symbol": symbol}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return None, f"Binance HTTP {r.status_code}: {r.text[:200]}"
        data = r.json()
        price = float(data["price"])
        _price_cache[symbol] = {"ts": _now(), "price": price}
        return price, ""
    except Exception as e:

        if c:
            return c["price"], f"Error consultando Binance ({type(e).__name__}). Mostrando último valor."
        return None, f"Error consultando Binance ({type(e).__name__})."

def get_klines(symbol: str, days: int, ttl: int = 120):
    """
    Klines: /api/v3/klines
    Para 1d y 7d usamos 1h. Para 30d usamos 4h (reduce puntos).
    """
    key = (symbol, days)
    c = _klines_cache.get(key)
    if c and (_now() - c["ts"] < ttl):
        return c["data"], ""

    if days <= 7:
        interval = "1h"
        limit = min(1000, days * 24)      # 24 pts por día
    else:
        interval = "4h"
        limit = min(1000, days * 6)       # 6 pts por día

    url = f"{BINANCE_BASE}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None, f"Binance HTTP {r.status_code}: {r.text[:200]}"

        klines = r.json()
        if not klines:
            return None, "Sin datos de klines."

        # kline format:
        # [
        #   [
        #     0 Open time (ms),
        #     1 Open,
        #     2 High,
        #     3 Low,
        #     4 Close,
        #     5 Volume,
        #     ...
        #   ],
        #   ...
        # ]
        xs = [datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc) for k in klines]
        ys = [float(k[4]) for k in klines]  # Close

        _klines_cache[key] = {"ts": _now(), "data": (xs, ys)}
        return (xs, ys), ""
    except Exception as e:
        if c:
            return c["data"], f"Error consultando klines ({type(e).__name__}). Mostrando cache."
        return None, f"Error consultando klines ({type(e).__name__})."


app = Dash(__name__)
server = app.server  # necesario para gunicorn en Render

tab1_layout = html.Div([
    html.H3("Precio actual (USDT)"),

    dcc.Dropdown(
        id="symbol-dropdown",
        options=COINS,
        value="BTCUSDT",
        clearable=False,
        style={"width": "320px"}
    ),

    html.H2(id="precio", style={"marginTop": "12px"}),
    html.Div("Siguiente actualización en:"),
    html.H2(id="countdown", style={"marginTop": "6px"}),

    html.Pre(id="error-precio", style={"color": "crimson", "whiteSpace": "pre-wrap"}),

    dcc.Interval(id="tick-1s", interval=1000, n_intervals=0),
    dcc.Interval(id="tick-price", interval=REFRESH_SECONDS * 1000, n_intervals=0),
])

tab2_layout = html.Div([
    html.H3("Histórico (Close)"),

    html.Div([
        html.Div([
            html.Label("Par (USDT)"),
            dcc.Dropdown(
                id="symbol-hist",
                options=COINS,
                value="BTCUSDT",
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
        html.H1("Dashboard Crypto (Binance + Dash)"),

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


@app.callback(
    Output("precio", "children"),
    Output("error-precio", "children"),
    Input("tick-price", "n_intervals"),
    Input("symbol-dropdown", "value"),
)
def actualizar_precio(_, symbol):
    price, err = get_price(symbol)
    if price is None:
        return "—", err
    return f"{symbol} = {price:,.6f} USDT", err

@app.callback(
    Output("countdown", "children"),
    Input("tick-1s", "n_intervals"),
)
def actualizar_countdown(ticks):
    elapsed = ticks % REFRESH_SECONDS
    remaining = REFRESH_SECONDS - elapsed
    return f"{remaining}s"

@app.callback(
    Output("hist-graph", "figure"),
    Output("error-hist", "children"),
    Input("symbol-hist", "value"),
    Input("days", "value"),
    Input("tick-hist", "n_intervals"),
)
def actualizar_historico(symbol, days, _):
    fig = go.Figure()
    data, err = get_klines(symbol, int(days))

    if data is None:
        fig.update_layout(
            title=f"{symbol} - últimos {days} días",
            xaxis_title="Tiempo",
            yaxis_title="Close (USDT)"
        )
        return fig, err

    x, y = data
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=symbol))
    fig.update_layout(
        title=f"{symbol} - últimos {days} días",
        xaxis_title="Tiempo (UTC)",
        yaxis_title="Close (USDT)"
    )
    return fig, err

if __name__ == "__main__":
    app.run(debug=True)
