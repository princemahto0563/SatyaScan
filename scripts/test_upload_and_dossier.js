// scripts/test_upload_and_dossier.js
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CONV_ID = '973b0911-900c-45aa-b614-8fd248f6907f';
const ARTIFACTS_DIR = `/Users/princemahto/.gemini/antigravity-ide/brain/${CONV_ID}`;
const SCREENSHOT_DIR = path.join(ARTIFACTS_DIR, 'production_evidence');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function run() {
  console.log('=== Testing Real Production File Upload & Full Dossier Flow ===');
  const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
  const pages = await browser.pages();
  let page = pages.find((p) => p.url().includes('satya-scan-phi.vercel.app'));
  if (!page) page = await browser.newPage();

  await page.setViewport({ width: 1440, height: 950 });

  const apiRequests = [];
  const apiResponses = [];
  const consoleErrors = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('[Browser Console Error]:', msg.text());
      consoleErrors.push(msg.text());
    }
  });

  page.on('request', req => {
    if (req.url().includes('/api/v1')) {
      console.log('[API Req]:', req.method(), req.url());
      apiRequests.push({ method: req.method(), url: req.url() });
    }
  });

  page.on('response', res => {
    if (res.url().includes('/api/v1')) {
      console.log('[API Res]:', res.status(), res.url());
      apiResponses.push({ status: res.status(), url: res.url() });
    }
  });

  // Ensure authenticated
  const isLoginVisible = await page.evaluate(() => document.body.innerText.includes('Authenticate Checkpoint Workstation'));
  if (isLoginVisible) {
    console.log('Authenticating workstation...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const b = btns.find(el => el.textContent.includes('Authenticate Checkpoint Workstation'));
      if (b) b.click();
    });
    await sleep(2500);
  }

  // Navigate to New Screening
  console.log('Navigating to New Screening...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(el => el.textContent.includes('New Screening'));
    if (b) b.click();
  });
  await sleep(1500);

  // Upload files
  const docPath = '/Users/princemahto/Downloads/SatyaScan/data/genuine/case01_genuine_arjun.jpg';
  const selfiePath = '/Users/princemahto/Downloads/SatyaScan/data/selfies/case01_selfie_arjun.jpg';

  const inputs = await page.$$('input[type="file"]');
  console.log(`Found ${inputs.length} file inputs`);
  if (inputs.length < 2) {
    throw new Error(`Expected at least 2 file inputs, found ${inputs.length}`);
  }

  console.log('Uploading document file...');
  await inputs[0].uploadFile(docPath);
  await inputs[0].evaluate(el => el.dispatchEvent(new Event('change', { bubbles: true })));
  await sleep(1000);

  console.log('Uploading selfie file...');
  await inputs[1].uploadFile(selfiePath);
  await inputs[1].evaluate(el => el.dispatchEvent(new Event('change', { bubbles: true })));
  await sleep(1000);

  // Check button state
  const btnState = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(el => el.textContent.includes('Initiate Full Screening'));
    return { exists: !!b, disabled: b ? b.disabled : null, text: b ? b.textContent : null };
  });
  console.log('Initiate Full Screening button:', btnState);

  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '15_ready_for_screening.png') });

  // Click Initiate Full Screening
  console.log('Clicking Initiate Full Screening...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(el => el.textContent.includes('Initiate Full Screening'));
    if (b) b.click();
  });

  console.log('Waiting for backend processing...');
  let done = false;
  for (let i = 0; i < 45; i++) {
    await sleep(1000);
    const body = await page.evaluate(() => document.body.innerText);
    if (
      body.includes('Executive Screening Report') ||
      body.includes('Screening Dossier') ||
      body.includes('LOW RISK') ||
      body.includes('Document Information') ||
      body.includes('Integrity Assessment')
    ) {
      console.log(`Upload screening completed successfully in ~${i + 1}s!`);
      done = true;
      break;
    }
  }

  if (!done) {
    console.error('Screening timed out or did not render dossier in time.');
  }

  await sleep(2000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '16_upload_screening_result_full.png'), fullPage: true });

  // Verify all dossier details
  const dossierDetails = await page.evaluate(() => {
    const text = document.body.innerText;
    return {
      hasExecutiveReport: text.includes('Executive Screening Report') || text.includes('Screening Dossier'),
      hasDocNumber: text.includes('Z2184901') || text.includes('Document Number'),
      hasHolderName: text.includes('ARJUN') || text.includes('MEHTA'),
      hasDOB: text.includes('1990') || text.includes('Date of Birth'),
      hasRiskBand: text.includes('LOW RISK'),
      hasMrzStatus: text.includes('ICAO') || text.includes('7-3-1') || text.includes('Checksums'),
      hasForensics: text.includes('Error Level Analysis') || text.includes('ELA') || text.includes('Noise Residual'),
      hasBiometrics: text.includes('Biometric') || text.includes('Face Match') || text.includes('Confidence'),
      hasPdfBtn: !!Array.from(document.querySelectorAll('a, button')).find(b => b.textContent && b.textContent.includes('Download Official PDF')),
      hasAuditBtn: !!Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Verify Audit Trail')),
      hasAnchorBtn: !!Array.from(document.querySelectorAll('button')).find(b => b.textContent && (b.textContent.includes('Anchor') || b.textContent.includes('Blockchain')))
    };
  });
  console.log('Dossier Components Check:', dossierDetails);

  // Verify Cryptographic Audit Trail
  console.log('\nTesting Cryptographic Audit Trail Verification...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(x => x.textContent.includes('Verify Audit Trail'));
    if (b) b.click();
  });
  await sleep(2500);

  const auditVerificationStatus = await page.evaluate(() => {
    const text = document.body.innerText;
    return {
      verified: text.includes('Audit') && (text.includes('Valid') || text.includes('Verified') || text.includes('SHA-256') || text.includes('Chain intact')),
      snippet: text.split('\n').filter(l => l.includes('Audit') || l.includes('Chain') || l.includes('SHA-256')).slice(0, 3)
    };
  });
  console.log('Audit Verification Result:', auditVerificationStatus);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '17_audit_trail_result.png') });

  // Verify PDF Download
  console.log('\nTesting PDF Report Download...');
  const pdfLink = await page.evaluate(() => {
    const a = Array.from(document.querySelectorAll('a')).find(el => el.textContent && el.textContent.includes('Download Official PDF'));
    return a ? a.href : null;
  });
  console.log('Official PDF Report link:', pdfLink);

  let pdfOk = false;
  if (pdfLink) {
    const pdfResponse = await page.evaluate(async (url) => {
      const res = await fetch(url);
      const ct = res.headers.get('content-type');
      return { status: res.status, contentType: ct, ok: res.ok };
    }, pdfLink);
    console.log('PDF Endpoint Response:', pdfResponse);
    pdfOk = pdfResponse.ok && pdfResponse.contentType.includes('pdf');
  }

  // Check API destinations
  const renderCalls = apiRequests.filter(r => r.url.includes('satyascan-backend.onrender.com'));
  const localhostCalls = apiRequests.filter(r => r.url.includes('localhost') || r.url.includes('127.0.0.1'));

  console.log('\n--- API Routing Verification ---');
  console.log(`Render backend calls: ${renderCalls.length}`);
  console.log(`Localhost calls: ${localhostCalls.length}`);
  console.log(`Console errors: ${consoleErrors.length}`);

  const summary = {
    screeningSuccess: done,
    dossierDetails,
    auditVerified: auditVerificationStatus.verified,
    pdfOk,
    renderCallsCount: renderCalls.length,
    localhostCallsCount: localhostCalls.length,
    consoleErrorsCount: consoleErrors.length
  };

  fs.writeFileSync(path.join(ARTIFACTS_DIR, 'upload_and_dossier_summary.json'), JSON.stringify(summary, null, 2));
  console.log('\nSaved upload_and_dossier_summary.json');

  browser.disconnect();
}

run().catch(console.error);
