/**
 * DayLife API 客户端 — 支持请求取消 + TTL 缓存
 */
const API = {
    BASE: '/api',

    // ── 请求取消支持 ──
    _controllers: {},
    _cache: {},

    async request(url, options = {}, tag = null) {
        // 带 tag 的请求支持取消（同 tag 新请求会取消旧请求）
        if (tag) {
            if (this._controllers[tag]) this._controllers[tag].abort();
            this._controllers[tag] = new AbortController();
            options.signal = this._controllers[tag].signal;
        }
        try {
            const resp = await fetch(this.BASE + url, {
                headers: { 'Content-Type': 'application/json', ...options.headers },
                ...options,
            });
            const json = await resp.json();
            if (json.code !== 0) {
                console.error('API Error:', json.message);
                return null;
            }
            return json.data;
        } catch (e) {
            if (e.name === 'AbortError') return null; // 被取消的请求静默处理
            console.error('Request failed:', url, e);
            return null;
        }
    },

    /** 带 TTL 缓存的请求 */
    async cachedRequest(url, ttlMs = 30000) {
        const now = Date.now();
        const cached = this._cache[url];
        if (cached && now - cached.time < ttlMs) {
            return cached.data;
        }
        const data = await this.request(url);
        if (data !== null) {
            this._cache[url] = { data, time: now };
        }
        return data;
    },

    /** 取消所有带 tag 的请求 */
    cancelAll() {
        Object.values(this._controllers).forEach(c => c.abort());
        this._controllers = {};
    },

    /** 清除缓存 */
    clearCache() { this._cache = {}; },

    // ── 活动记录 ──
    async getEntries(params = {}) {
        const qs = new URLSearchParams();
        Object.entries(params).forEach(([k, v]) => {
            if (v != null && v !== '') qs.set(k, v);
        });
        return this.request('/entries?' + qs.toString());
    },
    async getEntriesByDate(date) {
        return this.request('/entries?date=' + date);
    },
    async searchEntries(keyword, limit = 50) {
        return this.request(`/entries/search?q=${encodeURIComponent(keyword)}&limit=${limit}`, {}, 'search');
    },
    async createEntry(data) {
        return this.request('/entries', { method: 'POST', body: JSON.stringify(data) });
    },
    async updateEntry(id, data) {
        return this.request(`/entries/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },
    async deleteEntry(id) {
        return this.request(`/entries/${id}`, { method: 'DELETE' });
    },

    // ── 分类（缓存 30s）──
    async getCategories() { return this.cachedRequest('/categories'); },

    // ── 统计 ──
    async getDailyStats(date) { return this.request('/stats/daily' + (date ? `?date=${date}` : '')); },
    async getHeatmap(year) { return this.request('/stats/heatmap' + (year ? `?year=${year}` : '')); },
    async getHeatmapDetail(year) { return this.request('/stats/heatmap-detail' + (year ? `?year=${year}` : ''), {}, 'heatmap'); },
    async getCategoryStats(start, end) {
        const qs = new URLSearchParams();
        if (start) qs.set('start', start);
        if (end) qs.set('end', end);
        return this.request('/stats/category?' + qs.toString(), {}, 'category-stats');
    },
    async getTrend(start, end, interval = 'day') {
        const qs = new URLSearchParams();
        if (start) qs.set('start', start);
        if (end) qs.set('end', end);
        qs.set('interval', interval);
        return this.request('/stats/trend?' + qs.toString(), {}, 'trend');
    },
    async getCompletion(start, end) {
        const qs = new URLSearchParams();
        if (start) qs.set('start', start);
        if (end) qs.set('end', end);
        return this.request('/stats/completion?' + qs.toString(), {}, 'completion');
    },
    async getStreak() { return this.cachedRequest('/stats/streak', 60000); },
    async getYearlySummary(year) { return this.cachedRequest('/stats/yearly-summary' + (year ? `?year=${year}` : ''), 60000); },

    // ── 导入 ──
    async triggerImport(filePath, dryRun = false) {
        const form = new FormData();
        form.append('file_path', filePath);
        form.append('dry_run', dryRun);
        try {
            const resp = await fetch(this.BASE + '/import/excel', { method: 'POST', body: form });
            return await resp.json();
        } catch (e) { console.error('Import failed:', e); return null; }
    },
    async getImportStatus() { return this.request('/import/status'); },
    async getImportHistory() { return this.request('/import/history'); },

    // ── AI 分类 ──
    async classifyBatch(items) {
        return this.request('/classify/batch', {
            method: 'POST',
            body: JSON.stringify({ items }),
        });
    },
    async classifyStatus() {
        return this.request('/classify/status');
    },
    async classifyRun(batchSize = 30) {
        return this.request(`/classify/run?batch_size=${batchSize}`);
    },

    // ── GitHub ──
    async getGithubCommits(start, end) {
        return this.request(`/github/commits?start=${start}&end=${end}`);
    },
    async syncGithub(start, end) {
        return this.request(`/github/sync?start=${start}&end=${end}`);
    },

    // ── 报告 ──
    async getReportTree() { return this.request('/reports/tree'); },
    async getReport(periodKey) { return this.request(`/reports/${encodeURIComponent(periodKey)}`); },
    async generateReport(periodType, periodKey, force = false) {
        return this.request(`/reports/generate?period_type=${periodType}&period_key=${encodeURIComponent(periodKey)}&force=${force}`);
    },
    async generateAllReports() { return this.request('/reports/generate-all'); },
    async formatReport(periodKey) {
        return this.request(`/reports/format-one?period_key=${encodeURIComponent(periodKey)}`);
    },
    async formatAllReports() { return this.request('/reports/format-all'); },

    // ── 标签 ──
    async getTags() { return this.request('/tags'); },
    async createTag(data) {
        return this.request('/tags', { method: 'POST', body: JSON.stringify(data) });
    },
    async deleteTag(tagId) {
        return this.request(`/tags/${tagId}`, { method: 'DELETE' });
    },
    async getTagEntries(tagId, page = 1, limit = 200) {
        return this.request(`/tags/${tagId}/entries?page=${page}&limit=${limit}`);
    },
    async aiBatchTag(tagId, mode = 'keyword') {
        return this.request(`/tags/${tagId}/ai-batch?mode=${mode}`);
    },
    async getTagProgress(tagId) {
        return this.request(`/tags/${tagId}/progress`);
    },

    // ── 语音 ──
    async transcribeVoice(audioBlob) {
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.webm');
        try {
            const resp = await fetch(this.BASE + '/voice/transcribe', {
                method: 'POST',
                body: formData,
            });
            const json = await resp.json();
            if (json.code !== 0) { console.error('Voice error:', json.message); return null; }
            return json.data;
        } catch (e) { console.error('Voice failed:', e); return null; }
    },

    // ── 导出（前端生成下载） ──
    async exportEntries(start, end, format = 'csv') {
        const data = await this.getEntries({ start, end, limit: 999 });
        if (!data || !data.items || !data.items.length) return null;
        return data.items;
    },
};
