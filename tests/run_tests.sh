#!/bin/bash
# Script för att köra MQTT-testerna
# Script to run MQTT tests

set -e

# Färger för output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}Kör MQTT-tester (Running MQTT tests)${NC}"
echo -e "${GREEN}==================================================================${NC}"
echo ""

# Check if config.yaml exists and determine broker type
cd "$(dirname "$0")/.."
if [ -f config.yaml ]; then
    MQTT_HOST=$(grep -E "^\s*host:" config.yaml | awk '{print $2}' | tr -d '"' | tr -d "'")
    
    if [[ "$MQTT_HOST" == "localhost" ]] || [[ "$MQTT_HOST" == "127.0.0.1" ]]; then
        echo -e "${BLUE}Info: config.yaml använder localhost MQTT broker${NC}"
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
    elif [[ "$MQTT_HOST" == YOUR_* ]]; then
        echo -e "${YELLOW}Varning: config.yaml har inte konfigurerats med riktig MQTT broker.${NC}"
        echo -e "${YELLOW}Testerna kommer använda localhost som standard.${NC}"
        echo ""
    else
        echo -e "${BLUE}Info: Använder MQTT broker från config.yaml: ${MQTT_HOST}${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}Info: config.yaml hittades inte, använder localhost som standard${NC}"
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
fi

# Kör testerna
PYTHONPATH=. python3 tests/test_mqtt_client.py "$@"

echo ""
echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}Testerna slutförda! (Tests completed!)${NC}"
echo -e "${GREEN}==================================================================${NC}"
