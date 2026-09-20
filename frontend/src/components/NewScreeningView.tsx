"use client";

import React, { useState, useRef, useCallback } from "react";
import Webcam from "react-webcam";
import { 
  Upload, Camera, CheckCircle2, AlertCircle, RefreshCw, 
  ArrowRight, ShieldCheck, User, Image as ImageIcon, Eye, FileText
} from "lucide-react";
import { submitScreening, submitPresetScreening, BACKEND_ROOT_URL } from "../lib/api";
import { ScreeningDetail } from "../lib/types";

interface NewScreeningViewProps {
  onScreeningCompleted: (detail: ScreeningDetail) => void;
}

export function NewScreeningView({ onScreeningCompleted }: NewScreeningViewProps) {
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docPreview, setDocPreview] = useState<string | null>(null);
  const [selfieFile, setSelfieFile] = useState<File | null>(null);
  const [selfiePreview, setSelfiePreview] = useState<string | null>(null);
  const [isWebcamOpen, setIsWebcamOpen] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState("PASSPORT");
  
  // Pipeline processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [pipelineStep, setPipelineStep] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const webcamRef = useRef<Webcam>(null);

  // Helper to handle document upload
  const handleDocChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setDocFile(file);
      setDocPreview(URL.createObjectURL(file));
      setErrorMessage(null);
    }
  };

  // Helper to handle selfie file upload
  const handleSelfieChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelfieFile(file);
      setSelfiePreview(URL.createObjectURL(file));
      setIsWebcamOpen(false);
      setCameraError(null);
    }
  };

  // Helper to capture live webcam snapshot
  const captureWebcamSelfie = useCallback(() => {
    if (webcamRef.current) {
      const imageSrc = webcamRef.current.getScreenshot();
      if (imageSrc) {
        setSelfiePreview(imageSrc);
        fetch(imageSrc)
          .then((res) => res.blob())
          .then((blob) => {
            const file = new File([blob], "live_selfie.jpg", { type: "image/jpeg" });
            setSelfieFile(file);
            setIsWebcamOpen(false);
          });
      }
    }
  }, [webcamRef]);

  // Execute Screening
  const runScreening = async () => {
    if (!docFile) {
      setErrorMessage("Please upload or select a travel document before initiating screening.");
      return;
    }

    setIsProcessing(true);
    setErrorMessage(null);

    // Timed pipeline progress steps
    setPipelineStep("Evaluating Image Quality Gate...");
    const t1 = setTimeout(() => setPipelineStep("Running Optical Character Recognition & Field Extraction..."), 150);
    const t2 = setTimeout(() => setPipelineStep("Parsing ICAO Doc 9303 TD3 MRZ & 7-3-1 Check Digits..."), 300);
    const t3 = setTimeout(() => setPipelineStep("Executing Multi-Signal Forensics (ELA Heatmap & Sensor Noise)..."), 500);
    const t4 = setTimeout(() => setPipelineStep("Running Biometric Comparison & Multi-Identity Check..."), 700);
    const t5 = setTimeout(() => setPipelineStep("Synthesizing Evidence & Calibrating Risk Factors..."), 900);

    try {
      const result = await submitScreening(docFile, selfieFile, documentType);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(t5);
      onScreeningCompleted(result);
    } catch (err: any) {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(t5);
      setErrorMessage(err.message || "Screening service returned an error. Please verify backend availability.");
    } finally {
      setIsProcessing(false);
      setPipelineStep("");
    }
  };

  const presetCases = [
    { num: "01", label: "Genuine Passport", desc: "Valid ICAO MRZ, Low Risk", color: "border-emerald-300 dark:border-emerald-500/40 text-emerald-800 dark:text-emerald-400 bg-emerald-50/50 dark:bg-emerald-500/5", path: "/data/genuine/case01_genuine_arjun.jpg", selfie: "/data/selfies/case01_selfie_arjun.jpg" },
    { num: "02", label: "Expired Document", desc: "Expired in 2022, Validity Flag", color: "border-amber-300 dark:border-amber-500/40 text-amber-800 dark:text-amber-400 bg-amber-50/50 dark:bg-amber-500/5", path: "/data/tampered/case02_expired_ravi.jpg", selfie: "/data/selfies/case01_selfie_arjun.jpg" },
    { num: "03", label: "DOB Altered", desc: "Visual DOB 2002 vs MRZ 1990", color: "border-rose-300 dark:border-rose-500/40 text-rose-800 dark:text-rose-400 bg-rose-50/50 dark:bg-rose-500/5", path: "/data/tampered/case03_tampered_dob.jpg", selfie: "/data/selfies/case01_selfie_arjun.jpg" },
    { num: "04", label: "Photo Replaced", desc: "Spliced Face + ELA Anomaly", color: "border-red-300 dark:border-red-500/40 text-red-800 dark:text-red-400 bg-red-50/50 dark:bg-red-500/5", path: "/data/tampered/case04_photo_replaced.jpg", selfie: "/data/selfies/case01_selfie_arjun.jpg" },
    { num: "05", label: "Cloned Stamp", desc: "Copy-Move Duplicate Elements", color: "border-purple-300 dark:border-purple-500/40 text-purple-800 dark:text-purple-400 bg-purple-50/50 dark:bg-purple-500/5", path: "/data/tampered/case05_copymove_stamp.jpg", selfie: "/data/selfies/case01_selfie_arjun.jpg" },
    { num: "06", label: "Multi-Identity", desc: "Same Face, Different Name Record", color: "border-cyan-300 dark:border-cyan-500/40 text-cyan-800 dark:text-cyan-400 bg-cyan-50/50 dark:bg-cyan-500/5", path: "/data/genuine/case06_multi_identity.jpg", selfie: "/data/selfies/case01_selfie_arjun.jpg" },
    { num: "07", label: "Degraded Quality", desc: "Severe Blur, Fails Quality Gate", color: "border-slate-300 dark:border-slate-500/40 text-slate-700 dark:text-slate-400 bg-slate-100/50 dark:bg-slate-500/5", path: "/data/tampered/case07_blurry_fail.jpg", selfie: "/data/selfies/case01_selfie_arjun.jpg" },
    { num: "08", label: "Appearance Variation", desc: "Identity Matches, Beard Recorded", color: "border-teal-300 dark:border-teal-500/40 text-teal-800 dark:text-teal-400 bg-teal-50/50 dark:bg-teal-500/5", path: "/data/genuine/case01_genuine_arjun.jpg", selfie: "/data/selfies/case08_selfie_bearded_arjun.jpg" },
    { num: "09", label: "Impersonation", desc: "Different Subject vs Document Photo", color: "border-rose-400 dark:border-rose-600/40 text-rose-900 dark:text-rose-300 bg-rose-50/50 dark:bg-rose-600/5", path: "/data/genuine/case01_genuine_arjun.jpg", selfie: "/data/selfies/case09_selfie_imposter.jpg" },
  ];

  // Execute screening for one of the controlled test cases
  const handlePresetClick = async (preset: typeof presetCases[0]) => {
    setIsProcessing(true);
    setErrorMessage(null);
    setPipelineStep(`Evaluating Case ${preset.num} (${preset.label})...`);

    const docUrl = `${BACKEND_ROOT_URL}${preset.path}`;
    const selfieUrl = preset.selfie ? `${BACKEND_ROOT_URL}${preset.selfie}` : null;
    setDocPreview(docUrl);
    setSelfiePreview(selfieUrl);

    fetch(docUrl)
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => {
        if (blob) {
          const fname = preset.path.split("/").pop() || "doc.jpg";
          setDocFile(new File([blob], fname, { type: "image/jpeg" }));
        }
      })
      .catch(() => {});

    if (selfieUrl) {
      fetch(selfieUrl)
        .then((r) => (r.ok ? r.blob() : null))
        .then((blob) => {
          if (blob) {
            const sname = preset.selfie.split("/").pop() || "selfie.jpg";
            setSelfieFile(new File([blob], sname, { type: "image/jpeg" }));
          }
        })
        .catch(() => {});
    }

    const t1 = setTimeout(() => setPipelineStep("Evaluating Image Quality Gate..."), 150);
    const t2 = setTimeout(() => setPipelineStep("Running Optical Character Recognition & Field Extraction..."), 350);
    const t3 = setTimeout(() => setPipelineStep("Parsing ICAO Doc 9303 TD3 MRZ & 7-3-1 Check Digits..."), 600);
    const t4 = setTimeout(() => setPipelineStep("Executing Multi-Signal Forensics (ELA Heatmap & Noise Residual)..."), 850);
    const t5 = setTimeout(() => setPipelineStep("Running Biometric Comparison & Multi-Identity Check..."), 1100);
    const t6 = setTimeout(() => setPipelineStep("Synthesizing Evidence & Calibrating Risk Factors..."), 1400);

    try {
      const result = await submitPresetScreening(preset.num);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(t5);
      clearTimeout(t6);
      onScreeningCompleted(result);
    } catch (err: any) {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(t5);
      clearTimeout(t6);
      setErrorMessage(err.message || "Screening service failed. Please verify backend availability.");
    } finally {
      setIsProcessing(false);
      setPipelineStep("");
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      
      {/* Header Section */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center space-x-2">
              <span>Document Verification Workstation</span>
            </h1>
            <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
              Submit a travel document (Passport, Visa) and optional live webcam capture for automated validation, forensic examination, and identity cross-verification.
            </p>
          </div>
          
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-600 dark:text-slate-400 font-medium">Document Type:</span>
            <select
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              className="rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-1.5 text-xs font-semibold text-teal-700 dark:text-teal-400 focus:outline-none focus:border-teal-600"
            >
              <option value="PASSPORT">Passport (ICAO TD3)</option>
              <option value="VISA">Visa Vignette</option>
            </select>
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
              Passport & Visa Only
            </span>
          </div>
        </div>
      </div>

      {/* Controlled Verification Test Suite Presets */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800/80 bg-white dark:bg-slate-900/40 p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <FileText className="h-4 w-4 text-teal-700 dark:text-teal-400" />
            <span className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
              Controlled Verification Test Suite
            </span>
          </div>
          <span className="text-[11px] text-slate-500 font-mono">9 BENCHMARK CASES</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {presetCases.map((p) => (
            <button
              key={p.num}
              onClick={() => handlePresetClick(p)}
              disabled={isProcessing}
              className={`flex flex-col items-start p-2.5 rounded-lg border text-left transition-all hover:shadow-sm disabled:opacity-60 disabled:cursor-not-allowed ${p.color}`}
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-xs font-bold font-mono">CASE {p.num}</span>
                <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-slate-200/80 dark:bg-slate-800/80">
                  {p.label}
                </span>
              </div>
              <span className="text-[11px] text-slate-600 dark:text-slate-300 mt-1">{p.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Upload and Capture Dual-Pane */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Pane 1: Document Upload */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-5 flex flex-col justify-between space-y-4 shadow-sm">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-semibold text-slate-900 dark:text-white flex items-center space-x-2">
                <ImageIcon className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                <span>Step 1: Travel Document Image</span>
              </span>
              <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 font-mono uppercase bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                MANDATORY
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Provide clear image capture of passport biodata page or visa stamp.
            </p>
          </div>

          <div className="relative border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-teal-500 rounded-xl p-4 transition text-center flex flex-col items-center justify-center min-h-[220px] bg-slate-50 dark:bg-slate-950/40">
            {docPreview ? (
              <div className="relative w-full flex flex-col items-center">
                <img
                  src={docPreview}
                  alt="Document Preview"
                  className="max-h-44 rounded-lg object-contain shadow-sm border border-slate-200 dark:border-slate-700"
                />
                <div className="mt-3 flex items-center space-x-2">
                  <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium flex items-center space-x-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>{docFile?.name || "Document Loaded"}</span>
                  </span>
                  <label className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer underline">
                    Change
                    <input type="file" accept="image/*" onChange={handleDocChange} className="hidden" />
                  </label>
                </div>
              </div>
            ) : (
              <label className="cursor-pointer flex flex-col items-center justify-center space-y-2 p-6 w-full">
                <div className="rounded-full bg-slate-100 dark:bg-slate-800 p-3 text-teal-600 dark:text-teal-400">
                  <Upload className="h-6 w-6" />
                </div>
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                  Click to select document image
                </span>
                <span className="text-xs text-slate-500">
                  Supports JPG, PNG, WEBP (Max 10MB)
                </span>
                <input type="file" accept="image/*" onChange={handleDocChange} className="hidden" />
              </label>
            )}
          </div>
        </div>

        {/* Pane 2: Live Selfie / Webcam Capture */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-5 flex flex-col justify-between space-y-4 shadow-sm">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-semibold text-slate-900 dark:text-white flex items-center space-x-2">
                <Camera className="h-4 w-4 text-cyan-600 dark:text-cyan-400" />
                <span>Step 2: Live Facial Capture</span>
              </span>
              <span className="text-[10px] font-bold text-teal-700 dark:text-teal-400 font-mono uppercase bg-teal-50 dark:bg-teal-950/60 px-1.5 py-0.5 rounded">
                RECOMMENDED
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Live camera capture for 1:1 biometric identity comparison & duplicate identity search.
            </p>
          </div>

          <div className="relative border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl p-4 transition text-center flex flex-col items-center justify-center min-h-[220px] bg-slate-50 dark:bg-slate-950/40">
            {isWebcamOpen ? (
              <div className="relative w-full flex flex-col items-center">
                <div className="relative rounded-lg overflow-hidden border border-slate-300 dark:border-slate-700 shadow-md max-w-[280px]">
                  <Webcam
                    audio={false}
                    ref={webcamRef}
                    screenshotFormat="image/jpeg"
                    videoConstraints={{ width: 400, height: 400, facingMode: "user" }}
                    onUserMediaError={() => {
                      setIsWebcamOpen(false);
                      setCameraError("Camera unavailable. You can upload a captured image instead.");
                    }}
                    className="w-full h-auto"
                  />
                  <div className="absolute inset-0 border-2 border-cyan-500/40 rounded-full m-4 pointer-events-none"></div>
                </div>
                <div className="mt-3 flex items-center space-x-3">
                  <button
                    onClick={captureWebcamSelfie}
                    className="rounded-lg bg-teal-700 dark:bg-teal-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-teal-800 shadow transition"
                  >
                    Snap Photo
                  </button>
                  <button
                    onClick={() => setIsWebcamOpen(false)}
                    className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : selfiePreview ? (
              <div className="relative w-full flex flex-col items-center">
                <img
                  src={selfiePreview}
                  alt="Selfie Preview"
                  className="max-h-44 rounded-lg object-contain shadow-sm border border-slate-200 dark:border-slate-700"
                />
                <div className="mt-3 flex items-center space-x-3">
                  <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium flex items-center space-x-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>Live Capture Ready</span>
                  </span>
                  <button
                    onClick={() => setIsWebcamOpen(true)}
                    className="text-xs text-teal-700 dark:text-teal-400 hover:underline"
                  >
                    Retake
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center space-y-3 p-4">
                {cameraError && (
                  <div className="text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 p-2 rounded-lg max-w-sm mb-1">
                    {cameraError}
                  </div>
                )}
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <button
                    onClick={() => {
                      setCameraError(null);
                      setIsWebcamOpen(true);
                    }}
                    className="flex items-center space-x-2 rounded-lg bg-slate-100 dark:bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-800 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 transition"
                  >
                    <Camera className="h-4 w-4 text-teal-600 dark:text-teal-400" />
                    <span>Open Camera</span>
                  </button>
                  <label className="flex items-center space-x-2 rounded-lg bg-slate-100 dark:bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-800 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 cursor-pointer transition">
                    <Upload className="h-4 w-4 text-slate-500" />
                    <span>Upload Image</span>
                    <input type="file" accept="image/*" onChange={handleSelfieChange} className="hidden" />
                  </label>
                </div>
                <span className="text-[11px] text-slate-500">
                  Optional for document-only verification; recommended for identity comparison.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Error Alert if any */}
      {errorMessage && (
        <div className="rounded-xl border border-rose-300 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/40 p-4 flex items-center space-x-3 text-rose-800 dark:text-rose-200 text-xs shadow-sm">
          <AlertCircle className="h-5 w-5 text-rose-600 dark:text-rose-400 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Verification Stepper & Execute Button */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 shadow-sm">
        <div>
          {isProcessing ? (
            <div className="flex items-center space-x-3">
              <RefreshCw className="h-5 w-5 text-teal-600 dark:text-teal-400 animate-spin" />
              <div>
                <span className="text-sm font-semibold text-slate-900 dark:text-white">
                  Document Screening Verification In Progress...
                </span>
                <p className="text-xs text-teal-700 dark:text-teal-300 font-mono mt-0.5">{pipelineStep}</p>
              </div>
            </div>
          ) : (
            <div>
              <span className="text-sm font-semibold text-slate-900 dark:text-white">
                Ready for Verification
              </span>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                Executes Image Quality Assessment, OCR, ICAO 7-3-1 Check Digits, Forensic Integrity Signals, and Biometric Comparison.
              </p>
            </div>
          )}
        </div>

        <button
          onClick={runScreening}
          disabled={isProcessing || !docFile}
          className={`flex items-center justify-center space-x-2 rounded-xl px-6 py-2.5 text-sm font-bold shadow-sm transition-all ${
            isProcessing || !docFile
              ? "bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-600 cursor-not-allowed border border-slate-300 dark:border-slate-700"
              : "bg-teal-700 dark:bg-teal-600 text-white hover:bg-teal-800 dark:hover:bg-teal-500 hover:scale-[1.01]"
          }`}
        >
          <span>Initiate Full Screening</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
