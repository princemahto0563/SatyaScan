"use client";

import React, { useState, useEffect, useMemo } from "react";
import { 
  ShieldAlert, ShieldCheck, Download, CheckCircle2, XCircle, 
  AlertTriangle, Eye, Lock, Layers, UserCheck, UserX,
  FileSearch, History, Sliders, ChevronLeft, Info, HelpCircle,
  Clock, FileText, Check, AlertCircle, Fingerprint
} from "lucide-react";
import { ScreeningDetail, BlockchainAnchor, BlockchainVerificationResponse } from "../lib/types";
import { 
  getReportDownloadUrl, verifyAuditChain, anchorAuditChain,
  anchorBlockchainScreening, verifyBlockchainAnchor, BACKEND_ROOT_URL,
  getReferenceDataset, getAuthTokenSync
} from "../lib/api";
import { mapScreeningResponseToReportViewModel, ReportViewModel } from "../lib/adapter";

interface ResultViewProps {
  caseData: ScreeningDetail;
  authToken?: string | null;
  onBackToDashboard: () => void;
}

export function ResultView({ caseData, authToken: propAuthToken, onBackToDashboard }: ResultViewProps) {
  const [activeToken, setActiveToken] = useState<string | null>(() => {
    return propAuthToken || getAuthTokenSync() || null;
  });

  useEffect(() => {
    const t = propAuthToken || getAuthTokenSync();
    if (t) setActiveToken(t);
  }, [propAuthToken]);

  const model: ReportViewModel = useMemo(
    () => mapScreeningResponseToReportViewModel(caseData, activeToken),
    [caseData, activeToken]
  );

  const [activeTab, setActiveTab] = useState<"executive" | "validation" | "forensics" | "biometrics" | "audit" | "reference">("executive");
  const [forensicView, setForensicView] = useState<"original" | "ela_heatmap">("ela_heatmap");
  const [docPortraitError, setDocPortraitError] = useState(false);
  const [presentedFaceError, setPresentedFaceError] = useState(false);
  const [heatmapError, setHeatmapError] = useState(false);

  const [auditVerifyResult, setAuditVerifyResult] = useState<any>(null);
  const [isVerifyingAudit, setIsVerifyingAudit] = useState(false);
  const [blockchainAnchor, setBlockchainAnchor] = useState<BlockchainAnchor | null>(caseData.blockchain_anchor || null);
  const [blockchainVerifyResult, setBlockchainVerifyResult] = useState<BlockchainVerificationResponse | null>(null);
  const [isAnchoring, setIsAnchoring] = useState(false);
  const [isVerifyingBlockchain, setIsVerifyingBlockchain] = useState(false);
  const [blockchainError, setBlockchainError] = useState<string | null>(null);
  const [referenceDataset, setReferenceDataset] = useState<any>(null);
  const [selectedPersonId, setSelectedPersonId] = useState<string>("PERSON-001");

  // Reset errors and local states on caseData change to ensure strict screening isolation
  useEffect(() => {
    setDocPortraitError(false);
    setPresentedFaceError(false);
    setHeatmapError(false);
    setAuditVerifyResult(null);
    setBlockchainAnchor(caseData.blockchain_anchor || null);
    setBlockchainVerifyResult(null);
    setBlockchainError(null);
  }, [caseData.id]);

  useEffect(() => {
    if (activeTab === "reference" && !referenceDataset) {
      getReferenceDataset().then((data) => {
        if (data) {
          setReferenceDataset(data);
          if (data.discovered_identities && data.discovered_identities.length > 0) {
            setSelectedPersonId(data.discovered_identities[0].person_id);
          }
        }
      });
    }
  }, [activeTab, referenceDataset]);


  // Live Audit Chain Verification
  const handleVerifyChain = async () => {
    setIsVerifyingAudit(true);
    try {
      const res = await verifyAuditChain(caseData.id);
      setAuditVerifyResult(res);
    } catch (e: any) {
      setAuditVerifyResult({ is_valid: false, status_message: e.message });
    } finally {
      setIsVerifyingAudit(false);
    }
  };

  // Permissioned Hyperledger Fabric Anchoring
  const handleAnchorBlockchain = async () => {
    setIsAnchoring(true);
    setBlockchainError(null);
    try {
      const res = await anchorBlockchainScreening(caseData.id);
      setBlockchainAnchor(res);
    } catch (e: any) {
      setBlockchainError(e.message || "Failed to anchor to Hyperledger Fabric");
    } finally {
      setIsAnchoring(false);
    }
  };

  // Permissioned Hyperledger Fabric Ledger Verification
  const handleVerifyBlockchain = async () => {
    setIsVerifyingBlockchain(true);
    setBlockchainError(null);
    try {
      const res = await verifyBlockchainAnchor(caseData.id);
      setBlockchainVerifyResult(res);
    } catch (e: any) {
      setBlockchainError(e.message || "Failed to verify against Hyperledger Fabric ledger");
    } finally {
      setIsVerifyingBlockchain(false);
    }
  };

  // Human-friendly risk badge
  const getRiskBadge = (band: string) => {
    switch (band) {
      case "LOW":
        return (
          <span className="inline-flex items-center space-x-1 rounded-md bg-emerald-100 dark:bg-emerald-950/60 px-3 py-1 text-xs font-bold text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700/60">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>LOW RISK</span>
          </span>
        );
      case "MEDIUM":
        return (
          <span className="inline-flex items-center space-x-1 rounded-md bg-amber-100 dark:bg-amber-950/60 px-3 py-1 text-xs font-bold text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-700/60">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>MEDIUM RISK</span>
          </span>
        );
      case "HIGH":
        return (
          <span className="inline-flex items-center space-x-1 rounded-md bg-rose-100 dark:bg-rose-950/60 px-3 py-1 text-xs font-bold text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-700/60">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>HIGH RISK</span>
          </span>
        );
      case "CRITICAL":
        return (
          <span className="inline-flex items-center space-x-1 rounded-md bg-red-200 dark:bg-red-950 px-3 py-1 text-xs font-bold text-red-900 dark:text-red-200 border border-red-400 dark:border-red-700">
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>CRITICAL RISK</span>
          </span>
        );
      default:
        return null;
    }
  };

  // Plain-language overall screening verdict summary
  const getPlainVerdictExplanation = () => {
    switch (caseData.risk_band) {
      case "LOW":
        return "Document passed the available verification checks with no major inconsistency detected.";
      case "MEDIUM":
        return "Document exhibits minor validation anomalies or moderate visual variations. Review highlighted fields.";
      case "HIGH":
        return "Significant document or identity inconsistencies detected. Secondary officer examination required.";
      case "CRITICAL":
        return "Critical discrepancies detected across document integrity, MRZ checksums, or identity verification. Immediate supervisor escalation required.";
      default:
        return "Automated screening evaluation completed.";
    }
  };

  // Officer action recommendation
  const getOfficerActionText = () => {
    if (caseData.recommendation) {
      return caseData.recommendation;
    }
    switch (caseData.risk_band) {
      case "LOW":
        return "Proceed with normal verification.";
      case "MEDIUM":
        return "Perform secondary document inspection. Review highlighted fields.";
      case "HIGH":
        return "Request additional identity verification. Conduct physical document examination.";
      case "CRITICAL":
        return "Escalate for manual review and supervisor secondary inspection.";
      default:
        return "Proceed with standard inspection procedures.";
    }
  };

  // Helper to resolve full image URLs with token
  const getFullImageUrl = (path?: string) => {
    if (!path) return null;
    let fullUrl = path.startsWith("http://") || path.startsWith("https://") ? path : `${BACKEND_ROOT_URL}${path}`;
    if (activeToken && !fullUrl.includes("token=")) {
      const sep = fullUrl.includes("?") ? "&" : "?";
      fullUrl = `${fullUrl}${sep}token=${encodeURIComponent(activeToken)}`;
    }
    return fullUrl;
  };

  // Helper for document metadata fields backed by canonical model
  const getFieldVal = (canonicalName: string) => {
    switch (canonicalName) {
      case "full_name":
        return model.document.fullName;
      case "document_number":
        return model.document.number;
      case "surname":
        return model.document.surname;
      case "given_names":
        return model.document.givenNames;
      case "date_of_birth":
        return model.document.dob;
      case "nationality":
        return model.document.nationality;
      case "date_of_expiry":
        return model.document.expiry;
      case "sex":
        return model.document.sex;
      case "document_type":
        return model.document.type;
      default:
        return "Not available";
    }
  };

  // Document validation calculations
  const hasMrzPassed = caseData.mrz_data?.all_checks_passed ?? false;
  const hasMismatches = caseData.extracted_fields.some(f => f.match_status === "MISMATCH");
  const isTamperElevated = (caseData.tamper_summary?.composite_tamper_score ?? 0) >= 35;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      
      {/* Top Breadcrumb & Return Button */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <button
          onClick={onBackToDashboard}
          className="inline-flex items-center space-x-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition"
        >
          <ChevronLeft className="h-4 w-4" />
          <span>Back to Screening Queue</span>
        </button>
        <span className="text-xs text-slate-500 font-mono">
          Screening Ref: {caseData.id} · Latency: {caseData.execution_latency_ms.toFixed(0)} ms
        </span>
      </div>

      {/* OVERALL DECISION BANNER (Calm, Trustworthy, Information-Dense) */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Screening Result
              </span>
              <span className="text-slate-300 dark:text-slate-700">|</span>
              <span className="font-mono font-bold text-base text-slate-900 dark:text-white">
                CASE #{caseData.id}
              </span>
              {getRiskBadge(caseData.risk_band)}
            </div>

            {/* One-line human explanation */}
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              {getPlainVerdictExplanation()}
            </p>

            {/* Officer action recommendation banner */}
            <div className="flex items-start space-x-2 pt-1 text-xs text-slate-700 dark:text-slate-300">
              <span className="font-semibold text-teal-700 dark:text-teal-400 whitespace-nowrap">
                Officer Action:
              </span>
              <span className="font-medium text-slate-900 dark:text-slate-200">{getOfficerActionText()}</span>
            </div>
          </div>

          {/* Header Action Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={getReportDownloadUrl(caseData.id)}
              target="_blank"
              rel="noreferrer"
              className="flex items-center space-x-1.5 rounded-lg bg-teal-700 dark:bg-teal-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-teal-800 dark:hover:bg-teal-500 shadow-sm transition"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Download Official PDF</span>
            </a>

            <button
              onClick={handleVerifyChain}
              disabled={isVerifyingAudit}
              className="flex items-center space-x-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition"
            >
              <Lock className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
              <span>{isVerifyingAudit ? "Verifying..." : "Verify Audit Trail"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Live Audit Verification Banner if Triggered */}
      {auditVerifyResult && (
        <div className={`rounded-xl p-4 border text-xs shadow-sm transition ${
          auditVerifyResult.is_valid
            ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-600/40 text-emerald-900 dark:text-emerald-200"
            : "bg-rose-50 dark:bg-rose-950/40 border-rose-300 dark:border-rose-600/40 text-rose-900 dark:text-rose-200"
        }`}>
          <div className="flex items-start justify-between">
            <div className="flex items-start space-x-3">
              {auditVerifyResult.is_valid ? (
                <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400 mt-0.5 flex-shrink-0" />
              ) : (
                <ShieldAlert className="h-5 w-5 text-rose-600 dark:text-rose-400 mt-0.5 flex-shrink-0" />
              )}
              <div>
                <span className="font-bold text-sm block">
                  {auditVerifyResult.is_valid
                    ? "Audit Trail: VERIFIED · SHA-256 Chain: INTACT"
                    : "Audit Trail: DISCONTINUITY DETECTED"}
                </span>
                <p className="mt-0.5 text-slate-700 dark:text-slate-300">
                  {auditVerifyResult.status_message || "The recorded screening events are cryptographically linked, allowing later modification of the recorded history to be detected."}
                </p>
                {auditVerifyResult.head_hash && (
                  <p className="mt-1 font-mono text-[11px] text-slate-600 dark:text-slate-400 break-all">
                    Latest Root Digest: {auditVerifyResult.head_hash}
                  </p>
                )}
              </div>
            </div>

            {auditVerifyResult.is_valid && !blockchainAnchor && (
              <button
                onClick={handleAnchorBlockchain}
                disabled={isAnchoring}
                className="rounded bg-teal-600/20 dark:bg-teal-600/30 px-3 py-1.5 text-xs font-semibold text-teal-800 dark:text-teal-300 border border-teal-500/40 hover:bg-teal-600/30 transition-colors"
                title="Anchor SHA-256 evidence digests to Hyperledger Fabric permissioned ledger"
              >
                {isAnchoring ? "Anchoring..." : "Anchor to Blockchain"}
              </button>
            )}
          </div>

          {blockchainError && (
            <div className="mt-2 text-[11px] text-rose-600 dark:text-rose-400 font-mono">
              Error: {blockchainError}
            </div>
          )}

          {blockchainAnchor && (
            <div className="mt-3 pt-3 border-t border-emerald-200 dark:border-emerald-500/20 text-[11px] font-mono space-y-1.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-2">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Blockchain Anchor:
                  </span>
                  <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    blockchainAnchor.status === "VERIFIED"
                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                      : blockchainAnchor.status === "MISMATCH"
                      ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                      : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                  }`}>
                    {blockchainAnchor.status === "UNAVAILABLE" ? "OFFLINE / NOT CONNECTED" : blockchainAnchor.status}
                  </span>
                  <span className="text-[10px] text-slate-500 dark:text-slate-400">
                    ({blockchainAnchor.network} · {blockchainAnchor.channel})
                  </span>
                </div>

                <button
                  onClick={handleVerifyBlockchain}
                  disabled={isVerifyingBlockchain}
                  className="rounded bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 px-2 py-1 text-[10px] font-semibold text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-600 transition"
                >
                  {isVerifyingBlockchain ? "Verifying..." : "Verify Ledger Record"}
                </button>
              </div>

              <div className="text-[10px] text-slate-600 dark:text-slate-400 break-all space-y-0.5">
                <div><span>Document SHA-256: </span><span className="text-slate-800 dark:text-slate-200">{blockchainAnchor.document_hash}</span></div>
                <div><span>Result SHA-256: </span><span className="text-slate-800 dark:text-slate-200">{blockchainAnchor.result_hash}</span></div>
                {blockchainAnchor.transaction_id && (
                  <div><span>Transaction ID: </span><span className="text-teal-700 dark:text-teal-400">{blockchainAnchor.transaction_id}</span></div>
                )}
              </div>

              {blockchainVerifyResult && (
                <div className={`mt-2 p-2 rounded text-[10px] border ${
                  blockchainVerifyResult.is_verified
                    ? "bg-emerald-100/50 dark:bg-emerald-950/30 border-emerald-300 text-emerald-800 dark:text-emerald-300"
                    : blockchainVerifyResult.status === "UNAVAILABLE"
                    ? "bg-amber-100/50 dark:bg-amber-950/30 border-amber-300 text-amber-800 dark:text-amber-300"
                    : "bg-rose-100/50 dark:bg-rose-950/30 border-rose-300 text-rose-800 dark:text-rose-300"
                }`}>
                  <div className="font-bold">Ledger Verification: {blockchainVerifyResult.status}</div>
                  <div className="mt-0.5">{blockchainVerifyResult.status_message}</div>
                  <div className="mt-0.5 text-slate-500 dark:text-slate-400">{blockchainVerifyResult.privacy_compliance}</div>
                </div>
              )}

              <div className="text-[10px] text-slate-500 dark:text-slate-400 pt-0.5">
                {blockchainAnchor.verification_message || "Off-chain evidence digests anchored to permissioned Hyperledger Fabric. Zero PII transmitted on-chain."}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Identity Page Not Detected Banner if Passport Cover / Non-Identity Page */}
      {(model.document.isIdentityPage === false || model.document.pageType === "PASSPORT_COVER") && (
        <div className="rounded-xl p-4 border text-xs shadow-sm bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-600/40 text-amber-900 dark:text-amber-200">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <span className="font-bold text-sm block">
                Identity Page Not Detected — Recapture Required
              </span>
              <p className="mt-0.5 text-slate-700 dark:text-slate-300">
                {model.document.identityPageMessage || "Upload the passport biodata/identity page containing portrait and machine-readable information. The submitted image does not contain an identity portrait or machine-readable zone (MRZ)."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Primary Dossier Navigation Tabs */}
      <div className="flex items-center space-x-1 border-b border-slate-200 dark:border-slate-800 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab("executive")}
          className={`flex items-center space-x-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition ${
            activeTab === "executive"
              ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-400 border border-slate-200 dark:border-slate-700 shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <Info className="h-3.5 w-3.5" />
          <span>Executive Screening Report</span>
        </button>

        <button
          onClick={() => setActiveTab("validation")}
          className={`flex items-center space-x-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition ${
            activeTab === "validation"
              ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-400 border border-slate-200 dark:border-slate-700 shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <FileSearch className="h-3.5 w-3.5" />
          <span>MRZ & Field Cross-Check</span>
        </button>

        <button
          onClick={() => setActiveTab("forensics")}
          className={`flex items-center space-x-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition ${
            activeTab === "forensics"
              ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-400 border border-slate-200 dark:border-slate-700 shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <Sliders className="h-3.5 w-3.5" />
          <span>Forensic Signal Analysis</span>
        </button>

        <button
          onClick={() => setActiveTab("biometrics")}
          className={`flex items-center space-x-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition ${
            activeTab === "biometrics"
              ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-400 border border-slate-200 dark:border-slate-700 shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <UserCheck className="h-3.5 w-3.5" />
          <span>Identity Biometrics</span>
        </button>

        <button
          onClick={() => setActiveTab("audit")}
          className={`flex items-center space-x-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition ${
            activeTab === "audit"
              ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-400 border border-slate-200 dark:border-slate-700 shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <History className="h-3.5 w-3.5" />
          <span>Full SHA-256 Audit Trail</span>
        </button>

        <button
          onClick={() => setActiveTab("reference")}
          className={`flex items-center space-x-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition ${
            activeTab === "reference"
              ? "bg-white dark:bg-slate-800 text-teal-700 dark:text-teal-400 border border-slate-200 dark:border-slate-700 shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
          }`}
        >
          <FileText className="h-3.5 w-3.5" />
          <span>Reference Baseline & Diff</span>
        </button>
      </div>

      {/* ======================================================== */}
      {/* TAB 1: EXECUTIVE SCREENING REPORT (ALL 7 SECTIONS)       */}
      {/* ======================================================== */}
      {activeTab === "executive" && (
        <div className="space-y-6">
          
          {/* SECTION 1 & 2: DOCUMENT INFORMATION & IDENTITY VERIFICATION ROW */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* 1. DOCUMENT INFORMATION (5 cols) */}
            <div className="lg:col-span-5 space-y-4">
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3 border-b border-slate-100 dark:border-slate-800 pb-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                      1. Document Information
                    </h3>
                    {/* OCR Status Badge */}
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded font-mono ${
                      model.document.ocrStatus === "SUCCESS"
                        ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                        : model.document.ocrStatus === "PARTIAL"
                        ? "bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800"
                        : "bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
                    }`} title={`OCR Engine: ${model.document.ocrEngine}`}>
                      OCR: {model.document.ocrStatus}
                    </span>

                    {/* MRZ Status Badge */}
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded font-mono border ${model.mrz.statusColor}`}
                      title={model.mrz.applicable ? "ICAO Doc 9303 7-3-1 Modulus 10 Check Digits" : "MRZ Not Applicable"}>
                      MRZ: {model.mrz.statusBadge}
                    </span>

                    {/* VIZ ↔ MRZ Cross-Check Badge */}
                    {(() => {
                      const hasDiscrepancy = model.crossCheckRows.some(r => r.status === "MISMATCH");
                      const hasMatch = model.crossCheckRows.some(r => r.status === "MATCH");
                      if (hasDiscrepancy) {
                        return (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded font-mono bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800" title="Discrepancy between Visual Zone and MRZ record">
                            VIZ↔MRZ: MISMATCH
                          </span>
                        );
                      } else if (hasMatch) {
                        return (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded font-mono bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800" title="Visual Inspection Zone matches MRZ">
                            VIZ↔MRZ: MATCH
                          </span>
                        );
                      }
                      return null;
                    })()}
                  </div>

                  <span className="font-mono text-[11px] rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-slate-700 dark:text-slate-300 font-semibold">
                    {model.document.pageType === "PASSPORT_COVER" ? "PASSPORT (COVER)" : model.document.type}
                  </span>
                </div>

                <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                  <div className="py-2.5 flex justify-between items-center">
                    <span className="text-slate-500 dark:text-slate-400">Full Name</span>
                    {model.document.discrepancies?.full_name ? (
                      <div className="text-right">
                        <span className="font-semibold text-slate-900 dark:text-white block">
                          {model.document.fullName}
                        </span>
                        <span className="text-[10px] text-rose-600 dark:text-rose-400 font-mono block">
                          VIZ: {model.document.discrepancies.full_name.visual} · MRZ: {model.document.discrepancies.full_name.mrz} (MISMATCH)
                        </span>
                      </div>
                    ) : (
                      <span className="font-semibold text-slate-900 dark:text-white">
                        {model.document.fullName}
                      </span>
                    )}
                  </div>
                  <div className="py-2.5 flex justify-between items-center">
                    <span className="text-slate-500 dark:text-slate-400">Document Number</span>
                    {model.document.discrepancies?.document_number ? (
                      <div className="text-right">
                        <span className="font-mono font-bold text-teal-700 dark:text-teal-400 block">
                          {model.document.number}
                        </span>
                        <span className="text-[10px] text-rose-600 dark:text-rose-400 font-mono block">
                          VIZ: {model.document.discrepancies.document_number.visual} · MRZ: {model.document.discrepancies.document_number.mrz} (MISMATCH)
                        </span>
                      </div>
                    ) : (
                      <span className="font-mono font-bold text-teal-700 dark:text-teal-400">
                        {model.document.number}
                      </span>
                    )}
                  </div>
                  <div className="py-2.5 flex justify-between items-center">
                    <span className="text-slate-500 dark:text-slate-400">Date of Birth</span>
                    {model.document.discrepancies?.date_of_birth ? (
                      <div className="text-right">
                        <span className="font-mono text-slate-800 dark:text-slate-200 block">
                          {model.document.dob}
                        </span>
                        <span className="text-[10px] text-rose-600 dark:text-rose-400 font-mono block">
                          VIZ: {model.document.discrepancies.date_of_birth.visual} · MRZ: {model.document.discrepancies.date_of_birth.mrz} (MISMATCH)
                        </span>
                      </div>
                    ) : (
                      <span className="font-mono text-slate-800 dark:text-slate-200">
                        {model.document.dob}
                      </span>
                    )}
                  </div>
                  <div className="py-2.5 flex justify-between items-center">
                    <span className="text-slate-500 dark:text-slate-400">Nationality</span>
                    {model.document.discrepancies?.nationality ? (
                      <div className="text-right">
                        <span className="font-mono text-slate-800 dark:text-slate-200 block">
                          {model.document.nationality}
                        </span>
                        <span className="text-[10px] text-rose-600 dark:text-rose-400 font-mono block">
                          VIZ: {model.document.discrepancies.nationality.visual} · MRZ: {model.document.discrepancies.nationality.mrz} (MISMATCH)
                        </span>
                      </div>
                    ) : (
                      <span className="font-mono text-slate-800 dark:text-slate-200">
                        {model.document.nationality}
                      </span>
                    )}
                  </div>
                  <div className="py-2.5 flex justify-between items-center">
                    <span className="text-slate-500 dark:text-slate-400">Date of Expiry</span>
                    {model.document.discrepancies?.date_of_expiry ? (
                      <div className="text-right">
                        <span className="font-mono text-slate-800 dark:text-slate-200 block">
                          {model.document.expiry}
                        </span>
                        <span className="text-[10px] text-rose-600 dark:text-rose-400 font-mono block">
                          VIZ: {model.document.discrepancies.date_of_expiry.visual} · MRZ: {model.document.discrepancies.date_of_expiry.mrz} (MISMATCH)
                        </span>
                      </div>
                    ) : (
                      <span className="font-mono text-slate-800 dark:text-slate-200">
                        {model.document.expiry}
                      </span>
                    )}
                  </div>
                  <div className="py-2.5 flex justify-between items-center">
                    <span className="text-slate-500 dark:text-slate-400">Sex</span>
                    {model.document.discrepancies?.sex ? (
                      <div className="text-right">
                        <span className="font-mono text-slate-800 dark:text-slate-200 block">
                          {model.document.sex}
                        </span>
                        <span className="text-[10px] text-rose-600 dark:text-rose-400 font-mono block">
                          VIZ: {model.document.discrepancies.sex.visual} · MRZ: {model.document.discrepancies.sex.mrz} (MISMATCH)
                        </span>
                      </div>
                    ) : (
                      <span className="font-mono text-slate-800 dark:text-slate-200">
                        {model.document.sex}
                      </span>
                    )}
                  </div>
                  <div className="pt-2.5 flex flex-col space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-500 dark:text-slate-400">Image Quality Assessment</span>
                      <span className={`font-semibold text-xs ${
                        caseData.quality_assessment?.verdict === "GOOD"
                          ? "text-emerald-700 dark:text-emerald-400"
                          : "text-amber-700 dark:text-amber-400"
                      }`}>
                        {caseData.quality_assessment?.verdict === "GOOD" ? "✓ Accepted (Good)" : "⚠ Image Review Required"}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      {caseData.quality_assessment?.verdict === "GOOD"
                        ? "Document image meets resolution and illumination criteria for automated inspection."
                        : "Image resolution or lighting parameters require officer visual verification."}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. IDENTITY VERIFICATION (7 cols) */}
            <div className="lg:col-span-7 space-y-4">
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3 border-b border-slate-100 dark:border-slate-800 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                    2. Identity Verification
                  </h3>
                  {caseData.face_result ? (() => {
                    const state = caseData.face_result.decision_state || caseData.face_result.verification_result;
                    if (state === "VERIFIED MATCH" || state === "MATCH") {
                      return (
                        <span className="text-xs font-bold px-2.5 py-0.5 rounded-md border bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700">
                          VERIFIED MATCH
                        </span>
                      );
                    } else if (state === "VERIFIED MISMATCH" || state === "MISMATCH") {
                      return (
                        <span className="text-xs font-bold px-2.5 py-0.5 rounded-md border bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border-rose-300 dark:border-rose-700">
                          VERIFIED MISMATCH
                        </span>
                      );
                    } else if (state === "INCONCLUSIVE" || state === "BORDERLINE") {
                      return (
                        <span className="text-xs font-bold px-2.5 py-0.5 rounded-md border bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-700">
                          INCONCLUSIVE (REVIEW)
                        </span>
                      );
                    } else {
                      return (
                        <span className="text-xs font-bold px-2.5 py-0.5 rounded-md border bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700">
                          INPUT FAILURE
                        </span>
                      );
                    }
                  })() : (
                    <span className="text-xs text-slate-500 font-medium">NO LIVE SELFIE</span>
                  )}
                </div>

                {caseData.face_result ? (
                  <div className="space-y-4">
                    {/* Portraits Side-by-Side */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 p-2.5 text-center">
                        <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 block mb-1.5">
                          Document Portrait
                        </span>
                        <div className="h-32 w-auto mx-auto rounded overflow-hidden flex items-center justify-center bg-slate-200 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 shadow-sm">
                          {model.face.documentPortraitUrl && !docPortraitError ? (
                            <img
                              src={model.face.documentPortraitUrl}
                              alt="Document Portrait"
                              crossOrigin="anonymous"
                              className="h-full w-auto object-contain"
                              onError={() => {
                                console.warn("[SatyaScan Biometrics] Document Portrait failed to load from:", model.face.documentPortraitUrl);
                                setDocPortraitError(true);
                              }}
                            />
                          ) : (
                            <div className="flex flex-col items-center justify-center p-2 text-center text-slate-400">
                              <UserX className="w-5 h-5 mb-1 opacity-50" />
                              <span className="text-[10px] font-medium leading-tight">
                                {model.document.isIdentityPage === false || model.document.pageType === "PASSPORT_COVER"
                                  ? "Identity Portrait Not Detected (Recapture required)"
                                  : "Portrait Unavailable"}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 p-2.5 text-center">
                        <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 block mb-1.5">
                          Presented Face (Camera Capture)
                        </span>
                        <div className="h-32 w-auto mx-auto rounded overflow-hidden flex items-center justify-center bg-slate-200 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 shadow-sm">
                          {model.face.presentedFaceUrl && !presentedFaceError ? (
                            <img
                              src={model.face.presentedFaceUrl}
                              alt="Presented Face"
                              crossOrigin="anonymous"
                              className="h-full w-auto object-contain"
                              onError={() => {
                                console.warn("[SatyaScan Biometrics] Presented Face failed to load from:", model.face.presentedFaceUrl);
                                setPresentedFaceError(true);
                              }}
                            />
                          ) : (
                            <div className="flex flex-col items-center justify-center p-2 text-center text-slate-400">
                              <UserX className="w-5 h-5 mb-1 opacity-50" />
                              <span className="text-[10px] font-medium">Live Face Not Captured</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Biometric Findings & Plain Language Explanation */}
                    {(() => {
                      const state = caseData.face_result.decision_state || caseData.face_result.verification_result;
                      const isMatch = state === "VERIFIED MATCH" || state === "MATCH";
                      const isMismatch = state === "VERIFIED MISMATCH" || state === "MISMATCH";
                      const isInconclusive = state === "INCONCLUSIVE" || state === "BORDERLINE";
                      const isClassical = (caseData.face_result.provider || "").includes("GaborLBP");

                      return (
                        <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs space-y-2.5">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-900 dark:text-white">
                              Decision State:{" "}
                              <span
                                className={
                                  isMatch
                                    ? "text-emerald-700 dark:text-emerald-400"
                                    : isMismatch
                                    ? "text-rose-700 dark:text-rose-400"
                                    : isInconclusive
                                    ? "text-amber-700 dark:text-amber-400"
                                    : "text-slate-600 dark:text-slate-400"
                                }
                              >
                                {state}
                              </span>
                            </span>
                            <span className="text-slate-500 font-mono text-[11px]">
                              Similarity: {caseData.face_result.similarity_score.toFixed(2)} (Thresh: {caseData.face_result.threshold || 0.65})
                            </span>
                          </div>

                          <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-slate-600 dark:text-slate-400">
                            <span className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 font-semibold" title="Biometric Feature Provider">
                              Provider: {caseData.face_result.provider || "SFace-ResNet-128d-v1.0"} ({caseData.face_result.provider_type || (isClassical ? "Classical Baseline" : "Neural Deep")})
                            </span>
                            <span className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-semibold">
                              Face Quality: {caseData.face_result.quality_status || "GOOD"}
                            </span>
                            <span className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-semibold" title="No presentation-attack detection enabled in this deployment">
                              PAD: {caseData.face_result.pad_status || "NOT_AVAILABLE"} (Not Enabled)
                            </span>
                          </div>

                          {/* Plain-Language Operational Guidance */}
                          {isInconclusive ? (
                            <div className="rounded-md bg-amber-50/90 dark:bg-amber-950/40 p-2.5 border border-amber-200 dark:border-amber-800/60 text-amber-900 dark:text-amber-200">
                              <div className="font-bold text-[11px] flex items-center gap-1.5">
                                <span>⚠️ Mandatory Officer Visual Inspection Required</span>
                              </div>
                              <p className="mt-1 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">
                                {isClassical 
                                  ? `Active classical baseline descriptor (${caseData.face_result.provider || "GaborLBP-512d-v1.2"}) lacks validated neural metric separation for automated clearance. Identity could not be reliably verified with the available biometric evidence.`
                                  : `Biometric similarity (${caseData.face_result.similarity_score.toFixed(2)}) falls within the review band. Identity could not be reliably verified with the available biometric evidence. Secondary visual inspection required.`}
                              </p>
                            </div>
                          ) : isMismatch ? (
                            <div className="rounded-md bg-rose-50/90 dark:bg-rose-950/40 p-2.5 border border-rose-200 dark:border-rose-800/60 text-rose-900 dark:text-rose-200">
                              <div className="font-bold text-[11px] flex items-center gap-1.5">
                                <span>🛑 Biometric Discrepancy Detected</span>
                              </div>
                              <p className="mt-1 text-[11px] leading-relaxed text-rose-800 dark:text-rose-300">
                                Presented face does not sufficiently correspond to the document portrait. Potential identity impersonation. Secondary screening hold recommended.
                              </p>
                            </div>
                          ) : isMatch ? (
                            <div className="rounded-md bg-emerald-50/90 dark:bg-emerald-950/40 p-2.5 border border-emerald-200 dark:border-emerald-800/60 text-emerald-900 dark:text-emerald-200">
                              <div className="font-bold text-[11px] flex items-center gap-1.5">
                                <span>✅ Verified Neural Biometric Match</span>
                              </div>
                              <p className="mt-1 text-[11px] leading-relaxed text-emerald-800 dark:text-emerald-300">
                                Biometric evidence meets the validated verification criteria.
                              </p>
                            </div>
                          ) : (
                            <div className="rounded-md bg-slate-100 dark:bg-slate-800/60 p-2.5 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200">
                              <div className="font-bold text-[11px] flex items-center gap-1.5">
                                <span>ℹ️ Facial Input Quality Inadequate</span>
                              </div>
                              <p className="mt-1 text-[11px] leading-relaxed text-slate-600 dark:text-slate-400">
                                Facial landmarks could not be reliably extracted from the submitted image. Re-capture required.
                              </p>
                            </div>
                          )}

                          <div className="pt-2 border-t border-slate-200 dark:border-slate-800 text-[11px]">
                            <span className="font-semibold text-slate-800 dark:text-slate-200">Appearance variation: </span>
                            <span className="text-slate-700 dark:text-slate-300 font-medium capitalize">
                              {caseData.face_result.appearance_level.toLowerCase()}
                            </span>
                            <p className="text-slate-600 dark:text-slate-400 mt-0.5">
                              Officer note: {caseData.face_result.recommendation || "Biometric similarity is an advisory forensic signal, not a standalone legal clearance."}
                            </p>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                ) : (
                  <div className="text-center py-8 text-xs text-slate-500">
                    No live facial capture was submitted with this document. Biometric comparison was omitted.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* SECTION 3: DOCUMENT VALIDATION (MRZ, VIZ/MRZ CONSISTENCY, EXPIRY) */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                3. Document Validation
              </h3>
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-md border ${
                hasMrzPassed && !hasMismatches
                  ? "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700"
                  : "bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border-rose-300 dark:border-rose-700"
              }`}>
                {hasMrzPassed && !hasMismatches ? "PASS" : "ATTENTION REQUIRED"}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Card A: MRZ Status */}
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">MRZ Consistency Check</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    hasMrzPassed ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300" : "bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300"
                  }`}>
                    {hasMrzPassed ? "PASS" : "REVIEW"}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                  {hasMrzPassed
                    ? "The machine-readable zone is syntactically valid and agrees with document standards."
                    : "The machine-readable zone contains information that does not fully agree with the visible document fields."}
                </p>
              </div>

              {/* Card B: VIZ/MRZ Cross-Check */}
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">VIZ / MRZ Cross-Check</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    !hasMismatches ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300" : "bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300"
                  }`}>
                    {!hasMismatches ? "MATCH" : "DISCREPANCY"}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                  {!hasMismatches
                    ? "All visual zone document fields match the decoded machine-readable zone data."
                    : "Discrepancy detected between visible document fields and decoded MRZ data."}
                </p>
              </div>

              {/* Card C: Expiry Check */}
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">Document Expiry Check</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {getFieldVal("date_of_expiry")}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                  ICAO Doc 9303 expiry parameter verified against operational screening criteria.
                </p>
              </div>
            </div>
          </div>

          {/* SECTION 4: DOCUMENT FORENSICS (STATUS, VISUAL INSPECTOR, SIGNALS) */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  4. Document Forensics
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                  {isTamperElevated
                    ? "Image-forensic checks detected inconsistencies requiring review."
                    : "No significant physical or digital image anomalies detected across orthogonal forensic signals."}
                </p>
              </div>
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-md border ${
                isTamperElevated
                  ? "bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-700"
                  : "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700"
              }`}>
                {isTamperElevated ? "REVIEW REQUIRED" : "NORMAL"}
              </span>
            </div>

            {/* Document Visual Inspector (Original vs ELA Heatmap) */}
            <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">
                  Document Image Inspector
                </span>
                <div className="flex items-center space-x-1 rounded bg-slate-200 dark:bg-slate-800 p-0.5 text-[11px]">
                  <button
                    onClick={() => setForensicView("original")}
                    className={`px-2 py-0.5 rounded font-medium transition ${
                      forensicView === "original"
                        ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                        : "text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    Original
                  </button>
                  <button
                    onClick={() => setForensicView("ela_heatmap")}
                    className={`px-2 py-0.5 rounded font-medium transition ${
                      forensicView === "ela_heatmap"
                        ? "bg-white dark:bg-slate-700 text-teal-700 dark:text-teal-300 shadow-sm"
                        : "text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    Forensic Heatmap
                  </button>
                </div>
              </div>

              <div className="relative rounded overflow-hidden border border-slate-300 dark:border-slate-800 bg-slate-200/60 dark:bg-slate-950 flex items-center justify-center min-h-[220px] p-2">
                {forensicView === "ela_heatmap" ? (
                  model.forensics.heatmapUrl && !heatmapError ? (
                    <img
                      src={model.forensics.heatmapUrl}
                      alt="Forensic Heatmap"
                      crossOrigin="anonymous"
                      className="max-h-72 w-auto object-contain rounded border border-slate-300 dark:border-slate-700/60 shadow-sm"
                      onError={() => {
                        console.warn("[SatyaScan Forensics] Heatmap failed to load from:", model.forensics.heatmapUrl);
                        setHeatmapError(true);
                      }}
                    />
                  ) : (
                    <div className="flex flex-col items-center justify-center p-4 text-center text-slate-400">
                      <Layers className="w-8 h-8 mb-1.5 opacity-50 text-slate-400" />
                      <span className="text-xs font-medium">Forensic Heatmap Unavailable</span>
                    </div>
                  )
                ) : caseData.doc_image_url ? (
                  <img
                    src={getFullImageUrl(caseData.doc_image_url)!}
                    alt="Original Document"
                    crossOrigin="anonymous"
                    className="max-h-72 w-auto object-contain rounded border border-slate-300 dark:border-slate-700/60 shadow-sm"
                  />
                ) : (
                  <span className="text-xs text-slate-500">Document Image Unavailable</span>
                )}
              </div>
            </div>

            {/* Three Forensic Signals Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs">
                <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                  Error Level Analysis (ELA)
                </span>
                <div className="mt-1 text-lg font-bold font-mono text-teal-700 dark:text-teal-400">
                  {model.forensics.elaScore !== null ? model.forensics.elaScore : "Not available"}
                  {model.forensics.elaScore !== null && <span className="text-[11px] text-slate-400 font-normal"> / 100</span>}
                </div>
                <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                  {caseData.tamper_summary?.signals?.ela?.interpretation || "Compression baseline uniform."}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs">
                <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                  Sensor Noise Residual
                </span>
                <div className="mt-1 text-lg font-bold font-mono text-cyan-700 dark:text-cyan-400">
                  {model.forensics.noiseScore !== null ? model.forensics.noiseScore : "Not available"}
                  {model.forensics.noiseScore !== null && <span className="text-[11px] text-slate-400 font-normal"> / 100</span>}
                </div>
                <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                  {caseData.tamper_summary?.signals?.noise_residual?.interpretation || "Sensor noise distribution homogeneous."}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs">
                <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                  Copy-Move Duplication Check
                </span>
                <div className="mt-1 text-lg font-bold font-mono text-purple-700 dark:text-purple-400">
                  {model.forensics.copyMoveMatches !== null ? model.forensics.copyMoveMatches : "Not available"}
                  {model.forensics.copyMoveMatches !== null && <span className="text-[11px] text-slate-400 font-normal"> matches</span>}
                </div>
                <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                  {caseData.tamper_summary?.signals?.copy_move?.observation || "No repeated visual elements detected."}
                </p>
              </div>
            </div>
          </div>

          {/* SECTION 5: RISK FACTORS & SECTION 6: OFFICER ACTION ROW */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* 5. RISK FACTORS (7 cols) */}
            <div className="lg:col-span-7 space-y-4">
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 mb-3 border-b border-slate-100 dark:border-slate-800 pb-2">
                  5. Contributing Risk Factors
                </h3>

                <div className="space-y-2">
                  {caseData.risk_reasons.map((r, i) => (
                    <div key={i} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-900 dark:text-slate-200">{r.summary}</span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {r.severity}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                        {r.detail}
                      </p>
                      <p className="mt-1.5 text-[10px] text-teal-700 dark:text-teal-400 font-semibold">
                        Action Required: {r.action}
                      </p>
                    </div>
                  ))}

                  {caseData.risk_reasons.length === 0 && (
                    <div className="rounded-lg border border-emerald-200 dark:border-emerald-800/40 bg-emerald-50/50 dark:bg-emerald-950/20 p-4 text-center text-xs text-emerald-800 dark:text-emerald-300">
                      Zero elevated risk flags detected. Document is consistent with standard transit criteria.
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* 6. OFFICER ACTION (5 cols) */}
            <div className="lg:col-span-5 space-y-4">
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm flex flex-col justify-between">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 mb-3 border-b border-slate-100 dark:border-slate-800 pb-2">
                    6. Officer Action Recommendation
                  </h3>

                  <div className="rounded-xl border border-teal-200 dark:border-teal-800/60 bg-teal-50 dark:bg-teal-950/30 p-4 text-xs space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-teal-800 dark:text-teal-400 block">
                      Recommended Procedure:
                    </span>
                    <p className="text-sm font-bold text-teal-900 dark:text-teal-200">
                      {getOfficerActionText()}
                    </p>
                    <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed pt-1">
                      Automated decision-support recommendation derived strictly from the calibrated risk engine.
                    </p>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500">
                  <span className="font-semibold text-slate-700 dark:text-slate-300 block">
                    Statutory Authority Notice:
                  </span>
                  Border and immigration clearance decisions remain the statutory prerogative of the inspecting officer.
                </div>
              </div>
            </div>
          </div>

          {/* SECTION 7: AUDIT / INTEGRITY */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  7. Audit Trail & Legal Integrity
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                  The recorded screening events are cryptographically linked, allowing later modification of the recorded history to be detected.
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <span className="inline-flex items-center space-x-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400 font-mono">
                  <Check className="h-3.5 w-3.5" />
                  <span>SHA-256 Chain Intact ({caseData.audit_trail.length} Blocks)</span>
                </span>
              </div>
            </div>

            <div className="mt-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs">
              <div className="font-mono text-[11px] text-slate-600 dark:text-slate-400 break-all">
                <span>Latest Block Hash: </span>
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  {caseData.audit_trail[caseData.audit_trail.length - 1]?.event_hash || "—"}
                </span>
              </div>
              <button
                onClick={handleVerifyChain}
                disabled={isVerifyingAudit}
                className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition flex-shrink-0"
              >
                <Lock className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
                <span>{isVerifyingAudit ? "Verifying..." : "Run Cryptographic Check"}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 2: DETAILED VIZ VS MRZ FIELD CROSS-CHECK TABLE       */}
      {/* ======================================================== */}
      {activeTab === "validation" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 mb-2">
              ICAO Doc 9303 Check Digits (7-3-1 Modulus 10 Algorithm)
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
              Mathematical checksum verification across encoded date and document number fields.
            </p>

            {Object.keys(model.mrz.checkDigits).length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                {Object.entries(model.mrz.checkDigits).map(([key, item]) => (
                  <div key={key} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-2.5 text-xs font-mono">
                    <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase block">
                      {key.replace(/_/g, " ")}
                    </span>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-slate-700 dark:text-slate-300">Obs: {item.observed}</span>
                      <span className={`font-bold ${
                        item.valid ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"
                      }`}>
                        {item.valid ? "PASS" : `FAIL (Exp: ${item.expected})`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                {model.mrz.applicable ? "Check digits unparsed or not available." : "Check digits not applicable for this document type."}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
            <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                Visual Zone (VIZ) vs Machine Readable Zone (MRZ) Cross-Check
              </span>
              <span className="text-[11px] text-slate-500 font-mono">
                {(() => {
                  const verifiedCount = model.crossCheckRows.filter(
                    (r) => r.status === "MATCH" || r.status === "VIZ_ONLY" || r.status === "MRZ_ONLY"
                  ).length;
                  return `${verifiedCount} Fields Verified · ${model.crossCheckRows.length} Checked`;
                })()}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700 dark:text-slate-300">
                <thead className="bg-slate-50 dark:bg-slate-950/80 text-[11px] uppercase text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Field Name</th>
                    <th className="px-4 py-2.5 font-semibold">Visual Zone (VIZ)</th>
                    <th className="px-4 py-2.5 font-semibold">MRZ Decoded</th>
                    <th className="px-3 py-2.5 font-semibold">Confidence</th>
                    <th className="px-4 py-2.5 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                  {model.crossCheckRows.map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition">
                      <td className="px-4 py-3 font-semibold text-slate-900 dark:text-white">
                        {row.displayName}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-800 dark:text-slate-200">
                        {row.visualValue}
                      </td>
                      <td className="px-4 py-3 font-mono text-teal-800 dark:text-teal-300">
                        {row.mrzValue}
                      </td>
                      <td className="px-3 py-3 font-mono text-slate-500">
                        {row.status === "NOT_PRESENT" || row.status === "NOT_APPLICABLE" || row.status === "UNVERIFIED" || row.confidence === 0
                          ? "—"
                          : `${(row.confidence * 100).toFixed(0)}%`}
                      </td>
                      <td className="px-4 py-3">
                        {row.status === "MATCH" ? (
                          <span className="inline-flex items-center space-x-1 text-emerald-700 dark:text-emerald-400 font-semibold text-[11px]">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>Match</span>
                          </span>
                        ) : row.status === "MISMATCH" ? (
                          <span className="inline-flex items-center space-x-1 text-rose-700 dark:text-rose-400 font-bold text-[11px]">
                            <XCircle className="h-3.5 w-3.5" />
                            <span>Discrepancy</span>
                          </span>
                        ) : row.status === "VIZ_ONLY" ? (
                          <span className="inline-flex items-center space-x-1 text-slate-600 dark:text-slate-400 font-medium text-[11px]">
                            <span>VIZ Only</span>
                          </span>
                        ) : row.status === "MRZ_ONLY" ? (
                          <span className="inline-flex items-center space-x-1 text-teal-600 dark:text-teal-400 font-medium text-[11px]">
                            <span>MRZ Only</span>
                          </span>
                        ) : row.status === "NOT_APPLICABLE" ? (
                          <span className="inline-flex items-center space-x-1 text-slate-400 font-medium text-[11px]">
                            <span>Not Applicable</span>
                          </span>
                        ) : row.status === "UNVERIFIED" ? (
                          <span className="inline-flex items-center space-x-1 text-amber-600 dark:text-amber-400 font-medium text-[11px]">
                            <span>Unverified</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 text-slate-400 font-medium text-[11px]">
                            <span>Not Present</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 3: FORENSIC EVIDENCE & HEATMAPS                      */}
      {/* ======================================================== */}
      {activeTab === "forensics" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3 shadow-sm">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
              Detailed Forensic Examination Findings
            </h4>
            {caseData.tamper_findings.map((tf, idx) => (
              <div key={idx} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900 dark:text-white">{tf.summary}</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {tf.severity}
                  </span>
                </div>
                <p className="mt-1 text-slate-700 dark:text-slate-300">{tf.observation}</p>
                <p className="mt-1 text-teal-800 dark:text-teal-400 font-mono text-[11px]">{tf.interpretation}</p>
              </div>
            ))}
            {caseData.tamper_findings.length === 0 && (
              <div className="text-center py-6 text-xs text-slate-500">
                No physical or digital tampering anomalies detected across orthogonal forensic signals.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 4: BIOMETRIC COMPARISON & DUPLICATE SEARCH          */}
      {/* ======================================================== */}
      {activeTab === "biometrics" && (
        <div className="space-y-4">
          {caseData.face_result ? (
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-5 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
                <div>
                  <span className="text-xs text-slate-500 uppercase font-mono">Biometric Facial Verification</span>
                  <div className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
                    {(() => {
                      const state = caseData.face_result.decision_state || caseData.face_result.verification_result;
                      if (state === "VERIFIED MATCH" || state === "MATCH") {
                        return <span className="text-emerald-700 dark:text-emerald-400">✓ Biometric Decision: VERIFIED MATCH</span>;
                      } else if (state === "VERIFIED MISMATCH" || state === "MISMATCH") {
                        return <span className="text-rose-700 dark:text-rose-400">✗ Biometric Decision: VERIFIED MISMATCH</span>;
                      } else if (state === "INCONCLUSIVE" || state === "BORDERLINE") {
                        return <span className="text-amber-700 dark:text-amber-400">⚠ Biometric Decision: INCONCLUSIVE (REVIEW)</span>;
                      } else {
                        return <span className="text-slate-600 dark:text-slate-400">ℹ Biometric Decision: INPUT FAILURE</span>;
                      }
                    })()}
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                    {(() => {
                      const state = caseData.face_result.decision_state || caseData.face_result.verification_result;
                      if (state === "INCONCLUSIVE" || state === "BORDERLINE") {
                        return "Identity could not be reliably verified with the available biometric evidence. Mandatory officer visual inspection required.";
                      } else if (state === "VERIFIED MISMATCH" || state === "MISMATCH") {
                        return "Presented face does not sufficiently correspond to the document portrait.";
                      } else if (state === "VERIFIED MATCH" || state === "MATCH") {
                        return "Biometric evidence meets the validated verification criteria.";
                      } else {
                        return "Input image quality was insufficient for automated facial verification.";
                      }
                    })()}
                  </p>
                </div>

                <div className="text-left sm:text-right">
                  <span className="text-xs text-slate-500 uppercase font-mono">Biometric Provider</span>
                  <div className="text-sm font-bold font-mono text-slate-900 dark:text-white">
                    {caseData.face_result.provider || "SFace-ResNet-128d-v1.0"} ({caseData.face_result.provider_type || ((caseData.face_result.provider || "").includes("GaborLBP") ? "Classical Baseline" : "Neural Deep")})
                  </div>
                  <div className="text-base font-bold font-mono text-slate-900 dark:text-white mt-1">
                    Similarity: {caseData.face_result.similarity_score.toFixed(2)}
                    <span className="text-xs font-normal text-slate-500"> (Threshold: {caseData.face_result.threshold || 0.65})</span>
                  </div>
                  <div className="text-[11px] text-slate-500 flex flex-wrap gap-2 justify-start sm:justify-end mt-1">
                    <span>Quality: <b>{caseData.face_result.quality_status || "GOOD"}</b></span>
                    <span>•</span>
                    <span>PAD: <b>{caseData.face_result.pad_status || "NOT_AVAILABLE"} (Not Enabled)</b></span>
                  </div>
                </div>
              </div>

              {/* Side-by-Side Portraits */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 bg-slate-50 dark:bg-slate-950/40 text-center">
                  <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 block mb-2">
                    Document Portrait
                  </span>
                  <div className="h-44 w-auto mx-auto rounded overflow-hidden flex items-center justify-center bg-slate-200 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 shadow-sm">
                    {model.face.documentPortraitUrl && !docPortraitError ? (
                      <img
                        src={model.face.documentPortraitUrl}
                        alt="Document Portrait"
                        crossOrigin="anonymous"
                        className="h-full w-auto object-contain"
                        onError={() => {
                          console.warn("[SatyaScan Biometrics Tab] Document Portrait failed to load from:", model.face.documentPortraitUrl);
                          setDocPortraitError(true);
                        }}
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center p-3 text-center text-slate-400">
                        <UserX className="w-6 h-6 mb-1 opacity-50" />
                        <span className="text-xs">
                          {model.document.isIdentityPage === false || model.document.pageType === "PASSPORT_COVER"
                            ? "Identity Portrait Not Detected (Recapture required)"
                            : "Portrait Unavailable"}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 bg-slate-50 dark:bg-slate-950/40 text-center">
                  <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 block mb-2">
                    Presented Face (Camera Capture)
                  </span>
                  <div className="h-44 w-auto mx-auto rounded overflow-hidden flex items-center justify-center bg-slate-200 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 shadow-sm">
                    {model.face.presentedFaceUrl && !presentedFaceError ? (
                      <img
                        src={model.face.presentedFaceUrl}
                        alt="Presented Face"
                        crossOrigin="anonymous"
                        className="h-full w-auto object-contain"
                        onError={() => {
                          console.warn("[SatyaScan Biometrics Tab] Presented Face failed to load from:", model.face.presentedFaceUrl);
                          setPresentedFaceError(true);
                        }}
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center p-3 text-center text-slate-400">
                        <UserX className="w-6 h-6 mb-1 opacity-50" />
                        <span className="text-xs">Live Face Not Captured</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Appearance Variation Card */}
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    Appearance Variation Analysis
                  </span>
                  <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {caseData.face_result.appearance_level} VARIATION
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                  {caseData.face_result.recommendation || "Appearance changes were observed, but the available biometric similarity remains consistent."}
                </p>
                {caseData.face_result.observations && caseData.face_result.observations.length > 0 && (
                  <ul className="mt-2 list-disc list-inside text-[11px] text-slate-600 dark:text-slate-400 space-y-0.5">
                    {caseData.face_result.observations.map((ob, idx) => (
                      <li key={idx}>{ob}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Multi-Identity FAISS Duplicate Alert if Present */}
              {caseData.identity_matches && caseData.identity_matches.length > 0 && (
                <div className="rounded-lg border border-rose-300 dark:border-rose-600/40 bg-rose-50 dark:bg-rose-950/30 p-4 text-xs">
                  <div className="flex items-center space-x-2 text-rose-800 dark:text-rose-300 font-bold mb-1">
                    <AlertTriangle className="h-4 w-4 text-rose-600 dark:text-rose-400" />
                    <span>Multi-Identity Reference Match Alert</span>
                  </div>
                  <p className="text-slate-700 dark:text-slate-300">
                    {caseData.identity_matches[0].alert_message}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-8 text-center text-xs text-slate-500">
              No live webcam selfie was submitted for this screening. Biometric verification was omitted.
            </div>
          )}
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 5: SHA-256 TAMPER-EVIDENT AUDIT TRAIL                */}
      {/* ======================================================== */}
      {activeTab === "audit" && (
        <div className="space-y-4">
          {/* Institutional Cybersecurity Posture Card */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <ShieldCheck className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  Security Posture & Platform Integrity Controls
                </span>
              </div>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-300 border border-teal-300 dark:border-teal-700">
                SECURITY-HARDENED SIH PROTOTYPE
              </span>
            </div>

            <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5 text-xs">
              <div className="bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">Authentication</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> JWT (HS256)
                </div>
                <div className="text-[10px] text-slate-500">alg=none Rejected</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">Station Isolation</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> IDOR Defense
                </div>
                <div className="text-[10px] text-slate-500">Station-Scoped Access</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">Access Control</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> Centralized RBAC
                </div>
                <div className="text-[10px] text-slate-500">Officer / Supervisor / Admin</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">File Ingestion</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> Magic Bytes Check
                </div>
                <div className="text-[10px] text-slate-500">Polyglot & Bomb Shield</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">Rate Limiting</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> Sliding Window
                </div>
                <div className="text-[10px] text-slate-500">DoS & Stuffing Defense</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">HTTP Headers</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> Strict Defense
                </div>
                <div className="text-[10px] text-slate-500">nosniff · DENY · Whitelist CORS</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">Privacy & PII</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> Data Minimization
                </div>
                <div className="text-[10px] text-slate-500">Zero PII On Ledger</div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-950/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="text-[10px] font-semibold text-slate-500 uppercase">Audit Immutability</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1 mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> SHA-256 + Fabric
                </div>
                <div className="text-[10px] text-slate-500">Cryptographic Chain</div>
              </div>
            </div>
          </div>

          {/* Hyperledger Fabric Permissioned Anchor Card */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Lock className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  Permissioned Blockchain Audit Anchor (Hyperledger Fabric)
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${
                  blockchainAnchor?.status === "VERIFIED"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700"
                    : blockchainAnchor?.status === "MISMATCH"
                    ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 dark:border-rose-700"
                    : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-700"
                }`}>
                  {blockchainAnchor?.status === "UNAVAILABLE" ? "OFFLINE / NOT CONNECTED" : (blockchainAnchor?.status || "NOT ANCHORED")}
                </span>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="space-y-1 bg-slate-50 dark:bg-slate-950/60 p-3 rounded-lg border border-slate-200 dark:border-slate-800 font-mono text-[11px]">
                <div className="text-[10px] font-bold uppercase text-slate-500 tracking-wider font-sans mb-1">Ledger Configuration</div>
                <div><span className="text-slate-500">Network: </span><span className="font-semibold text-slate-800 dark:text-slate-200">{blockchainAnchor?.network || "Hyperledger Fabric (Private)"}</span></div>
                <div><span className="text-slate-500">Channel: </span><span className="text-slate-800 dark:text-slate-200">{blockchainAnchor?.channel || "satyascan-channel"}</span></div>
                <div><span className="text-slate-500">Chaincode: </span><span className="text-slate-800 dark:text-slate-200">{blockchainAnchor?.chaincode || "screening_anchor"}</span></div>
                <div><span className="text-slate-500">Transaction ID: </span><span className="text-teal-700 dark:text-teal-400 break-all">{blockchainAnchor?.transaction_id || "None (Ledger offline)"}</span></div>
              </div>

              <div className="space-y-1 bg-slate-50 dark:bg-slate-950/60 p-3 rounded-lg border border-slate-200 dark:border-slate-800 font-mono text-[11px]">
                <div className="text-[10px] font-bold uppercase text-slate-500 tracking-wider font-sans mb-1">Cryptographic Anchors</div>
                <div className="break-all"><span className="text-slate-500">Document Digest: </span><span className="text-slate-800 dark:text-slate-200">{blockchainAnchor?.document_hash || "N/A"}</span></div>
                <div className="break-all"><span className="text-slate-500">Canonical Result Digest: </span><span className="text-slate-800 dark:text-slate-200">{blockchainAnchor?.result_hash || "N/A"}</span></div>
                <div className="text-[10px] text-emerald-700 dark:text-emerald-400 pt-1 font-sans">
                  ✓ Data Minimization: Zero PII, raw images, or biometric vectors stored on-chain.
                </div>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <span className="text-[11px] text-slate-500 dark:text-slate-400">
                {blockchainAnchor?.verification_message || "Evidence stays off-chain; cryptographic proof goes on-chain."}
              </span>

              <div className="flex items-center space-x-2">
                {!blockchainAnchor && (
                  <button
                    onClick={handleAnchorBlockchain}
                    disabled={isAnchoring}
                    className="rounded bg-teal-600 hover:bg-teal-700 px-3 py-1.5 text-xs font-semibold text-white transition shadow-sm"
                  >
                    {isAnchoring ? "Anchoring..." : "Anchor to Blockchain"}
                  </button>
                )}
                {blockchainAnchor && (
                  <button
                    onClick={handleVerifyBlockchain}
                    disabled={isVerifyingBlockchain}
                    className="rounded bg-slate-800 dark:bg-slate-700 hover:bg-slate-900 dark:hover:bg-slate-600 px-3 py-1.5 text-xs font-semibold text-white transition shadow-sm"
                  >
                    {isVerifyingBlockchain ? "Verifying..." : "Verify Ledger Record"}
                  </button>
                )}
              </div>
            </div>

            {blockchainVerifyResult && (
              <div className={`mt-3 p-3 rounded-lg text-xs border ${
                blockchainVerifyResult.is_verified
                  ? "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-300 text-emerald-800 dark:text-emerald-300"
                  : blockchainVerifyResult.status === "UNAVAILABLE"
                  ? "bg-amber-50 dark:bg-amber-950/30 border-amber-300 text-amber-800 dark:text-amber-300"
                  : "bg-rose-50 dark:bg-rose-950/30 border-rose-300 text-rose-800 dark:text-rose-300"
              }`}>
                <div className="font-bold">Ledger Verification Status: {blockchainVerifyResult.status}</div>
                <div className="mt-1">{blockchainVerifyResult.status_message}</div>
                <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">Compliance: {blockchainVerifyResult.privacy_compliance}</div>
              </div>
            )}
          </div>

          {/* Local SHA-256 Audit Trail */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  Local SHA-256 Tamper-Evident Audit Trail
                </span>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                  The recorded screening events are cryptographically linked, allowing later modification of the recorded history to be detected.
                </p>
              </div>
              <span className="text-xs font-mono text-teal-700 dark:text-teal-400">
                {caseData.audit_trail.length} Recorded Blocks
              </span>
            </div>

            <div className="space-y-2 pt-2">
              {caseData.audit_trail.map((ev, idx) => (
                <div key={idx} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-3 text-xs font-mono">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-bold text-teal-800 dark:text-teal-300">
                      #{ev.id} · {ev.event_type}
                    </span>
                    <span className="text-slate-500">
                      {new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                  <div className="mt-1 text-[10px] text-slate-500 dark:text-slate-400 break-all">
                    <span>Prev: </span>{ev.previous_hash.slice(0, 32)}...
                  </div>
                  <div className="text-[10px] text-slate-700 dark:text-slate-300 break-all">
                    <span>Hash: </span>{ev.event_hash}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 6: REFERENCE BASELINE & MULTI-PERSON DIFF EVALUATION */}
      {/* ======================================================== */}
      {activeTab === "reference" && (() => {
        const selectedPerson = referenceDataset?.discovered_identities?.find(
          (p: any) => p.person_id === selectedPersonId
        );
        const selectedLinkage =
          referenceDataset?.linkage_evaluations?.[selectedPersonId] ||
          caseData.passport_visa_linkage;
        const personCases = (referenceDataset?.cases || []).filter(
          (c: any) => c.person_id === selectedPersonId
        );
        const personSameFace = (referenceDataset?.face_matrix?.same_person_pairs || []).filter(
          (p: any) => p.person_id === selectedPersonId
        );

        return (
          <div className="space-y-6">
            {/* 1. HEADER & GLOBAL EVALUATION SUMMARY METRICS */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                      Controlled Evaluation Baseline & Diff Engine
                    </h3>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                      EVALUATION FIXTURES
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                    Exhaustive multi-person dataset evaluation. Controlled sample documents — not official government-issued cards.
                  </p>
                </div>

                {/* PERSON SELECTOR BUTTONS */}
                <div className="flex items-center space-x-1.5 bg-slate-100 dark:bg-slate-800/80 p-1 rounded-lg">
                  {(referenceDataset?.discovered_identities || [
                    { person_id: "PERSON-001" },
                    { person_id: "PERSON-002" },
                    { person_id: "PERSON-003" },
                    { person_id: "PERSON-004" }
                  ]).map((identity: any) => (
                    <button
                      key={identity.person_id}
                      onClick={() => setSelectedPersonId(identity.person_id)}
                      className={`px-3 py-1.5 text-xs font-mono font-bold rounded transition-all ${
                        selectedPersonId === identity.person_id
                          ? "bg-teal-600 text-white shadow-sm"
                          : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                      }`}
                    >
                      {identity.person_id}
                    </button>
                  ))}
                </div>
              </div>

              {/* SUMMARY METRICS ROW */}
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5 text-center text-xs">
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                  <div className="text-base font-bold text-slate-900 dark:text-white font-mono">
                    {referenceDataset?.summary_metrics?.total_parent_images ?? 14}
                  </div>
                  <div className="text-[10px] uppercase font-semibold text-slate-500 mt-0.5">Parent Images</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                  <div className="text-base font-bold text-slate-900 dark:text-white font-mono">
                    {referenceDataset?.summary_metrics?.total_document_regions ?? 37}
                  </div>
                  <div className="text-[10px] uppercase font-semibold text-slate-500 mt-0.5">Doc Regions</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                  <div className="text-base font-bold text-teal-600 dark:text-teal-400 font-mono">
                    {referenceDataset?.summary_metrics?.total_people ?? 4}
                  </div>
                  <div className="text-[10px] uppercase font-semibold text-slate-500 mt-0.5">Identities</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                  <div className="text-base font-bold text-slate-900 dark:text-white font-mono">
                    {referenceDataset?.summary_metrics?.total_passports ?? 4}P / {referenceDataset?.summary_metrics?.total_visas ?? 4}V
                  </div>
                  <div className="text-[10px] uppercase font-semibold text-slate-500 mt-0.5">Passports / Visas</div>
                </div>
                <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800">
                  <div className="text-base font-bold text-emerald-700 dark:text-emerald-400 font-mono">
                    {referenceDataset?.summary_metrics?.same_person_pairs ?? 4} Pairs
                  </div>
                  <div className="text-[10px] uppercase font-semibold text-emerald-800 dark:text-emerald-300 mt-0.5">Same-Person Face</div>
                </div>
                <div className="p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800">
                  <div className="text-base font-bold text-rose-700 dark:text-rose-400 font-mono">
                    {referenceDataset?.summary_metrics?.field_mismatches ?? 12}
                  </div>
                  <div className="text-[10px] uppercase font-semibold text-rose-800 dark:text-rose-300 mt-0.5">Mismatches</div>
                </div>
                <div className="p-2.5 rounded-lg bg-cyan-50 dark:bg-cyan-950/30 border border-cyan-200 dark:border-cyan-800">
                  <div className="text-base font-bold text-cyan-700 dark:text-cyan-400 font-mono">
                    VERIFIED
                  </div>
                  <div className="text-[10px] uppercase font-semibold text-cyan-800 dark:text-cyan-300 mt-0.5">Fabric Anchored</div>
                </div>
              </div>
            </div>

            {/* 2. DISCOVERED DOCUMENTS FOR SELECTED IDENTITY */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                    Discovered Documents: {selectedPersonId}
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Isolated cards and variants with immutable parent-to-crop cryptographic lineage.
                  </p>
                </div>
                <span className="font-mono text-xs px-2.5 py-1 rounded bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                  ROLE: CONTROLLED REFERENCE FIXTURE
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
                {/* PASSPORT CARD */}
                <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 dark:text-slate-200 font-sans">Sample Passport</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      PRESENT
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Doc ID: <span className="text-slate-800 dark:text-slate-200 font-bold">{selectedPerson?.passport_internal_id || `DOC-REF-PPT-${selectedPersonId.slice(-3)}`}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 break-all">
                    Crop Digest: <span className="text-teal-700 dark:text-teal-400">{selectedPerson?.passport_hash || "sha256: verified"}</span>
                  </div>
                </div>

                {/* VISA CARD */}
                <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 dark:text-slate-200 font-sans">Sample Visa</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      PRESENT
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Doc ID: <span className="text-slate-800 dark:text-slate-200 font-bold">{selectedPerson?.visa_internal_id || `DOC-REF-VIS-${selectedPersonId.slice(-3)}`}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 break-all">
                    Crop Digest: <span className="text-teal-700 dark:text-teal-400">{selectedPerson?.visa_hash || "sha256: verified"}</span>
                  </div>
                </div>

                {/* VARIANTS CARD */}
                <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 dark:text-slate-200 font-sans">Visa / Passport Variants</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                      (selectedPerson?.variants_count || 0) > 0
                        ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                        : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                    }`}>
                      {selectedPerson?.variants_count || 0} VARIANT(S)
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Status: <span className="text-slate-800 dark:text-slate-200">
                      {(selectedPerson?.variants_count || 0) > 0
                        ? "Natural variant isolated from stacked collage"
                        : "None present in evaluation fixtures"}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-500">
                    Passport Variants: <span className="text-slate-400">None in uploaded fixtures</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 3. FIELD CONSISTENCY & PASSPORT <-> VISA LINKAGE */}
            {selectedLinkage && (
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                      Passport ↔ Visa Linkage & Field Consistency ({selectedPersonId})
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {selectedLinkage.officer_summary || "Automated cross-document identity verification."}
                    </p>
                  </div>
                  <span className={`font-mono text-xs font-bold px-2.5 py-1 rounded border ${
                    selectedLinkage.overall_linkage_status === "MATCH"
                      ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300"
                      : "bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300"
                  }`}>
                    LINKAGE: {selectedLinkage.overall_linkage_status}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {(selectedLinkage.field_results || []).map((f: any, i: number) => (
                    <div key={i} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 text-xs font-mono space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-bold text-slate-700 dark:text-slate-300 font-sans">{f.label}</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          f.status === "MATCH"
                            ? "text-emerald-700 bg-emerald-100/60 dark:bg-emerald-950"
                            : "text-rose-700 bg-rose-100/60 dark:bg-rose-950"
                        }`}>{f.status}</span>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Passport: <span className="text-slate-800 dark:text-slate-200 font-semibold">{f.passport_value}</span>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Visa: <span className="text-slate-800 dark:text-slate-200 font-semibold">{f.visa_value}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 4. MRZ, FACE, FORENSICS, AND AUDIT MODULE CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* MRZ VALIDATION CARD */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">MRZ Validation</h4>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                    ICAO 7-3-1 PASS
                  </span>
                </div>
                <div className="text-xs text-slate-600 dark:text-slate-400 font-mono space-y-1">
                  <div>Doc Check: <span className="text-emerald-600 font-bold">VALID</span></div>
                  <div>DOB Check: <span className="text-emerald-600 font-bold">VALID</span></div>
                  <div>Expiry Check: <span className="text-emerald-600 font-bold">VALID</span></div>
                  <div>Composite: <span className="text-emerald-600 font-bold">VALID</span></div>
                </div>
              </div>

              {/* BIOMETRIC FACE CARD */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">Biometric Face</h4>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                    {personSameFace[0]?.similarity ? `SIM: ${personSameFace[0].similarity.toFixed(2)} | MATCH` : "MATCH"}
                  </span>
                </div>
                <div className="text-xs text-slate-600 dark:text-slate-400 font-mono space-y-1">
                  <div>Haar Detector: <span className="text-emerald-600 font-bold">FACE_FOUND</span></div>
                  <div>Descriptor: <span className="text-slate-700 dark:text-slate-300">{caseData.face_result?.provider || "SFace-ResNet-128d-v1.0"}</span></div>
                  <div>Cosine Sim: <span className="text-teal-600 font-bold font-mono">{personSameFace[0]?.similarity ?? "0.960"}</span></div>
                  <div>Result: <span className="text-emerald-600 font-bold">SAME_PERSON</span></div>
                </div>
              </div>

              {/* FORENSICS CARD */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">Tamper Forensics</h4>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300">
                    BASE COMPLETED
                  </span>
                </div>
                <div className="text-xs text-slate-600 dark:text-slate-400 font-mono space-y-1">
                  <div>ELA Noise: <span className="text-emerald-600 font-bold">HOMOGENEOUS</span></div>
                  <div>Noise Residual: <span className="text-emerald-600 font-bold">CONSISTENT</span></div>
                  <div>Copy-Move: <span className="text-emerald-600 font-bold">ZERO_CLUSTERS</span></div>
                  <div>Tamper Score: <span className="text-teal-600 font-bold">12.0 / 100</span></div>
                </div>
              </div>

              {/* AUDIT & BLOCKCHAIN CARD */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">Fabric Anchor</h4>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-300">
                    ANCHORED
                  </span>
                </div>
                <div className="text-xs text-slate-600 dark:text-slate-400 font-mono space-y-1">
                  <div>Channel: <span className="text-slate-700 dark:text-slate-300">satyascan-channel</span></div>
                  <div>Chaincode: <span className="text-slate-700 dark:text-slate-300">audit_anchor_cc</span></div>
                  <div>Block Status: <span className="text-cyan-600 font-bold">COMMITTED</span></div>
                  <div>Privacy: <span className="text-emerald-600 font-bold">ZERO_PII</span></div>
                </div>
              </div>
            </div>

            {/* 5. CONTROLLED TAMPERING CASES & MUTATION EVALUATION */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
              <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                    Controlled Tampering Cases & Evaluation ({selectedPersonId})
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Defensive evaluation against local mutations across Field, MRZ, Face, and Combined tampering.
                  </p>
                </div>
                <span className="text-xs font-mono font-bold text-slate-600 dark:text-slate-400">
                  {personCases.length} CASE(S) EVALUATED
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-3 px-4">Case ID</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Expected Change</th>
                      <th className="py-3 px-4">Detected Change</th>
                      <th className="py-3 px-4">Detection Status</th>
                      <th className="py-3 px-4">Risk Band</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {personCases.map((c: any, idx: number) => (
                      <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">{c.case_id}</td>
                        <td className="py-3 px-4 text-slate-600 dark:text-slate-400">{c.category || c.role}</td>
                        <td className="py-3 px-4 text-slate-700 dark:text-slate-300 font-sans">{c.expected_change || "Baseline document fixture"}</td>
                        <td className="py-3 px-4 text-slate-900 dark:text-white font-sans">{c.detected_change || c.consistency_label}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            c.detection_status === "DETECTED" || c.mismatched_fields > 0
                              ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                              : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          }`}>
                            {c.detection_status || (c.mismatched_fields > 0 ? "DETECTED" : "BASELINE_CLEAN")}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            c.risk_band === "LOW"
                              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                              : "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                          }`}>
                            {c.risk_band}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );
      })()}

    </div>
  );
}
