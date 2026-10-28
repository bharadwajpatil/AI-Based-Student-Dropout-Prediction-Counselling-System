#!/usr/bin/env bash
# ==============================================================================
# Student Dropout Prediction & Counselling System - Startup Script
# Starts Docker Compose services and displays system URLs & credentials.
# ==============================================================================

set -e

# Terminal Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "\n${BOLD}${CYAN}========================================================================${NC}"
echo -e "${BOLD}${CYAN}     🎓 STUDENT DROPOUT PREDICTION & COUNSELLING SYSTEM STARTUP         ${NC}"
echo -e "${BOLD}${CYAN}========================================================================${NC}\n"

echo -e "${YELLOW}➔ Starting Docker Compose services in the background...${NC}"
docker compose up -d

echo -e "\n${YELLOW}➔ Verifying services health status...${NC}"
# Brief wait to ensure ports are listening
sleep 2

echo -e "\n${BOLD}${GREEN}========================================================================${NC}"
echo -e "${BOLD}${GREEN}                     🚀 SYSTEM IS UP AND RUNNING!                       ${NC}"
echo -e "${BOLD}${GREEN}========================================================================${NC}\n"

echo -e "${BOLD}🌐 APPLICATION ACCESS URLS:${NC}"
echo -e "  • ${BOLD}Frontend Web Portal:${NC}      ${CYAN}http://localhost:5173${NC}"
echo -e "  • ${BOLD}Backend API Docs (Swagger):${NC} ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  • ${BOLD}Email Testing (MailHog):${NC}    ${CYAN}http://localhost:8025${NC}"
echo -e "  • ${BOLD}MongoDB Database:${NC}           ${CYAN}mongodb://localhost:27017${NC}"

echo -e "\n${BOLD}🔑 PRE-SEEDED DEMO CREDENTIALS:${NC}"
echo -e "  ┌──────────────────┬───────────────────────────────┬─────────────────┐"
echo -e "  │ ${BOLD}Role${NC}             │ ${BOLD}Email${NC}                         │ ${BOLD}Password${NC}        │"
echo -e "  ├──────────────────┼───────────────────────────────┼─────────────────┤"
echo -e "  │ Super Admin      │ admin@university.edu          │ AdminPass@123   │"
echo -e "  │ HOD (CS)         │ hod.cs@university.edu         │ HodPass@123     │"
echo -e "  │ HOD (EE)         │ hod.ee@university.edu         │ HodPass@123     │"
echo -e "  │ Faculty 1        │ prof.sharma@university.edu    │ TeacherPass@123 │"
echo -e "  │ Faculty 2        │ prof.kapoor@university.edu    │ TeacherPass@123 │"
echo -e "  │ Student          │ student.demo@university.edu   │ StudentPass@123 │"
echo -e "  └──────────────────┴───────────────────────────────┴─────────────────┘"

echo -e "\n${BOLD}🛠️ QUICK COMMANDS:${NC}"
echo -e "  • Stop services:     ${YELLOW}./stop.sh${NC} (or ${YELLOW}docker compose down${NC})"
echo -e "  • View backend logs: ${YELLOW}docker compose logs -f backend${NC}"
echo -e "  • Re-seed demo data: ${YELLOW}docker compose exec backend python scripts/seed_demo_data.py${NC}"
echo -e "\n${BOLD}${CYAN}========================================================================${NC}\n"
