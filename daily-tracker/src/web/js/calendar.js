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
        tbody.innerHTML = '';

        const year = this.currentYear, month = this.currentMonth;
        const totalDays = new Date(year, month + 1, 0).getDate();
        let startDow = new Date(year, month, 1).getDay() - 1;
        if (startDow < 0) startDow = 6;
        const todayStr = this.fmtDate(new Date());

        const cells = [];
        // 上月填充
        const prevLast = new Date(year, month, 0).getDate();
        for (let i = startDow - 1; i >= 0; i--) {
            const d = prevLast - i;
            cells.push({ day: d, dateStr: this.fmtDate(new Date(year, month - 1, d)), outside: true });
        }
        // 本月
        for (let d = 1; d <= totalDays; d++) {
            cells.push({ day: d, dateStr: this.fmtDate(new Date(year, month, d)), outside: false });
        }
        // 下月填充
        const rem = 7 - (cells.length % 7);
        if (rem < 7) {
            for (let d = 1; d <= rem; d++) {
                cells.push({ day: d, dateStr: this.fmtDate(new Date(year, month + 1, d)), outside: true });
            }
        }

        for (let i = 0; i < cells.length; i += 7) {
            const tr = document.createElement('tr');
            for (let j = 0; j < 7; j++) {
                const c = cells[i + j];
                const td = document.createElement('td');
                td.className = 'cal-cell';
                if (c.outside) td.classList.add('outside');
                if (c.dateStr === todayStr) td.classList.add('today');
                if (j >= 5) td.classList.add('weekend');

                const entries = this.monthEntries[c.dateStr] || [];
                const subs = this.toItems(entries);
                const n = subs.length;

                // inner div 固定高度
                const inner = document.createElement('div');
                inner.className = 'cal-inner';

                // 日期行：数字 + badge + 分类色块（同一行）
                const dn = document.createElement('div');
                dn.className = 'cal-day-num';
                dn.textContent = c.day;
                if (n > 0) {
                    const b = document.createElement('span');
                    b.className = 'cal-badge';
                    b.textContent = n;
                    dn.appendChild(b);
                }
                // 分类色块（紧跟 badge 后面）
                if (n > 0 && !c.outside) {
                    const cc = {};
                    subs.forEach(s => { cc[s.category] = (cc[s.category] || 0) + 1; });
                    const cr = document.createElement('span');
                    cr.className = 'cal-cats';
                    this.CATEGORY_ORDER.forEach(cat => {
                        const bl = document.createElement('span');
                        bl.className = 'cat-block';
                        const cnt = cc[cat] || 0;
                        if (cnt > 0) {
                            bl.style.background = this.CATEGORY_COLORS[cat];
                            bl.style.opacity = Math.min(0.4 + cnt * 0.2, 1);
                            bl.title = `${cat}: ${cnt}条`;
                        } else {
                            bl.style.background = 'var(--border-light)';
                        }
                        cr.appendChild(bl);
                    });
                    dn.appendChild(cr);
                }
                inner.appendChild(dn);

                // 内容预览
                if (n > 0 && !c.outside) {
                    const pv = document.createElement('div');
                    pv.className = 'cal-preview';
                    subs.forEach(item => {
                        const ln = document.createElement('div');
                        const isGh = item.text.startsWith('[GitHub]');
                        const sc = item.status === 'completed' ? 'is-done' : item.status === 'incomplete' ? 'is-fail' : '';
                        ln.className = 'cal-preview-item ' + sc + (isGh ? ' is-github' : '');
                        const sd = isGh ? 'dot-github' : (item.status === 'completed' ? 'dot-done' : item.status === 'incomplete' ? 'dot-fail' : 'dot-progress');
                        ln.innerHTML = `<span class="cal-dot ${sd}"></span><span class="cal-preview-text">${this.esc(item.text)}</span>`;
                        pv.appendChild(ln);
                    });
                    inner.appendChild(pv);
                }

                td.appendChild(inner);
                td.onclick = () => { if (this.onDayClick) this.onDayClick(c.dateStr); };
                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        }
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
        const data = await API.getEntries({ start: `${year}-01-01`, end: `${year}-12-31`, limit: 9999 });
        this.heatmapYearItems = {};
        if (data && data.items) {
            const byDate = {};
            data.items.forEach(e => {
                if (!byDate[e.date]) byDate[e.date] = [];
                byDate[e.date].push(e);
            });
            for (const [ds, es] of Object.entries(byDate)) {
                this.heatmapYearItems[ds] = this.toItems(es);
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
        grid.appendChild(this.buildHeatmapRow(year, '总览', null, ds => (items[ds] || []).length));

        // GitHub 行
        let hasGh = false;
        for (const dayItems of Object.values(items)) {
            if (dayItems.some(i => i.text.startsWith('[GitHub]'))) { hasGh = true; break; }
        }
        if (hasGh) {
            grid.appendChild(this.buildHeatmapRow(year, 'GitHub', '#8b5cf6',
                ds => (items[ds] || []).filter(i => i.text.startsWith('[GitHub]')).length));
        }

        // 分类行
        const catHas = {};
        for (const dayItems of Object.values(items)) {
            dayItems.forEach(i => { if (i.category !== '其他') catHas[i.category] = true; });
        }
        this.CATEGORY_ORDER.forEach(cat => {
            if (!catHas[cat]) return;
            grid.appendChild(this.buildHeatmapRow(year, cat, this.CATEGORY_COLORS[cat],
                ds => (items[ds] || []).filter(i => i.category === cat).length));
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
