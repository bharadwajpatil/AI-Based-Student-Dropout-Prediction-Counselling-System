#!/usr/bin/env bash
# ==============================================================================
# Student Dropout Prediction & Counselling System - Shutdown Script
# Gracefully stops Docker Compose services.
# ==============================================================================

set -e

# Terminal Colors
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "\n${YELLOW}➔ Stopping Docker Compose services gracefully...${NC}"
docker compose down

echo -e "\n${BOLD}${GREEN}✔ All containers stopped successfully.${NC}"
echo -e "To start again anytime, run: ${BOLD}./run.sh${NC}\n"
