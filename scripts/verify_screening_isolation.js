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
  console.log('   SATYASCAN PHASE 16 — SCREENING ISOLATION VERIFICATION       ');
  console.log('================================================================');

  const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
  const pages = await browser.pages();
  let page = pages.find((p) => p.url().includes('satya-scan-phi.vercel.app'));
  if (!page) {
    page = await browser.newPage();
    await page.goto('https://satya-scan-phi.vercel.app', { waitUntil: 'networkidle2' });
  }

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

  // 1. Run Screening A (Preset 01 - Arjun Sharma)
  console.log('\n[1] Running Screening A (Preset 01: Arjun Sharma)...');
  await goToNewScreening();
  const allBtns1 = await page.$$('button');
  for (const b of allBtns1) {
    const txt = await page.evaluate(el => el.textContent, b);
    if (txt && txt.includes('CASE 01')) {
      await b.click();
      break;
    }
  }
  await sleep(8000);

  const dataA = await page.evaluate(() => {
    const text = document.body.innerText;
    const refMatch = text.match(/SAT-2026-[A-Z0-9]+/);
    const images = Array.from(document.querySelectorAll('img')).map(i => i.src);
    return {
      ref: refMatch ? refMatch[0] : null,
      name: text.includes('ARJUN SHARMA') ? 'ARJUN SHARMA' : 'UNKNOWN',
      docNum: text.includes('Z1234567') ? 'Z1234567' : 'UNKNOWN',
      risk: text.includes('LOW RISK') ? 'LOW RISK' : 'OTHER',
      images
    };
  });
  console.log('Screening A:', dataA);

  // 2. Run Screening B (Preset 02 - Expired Document)
  console.log('\n[2] Running Screening B (Preset 02: Expired Document)...');
  await goToNewScreening();
  const allBtns2 = await page.$$('button');
  for (const b of allBtns2) {
    const txt = await page.evaluate(el => el.textContent, b);
    if (txt && txt.includes('CASE 02')) {
      await b.click();
      break;
    }
  }
  await sleep(8000);

  const dataB = await page.evaluate(() => {
    const text = document.body.innerText;
    const refMatch = text.match(/SAT-2026-[A-Z0-9]+/);
    const images = Array.from(document.querySelectorAll('img')).map(i => i.src);
    return {
      ref: refMatch ? refMatch[0] : null,
      name: text.includes('RAVI PATEL') ? 'RAVI PATEL' : (text.includes('ARJUN SHARMA') ? 'ARJUN SHARMA' : 'OTHER'),
      docNum: text.includes('R1234567') ? 'R1234567' : (text.includes('Z1234567') ? 'Z1234567' : 'OTHER'),
      isExpired: text.includes('EXPIRED') || text.includes('Expired') || text.includes('PASSPORT_EXPIRED'),
      images
    };
  });
  console.log('Screening B:', dataB);

  // 3. Assertions for Strict Isolation
  console.log('\n[3] Evaluating Strict Isolation...');
  const differentRefs = dataA.ref !== dataB.ref;
  const differentNames = dataA.name !== dataB.name && dataB.name !== 'ARJUN SHARMA';
  const differentDocNums = dataA.docNum !== dataB.docNum && dataB.docNum !== 'Z1234567';
  
  // Check image URL isolation (screening IDs in media URLs must match current screening)
  const aImagesHaveBRef = dataA.images.some(u => dataB.ref && u.includes(dataB.ref));
  const bImagesHaveARef = dataB.images.some(u => dataA.ref && u.includes(dataA.ref));

  console.log(' - Different Screening IDs :', differentRefs, `(${dataA.ref} vs ${dataB.ref})`);
  console.log(' - Different Identity Names:', differentNames, `(${dataA.name} vs ${dataB.name})`);
  console.log(' - Different Document Nums :', differentDocNums, `(${dataA.docNum} vs ${dataB.docNum})`);
  console.log(' - Zero Media Cross-Talk   :', !aImagesHaveBRef && !bImagesHaveARef);

  const isolationResult = {
    screeningA: dataA,
    screeningB: dataB,
    passed: differentRefs && differentNames && differentDocNums && !aImagesHaveBRef && !bImagesHaveARef
  };

  fs.writeFileSync(
    path.join(EVIDENCE_DIR, 'screening_isolation_results.json'),
    JSON.stringify(isolationResult, null, 2)
  );

  console.log('\nISOLATION TEST PASSED: ', isolationResult.passed);
  await browser.disconnect();
}

run().catch(console.error);
