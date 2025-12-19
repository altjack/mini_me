#!/bin/bash
# ============================================================
# Daily Report - Script di avvio servizi locali
# ============================================================
# Questo script avvia tutti i servizi necessari per il backend:
# - PostgreSQL
# - Redis
# - nginx (reverse proxy)
# - Cloudflare Tunnel
# - Flask API
# ============================================================

set -e

# Colori per output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "============================================================"
echo "Daily Report - Avvio Servizi Locali"
echo "============================================================"
echo ""

# 1. PostgreSQL
echo -e "${YELLOW}[1/5]${NC} Avvio PostgreSQL..."
if brew services list | grep -q "postgresql@16.*started"; then
    echo -e "  ${GREEN}✓${NC} PostgreSQL già in esecuzione"
else
    brew services start postgresql@16
    sleep 2
    echo -e "  ${GREEN}✓${NC} PostgreSQL avviato"
fi

# 2. Redis
echo -e "${YELLOW}[2/5]${NC} Avvio Redis..."
if brew services list | grep -q "redis.*started"; then
    echo -e "  ${GREEN}✓${NC} Redis già in esecuzione"
else
    brew services start redis
    sleep 1
    echo -e "  ${GREEN}✓${NC} Redis avviato"
fi

# 3. nginx
echo -e "${YELLOW}[3/5]${NC} Avvio nginx..."
if brew services list | grep -q "nginx.*started"; then
    echo -e "  ${GREEN}✓${NC} nginx già in esecuzione"
else
    brew services start nginx
    sleep 1
    echo -e "  ${GREEN}✓${NC} nginx avviato"
fi

# 4. Cloudflare Tunnel
echo -e "${YELLOW}[4/5]${NC} Avvio Cloudflare Tunnel..."
if pgrep -f "cloudflared tunnel" > /dev/null; then
    echo -e "  ${GREEN}✓${NC} Cloudflare Tunnel già in esecuzione"
else
    cloudflared tunnel run daily-report-api > /tmp/cloudflared.log 2>&1 &
    sleep 3
    if pgrep -f "cloudflared tunnel" > /dev/null; then
        echo -e "  ${GREEN}✓${NC} Cloudflare Tunnel avviato"
    else
        echo -e "  ${RED}✗${NC} Errore avvio tunnel. Controlla /tmp/cloudflared.log"
    fi
fi

# 5. Flask API
echo -e "${YELLOW}[5/5]${NC} Avvio Flask API..."
if lsof -i :5001 > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Flask API già in esecuzione su porta 5001"
else
    cd "$PROJECT_DIR"
    source .venv/bin/activate
    python3 -m backend.api > /tmp/flask-api.log 2>&1 &
    sleep 2
    if lsof -i :5001 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Flask API avviata su porta 5001"
    else
        echo -e "  ${RED}✗${NC} Errore avvio API. Controlla /tmp/flask-api.log"
    fi
fi

echo ""
echo "============================================================"
echo -e "${GREEN}Tutti i servizi sono attivi!${NC}"
echo "============================================================"
echo ""
echo "Endpoints disponibili:"
echo "  - Locale:     http://localhost:5001/api/health"
echo "  - nginx:      http://localhost:8080/api/health"
echo "  - Pubblico:   https://api.bluetunnel.org/api/health"
echo ""
echo "Per fermare i servizi: ./scripts/stop-local-server.sh"
