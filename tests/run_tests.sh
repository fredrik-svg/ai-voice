#!/bin/bash
# Script för att köra MQTT-testerna
# Script to run MQTT tests

set -e

# Färger för output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Gå till repository root
cd "$(dirname "$0")/.."

# Aktivera virtuell miljö om den finns
if [ -f "venv/bin/activate" ]; then
    echo -e "${GREEN}Aktiverar virtuell miljö...${NC}"
    source venv/bin/activate
else
    echo -e "${RED}Fel: Virtuell miljö hittades inte i venv/bin/activate${NC}"
    echo -e "${YELLOW}Kör './scripts/install_deps.sh' först för att skapa den.${NC}"
    exit 1
fi

echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}Kör MQTT-tester (Running MQTT tests)${NC}"
echo -e "${GREEN}==================================================================${NC}"
echo ""

# Kontrollera att Mosquitto körs
if ! pgrep -x "mosquitto" > /dev/null; then
    echo -e "${YELLOW}Varning: Mosquitto verkar inte köra.${NC}"
    echo -e "${YELLOW}Försöker starta Mosquitto...${NC}"
    
    if command -v systemctl &> /dev/null; then
        sudo systemctl start mosquitto || echo -e "${YELLOW}Kunde inte starta Mosquitto automatiskt. Starta det manuellt.${NC}"
    else
        echo -e "${YELLOW}Starta Mosquitto manuellt innan testerna körs.${NC}"
    fi
    echo ""
fi

# Kör testerna
PYTHONPATH=. python3 tests/test_mqtt_client.py "$@"

echo ""
echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}Testerna slutförda! (Tests completed!)${NC}"
echo -e "${GREEN}==================================================================${NC}"
