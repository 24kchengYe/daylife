/**
 * postinstall: 复制 electron.exe 为 DayLife.exe 并设置自定义图标
 * npm install 后自动执行
 */
const fs = require('fs');
const path = require('path');

const distDir = path.join(__dirname, '..', 'node_modules', 'electron', 'dist');
const src = path.join(distDir, 'electron.exe');
const dst = path.join(distDir, 'DayLife.exe');
const ico = path.join(__dirname, '..', 'icon.ico');

if (!fs.existsSync(src)) {
    console.log('[postinstall] electron.exe not found, skipping');
    process.exit(0);
}

// 复制
fs.copyFileSync(src, dst);
console.log('[postinstall] Copied electron.exe -> DayLife.exe');

// 设置图标
try {
    const { rcedit } = require('rcedit');
    rcedit(dst, {
        icon: ico,
        'version-string': {
            ProductName: 'DayLife',
            FileDescription: 'DayLife - 每日记录',
            CompanyName: '24kchengYe',
        },
    }).then(() => {
        console.log('[postinstall] Icon and metadata set on DayLife.exe');
    }).catch(e => {
        console.log('[postinstall] rcedit failed:', e.message);
    });
} catch (e) {
    console.log('[postinstall] rcedit not available, icon not set');
}
