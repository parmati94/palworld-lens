#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const partialsDir = join(__dirname, 'partials');

// Read all partials
const head = readFileSync(join(partialsDir, 'head.html'), 'utf-8');
const header = readFileSync(join(partialsDir, 'header.html'), 'utf-8');
const content = readFileSync(join(partialsDir, 'content.html'), 'utf-8');
const footer = readFileSync(join(partialsDir, 'footer.html'), 'utf-8');

// Combine into final HTML - exactly as it appears in original
const fullHTML = `${head}${header}${content}${footer}`;

// Write the final HTML
writeFileSync(join(__dirname, 'index.html'), fullHTML);

console.log('✅ Built index.html from partials');
