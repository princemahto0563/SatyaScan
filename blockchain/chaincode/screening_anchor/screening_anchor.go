/*
 * SatyaScan — Hyperledger Fabric Screening Anchor Chaincode
 * SIH26188 · Theme: Blockchain & Cybersecurity
 *
 * Privacy Principle:
 * "Evidence stays off-chain. Cryptographic proof goes on-chain."
 *
 * Zero PII Guarantee:
 * Never stores passenger names, dates of birth, images, biometrics,
 * OCR raw text, or document numbers on the immutable ledger.
 */

package main

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// ScreeningAnchorContract provides functions for anchoring screening evidence hashes
type ScreeningAnchorContract struct {
	contractapi.Contract
}

// ScreeningAnchor represents the minimal immutable audit anchor stored on-chain
type ScreeningAnchor struct {
	ScreeningID     string `json:"screeningId"`
	DocumentHash    string `json:"documentHash"`
	ResultHash      string `json:"resultHash"`
	RiskLevel       string `json:"riskLevel"`
	CheckpointID    string `json:"checkpointId"`
	Timestamp       string `json:"timestamp"`
	PipelineVersion string `json:"pipelineVersion"`
	AnchorVersion   string `json:"anchorVersion"`
}

// VerificationResult provides the structured response for anchor verification
type VerificationResult struct {
	ScreeningID         string `json:"screeningId"`
	IsVerified          bool   `json:"isVerified"`
	DocumentHashMatches bool   `json:"documentHashMatches"`
	ResultHashMatches   bool   `json:"resultHashMatches"`
	OnChainRecord       *ScreeningAnchor `json:"onChainRecord,omitempty"`
	StatusMessage       string `json:"statusMessage"`
}

// InitLedger initializes chaincode state if necessary
func (s *ScreeningAnchorContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
	return nil
}

// isValidSHA256 validates that a hash string is exactly 64 hexadecimal characters
func isValidSHA256(h string) bool {
	if len(h) != 64 {
		return false
	}
	_, err := hex.DecodeString(h)
	return err == nil
}

// CreateScreeningAnchor creates and stores a new immutable screening anchor on the ledger
func (s *ScreeningAnchorContract) CreateScreeningAnchor(
	ctx contractapi.TransactionContextInterface,
	screeningID string,
	documentHash string,
	resultHash string,
	riskLevel string,
	checkpointID string,
	timestamp string,
	pipelineVersion string,
	anchorVersion string,
) error {
	// 1. Input sanitization & validation
	screeningID = strings.TrimSpace(screeningID)
	documentHash = strings.ToLower(strings.TrimSpace(documentHash))
	resultHash = strings.ToLower(strings.TrimSpace(resultHash))
	riskLevel = strings.ToUpper(strings.TrimSpace(riskLevel))
	checkpointID = strings.TrimSpace(checkpointID)
	timestamp = strings.TrimSpace(timestamp)
	pipelineVersion = strings.TrimSpace(pipelineVersion)
	anchorVersion = strings.TrimSpace(anchorVersion)

	if screeningID == "" {
		return fmt.Errorf("screeningId cannot be empty")
	}
	if !isValidSHA256(documentHash) {
		return fmt.Errorf("documentHash must be a valid 64-character SHA-256 hex string")
	}
	if !isValidSHA256(resultHash) {
		return fmt.Errorf("resultHash must be a valid 64-character SHA-256 hex string")
	}

	validRiskLevels := map[string]bool{"LOW": true, "MEDIUM": true, "HIGH": true, "CRITICAL": true}
	if !validRiskLevels[riskLevel] {
		return fmt.Errorf("invalid riskLevel '%s'; allowed values: LOW, MEDIUM, HIGH, CRITICAL", riskLevel)
	}

	// 2. Duplicate anchor prevention (Enforce one anchor per screening)
	exists, err := s.ScreeningAnchorExists(ctx, screeningID)
	if err != nil {
		return fmt.Errorf("failed checking anchor existence: %v", err)
	}
	if exists {
		return fmt.Errorf("screening anchor for ID '%s' already exists; immutable anchors cannot be overwritten", screeningID)
	}

	// 3. Construct on-chain asset
	anchor := ScreeningAnchor{
		ScreeningID:     screeningID,
		DocumentHash:    documentHash,
		ResultHash:      resultHash,
		RiskLevel:       riskLevel,
		CheckpointID:    checkpointID,
		Timestamp:       timestamp,
		PipelineVersion: pipelineVersion,
		AnchorVersion:   anchorVersion,
	}

	anchorJSON, err := json.Marshal(anchor)
	if err != nil {
		return fmt.Errorf("failed to marshal anchor JSON: %v", err)
	}

	// 4. Commit to ledger state
	err = ctx.GetStub().PutState(screeningID, anchorJSON)
	if err != nil {
		return fmt.Errorf("failed to put state to ledger: %v", err)
	}

	// 5. Emit event for downstream audit watchers
	eventPayload, _ := json.Marshal(map[string]string{
		"screeningId":  screeningID,
		"documentHash": documentHash,
		"resultHash":   resultHash,
	})
	_ = ctx.GetStub().SetEvent("AnchorCreated", eventPayload)

	return nil
}

