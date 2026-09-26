/**
 * Smoke tests against a running palworld-lens (the dev container by default): the modals open, stack
 * and close the way they should, and "Show on map" lands on the right map. They drive the page through
 * Alpine, so they need a real save loaded and auth off (dev). Skipped when nothing answers at the URL
 * or no headless Chromium is installed.
 *
 *   npm run test:e2e                      # http://localhost:5176
 *   LENS_E2E_URL=http://host:port npm run test:e2e
 *   LENS_E2E_BROWSER=/path/to/chrome      # otherwise the newest chrome-headless-shell under ~/.cache/ms-playwright
 */
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { chromium } from 'playwright-core';

const URL = (process.env.LENS_E2E_URL || 'http://localhost:5176').replace(/\/$/, '');

function findBrowser() {
    if (process.env.LENS_E2E_BROWSER) return process.env.LENS_E2E_BROWSER;
    const root = join(homedir(), '.cache', 'ms-playwright');
    if (!existsSync(root)) return null;
    const builds = readdirSync(root).filter(d => d.startsWith('chromium_headless_shell-')).sort();
    for (const b of builds.reverse()) {
        const p = join(root, b, 'chrome-headless-shell-linux64', 'chrome-headless-shell');
        if (existsSync(p)) return p;
    }
    return null;
}

async function reachable() {
    try {
        const r = await fetch(`${URL}/api/players`, { signal: AbortSignal.timeout(3000) });
        return r.ok;
    } catch { return false; }
}

const executablePath = findBrowser();
const up = await reachable();
const skip = !up ? `nothing answering at ${URL}` : !executablePath ? 'no headless Chromium found' : false;

let browser, page;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const APP = 'Alpine.$data(document.body)';
const modal = name => `Alpine.$data(document.querySelector('[x-data="${name}()"]'))`;
const MAP = `(() => { const el = document.querySelector('#worldMap'); return el ? Alpine.$data(el.parentElement) : null; })()`;

