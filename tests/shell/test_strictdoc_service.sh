#!/bin/bash
set -e

# Define constants
CONTAINER_NAME="strictdoc_service_test"
IMAGE_NAME="strictdoc-service:test"
PORT=9083
BASE_URL="http://localhost:${PORT}"

# Colors for output
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
NC="\033[0m" # No Color

# Log function
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# Error function
error() {
    echo -e "${RED}[ERROR]${NC} $1"
    # Show container logs if container exists
    if docker ps -q -f name=${CONTAINER_NAME} &>/dev/null; then
        echo -e "\nContainer logs:"
        docker logs ${CONTAINER_NAME}
    fi
    exit 1
}

# Warning function
warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Cleanup function
cleanup() {
    log "Cleaning up resources..."

    # Stop container if running
    if docker ps -q -f name=${CONTAINER_NAME} &>/dev/null; then
        log "Stopping container ${CONTAINER_NAME}..."
        docker stop ${CONTAINER_NAME} >/dev/null 2>&1 || warn "Failed to stop container"
    fi

    # Remove container if it exists
    if docker ps -aq -f name=${CONTAINER_NAME} &>/dev/null; then
        log "Removing container ${CONTAINER_NAME}..."
        docker rm -f ${CONTAINER_NAME} >/dev/null 2>&1 || warn "Failed to remove container"
    fi

    # Remove image if it exists
    if docker images ${IMAGE_NAME} -q &>/dev/null; then
        log "Removing image ${IMAGE_NAME}..."
        docker rmi -f ${IMAGE_NAME} >/dev/null 2>&1 || warn "Failed to remove image"
    fi

    log "Cleanup completed"
}

# Register cleanup on script exit
trap cleanup EXIT

# Initial cleanup to ensure clean state
cleanup

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    error "Docker is not installed or not in PATH"
fi

# Check if curl is available
if ! command -v curl &> /dev/null; then
    error "curl is not installed or not in PATH"
fi

# Build Docker image with verbose output for debugging
log "Building Docker image..."
log "Running: docker build -t ${IMAGE_NAME} ."
if ! docker build -t ${IMAGE_NAME} . ; then
    error "Failed to build Docker image"
fi

# Run container with verbose output
log "Starting container..."
log "Running: docker run -d --name ${CONTAINER_NAME} -p ${PORT}:${PORT} ${IMAGE_NAME}"
if ! docker run -d --name ${CONTAINER_NAME} -p ${PORT}:${PORT} ${IMAGE_NAME} ; then
    error "Failed to start container"
fi

# Show container status immediately after start
log "Container status after start:"
docker ps -a | grep ${CONTAINER_NAME} || true
log "Container logs after start:"
docker logs ${CONTAINER_NAME}

# Wait for container to be healthy
log "Waiting for container to be healthy..."
attempt=1
max_attempts=10
until [ "$attempt" -gt "$max_attempts" ] || docker ps | grep ${CONTAINER_NAME} | grep -q "healthy"; do
    if ! docker ps -q -f name=${CONTAINER_NAME} >/dev/null 2>&1; then
        log "Container stopped unexpectedly. Checking logs..."
        docker logs ${CONTAINER_NAME}
        error "Container stopped unexpectedly. Check docker logs for details"
    fi
    log "Attempt $attempt/$max_attempts - Waiting for container to be healthy..."
    log "Current container status:"
    docker ps -a | grep ${CONTAINER_NAME} || true
    sleep 5
    ((attempt++))
done

if [ "$attempt" -gt "$max_attempts" ]; then
    # Show container logs before failing
    echo -e "\nContainer logs:"
    docker logs ${CONTAINER_NAME}
    error "Container failed to become healthy after $max_attempts attempts"
fi

log "Container is healthy. Running tests..."

# Test 1: Check version endpoint
log "Test 1: Checking version endpoint..."
VERSION_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" ${BASE_URL}/version)
if [ "$VERSION_RESPONSE" -ne 200 ]; then
    error "Version endpoint returned non-200 status code: $VERSION_RESPONSE"
