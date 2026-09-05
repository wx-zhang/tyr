import { slides } from './deck.mjs';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';

const root = new URL('./', import.meta.url);
const files = new Map([
  ['/', ['index.html', 'text/html']],
  ['/index.html', ['index.html', 'text/html']],
  ['/styles.css', ['styles.css', 'text/css']],
  ['/slides.css', ['slides.css', 'text/css']],
  ['/app.js', ['app.js', 'text/javascript']],
  ['/deck.mjs', ['deck.mjs', 'text/javascript']],
  ['/assets/tyr.svg', ['assets/tyr.svg', 'image/svg+xml']],
  ['/assets/gamr.svg', ['assets/gamr.svg', 'image/svg+xml']],
  ...slides.map(([file]) => [`/slides/${file}`, [`slides/${file}`, 'text/html']]),
]);
const port = Number(process.env.PORT || 4177);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('PORT must be an integer between 1 and 65535');
const server = createServer(async (request, response) => {
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('Cache-Control', 'no-store');
  response.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.writeHead(405, { Allow: 'GET, HEAD' }).end('Method not allowed');
    return;
  }
  const path = request.url?.split('?')[0];
  const file = files.get(path);
  if (!file) {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not found');
    return;
  }
  try {
    const body = await readFile(new URL(file[0], root));
    response.writeHead(200, { 'Content-Type': `${file[1]}; charset=utf-8`, 'Content-Length': body.length });
    response.end(request.method === 'HEAD' ? undefined : body);
  } catch (error) {
    console.error(`Unable to serve ${file[0]}: ${error.message}`);
    response.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Unable to load deck asset');
  }
});
server.listen(port, '127.0.0.1', () => console.log(`Deck ready: http://127.0.0.1:${port}`));
