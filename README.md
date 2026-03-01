# Quant Rotational API v2

Motor cuantitativo rotacional con FastAPI. Backend para el dashboard en Vercel.

## Estructura

```
quant-api/
├── app/
│   ├── main.py                  # Entry point FastAPI
│   ├── routers/
│   │   ├── signal.py            # GET /api/signal
│   │   └── backtest.py          # POST /api/backtest, /analyze, /stress
│   ├── services/
│   │   ├── core.py              # Motor cuantitativo central
│   │   ├── backtest.py          # Backtesting vectorizado
│   │   └── telegram.py          # Notificaciones Telegram
│   └── models/
│       └── schemas.py           # Modelos Pydantic
├── requirements.txt
├── railway.toml                 # Config Railway deploy
├── .env.example
└── .github/workflows/
    └── daily_signal.yml         # GitHub Actions (señal diaria)
```

## Setup local

```bash
# 1. Clonar e instalar
git clone https://github.com/tu-usuario/quant-api
cd quant-api
pip install -r requirements.txt

# 2. Variables de entorno
cp .env.example .env
# Editar .env con tus tokens de Telegram

# 3. Correr en desarrollo
uvicorn app.main:app --reload --port 8000
```

Documentación interactiva: http://localhost:8000/docs

## Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/api/signal` | Señal rotacional actual |
| POST | `/api/signal/telegram` | Enviar señal a Telegram |
| POST | `/api/backtest` | Backtest completo |
| GET | `/api/backtest/scenarios` | Escenarios stress disponibles |
| GET | `/api/backtest/stress/{key}` | Stress test histórico |
| POST | `/api/backtest/analyze` | Analizar activo candidato |

### Ejemplos

```bash
# Señal actual
curl http://localhost:8000/api/signal

# Señal con tickers personalizados
curl "http://localhost:8000/api/signal?tickers=SPY,QQQ,BTC-USD,ETH-USD,GLD,SOL-USD"

# Backtest desde 2020
curl -X POST http://localhost:8000/api/backtest \
  -H "Content-Type: application/json" \
  -d '{"start": "2020-01-01", "initial_capital": 10000}'

# Analizar SOL como candidato
curl -X POST http://localhost:8000/api/backtest/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "SOL-USD"}'

# Stress test COVID
curl http://localhost:8000/api/backtest/stress/covid_2020

# Enviar señal a Telegram
curl -X POST http://localhost:8000/api/signal/telegram \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Deploy en Railway

1. Pusheá el código a GitHub
2. Entrá a [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Seleccioná el repo
4. En **Variables**, agregá:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Railway detecta `railway.toml` y hace el deploy automático

Railway URL de ejemplo: `https://quant-api-production.up.railway.app`

## Variables de entorno en GitHub Actions

En tu repo de GitHub → Settings → Secrets → Actions:
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `API_BASE_URL` → URL de Railway (ej: `https://quant-api-production.up.railway.app`)

## Agregar activos nuevos

Para agregar un activo (ej: SOL-USD):

1. Agregarlo a `SLEEVE_MAP` en `app/services/core.py`
2. Si es crypto, definir su split en `CRYPTO_SPLIT`
3. Llamar al endpoint `/api/signal?tickers=SPY,QQQ,BTC-USD,ETH-USD,GLD,SOL-USD`

No requiere cambios en el código de routers ni schemas.

## Conectar con el frontend (Vercel)

En el frontend Next.js, usar la URL de Railway como variable de entorno:

```env
NEXT_PUBLIC_API_URL=https://quant-api-production.up.railway.app
```

```js
// Ejemplo de fetch en Next.js
const signal = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/signal`)
  .then(r => r.json())
```
