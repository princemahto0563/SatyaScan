/**
 * SatyaScan API Client
 * Connects to FastAPI backend at /api/v1 (defaults to http://localhost:8000/api/v1)
 */

import { ScreeningDetail, ScreeningSummary } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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

  const res = await fetch(`${API_BASE_URL}/screenings`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Screening processing failed." }));
    throw new Error(err.detail || `Server returned ${res.status}`);
  }

  return res.json();
}

export async function getScreeningsList(limit: number = 30): Promise<ScreeningSummary[]> {
  const res = await fetch(`${API_BASE_URL}/screenings?limit=${limit}`);
  if (!res.ok) {
    throw new Error("Failed to fetch screening history");
  }
  return res.json();
}

export async function getScreeningDetail(id: string): Promise<ScreeningDetail> {
  const res = await fetch(`${API_BASE_URL}/screenings/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch screening ${id}`);
  }
  return res.json();
}

export async function verifyAuditChain(screeningId: string) {
  const res = await fetch(`${API_BASE_URL}/audit/${screeningId}/verify`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Audit verification request failed");
  }
  return res.json();
}

export async function anchorAuditChain(screeningId: string) {
  const res = await fetch(`${API_BASE_URL}/audit/${screeningId}/anchor`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Blockchain anchor request failed");
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
  const res = await fetch(`${API_BASE_URL}/analytics`);
  if (!res.ok) {
    throw new Error("Failed to fetch analytics");
  }
  return res.json();
}

export async function getWatchlist() {
  const res = await fetch(`${API_BASE_URL}/watchlist`);
  if (!res.ok) {
    throw new Error("Failed to fetch reference watchlist");
  }
  return res.json();
}
