import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { open } from 'node:fs/promises';
import { join } from 'node:path';

export async function printPdf(browser, url, output, temporary) {
  const child = spawn(browser, [
    '--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-extensions', '--disable-sync',
    '--allow-file-access-from-files', '--remote-debugging-address=127.0.0.1',
    '--remote-debugging-port=0', `--user-data-dir=${join(temporary, 'profile')}`, 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  const exited = once(child, 'close');
  const pending = new Map();
  let socket;
  let sequence = 0;
  let log = '';
  let timedOut = false;
  const fail = error => {
    for (const promise of pending.values()) promise.reject(error);
    pending.clear();
  };
  const timer = setTimeout(() => {
    timedOut = true;
    fail(new Error('PDF export timed out after 60 seconds.'));
    child.kill('SIGKILL');
  }, 60000);
  try {
    const endpoint = await new Promise((resolve, reject) => {
      child.on('error', reject);
      child.once('close', () => reject(new Error(`Browser exited before becoming ready. ${log}`)));
      child.stderr.on('data', chunk => {
        log = (log + chunk.toString()).slice(-12000);
        const match = log.match(/DevTools listening on (ws:\/\/[^\s]+)/);
        if (match) resolve(match[1]);
      });
    });
    socket = new WebSocket(endpoint);
    await new Promise((resolve, reject) => {
      socket.addEventListener('open', resolve, { once: true });
      socket.addEventListener('error', () => reject(new Error('Could not connect to local Chromium.')), { once: true });
      child.once('close', () => reject(new Error('Browser exited while connecting.')));
    });
    socket.addEventListener('message', event => {
      const message = JSON.parse(event.data);
      const promise = pending.get(message.id);
      if (!promise) return;
      pending.delete(message.id);
      if (message.error) promise.reject(new Error(message.error.message));
      else promise.resolve(message.result);
    });
    socket.addEventListener('close', () => fail(new Error('Chromium connection closed.')));
    child.once('close', () => fail(new Error(`Browser exited during PDF export. ${log}`)));
    const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
      if (timedOut || socket.readyState !== WebSocket.OPEN) return reject(new Error('Chromium is unavailable.'));
      const id = ++sequence;
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params, sessionId }));
    });
    const { targetId } = await command('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await command('Target.attachToTarget', { targetId, flatten: true });
    await command('Page.enable', {}, sessionId);
    const navigation = await command('Page.navigate', { url }, sessionId);
    if (navigation.errorText) throw new Error(navigation.errorText);
    const ready = await command('Runtime.evaluate', {
      expression: `(async () => {
        if (document.readyState !== 'complete') await new Promise(resolve => addEventListener('load', resolve, {once: true}));
        await document.fonts.ready;
        if ([...document.images].some(image => !image.complete || !image.naturalWidth)) throw new Error('A deck image failed to load.');
        return document.querySelectorAll('.pdf-page').length;
      })()`, awaitPromise: true, returnByValue: true,
    }, sessionId);
    if (ready.exceptionDetails || !ready.result.value) throw new Error('The print document did not load completely.');
    const { stream } = await command('Page.printToPDF', {
      printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false,
      marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0,
      transferMode: 'ReturnAsStream',
    }, sessionId);
    const file = await open(output, 'wx');
    try {
      let eof = false;
      while (!eof) {
        const chunk = await command('IO.read', { handle: stream, size: 65536 }, sessionId);
        await file.writeFile(chunk.base64Encoded ? Buffer.from(chunk.data, 'base64') : chunk.data);
        eof = chunk.eof;
      }
    } finally { await file.close(); }
    await command('IO.close', { handle: stream }, sessionId);
  } finally {
    clearTimeout(timer);
    socket?.close();
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
    const force = setTimeout(() => child.kill('SIGKILL'), 3000);
    try { await exited; } finally { clearTimeout(force); }
  }
}
