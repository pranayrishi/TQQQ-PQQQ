# Automated Systematic Trading System

A fully automated trading system for leveraged NASDAQ ETFs (TQQQ/SQQQ) based on trend-following and mean-reversion strategies.

## Overview

This system implements a systematic trading approach using:
- **7 Trading Strategies**: MA Breakout, Momentum, Mean Reversion, and Velocity Filter
- **Automated Execution**: Trades in the last 10 minutes before market close
- **Risk Management**: Position limits, daily loss limits, and circuit breakers
- **Comprehensive Backtesting**: 40+ years of historical data support

### Trading Universe
- **TQQQ**: 3x Leveraged Long NASDAQ-100
- **SQQQ**: 3x Leveraged Short NASDAQ-100
- **NDX**: NASDAQ-100 Index (signals only)

## Quick Start

### 1. Setup

```bash
# Clone and enter directory
cd trading_system

# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh

# Activate virtual environment
source venv/bin/activate
```

### 2. Configure API Keys

Edit `config/credentials.yaml`:

```yaml
alpaca_api_key: "your_alpaca_api_key"
alpaca_api_secret: "your_alpaca_secret"
```

### 3. Run Backtest

```bash
python scripts/run_backtest.py --initial-capital 100000
```

### 4. Start Scheduled Trading

```bash
python -m src.main
```

To verify the full workflow against the configured account without submitting
orders, run:

```bash
python -m src.main --run-once --dry-run --force
```

The included GitHub Actions workflow also enforces `--dry-run`; it exercises
the remote data, strategy, and account paths without submitting orders.

## Project Structure

```
trading_system/
├── config/
│   ├── settings.yaml          # Main configuration
│   └── credentials.yaml       # API keys (gitignored)
├── src/
│   ├── data/                  # Data infrastructure
│   ├── strategies/            # Trading strategies
│   ├── backtest/              # Backtesting engine
│   ├── execution/             # Order execution
│   ├── brokers/               # Broker integrations
│   ├── monitoring/            # Alerts and health checks
│   ├── visualization/         # Charts and reports
│   └── utils/                 # Utilities
├── tests/                     # Unit and integration tests
├── scripts/                   # Helper scripts
└── data/                      # Data storage
```

## Strategies

| Strategy | Type | Weight | Description |
|----------|------|--------|-------------|
| MA Breakout Long | Trend Following | 25% | Long when price > 50 MA and 250 MA |
| MA Breakout Short | Trend Following | 15% | Short when price < 50 MA and 250 MA |
| Momentum Long | Trend Following | 20% | Long on positive 6-month momentum |
| Momentum Short | Trend Following | 10% | Short on negative momentum |
| Mean Reversion Long | Mean Reversion | 10% | Buy dips in uptrends |
| Mean Reversion Short | Mean Reversion | 10% | Sell rallies in downtrends |
| Velocity Filter | Risk Management | 10% | Scale positions by trend velocity |

## Configuration

### Main Settings (`config/settings.yaml`)

```yaml
system:
  timezone: "US/Eastern"
  log_level: "INFO"

execution:
  execution_window_start: "15:50"
  execution_window_end: "16:00"

risk:
  max_position_pct: 1.0
  max_daily_loss_pct: 0.10
  max_order_value: 1000000

brokers:
  alpaca:
    paper: true  # Set to false for live trading
```

## API Requirements

### yfinance
- Used for adjusted historical data for NDX, TQQQ, and SQQQ
- No separate market-data API key is required
- Intended for personal-use access to Yahoo Finance data

### Alpaca
- Used for paper/live trading and current IEX market snapshots
- Supplies the latest quote, trade, minute bar, daily bar, and prior daily bar
- Free paper trading account
- Sign up at: https://alpaca.markets

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Deployment

### Docker

```bash
# Build image
docker build -t trading-system .

# Run container
docker run -d \
  -e ALPACA_API_KEY=your_key \
  -e ALPACA_API_SECRET=your_secret \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  trading-system
```

### Systemd Service

```bash
# Copy service file
sudo cp scripts/trading-system.service /etc/systemd/system/

# Enable and start
sudo systemctl enable trading-system
sudo systemctl start trading-system
```

## Safety Features

1. **Paper Trading Default**: System defaults to paper trading mode
2. **Position Limits**: Never exceeds 100% allocation
3. **Daily Loss Limit**: Halts trading if daily loss exceeds 10%
4. **Order Validation**: All orders validated before submission
5. **Health Monitoring**: Regular system health checks
6. **Alert System**: SMS/Email notifications for errors

## Expected Performance

Based on backtesting:
- **Expected Annual Return**: ~40%
- **Maximum Drawdown**: 30-35%
- **Trading Frequency**: 1-2 trades per week

**DISCLAIMER**: Past performance does not guarantee future results. This system handles real money - use at your own risk.

## License

Private/Proprietary

## Support

For issues, check the logs in `logs/trading.log`.
