// scripts/run_production_verification.js
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CONV_ID = '973b0911-900c-45aa-b614-8fd248f6907f';
const ARTIFACTS_DIR = `/Users/princemahto/.gemini/antigravity-ide/brain/${CONV_ID}`;
const SCREENSHOT_DIR = path.join(ARTIFACTS_DIR, 'screenshots');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function run() {
  console.log('=== Starting Real Production Verification on Chrome ===');
  const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
  const pages = await browser.pages();
  
  // Find or create the Vercel production page
  let page = pages.find((p) => p.url().includes('satya-scan-phi.vercel.app'));
  if (!page) {
    page = await browser.newPage();
  }

  const consoleLogs = [];
  const networkLogs = [];
  const networkErrors = [];
  const corsErrors = [];
  const apiRequests = [];

  page.on('console', (msg) => {
    const text = msg.text();
    const type = msg.type();
    consoleLogs.push({ type, text });
    if (type === 'error') {
      console.log(`[Browser Console Error]: ${text}`);
      if (text.toLowerCase().includes('cors') || text.toLowerCase().includes('access-control-allow-origin')) {
        corsErrors.push(text);
      }
    }
  });

  page.on('pageerror', (err) => {
    console.log(`[Browser Page Error]: ${err.message}`);
    consoleLogs.push({ type: 'pageerror', text: err.message });
  });

  page.on('request', (req) => {
    const url = req.url();
    const method = req.method();
    if (url.includes('/api/v1')) {
      apiRequests.push({ method, url, postData: req.postData() });
      console.log(`[API Request]: ${method} ${url}`);
    }
  });

  page.on('requestfailed', (req) => {
    const failure = req.failure();
    const url = req.url();
    console.log(`[Request Failed]: ${req.method()} ${url} - ${failure?.errorText}`);
    networkErrors.push({ url, error: failure?.errorText });
    if (failure?.errorText?.includes('CORS') || failure?.errorText?.includes('blocked')) {
      corsErrors.push(`CORS Block on ${url}: ${failure.errorText}`);
    }
  });

  page.on('response', (res) => {
    const url = res.url();
    const status = res.status();
    networkLogs.push({ url, status, ok: res.ok() });
    if (url.includes('/api/v1')) {
      console.log(`[API Response]: ${status} ${url}`);
    }
    if (status >= 400 && url.includes('/api/v1')) {
      networkErrors.push({ url, status });
    }
  });

  console.log('\n--- 1. Navigating to https://satya-scan-phi.vercel.app ---');
  await page.goto('https://satya-scan-phi.vercel.app', { waitUntil: 'networkidle2' });
  await sleep(1500);

  const initialShot = path.join(SCREENSHOT_DIR, '01_login_page.png');
  await page.screenshot({ path: initialShot, fullPage: true });
  console.log(`Saved screenshot: 01_login_page.png`);

  // Check if checkpoint login is displayed
  const pageText = await page.evaluate(() => document.body.innerText);
  console.log('Page header / title preview:', pageText.slice(0, 150).replace(/\n/g, ' '));

  console.log('\n--- 2. Performing Checkpoint Authentication ---');
  // Check if we need to log in
  const isLoginForm = await page.evaluate(() => {
    return !!document.querySelector('form') || document.body.innerText.includes('Checkpoint Authentication') || document.body.innerText.includes('Authenticate Workstation');
  });
  console.log('Is login form present?', isLoginForm);

  if (isLoginForm) {
    // Fill credentials and submit
    await page.evaluate(() => {
      // Find submit button
      const buttons = Array.from(document.querySelectorAll('button'));
      const authBtn = buttons.find(b => b.textContent && (b.textContent.includes('Authenticate') || b.textContent.includes('Sign In') || b.textContent.includes('Login')));
      if (authBtn) {
        console.log('Clicking auth button:', authBtn.textContent);
        authBtn.click();
      }
    });

    console.log('Waiting for login to complete and dashboard to load...');
    await sleep(3000);
  }

  const afterLoginShot = path.join(SCREENSHOT_DIR, '02_dashboard.png');
  await page.screenshot({ path: afterLoginShot, fullPage: true });
  console.log(`Saved screenshot: 02_dashboard.png`);

  const dashboardText = await page.evaluate(() => document.body.innerText);
  const isAuthenticated = dashboardText.includes('Checkpoint') || dashboardText.includes('DELHI AIRPORT') || dashboardText.includes('Delhi Airport') || dashboardText.includes('Screening');
  console.log('Is Authenticated / Dashboard displayed?', isAuthenticated);

  console.log('\n--- 3. Navigating to New Screening ---');
  await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button, a'));
    const newScreeningBtn = buttons.find(b => b.textContent && b.textContent.includes('New Screening'));
    if (newScreeningBtn) {
      newScreeningBtn.click();
    }
  });
  await sleep(1500);

  const newScreeningShot = path.join(SCREENSHOT_DIR, '03_new_screening_view.png');
  await page.screenshot({ path: newScreeningShot, fullPage: true });
  console.log(`Saved screenshot: 03_new_screening_view.png`);

  console.log('\n--- 4. Executing Screening Flow (CASE 01: Genuine Passport) ---');
  const clickedPreset = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const case1Btn = buttons.find(b => b.textContent && (b.textContent.includes('CASE 01') || b.textContent.includes('Case 01') || b.textContent.includes('Genuine Passport')));
    if (case1Btn) {
      case1Btn.click();
      return true;
    }
    return false;
  });
  console.log('Clicked CASE 01 preset button:', clickedPreset);

  console.log('Waiting for screening pipeline processing...');
  // Wait up to 45 seconds for the result dossier
  let completed = false;
  for (let i = 0; i < 45; i++) {
    await sleep(1000);
    const bodyText = await page.evaluate(() => document.body.innerText);
    if (
      bodyText.includes('Executive Screening Report') ||
      bodyText.includes('Screening Dossier') ||
      bodyText.includes('PASSPORT') ||
      bodyText.includes('Document Information') ||
      bodyText.includes('Integrity Assessment')
    ) {
      completed = true;
      console.log(`Screening completed in ~${i + 1} seconds!`);
      break;
    }
  }

  await sleep(2000);
  const resultShot = path.join(SCREENSHOT_DIR, '04_screening_result.png');
  await page.screenshot({ path: resultShot, fullPage: true });
  console.log(`Saved screenshot: 04_screening_result.png`);

  console.log('\n--- Verification Analysis ---');
  console.log('Total API Requests recorded:', apiRequests.length);
  apiRequests.forEach((req, idx) => {
    console.log(`  [${idx + 1}] ${req.method} ${req.url}`);
  });

  const localhostApiRequests = apiRequests.filter(r => r.url.includes('localhost') || r.url.includes('127.0.0.1'));
  const renderApiRequests = apiRequests.filter(r => r.url.includes('satyascan-backend.onrender.com'));

  console.log(`Requests to Render Backend: ${renderApiRequests.length}`);
  console.log(`Requests to Localhost: ${localhostApiRequests.length}`);
  console.log(`CORS Errors recorded: ${corsErrors.length}`);
  console.log(`Network Errors: ${networkErrors.length}`);

  const hydrationErrors = consoleLogs.filter(l => l.text.toLowerCase().includes('hydration') || l.text.toLowerCase().includes('react-dom'));
  console.log(`Hydration Errors recorded: ${hydrationErrors.length}`);

  // Disconnect puppeteer cleanly
  browser.disconnect();

  const report = {
    completed,
    isAuthenticated,
    apiRequestsCount: apiRequests.length,
    renderApiRequestsCount: renderApiRequests.length,
    localhostApiRequestsCount: localhostApiRequests.length,
    corsErrors,
    networkErrors,
    hydrationErrorsCount: hydrationErrors.length,
    consoleErrorsCount: consoleLogs.filter(l => l.type === 'error').length
  };

  fs.writeFileSync(path.join(ARTIFACTS_DIR, 'verification_report.json'), JSON.stringify(report, null, 2));
  console.log('\nSaved verification_report.json');
}

run().catch((err) => {
  console.error('Test execution error:', err);
  process.exit(1);
});