// GetScreeningAnchor retrieves an existing screening anchor from the ledger by screeningID
func (s *ScreeningAnchorContract) GetScreeningAnchor(
	ctx contractapi.TransactionContextInterface,
	screeningID string,
) (*ScreeningAnchor, error) {
	screeningID = strings.TrimSpace(screeningID)
	if screeningID == "" {
		return nil, fmt.Errorf("screeningId cannot be empty")
	}

	anchorBytes, err := ctx.GetStub().GetState(screeningID)
	if err != nil {
		return nil, fmt.Errorf("failed to read state from ledger for ID '%s': %v", screeningID, err)
	}
	if anchorBytes == nil {
		return nil, fmt.Errorf("screening anchor '%s' does not exist on ledger", screeningID)
	}

	var anchor ScreeningAnchor
	err = json.Unmarshal(anchorBytes, &anchor)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal anchor JSON: %v", err)
	}

	return &anchor, nil
}

// ScreeningAnchorExists returns true if a screening anchor exists on the ledger
func (s *ScreeningAnchorContract) ScreeningAnchorExists(
	ctx contractapi.TransactionContextInterface,
	screeningID string,
) (bool, error) {
	screeningID = strings.TrimSpace(screeningID)
	anchorBytes, err := ctx.GetStub().GetState(screeningID)
	if err != nil {
		return false, fmt.Errorf("failed to read state: %v", err)
	}
	return anchorBytes != nil, nil
}

// VerifyScreeningAnchor compares presented off-chain hashes against the immutable on-chain record
func (s *ScreeningAnchorContract) VerifyScreeningAnchor(
	ctx contractapi.TransactionContextInterface,
	screeningID string,
	documentHash string,
	resultHash string,
) (*VerificationResult, error) {
	screeningID = strings.TrimSpace(screeningID)
	documentHash = strings.ToLower(strings.TrimSpace(documentHash))
	resultHash = strings.ToLower(strings.TrimSpace(resultHash))

	anchor, err := s.GetScreeningAnchor(ctx, screeningID)
	if err != nil {
		return &VerificationResult{
			ScreeningID:         screeningID,
			IsVerified:          false,
			DocumentHashMatches: false,
			ResultHashMatches:   false,
			StatusMessage:       fmt.Sprintf("Anchor record not found on ledger: %v", err),
		}, nil
	}

	docMatch := (anchor.DocumentHash == documentHash)
	resMatch := (anchor.ResultHash == resultHash)
	allMatch := docMatch && resMatch

	msg := "BLOCKCHAIN RECORD MATCHES LOCAL EVIDENCE"
	if !docMatch && !resMatch {
		msg = "CRITICAL: Both document hash and result hash mismatch on-chain record!"
	} else if !docMatch {
		msg = "CRITICAL: Document hash does not match immutable on-chain record!"
	} else if !resMatch {
		msg = "CRITICAL: Result hash does not match immutable on-chain record!"
	}

	return &VerificationResult{
		ScreeningID:         screeningID,
		IsVerified:          allMatch,
		DocumentHashMatches: docMatch,
		ResultHashMatches:   resMatch,
		OnChainRecord:       anchor,
		StatusMessage:       msg,
	}, nil
}

func main() {
	chaincode, err := contractapi.NewChaincode(&ScreeningAnchorContract{})
	if err != nil {
		fmt.Printf("Error creating SatyaScan Screening Anchor chaincode: %v\n", err)
		return
	}

	if err := chaincode.Start(); err != nil {
		fmt.Printf("Error starting SatyaScan Screening Anchor chaincode: %v\n", err)
	}
}