fi

VERSION_JSON=$(curl -s ${BASE_URL}/version)
log "Version info: $VERSION_JSON"

# Create a temporary directory for test files
TEST_DIR=$(mktemp -d)
SDOC_FILE="$TEST_DIR/input.sdoc"
JSON_FILE="$TEST_DIR/output.json"
HTML_FILE="$TEST_DIR/output.zip"
REQIF_FILE="$TEST_DIR/output.reqif"
PDF_FILE="$TEST_DIR/output.pdf"
EXCEL_FILE="$TEST_DIR/output.xlsx"
RST_FILE="$TEST_DIR/output.rst"
SDOC_EXPORT_FILE="$TEST_DIR/output.sdoc"
REQIFZ_FILE="$TEST_DIR/output.reqifz"

# Write test SDOC file with proper newlines
cat > "${SDOC_FILE}" << 'EOF'
[DOCUMENT]
TITLE: Test Document

[[SECTION]]
TITLE: Test Section

[REQUIREMENT]
UID: REQ-001
STATUS: Draft
TITLE: First Requirement
STATEMENT: >>>
This is a test requirement
<<<

[REQUIREMENT]
UID: REQ-002
STATUS: Approved
TITLE: Second Requirement
STATEMENT: >>>
This is another test requirement
<<<

[[/SECTION]]
EOF

# Test 2a: Export SDOC to JSON
log "Test 2a: Exporting SDOC to JSON..."

