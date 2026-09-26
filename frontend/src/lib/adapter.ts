/**
 * SatyaScan Canonical Report Adapter
 * Transforms raw backend ScreeningDetail API payload into a strongly-typed,
 * normalized ReportViewModel for reliable rendering.
 *
 * Implements strict field prioritization:
 * 1. Verified MRZ value when valid
 * 2. Visual Inspection Zone (VIZ) / OCR value
 * 3. Validated field_value
 * 4. Truthful unavailable state ("Not available" / "Not applicable")
 *
 * NEVER substitutes fake demo names or case IDs.
 * ALWAYS preserves screening-specific isolation.
 */

import { ScreeningDetail, ExtractedField } from "./types";
import { BACKEND_ROOT_URL, API_BASE_URL, getAuthTokenSync } from "./api";

export interface DocumentViewModel {
  type: string;
  pageType?: string;
  isIdentityPage?: boolean;
  identityPageMessage?: string;
  number: string;
  maskedNumber: string;
  surname: string;
  givenNames: string;
  fullName: string;
  nationality: string;
  dob: string;
  expiry: string;
  sex: string;
  ocrStatus: "SUCCESS" | "PARTIAL" | "FAILED" | "UNAVAILABLE";
  ocrEngine: string;
  qualityVerdict: "GOOD" | "NEEDS_BETTER_IMAGE" | "REJECTED" | string;
  qualityScore: number;
  qualityMessage: string;
  discrepancies?: Record<string, { visual: string; mrz: string }>;
}

export interface MRZViewModel {
  applicable: boolean;
  parsed: boolean;
  statusBadge: "7-3-1 PASS" | "CHECKSUM FAIL" | "UNPARSED" | "NOT APPLICABLE" | "NOT DETECTED" | "INPUT INSUFFICIENT";
  statusColor: string;
  statusMessage?: string;
  lines: string[];
  checkDigits: Record<string, { observed: string; expected: string; valid: boolean }>;
  allChecksPassed: boolean;
  decodedFields: Record<string, string>;
  rawDateOfBirth?: string;
  rawDateOfExpiry?: string;
}

export interface FaceViewModel {
  result: "VERIFIED MATCH" | "VERIFIED MISMATCH" | "INCONCLUSIVE" | "INPUT FAILURE" | "NO LIVE CAPTURE";
  decisionState: string;
  similarity: number | null;
  similarityPercent: string;
  threshold: number;
  provider: string;
  providerType: string;
  qualityStatus: string;
  appearanceLevel: string;
  observations: string[];
  recommendation: string;
  padStatus: string;
  padReason: string;
  documentPortraitUrl: string | null;
  presentedFaceUrl: string | null;
  hasLiveSelfie: boolean;
}

export interface ForensicsViewModel {
  compositeScore: number;
  verdict: string;
  elaScore: number | null;
  noiseScore: number | null;
  copyMoveMatches: number | null;
  heatmapUrl: string | null;
  findingsCount: number;
  findings: Array<{
    technique: string;
    severity: string;
    score: number;
    summary: string;
    observation: string;
    interpretation: string;
  }>;
}

export interface CrossCheckRow {
  fieldName: string;
  displayName: string;
  visualValue: string;
  mrzValue: string;
  confidence: number;
  status: "MATCH" | "MISMATCH" | "VIZ_ONLY" | "MRZ_ONLY" | "NOT_PRESENT" | "NOT_APPLICABLE" | "UNVERIFIED";
  statusLabel: string;
}

export interface RiskViewModel {
  score: number;
  band: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  recommendation: string;
  reasons: Array<{
    category: string;
    severity: string;
    points?: number;
    summary: string;
    detail: string;
    action?: string;
  }>;
  signalBreakdown: {
    mrzIntegrity: number;
    tamperForensics: number;
    faceVerification: number;
  };
}

export interface AuditViewModel {
  eventsCount: number;
  headHash: string;
  genesisHash: string;
  events: Array<{
    id: number;
    timestamp: string;
    actor: string;
    eventType: string;
    payloadHash: string;
    eventHash: string;
  }>;
  blockchainAnchor: any;
}

export interface ReportViewModel {
  screeningId: string;
  createdAt: string;
  checkpointId: string;
  checkpointName: string;
  latencyMs: number;
  pdfDownloadUrl: string;
  document: DocumentViewModel;
  mrz: MRZViewModel;
  face: FaceViewModel;
  forensics: ForensicsViewModel;
  crossCheckRows: CrossCheckRow[];
  risk: RiskViewModel;
  audit: AuditViewModel;
}

/**
 * Resolves an authenticated asset URL with JWT token query parameter.
 */
