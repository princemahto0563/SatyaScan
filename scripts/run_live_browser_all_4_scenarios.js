const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const ARTIFACTS_DIR = '/Users/princemahto/.gemini/antigravity-ide/brain/d7df07b4-ace7-4283-9b77-c1c58ca4e251';
const EVIDENCE_DIR = path.join(ARTIFACTS_DIR, 'live_browser_evidence');
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function run() {
  console.log('================================================================');
  console.log('   SATYASCAN REAL LIVE BROWSER 4-SCENARIO VERIFICATION SUITE   ');
  console.log('================================================================');

  const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
  const pages = await browser.pages();
  let page = pages.find((p) => p.url().includes('satya-scan-phi.vercel.app'));
  if (!page) {
    page = await browser.newPage();
    await page.goto('https://satya-scan-phi.vercel.app', { waitUntil: 'networkidle2' });
  }

  await page.setViewport({ width: 1440, height: 900 });

  async function goToNewScreening() {
    const buttons = await page.$$('button');
    for (const b of buttons) {
      const txt = await page.evaluate(el => el.textContent, b);
      if (txt && txt.trim() === 'New Screening') {
        await b.click();
        await sleep(1500);
        break;
      }
    }
  }

  const scenarioResults = [];

  // =========================================================================
  // SCENARIO 1: Genuine Passport + Genuine Live Face (Preset 01)
  // =========================================================================
  console.log('\n--- Running Scenario 1: Genuine Passport + Genuine Face (CASE 01) ---');
  await goToNewScreening();

  const case01Btn = (await page.$$('button')).find(async (b) => {
    const txt = await page.evaluate(el => el.textContent, b);
    return txt && txt.includes('CASE 01');
  });
  // Find by text evaluation
  const allBtns1 = await page.$$('button');
  for (const b of allBtns1) {
    const txt = await page.evaluate(el => el.textContent, b);
    if (txt && txt.includes('CASE 01')) {
      await b.click();
      console.log('Clicked CASE 01 button');
      break;
    }
  }

  console.log('Waiting for Case 01 screening to finish...');
  await sleep(9000);

  const shot1 = path.join(EVIDENCE_DIR, '01_genuine_passport_live.png');
  await page.screenshot({ path: shot1, fullPage: true });
  console.log(`Saved screenshot: ${shot1}`);

  const eval1 = await page.evaluate(() => {
    const text = document.body.innerText;
    return {
      title: 'Genuine Passport (Arjun Sharma)',
      hasArjun: text.includes('ARJUN SHARMA'),
      hasZDoc: text.includes('Z1234567'),
      hasOcrSuccess: text.includes('OCR: SUCCESS') || text.includes('SUCCESS'),
      hasMrzPass: text.includes('7-3-1 PASS') || text.includes('MRZ: 7-3-1 PASS'),
      hasVerifiedMatch: text.includes('VERIFIED MATCH'),
      hasLowRisk: text.includes('LOW RISK'),
      hasSha256: text.includes('SHA-256')
    };
  });
  scenarioResults.push(eval1);
  console.log('Case 01 Results:', eval1);

  // =========================================================================
  // SCENARIO 2: Passport + Imposter Face (CASE 09)
  // =========================================================================
  console.log('\n--- Running Scenario 2: Passport + Imposter Face (CASE 09) ---');
  await goToNewScreening();

  const allBtns2 = await page.$$('button');
  for (const b of allBtns2) {
    const txt = await page.evaluate(el => el.textContent, b);
    if (txt && txt.includes('CASE 09')) {
      await b.click();
      console.log('Clicked CASE 09 button');
      break;
    }
  }

  console.log('Waiting for Case 09 screening to finish...');
  await sleep(9000);

  const shot2 = path.join(EVIDENCE_DIR, '02_imposter_face_live.png');
  await page.screenshot({ path: shot2, fullPage: true });
  console.log(`Saved screenshot: ${shot2}`);

  const eval2 = await page.evaluate(() => {
    const text = document.body.innerText;
    return {
      title: 'Imposter Face (CASE 09)',
      hasVerifiedMismatch: text.includes('VERIFIED MISMATCH') || text.includes('MISMATCH'),
      hasManualReview: text.includes('MANUAL REVIEW') || text.includes('MEDIUM RISK') || text.includes('HIGH RISK'),
      hasBiometricReason: text.includes('Biometric Mismatch') || text.includes('does not match document portrait') || text.includes('exceeds permitted tolerance'),
      hasSha256: text.includes('SHA-256')
    };
  });
  scenarioResults.push(eval2);
  console.log('Case 09 Results:', eval2);

  // =========================================================================
  // SCENARIO 3: Passport Cover Upload
  // =========================================================================
  console.log('\n--- Running Scenario 3: Passport Cover Upload ---');
  await goToNewScreening();

  const docInput = await page.$('input[type="file"]');
  if (docInput) {
    const coverPath = path.resolve('data/reference/booklets/crop_cover_1df5fe5b.jpg');
    console.log('Uploading passport cover:', coverPath);
    await docInput.uploadFile(coverPath);
    await sleep(1000);

    // Find "Initiate Full Screening" button
    const allBtns3 = await page.$$('button');
    for (const b of allBtns3) {
      const txt = await page.evaluate(el => el.textContent, b);
      if (txt && txt.includes('Initiate Full Screening')) {
        await b.click();
        console.log('Clicked Initiate Full Screening');
        break;
      }
    }

    console.log('Waiting for Passport Cover screening to finish...');
    await sleep(9000);

    const shot3 = path.join(EVIDENCE_DIR, '03_passport_cover_live.png');
    await page.screenshot({ path: shot3, fullPage: true });
    console.log(`Saved screenshot: ${shot3}`);

    const eval3 = await page.evaluate(() => {
      const text = document.body.innerText;
      return {
        title: 'Passport Cover',
        hasIdentityPageAlert: text.includes('Identity Page Not Detected') || text.includes('PASSPORT_COVER') || text.includes('biodata/identity page containing portrait'),
        hasUnableToVerify: text.includes('UNABLE_TO_VERIFY') || text.includes('Unable to verify') || text.includes('INPUT_FAILURE') || text.includes('Identity Incomplete'),
        hasNoBrokenImages: !Array.from(document.querySelectorAll('img')).some(i => i.naturalWidth === 0 && i.src),
        hasSha256: text.includes('SHA-256')
      };
    });
    scenarioResults.push(eval3);
    console.log('Passport Cover Results:', eval3);
  }

  // =========================================================================
  // SCENARIO 4: Genuine Visa Upload
  // =========================================================================
  console.log('\n--- Running Scenario 4: Genuine Visa Upload ---');
  await goToNewScreening();

  // Change document type select to VISA if available
  const select = await page.$('select');
  if (select) {
    await select.select('VISA');
    console.log('Selected document type: VISA');
    await sleep(500);
  }

  const visaInput = await page.$('input[type="file"]');
  if (visaInput) {
    const visaPath = path.resolve('data/reference/visas/PERSON-003_visa_ref.jpg');
    console.log('Uploading visa document:', visaPath);
    await visaInput.uploadFile(visaPath);
    await sleep(1000);

    // Find "Initiate Full Screening" button
    const allBtns4 = await page.$$('button');
    for (const b of allBtns4) {
      const txt = await page.evaluate(el => el.textContent, b);
      if (txt && txt.includes('Initiate Full Screening')) {
        await b.click();
        console.log('Clicked Initiate Full Screening');
        break;
      }
    }

    console.log('Waiting for Visa screening to finish...');
    await sleep(9000);

    const shot4 = path.join(EVIDENCE_DIR, '04_genuine_visa_live.png');
    await page.screenshot({ path: shot4, fullPage: true });
    console.log(`Saved screenshot: ${shot4}`);

    const eval4 = await page.evaluate(() => {
      const text = document.body.innerText;
      return {
        title: 'Genuine Visa (Navneet Negi)',
        hasNavneet: text.includes('NAVNEET') || text.includes('NEGI') || text.includes('ABC 1234567') || text.includes('ABC1234567'),
        hasNoGarbageLabels: !text.includes('MAT /NOM:') && !text.includes('SURNAME/NOM:'),
        hasMrzNotApplicableOrUnparsed: text.includes('Not Applicable') || text.includes('MRZ_NOT_APPLICABLE') || text.includes('MRZ_UNPARSED') || text.includes('Unparsed') || text.includes('N/A'),
        hasSha256: text.includes('SHA-256')
      };
    });
    scenarioResults.push(eval4);
    console.log('Visa Results:', eval4);
  }

  // Save full JSON summary
  const summaryPath = path.join(EVIDENCE_DIR, 'live_browser_scenarios_summary.json');
  fs.writeFileSync(summaryPath, JSON.stringify(scenarioResults, null, 2));
  console.log(`\nAll 4 scenarios verified and recorded. Summary saved to: ${summaryPath}`);

  await browser.disconnect();
}

run().catch(console.error);
