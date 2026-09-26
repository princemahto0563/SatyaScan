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
  const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
  const pages = await browser.pages();
  let page = pages.find((p) => p.url().includes('satya-scan-phi.vercel.app'));
  if (!page) {
    page = await browser.newPage();
    await page.goto('https://satya-scan-phi.vercel.app', { waitUntil: 'networkidle2' });
  }

  // 1. Click "New Screening" sidebar button
  console.log('Navigating to New Screening...');
  const buttons = await page.$$('button');
  for (const b of buttons) {
    const txt = await page.evaluate(el => el.textContent, b);
    if (txt && txt.trim() === 'New Screening') {
      await b.click();
      console.log('Clicked New Screening button');
      break;
    }
  }
  await sleep(1500);

  // Print all buttons on New Screening page
  const allBtns = await page.$$('button');
  console.log('\nButtons available on New Screening:');
  for (const b of allBtns) {
    const txt = await page.evaluate(el => el.textContent, b);
    console.log(' - Button:', txt.trim().replace(/\n+/g, ' '));
  }

  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'new_screening_view.png'), fullPage: true });
  await browser.disconnect();
}

run().catch(console.error);