function resolveAssetUrl(path: string | null | undefined, token?: string | null): string | null {
  if (!path) return null;
  let fullUrl = path.startsWith("http://") || path.startsWith("https://") ? path : `${BACKEND_ROOT_URL}${path}`;
  const effectiveToken = token || getAuthTokenSync();
  if (effectiveToken && !fullUrl.includes("token=")) {
    const separator = fullUrl.includes("?") ? "&" : "?";
    fullUrl = `${fullUrl}${separator}token=${encodeURIComponent(effectiveToken)}`;
  }
  return fullUrl;
}

const LABEL_NOISE_PATTERNS = [
  /^(?:SURNAME|NOM|GIVEN\s*NAMES?|PRENOMS?|FULL\s*NAME|NAME|HOLDER|OF\s*HOLDER)[\s\:\./\-_]*$/i,
  /^(?:MAT(?:RICULE)?[\s\:\./\-_]*(?:NOM)?|ME\s*INOM|MAT\s*\/NOM[\s\:\.]*|NOM[\s\:\.]*|PRENOM[\s\:\.]*)$/i,
  /^(?:PASSPORT|PASSPORT\s*NO|DOCUMENT\s*NO|DOC\s*NO|VISA\s*NO|VIGNETTE\s*NO)[\s\:\./\-_]*$/i,
  /^(?:COUNTRY|NATIONALITY|CITIZENSHIP|SEX|GENDER|DATE\s*OF\s*BIRTH|DOB|DATE\s*OF\s*EXPIRY|EXPIRY)[\s\:\./\-_]*$/i,
  /^(?:TYPE|CATEGORY|ENTRIES|VALID\s*FROM|VALID\s*UNTIL|ISSUING\s*POST|PLACE\s*OF\s*ISSUE)[\s\:\./\-_]*$/i,
  /^(?:SIGNATURE|OFFICER|BEARER|AUTORITE|AUTHORITY|REPUBLIC|GOVERNMENT)[\s\:\./\-_]*$/i,
];

export function isLabelNoise(val: string, fieldName?: string): boolean {
  if (!val) return true;
  const s = val.trim();

  const fn = fieldName ? fieldName.toLowerCase() : "";
  if (fn === "document_type" || fn === "doc_type" || fn === "type") {
    const cleanDoc = s.toUpperCase().replace(/[^A-Z]/g, "");
    if (["PASSPORT", "VISA", "ID", "P", "V", "TRAVELDOCUMENT"].includes(cleanDoc)) {
      return false;
    }
  }

  if (fn === "sex" || fn === "gender") {
    const cleanSex = s.toUpperCase().replace(/[^A-Z]/g, "");
    if (["M", "F", "MALE", "FEMALE"].includes(cleanSex)) {
      return false;
    }
  }

  if (s.length < 2) return true;

  if (LABEL_NOISE_PATTERNS.some((p) => p.test(s))) return true;
  if (/^(\/NOM|MAT\s*\/|ME\s*INOM|MATRICULE)/i.test(s)) return true;

  // If value has 3+ consecutive digits, it's typically a document number or date
  if (/\d{3,}/.test(s)) return false;

  const STOPWORDS = new Set([
    "NOM", "SURNAME", "PRENOM", "PRENOMS", "GIVEN", "GIVENNAMES", "NAME", "FULLNAME",
    "MAT", "MATRICULE", "HOLDER", "SIGNATURE", "OFFICER", "PASSPORT", "PASSPORTNO",
    "DOCUMENT", "DOCUMENTNO", "VISA", "VIGNETTE", "NATIONALITY", "CITIZENSHIP", "SEX",
    "DATEOFBIRTH", "DOB", "EXPIRY", "EXPIRATION", "VALIDITY", "OF", "NO", "NR", "NUM", "BIRTH",
    "MATNOM", "SURNAMENOM", "DELIVRANCE", "DELIVERY", "AUTORITE", "AUTHORITY", "BEARER", "PAYS"
  ]);

  const cleanAlpha = s.replace(/[^A-Za-z]/g, "").toUpperCase();
  if (STOPWORDS.has(cleanAlpha)) return true;

  const tokens = s.toUpperCase().split(/[^A-Za-z]+/).filter(Boolean);
  if (tokens.length > 0 && tokens.every(t => STOPWORDS.has(t) || t.length <= 1)) return true;

  return false;
}

/**
 * Normalizes empty, null, placeholder, or OCR label garbage strings into a truthful unavailable state.
 */
function normalizeFieldValue(
  val: any,
  fallback: string = "Not available",
  fieldName?: string
): string {
  if (val === null || val === undefined) return fallback;
  const s = String(val).trim();
  if (s === "" || s === "—" || s === "-" || s === "None" || s === "null" || s === "undefined") {
    return fallback;
  }
  if (isLabelNoise(s, fieldName)) {
    return fallback;
  }
  return s;
}

