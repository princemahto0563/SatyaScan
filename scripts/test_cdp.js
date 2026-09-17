// scripts/test_cdp.js
const fs = require('fs');

async function main() {
  const tabsRes = await fetch('http://localhost:9222/json/list');
  const tabs = await tabsRes.json();
  const pageTab = tabs.find(t => t.type === 'page' && t.url.includes('3000'));
  if (!pageTab) {
    console.error('No page tab found for localhost:3000');
    process.exit(1);
  }
  console.log('Connecting to tab:', pageTab.id, pageTab.webSocketDebuggerUrl);

  const ws = new WebSocket(pageTab.webSocketDebuggerUrl);
  let id = 1;
  const pending = new Map();

  function send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const msgId = id++;
      pending.set(msgId, { resolve, reject });
      ws.send(JSON.stringify({ id: msgId, method, params }));
    });
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.id && pending.has(data.id)) {
      const { resolve, reject } = pending.get(data.id);
      pending.delete(data.id);
      if (data.error) reject(data.error);
      else resolve(data.result);
    }
  };

  await new Promise((resolve) => { ws.onopen = resolve; });
  console.log('Connected via CDP WebSocket');

  // Evaluate title
  const evalRes = await send('Runtime.evaluate', { expression: 'document.title' });
  console.log('Document title:', evalRes.result.value);

  // Capture screenshot test
  const shotRes = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('/tmp/cdp_test.png', Buffer.from(shotRes.data, 'base64'));
  console.log('Screenshot saved to /tmp/cdp_test.png, size:', fs.statSync('/tmp/cdp_test.png').size);

  ws.close();
}

main().catch(console.error);
