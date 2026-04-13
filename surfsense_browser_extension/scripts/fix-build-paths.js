#!/usr/bin/env node
/**
 * Post-build script to fix absolute paths in Plasmo-generated HTML files.
 * 
 * Problem: Plasmo generates HTML files with absolute paths (e.g., href="/file.css")
 * which don't work in Chrome extensions (ERR_FILE_NOT_FOUND).
 * 
 * Solution: Replace absolute paths with relative paths (e.g., href="./file.css")
 */

const fs = require('fs');
const path = require('path');

const BUILD_DIR = path.join(__dirname, '..', 'build', 'chrome-mv3-prod');
const HTML_FILES = ['popup.html', 'sidepanel.html'];

function fixPaths(filePath) {
    if (!fs.existsSync(filePath)) {
        console.log(`⚠️  File not found: ${filePath}`);
        return false;
    }

    let content = fs.readFileSync(filePath, 'utf8');
    const originalContent = content;

    // Replace absolute paths with relative paths
    // href="/something" -> href="./something"
    // src="/something" -> src="./something"
    content = content.replace(/href="\/([^"]+)"/g, 'href="./$1"');
    content = content.replace(/src="\/([^"]+)"/g, 'src="./$1"');

    if (content !== originalContent) {
        fs.writeFileSync(filePath, content, 'utf8');
        console.log(`✅ Fixed paths in: ${path.basename(filePath)}`);
        return true;
    } else {
        console.log(`ℹ️  No changes needed: ${path.basename(filePath)}`);
        return false;
    }
}

function main() {
    console.log('🔧 Fixing build paths for Chrome extension...\n');

    if (!fs.existsSync(BUILD_DIR)) {
        console.error(`❌ Build directory not found: ${BUILD_DIR}`);
        console.error('   Run "pnpm build" first.');
        process.exit(1);
    }

    let fixedCount = 0;
    for (const htmlFile of HTML_FILES) {
        const filePath = path.join(BUILD_DIR, htmlFile);
        if (fixPaths(filePath)) {
            fixedCount++;
        }
    }

    console.log(`\n✨ Done! Fixed ${fixedCount} file(s).`);
}

main();

