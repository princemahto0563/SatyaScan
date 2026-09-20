/**
 * SatyaScan API Client
 * Connects to FastAPI backend at /api/v1 (defaults to http://localhost:8000/api/v1)
 * Includes in-memory JWT authentication & Checkpoint Workstation session manager.
 * Strict security: Zero token persistence in localStorage/sessionStorage (XSS protection).
 */

import { ScreeningDetail, ScreeningSummary, CheckpointInfo, UserSession, BlockchainAnchor, BlockchainVerificationResponse } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const BACKEND_ROOT_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, "");

const TIMEOUT_MS = 60000;

// IN-MEMORY AUTHENTICATION STATE: Protects against XSS token exfiltration
let inMemoryAuthToken: string | null = null;
let inMemorySession: UserSession | null = null;
type AuthListener = (session: UserSession | null) => void;
const authListeners: Set<AuthListener> = new Set();

export function getSession(): UserSession | null {
  return inMemorySession;
}

export function subscribeAuth(listener: AuthListener): () => void {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
}

function notifyAuthChange(session: UserSession | null) {
  inMemorySession = session;
  authListeners.forEach((fn) => {
    try {
      fn(session);
    } catch (e) {
      console.error("[SatyaScan Auth] Listener error:", e);
    }
  });
}

export async function getCheckpoints(): Promise<CheckpointInfo[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/checkpoints`, {
      method: "GET",
      cache: "no-store",
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.error("[SatyaScan Auth] Failed to load checkpoints:", err);
  }
  return [];
}

export async function loginCheckpoint(
  checkpointId: string,
  username: string,
  password: string
): Promise<{ success: boolean; error?: string; session?: UserSession }> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.trim(),
        password,
        checkpoint_id: checkpointId,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      inMemoryAuthToken = data.access_token;
      const session: UserSession = {
        id: data.user?.id,
        username: data.username,
        full_name: data.full_name,
        badge_number: data.badge_number,
        role: data.role,
        checkpoint_id: data.checkpoint_id || checkpointId,
        checkpoint_name: data.checkpoint_name || data.user?.checkpoint_name,
        location: data.user?.location,
        access_token: data.access_token,
      };
      notifyAuthChange(session);
      return { success: true, session };
    }

    const errData = await res.json().catch(() => ({}));
    const errorMsg =
      errData.detail ||
      (res.status === 401
        ? "Invalid checkpoint credentials."
        : `Authentication failed (HTTP ${res.status})`);
    return { success: false, error: errorMsg };
  } catch (err: any) {
    return {
      success: false,
      error: `Connection error: Unable to reach authentication service at ${API_BASE_URL}`,
    };
  }
}

export function logout(): void {
  inMemoryAuthToken = null;
  notifyAuthChange(null);
}

export async function getAuthToken(): Promise<string> {
  return inMemoryAuthToken || "";
}

export async function authenticatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = await getAuthToken();
  const headers = new Headers(init?.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(input, { ...init, headers });

  // Handle expired token or revoked session: notify listeners to prompt re-login
  if (res.status === 401 && token) {
    inMemoryAuthToken = null;
    notifyAuthChange(null);
  }

  return res;
}

export interface HealthStatus {
  online: boolean;
  status: string;
  service: string;
  version: string;
  mode: string;
  latencyMs?: number;
}

export async function checkBackendHealth(): Promise<HealthStatus> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 4000);
  const start = performance.now();
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timeoutId);
    if (res.ok) {
      const data = await res.json();
      return {
        online: true,
        status: data.status || "HEALTHY",
        service: data.service || "SatyaScan Screening Engine",
        version: data.version || "1.0.0",
        mode: data.mode || "PROTOTYPE_OPERATIONAL",
        latencyMs: Math.round(performance.now() - start),
      };
    }
    return {
      online: false,
      status: `HTTP ${res.status}`,
      service: "SatyaScan",
      version: "unknown",
      mode: "UNAVAILABLE",
    };
  } catch {
    clearTimeout(timeoutId);
    return {
      online: false,
      status: "DISCONNECTED",
      service: "SatyaScan",
      version: "unknown",
      mode: "OFFLINE",
    };
  }
}

async function extractErrorMessage(res: Response): Promise<string> {
  let detailMsg = `Backend returned HTTP ${res.status}`;
  try {
    const err = await res.json();
    if (err.detail) {
      detailMsg += ` — ${typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail)}`;
    }
  } catch {
    // Non-JSON body
  }
  return detailMsg;
}

function handleFetchError(err: any): never {
  if (err.name === "AbortError") {
    throw new Error(
      "Screening timed out after 60 seconds. The backend may still be processing this case. Please retry or inspect the case status."
    );
  }
  if (err instanceof TypeError && (err.message === "Failed to fetch" || err.message.includes("fetch"))) {
    throw new Error(
      `Screening service unavailable: Unable to connect to backend at ${API_BASE_URL}. Ensure the backend service is running and accessible.`
    );
  }
  throw err;
}

export async function submitScreening(
  docFile: File,
  liveFile?: File | null,
  docType: string = "PASSPORT"
): Promise<ScreeningDetail> {
  const formData = new FormData();
  formData.append("document_file", docFile);
  if (liveFile) {
    formData.append("live_selfie_file", liveFile);
  }
  formData.append("document_type", docType);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await authenticatedFetch(`${API_BASE_URL}/screenings`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      const msg = await extractErrorMessage(res);
      throw new Error(`Screening request failed: ${msg}`);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    handleFetchError(err);
  }
}

export async function submitPresetScreening(caseNum: string): Promise<ScreeningDetail> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await authenticatedFetch(`${API_BASE_URL}/screenings/preset/${caseNum}`, {
      method: "POST",
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      const msg = await extractErrorMessage(res);
      throw new Error(`Screening request failed: ${msg}`);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    handleFetchError(err);
  }
}

export async function getScreeningsList(limit: number = 30): Promise<ScreeningSummary[]> {
  const res = await authenticatedFetch(`${API_BASE_URL}/screenings?limit=${limit}`);
  if (!res.ok) {
    throw new Error("Failed to fetch screening history");
  }
  return res.json();
}

export async function getScreeningDetail(id: string): Promise<ScreeningDetail> {
  const res = await authenticatedFetch(`${API_BASE_URL}/screenings/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch screening ${id}`);
  }
  return res.json();
}

export async function verifyAuditChain(screeningId: string) {
  const res = await authenticatedFetch(`${API_BASE_URL}/audit/${screeningId}/verify`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Audit verification request failed");
  }
  return res.json();
}

export async function anchorAuditChain(screeningId: string) {
  const res = await authenticatedFetch(`${API_BASE_URL}/audit/${screeningId}/anchor`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Blockchain anchor request failed");
  }
  return res.json();
}

export async function getBlockchainAnchor(screeningId: string): Promise<BlockchainAnchor> {
  const res = await authenticatedFetch(`${API_BASE_URL}/blockchain/${screeningId}`);
  if (!res.ok) {
    throw new Error("Failed to fetch blockchain anchor");
  }
  return res.json();
}

export async function anchorBlockchainScreening(screeningId: string): Promise<BlockchainAnchor> {
  const res = await authenticatedFetch(`${API_BASE_URL}/blockchain/${screeningId}/anchor`, {
    method: "POST",
  });
  if (!res.ok) {
    const msg = await extractErrorMessage(res);
    throw new Error(msg || "Blockchain anchor request failed");
  }
  return res.json();
}

export async function verifyBlockchainAnchor(screeningId: string): Promise<BlockchainVerificationResponse> {
  const res = await authenticatedFetch(`${API_BASE_URL}/blockchain/${screeningId}/verify`, {
    method: "POST",
  });
  if (!res.ok) {
    const msg = await extractErrorMessage(res);
    throw new Error(msg || "Blockchain verification request failed");
  }
  return res.json();
}

export function getReportDownloadUrl(screeningId: string): string {
  return `${API_BASE_URL}/reports/${screeningId}/pdf`;
}

export function getMediaUrl(screeningId: string, type: "doc" | "live" | "heatmap"): string {
  return `${API_BASE_URL}/screenings/media/${screeningId}/${type}`;
}

export async function getAnalytics() {
  const res = await authenticatedFetch(`${API_BASE_URL}/analytics`);
  if (!res.ok) {
    throw new Error("Failed to fetch analytics");
  }
  return res.json();
}

export async function getWatchlist() {
  const res = await authenticatedFetch(`${API_BASE_URL}/watchlist`);
  if (!res.ok) {
    throw new Error("Failed to fetch reference watchlist");
  }
  return res.json();
}
