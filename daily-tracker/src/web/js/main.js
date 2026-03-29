/**
 * DayLife 入口文件 — Vite 构建用
 * 把所有模块合并为一个 minified bundle
 */

// Vendor libs（Vite 会 tree-shake 未使用的部分）
import './dayjs.min.js';
import './dayjs-zh-cn.js';
import './marked.min.js';

// App modules（保持全局变量挂载）
import './api.js';
import './charts.js';
import './calendar.js';
import './timeline.js';
import './app.js';

// Init dayjs locale
if (window.dayjs) dayjs.locale('zh-cn');
