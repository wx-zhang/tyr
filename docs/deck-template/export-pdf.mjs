import { constants } from 'node:fs';
import { access, copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, delimiter, dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { slides } from './deck.mjs';
import { printPdf } from './chromium-pdf.mjs';

const deck = dirname(fileURLToPath(import.meta.url));
const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

async function findBrowser(explicit) {
  const candidates = explicit ? [explicit] : [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
    ...['PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'].flatMap(key => process.env[key] ? [join(process.env[key], 'Google', 'Chrome', 'Application', 'chrome.exe')] : []),
    ...(process.env.PATH || '').split(delimiter).flatMap(dir => ['google-chrome', 'chromium', 'chromium-browser', 'brave-browser'].map(name => join(dir, name))),
  ];
  for (const candidate of candidates.filter(Boolean)) {
    try { await access(candidate, constants.X_OK); return candidate; } catch {}
  }
  throw new Error('Chrome/Chromium not found. Set CHROME_PATH or pass --browser /absolute/path/to/browser.');
}

async function main() {
  const { values } = parseArgs({ options: {
    output: { type: 'string' }, theme: { type: 'string', default: 'dark' },
    browser: { type: 'string' }, help: { type: 'boolean', short: 'h' },
  } });
  if (values.help) {
    console.log('Usage: node export-pdf.mjs [--output name.pdf] [--theme dark|light] [--browser /path/to/chrome]\nOutput: .gamr/<name.pdf> under the current working directory. Existing PDFs are never overwritten.');
    return;
  }
  if (!['dark', 'light'].includes(values.theme)) throw new Error('--theme must be dark or light.');
  const name = values.output || `${basename(deck)}.pdf`;
  if (name !== basename(name) || /[\\/]/.test(name) || !name.endsWith('.pdf')) throw new Error('--output must be a filename ending in .pdf, without directory components.');
  const output = resolve('.gamr', name);
  try {
    await access(output);
    throw new Error(`Output already exists: ${output}. Choose another --output filename.`);
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (!slides.length) throw new Error('The slide manifest is empty.');
  for (const [file] of slides) {
    if (!/^[a-zA-Z0-9_-]+\.html$/.test(file)) throw new Error(`Invalid slide filename: ${file}`);
  }
  const browser = await findBrowser(values.browser);
  const shell = await readFile(join(deck, 'index.html'), 'utf8');
  const stage = shell.match(/<div id="stage">([\s\S]*?)<\/main>/)?.[0].replace(/<\/main>$/, '');
  if (!stage || !stage.includes('<div id="slide-content" aria-live="polite"></div>')) throw new Error('Expected deck stage and empty slide-content container in index.html.');
  const pages = await Promise.all(slides.map(async ([file, , label], index) => {
    const fragment = (await readFile(join(deck, 'slides', file), 'utf8')).replace(/<template\b[^>]*>[\s\S]*?<\/template>/gi, '');
    return `<article class="pdf-page">${stage
      .replace('<div id="slide-content" aria-live="polite"></div>', () => `<div id="slide-content">${fragment}</div>`)
      .replace(/<span id="section-label">[\s\S]*?<\/span>/, () => `<span id="section-label">${escape(label)}</span>`)
      .replace(/<span id="slide-count">[\s\S]*?<\/span>/, `<span id="slide-count">${String(index + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}</span>`)
      .replace(/<div id="progress"[^>]*><\/div>/, '')}</article>`;
  }));
  const html = `<!doctype html><html data-theme="${values.theme}"><head><meta charset="utf-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src file: 'unsafe-inline'; img-src file: data:; font-src file:; base-uri file:">
    <base href="${escape(pathToFileURL(`${deck}/`).href)}"><title>${escape(basename(deck))}</title>
    <link rel="stylesheet" href="styles.css"><style>
    @page{size:1600px 900px;margin:0}
    html,body{margin:0;padding:0;width:1600px;background:var(--bg);overflow:visible}
    *{animation:none!important;transition:none!important;print-color-adjust:exact!important;-webkit-print-color-adjust:exact!important}
    .pdf-page{width:1600px;height:900px;break-after:page;break-inside:avoid;overflow:hidden}
    .pdf-page:last-child{break-after:auto}
    #stage{transform:none!important;box-shadow:none!important}
    </style></head><body>${pages.join('\n')}</body></html>`;
  const temporary = await mkdtemp(join(tmpdir(), 'gamr-deck-pdf-'));
  try {
    const input = join(temporary, 'deck.html');
    const pdf = join(temporary, 'deck.pdf');
    await writeFile(input, html);
    await printPdf(browser, pathToFileURL(input).href, pdf, temporary);
    await mkdir(dirname(output), { recursive: true });
    await copyFile(pdf, output, constants.COPYFILE_EXCL);
    console.log(`Exported ${slides.length} slides (${values.theme}): ${output}`);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(`PDF export failed: ${error.message}`); process.exitCode = 1; });