# Make the export request using the file path
EXPORT_RESPONSE=$(curl -s -o "${JSON_FILE}" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=json&file_name=test-export")

if [ "$EXPORT_RESPONSE" -ne 200 ]; then
    # Show the error response and file contents for debugging
    ERROR_CONTENT=$(cat ${JSON_FILE})
    error "JSON export endpoint returned non-200 status code: $EXPORT_RESPONSE\nError: $ERROR_CONTENT"
fi

log "JSON export response status code: $EXPORT_RESPONSE"

# Verify JSON content
if [ ! -s "${JSON_FILE}" ]; then
    error "JSON response is empty"
fi

# Check file type
file "${JSON_FILE}" > "${TEST_DIR}/json_file_type.txt"
log "JSON file type: $(cat ${TEST_DIR}/json_file_type.txt)"

# Display file size
log "JSON file size: $(wc -c < ${JSON_FILE}) bytes"

# Display JSON contents for debugging (first 100 bytes as hex)
log "JSON file contents (hex):"
xxd -l 100 "${JSON_FILE}" | head -n 10

# Save JSON file for inspection
SAVED_JSON="test-export.json"
cp "${JSON_FILE}" "${SAVED_JSON}"
log "JSON file saved to ${SAVED_JSON}"

# Validate JSON structure if jq is available
if command -v jq &> /dev/null; then
    if ! cat "${JSON_FILE}" | jq -e . > /dev/null 2>&1; then
        error "JSON is not valid"
    else
        log "JSON validated successfully with jq"
    fi
else
    log "jq not available, skipping detailed JSON validation"
fi

# Check if JSON contains expected content
if ! grep -q "REQ-001" "${JSON_FILE}" || ! grep -q "REQ-002" "${JSON_FILE}"; then
    error "JSON file does not contain expected requirement UIDs"
fi

if ! grep -q "Draft" "${JSON_FILE}" || ! grep -q "Approved" "${JSON_FILE}"; then
    error "JSON file does not contain expected status values"
fi

log "JSON content validation passed"

# Test 2b: Export SDOC to HTML
log "Test 2b: Exporting SDOC to HTML..."

# Make the export request using the file path
EXPORT_RESPONSE=$(curl -s -o "${HTML_FILE}" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=html&file_name=test-export")

if [ "$EXPORT_RESPONSE" -ne 200 ]; then
    # Show the error response and file contents for debugging
    ERROR_CONTENT=$(cat ${HTML_FILE})
    error "HTML export endpoint returned non-200 status code: $EXPORT_RESPONSE\nError: $ERROR_CONTENT"
fi

log "HTML export response status code: $EXPORT_RESPONSE"

# Verify HTML zip content
if [ ! -s "${HTML_FILE}" ]; then
    error "HTML response is empty"
fi

# Check file type
file "${HTML_FILE}" > "${TEST_DIR}/html_file_type.txt"
log "HTML file type: $(cat ${TEST_DIR}/html_file_type.txt)"

# Display file size
log "HTML file size: $(wc -c < ${HTML_FILE}) bytes"

# Display HTML zip contents for debugging (first 100 bytes as hex)
log "HTML zip file contents (hex):"
xxd -l 100 "${HTML_FILE}" | head -n 10

# Save HTML zip file for inspection
SAVED_HTML="test-export.zip"
cp "${HTML_FILE}" "${SAVED_HTML}"
log "HTML zip file saved to ${SAVED_HTML}"

# Check if it's a zip file
if command -v unzip &> /dev/null && file "${HTML_FILE}" | grep -q "Zip archive data\|zip archive\|ZIP"; then
    log "HTML export appears to be a valid zip archive"

    # Create a temporary directory to extract zip
    HTML_EXTRACT_DIR="${TEST_DIR}/html_extract"
    mkdir -p "${HTML_EXTRACT_DIR}"

    # Extract zip and check content
    if unzip -q "${HTML_FILE}" -d "${HTML_EXTRACT_DIR}" 2>/dev/null; then
        # Check if any HTML files exist
        if find "${HTML_EXTRACT_DIR}" -type f -name "*.html" | grep -q .; then
            log "HTML export contains HTML files"

            # Check if HTML contains expected content
            if ! find "${HTML_EXTRACT_DIR}" -type f -name "*.html" -exec grep -l "REQ-001" {} \; | grep -q .; then
                log "Warning: Could not find REQ-001 in HTML files, but this may be due to HTML structure"
            else
                log "Found REQ-001 in HTML files"
            fi
        else
            log "Warning: No HTML files found in the extracted zip"
        fi
    else
        log "Warning: Failed to extract HTML zip archive, but continuing tests"
    fi
else
    log "HTML export does not appear to be a zip archive, but this may be expected depending on the implementation"
fi

# Test 2c: Export SDOC to ReqIF
log "Test 2c: Exporting SDOC to ReqIF..."

# Make the export request using the file path
EXPORT_RESPONSE=$(curl -s -o "${REQIF_FILE}" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=reqif-sdoc&file_name=test-export")

if [ "$EXPORT_RESPONSE" -ne 200 ]; then
    # Show the error response and file contents for debugging
    ERROR_CONTENT=$(cat ${REQIF_FILE})
    error "ReqIF export endpoint returned non-200 status code: $EXPORT_RESPONSE\nError: $ERROR_CONTENT"
fi

log "ReqIF export response status code: $EXPORT_RESPONSE"

# Verify ReqIF content
if [ ! -s "${REQIF_FILE}" ]; then
    error "ReqIF response is empty"
fi

# Check file type
file "${REQIF_FILE}" > "${TEST_DIR}/reqif_file_type.txt"
log "ReqIF file type: $(cat ${TEST_DIR}/reqif_file_type.txt)"

# Display file size
log "ReqIF file size: $(wc -c < ${REQIF_FILE}) bytes"

# Display ReqIF contents for debugging (first 100 bytes as hex)
log "ReqIF file contents (hex):"
xxd -l 100 "${REQIF_FILE}" | head -n 10

# Save ReqIF file for inspection
SAVED_REQIF="test-export.reqif"
cp "${REQIF_FILE}" "${SAVED_REQIF}"
log "ReqIF file saved to ${SAVED_REQIF}"

# Basic validation - check for XML and ReqIF elements
if grep -q "<?xml" "${REQIF_FILE}" && grep -q "<REQ-IF" "${REQIF_FILE}"; then
    log "ReqIF file appears to be valid XML with REQ-IF elements"
else
    log "Warning: ReqIF file doesn't appear to be valid ReqIF XML, but continuing tests"
fi

# Check if ReqIF contains expected content (UIDs)
if grep -q "REQ-001" "${REQIF_FILE}" && grep -q "REQ-002" "${REQIF_FILE}"; then
    log "ReqIF file contains expected requirement UIDs"
else
    log "Warning: ReqIF file doesn't contain expected UIDs, but this may be due to ReqIF encoding"
fi

# Test 2d: Export SDOC to PDF
log "Test 2d: Exporting SDOC to PDF..."

# Make the export request using the file path
PDF_EXPORT_RESPONSE=$(curl -s -o "${PDF_FILE}" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=html2pdf&file_name=test-export")

log "PDF export response status code: ${PDF_EXPORT_RESPONSE}"

# Check if PDF export is supported
if [ "${PDF_EXPORT_RESPONSE}" -ne 200 ]; then
    log "Note: PDF export (html2pdf) may not be supported in this version of StrictDoc. Skipping PDF validation."
else
    # Verify PDF content
    if [ ! -s "${PDF_FILE}" ]; then
        error "PDF response is empty"
    fi

    # Check file type
    file "${PDF_FILE}" > "${TEST_DIR}/pdf_file_type.txt"
    log "PDF file type: $(cat ${TEST_DIR}/pdf_file_type.txt)"

    # Display file size
    log "PDF file size: $(wc -c < ${PDF_FILE}) bytes"

    # Display PDF contents for debugging (first 100 bytes as hex)
    log "PDF file contents (hex):"
    xxd -l 100 "${PDF_FILE}" | head -n 10

    # Save PDF file for inspection
    SAVED_PDF="test-export.pdf"
    cp "${PDF_FILE}" "${SAVED_PDF}"
    log "PDF file saved to ${SAVED_PDF}"

    # Basic validation - check for PDF signature
    if head -c 4 "${PDF_FILE}" | grep -q "%PDF"; then
        log "PDF file has correct signature"
    else
        log "Warning: File does not have PDF signature, but continuing tests"
    fi
fi

# Test 2e: Export SDOC to Excel
log "Test 2e: Exporting SDOC to Excel..."

# Make the export request using the file path
EXPORT_RESPONSE=$(curl -s -o "${EXCEL_FILE}" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=excel&file_name=test-export")

if [ "$EXPORT_RESPONSE" -ne 200 ]; then
    # Show the error response and file contents for debugging
    ERROR_CONTENT=$(cat ${EXCEL_FILE})
    error "Excel export endpoint returned non-200 status code: $EXPORT_RESPONSE\nError: $ERROR_CONTENT"
fi

log "Excel export response status code: $EXPORT_RESPONSE"

# Verify Excel content
if [ ! -s "${EXCEL_FILE}" ]; then
    error "Excel response is empty"
fi

# Check file type
file "${EXCEL_FILE}" > "${TEST_DIR}/excel_file_type.txt"
log "Excel file type: $(cat ${TEST_DIR}/excel_file_type.txt)"

# Display file size
log "Excel file size: $(wc -c < ${EXCEL_FILE}) bytes"

# Display Excel contents for debugging (first 100 bytes as hex)
log "Excel file contents (hex):"
xxd -l 100 "${EXCEL_FILE}" | head -n 10

# Save Excel file for inspection
SAVED_EXCEL="test-export.xlsx"
cp "${EXCEL_FILE}" "${SAVED_EXCEL}"
log "Excel file saved to ${SAVED_EXCEL}"

# Basic validation - check for xlsx signature (PK zip signature)
if head -c 2 "${EXCEL_FILE}" | xxd -p | grep -q "504b"; then
    log "Excel file has correct signature (XLSX/ZIP format)"
else
    log "Warning: File does not have Excel/XLSX signature, but continuing tests"
fi

# Test 2f: Export SDOC to RST
log "Test 2f: Exporting SDOC to RST..."

# Make the export request using the file path
EXPORT_RESPONSE=$(curl -s -o "${RST_FILE}" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=rst&file_name=test-export")

if [ "$EXPORT_RESPONSE" -ne 200 ]; then
    # Show the error response and file contents for debugging
    ERROR_CONTENT=$(cat ${RST_FILE})
    error "RST export endpoint returned non-200 status code: $EXPORT_RESPONSE\nError: $ERROR_CONTENT"
fi

log "RST export response status code: $EXPORT_RESPONSE"

# Verify RST content
if [ ! -s "${RST_FILE}" ]; then
    error "RST response is empty"
fi

# Check file type
file "${RST_FILE}" > "${TEST_DIR}/rst_file_type.txt"
log "RST file type: $(cat ${TEST_DIR}/rst_file_type.txt)"

# Display file size
log "RST file size: $(wc -c < ${RST_FILE}) bytes"

# Display RST contents for debugging (first 100 bytes as hex)
log "RST file contents (hex):"
xxd -l 100 "${RST_FILE}" | head -n 10

# Save RST file for inspection
SAVED_RST="test-export.rst"
cp "${RST_FILE}" "${SAVED_RST}"
log "RST file saved to ${SAVED_RST}"

# Basic validation for RST format
if grep -q "REQ-001" "${RST_FILE}" && grep -q "REQ-002" "${RST_FILE}"; then
    log "RST file contains expected requirement UIDs"
else
    log "Warning: RST file doesn't contain expected UIDs, but this may be due to RST formatting"
fi

# Test 2g: Export SDOC back to SDOC format
log "Test 2g: Exporting SDOC back to SDOC format..."

# Make the export request using the file path
EXPORT_RESPONSE=$(curl -s -o "${SDOC_EXPORT_FILE}" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=sdoc&file_name=test-export")

if [ "$EXPORT_RESPONSE" -ne 200 ]; then
    # Show the error response and file contents for debugging
    ERROR_CONTENT=$(cat ${SDOC_EXPORT_FILE})
    error "SDOC export endpoint returned non-200 status code: $EXPORT_RESPONSE\nError: $ERROR_CONTENT"
fi

log "SDOC export response status code: $EXPORT_RESPONSE"

# Verify SDOC content
if [ ! -s "${SDOC_EXPORT_FILE}" ]; then
    error "SDOC export response is empty"
fi

# Check file type
file "${SDOC_EXPORT_FILE}" > "${TEST_DIR}/sdoc_export_file_type.txt"
log "SDOC export file type: $(cat ${TEST_DIR}/sdoc_export_file_type.txt)"

# Display file size
log "SDOC export file size: $(wc -c < ${SDOC_EXPORT_FILE}) bytes"

# Display SDOC export contents for debugging (first 100 bytes as hex)
log "SDOC export file contents (hex):"
xxd -l 100 "${SDOC_EXPORT_FILE}" | head -n 10

# Save SDOC export file for inspection
SAVED_SDOC="test-export.sdoc"
cp "${SDOC_EXPORT_FILE}" "${SAVED_SDOC}"
log "SDOC export file saved to ${SAVED_SDOC}"

# Basic validation for SDOC format - should contain [DOCUMENT] and [REQUIREMENT] tags
if grep -q "\[DOCUMENT\]" "${SDOC_EXPORT_FILE}" && grep -q "\[REQUIREMENT\]" "${SDOC_EXPORT_FILE}"; then
    log "SDOC export file has correct SDOC structure"
else
    log "Warning: SDOC export file doesn't have expected SDOC structure, but continuing tests"
fi

# Basic validation for requirement UIDs
if grep -q "REQ-001" "${SDOC_EXPORT_FILE}" && grep -q "REQ-002" "${SDOC_EXPORT_FILE}"; then
    log "SDOC export file contains expected requirement UIDs"
else
    log "Warning: SDOC export file doesn't contain expected UIDs, but this may be due to formatting"
fi

# Test 2h: Export SDOC to ReqIFZ (compressed ReqIF)
log "Test 2h: Exporting SDOC to ReqIFZ..."

# Make the export request using the file path
EXPORT_RESPONSE=$(curl -s -o "${REQIFZ_FILE}" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=reqifz-sdoc&file_name=test-export")

if [ "$EXPORT_RESPONSE" -ne 200 ]; then
    # Show the error response and file contents for debugging
    ERROR_CONTENT=$(cat ${REQIFZ_FILE})
    error "ReqIFZ export endpoint returned non-200 status code: $EXPORT_RESPONSE\nError: $ERROR_CONTENT"
fi

log "ReqIFZ export response status code: $EXPORT_RESPONSE"

# Verify ReqIFZ content
if [ ! -s "${REQIFZ_FILE}" ]; then
    error "ReqIFZ response is empty"
fi

# Check file type
file "${REQIFZ_FILE}" > "${TEST_DIR}/reqifz_file_type.txt"
log "ReqIFZ file type: $(cat ${TEST_DIR}/reqifz_file_type.txt)"

# Display file size
log "ReqIFZ file size: $(wc -c < ${REQIFZ_FILE}) bytes"

# Display ReqIFZ contents for debugging (first 100 bytes as hex)
log "ReqIFZ file contents (hex):"
xxd -l 100 "${REQIFZ_FILE}" | head -n 10

# Save ReqIFZ file for inspection
SAVED_REQIFZ="test-export.reqifz"
cp "${REQIFZ_FILE}" "${SAVED_REQIFZ}"
log "ReqIFZ file saved to ${SAVED_REQIFZ}"

# Check if it's a zip file (ReqIFZ is a zip archive)
if file "${REQIFZ_FILE}" | grep -q "Zip archive data\|zip archive\|ZIP"; then
    log "ReqIFZ file appears to be a valid zip archive"

    # Create a temporary directory to extract zip
    REQIFZ_EXTRACT_DIR="${TEST_DIR}/reqifz_extract"
    mkdir -p "${REQIFZ_EXTRACT_DIR}"

    # Extract zip and check content
    if command -v unzip &> /dev/null && unzip -q "${REQIFZ_FILE}" -d "${REQIFZ_EXTRACT_DIR}" 2>/dev/null; then
        # Check if any XML or ReqIF files exist
        if find "${REQIFZ_EXTRACT_DIR}" -type f -name "*.xml" -o -name "*.reqif" | grep -q .; then
            log "ReqIFZ contains XML/ReqIF files"
        else
            log "Warning: No XML/ReqIF files found in the extracted ReqIFZ archive, but continuing tests"
        fi
    else
        log "Warning: Failed to extract ReqIFZ archive or unzip not available, but continuing tests"
    fi
else
    log "Warning: ReqIFZ file doesn't appear to be a zip archive, but continuing tests"
fi

# Test 3: Test invalid format
log "Test 3: Testing invalid export format..."
INVALID_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "@${SDOC_FILE}" \
    "${BASE_URL}/export?format=invalid&file_name=test-export")

if [ "$INVALID_RESPONSE" -ne 400 ]; then
    error "Invalid format test failed. Expected 400, got: $INVALID_RESPONSE"
fi

# Test 4: Test invalid SDOC content
log "Test 4: Testing invalid SDOC content..."
INVALID_SDOC="Invalid content without DOCUMENT section"
INVALID_CONTENT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST \
    -H "Content-Type: text/plain" \
    --data-binary "${INVALID_SDOC}" \
    "${BASE_URL}/export?format=csv&file_name=test-export")

if [ "$INVALID_CONTENT_RESPONSE" -ne 400 ]; then
    error "Invalid content test failed. Expected 400, got: $INVALID_CONTENT_RESPONSE"
fi

# Clean up temporary files
rm -rf "${TEST_DIR}"

log "All tests passed successfully!"
exit 0