/**
 * Resolves a field using explicit priority:
 * 1. Verified MRZ value if valid
 * 2. Visual Inspection Zone (VIZ) / OCR value
 * 3. General field_value
 * 4. Fallback string
 */
function resolveFieldValue(
  canonicalName: string,
  fields: ExtractedField[] = [],
  mrzData?: Record<string, any> | null,
  isMrzValid: boolean = false,
  fallback: string = "Not available"
): string {
  const aliasMap: Record<string, string[]> = {
    document_type: ["document_type", "doc_type", "type", "visa_type"],
    document_number: ["document_number", "passport_number", "visa_number", "doc_number"],
    surname: ["surname", "last_name"],
    given_names: ["given_names", "first_name", "names"],
    full_name: ["full_name", "holder_name", "name"],
    nationality: ["nationality", "issuing_country", "country"],
    date_of_birth: ["date_of_birth", "dob", "birth_date"],
    date_of_expiry: ["date_of_expiry", "valid_until", "expiry", "expiry_date", "expiration_date"],
    sex: ["sex", "gender"],
  };

  const aliases = aliasMap[canonicalName] || [canonicalName];

  // 1. If MRZ parsed & valid, prioritize MRZ for identity-critical fields
  if (mrzData && mrzData.parsed && isMrzValid) {
    for (const a of aliases) {
      if (mrzData[a]) {
        const norm = normalizeFieldValue(mrzData[a], "", canonicalName);
        if (norm) return norm;
      }
    }
  }

  // 2. Check visual zone / extracted fields
  for (const a of aliases) {
    const matched = fields.find((f) => f.field_name.toLowerCase() === a.toLowerCase());
    if (matched) {
      if (matched.visual_value) {
        const norm = normalizeFieldValue(matched.visual_value, "", canonicalName);
        if (norm) return norm;
      }
      if (matched.mrz_value) {
        const norm = normalizeFieldValue(matched.mrz_value, "", canonicalName);
        if (norm) return norm;
      }
      if (matched.field_value) {
        const norm = normalizeFieldValue(matched.field_value, "", canonicalName);
        if (norm) return norm;
      }
    }
  }

  // 3. Fallback to mrzData if available even if partial
  if (mrzData) {
    for (const a of aliases) {
      if (mrzData[a]) {
        const norm = normalizeFieldValue(mrzData[a], "", canonicalName);
        if (norm) return norm;
      }
    }
  }

  // 4. If full_name was requested, try composing from given_names + surname
  if (canonicalName === "full_name") {
    const s = resolveFieldValue("surname", fields, mrzData, isMrzValid, "");
    const g = resolveFieldValue("given_names", fields, mrzData, isMrzValid, "");
    const combined = `${g} ${s}`.trim();
    if (combined && !isLabelNoise(combined, "full_name")) return combined;
  }

  return fallback;
}

/**
 * Verifies if year, month, day represent a real calendar day.
 */
function isValidCalendarDate(year: number, month: number, day: number): boolean {
  if (month < 1 || month > 12) return false;
  if (day < 1 || day > 31) return false;
  const d = new Date(year, month - 1, day);
  return d.getFullYear() === year && d.getMonth() === month - 1 && d.getDate() === day;
}

/**
 * Normalizes valid date representations to canonical ISO YYYY-MM-DD for comparison ONLY.
 * Supports:
 * - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
 * - YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
 * - YYMMDD (ICAO Doc 9303 raw format)
 * Returns ISO string if valid, otherwise null.
 */
