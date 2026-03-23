/**
 * DayLife ECharts 图表配置与渲染
 */
const Charts = {
    instances: {},
    isDark: false,

    init(dark = false) {
        this.isDark = dark;
    },

    getTheme() {
        return this.isDark ? 'dark' : null;
    },

    getOrCreate(el, forceRecreate = false) {
        const id = typeof el === 'string' ? el : el.id;
        const dom = typeof el === 'string' ? document.getElementById(el) : el;
        if (!dom) return null;
        if (forceRecreate && this.instances[id]) {
            this.instances[id].dispose();
            delete this.instances[id];
        }
        if (!this.instances[id]) {
            this.instances[id] = echarts.init(dom, this.getTheme(), { renderer: 'canvas' });
        }
        return this.instances[id];
    },

    disposeAll() {
        Object.values(this.instances).forEach(c => c.dispose());
        this.instances = {};
    },

    resizeAll() {
        Object.values(this.instances).forEach(c => c.resize());
    },

    // ── 完成率环形图 ──────────────────────────────────────────
    renderCompletionRing(el, rate, label = '完成率') {
        const chart = this.getOrCreate(el, true);
        if (!chart) return;
        const pct = Math.round(rate * 100);
        const color = pct >= 80 ? '#10B981' : pct >= 50 ? '#F59E0B' : '#EF4444';
        chart.setOption({
            series: [{
                type: 'pie',
                radius: ['65%', '85%'],
                avoidLabelOverlap: false,
                label: {
                    show: true,
                    position: 'center',
                    formatter: `{a|${pct}%}\n{b|${label}}`,
                    rich: {
                        a: { fontSize: 28, fontWeight: 'bold', color: color, lineHeight: 36 },
                        b: { fontSize: 13, color: '#888', lineHeight: 24 },
                    },
                },
                data: [
                    { value: pct, itemStyle: { color: color } },
                    { value: 100 - pct, itemStyle: { color: this.isDark ? '#333' : '#F1F1F1' } },
                ],
                animationType: 'scale',
            }],
        });
        return chart;
    },

    // ── 分类占比饼图 ──────────────────────────────────────────
    renderCategoryPie(el, data) {
        const chart = this.getOrCreate(el, true);
        if (!chart) return;
        chart.setOption({
            tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
            legend: {
                orient: 'vertical',
                right: 10,
                top: 'center',
                textStyle: { color: this.isDark ? '#ccc' : '#333' },
            },
            series: [{
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['40%', '50%'],
                itemStyle: { borderRadius: 6, borderColor: this.isDark ? '#1a1a2e' : '#fff', borderWidth: 2 },
                label: { show: false },
                emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
                data: data.map(d => ({
                    name: `${d.icon || ''} ${d.category}`,
                    value: d.count,
                    itemStyle: { color: d.color || undefined },
                })),
            }],
        });
        return chart;
    },

    // ── 趋势折线图 ──────────────────────────────────────────
    renderTrendLine(el, data, xKey = 'date') {
        const chart = this.getOrCreate(el, true);
        if (!chart) return;
        const dates = data.map(d => d[xKey] || d.week_start || d.month);
        chart.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 50, right: 20, top: 30, bottom: 30 },
            xAxis: {
                type: 'category',
                data: dates,
                axisLabel: {
                    color: this.isDark ? '#aaa' : '#666',
                    formatter: v => v.length > 7 ? v.slice(5) : v,
                },
                axisLine: { lineStyle: { color: this.isDark ? '#444' : '#ddd' } },
            },
            yAxis: {
                type: 'value',
                minInterval: 1,
                axisLabel: { color: this.isDark ? '#aaa' : '#666' },
                splitLine: { lineStyle: { color: this.isDark ? '#333' : '#eee' } },
            },
            series: [{
                type: 'line',
                data: data.map(d => d.count),
                smooth: true,
                symbol: 'circle',
                symbolSize: 6,
                lineStyle: { width: 3, color: '#4F46E5' },
                itemStyle: { color: '#4F46E5' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(79,70,229,0.3)' },
                        { offset: 1, color: 'rgba(79,70,229,0.02)' },
                    ]),
                },
            }],
        });
        return chart;
    },

    // ── 分类完成率柱状图 ──────────────────────────────────────
    renderCompletionBar(el, data) {
        const chart = this.getOrCreate(el, true);
        if (!chart) return;
        chart.setOption({
            tooltip: { trigger: 'axis', formatter: p => `${p[0].name}: ${Math.round(p[0].value * 100)}%` },
            grid: { left: 80, right: 20, top: 10, bottom: 30 },
            xAxis: {
                type: 'value',
                max: 1,
                axisLabel: { formatter: v => Math.round(v * 100) + '%', color: this.isDark ? '#aaa' : '#666' },
                splitLine: { lineStyle: { color: this.isDark ? '#333' : '#eee' } },
            },
            yAxis: {
                type: 'category',
                data: data.map(d => `${d.icon || ''} ${d.category}`),
                axisLabel: { color: this.isDark ? '#ccc' : '#333' },
            },
            series: [{
                type: 'bar',
                data: data.map(d => ({
                    value: d.completion_rate,
                    itemStyle: { color: d.color || '#4F46E5', borderRadius: [0, 4, 4, 0] },
                })),
                barWidth: 18,
            }],
        });
        return chart;
    },
};

window.addEventListener('resize', () => Charts.resizeAll());
