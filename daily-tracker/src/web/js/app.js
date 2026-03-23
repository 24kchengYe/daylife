/**
 * DayLife 主控制器
 */
const App = {
    currentView: 'dashboard',
    isDark: false,
    categories: [],
    selectedDate: dayjs().format('YYYY-MM-DD'),

    async init() {
        // 默认暗色主题，用户可切换
        const saved = localStorage.getItem('daylife-theme');
        this.isDark = saved ? saved === 'dark' : true;
        this.applyTheme();

        const cats = await API.getCategories();
        this.categories = cats || [];

        Calendar.init(date => this.onDayClick(date));

        // Nav
        document.querySelectorAll('[data-nav]').forEach(el => {
            el.onclick = () => this.switchView(el.dataset.nav);
        });
        document.getElementById('btn-prev')?.addEventListener('click', () => Calendar.prevMonth());
        document.getElementById('btn-next')?.addEventListener('click', () => Calendar.nextMonth());
        document.getElementById('btn-today')?.addEventListener('click', () => {
            Calendar.goToday();
            this.switchView('dashboard');
        });

        // 月份选择器
        const monthPicker = document.getElementById('month-picker');
        if (monthPicker) {
            monthPicker.addEventListener('change', () => {
                const [y, m] = monthPicker.value.split('-').map(Number);
                if (y && m) {
                    Calendar.currentYear = y;
                    Calendar.currentMonth = m - 1;
                    Calendar.loadMonth(y, m - 1);
                }
            });
        }

        // Search
        const si = document.getElementById('search-input');
        document.getElementById('search-btn')?.addEventListener('click', () => this.doSearch(si.value));
        si?.addEventListener('keydown', e => { if (e.key === 'Enter') this.doSearch(si.value); });

        // Import
        document.getElementById('import-btn')?.addEventListener('click', () => this.triggerImport());

        // Export
        document.getElementById('export-btn')?.addEventListener('click', () => this.doExport());
        // Default export dates
        const es = document.getElementById('export-start');
        const ee = document.getElementById('export-end');
        if (es) es.value = dayjs().startOf('month').format('YYYY-MM-DD');
        if (ee) ee.value = dayjs().format('YYYY-MM-DD');

        // Theme
        document.getElementById('theme-toggle')?.addEventListener('click', () => this.toggleTheme());

        // Quick input
        document.getElementById('quick-input')?.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.quickSave(); }
        });
        document.getElementById('quick-save-btn')?.addEventListener('click', () => this.quickSave());

        // 设置默认日期
        const ghEnd = document.getElementById('gh-sync-end');
        if (ghEnd) ghEnd.value = dayjs().format('YYYY-MM-DD');

        // 统计页时间选择下拉（动态：基于数据库中实际有数据的年月）
        this.buildStatPeriodDropdown();

        // 检查未分类条目
        setTimeout(() => this.checkUnclassified(), 2000);
    },

    // ── Views ──
    switchView(view) {
        this.currentView = view;
        document.querySelectorAll('.view-panel').forEach(el => {
            el.classList.toggle('active', el.dataset.view === view);
        });
        document.querySelectorAll('[data-nav]').forEach(el => {
            el.classList.toggle('nav-active', el.dataset.nav === view);
        });
        if (view === 'stats') {
            this.refreshStats();
            Calendar.loadHeatmapYear(parseInt(document.getElementById('heatmap-year')?.value || Calendar.currentYear));
        }
        if (view === 'search') document.getElementById('search-input')?.focus();
        if (view === 'import') this.loadImportHistory();
    },

    showMonthPicker() {
        const picker = document.getElementById('month-picker');
        if (!picker) return;
        // 设置当前值
        const y = Calendar.currentYear;
        const m = String(Calendar.currentMonth + 1).padStart(2, '0');
        picker.value = `${y}-${m}`;
        picker.style.pointerEvents = 'auto';
        picker.showPicker();
        picker.style.pointerEvents = 'none';
    },

    // ── Day click ──
    onDayClick(dateStr) {
        this.selectedDate = dateStr;
        this.showDayModal(dateStr);
    },

    // ── Day modal ──
    async showDayModal(dateStr) {
        const modal = document.getElementById('day-modal');
        if (!modal) return;

        document.getElementById('day-modal-title').textContent =
            dayjs(dateStr).format('M月D日 dddd');

        const catSelect = document.getElementById('quick-category');
        const catsFiltered = this.categories.filter(c => c.name !== '其他');
        catSelect.innerHTML = '<option value="">AI自动分类</option>' +
            catsFiltered.map(c => `<option value="${c.name}">${c.icon || ''} ${c.name}</option>`).join('');

        document.getElementById('quick-input').value = '';

        await this.loadDayEntries(dateStr);
        modal.classList.add('active');
        setTimeout(() => document.getElementById('quick-input')?.focus(), 80);
    },

    async loadDayEntries(dateStr) {
        const el = document.getElementById('day-entries-list');
        if (!el) return;
        const data = await API.getEntriesByDate(dateStr);
        const entries = data ? (data.items || data) : [];

        if (!entries.length) {
            el.innerHTML = '<div class="day-entries-empty">还没有记录</div>';
            return;
        }

        el.innerHTML = entries.map(e => {
            const cat = e.category || {};
            const isDone = e.status === 'completed';
            const dot = isDone ? 'dot-done' : 'dot-progress';
            const doneClass = isDone ? 'entry-done' : '';
            const catColor = cat.color || '#888';
            return `<div class="day-entry-item ${doneClass}">
                <div class="day-entry-main">
                    <span class="cal-dot-btn ${dot}" onclick="App.toggleStatus(${e.id},'${e.status}','${dateStr}')" title="${isDone ? '已完成，点击取消' : '点击标记完成'}"></span>
                    <span class="day-entry-content">${this.esc(e.content)}</span>
                </div>
                <div class="day-entry-meta">
                    <span class="day-entry-cat" style="color:${catColor}" onclick="App.cycleCategory(${e.id},'${dateStr}')" title="点击切换分类">${cat.icon||'📝'} ${cat.name||'未分类'}</span>
                </div>
                <div class="day-entry-actions">
                    <button class="btn-icon btn-xs" title="编辑" onclick="App.editEntry(${e.id},'${dateStr}')">✏️</button>
                    <button class="btn-icon btn-xs btn-danger" title="删除" onclick="App.removeEntry(${e.id},'${dateStr}')">🗑️</button>
                </div>
            </div>`;
        }).join('');
    },

    async loadDayGithub(dateStr) {
        // GitHub commits 显示在 entries 列表下方
        const el = document.getElementById('day-entries-list');
        if (!el) return;
        const ghData = await API.getGithubCommits(dateStr, dateStr).catch(() => null);
        if (!ghData || !ghData[dateStr] || ghData[dateStr].length === 0) return;
        const ghHtml = ghData[dateStr].map(g =>
            `<div class="day-entry-item day-gh-entry">
                <div class="day-entry-main">
                    <span class="cal-dot" style="background:var(--green)"></span>
                    <span class="day-entry-content"><strong>${this.esc(g.repo)}</strong>: ${this.esc(g.summary)} <span style="color:var(--text-3)">(${g.count} commits)</span></span>
                </div>
            </div>`
        ).join('');
        el.insertAdjacentHTML('beforeend',
            `<div class="day-gh-section"><div class="day-gh-title">GitHub Commits</div>${ghHtml}</div>`);
    },

    // ── Quick save ──
    async quickSave() {
        const input = document.getElementById('quick-input');
        const content = input.value.trim();
        if (!content) return;

        const category = document.getElementById('quick-category').value || null;
        await API.createEntry({
            date: this.selectedDate,
            content,
            category,
            status: 'completed',
            source: 'web',
        });
        // 没选分类的，后台标记为未AI分类，下次会被自动分类
        // 选了分类的，已在 entry_service 里标记 ai_classified=1
        input.value = '';
        this.toast('已保存');
        await this.loadDayEntries(this.selectedDate);
        Calendar.loadMonth(Calendar.currentYear, Calendar.currentMonth);
    },

    // ── Edit entry ──
    async editEntry(id, dateStr) {
        const data = await API.getEntriesByDate(dateStr);
        const entries = data ? (data.items || data) : [];
        const entry = entries.find(e => e.id === id);
        if (!entry) return;
        this.showEntryModal(entry, dateStr);
    },

    showEntryModal(entry, dateStr) {
        const modal = document.getElementById('entry-modal');
        if (!modal) return;
        modal.classList.add('active');

        const form = document.getElementById('entry-form');
        document.getElementById('modal-title').textContent = entry ? '编辑记录' : '添加记录';

        const cs = form.querySelector('[name="category"]');
        const editCats = this.categories.filter(c => c.name !== '其他');
        cs.innerHTML = '<option value="">AI自动分类</option>' +
            editCats.map(c => `<option value="${c.name}" ${entry?.category?.name===c.name?'selected':''}>${c.icon||''} ${c.name}</option>`).join('');

        form.querySelector('[name="content"]').value = entry?.content || '';
        form.querySelector('[name="is_done"]').checked = entry?.status === 'completed';
        form.querySelector('[name="notes"]').value = entry?.notes || '';
        form.querySelector('[name="date"]').value = dateStr || this.selectedDate;
        form.dataset.entryId = entry?.id || '';

        form.onsubmit = async (e) => {
            e.preventDefault();
            const fd = new FormData(form);
            const isDone = form.querySelector('[name="is_done"]').checked;
            const payload = {
                date: fd.get('date'), content: fd.get('content'),
                category: fd.get('category') || null,
                status: isDone ? 'completed' : 'in_progress',
                notes: fd.get('notes') || null, source: 'web',
            };
            if (form.dataset.entryId) { await API.updateEntry(parseInt(form.dataset.entryId), payload); this.toast('已更新'); }
            else { await API.createEntry(payload); this.toast('已保存'); }
            modal.classList.remove('active');
            await this.loadDayEntries(payload.date);
            Calendar.loadMonth(Calendar.currentYear, Calendar.currentMonth);
        };
    },

    closeModal() { document.getElementById('entry-modal')?.classList.remove('active'); },
    closeDayModal() { document.getElementById('day-modal')?.classList.remove('active'); },

    async toggleStatus(id, cur, dateStr) {
        const next = cur === 'completed' ? 'in_progress' : 'completed';
        await API.updateEntry(id, { status: next });
        await this.loadDayEntries(dateStr);
        Calendar.loadMonth(Calendar.currentYear, Calendar.currentMonth);
    },

    async cycleCategory(id, dateStr) {
        // 弹出分类选择
        const cats = this.categories;
        const menu = cats.map(c => `${c.icon||''} ${c.name}`).join('\n');
        const choice = prompt(`选择分类（输入数字）：\n${cats.map((c,i) => `${i+1}. ${c.icon||''} ${c.name}`).join('\n')}`);
        if (!choice) return;
        const idx = parseInt(choice) - 1;
        if (idx >= 0 && idx < cats.length) {
            await API.updateEntry(id, { category: cats[idx].name });
            await this.loadDayEntries(dateStr);
            Calendar.loadMonth(Calendar.currentYear, Calendar.currentMonth);
        }
    },

    async removeEntry(id, dateStr) {
        if (!confirm('确定删除？')) return;
        await API.deleteEntry(id);
        await this.loadDayEntries(dateStr);
        Calendar.loadMonth(Calendar.currentYear, Calendar.currentMonth);
    },

    // ── Stats ──
    async refreshStats() {
        Charts.init(this.isDark);
        const today = dayjs();
        const ms = today.startOf('month').format('YYYY-MM-DD');
        const ts = today.format('YYYY-MM-DD');

        const [streak, mc, catStats, trend, ys] = await Promise.all([
            API.getStreak(),
            API.getCompletion(ms, ts),
            API.getCategoryStats(ms, ts),
            API.getTrend(today.subtract(30,'day').format('YYYY-MM-DD'), ts, 'day'),
            API.getYearlySummary(today.year()),
        ]);

        if (streak) {
            const e1 = document.getElementById('streak-count');
            if (e1) e1.textContent = streak.current_streak || 0;
            const e2 = document.getElementById('streak-longest');
            if (e2) e2.textContent = streak.longest_streak?.days || 0;
        }
        if (ys) {
            const e3 = document.getElementById('total-entries');
            if (e3) e3.textContent = ys.total || 0;
        }
        if (mc && mc.length) {
            const total = mc.reduce((s,c) => s + (c.count||0), 0);
            const done = mc.reduce((s,c) => s + (c.completed||0), 0);
            const rate = total > 0 ? done / total : 0;
            Charts.renderCompletionRing('chart-month-completion', rate, '本月');
        } else Charts.renderCompletionRing('chart-month-completion', 0, '本月');

        if (catStats) Charts.renderCategoryPie('chart-category', catStats);
        if (trend) Charts.renderTrendLine('chart-trend', trend);

        // 高亮按钮
        document.querySelectorAll('.trend-range').forEach(b => {
            b.classList.toggle('btn-primary', b.dataset.range === String(this._trendDays || 30));
        });
        document.querySelectorAll('.stat-range').forEach(b => {
            b.classList.toggle('btn-primary', b.dataset.range === (this._statRange || 'month'));
        });
    },

    _statRange: 'month',
    async setStatRange(range) {
        this._statRange = range;
        const today = dayjs();
        let start, label;

        switch (range) {
            case 'month':
                start = today.startOf('month').format('YYYY-MM-DD');
                label = '本月';
                break;
            case 'quarter':
                start = today.startOf('quarter').format('YYYY-MM-DD');
                label = '本季度';
                break;
            case 'year':
                start = today.startOf('year').format('YYYY-MM-DD');
                label = '本年';
                break;
            case '90':
                start = today.subtract(90, 'day').format('YYYY-MM-DD');
                label = '近3月';
                break;
            case '365':
                start = today.subtract(365, 'day').format('YYYY-MM-DD');
                label = '近1年';
                break;
            case 'all':
                start = '2018-01-01';
                label = '全部';
                break;
            default:
                start = today.startOf('month').format('YYYY-MM-DD');
                label = '本月';
        }

        const end = today.format('YYYY-MM-DD');

        // 更新标题
        const ct = document.getElementById('completion-title');
        if (ct) ct.textContent = `${label}完成率`;
        const cat = document.getElementById('category-title');
        if (cat) cat.textContent = `${label}分类占比`;

        // 高亮按钮，重置下拉
        document.querySelectorAll('.stat-range').forEach(b => {
            b.classList.toggle('btn-primary', b.dataset.range === range);
        });
        const sp = document.getElementById('stat-period');
        if (sp) sp.value = '';

        // 重新加载数据
        const [mc, catStats] = await Promise.all([
            API.getCompletion(start, end),
            API.getCategoryStats(start, end),
        ]);

        if (mc && mc.length) {
            const total = mc.reduce((s, c) => s + (c.count || 0), 0);
            const done = mc.reduce((s, c) => s + (c.completed || 0), 0);
            const rate = total > 0 ? done / total : 0;
            Charts.renderCompletionRing('chart-month-completion', rate, label);
        } else {
            Charts.renderCompletionRing('chart-month-completion', 0, label);
        }
        if (catStats) Charts.renderCategoryPie('chart-category', catStats);
    },

    buildStatPeriodDropdown() {
        const sel = document.getElementById('stat-period');
        if (!sel) return;
        const now = dayjs();
        let html = '<option value="">指定时间...</option>';
        html += '<optgroup label="按年">';
        for (let y = now.year(); y >= 2018; y--) {
            html += `<option value="y-${y}">${y}年</option>`;
        }
        html += '</optgroup><optgroup label="按月">';
        // 从当前月往回到 2018年1月
        let d = now.startOf('month');
        const stop = dayjs('2018-01-01');
        while (d.isAfter(stop) || d.isSame(stop)) {
            html += `<option value="m-${d.format('YYYY-MM')}">${d.format('YYYY年M月')}</option>`;
            d = d.subtract(1, 'month');
        }
        html += '</optgroup>';
        sel.innerHTML = html;
    },

    async setStatPeriod(val) {
        if (!val) return;
        this._statRange = 'custom';
        let start, end, label;
        if (val.startsWith('y-')) {
            const y = parseInt(val.slice(2));
            start = `${y}-01-01`;
            end = `${y}-12-31`;
            label = `${y}年`;
        } else if (val.startsWith('m-')) {
            const d = dayjs(val.slice(2) + '-01');
            start = d.format('YYYY-MM-DD');
            end = d.endOf('month').format('YYYY-MM-DD');
            label = d.format('YYYY年M月');
        }
        document.querySelectorAll('.stat-range').forEach(b => b.classList.remove('btn-primary'));
        await this._loadStatRange(start, end, label);
    },

    async _loadStatRange(start, end, label) {
        const ct = document.getElementById('completion-title');
        if (ct) ct.textContent = `${label}完成率`;
        const cat = document.getElementById('category-title');
        if (cat) cat.textContent = `${label}分类占比`;

        const [mc, catStats] = await Promise.all([
            API.getCompletion(start, end),
            API.getCategoryStats(start, end),
        ]);
        if (mc && mc.length) {
            const total = mc.reduce((s, c) => s + (c.count || 0), 0);
            const done = mc.reduce((s, c) => s + (c.completed || 0), 0);
            Charts.renderCompletionRing('chart-month-completion', total > 0 ? done / total : 0, label);
        } else {
            Charts.renderCompletionRing('chart-month-completion', 0, label);
        }
        if (catStats) Charts.renderCategoryPie('chart-category', catStats);
    },

    _trendDays: 30,
    async setTrendRange(days) {
        this._trendDays = days;
        const today = dayjs();
        const ts = today.format('YYYY-MM-DD');
        const startDate = days > 0 ? today.subtract(days, 'day').format('YYYY-MM-DD') : '2018-01-01';
        const interval = days > 180 ? 'month' : days > 60 ? 'week' : 'day';
        const trend = await API.getTrend(startDate, ts, interval);
        if (trend) Charts.renderTrendLine('chart-trend', trend);
        document.querySelectorAll('.trend-range').forEach(b => {
            b.classList.toggle('btn-primary', b.dataset.range === String(days));
        });
    },

    // ── AI Classify (database-backed) ──
    async checkUnclassified() {
        const status = await API.classifyStatus();
        if (!status) return;
        if (status.unclassified > 0) {
            this._classifyTotal = status.total;
            this._classifyRemaining = status.unclassified;
            const bar = document.getElementById('ai-classify-bar');
            if (bar) bar.style.display = '';
            const txt = document.getElementById('ai-classify-text');
            if (txt) txt.textContent = `${status.unclassified} 个历日待AI分类（共 ${status.total} 个历日，已完成 ${status.classified} 个）`;
        }
    },

    async runAIClassify() {
        const btn = document.getElementById('ai-classify-btn');
        const progressDiv = document.getElementById('ai-classify-progress');
        const fillEl = document.getElementById('ai-progress-fill');
        const textEl = document.getElementById('ai-progress-text');
        const infoTxt = document.getElementById('ai-classify-text');

        btn.disabled = true;
        btn.textContent = '分类中...';
        progressDiv.style.display = '';

        const total = this._classifyRemaining || 0;
        let done = 0;

        // 轮询调用 /classify/run，每次处理一批
        while (true) {
            const result = await API.classifyRun(30);
            if (!result) { infoTxt.textContent = '分类出错，请重试'; break; }
            done += result.done;
            const remaining = result.remaining;
            const pct = total > 0 ? Math.min(Math.round((total - remaining) / total * 100), 100) : 100;
            fillEl.style.width = pct + '%';
            textEl.textContent = `${total - remaining}/${total}`;
            infoTxt.textContent = `正在分类... ${total - remaining}/${total} 个历日`;

            if (remaining === 0 || result.done === 0) break;
        }

        this.toast(`AI 分类完成：${done} 个历日`);
        // 3秒后隐藏分类栏
        setTimeout(() => {
            document.getElementById('ai-classify-bar').style.display = 'none';
        }, 3000);

        // 刷新
        Calendar.loadMonth(Calendar.currentYear, Calendar.currentMonth);
        Calendar.loadHeatmapYear(parseInt(document.getElementById('heatmap-year')?.value || Calendar.currentYear));
    },

    // ── Export ──
    async doExport() {
        const start = document.getElementById('export-start')?.value;
        const end = document.getElementById('export-end')?.value;
        const format = document.getElementById('export-format')?.value || 'csv';
        const statusEl = document.getElementById('export-status');

        if (!start || !end) { alert('请选择日期范围'); return; }
        statusEl.textContent = '导出中...';

        const entries = await API.exportEntries(start, end);
        if (!entries || !entries.length) { statusEl.textContent = '该范围内没有数据'; return; }

        let content, filename, mime;

        if (format === 'csv') {
            const header = 'date,category,content,status,start_time,end_time,notes';
            const rows = entries.map(e => {
                const cat = e.category?.name || '';
                const c = '"' + (e.content||'').replace(/"/g, '""') + '"';
                const n = '"' + (e.notes||'').replace(/"/g, '""') + '"';
                return `${e.date},${cat},${c},${e.status},${e.start_time||''},${e.end_time||''},${n}`;
            });
            content = '\uFEFF' + header + '\n' + rows.join('\n');
            filename = `daylife_${start}_${end}.csv`;
            mime = 'text/csv;charset=utf-8';
        } else if (format === 'json') {
            const data = entries.map(e => ({
                date: e.date, category: e.category?.name || null,
                content: e.content, status: e.status,
                start_time: e.start_time, end_time: e.end_time, notes: e.notes
            }));
            content = JSON.stringify(data, null, 2);
            filename = `daylife_${start}_${end}.json`;
            mime = 'application/json';
        } else {
            let lines = [`# DayLife ${start} ~ ${end}\n`];
            let curDay = null;
            entries.forEach(e => {
                if (e.date !== curDay) { curDay = e.date; lines.push(`\n## ${curDay}\n`); }
                const s = {completed:'V', incomplete:'X', in_progress:'~'}[e.status] || '?';
                const cat = e.category?.name ? `[${e.category.name}] ` : '';
                lines.push(`- [${s}] ${cat}${e.content}`);
            });
            content = lines.join('\n');
            filename = `daylife_${start}_${end}.md`;
            mime = 'text/markdown';
        }

        // 下载
        const blob = new Blob([content], { type: mime });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
        statusEl.textContent = `已导出 ${entries.length} 条记录`;
    },

    // ── Search ──
    async doSearch(kw) {
        if (!kw?.trim()) return;
        const el = document.getElementById('search-results');
        el.innerHTML = '<div class="loading">搜索中...</div>';

        const data = await API.searchEntries(kw.trim());
        if (!data?.length) { el.innerHTML = '<div class="empty-state">未找到匹配结果</div>'; return; }

        el.innerHTML = data.map(e => {
            const cat = e.category || {};
            return `<div class="search-item" onclick="App.closeDayModal();App.switchView('dashboard');App.onDayClick('${e.date}');">
                <div class="search-item-header">
                    <span class="search-item-date">${dayjs(e.date).format('YYYY-MM-DD ddd')}</span>
                    <span class="search-item-cat" style="color:${cat.color||'#666'}">${cat.icon||''} ${cat.name||''}</span>
                </div>
                <div class="search-item-content">${this.highlight(e.content, kw)}</div>
            </div>`;
        }).join('');
    },

    highlight(text, kw) {
        if (!text || !kw) return text || '';
        const esc = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return this.esc(text).replace(new RegExp(esc, 'gi'), m => `<mark>${m}</mark>`);
    },

    esc(text) {
        if (!text) return '';
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    },

    toast(msg) {
        const t = document.createElement('div');
        t.className = 'toast';
        t.textContent = msg;
        document.body.appendChild(t);
        setTimeout(() => t.remove(), 2000);
    },

    // ── GitHub Sync ──
    async syncGithub() {
        const start = document.getElementById('gh-sync-start')?.value;
        const end = document.getElementById('gh-sync-end')?.value;
        const statusEl = document.getElementById('gh-sync-status');
        if (!start || !end) { alert('请选择日期范围'); return; }
        statusEl.innerHTML = '<div class="loading">正在同步 GitHub...</div>';
        const result = await API.syncGithub(start, end);
        if (result) {
            statusEl.innerHTML = `<div style="color:var(--green);font-weight:600;margin-top:8px">同步完成：导入 ${result.imported} 条，跳过 ${result.skipped} 条（${result.total_dates} 天）</div>`;
            this.toast(`GitHub 同步完成：${result.imported} 条`);
            Calendar.loadMonth(Calendar.currentYear, Calendar.currentMonth);
        } else {
            statusEl.innerHTML = '<div style="color:var(--red)">同步失败</div>';
        }
    },

    // ── Import ──
    async triggerImport() {
        const p = document.getElementById('import-path');
        const dr = document.getElementById('import-dryrun');
        if (!p?.value.trim()) { alert('请输入路径'); return; }
        const s = document.getElementById('import-status');
        if (s) s.innerHTML = '<div class="loading">正在导入...</div>';

        const r = await API.triggerImport(p.value.trim(), dr?.checked || false);
        if (r) {
            if (s) s.innerHTML = `<div class="import-result">${JSON.stringify(r, null, 2)}</div>`;
            this.pollImportStatus();
        }
    },

    async pollImportStatus() {
        const s = document.getElementById('import-status');
        const check = async () => {
            const st = await API.getImportStatus();
            if (!st) return;
            if (st.running) {
                if (s) s.innerHTML = `<div class="loading">导入中... ${st.progress||''}</div>`;
                setTimeout(check, 2000);
            } else {
                if (st.last_result && s) {
                    s.innerHTML = `<div class="import-result"><div class="import-done">导入完成</div><pre>${JSON.stringify(st.last_result, null, 2)}</pre></div>`;
                }
                this.loadImportHistory();
                Calendar.loadMonth(Calendar.currentYear, Calendar.currentMonth);
            }
        };
        setTimeout(check, 2000);
    },

    async loadImportHistory() {
        const el = document.getElementById('import-history');
        if (!el) return;
        const data = await API.getImportHistory();
        if (!data?.length) { el.innerHTML = '<div class="empty-state">暂无导入记录</div>'; return; }
        el.innerHTML = `<table class="data-table">
            <thead><tr><th>时间</th><th>来源</th><th>导入</th><th>跳过</th><th>范围</th></tr></thead>
            <tbody>${data.map(r => `<tr>
                <td>${r.imported_at ? dayjs(r.imported_at).format('YY-MM-DD HH:mm') : '-'}</td>
                <td title="${r.source_file}">${r.source_file.split(/[/\\]/).pop()}</td>
                <td class="text-green">${r.rows_imported}</td>
                <td class="text-red">${r.rows_skipped}</td>
                <td>${r.date_range_start||'?'} ~ ${r.date_range_end||'?'}</td>
            </tr>`).join('')}</tbody>
        </table>`;
    },

    // ── Theme ──
    toggleTheme() {
        this.isDark = !this.isDark;
        localStorage.setItem('daylife-theme', this.isDark ? 'dark' : 'light');
        this.applyTheme();
        Charts.disposeAll();
        if (this.currentView === 'stats') this.refreshStats();
    },
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.isDark ? 'dark' : 'light');
        const icon = document.getElementById('theme-icon');
        if (icon) icon.textContent = this.isDark ? '☀️' : '🌙';
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