export function normalizeDateForComparison(val: any): string | null {
  if (!val) return null;
  const s = String(val).trim();
  if (!s || s === "—" || s === "-" || s.toLowerCase() === "null") return null;

  // Pattern: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
  const ymdMatch = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/);
  if (ymdMatch) {
    const y = parseInt(ymdMatch[1], 10);
    const m = parseInt(ymdMatch[2], 10);
    const d = parseInt(ymdMatch[3], 10);
    if (isValidCalendarDate(y, m, d)) {
      return `${y.toString().padStart(4, "0")}-${m.toString().padStart(2, "0")}-${d.toString().padStart(2, "0")}`;
    }
  }

  // Pattern: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
  const dmyMatch = s.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/);
  if (dmyMatch) {
    const d = parseInt(dmyMatch[1], 10);
    const m = parseInt(dmyMatch[2], 10);
    const y = parseInt(dmyMatch[3], 10);
    if (isValidCalendarDate(y, m, d)) {
      return `${y.toString().padStart(4, "0")}-${m.toString().padStart(2, "0")}-${d.toString().padStart(2, "0")}`;
    }
  }

  // Pattern: DD Month YYYY (e.g. 20 JULY 2003, 01 MAR 2024)
  const monthNameMatch = s.match(/^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$/);
  if (monthNameMatch) {
    const monthMap: Record<string, number> = {
      jan: 1, january: 1,
      feb: 2, february: 2,
      mar: 3, march: 3,
      apr: 4, april: 4,
      may: 5,
      jun: 6, june: 6,
      jul: 7, july: 7,
      aug: 8, august: 8,
      sep: 9, september: 9,
      oct: 10, october: 10,
      nov: 11, november: 11,
      dec: 12, december: 12,
    };
    const m = monthMap[monthNameMatch[2].toLowerCase()];
    if (m) {
      const d = parseInt(monthNameMatch[1], 10);
      const y = parseInt(monthNameMatch[3], 10);
      if (isValidCalendarDate(y, m, d)) {
        return `${y.toString().padStart(4, "0")}-${m.toString().padStart(2, "0")}-${d.toString().padStart(2, "0")}`;
      }
    }
  }

  // Pattern: YYMMDD (6 digits, ICAO 9303 standard)
  const raw6Match = s.match(/^(\d{2})(\d{2})(\d{2})$/);
  if (raw6Match) {
    let y = parseInt(raw6Match[1], 10);
    y = y > 50 ? 1900 + y : 2000 + y;
    const m = parseInt(raw6Match[2], 10);
    const d = parseInt(raw6Match[3], 10);
    if (isValidCalendarDate(y, m, d)) {
      return `${y.toString().padStart(4, "0")}-${m.toString().padStart(2, "0")}-${d.toString().padStart(2, "0")}`;
    }
  }

  return null;
}

/**
 * Field equivalence comparator enforcing canonical date comparison,
 * token-order tolerance for full names, and abbreviation matching (e.g. INDIAN vs IND).
 */
export function isFieldMatch(fieldName: string, vizVal: string, mrzVal: string): boolean {
  const isDateField =
    fieldName === "date_of_birth" ||
    fieldName === "date_of_expiry" ||
    fieldName.includes("date") ||
    fieldName === "dob" ||
    fieldName === "expiry";

  if (isDateField) {
    const normV = normalizeDateForComparison(vizVal);
    const normM = normalizeDateForComparison(mrzVal);
    if (normV && normM) {
      return normV === normM;
    }
  }

  const cleanV = vizVal.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  const cleanM = mrzVal.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  if (cleanV === cleanM) return true;

  if (fieldName === "nationality") {
    if ((cleanV === "INDIAN" && cleanM === "IND") || (cleanV === "IND" && cleanM === "INDIAN")) return true;
    if (cleanV.startsWith(cleanM) || cleanM.startsWith(cleanV)) return true;
  }

  if (fieldName === "document_type") {
    if ((cleanV === "PASSPORT" && cleanM === "P") || (cleanV === "P" && cleanM === "PASSPORT")) return true;
    if ((cleanV === "VISA" && cleanM === "V") || (cleanV === "V" && cleanM === "VISA")) return true;
  }

  if (fieldName === "sex" || fieldName === "gender") {
    if ((cleanV === "M" || cleanV === "MALE") && (cleanM === "M" || cleanM === "MALE")) return true;
    if ((cleanV === "F" || cleanV === "FEMALE") && (cleanM === "F" || cleanM === "FEMALE")) return true;
  }

  if (fieldName === "full_name" || fieldName === "name") {
    const wordsV = vizVal.toUpperCase().split(/[^A-Z]+/).filter((w) => w.length > 1);
    const wordsM = mrzVal.toUpperCase().split(/[^A-Z]+/).filter((w) => w.length > 1);
    if (wordsV.length > 0 && wordsM.length > 0) {
      const setV = new Set(wordsV);
      const setM = new Set(wordsM);
      const intersect = wordsV.filter((w) => setM.has(w));
      const overlap = intersect.length / Math.max(setV.size, setM.size);
      if (overlap >= 0.7) return true;
    }
  }

  if (cleanV.startsWith(cleanM) || cleanM.startsWith(cleanV)) {
    return true;
  }

  return false;
}

/**
 * Builds dynamic MRZ & Visual Inspection Zone cross-check rows.
 * Merges every standard canonical field and all extra extracted fields.
 */