before(async () => {
    if (skip) return;
    browser = await chromium.launch({ headless: true, executablePath, args: ['--use-gl=angle', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
    page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    page.on('pageerror', e => { throw new Error(`page error: ${e.message}`); });
    await page.goto(`${URL}/`, { waitUntil: 'networkidle' });
    await page.waitForFunction(`${APP}.players?.length > 0 && ${APP}.pals?.length > 0`, null, { timeout: 30000 });
});
after(async () => { if (browser) await browser.close(); });

const pressEscape = async () => { await page.keyboard.press('Escape'); await sleep(350); };
const isOpen = (name, flag) => page.evaluate(`${modal(name)}.${flag}`);

test('the app loads with players and pals', { skip }, async () => {
    const n = await page.evaluate(`[${APP}.players.length, ${APP}.pals.length]`);
    assert.ok(n[0] > 0 && n[1] > 0, `players ${n[0]}, pals ${n[1]}`);
});

test('player modal opens on the inventory and closes on Escape', { skip }, async () => {
    const name = await page.evaluate(`(() => { const a = ${APP}; a.currentTab = 'players';
        const p = a.players.find(p => (p.bag || []).length > 0) || a.players[0];
        window.dispatchEvent(new CustomEvent('open-player-modal', { detail: { player: p, tab: 'inventory' } })); return p.player_name; })()`);
    await sleep(500);
    assert.equal(await isOpen('playerModal', 'showPlayerModal'), true);
    assert.ok((await page.locator('[x-data="playerModal()"] h2').first().innerText()).includes(name));
    assert.ok(await page.locator('[x-data="playerModal()"] [role="button"][data-tip]:visible').count() > 0, 'no item tiles in the bag');
    await pressEscape();
    assert.equal(await isOpen('playerModal', 'showPlayerModal'), false);
});

test('item popup from a bag slot: description arrives, Escape closes only the popup', { skip }, async () => {
    await page.evaluate(`(() => { const a = ${APP}; const p = a.players.find(p => (p.bag || []).length > 0) || a.players[0];
        window.dispatchEvent(new CustomEvent('open-player-modal', { detail: { player: p, tab: 'inventory' } })); })()`);
    await sleep(500);
    await page.locator('[x-data="playerModal()"] [role="button"][data-tip]:visible').first().click();
    await page.waitForFunction(`${modal('itemModal')}.detail !== null`, null, { timeout: 5000 });
    const d = await page.evaluate(`(() => { const m = ${modal('itemModal')}; return { show: m.showItemModal, name: m.itemName, desc: m.detail.description }; })()`);
    assert.equal(d.show, true);
    assert.ok(d.name && d.desc, `popup for ${d.name} has no description`);
    assert.ok(!/Factory Hard|WeaponFactory/.test(d.desc), 'raw workbench id in description');
    await pressEscape();
    assert.equal(await isOpen('itemModal', 'showItemModal'), false, 'popup still open');
    assert.equal(await isOpen('playerModal', 'showPlayerModal'), true, 'Escape closed the player modal under the popup');
    await pressEscape();
    assert.equal(await isOpen('playerModal', 'showPlayerModal'), false);
});

test('chest modal: tiles open the item popup', { skip }, async () => {
    await page.evaluate(`(async () => { const r = await fetch('/api/base-containers', { credentials: 'same-origin' }); const j = await r.json();
        const c = Object.values(j.containers || {}).flat().sort((a, b) => (b.items?.length || 0) - (a.items?.length || 0))[0];
        window.dispatchEvent(new CustomEvent('open-container-modal', { detail: { container: c } })); })()`);
    await sleep(500);
    assert.equal(await isOpen('containerModal', 'showContainerModal'), true);
    await page.locator('[x-data="containerModal()"] [role="button"]:visible').first().click();
    await page.waitForFunction(`${modal('itemModal')}.detail !== null`, null, { timeout: 5000 });
    assert.equal(await isOpen('itemModal', 'showItemModal'), true);
    await pressEscape();
    assert.equal(await isOpen('containerModal', 'showContainerModal'), true, 'Escape closed the chest under the popup');
    await pressEscape();
    assert.equal(await isOpen('containerModal', 'showContainerModal'), false);
});

test('pal modal opens from a pal and closes on Escape', { skip }, async () => {
    const name = await page.evaluate(`(() => { const pal = ${APP}.pals[0]; window.dispatchEvent(new CustomEvent('open-pal-modal', { detail: pal })); return pal.nickname || pal.name; })()`);
    await sleep(500);
    assert.equal(await isOpen('palModal', 'showPalModal'), true);
    assert.ok((await page.locator('[x-data="palModal()"] .modal-panel').innerText()).includes(name), `pal modal does not show ${name}`);
    await pressEscape();
    assert.equal(await isOpen('palModal', 'showPalModal'), false);
});

test('settings modal opens from the app state and closes on Escape', { skip }, async () => {
    await page.evaluate(`${APP}.showSettings = true`);
    await sleep(300);
    assert.ok(await page.getByText('Settings', { exact: true }).first().isVisible());
    await pressEscape();
    assert.equal(await page.evaluate(`${APP}.showSettings`), false);
});

test('"Show on map" leaves the World Tree for the map the player is on', { skip }, async () => {
    await page.evaluate(`${APP}.currentTab = 'map'`);
    await page.waitForFunction(`(${MAP})?.mapReady === true`, null, { timeout: 30000 });
    await page.evaluate(`(${MAP}).switchMapLayer('Tree')`);
    await sleep(1200);
    assert.equal(await page.evaluate(`(${MAP}).mapLayer`), 'Tree');
    await page.evaluate(`${APP}.currentTab = 'players'`);
    await sleep(400);
    await page.locator('button[aria-label="Show on map"]').first().click();
    await sleep(1500);
    const s = await page.evaluate(`(() => { const m = ${MAP}; return { tab: ${APP}.currentTab, layer: m.mapLayer }; })()`);
    assert.equal(s.tab, 'map');
    assert.equal(s.layer, 'MainMap');
});
