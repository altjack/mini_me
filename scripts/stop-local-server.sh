#!/bin/bash
# ============================================================
# Daily Report - Script di arresto servizi locali
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================================"
echo "Daily Report - Arresto Servizi Locali"
echo "============================================================"
echo ""

# 1. Flask API
echo -e "${YELLOW}[1/5]${NC} Arresto Flask API..."
pkill -f "python3 -m backend.api" 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} Flask API fermata"

# 2. Cloudflare Tunnel
echo -e "${YELLOW}[2/5]${NC} Arresto Cloudflare Tunnel..."
pkill -f "cloudflared tunnel" 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} Cloudflare Tunnel fermato"

# 3. nginx (opzionale, mantieni attivo)
echo -e "${YELLOW}[3/5]${NC} nginx..."
echo -e "  ${GREEN}→${NC} nginx lasciato attivo (brew services stop nginx per fermarlo)"

# 4. Redis (opzionale, mantieni attivo)
echo -e "${YELLOW}[4/5]${NC} Redis..."
echo -e "  ${GREEN}→${NC} Redis lasciato attivo (brew services stop redis per fermarlo)"

# 5. PostgreSQL (opzionale, mantieni attivo)
echo -e "${YELLOW}[5/5]${NC} PostgreSQL..."
echo -e "  ${GREEN}→${NC} PostgreSQL lasciato attivo (brew services stop postgresql@16 per fermarlo)"

echo ""
echo "============================================================"
echo -e "${GREEN}Servizi principali fermati!${NC}"
echo "============================================================"
echo ""
echo "Nota: PostgreSQL, Redis e nginx sono rimasti attivi."
echo "Per fermare tutto: brew services stop --all"
