#!/bin/bash
# ==============================================================================
# SatyaScan — Hyperledger Fabric Chaincode Deployment Script
# Deploys the screening_anchor chaincode to a Hyperledger Fabric channel.
# ==============================================================================

set -euo pipefail

CHANNEL_NAME="${1:-satyascan-channel}"
CC_NAME="${2:-screening_anchor}"
CC_VERSION="${3:-1.0}"
CC_SEQUENCE="${4:-1}"
CC_SRC_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/chaincode/screening_anchor" && pwd)"

echo "========================================================================"
echo "SATYASCAN HYPERLEDGER FABRIC CHAINCODE DEPLOYMENT"
echo "========================================================================"
echo "  Channel          : ${CHANNEL_NAME}"
echo "  Chaincode Name   : ${CC_NAME}"
echo "  Version          : ${CC_VERSION}"
echo "  Sequence         : ${CC_SEQUENCE}"
echo "  Chaincode Path   : ${CC_SRC_PATH}"
echo "========================================================================"

if ! command -v peer &> /dev/null; then
    echo "[!] Error: 'peer' CLI binary not found in PATH."
    echo "    Please ensure Hyperledger Fabric binaries are downloaded and added to PATH."
    echo "    Example: export PATH=\$PATH:/path/to/fabric-samples/bin"
    exit 1
fi

echo "[Step 1/5] Packaging chaincode..."
peer lifecycle chaincode package "${CC_NAME}.tar.gz" \
  --path "${CC_SRC_PATH}" \
  --lang golang \
  --label "${CC_NAME}_${CC_VERSION}"

echo "[Step 2/5] Installing chaincode on peer0.org1..."
peer lifecycle chaincode install "${CC_NAME}.tar.gz"

CC_PACKAGE_ID=$(peer lifecycle chaincode calculatepackageid "${CC_NAME}.tar.gz")
echo "  -> Package ID: ${CC_PACKAGE_ID}"

echo "[Step 3/5] Approving chaincode definition for Org1..."
peer lifecycle chaincode approveformyorg \
  -o localhost:7050 \
  --ordererTLSHostnameOverride orderer.example.com \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}" \
  --version "${CC_VERSION}" \
  --package-id "${CC_PACKAGE_ID}" \
  --sequence "${CC_SEQUENCE}"

echo "[Step 4/5] Committing chaincode definition to channel..."
peer lifecycle chaincode commit \
  -o localhost:7050 \
  --ordererTLSHostnameOverride orderer.example.com \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}" \
  --version "${CC_VERSION}" \
  --sequence "${CC_SEQUENCE}"

echo "[Step 5/5] Querying committed chaincode..."
peer lifecycle chaincode querycommitted \
  --channelID "${CHANNEL_NAME}" \
  --name "${CC_NAME}"

echo "========================================================================"
echo "[SUCCESS] Screening Anchor Chaincode successfully deployed to ${CHANNEL_NAME}!"
echo "========================================================================"
