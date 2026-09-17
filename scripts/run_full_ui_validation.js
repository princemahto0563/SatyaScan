// scripts/run_full_ui_validation.js
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CONV_ID = 'ec9eb643-9d7d-406a-9d38-c33537a040d6';
const SCREENSHOT_DIR = `/Users/princemahto/.gemini/antigravity-ide/brain/${CONV_ID}/screenshots`;
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const resolutions = [
  { name: 'mobile_375x812', width: 375, height: 812, isMobile: true },
  { name: 'mobile_390x844', width: 390, height: 844, isMobile: true },
  { name: 'mobile_430x932', width: 430, height: 932, isMobile: true },
  { name: 'tablet_768x1024', width: 768, height: 1024, isMobile: false },
  { name: 'laptop_1024x768', width: 1024, height: 768, isMobile: false },
  { name: 'laptop_1280x800', width: 1280, height: 800, isMobile: false },
  { name: 'desktop_1440x900', width: 1440, height: 900, isMobile: false },
];

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function run() {
  console.log('=== SatyaScan Full UI & Responsive Validation ===');
  const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
  const page = await browser.newPage();

  // Helper to set theme
  async function setTheme(theme) {
    await page.evaluate((t) => {
      localStorage.setItem('satyascan_theme', t);
      if (t === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }, theme);
    await sleep(300);
  }

  // Helper to click New Screening
  async function goToNewScreening() {
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const newScreeningBtn = btns.find(b => b.textContent && b.textContent.includes('New Screening'));
      if (newScreeningBtn) newScreeningBtn.click();
    });
    await sleep(1000);
  }

  // 1. Dashboard Responsive Screenshots (Dark & Light)
  console.log('\n--- 1. Testing Dashboard Responsive Layouts ---');
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
  await sleep(1000);

  // Dark Mode
  await setTheme('dark');
  for (const res of resolutions) {
    await page.setViewport({ width: res.width, height: res.height, isMobile: res.isMobile });
    await sleep(250);
    const dest = path.join(SCREENSHOT_DIR, `dashboard_${res.name}_dark.png`);
    await page.screenshot({ path: dest, fullPage: false });
    console.log(`Saved: dashboard_${res.name}_dark.png (${fs.statSync(dest).size} bytes)`);
  }

  // Light Mode
  await setTheme('light');
  for (const res of resolutions) {
    await page.setViewport({ width: res.width, height: res.height, isMobile: res.isMobile });
    await sleep(250);
    const dest = path.join(SCREENSHOT_DIR, `dashboard_${res.name}_light.png`);
    await page.screenshot({ path: dest, fullPage: false });
    console.log(`Saved: dashboard_${res.name}_light.png (${fs.statSync(dest).size} bytes)`);
  }

  // 2. Screening CASE 01 (Genuine Passport)
  console.log('\n--- 2. Testing CASE 01 (Genuine Passport) Screening ---');
  await page.setViewport({ width: 1280, height: 850 });
  await setTheme('dark');
  await goToNewScreening();

  console.log('Clicking CASE 01 preset button...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const caseBtn = btns.find(b => b.textContent && b.textContent.includes('CASE 01'));
    if (caseBtn) caseBtn.click();
  });

  console.log('Waiting for CASE 01 screening completion & Result Dossier...');
  await page.waitForFunction(
    () => document.body.innerText.includes('Executive Screening Report') || document.body.innerText.includes('Document Information'),
    { timeout: 40000 }
  );
  await sleep(2000);

  const case01DarkDest = path.join(SCREENSHOT_DIR, 'case01_executive_report_dark.png');
  await page.screenshot({ path: case01DarkDest, fullPage: true });
  console.log(`Saved: case01_executive_report_dark.png (${fs.statSync(case01DarkDest).size} bytes)`);

  // Test Forensic Heatmap toggle
  console.log('Toggling Forensic Heatmap view...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(btn => btn.textContent && (btn.textContent.includes('Forensic Heatmap') || btn.textContent.includes('Original Document')));
    if (b) b.click();
  });
  await sleep(1000);
  const heatmapDest = path.join(SCREENSHOT_DIR, 'case01_forensic_heatmap.png');
  await page.screenshot({ path: heatmapDest });
  console.log(`Saved: case01_forensic_heatmap.png (${fs.statSync(heatmapDest).size} bytes)`);

  // Test Audit Trail Verification button
  console.log('Clicking "Verify Audit Trail" button...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const b = btns.find(btn => btn.textContent && (btn.textContent.includes('Verify Audit Trail') || btn.textContent.includes('Verify Chain') || btn.textContent.includes('Cryptographic Check')));
    if (b) b.click();
  });
  await sleep(2500);
  const auditDest = path.join(SCREENSHOT_DIR, 'case01_audit_verified.png');
  await page.screenshot({ path: auditDest });
  console.log(`Saved: case01_audit_verified.png (${fs.statSync(auditDest).size} bytes)`);

  // Light Mode version of Executive Report
  console.log('Capturing Case 01 Executive Report in Light Mode...');
  await setTheme('light');
  await sleep(500);
  const case01LightDest = path.join(SCREENSHOT_DIR, 'case01_executive_report_light.png');
  await page.screenshot({ path: case01LightDest, fullPage: true });
  console.log(`Saved: case01_executive_report_light.png (${fs.statSync(case01LightDest).size} bytes)`);

  // Mobile version of Executive Report
  console.log('Capturing Case 01 Executive Report on Mobile (375x812)...');
  await page.setViewport({ width: 375, height: 812, isMobile: true });
  await sleep(500);
  const case01MobileDest = path.join(SCREENSHOT_DIR, 'case01_executive_report_mobile_375.png');
  await page.screenshot({ path: case01MobileDest, fullPage: true });
  console.log(`Saved: case01_executive_report_mobile_375.png (${fs.statSync(case01MobileDest).size} bytes)`);

  // 3. Screening CASE 03 (DOB Alteration)
  console.log('\n--- 3. Testing CASE 03 (DOB Alteration) Screening ---');
  await page.setViewport({ width: 1280, height: 850 });
  await setTheme('dark');
  await goToNewScreening();

  console.log('Clicking CASE 03 preset button...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const caseBtn = btns.find(b => b.textContent && b.textContent.includes('CASE 03'));
    if (caseBtn) caseBtn.click();
  });

  console.log('Waiting for CASE 03 screening completion & Result Dossier...');
  await page.waitForFunction(
    () => document.body.innerText.includes('Executive Screening Report') || document.body.innerText.includes('Document Information'),
    { timeout: 40000 }
  );
  await sleep(2000);

  const case03Dest = path.join(SCREENSHOT_DIR, 'case03_dob_altered_report.png');
  await page.screenshot({ path: case03Dest, fullPage: true });
  console.log(`Saved: case03_dob_altered_report.png (${fs.statSync(case03Dest).size} bytes)`);

  // 4. Screening CASE 08 (Appearance Variation)
  console.log('\n--- 4. Testing CASE 08 (Appearance Variation) Screening ---');
  await goToNewScreening();

  console.log('Clicking CASE 08 preset button...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const caseBtn = btns.find(b => b.textContent && b.textContent.includes('CASE 08'));
    if (caseBtn) caseBtn.click();
  });

  console.log('Waiting for CASE 08 screening completion & Result Dossier...');
  await page.waitForFunction(
    () => document.body.innerText.includes('Executive Screening Report') || document.body.innerText.includes('Document Information'),
    { timeout: 40000 }
  );
  await sleep(2000);

  const case08Dest = path.join(SCREENSHOT_DIR, 'case08_appearance_variation_report.png');
  await page.screenshot({ path: case08Dest, fullPage: true });
  console.log(`Saved: case08_appearance_variation_report.png (${fs.statSync(case08Dest).size} bytes)`);

  await page.close();
  browser.disconnect();
  console.log('\n=== All UI Validations & Captures Completed Successfully! ===');
}

run().catch(err => {
  console.error('Fatal error in UI validation:', err);
  process.exit(1);
});
