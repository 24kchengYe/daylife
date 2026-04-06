/**
 * DayLife 月历组件 + 年度热力图（分类多行）
 */
const Calendar = {
    currentYear: new Date().getFullYear(),
    currentMonth: new Date().getMonth(),
    monthEntries: {},
    heatmapYearItems: {},
    onDayClick: null,

    // 关键词分类（LLM fallback）
    CATEGORY_KEYWORDS: {
        '科研': ['论文','paper','研究','实验','数据分析','模型','算法','scidata','gis','遥感','建模','仿真','survey','review','综述','课题','基金','申请书','efc','aius','街景','鬼城','城市规划','空间','建筑'],
        '编程': ['代码','编程','python','java','debug','git','网站','开发','前端','后端','pycharm','vscode','code','爬虫','api','程序'],
        '运动': ['运动','跑步','健身','锻炼','游泳','骑行','体育','篮球','羽毛球','乒乓'],
        '学习': ['学习','课程','考试','复习','笔试','教材','mooc','文献','阅读','课','ppt','教学'],
        '社交': ['社交','聚餐','组会','讨论','沙龙','座谈','答辩','面试','沟通','推送','公众号'],
        '工作': ['工作','工资','助教','助研','值班','办公','行政','材料','通知','体育部','研运会','骑行市集','部务','奖学金','志愿','报销','交接'],
        '娱乐': ['娱乐','游戏','电影','音乐','视频','小说','旅游','长沙','南京','成都','威海'],
        '休息': ['休息','睡觉','午休'],
        '生活': ['生活','购物','买','吃饭','做饭','打扫','洗','修','搬','快递','签证','火车','飞机','婚礼','补牙','衣服'],
    },

    CATEGORY_COLORS: {
        '学习':'#4A90D9','科研':'#7B68EE','编程':'#00BCD4','运动':'#2ECC71',
        '生活':'#F39C12','社交':'#FF6B6B','工作':'#E74C3C','娱乐':'#9B59B6',
        '休息':'#95A5A6','GitHub':'#8b5cf6','其他':'#BDC3C7',
    },
    CATEGORY_ORDER: ['学习','科研','编程','运动','生活','社交','工作','娱乐','休息','GitHub'],

    classifyItem(text) {
        if (!text) return '其他';
        const lower = text.toLowerCase();
        for (const [cat, keywords] of Object.entries(this.CATEGORY_KEYWORDS)) {
            for (const kw of keywords) {
                if (lower.includes(kw.toLowerCase())) return cat;
            }
        }
        return '其他';
    },

    /**
     * 把 entries 转成显示用的 items 列表
     * 迁移后每条 entry 就是一个独立活动，不再需要拆分
     */
    toItems(entries) {
        return entries.map(e => ({
            text: e.content,
            status: e.status,
            category: e.category?.name || this.classifyItem(e.content),
            id: e.id,
        }));
    },


    init(onDayClick) {
        this.onDayClick = onDayClick;
        this.initHeatmapYearSelector();
        this.loadMonth(this.currentYear, this.currentMonth);
        this.loadHeatmapYear(this.currentYear);
    },

    updateMonthLabel() {
        const el = document.getElementById('month-label');
        if (el) el.textContent = `${this.currentYear}年${this.currentMonth + 1}月`;
    },
    prevMonth() {
        this.currentMonth--;
        if (this.currentMonth < 0) { this.currentMonth = 11; this.currentYear--; }
        this.loadMonth(this.currentYear, this.currentMonth);
    },
    nextMonth() {
        this.currentMonth++;
        if (this.currentMonth > 11) { this.currentMonth = 0; this.currentYear++; }
        this.loadMonth(this.currentYear, this.currentMonth);
    },
    goToday() {
        const t = new Date();
        this.currentYear = t.getFullYear();
        this.currentMonth = t.getMonth();
        this.loadMonth(this.currentYear, this.currentMonth);
    },

    async loadMonth(year, month) {
        this.currentYear = year;
        this.currentMonth = month;
        this.updateMonthLabel();
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);

        const data = await API.getEntries({ start: this.fmtDate(firstDay), end: this.fmtDate(lastDay), limit: 9999 });
        this.monthEntries = {};
        if (data && data.items) {
            data.items.forEach(e => {
                if (!this.monthEntries[e.date]) this.monthEntries[e.date] = [];
                this.monthEntries[e.date].push(e);
            });
        }
        this.renderMonthGrid();
    },

    renderMonthGrid() {
        const tbody = document.getElementById('calendar-body');
        if (!tbody) return;

        const year = this.currentYear, month = this.currentMonth;
        const totalDays = new Date(year, month + 1, 0).getDate();
        let startDow = new Date(year, month, 1).getDay() - 1;
        if (startDow < 0) startDow = 6;
        const todayStr = this.fmtDate(new Date());

        const cells = [];
        const prevLast = new Date(year, month, 0).getDate();
        for (let i = startDow - 1; i >= 0; i--) {
            const d = prevLast - i;
            cells.push({ day: d, dateStr: this.fmtDate(new Date(year, month - 1, d)), outside: true });
        }
        for (let d = 1; d <= totalDays; d++) {
            cells.push({ day: d, dateStr: this.fmtDate(new Date(year, month, d)), outside: false });
        }
        const rem = 7 - (cells.length % 7);
        if (rem < 7) {
            for (let d = 1; d <= rem; d++) {
                cells.push({ day: d, dateStr: this.fmtDate(new Date(year, month + 1, d)), outside: true });
            }
        }

        // 构建 HTML 字符串（单次 innerHTML，减少 350+ DOM 操作）
        let html = '';
        for (let i = 0; i < cells.length; i += 7) {
            html += '<tr>';
            for (let j = 0; j < 7; j++) {
                const c = cells[i + j];
                const entries = this.monthEntries[c.dateStr] || [];
                const subs = this.toItems(entries);
                const n = subs.length;
                const cls = ['cal-cell'];
                if (c.outside) cls.push('outside');
                if (c.dateStr === todayStr) cls.push('today');
                if (j >= 5) cls.push('weekend');

                html += `<td class="${cls.join(' ')}" data-date="${c.dateStr}"><div class="cal-inner">`;
                html += `<div class="cal-day-num">${c.day}`;
                if (n > 0) html += `<span class="cal-badge">${n}</span>`;
                if (n > 0 && !c.outside) {
                    const cc = {};
                    subs.forEach(s => { cc[s.category] = (cc[s.category] || 0) + 1; });
                    html += '<span class="cal-cats">';
                    this.CATEGORY_ORDER.forEach(cat => {
                        const cnt = cc[cat] || 0;
                        if (cnt > 0) {
                            html += `<span class="cat-block" style="background:${this.CATEGORY_COLORS[cat]};opacity:${Math.min(0.4 + cnt * 0.2, 1)}" title="${cat}: ${cnt}条"></span>`;
                        } else {
                            html += `<span class="cat-block" style="background:var(--border-light)"></span>`;
                        }
                    });
                    html += '</span>';
                }
                html += '</div>';
                if (n > 0 && !c.outside) {
                    html += '<div class="cal-preview">';
                    subs.forEach(item => {
                        const isGh = item.text.startsWith('[GitHub]');
                        const sc = item.status === 'completed' ? 'is-done' : item.status === 'incomplete' ? 'is-fail' : '';
                        const sd = isGh ? 'dot-github' : (item.status === 'completed' ? 'dot-done' : item.status === 'incomplete' ? 'dot-fail' : 'dot-progress');
                        html += `<div class="cal-preview-item ${sc}${isGh ? ' is-github' : ''}"><span class="cal-dot ${sd}"></span><span class="cal-preview-text">${this.esc(item.text)}</span></div>`;
                    });
                    html += '</div>';
                }
                html += '</div></td>';
            }
            html += '</tr>';
        }
        tbody.innerHTML = html;

        // 事件委托（1 个监听器替代 42 个 onclick）
        tbody.onclick = (e) => {
            const td = e.target.closest('.cal-cell');
            if (td && td.dataset.date && this.onDayClick) this.onDayClick(td.dataset.date);
        };
    },

    // ═══ 年度热力图（分类多行，无星期标签） ═══
    initHeatmapYearSelector() {
        const sel = document.getElementById('heatmap-year');
        if (!sel) return;
        for (let y = 2026; y >= 2019; y--) {
            const o = document.createElement('option');
            o.value = y; o.textContent = y + '年';
            if (y === this.currentYear) o.selected = true;
            sel.appendChild(o);
        }
        sel.onchange = () => this.loadHeatmapYear(parseInt(sel.value));
    },

    async loadHeatmapYear(year) {
        // 使用轻量 API：只获取聚合数据（KB 级），不获取完整 content（MB 级）
        const data = await API.getHeatmapDetail(year);
        this.heatmapYearItems = {};
        if (data && Array.isArray(data)) {
            for (const r of data) {
                if (!this.heatmapYearItems[r.date]) this.heatmapYearItems[r.date] = [];
                this.heatmapYearItems[r.date].push({
                    cat: r.category, color: r.color, icon: r.icon,
                    count: r.count, done: r.status === 'completed',
                });
            }
        }
        this.renderHeatmap(year);
    },

    buildHeatmapRow(year, label, color, countFn) {
        const row = document.createElement('div');
        row.className = 'heatmap-row';

        const lbl = document.createElement('div');
        lbl.className = 'heatmap-label';
        lbl.textContent = label;
        if (color) lbl.style.color = color;
        row.appendChild(lbl);

        const weeks = document.createElement('div');
        weeks.className = 'calendar-weeks';

        const firstDay = new Date(year, 0, 1);
        const lastDay = new Date(year, 11, 31);
        let cur = new Date(firstDay);
        const dow = cur.getDay();
        cur.setDate(cur.getDate() + (dow === 0 ? -6 : 1 - dow));

        while (cur <= lastDay || cur.getDay() !== 1) {
            const wk = document.createElement('div');
            wk.className = 'calendar-week';
            for (let d = 0; d < 7; d++) {
                const cell = document.createElement('div');
                cell.className = 'calendar-cell';
                const ds = this.fmtDate(cur);
                if (cur.getFullYear() === year) {
                    const cnt = countFn(ds);
                    cell.className += ' ' + this.getColorClass(cnt);
                    cell.title = dayjs(ds).format('M月D日') + (cnt > 0 ? ` ${cnt}条` : '');
                    cell.onclick = () => { if (this.onDayClick) this.onDayClick(ds); };
                } else {
                    cell.className += ' calendar-cell-empty';
                }
                wk.appendChild(cell);
                cur.setDate(cur.getDate() + 1);
            }
            weeks.appendChild(wk);
            if (cur > lastDay && cur.getDay() === 1) break;
        }

        row.appendChild(weeks);
        return row;
    },

    renderHeatmap(year) {
        const grid = document.getElementById('heatmap-grid');
        if (!grid) return;
        grid.innerHTML = '';

        const items = this.heatmapYearItems || {};

        // 月份标签（按实际周位置定位）
        const mlRow = document.createElement('div');
        mlRow.className = 'heatmap-row heatmap-month-row';
        const mlSpacer = document.createElement('div');
        mlSpacer.className = 'heatmap-label';
        mlRow.appendChild(mlSpacer);

        const mlContainer = document.createElement('div');
        mlContainer.className = 'calendar-month-labels';
        mlContainer.style.position = 'relative';

        // 计算每个月第一天所在的周索引
        const cellW = 18; // 16px cell + 2px gap
        const months = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
        const jan1 = new Date(year, 0, 1);
        const jan1dow = jan1.getDay();
        const startOffset = jan1dow === 0 ? -6 : 1 - jan1dow;
        const gridStart = new Date(jan1);
        gridStart.setDate(gridStart.getDate() + startOffset);

        for (let m = 0; m < 12; m++) {
            const monthFirst = new Date(year, m, 1);
            const diffDays = Math.round((monthFirst - gridStart) / 86400000);
            const weekIdx = Math.floor(diffDays / 7);
            const s = document.createElement('span');
            s.textContent = months[m];
            s.style.position = 'absolute';
            s.style.left = (weekIdx * cellW) + 'px';
            mlContainer.appendChild(s);
        }

        // 容器需要有宽度
        const totalWeeks = 53;
        mlContainer.style.width = (totalWeeks * cellW) + 'px';
        mlContainer.style.height = '14px';
        mlRow.appendChild(mlContainer);
        grid.appendChild(mlRow);

        // 总览行
        grid.appendChild(this.buildHeatmapRow(year, '总览', null, ds => (items[ds] || []).reduce((s, i) => s + i.count, 0)));

        // GitHub 行
        let hasGh = false;
        for (const dayItems of Object.values(items)) {
            if (dayItems.some(i => i.cat === 'GitHub')) { hasGh = true; break; }
        }
        if (hasGh) {
            grid.appendChild(this.buildHeatmapRow(year, 'GitHub', '#8b5cf6',
                ds => (items[ds] || []).filter(i => i.cat === 'GitHub').reduce((s, i) => s + i.count, 0)));
        }

        // 分类行
        const catHas = {};
        for (const dayItems of Object.values(items)) {
            dayItems.forEach(i => { if (i.cat !== '其他') catHas[i.cat] = true; });
        }
        this.CATEGORY_ORDER.forEach(cat => {
            if (!catHas[cat]) return;
            grid.appendChild(this.buildHeatmapRow(year, cat, this.CATEGORY_COLORS[cat],
                ds => (items[ds] || []).filter(i => i.cat === cat).reduce((s, i) => s + i.count, 0)));
        });
    },

    getColorClass(c) {
        if (c === 0) return 'level-0';
        if (c <= 2) return 'level-1';
        if (c <= 5) return 'level-2';
        if (c <= 8) return 'level-3';
        return 'level-4';
    },

    esc(t) {
        if (!t) return '';
        const d = document.createElement('div');
        d.textContent = t;
        return d.innerHTML;
    },

    fmtDate(d) {
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    },
};
