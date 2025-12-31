#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const partialsDir = join(__dirname, 'partials');
const tabsDir = join(partialsDir, 'tabs');

// Read all partials
const head = readFileSync(join(partialsDir, 'head.html'), 'utf-8');
const header = readFileSync(join(partialsDir, 'header.html'), 'utf-8');

// Read tab navigation and individual tabs
const tabNavigation = readFileSync(join(partialsDir, 'tab-navigation.html'), 'utf-8');
const overviewTab = readFileSync(join(tabsDir, 'overview-tab.html'), 'utf-8');
const playersTab = readFileSync(join(tabsDir, 'players-tab.html'), 'utf-8');
const palsTab = readFileSync(join(tabsDir, 'pals-tab.html'), 'utf-8');

// Read modals and footer
const modals = readFileSync(join(partialsDir, 'modals.html'), 'utf-8');
const footer = readFileSync(join(partialsDir, 'footer.html'), 'utf-8');

// Combine into final HTML - exactly as it appears in original
const fullHTML = `${head}${header}${tabNavigation}${overviewTab}${playersTab}${palsTab}${modals}${footer}`;

// Write the final HTML
writeFileSync(join(__dirname, 'index.html'), fullHTML);

console.log('✅ Built index.html from partials');
