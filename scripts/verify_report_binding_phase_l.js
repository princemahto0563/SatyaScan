// scripts/verify_report_binding_phase_l.js
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CONV_ID = 'b3033d63-4f18-4514-aad8-3a17ffd81b70';
const ARTIFACTS_DIR = `/Users/princemahto/.gemini/antigravity-ide/brain/${CONV_ID}`;
const EVIDENCE_DIR = path.join(ARTIFACTS_DIR, 'phase_l_evidence');
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function run() {
  console.log('====================================================================');
  console.log('   SATYASCAN PHASE L — PRODUCTION END-TO-END VERIFICATION           ');
  console.log('====================================================================');

  const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
  const pages = await browser.pages();
  let page = pages.find((p) => p.url().includes('satya-scan-phi.vercel.app'));
  if (!page) {
    page = await browser.newPage();
  }

  await page.setViewport({ width: 1440, height: 950 });

  const consoleLogs = [];
  const networkErrors = [];

  page.on('console', (msg) => {
    const text = msg.text();
    const type = msg.type();
    consoleLogs.push({ type, text });
    if (type === 'error' || type === 'warning') {
      console.log(`[Browser Console ${type}]: ${text}`);
    }
  });

  page.on('requestfailed', (req) => {
    networkErrors.push({ url: req.url(), errorText: req.failure().errorText });
    console.log(`[Network Failed]: ${req.url()} - ${req.failure().errorText}`);
  });

  console.log('\n[1] Navigating to https://satya-scan-phi.vercel.app and purging stale SW cache...');
  await page.goto('https://satya-scan-phi.vercel.app', { waitUntil: 'networkidle2' });

  // Purge any stale service worker / cache to ensure latest deployment
  await page.evaluate(async () => {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      for (const r of registrations) {
        await r.unregister();
      }
      const keys = await caches.keys();
      for (const k of keys) {
        await caches.delete(k);
      }
      sessionStorage.clear();
      localStorage.clear();
    } catch (e) {}
  });

  // Reload with bypass cache
  await page.goto('https://satya-scan-phi.vercel.app', { waitUntil: 'networkidle2' });
  await sleep(1500);

  // Authenticate if on login screen
  const isLoginForm = await page.evaluate(() => {
    return (
      document.body.innerText.includes('Authenticate Checkpoint Workstation') ||
      document.body.innerText.includes('Checkpoint Access')
    );
  });

  if (isLoginForm) {
    console.log('[2] Authenticating as Checkpoint Officer (delhi_airport)...');
    await page.click('#login-submit-button');
    await sleep(3000);
  }

  // Go to New Screening
  console.log('[3] Navigating to New Screening...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find((el) => el.textContent.includes('New Screening'));
    if (b) b.click();
  });
  await sleep(2000);

  // Select CASE 01 (Genuine Passport Arjun Sharma)
  console.log('[4] Selecting CASE 01 (Genuine Passport Arjun Sharma)...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(
      (el) =>
        el.textContent.includes('CASE 01') ||
        el.textContent.includes('Genuine Passport')
    );
    if (b) b.click();
  });

  console.log('Waiting for Case 01 screening to complete and report to render...');
  let case01Done = false;
  for (let i = 0; i < 40; i++) {
    await sleep(1000);
    const bodyText = await page.evaluate(() => document.body.innerText);
    if (
      bodyText.includes('Executive Screening Report') ||
      bodyText.includes('1. Document Information') ||
      bodyText.includes('ROUTINE CLEARANCE PERMITTED') ||
      bodyText.includes('LOW RISK')
    ) {
      case01Done = true;
      console.log(`✓ Case 01 completed and report rendered in ~${i + 1}s`);
      break;
    }
  }

  if (!case01Done) {
    throw new Error('Case 01 screening did not complete within 40 seconds');
  }

  await sleep(3000);

  // Capture Full Page Screenshot for Case 01
  const case01ScreenshotPath = path.join(EVIDENCE_DIR, '01_case01_executive_report.png');
  await page.screenshot({ path: case01ScreenshotPath, fullPage: true });
  console.log(`Captured Case 01 report screenshot: ${case01ScreenshotPath}`);

  // Detailed Verification of Report Data for Case 01
  console.log('\n[5] Verifying Case 01 Report Data-Binding & Assets in DOM:');
  const case01Data = await page.evaluate(() => {
    const body = document.body.innerText;
    const imgs = Array.from(document.querySelectorAll('img')).map((img) => ({
      src: img.src,
      alt: img.alt,
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
      complete: img.complete,
    }));

    const docPortraitImg = imgs.find((i) => i.alt.includes('Document Portrait'));
    const liveFaceImg = imgs.find((i) => i.alt.includes('Presented Face'));
    const heatmapImg = imgs.find(
      (i) => i.alt.includes('Forensic Heatmap') || i.alt.includes('Original Document')
    );

    // Extract Case ID
    const caseIdMatch = body.match(/SAT-\d{4}-[A-Z0-9]+/);
    const screeningId = caseIdMatch ? caseIdMatch[0] : null;

    return {
      screeningId,
      hasDocumentSection: body.includes('1. Document Information'),
      hasFullName: body.includes('ARJUN SHARMA'),
      hasDocNumber: body.includes('Z1234567'),
      hasDOB: body.includes('14/05/1992') || body.includes('1992-05-14'),
      hasNationality: body.includes('INDIAN') || body.includes('IND'),
      hasExpiry: body.includes('13/05/2028') || body.includes('2028-05-13'),
      hasSex: body.includes('MALE'),
      hasOcrStatus: body.includes('OCR: SUCCESS') || body.includes('OCR: PARTIAL'),
      hasMrzBadge: body.includes('MRZ: 7-3-1 PASS') || body.includes('7-3-1 PASS'),
      hasVizMrzMatch: body.includes('VIZ↔MRZ: MATCH'),

      hasIdentitySection: body.includes('2. Identity Verification'),
      hasMatchDecision: body.includes('VERIFIED MATCH'),
      hasSimilarityScore:
        body.includes('Similarity: 0.9') || body.includes('Similarity: 1.0'),
      hasFaceQuality: body.includes('Face Quality: GOOD'),

      docPortraitImg,
      liveFaceImg,
      heatmapImg,

      hasForensicsSection:
        body.includes('Forensic Signal Analysis') ||
        body.includes('Document Image Inspector'),
      hasElaScore: body.includes('Error Level Analysis (ELA)'),
      hasNoiseScore: body.includes('Sensor Noise Residual'),
      hasCopyMove: body.includes('Copy-Move Duplication Check'),

      hasRiskScore:
        body.includes('5. Contributing Risk Factors') ||
        body.includes('Risk Score') ||
        body.includes('LOW RISK'),

      pdfUrl:
        Array.from(document.querySelectorAll('a')).find((a) =>
          a.textContent.includes('Download Official PDF')
        )?.href || null,
    };
  });

  console.log('Case 01 Extracted Info:', {
    screeningId: case01Data.screeningId,
    fullName: case01Data.hasFullName,
    docNumber: case01Data.hasDocNumber,
    dob: case01Data.hasDOB,
    nationality: case01Data.hasNationality,
    expiry: case01Data.hasExpiry,
    sex: case01Data.hasSex,
    ocrStatus: case01Data.hasOcrStatus,
    mrzBadge: case01Data.hasMrzBadge,
    matchDecision: case01Data.hasMatchDecision,
    docPortraitLoaded:
      case01Data.docPortraitImg && case01Data.docPortraitImg.naturalWidth > 0,
    docPortraitDims: case01Data.docPortraitImg ? `${case01Data.docPortraitImg.naturalWidth}x${case01Data.docPortraitImg.naturalHeight}` : 'none',
    liveFaceLoaded:
      case01Data.liveFaceImg && case01Data.liveFaceImg.naturalWidth > 0,
    liveFaceDims: case01Data.liveFaceImg ? `${case01Data.liveFaceImg.naturalWidth}x${case01Data.liveFaceImg.naturalHeight}` : 'none',
    heatmapLoaded:
      case01Data.heatmapImg && case01Data.heatmapImg.naturalWidth > 0,
    heatmapDims: case01Data.heatmapImg ? `${case01Data.heatmapImg.naturalWidth}x${case01Data.heatmapImg.naturalHeight}` : 'none',
  });

  // Switch to Tab 2: Validation (VIZ vs MRZ Cross-Check Table)
  console.log('\n[6] Navigating to Tab 2: Validation (VIZ vs MRZ Cross-Check)...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const tabBtn = btns.find(
      (b) => b.textContent.includes('Validation') || b.textContent.includes('MRZ')
    );
    if (tabBtn) tabBtn.click();
  });
  await sleep(1500);

  const crossCheckData = await page.evaluate(() => {
    const text = document.body.innerText;
    const rows = Array.from(document.querySelectorAll('tr')).map((tr) => tr.innerText);
    return {
      rowCount: rows.length,
      rows: rows.slice(0, 10),
      hasDocumentTypeRow: text.includes('DOCUMENT TYPE'),
      hasDocumentNumberRow: text.includes('DOCUMENT NUMBER'),
      hasSurnameRow: text.includes('SURNAME'),
      hasGivenNamesRow: text.includes('GIVEN NAMES'),
      hasFullNameRow: text.includes('FULL NAME'),
      hasNationalityRow: text.includes('NATIONALITY'),
      hasDobRow: text.includes('DATE OF BIRTH'),
      hasExpiryRow: text.includes('DATE OF EXPIRY'),
      hasSexRow: text.includes('SEX'),
      hasMatchBadges: text.includes('Match') || text.includes('MATCH'),
    };
  });

  const tab2ScreenshotPath = path.join(EVIDENCE_DIR, '02_case01_cross_check_tab.png');
  await page.screenshot({ path: tab2ScreenshotPath, fullPage: true });
  console.log('Cross-Check Table:', crossCheckData);

  // Test PDF Fetch
  console.log('\n[7] Testing Official PDF Download for Case 01...');
  let pdfResult = null;
  if (case01Data.pdfUrl) {
    const sanitizedPdfUrl = case01Data.pdfUrl.replace(/token=[^&]+/g, 'token=[REDACTED]');
    console.log('PDF URL:', sanitizedPdfUrl);
    pdfResult = await page.evaluate(async (url) => {
      try {
        const resp = await fetch(url);
        const blob = await resp.blob();
        return {
          status: resp.status,
          contentType: resp.headers.get('content-type'),
          size: blob.size,
          ok: resp.ok,
        };
      } catch (e) {
        return { error: e.message };
      }
    }, case01Data.pdfUrl);
    console.log('PDF Download Response:', pdfResult);
  }

  // Switch back to Tab 1 before testing Case 03
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const tabBtn = btns.find((b) => b.textContent.includes('Executive'));
    if (tabBtn) tabBtn.click();
  });
  await sleep(1000);

  // PHASE H — SCREENING DATA ISOLATION TEST
  console.log('\n[8] Phase H: Testing Screening Data Isolation with CASE 03 (DOB Altered)...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const newBtn = btns.find((b) => b.textContent.includes('New Screening'));
    if (newBtn) newBtn.click();
  });
  await sleep(2000);

  // Select CASE 03 (DOB Altered)
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(
      (el) =>
        el.textContent.includes('CASE 03') ||
        el.textContent.includes('DOB Altered')
    );
    if (b) b.click();
  });

  console.log('Waiting for Case 03 screening to complete...');
  let case03Done = false;
  for (let i = 0; i < 40; i++) {
    await sleep(1000);
    const bodyText = await page.evaluate(() => document.body.innerText);
    if (
      bodyText.includes('Executive Screening Report') ||
      bodyText.includes('1. Document Information') ||
      bodyText.includes('DOB Mismatch') ||
      bodyText.includes('HIGH RISK') ||
      bodyText.includes('FLAGGED FOR SECONDARY INSPECTION') ||
      bodyText.includes('Screening Ref: SAT-2026-')
    ) {
      case03Done = true;
      console.log(`✓ Case 03 completed and report rendered in ~${i + 1}s`);
      break;
    }
  }

  if (!case03Done) {
    throw new Error('Case 03 screening did not complete within 40 seconds');
  }

  await sleep(3000);

  const case03ScreenshotPath = path.join(EVIDENCE_DIR, '03_case03_dob_mismatch_report.png');
  await page.screenshot({ path: case03ScreenshotPath, fullPage: true });
  console.log(`Captured Case 03 report screenshot: ${case03ScreenshotPath}`);

  const case03Data = await page.evaluate(() => {
    const body = document.body.innerText;
    const caseIdMatch = body.match(/SAT-\d{4}-[A-Z0-9]+/);
    const screeningId = caseIdMatch ? caseIdMatch[0] : null;

    const imgs = Array.from(document.querySelectorAll('img')).map((img) => ({
      src: img.src,
      alt: img.alt,
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
    }));

    const docPortraitImg = imgs.find((i) => i.alt.includes('Document Portrait'));
    const liveFaceImg = imgs.find((i) => i.alt.includes('Presented Face'));
    const heatmapImg = imgs.find(
      (i) => i.alt.includes('Forensic Heatmap') || i.alt.includes('Original Document')
    );

    // Check discrepancy rendering
    const hasDiscrepancyBadge =
      body.includes('14/05/1990') ||
      body.includes('1990-05-14') ||
      body.includes('VIZ↔MRZ: MISMATCH') ||
      body.includes('MISMATCH') ||
      body.includes('Discrepancy');

    return {
      screeningId,
      hasDiscrepancyBadge,
      docPortraitImg,
      liveFaceImg,
      heatmapImg,
    };
  });

  console.log('Case 03 Isolation & Discrepancy Info:', {
    screeningId: case03Data.screeningId,
    isDistinctFromCase01:
      case03Data.screeningId !== null &&
      case03Data.screeningId !== case01Data.screeningId,
    hasDiscrepancyBadge: case03Data.hasDiscrepancyBadge,
    docPortraitLoaded:
      case03Data.docPortraitImg && case03Data.docPortraitImg.naturalWidth > 0,
    liveFaceLoaded:
      case03Data.liveFaceImg && case03Data.liveFaceImg.naturalWidth > 0,
    heatmapLoaded:
      case03Data.heatmapImg && case03Data.heatmapImg.naturalWidth > 0,
  });

  const isolationVerified =
    case03Data.screeningId !== null &&
    case01Data.screeningId !== null &&
    case03Data.screeningId !== case01Data.screeningId &&
    case03Data.docPortraitImg &&
    case03Data.docPortraitImg.src.includes(case03Data.screeningId) &&
    case01Data.docPortraitImg &&
    case01Data.docPortraitImg.src.includes(case01Data.screeningId);

  const finalVerdict =
    case01Data.hasFullName &&
    case01Data.hasDocNumber &&
    case01Data.hasDOB &&
    case01Data.hasNationality &&
    case01Data.hasExpiry &&
    case01Data.hasSex &&
    case01Data.docPortraitImg &&
    case01Data.docPortraitImg.naturalWidth > 0 &&
    case01Data.liveFaceImg &&
    case01Data.liveFaceImg.naturalWidth > 0 &&
    case01Data.heatmapImg &&
    case01Data.heatmapImg.naturalWidth > 0 &&
    crossCheckData.hasDocumentNumberRow &&
    crossCheckData.hasFullNameRow &&
    crossCheckData.hasDobRow &&
    pdfResult &&
    pdfResult.status === 200 &&
    pdfResult.size > 1000 &&
    isolationVerified;

  const sanitizeTokens = (obj) => {
    return JSON.parse(
      JSON.stringify(obj, (key, value) => {
        if (typeof value === 'string' && value.includes('token=')) {
          return value.replace(/token=[^&]+/g, 'token=[REDACTED]');
        }
        return value;
      })
    );
  };

  const summary = sanitizeTokens({
    case01Data,
    crossCheckData,
    pdfResult,
    case03Data,
    isolationVerified,
    finalVerdict,
  });

  fs.writeFileSync(
    path.join(EVIDENCE_DIR, 'phase_l_verification_summary.json'),
    JSON.stringify(summary, null, 2)
  );

  console.log('\n====================================================================');
  console.log(`PHASE L VERDICT: ${finalVerdict ? 'ALL CRITICAL CHECKS PASSED ✓' : 'SOME CHECKS FAILED ✗'}`);
  console.log('====================================================================');

  browser.disconnect();
}

run().catch((err) => {
  console.error('Error running Phase L verification:', err);
  process.exit(1);
});
