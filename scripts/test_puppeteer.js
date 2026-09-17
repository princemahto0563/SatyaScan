const puppeteer = require('puppeteer-core');

async function test() {
  console.log('Connecting to Chrome on port 9222...');
  const browser = await puppeteer.connect({
    browserURL: 'http://localhost:9222'
  });
  console.log('Connected! Creating page...');
  const page = await browser.newPage();
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded', timeout: 15000 });
  console.log('Loaded http://localhost:3000, title:', await page.title());
  await page.screenshot({ path: '/tmp/puppeteer_test.png' });
  console.log('Screenshot captured successfully to /tmp/puppeteer_test.png');
  await page.close();
  browser.disconnect();
}

test().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
