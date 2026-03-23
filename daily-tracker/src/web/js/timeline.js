/**
 * DayLife 每日时间线视图
 */
const Timeline = {
    container: null,
    currentDate: null,
    entries: [],
    categories: [],
    onUpdate: null,

    init(containerId, onUpdate) {
        this.container = document.getElementById(containerId);
        this.onUpdate = onUpdate;
    },

    setCategories(cats) {
        this.categories = cats || [];
    },

    async loadDate(dateStr) {
        this.currentDate = dateStr;
        const data = await API.getEntriesByDate(dateStr);
        this.entries = data ? (data.items || data) : [];
        this.render();
    },

    render() {
        if (!this.container) return;
        const titleEl = this.container.querySelector('.timeline-date');
        if (titleEl) {
            titleEl.textContent = this.currentDate
                ? dayjs(this.currentDate).format('YYYY年M月D日 dddd')
                : '请选择日期';
        }

        const listEl = this.container.querySelector('.timeline-list');
        if (!listEl) return;
        listEl.innerHTML = '';

        if (!this.entries.length) {
            listEl.innerHTML = `<div class="timeline-empty">
                <div class="empty-icon">📭</div>
                <div>这一天还没有记录</div>
                <button class="btn btn-primary btn-sm" onclick="Timeline.showAddForm()">添加活动</button>
            </div>`;
            return;
        }

        // 按时间排序
        const sorted = [...this.entries].sort((a, b) => {
            if (a.start_time && b.start_time) return a.start_time.localeCompare(b.start_time);
            if (a.start_time) return -1;
            if (b.start_time) return 1;
            return (a.id || 0) - (b.id || 0);
        });

        sorted.forEach(entry => {
            const item = document.createElement('div');
            item.className = 'timeline-item';
            item.dataset.id = entry.id;

            const cat = entry.category || {};
            const color = cat.color || '#4F46E5';
            const statusClass = entry.status === 'completed' ? 'status-done'
                : entry.status === 'incomplete' ? 'status-fail' : 'status-progress';
            const statusIcon = entry.status === 'completed' ? '✓'
                : entry.status === 'incomplete' ? '✗' : '◔';
            const statusLabel = entry.status === 'completed' ? '已完成'
                : entry.status === 'incomplete' ? '未完成' : '进行中';

            const timeStr = entry.start_time
                ? entry.start_time.slice(0, 5) + (entry.end_time ? ' - ' + entry.end_time.slice(0, 5) : '')
                : '';

            const durationStr = entry.duration_minutes
                ? `${Math.floor(entry.duration_minutes / 60)}h${entry.duration_minutes % 60 ? entry.duration_minutes % 60 + 'm' : ''}`
                : '';

            const tags = (entry.tags || []).map(t =>
                `<span class="tag" style="background:${t.color || '#e5e7eb'}">${t.name}</span>`
            ).join('');

            item.innerHTML = `
                <div class="timeline-dot" style="background:${color}"></div>
                <div class="timeline-connector" style="background:${color}30"></div>
                <div class="timeline-card">
                    <div class="timeline-card-header">
                        <div class="timeline-category" style="color:${color}">
                            ${cat.icon || '📝'} ${cat.name || '未分类'}
                        </div>
                        <span class="timeline-status ${statusClass}" title="${statusLabel}">${statusIcon}</span>
                    </div>
                    <div class="timeline-content">${this.escapeHtml(entry.content)}</div>
                    <div class="timeline-meta">
                        ${timeStr ? `<span class="meta-time">🕐 ${timeStr}</span>` : ''}
                        ${durationStr ? `<span class="meta-duration">⏱ ${durationStr}</span>` : ''}
                        ${entry.priority && entry.priority !== 3 ? `<span class="meta-priority">P${entry.priority}</span>` : ''}
                        ${tags}
                    </div>
                    ${entry.notes ? `<div class="timeline-notes">${this.escapeHtml(entry.notes)}</div>` : ''}
                    <div class="timeline-actions">
                        <button class="btn-icon" title="编辑" onclick="Timeline.editEntry(${entry.id})">✏️</button>
                        <button class="btn-icon" title="切换状态" onclick="Timeline.toggleStatus(${entry.id}, '${entry.status}')">🔄</button>
                        <button class="btn-icon btn-danger" title="删除" onclick="Timeline.removeEntry(${entry.id})">🗑️</button>
                    </div>
                </div>
            `;
            listEl.appendChild(item);
        });

        // 添加按钮
        const addBtn = document.createElement('div');
        addBtn.className = 'timeline-add';
        addBtn.innerHTML = `<button class="btn btn-primary btn-sm" onclick="Timeline.showAddForm()">+ 添加活动</button>`;
        listEl.appendChild(addBtn);
    },

    showAddForm() {
        App.showEntryModal(null, this.currentDate);
    },

    async editEntry(id) {
        const entry = this.entries.find(e => e.id === id);
        if (entry) App.showEntryModal(entry);
    },

    async toggleStatus(id, current) {
        const next = current === 'completed' ? 'incomplete'
            : current === 'incomplete' ? 'in_progress' : 'completed';
        await API.updateEntry(id, { status: next });
        this.loadDate(this.currentDate);
        if (this.onUpdate) this.onUpdate();
    },

    async removeEntry(id) {
        if (!confirm('确定删除这条记录？')) return;
        await API.deleteEntry(id);
        this.loadDate(this.currentDate);
        if (this.onUpdate) this.onUpdate();
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};
