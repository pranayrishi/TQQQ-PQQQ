#!/bin/bash
# Setup script for the Automated Trading System

set -e

echo "========================================"
echo "Automated Trading System Setup"
echo "========================================"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

echo "Python version: $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create directory structure
echo ""
echo "Creating directory structure..."
mkdir -p data/cache
mkdir -p data/backtest_results
mkdir -p data/trade_logs
mkdir -p logs

# Copy credentials template if needed
if [ ! -f config/credentials.yaml ]; then
    echo ""
    echo "Creating credentials file from template..."
    cp config/credentials.yaml.template config/credentials.yaml
    echo "IMPORTANT: Edit config/credentials.yaml with your API keys!"
fi

# Set permissions
chmod +x scripts/*.py
chmod +x scripts/*.sh

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Edit config/credentials.yaml with your API keys"
echo "3. Run a backtest: python scripts/run_backtest.py"
echo "4. Start the scheduler: python -m src.main"
echo ""