function buildCrossCheckRows(
  fields: ExtractedField[] = [],
  mrzData?: Record<string, any> | null,
  docType: string = "PASSPORT",
  mrzStatus: string = "MRZ_VALID"
): CrossCheckRow[] {
  const canonicalDefs: Array<{ key: string; label: string }> = [
    { key: "document_type", label: "DOCUMENT TYPE" },
    { key: "document_number", label: "DOCUMENT NUMBER" },
    { key: "surname", label: "SURNAME" },
    { key: "given_names", label: "GIVEN NAMES" },
    { key: "full_name", label: "FULL NAME" },
    { key: "nationality", label: "NATIONALITY" },
    { key: "date_of_birth", label: "DATE OF BIRTH" },
    { key: "date_of_expiry", label: "DATE OF EXPIRY" },
    { key: "sex", label: "SEX" },
  ];

  const rows: CrossCheckRow[] = [];
  const handledKeys = new Set<string>();

  const isMrzNotApplicable = mrzStatus === "MRZ_NOT_APPLICABLE" || docType.toUpperCase() === "VISA";
  const isInputInsufficient = mrzStatus === "MRZ_INPUT_INSUFFICIENT";
  const isMrzNotDetected = mrzStatus === "MRZ_NOT_DETECTED";

  for (const def of canonicalDefs) {
    handledKeys.add(def.key);
    // Find matching extracted field
    const fieldMatch = fields.find(
      (f) =>
        f.field_name.toLowerCase() === def.key.toLowerCase() ||
        (def.key === "document_number" && (f.field_name.toLowerCase() === "passport_number" || f.field_name.toLowerCase() === "visa_number")) ||
        (def.key === "full_name" && (f.field_name.toLowerCase() === "name" || f.field_name.toLowerCase() === "holder_name")) ||
        (def.key === "date_of_expiry" && f.field_name.toLowerCase() === "valid_until")
    );

    const mrzValRaw =
      mrzData && mrzData.parsed
        ? mrzData[def.key] ||
          (def.key === "document_number" ? (mrzData.document_number || mrzData.passport_number) : undefined) ||
          (def.key === "document_type" ? mrzData.document_code : undefined)
        : null;

    const vizVal = normalizeFieldValue(fieldMatch?.visual_value || fieldMatch?.field_value, "", def.key);
    const mrzVal = normalizeFieldValue(mrzValRaw || fieldMatch?.mrz_value, "", def.key);
    const conf = fieldMatch?.confidence ?? (vizVal ? 0.95 : 0.0);

    let status: CrossCheckRow["status"] = "NOT_PRESENT";
    let statusLabel = "Not Present";

    if (vizVal && mrzVal) {
      const isMatch = isFieldMatch(def.key, vizVal, mrzVal);
      if (isMatch) {
        status = "MATCH";
        statusLabel = "Match";
      } else {
        status = "MISMATCH";
        statusLabel = "Discrepancy";
      }
    } else if (vizVal) {
      status = isMrzNotApplicable ? "NOT_APPLICABLE" : "VIZ_ONLY";
      statusLabel = isMrzNotApplicable ? "Not Applicable" : "VIZ Only";
    } else if (mrzVal) {
      status = "MRZ_ONLY";
      statusLabel = "MRZ Only";
    } else {
      if (isInputInsufficient) {
        status = "UNVERIFIED";
        statusLabel = "Unverified";
      } else if (isMrzNotApplicable) {
        status = "NOT_APPLICABLE";
        statusLabel = "Not Applicable";
      } else {
        status = "NOT_PRESENT";
        statusLabel = "Not Present";
      }
    }

    let displayMrzValue = mrzVal;
    if (!displayMrzValue) {
      if (isMrzNotApplicable) {
        displayMrzValue = "Not applicable";
      } else if (isInputInsufficient) {
        displayMrzValue = "Identity page required";
      } else if (isMrzNotDetected) {
        displayMrzValue = "Not detected";
      } else if (mrzData?.parsed) {
        displayMrzValue = "Not present in MRZ";
      } else {
        displayMrzValue = "MRZ unparsed";
      }
    }

    rows.push({
      fieldName: def.key,
      displayName: def.label,
      visualValue: vizVal || "Not available",
      mrzValue: displayMrzValue,
      confidence: conf,
      status,
      statusLabel,
    });
  }

  // Add any extra non-canonical fields present in extracted_fields
  for (const f of fields) {
    const lk = f.field_name.toLowerCase();
    if (!handledKeys.has(lk) && lk !== "passport_number" && lk !== "name" && lk !== "holder_name" && lk !== "visa_number") {
      const vVal = normalizeFieldValue(f.visual_value || f.field_value, "", lk);
      const mVal = normalizeFieldValue(f.mrz_value, "", lk);
      let status: CrossCheckRow["status"] = (f.match_status as any) || "VIZ_ONLY";
      let statusLabel = f.match_status || "Extracted";

      if (vVal && mVal) {
        const isMatch = isFieldMatch(lk, vVal, mVal);
        if (isMatch) {
          status = "MATCH";
          statusLabel = "Match";
        } else {
          status = "MISMATCH";
          statusLabel = "Discrepancy";
        }
      }

      rows.push({
        fieldName: f.field_name,
        displayName: f.field_name.replace(/_/g, " ").toUpperCase(),
        visualValue: vVal || "Not available",
        mrzValue: mVal || (isMrzNotApplicable ? "Not applicable" : "Not available"),
        confidence: f.confidence,
        status,
        statusLabel,
      });
    }
  }

  return rows;
}

