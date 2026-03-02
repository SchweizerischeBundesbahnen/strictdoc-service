#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Generating test load for StrictDoc Service...${NC}"
echo ""

# Configuration
BASE_URL="http://localhost:9083"
REQUESTS=${1:-100}
CONCURRENCY=${2:-10}

echo -e "${YELLOW}Configuration:${NC}"
echo -e "  Requests:    ${REQUESTS}"
echo -e "  Concurrency: ${CONCURRENCY}"
echo ""

# Check if service is running
if ! curl -sf ${BASE_URL}/version > /dev/null 2>&1; then
    echo -e "${RED}Error: StrictDoc service is not running at ${BASE_URL}${NC}"
    echo -e "${YELLOW}Run ./monitoring/start-monitoring.sh first${NC}"
    exit 1
fi

# Function to send SDOC export request
send_sdoc_request() {
    local id=$1
    local content="[DOCUMENT]
TITLE: Test Document ${id}

[REQUIREMENT]
UID: REQ-SDOC-${id}
TITLE: Test Requirement
STATEMENT: This requirement tests SDOC export"
    echo "$content" | curl -s -X POST "${BASE_URL}/export?format=sdoc&file_name=test_${id}" \
         -H "Content-Type: text/plain" \
         --data-binary @- \
         -o /dev/null
}

# Function to send JSON export request
send_json_request() {
    local id=$1
    local content="[DOCUMENT]
TITLE: JSON Export Test ${id}

[REQUIREMENT]
UID: REQ-JSON-${id}
TITLE: JSON Requirement
STATEMENT: This requirement tests JSON export"
    echo "$content" | curl -s -X POST "${BASE_URL}/export?format=json&file_name=test_${id}" \
         -H "Content-Type: text/plain" \
         --data-binary @- \
         -o /dev/null
}

# Function to send RST export request
send_rst_request() {
    local id=$1
    local content="[DOCUMENT]
TITLE: RST Export Test ${id}

[REQUIREMENT]
UID: REQ-RST-${id}
TITLE: RST Requirement
STATEMENT: This requirement tests RST export"
    echo "$content" | curl -s -X POST "${BASE_URL}/export?format=rst&file_name=test_${id}" \
         -H "Content-Type: text/plain" \
         --data-binary @- \
         -o /dev/null
}

# Generate mixed load
echo -e "${YELLOW}Generating ${REQUESTS} requests...${NC}"
echo -n "Progress: "

count=0
pids=()

for i in $(seq 1 $REQUESTS); do
    # Mix of different export formats
    case $((i % 3)) in
        0) send_json_request $i & ;;
        1) send_rst_request $i & ;;
        *) send_sdoc_request $i & ;;
    esac

    pids+=($!)
    count=$((count + 1))

    # Limit concurrency
    if [ ${#pids[@]} -ge $CONCURRENCY ]; then
        wait ${pids[0]}
        pids=("${pids[@]:1}")
    fi

    # Progress indicator
    if [ $((count % 10)) -eq 0 ]; then
        echo -n "."
    fi
done

# Wait for remaining requests
for pid in "${pids[@]}"; do
    wait $pid
done

echo -e " ${GREEN}Done!${NC}"
echo ""
echo -e "${GREEN}Generated ${REQUESTS} requests${NC}"
echo ""
echo -e "${BLUE}Check metrics at:${NC}"
echo -e "  • Prometheus:        ${YELLOW}http://localhost:9090/graph${NC}"
echo -e "  • Grafana:           ${YELLOW}http://localhost:3000/d/strictdoc-service${NC}"
echo ""
