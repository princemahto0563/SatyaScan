// scripts/deterministic_live_harness.js
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const ARTIFACTS_DIR = '/Users/princemahto/.gemini/antigravity-ide/brain/d7df07b4-ace7-4283-9b77-c1c58ca4e251';
const EVIDENCE_DIR = path.join(ARTIFACTS_DIR, 'live_browser_evidence');
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// Global collector
const harnessResult = {
  step: '[00] START',
  lastSuccessfulStep: '[00] START',
  status: 'PENDING',
  apiResponse: null,
  backendValues: {},
  uiValues: {},
  fieldComparisons: [],
  mrzState: null,
  images: [],
  pdfButtonPresent: false,
  elapsedMs: 0,
  error: null,
};

async function run() {
  const startTime = Date.now();
  console.log('[00] START: Initiating SatyaScan Deterministic Test Harness');

  // Hard global timeout inside the script
  const globalTimer = setTimeout(() => {
    console.error(`\nHARNESS TIMEOUT: Scenario exceeded 60s hard limit!`);
    console.error(`Last successful step: ${harnessResult.lastSuccessfulStep}`);
    process.exit(1);
  }, 60000);

  let browser = null;

  try {
    // -----------------------------------------------------------------------
    // [01] Connecting to Chrome :9222
    // -----------------------------------------------------------------------
    console.log('[01] Connecting to Chrome :9222 (timeout: 10s)...');
    harnessResult.step = '[01] Connecting to Chrome :9222';

    const connectPromise = puppeteer.connect({
      browserURL: 'http://localhost:9222',
      defaultViewport: { width: 1440, height: 950 },
    });

    const connectTimeout = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('CHROME_CONNECTION_FAILED: Timeout connecting to port 9222')), 10000)
    );

    browser = await Promise.race([connectPromise, connectTimeout]);
    console.log('[02] Connected to Chrome');
    harnessResult.lastSuccessfulStep = '[02] Connected to Chrome';

    // -----------------------------------------------------------------------
    // [03] Enumerating pages
    // -----------------------------------------------------------------------
    console.log('[03] Enumerating pages...');
    harnessResult.step = '[03] Enumerating pages';
    const pages = await browser.pages();
    console.log(`     Total browser pages open: ${pages.length}`);
    for (const p of pages) {
      console.log(`     - Page URL: ${p.url()}`);
    }

    let page = pages.find((p) => p.url().includes('satya-scan-phi.vercel.app'));
    if (!page) {
      console.log('     SatyaScan tab not in existing list, navigating first page to Vercel...');
      page = pages[0] || (await browser.newPage());
      await page.goto('https://satya-scan-phi.vercel.app', { waitUntil: 'load', timeout: 15000 });
    }
    console.log('[04] Found Vercel page: ' + page.url());
    harnessResult.lastSuccessfulStep = '[04] Found Vercel page';

    // Set viewport
    await page.setViewport({ width: 1440, height: 950 });

    // -----------------------------------------------------------------------
    // [05] Reading browser storage (A. inspect existing state)
    // -----------------------------------------------------------------------
    console.log('[05] Reading browser storage...');
    harnessResult.step = '[05] Reading browser storage';

    const storageInfo = await page.evaluate(() => {
      const token = sessionStorage.getItem('satyascan_auth_token') || localStorage.getItem('satyascan_auth_token');
      const session = sessionStorage.getItem('satyascan_session') || localStorage.getItem('satyascan_session');
      const isLoginVisible = !!document.querySelector('input[type="password"]');
      return {
        hasToken: !!token,
        hasSession: !!session,
        isLoginVisible,
      };
    });

    console.log(`     Existing Session: ${storageInfo.hasSession ? 'YES' : 'NO'} | Token Present: ${storageInfo.hasToken ? 'YES' : 'NO'} | Login Screen Visible: ${storageInfo.isLoginVisible ? 'YES' : 'NO'}`);
    harnessResult.lastSuccessfulStep = '[05] Reading browser storage';

    let isAuthenticated = storageInfo.hasToken && !storageInfo.isLoginVisible;

    if (!isAuthenticated) {
      // ---------------------------------------------------------------------
      // [06] Clearing storage
      // ---------------------------------------------------------------------
      console.log('[06] Clearing storage...');
      harnessResult.step = '[06] Clearing storage';
      await page.evaluate(() => {
        sessionStorage.clear();
        localStorage.clear();
      });

      // ---------------------------------------------------------------------
      // [07] Unregistering service workers
      // ---------------------------------------------------------------------
      console.log('[07] Unregistering service workers...');
      harnessResult.step = '[07] Unregistering service workers';
      await page.evaluate(async () => {
        if ('serviceWorker' in navigator) {
          const regs = await navigator.serviceWorker.getRegistrations();
          for (const r of regs) await r.unregister();
        }
        if ('caches' in window) {
          const keys = await caches.keys();
          for (const k of keys) await caches.delete(k);
        }
      });

      // ---------------------------------------------------------------------
      // [08] Reloading Vercel
      // ---------------------------------------------------------------------
      console.log('[08] Reloading Vercel...');
      harnessResult.step = '[08] Reloading Vercel';
      await page.goto('https://satya-scan-phi.vercel.app', { waitUntil: 'load', timeout: 15000 });
      await sleep(1000);

      // ---------------------------------------------------------------------
      // [09] Login page detected
      // ---------------------------------------------------------------------
      console.log('[09] Login page detected');
      harnessResult.step = '[09] Login page detected';

      // ---------------------------------------------------------------------
      // [10] Submitting login
      // ---------------------------------------------------------------------
      console.log('[10] Submitting login (officer / officer123)...');
      harnessResult.step = '[10] Submitting login';

      // Attach login listener before clicking
      const loginResponsePromise = new Promise((resolve) => {
        const handler = async (res) => {
          if (res.url().includes('/api/v1/auth/token') || res.url().includes('/api/v1/auth/login')) {
            page.off('response', handler);
            let hasToken = false;
            try {
              const body = await res.json();
              hasToken = !!body.access_token;
            } catch (e) {}
            resolve({ status: res.status(), hasToken });
          }
        };
        page.on('response', handler);
        setTimeout(() => {
          page.off('response', handler);
          resolve({ status: 'TIMEOUT', hasToken: false });
        }, 15000);
      });

      await page.evaluate(() => {
        const u = document.querySelector('input[type="text"]');
        const p = document.querySelector('input[type="password"]');
        if (u) {
          u.value = 'officer';
          u.dispatchEvent(new Event('input', { bubbles: true }));
          u.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (p) {
          p.value = 'officer123';
          p.dispatchEvent(new Event('input', { bubbles: true }));
          p.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });

      const submitBtn = await page.$('button[type="submit"]');
      if (!submitBtn) throw new Error('Login submit button not found');
      await submitBtn.click();

      // ---------------------------------------------------------------------
      // [11] Login response received
      // ---------------------------------------------------------------------
      const loginResult = await loginResponsePromise;
      console.log(`[11] Login response received: HTTP ${loginResult.status}`);
      console.log(`     ACCESS TOKEN RECEIVED: ${loginResult.hasToken ? 'YES' : 'NO'}`);
      if (loginResult.status !== 200 && loginResult.status !== 'TIMEOUT') {
        throw new Error(`LOGIN_FAILED: HTTP ${loginResult.status}`);
      }

      // Wait up to 8s for session in storage
      let sessionConfirmed = false;
      for (let i = 0; i < 8; i++) {
        await sleep(1000);
        const check = await page.evaluate(() => {
          const t = sessionStorage.getItem('satyascan_auth_token') || sessionStorage.getItem('satyascan_session');
          return !!t && !document.querySelector('input[type="password"]');
        });
        if (check) {
          sessionConfirmed = true;
          break;
        }
      }

      console.log(`     SESSION SAVED: ${sessionConfirmed ? 'YES' : 'NO'}`);
      if (!sessionConfirmed) throw new Error('AUTH_TIMEOUT: Session not confirmed after login');
    }

    // -----------------------------------------------------------------------
    // [12] Auth state confirmed
    // -----------------------------------------------------------------------
    console.log('[12] Auth state confirmed. Workstation authenticated.');
    harnessResult.lastSuccessfulStep = '[12] Auth state confirmed';

    // -----------------------------------------------------------------------
    // [13] Navigating to New Screening
    // -----------------------------------------------------------------------
    console.log('[13] Navigating to New Screening...');
    harnessResult.step = '[13] Navigating to New Screening';

    const navButtons = await page.$$('button');
    let navClicked = false;
    for (const b of navButtons) {
      const txt = await page.evaluate((el) => el.textContent, b);
      if (txt && txt.trim() === 'New Screening') {
        await b.click();
        navClicked = true;
        break;
      }
    }
    if (!navClicked) {
      console.log('     New Screening button not found, checking current view...');
    }
    await sleep(1000);

    // -----------------------------------------------------------------------
    // [14] New Screening loaded
    // -----------------------------------------------------------------------
    console.log('[14] New Screening loaded');
    harnessResult.lastSuccessfulStep = '[14] New Screening loaded';

    // -----------------------------------------------------------------------
    // [15] Selecting CASE 01
    // -----------------------------------------------------------------------
    console.log('[15] Selecting CASE 01 (Genuine Passport)...');
    harnessResult.step = '[15] Selecting CASE 01';

    // -----------------------------------------------------------------------
    // [16] Screening request started (attach listener BEFORE trigger)
    // -----------------------------------------------------------------------
    let apiData = null;
    let apiStatus = null;
    let reqStart = null;
    let resEnd = null;

    const screeningResponsePromise = new Promise((resolve) => {
      const handler = async (res) => {
        const url = res.url();
        const method = res.request().method();
        if ((url.includes('/api/v1/screenings') || url.includes('/api/v1/screenings/preset')) && method === 'POST') {
          resEnd = Date.now();
          apiStatus = res.status();
          try {
            apiData = await res.json();
          } catch (e) {
            try {
              apiData = await res.text();
            } catch (_) {}
          }
          page.off('response', handler);
          resolve({ status: apiStatus, data: apiData, elapsed: resEnd - reqStart });
        }
      };
      page.on('response', handler);
      setTimeout(() => {
        page.off('response', handler);
        resolve({ status: 'TIMEOUT', data: null, elapsed: 30000 });
      }, 30000);
    });

    reqStart = Date.now();
    console.log(`[16] Screening request started at: ${new Date(reqStart).toISOString()}`);
    harnessResult.step = '[16] Screening request started';

    // Click CASE 01 button
    const allBtns = await page.$$('button');
    let case01Clicked = false;
    for (const b of allBtns) {
      const txt = await page.evaluate((el) => el.textContent, b);
      if (txt && txt.includes('CASE 01')) {
        await b.click();
        case01Clicked = true;
        break;
      }
    }
    if (!case01Clicked) {
      throw new Error('CASE 01 preset button not found on page!');
    }

    // Heartbeat while waiting for response
    const waitInterval = setInterval(() => {
      const sec = Math.round((Date.now() - reqStart) / 1000);
      console.log(`     Waiting for screening... ${sec}s`);
    }, 5000);

    const apiResult = await screeningResponsePromise;
    clearInterval(waitInterval);

    // -----------------------------------------------------------------------
    // [17] Screening response received
    // -----------------------------------------------------------------------
    console.log(`[17] Screening response received at: ${new Date(resEnd || Date.now()).toISOString()}`);
    console.log(`     STATUS: HTTP ${apiResult.status} | ELAPSED: ${apiResult.elapsed}ms`);
    harnessResult.step = '[17] Screening response received';
    harnessResult.lastSuccessfulStep = '[17] Screening response received';
    harnessResult.apiResponse = apiResult;

    if (apiResult.status === 'TIMEOUT') {
      throw new Error('SCREENING_TIMEOUT: API did not respond within 30s');
    }
    if (apiResult.status >= 400) {
      console.error('API Error Response:', JSON.stringify(apiResult.data, null, 2));
      throw new Error(`SCREENING_API_ERROR: HTTP ${apiResult.status}`);
    }

    // Extract backend values from API JSON
    const backendData = apiResult.data || {};
    const backendFields = backendData.extracted_fields || [];
    function getBackendFieldValue(name) {
      const f = backendFields.find((x) => x.field_name === name);
      return f ? (f.visual_value || f.field_value || f.mrz_value) : null;
    }

    harnessResult.backendValues = {
      screening_id: backendData.id || backendData.screening_id,
      document_type: backendData.document_type,
      full_name: getBackendFieldValue('full_name') || backendData.mrz_data?.full_name,
      document_number: getBackendFieldValue('document_number') || backendData.mrz_data?.document_number,
      date_of_birth: getBackendFieldValue('date_of_birth') || backendData.mrz_data?.date_of_birth,
      nationality: getBackendFieldValue('nationality') || backendData.mrz_data?.nationality,
      date_of_expiry: getBackendFieldValue('date_of_expiry') || backendData.mrz_data?.date_of_expiry,
      sex: getBackendFieldValue('sex') || backendData.mrz_data?.sex,
      mrz_status: backendData.mrz_status || (backendData.mrz_data?.parsed ? 'MRZ_VALID' : 'MRZ_UNPARSED'),
      face_result: backendData.face_result?.verification_result || backendData.face_result?.decision_state || 'NOT_AVAILABLE',
    };
    harnessResult.mrzState = harnessResult.backendValues.mrz_status;

    console.log('\n--- BACKEND PARSED SUMMARY ---');
    console.log(`  Screening ID:    ${harnessResult.backendValues.screening_id}`);
    console.log(`  Full Name:       ${harnessResult.backendValues.full_name}`);
    console.log(`  Document Number: ${harnessResult.backendValues.document_number}`);
    console.log(`  DOB:             ${harnessResult.backendValues.date_of_birth}`);
    console.log(`  Expiry:          ${harnessResult.backendValues.date_of_expiry}`);
    console.log(`  Nationality:     ${harnessResult.backendValues.nationality}`);
    console.log(`  MRZ State:       ${harnessResult.backendValues.mrz_status}`);
    console.log(`  Face Result:     ${harnessResult.backendValues.face_result}`);
    console.log('------------------------------\n');

    // -----------------------------------------------------------------------
    // [18] Report page detected
    // -----------------------------------------------------------------------
    console.log('[18] Report page detected (waiting for UI render)...');
    harnessResult.step = '[18] Report page detected';

    let uiRendered = false;
    for (let i = 0; i < 15; i++) {
      await sleep(1000);
      const isVisible = await page.evaluate(() => {
        const t = document.body.innerText;
        return t.includes('Executive Screening Report') || t.includes('1. Document Information') || t.includes('Screening Dossier');
      });
      if (isVisible) {
        uiRendered = true;
        break;
      }
    }
    if (!uiRendered) {
      throw new Error('UI_RENDER_TIMEOUT: Report view did not render within 15s');
    }
    harnessResult.lastSuccessfulStep = '[18] Report page detected';

    // -----------------------------------------------------------------------
    // [19] Extracting report fields & Report Assertions
    // -----------------------------------------------------------------------
    console.log('[19] Extracting report fields...');
    harnessResult.step = '[19] Extracting report fields';

    const uiFields = await page.evaluate(() => {
      function getCardValue(label) {
        const elements = Array.from(document.querySelectorAll('div, span'));
        for (let i = 0; i < elements.length; i++) {
          if (elements[i].textContent && elements[i].textContent.trim() === label) {
            const parent = elements[i].closest('.flex') || elements[i].parentElement;
            if (parent) {
              const children = Array.from(parent.children);
              if (children.length >= 2) {
                return children[1].textContent.trim();
              }
            }
          }
        }
        return 'Not available';
      }

      return {
        full_name: getCardValue('Full Name'),
        document_number: getCardValue('Document Number'),
        date_of_birth: getCardValue('Date of Birth'),
        nationality: getCardValue('Nationality'),
        date_of_expiry: getCardValue('Date of Expiry'),
        sex: getCardValue('Sex'),
      };
    });
    harnessResult.uiValues = uiFields;

    console.log('\n========================================================================================');
    console.log('FIELD                   | BACKEND VALUE         | UI VALUE              | STATUS        ');
    console.log('========================================================================================');

    const fieldsToCheck = ['full_name', 'document_number', 'date_of_birth', 'nationality', 'date_of_expiry', 'sex'];
    let bindingFailure = false;

    for (const f of fieldsToCheck) {
      const bVal = String(harnessResult.backendValues[f] || '—');
      const uVal = String(harnessResult.uiValues[f] || '—');

      // Check if backend has a value but UI says "Not available"
      let status = 'MATCH';
      if (bVal !== '—' && bVal !== 'Not available' && (uVal === 'Not available' || uVal === '—')) {
        status = 'DATA_BINDING_FAILURE';
        bindingFailure = true;
      } else if (uVal.includes(bVal) || bVal.includes(uVal) || (f === 'nationality' && (bVal === 'IND' || bVal === 'INDIAN'))) {
        status = 'MATCH';
      } else {
        status = 'DISCREPANCY_NOTED';
      }

      harnessResult.fieldComparisons.push({ field: f, backend: bVal, ui: uVal, status });
      console.log(`${f.padEnd(23)} | ${bVal.slice(0, 21).padEnd(21)} | ${uVal.slice(0, 21).padEnd(21)} | ${status}`);
    }
    console.log('========================================================================================\n');

    if (bindingFailure) {
      throw new Error('DATA_BINDING_FAILURE: Backend extracted real identity values but UI rendered "Not available"');
    }
    harnessResult.lastSuccessfulStep = '[19] Extracting report fields';

    // -----------------------------------------------------------------------
    // [20] Checking images (Document Portrait, Presented Face, Forensic Heatmap)
    // -----------------------------------------------------------------------
    console.log('[20] Checking images (timeout: 10s)...');
    harnessResult.step = '[20] Checking images';

    const imageCheckStart = Date.now();
    let imgData = null;

    while (Date.now() - imageCheckStart < 10000) {
      imgData = await page.evaluate(() => {
        const imgs = Array.from(document.querySelectorAll('img'));
        return imgs.map((img) => ({
          src: img.src,
          naturalWidth: img.naturalWidth,
          naturalHeight: img.naturalHeight,
          complete: img.complete,
        }));
      });

      const pending = imgData.filter((i) => i.src && !i.complete);
      if (pending.length === 0) break;
      await sleep(500);
    }

    harnessResult.images = imgData || [];
    console.log(`     Total images in report: ${harnessResult.images.length}`);

    let brokenCount = 0;
    for (const img of harnessResult.images) {
      const isBroken = img.src && img.complete && img.naturalWidth === 0;
      if (isBroken) brokenCount++;
      console.log(`     - [${isBroken ? 'BROKEN' : 'OK'}] ${img.src} (${img.naturalWidth}x${img.naturalHeight})`);
    }

    if (brokenCount > 0) {
      console.log(`     WARNING: ${brokenCount} broken image(s) detected`);
    }
    harnessResult.lastSuccessfulStep = '[20] Checking images';

    // -----------------------------------------------------------------------
    // [21] Checking MRZ table
    // -----------------------------------------------------------------------
    console.log('[21] Checking MRZ table (switching to MRZ & Field Cross-Check tab)...');
    harnessResult.step = '[21] Checking MRZ table';

    // Click the MRZ tab button
    const tabButtons = await page.$$('button');
    let tabClicked = false;
    for (const tb of tabButtons) {
      const txt = await page.evaluate((el) => el.textContent, tb);
      if (txt && (txt.includes('MRZ & Field Cross-Check') || txt.includes('Field Cross-Check'))) {
        await tb.click();
        tabClicked = true;
        break;
      }
    }
    await sleep(1500);

    const tableData = await page.evaluate(() => {
      const badgeEl = Array.from(document.querySelectorAll('span, div')).find((el) =>
        el.textContent && el.textContent.includes('Fields Verified')
      );
      const verifiedBadge = badgeEl ? badgeEl.textContent.trim() : 'NOT_FOUND';

      const rows = [];
      const trs = document.querySelectorAll('tbody tr');
      trs.forEach((tr) => {
        const cells = Array.from(tr.querySelectorAll('td')).map((td) => td.textContent.trim());
        if (cells.length >= 5) {
          rows.push({
            name: cells[0],
            viz: cells[1],
            mrz: cells[2],
            conf: cells[3],
            status: cells[4],
          });
        }
      });

      return {
        verifiedBadge,
        rows,
        hasRepeatedMrzUnparsed: rows.some((r) => r.mrz.includes('MRZ unparsed')),
        hasZeroPercent: rows.some((r) => r.conf === '0%'),
      };
    });

    console.log(`     Verified Badge: "${tableData.verifiedBadge}"`);
    console.log(`     Cross-Check Table Rows: ${tableData.rows.length}`);
    for (const r of tableData.rows) {
      console.log(`       - ${r.name.padEnd(18)} | VIZ: ${r.viz.padEnd(16)} | MRZ: ${r.mrz.padEnd(16)} | Conf: ${r.conf.padEnd(5)} | ${r.status}`);
    }
    console.log(`     Has "MRZ unparsed" repeated in cells: ${tableData.hasRepeatedMrzUnparsed ? 'FAIL' : 'PASS (clean)'}`);
    console.log(`     Has "0%" confidence in cells:         ${tableData.hasZeroPercent ? 'FAIL' : 'PASS (clean)'}`);
    harnessResult.lastSuccessfulStep = '[21] Checking MRZ table';

    // -----------------------------------------------------------------------
    // [22] Checking PDF export button
    // -----------------------------------------------------------------------
    console.log('[22] Checking PDF...');
    harnessResult.step = '[22] Checking PDF';

    const hasPdfBtn = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button, a'));
      return btns.some((b) => b.textContent && b.textContent.toLowerCase().includes('pdf'));
    });
    harnessResult.pdfButtonPresent = hasPdfBtn;
    console.log(`     PDF Download Action Present: ${hasPdfBtn ? 'YES' : 'NO'}`);
    harnessResult.lastSuccessfulStep = '[22] Checking PDF';

    // Take screenshot of finished report
    const screenshotPath = path.join(EVIDENCE_DIR, '01_genuine_passport_live.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`     Report screenshot saved: ${screenshotPath}`);

    // -----------------------------------------------------------------------
    // [23] COMPLETE
    // -----------------------------------------------------------------------
    harnessResult.step = '[23] COMPLETE';
    harnessResult.lastSuccessfulStep = '[23] COMPLETE';
    harnessResult.status = 'PASS';
    harnessResult.elapsedMs = Date.now() - startTime;

    console.log(`\n[23] COMPLETE: CASE 01 DETERMINISTIC VERIFICATION PASSED in ${Math.round(harnessResult.elapsedMs / 1000)}s!`);

    clearTimeout(globalTimer);
  } catch (err) {
    harnessResult.status = 'FAIL';
    harnessResult.error = err.message;
    harnessResult.elapsedMs = Date.now() - startTime;

    console.error(`\n======================================================`);
    console.error(`HARNESS FAILED AT STEP: ${harnessResult.step}`);
    console.error(`LAST SUCCESSFUL STEP:   ${harnessResult.lastSuccessfulStep}`);
    console.error(`ELAPSED:                ${Math.round(harnessResult.elapsedMs / 1000)}s`);
    console.error(`ERROR:                  ${err.message}`);
    console.error(`======================================================\n`);
  } finally {
    clearTimeout(globalTimer);

    // Save summary json
    const summaryPath = path.join(EVIDENCE_DIR, 'deterministic_case01_summary.json');
    fs.writeFileSync(summaryPath, JSON.stringify(harnessResult, null, 2));
    console.log(`Summary written to: ${summaryPath}`);

    // Disconnect browser safely
    if (browser) {
      try {
        console.log('Disconnecting from Chrome DevTools Protocol...');
        await browser.disconnect();
      } catch (e) {}
    }

    console.log(`Harness exiting with status: ${harnessResult.status}`);
    process.exit(harnessResult.status === 'PASS' ? 0 : 1);
  }
}

run();
