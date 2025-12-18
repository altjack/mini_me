#!/bin/bash
# Script per rimuovere file temporanei e log

echo "🧹 Pulizia file temporanei..."

# Rimuovi log files dalla root (se presenti)
rm -f *.log
echo "  ✓ Log files root rimossi"

# Rimuovi cache Python
rm -rf __pycache__
rm -rf agent/__pycache__
rm -rf ga4_extraction/__pycache__
rm -rf tests/__pycache__
rm -rf scripts/__pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "  ✓ Cache Python rimossa"

# Rimuovi file .pyc
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
echo "  ✓ File .pyc/.pyo rimossi"

# Opzionale: pulizia log directory (commenta se vuoi mantenere i log)
# rm -rf logs/*.log
# echo "  ✓ Log directory pulita"

echo ""
echo "✅ Pulizia completata!"