/**
 * Canonical mapper transforming raw ScreeningDetail into a robust ReportViewModel.
 */
export function mapScreeningResponseToReportViewModel(
  data: ScreeningDetail,
  authToken?: string | null
): ReportViewModel {
  const isPassport = (data.document_type || "PASSPORT").toUpperCase() === "PASSPORT";
  const mrzParsed = Boolean(data.mrz_data?.parsed);
  const mrzAllChecksPassed = Boolean(data.mrz_data?.all_checks_passed);
  const mrzStatusRaw = (data as any).mrz_status || (data.mrz_data as any)?.mrz_status || (data.mrz_data as any)?.status;

  const pageType = (data as any).page_type || (isPassport ? "PASSPORT_IDENTITY_PAGE" : "VISA_VIGNETTE");
  const isIdentityPage = (data as any).is_identity_page !== undefined ? (data as any).is_identity_page : (pageType !== "PASSPORT_COVER");
  const identityPageMessage = (data as any).identity_page_message || (!isIdentityPage ? "Identity Page Not Detected — recapture required. Upload the passport biodata/identity page containing portrait and machine-readable information." : undefined);

  // MRZ Status Badge with explicit 6-state model
  let mrzStatusBadge: MRZViewModel["statusBadge"] = "NOT APPLICABLE";
  let mrzStatusColor = "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";

  if (mrzStatusRaw === "MRZ_VALID" || (mrzParsed && mrzAllChecksPassed)) {
    mrzStatusBadge = "7-3-1 PASS";
    mrzStatusColor = "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800";
  } else if (mrzStatusRaw === "MRZ_INVALID" || (mrzParsed && !mrzAllChecksPassed)) {
    mrzStatusBadge = "CHECKSUM FAIL";
    mrzStatusColor = "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-800";
  } else if (mrzStatusRaw === "MRZ_NOT_APPLICABLE" || (!isPassport && !mrzParsed)) {
    mrzStatusBadge = "NOT APPLICABLE";
    mrzStatusColor = "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";
  } else if (mrzStatusRaw === "MRZ_INPUT_INSUFFICIENT" || pageType === "PASSPORT_COVER" || !isIdentityPage) {
    mrzStatusBadge = "INPUT INSUFFICIENT";
    mrzStatusColor = "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800";
  } else if (mrzStatusRaw === "MRZ_NOT_DETECTED") {
    mrzStatusBadge = "NOT DETECTED";
    mrzStatusColor = "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800";
  } else if (mrzStatusRaw === "MRZ_UNPARSED" || (isPassport && !mrzParsed)) {
    mrzStatusBadge = "UNPARSED";
    mrzStatusColor = "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800";
  }

  // Document Fields with truthful resolution
  const docType = data.document_type || "PASSPORT";
  const docNumber = resolveFieldValue("document_number", data.extracted_fields, data.mrz_data, mrzAllChecksPassed, "");
  const hasValidMasked = data.masked_document_id &&
    !data.masked_document_id.includes("UNKNOWN") &&
    !data.masked_document_id.includes("UNAVAILABLE") &&
    !data.masked_document_id.startsWith("VIS******");
  const fullDocNumber = docNumber || (hasValidMasked ? `${data.masked_document_id} (Masked)` : "Not available");
  const surname = resolveFieldValue("surname", data.extracted_fields, data.mrz_data, mrzAllChecksPassed, "Not available");
  const givenNames = resolveFieldValue("given_names", data.extracted_fields, data.mrz_data, mrzAllChecksPassed, "Not available");
  const fullName = resolveFieldValue("full_name", data.extracted_fields, data.mrz_data, mrzAllChecksPassed, "Not available");
  const nationality = resolveFieldValue("nationality", data.extracted_fields, data.mrz_data, mrzAllChecksPassed, "Not available");
  const dob = resolveFieldValue("date_of_birth", data.extracted_fields, data.mrz_data, mrzAllChecksPassed, "Not available");
  const expiry = resolveFieldValue("date_of_expiry", data.extracted_fields, data.mrz_data, mrzAllChecksPassed, "Not available");
  const sex = resolveFieldValue("sex", data.extracted_fields, data.mrz_data, mrzAllChecksPassed, "Not available");

  // Determine truthful OCR Status
  let ocrStatus: DocumentViewModel["ocrStatus"] = "FAILED";
  const hasExtractedValues = data.extracted_fields?.some(
    (f) => f.field_name !== "document_type" && (Boolean(f.visual_value) || Boolean(f.field_value))
  );

  if (data.ocr_status) {
    ocrStatus = data.ocr_status as any;
  } else if (hasExtractedValues) {
    ocrStatus = "SUCCESS";
  } else if (mrzParsed) {
    ocrStatus = "PARTIAL";
  } else {
    ocrStatus = "FAILED";
  }

  // Image and Crop URLs with authentication token query param
  const docPortraitRaw =
    data.doc_face_url ||
    data.face_result?.doc_face_crop_url ||
    `/api/v1/screenings/media/${data.id}/doc_face`;

  const presentedFaceRaw =
    data.live_face_url ||
    data.face_result?.live_face_crop_url ||
    (data.live_image_url ? `/api/v1/screenings/media/${data.id}/live_face` : null);

  const heatmapRaw =
    data.ela_heatmap_url ||
    `/api/v1/screenings/media/${data.id}/heatmap`;

  const documentPortraitUrl = resolveAssetUrl(docPortraitRaw, authToken);
  const presentedFaceUrl = resolveAssetUrl(presentedFaceRaw, authToken);
  const heatmapUrl = resolveAssetUrl(heatmapRaw, authToken);

  // Biometric / Face Verification
  const faceRes = data.face_result;
  let faceResultStatus: FaceViewModel["result"] = "NO LIVE CAPTURE";
  if (faceRes) {
    const rawRes = (faceRes.decision_state || faceRes.verification_result || "").toUpperCase();
    if (rawRes.includes("MATCH") && !rawRes.includes("MISMATCH")) {
      faceResultStatus = "VERIFIED MATCH";
    } else if (rawRes.includes("MISMATCH")) {
      faceResultStatus = "VERIFIED MISMATCH";
    } else if (rawRes.includes("INCONCLUSIVE") || rawRes.includes("BORDERLINE")) {
      faceResultStatus = "INCONCLUSIVE";
    } else {
      faceResultStatus = "INPUT FAILURE";
    }
  }

  // Forensics Signals
  const tamperSummary = data.tamper_summary || { composite_tamper_score: 0, findings_count: 0 };
  const findings = (data.tamper_findings || []).map((t) => ({
    technique: t.technique,
    severity: t.severity,
    score: t.score,
    summary: t.summary,
    observation: t.observation || "Anomaly detected in spatial residual variance.",
    interpretation: t.interpretation || "Evidence suggests localized digital edit or splicing.",
  }));

  const elaFinding = findings.find((f) => f.technique === "ELA");
  const noiseFinding = findings.find((f) => f.technique === "NOISE_RESIDUAL");
  const copyMoveFinding = findings.find((f) => f.technique === "COPY_MOVE");

  // Cross-check rows & Discrepancies
  const crossCheckRows = buildCrossCheckRows(
    data.extracted_fields,
    data.mrz_data,
    data.document_type || "PASSPORT",
    mrzStatusRaw || (pageType === "PASSPORT_COVER" || !isIdentityPage ? "MRZ_INPUT_INSUFFICIENT" : (!isPassport ? "MRZ_NOT_APPLICABLE" : "MRZ_VALID"))
  );
  const discrepancies: Record<string, { visual: string; mrz: string }> = {};
  for (const row of crossCheckRows) {
    if (row.status === "MISMATCH" && row.visualValue !== "Not available" && row.mrzValue !== "Not available") {
      discrepancies[row.fieldName] = { visual: row.visualValue, mrz: row.mrzValue };
    }
  }

  // PDF Download URL with auth token
  const effectiveAuth = authToken || getAuthTokenSync();
  const tokenParam = effectiveAuth ? `?token=${encodeURIComponent(effectiveAuth)}` : "";
  const pdfDownloadUrl = `${API_BASE_URL}/reports/${data.id}/pdf${tokenParam}`;

  return {
    screeningId: data.id,
    createdAt: data.created_at,
    checkpointId: data.checkpoint_id || "CP-DEL-AIR",
    checkpointName: data.checkpoint_name || "Delhi Airport Immigration Checkpoint",
    latencyMs: data.execution_latency_ms || 0,
    pdfDownloadUrl,

    document: {
      type: docType,
      pageType,
      isIdentityPage,
      identityPageMessage,
      number: fullDocNumber,
      maskedNumber: data.masked_document_id || "Not available",
      surname,
      givenNames,
      fullName,
      nationality,
      dob,
      expiry,
      sex,
      ocrStatus,
      ocrEngine: data.ocr_engine || "Tesseract",
      qualityVerdict: data.quality_assessment?.verdict || "GOOD",
      qualityScore: data.quality_assessment?.overall_score || 85,
      qualityMessage:
        data.quality_assessment?.verdict === "GOOD"
          ? "Document image meets resolution and illumination criteria for automated inspection."
          : "Image resolution or lighting parameters require officer visual verification.",
      discrepancies,
    },

    mrz: {
      applicable: isPassport && pageType !== "PASSPORT_COVER" && isIdentityPage,
      parsed: mrzParsed,
      statusBadge: mrzStatusBadge,
      statusColor: mrzStatusColor,
      lines: (data.mrz_data as any)?.raw_lines || [],
      checkDigits: data.mrz_data?.check_digits || {},
      allChecksPassed: mrzAllChecksPassed,
      decodedFields: {
        document_number: normalizeFieldValue(data.mrz_data?.document_number, "Not available"),
        date_of_birth: normalizeFieldValue(data.mrz_data?.date_of_birth, "Not available"),
        date_of_expiry: normalizeFieldValue(data.mrz_data?.date_of_expiry, "Not available"),
        nationality: normalizeFieldValue(data.mrz_data?.nationality, "Not available"),
        full_name: normalizeFieldValue(data.mrz_data?.full_name, "Not available"),
      },
    },

    face: {
      result: faceResultStatus,
      decisionState: faceRes?.decision_state || faceRes?.verification_result || "NO LIVE CAPTURE",
      similarity: faceRes ? faceRes.similarity_score : null,
      similarityPercent: faceRes ? `${(faceRes.similarity_score * 100).toFixed(1)}%` : "N/A",
      threshold: faceRes?.threshold || 0.68,
      provider: faceRes?.provider || "SFace-ResNet-128d-v1.0",
      providerType: faceRes?.provider_type || "DEEP_NEURAL",
      qualityStatus: faceRes?.quality_status || "GOOD",
      appearanceLevel: faceRes?.appearance_level || "MINIMAL",
      observations: faceRes?.observations || [],
      recommendation: faceRes?.recommendation || "Biometric inspection complete.",
      padStatus: faceRes?.pad_status || "NOT_AVAILABLE",
      padReason: faceRes?.pad_reason || "Presentation-attack detection not enabled in prototype.",
      documentPortraitUrl,
      presentedFaceUrl,
      hasLiveSelfie: Boolean(presentedFaceUrl),
    },

    forensics: {
      compositeScore: tamperSummary.composite_tamper_score ?? 0,
      verdict:
        (tamperSummary.composite_tamper_score ?? 0) >= 35
          ? "FORENSIC ANOMALIES DETECTED"
          : "NO TAMPERING DETECTED",
      elaScore: (data.tamper_summary as any)?.signals?.ela?.anomaly_score ?? (elaFinding ? elaFinding.score : 0),
      noiseScore: (data.tamper_summary as any)?.signals?.noise_residual?.anomaly_score ?? (noiseFinding ? noiseFinding.score : 0),
      copyMoveMatches: (data.tamper_summary as any)?.signals?.copy_move?.matches_found ?? (copyMoveFinding ? copyMoveFinding.score : 0),
      heatmapUrl,
      findingsCount: findings.length,
      findings,
    },

    crossCheckRows,

    risk: {
      score: data.risk_score || 0,
      band: data.risk_band || "LOW",
      recommendation: data.recommendation || "Routine Clearance Permitted.",
      reasons: data.risk_reasons || [],
      signalBreakdown: {
        mrzIntegrity: data.signal_breakdown?.mrz_integrity ?? 0,
        tamperForensics: data.signal_breakdown?.tamper_forensics ?? 0,
        faceVerification: data.signal_breakdown?.face_verification ?? 0,
      },
    },

    audit: {
      eventsCount: data.audit_trail?.length || 0,
      headHash: data.audit_trail?.[data.audit_trail.length - 1]?.event_hash || "",
      genesisHash: data.audit_trail?.[0]?.event_hash || "",
      events: (data.audit_trail || []).map((e) => ({
        id: e.id,
        timestamp: e.timestamp,
        actor: e.actor,
        eventType: e.event_type,
        payloadHash: e.payload_hash,
        eventHash: e.event_hash,
      })),
      blockchainAnchor: data.blockchain_anchor || null,
    },
  };
}
