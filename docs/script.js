// Domains Blacklist - site behaviour.
//
// Every number rendered here comes from data/*.json, which is generated at
// build time from the blacklist artifact that users actually download. There is
// no hardcoded fallback data: when a fetch fails the page says so instead of
// showing a plausible number that happens to be wrong.

(function () {
    'use strict';

    const CONFIG = {
        STATS: 'data/stats.json',
        HISTORY: 'data/history.json',
        SOURCES: 'data/sources.json',
        QUALITY: 'data/quality.json',
        INDEX: 'data/index.json',
        SHARDS: 'data/shards',
        DEFAULT_TREND_DAYS: 90
    };

    const utils = {
        formatNumber(num) {
            return new Intl.NumberFormat('en-US').format(num);
        },

        formatCompact(num) {
            if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
            if (num >= 1e3) return (num / 1e3).toFixed(1) + 'k';
            return String(num);
        },

        formatBytes(bytes) {
            if (!bytes) return '…';
            const mb = bytes / (1024 * 1024);
            return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
        },

        formatSigned(count, percentage) {
            const sign = count >= 0 ? '+' : '';
            const pct = (percentage === null || percentage === undefined)
                ? '' : ` (${sign}${percentage}%)`;
            return `${sign}${utils.formatNumber(count)}${pct}`;
        },

        // Dates are rendered relative to the viewer's clock but always show the
        // absolute UTC timestamp too, so "2 days ago" can never be the only
        // claim about freshness.
        formatRelative(dateString) {
            if (!dateString) return 'unknown';
            const date = new Date(dateString);
            if (isNaN(date)) return 'unknown';

            const days = Math.floor((Date.now() - date) / 86400000);
            if (days <= 0) return 'today';
            if (days === 1) return 'yesterday';
            if (days < 30) return `${days} days ago`;
            return date.toISOString().slice(0, 10);
        },

        formatUTC(dateString) {
            if (!dateString) return 'unknown';
            const date = new Date(dateString);
            if (isNaN(date)) return 'unknown';
            return date.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
        },

        async fetchJSON(url) {
            const response = await fetch(url, { cache: 'no-cache' });
            if (!response.ok) {
                throw new Error(`${url} responded ${response.status}`);
            }
            return response.json();
        },

        setText(id, value) {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        },

        // A single place that marks a value as unavailable, so a failed fetch
        // always looks like a failure and never like data.
        setUnavailable(id, label) {
            const el = document.getElementById(id);
            if (!el) return;
            el.textContent = label || 'unavailable';
            el.classList.add('value-unavailable');
        }
    };

    class StatsManager {
        constructor() {
            this.stats = null;
            this.history = null;
            this.chart = null;
            this.trendDays = CONFIG.DEFAULT_TREND_DAYS;
        }

        async init() {
            const [stats, history] = await Promise.allSettled([
                utils.fetchJSON(CONFIG.STATS),
                utils.fetchJSON(CONFIG.HISTORY)
            ]);

            if (stats.status === 'fulfilled') {
                this.stats = stats.value;
                this.renderStats();
            } else {
                console.error('Failed to load statistics:', stats.reason);
                this.renderUnavailable();
            }

            if (history.status === 'fulfilled') {
                this.history = history.value;
                this.initTrendControls();
                this.renderChart();
            } else {
                console.error('Failed to load history:', history.reason);
                this.renderChartUnavailable('Historical data could not be loaded.');
            }
        }

        renderStats() {
            const s = this.stats;

            utils.setText('hero-count', utils.formatNumber(s.total_domains));
            utils.setText('hero-sources', s.blacklist_sources);
            utils.setText('total-domains', utils.formatNumber(s.total_domains));
            utils.setText('sources-count', s.blacklist_sources);
            utils.setText('whitelisted-count', utils.formatNumber(s.whitelisted_domains));

            const daily = s.changes && s.changes.daily;
            const changeEl = document.getElementById('daily-change');
            if (changeEl) {
                if (daily && typeof daily.count === 'number') {
                    changeEl.textContent = `${utils.formatSigned(daily.count, daily.percentage)} vs yesterday`;
                    changeEl.className = 'stat-change ' + (daily.count >= 0 ? 'positive' : 'negative');
                } else {
                    changeEl.textContent = 'no comparison available';
                    changeEl.className = 'stat-change';
                }
            }

            // Most whitelist entries match nothing on a given day and are
            // standing by, so the raw count alone overstates how much is
            // actively being held back.
            if (s.whitelist && typeof s.whitelist.active === 'number') {
                utils.setText('whitelist-active',
                    `${utils.formatNumber(s.whitelist.active)} holding back a source today`);
            }

            this.renderClassified(s);

            const published = s.release && s.release.published_at;
            utils.setText('last-update', utils.formatRelative(published));
            utils.setText('update-time', utils.formatUTC(published));

            const weekly = s.changes && s.changes.weekly;
            const monthly = s.changes && s.changes.monthly;

            if (weekly) {
                utils.setText('weekly-growth', utils.formatSigned(weekly.count, weekly.percentage));
            } else {
                utils.setUnavailable('weekly-growth', 'not enough history');
            }

            if (monthly) {
                utils.setText('monthly-growth', utils.formatSigned(monthly.count, monthly.percentage));
                utils.setText('avg-daily', `${utils.formatSigned(Math.round(monthly.count / 30))} domains/day`);
            } else {
                utils.setUnavailable('monthly-growth', 'not enough history');
                utils.setUnavailable('avg-daily', 'not enough history');
            }

            utils.setText('footer-domains', `${utils.formatNumber(s.total_domains)} domains`);
            utils.setText('footer-sources', `${s.blacklist_sources} sources`);

            this.renderProvenance();
        }

        // Categories the list blocks that no upstream source declares, so the
        // source-derived table cannot show them. Adult content is the reason
        // this exists: it went undeclared for as long as the site did.
        renderClassified(s) {
            const section = document.getElementById('classified');
            const bands = document.getElementById('classified-bands');
            const entries = s.classified_categories || [];
            if (!section || !bands || !entries.length) return;

            bands.innerHTML = '';
            entries.forEach(entry => {
                const cell = document.createElement('div');
                cell.className = 'quality-band';

                const value = document.createElement('div');
                value.className = 'quality-band-value';
                value.textContent = utils.formatNumber(entry.domains);

                const caption = document.createElement('div');
                caption.className = 'quality-band-label';
                caption.textContent = `${entry.category} (${entry.percent}% of the list)`;

                cell.append(value, caption);
                bands.appendChild(cell);
            });

            section.hidden = false;
        }

        renderProvenance() {
            const s = this.stats;
            const release = s.release || {};

            utils.setText('prov-built', utils.formatUTC(s.generated_at));
            utils.setText('prov-release', utils.formatUTC(release.published_at));
            utils.setText('prov-size', utils.formatBytes(release.blacklist_bytes));
            utils.setText('prov-domains', utils.formatNumber(s.total_domains));

            const digest = document.getElementById('prov-sha256');
            if (digest) digest.textContent = release.blacklist_sha256 || 'unavailable';

            const runLink = document.getElementById('prov-run');
            if (runLink && s.build && s.build.run_url) {
                runLink.href = s.build.run_url;
                runLink.textContent = 'view build log';
            } else if (runLink) {
                runLink.replaceWith(document.createTextNode('unavailable'));
            }
        }

        renderUnavailable() {
            ['total-domains', 'sources-count', 'whitelisted-count', 'last-update',
             'weekly-growth', 'monthly-growth', 'avg-daily'].forEach(id => {
                utils.setUnavailable(id);
            });
            utils.setText('hero-count', '…');
            utils.setText('update-time', '');

            const banner = document.getElementById('data-error');
            if (banner) {
                banner.hidden = false;
                banner.textContent =
                    'Statistics could not be loaded. Nothing is shown rather than showing stale numbers.';
            }
        }

        initTrendControls() {
            document.querySelectorAll('[data-trend-days]').forEach(btn => {
                btn.addEventListener('click', () => {
                    this.trendDays = Number(btn.dataset.trendDays);
                    document.querySelectorAll('[data-trend-days]').forEach(other => {
                        other.classList.toggle('active', other === btn);
                    });
                    this.renderChart();
                });
            });
        }

        renderChartUnavailable(message) {
            const container = document.getElementById('chart-status');
            if (container) {
                container.hidden = false;
                container.textContent = message;
            }
            const canvas = document.getElementById('trendChart');
            if (canvas) canvas.hidden = true;
        }

        renderChart() {
            const canvas = document.getElementById('trendChart');
            if (!canvas || !window.Chart) return;

            const series = (this.history || []).slice(-this.trendDays);

            // Two points is the minimum that can honestly be called a trend.
            if (series.length < 2) {
                this.renderChartUnavailable(
                    `Only ${series.length} day(s) of history recorded so far - not enough to plot a trend.`
                );
                return;
            }

            const status = document.getElementById('chart-status');
            if (status) status.hidden = true;
            canvas.hidden = false;

            const labels = series.map(p => p.date);
            const values = series.map(p => p.total_domains);

            const styles = getComputedStyle(document.documentElement);
            const grid = styles.getPropertyValue('--chart-grid').trim() || '#e5e7eb';
            const line = styles.getPropertyValue('--chart-line').trim() || '#2563eb';

            if (this.chart) this.chart.destroy();

            this.chart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: 'Total domains',
                        data: values,
                        borderColor: line,
                        backgroundColor: 'rgba(37, 99, 235, 0.10)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.25,
                        pointRadius: series.length > 45 ? 0 : 2,
                        pointHoverRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    interaction: { intersect: false, mode: 'index' },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: ctx => `${utils.formatNumber(ctx.parsed.y)} domains`
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            ticks: { callback: v => utils.formatCompact(v) },
                            grid: { color: grid }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }
                        }
                    }
                }
            });

            const caption = document.getElementById('chart-caption');
            if (caption) {
                caption.textContent =
                    `${series.length} daily measurements, ${labels[0]} to ${labels[labels.length - 1]}.`;
            }
        }
    }

    // Renders the upstream lists this project aggregates, with the licence each
    // one is redistributed under. Unverified licences are labelled as such.
    class SourcesManager {
        constructor() {
            this.tbody = document.getElementById('sources-body');
            this.data = null;
        }

        async init() {
            if (!this.tbody) return;

            try {
                this.data = await utils.fetchJSON(CONFIG.SOURCES);
            } catch (error) {
                console.error('Failed to load sources:', error);
                this.tbody.innerHTML =
                    '<tr><td colspan="5" class="value-unavailable">Source list could not be loaded.</td></tr>';
                // The category breakdown comes from the same document, so it is
                // unavailable too and must not be left saying "Loading...".
                const body = document.getElementById('categories-body');
                if (body) {
                    body.innerHTML =
                        '<tr><td colspan="3" class="value-unavailable">Category breakdown could not be loaded.</td></tr>';
                }
                return;
            }

            this.render();
        }

        licenseCell(license) {
            const cell = document.createElement('td');
            if (!license) {
                cell.textContent = 'unknown';
                cell.className = 'license-unknown';
                return cell;
            }

            const label = license.spdx || license.name || 'unknown';

            if (license.url) {
                const link = document.createElement('a');
                link.href = license.url;
                link.target = '_blank';
                link.rel = 'noopener';
                link.textContent = label;
                cell.appendChild(link);
            } else {
                cell.appendChild(document.createTextNode(label));
            }

            if (!license.verified) {
                cell.classList.add('license-unknown');
                const flag = document.createElement('span');
                flag.className = 'license-flag';
                flag.textContent = 'unverified';
                flag.title = license.note || 'No licence statement found at the source.';
                cell.appendChild(document.createTextNode(' '));
                cell.appendChild(flag);
            }

            return cell;
        }

        // What a reader is actually installing, split by what each category
        // supplied and by what would be lost without it.
        renderCategories() {
            const body = document.getElementById('categories-body');
            const status = document.getElementById('categories-status');
            if (!body) return;

            const categories = this.data.categories || [];
            body.innerHTML = '';

            if (!categories.length) {
                if (status) {
                    status.hidden = false;
                    status.textContent =
                        'The category breakdown is produced by the release pipeline and has not run yet.';
                }
                return;
            }

            categories.forEach(entry => {
                const row = document.createElement('tr');

                const name = document.createElement('td');
                const tag = document.createElement('span');
                tag.className = 'category-tag';
                tag.textContent = entry.category;
                name.appendChild(tag);

                const domains = document.createElement('td');
                domains.className = 'numeric';
                domains.textContent = utils.formatNumber(entry.domains);

                const exclusive = document.createElement('td');
                exclusive.className = 'numeric';
                exclusive.textContent = utils.formatNumber(entry.exclusive);

                row.append(name, domains, exclusive);
                body.appendChild(row);
            });
        }

        render() {
            this.renderCategories();

            const sources = this.data.sources || [];
            this.tbody.innerHTML = '';

            sources.forEach(source => {
                const row = document.createElement('tr');

                const nameCell = document.createElement('td');
                const link = document.createElement('a');
                link.href = source.homepage;
                link.target = '_blank';
                link.rel = 'noopener';
                link.textContent = source.name;
                nameCell.appendChild(link);

                const project = document.createElement('div');
                project.className = 'source-project';
                project.textContent = source.maintainer;
                nameCell.appendChild(project);

                if (source.mirror_of) {
                    const mirror = document.createElement('div');
                    mirror.className = 'source-mirror';
                    mirror.textContent = `re-published via ${source.mirror_of.name}`;
                    nameCell.appendChild(mirror);
                }
                row.appendChild(nameCell);

                const catCell = document.createElement('td');
                (source.categories || []).forEach(category => {
                    const tag = document.createElement('span');
                    tag.className = 'category-tag';
                    tag.textContent = category;
                    catCell.appendChild(tag);
                });
                row.appendChild(catCell);

                row.appendChild(this.licenseCell(source.license));

                const metrics = source.metrics;

                const domainsCell = document.createElement('td');
                domainsCell.className = 'numeric';
                if (metrics && typeof metrics.domains === 'number') {
                    domainsCell.textContent = utils.formatNumber(metrics.domains);
                } else {
                    domainsCell.textContent = '…';
                    domainsCell.classList.add('value-unavailable');
                }
                row.appendChild(domainsCell);

                const statusCell = document.createElement('td');
                if (metrics) {
                    const ok = metrics.ok;
                    const badge = document.createElement('span');
                    badge.className = 'status-badge ' + (ok ? 'status-ok' : 'status-fail');
                    badge.textContent = ok ? `HTTP ${metrics.http_status}` : (metrics.error || `HTTP ${metrics.http_status}`);
                    statusCell.appendChild(badge);
                } else {
                    statusCell.textContent = 'not measured yet';
                    statusCell.classList.add('value-unavailable');
                }
                row.appendChild(statusCell);

                if (source.notes) {
                    row.title = source.notes;
                    row.classList.add('has-note');
                }

                this.tbody.appendChild(row);
            });

            const summary = document.getElementById('sources-summary');
            if (summary) {
                const verified = sources.filter(s => s.license && s.license.verified).length;
                const parts = [`${sources.length} upstream lists`, `${verified} with a verified licence`];
                if (this.data.measured) {
                    const failing = sources.filter(s => s.metrics && !s.metrics.ok).length;
                    parts.push(failing ? `${failing} failing` : 'all fetching cleanly');
                } else {
                    parts.push('per-source metrics pending first pipeline run');
                }
                summary.textContent = parts.join(' · ');
            }
        }
    }

    // Renders the popularity cross-check: which widely-used domains this list
    // blocks, and which source supplied each one. Published rather than hidden
    // because most of these blocks are deliberate, and the ones that are not
    // should be easy for anyone to spot and report.
    class QualityManager {
        constructor() {
            this.body = document.getElementById('quality-body');
            this.bands = document.getElementById('quality-bands');
            this.status = document.getElementById('quality-status');
        }

        async init() {
            if (!this.body) return;

            let data;
            try {
                data = await utils.fetchJSON(CONFIG.QUALITY);
            } catch (error) {
                console.error('Failed to load quality report:', error);
                this.body.innerHTML = '';
                if (this.status) {
                    this.status.hidden = false;
                    this.status.textContent =
                        'No cross-check has been published yet. It is produced by the release pipeline.';
                }
                return;
            }

            this.renderBands(data);
            this.renderTable(data);
        }

        renderBands(data) {
            if (!this.bands) return;

            const counts = (data.popularity && data.popularity.blocked_in_band) || {};
            const labels = [
                ['top_1000', 'of the top 1,000'],
                ['top_10000', 'of the top 10,000'],
                ['top_100000', 'of the top 100,000'],
                ['top_1000000', 'of the top 1,000,000']
            ];

            this.bands.innerHTML = '';
            labels.forEach(([key, label]) => {
                if (typeof counts[key] !== 'number') return;

                const cell = document.createElement('div');
                cell.className = 'quality-band';

                const value = document.createElement('div');
                value.className = 'quality-band-value';
                value.textContent = utils.formatNumber(counts[key]);

                const caption = document.createElement('div');
                caption.className = 'quality-band-label';
                caption.textContent = label;

                cell.append(value, caption);
                this.bands.appendChild(cell);
            });
        }

        renderTable(data) {
            const entries = (data.popularity && data.popularity.most_popular_blocked) || [];
            this.body.innerHTML = '';

            if (!entries.length) {
                const row = document.createElement('tr');
                const cell = document.createElement('td');
                cell.colSpan = 3;
                cell.textContent = 'No blocked domain appears in the ranking.';
                row.appendChild(cell);
                this.body.appendChild(row);
                return;
            }

            entries.forEach(entry => {
                const row = document.createElement('tr');

                const rank = document.createElement('td');
                rank.className = 'numeric';
                rank.textContent = `#${utils.formatNumber(entry.rank)}`;

                const domain = document.createElement('td');
                domain.textContent = entry.domain;

                const sources = document.createElement('td');
                if (entry.sources && entry.sources.length) {
                    sources.textContent = entry.sources.join(', ');
                } else {
                    sources.textContent = 'not recorded';
                    sources.classList.add('value-unavailable');
                }

                row.append(rank, domain, sources);
                this.body.appendChild(row);
            });
        }
    }

    // Domain lookup against the static sharded index.
    //
    // The index is a set of files named after the first N hex characters of the
    // SHA-256 of each domain. Checking a domain means hashing it locally and
    // fetching exactly one shard (~25 KB) instead of the 100 MB blacklist. The
    // answer is exact - there are no false positives.
    class DomainSearchManager {
        constructor() {
            this.searchBtn = document.getElementById('searchBtn');
            this.domainInput = document.getElementById('domainInput');
            this.searchResult = document.getElementById('searchResult');
            this.manifest = null;
            this.shardCache = new Map();

            this.init();
        }

        init() {
            if (!this.searchBtn || !this.domainInput) return;

            this.searchBtn.addEventListener('click', () => this.search());
            this.domainInput.addEventListener('keypress', e => {
                if (e.key === 'Enter') this.search();
            });
        }

        async loadManifest() {
            if (!this.manifest) {
                this.manifest = await utils.fetchJSON(CONFIG.INDEX);
            }
            return this.manifest;
        }

        async sha256(text) {
            const digest = await crypto.subtle.digest(
                'SHA-256', new TextEncoder().encode(text)
            );
            return Array.from(new Uint8Array(digest))
                .map(b => b.toString(16).padStart(2, '0'))
                .join('');
        }

        async loadShard(name) {
            if (this.shardCache.has(name)) return this.shardCache.get(name);

            const response = await fetch(`${CONFIG.SHARDS}/${name}.txt`);
            if (!response.ok) throw new Error(`shard ${name} responded ${response.status}`);

            const text = await response.text();
            const set = new Set(text.split('\n').filter(Boolean));
            this.shardCache.set(name, set);
            return set;
        }

        async isListed(domain) {
            const manifest = await this.loadManifest();
            const digest = await this.sha256(domain);
            const shard = await this.loadShard(digest.slice(0, manifest.prefix_length));
            return shard.has(domain);
        }

        // A domain can be blocked because a parent domain is listed, so report
        // that explicitly instead of answering "not listed" and being useless.
        parentDomains(domain) {
            const labels = domain.split('.');
            const parents = [];
            for (let i = 1; i <= labels.length - 2; i++) {
                parents.push(labels.slice(i).join('.'));
            }
            return parents;
        }

        async search() {
            const domain = this.domainInput.value.trim().toLowerCase().replace(/\.$/, '');

            if (!domain) {
                this.showResult('Enter a domain name to check.', 'error');
                return;
            }
            if (!/^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$/.test(domain)) {
                this.showResult('That does not look like a domain. Example: example.com', 'error');
                return;
            }
            if (!crypto.subtle) {
                this.showResult('This browser cannot compute SHA-256, so lookups are unavailable.', 'error');
                return;
            }

            this.showResult('Checking...', 'loading');
            this.searchBtn.disabled = true;

            try {
                if (await this.isListed(domain)) {
                    this.showResult(`${domain} is in the blacklist.`, 'found');
                    return;
                }

                for (const parent of this.parentDomains(domain)) {
                    if (await this.isListed(parent)) {
                        this.showResult(
                            `${domain} is not listed itself, but its parent domain ${parent} is. ` +
                            `DNS-level blockers that match subdomains will block it.`,
                            'found-parent'
                        );
                        return;
                    }
                }

                this.showResult(
                    `${domain} is not in this blacklist. That is not a safety verdict - ` +
                    `it only means no configured source reported it.`,
                    'not-found'
                );
            } catch (error) {
                console.error('Lookup failed:', error);
                this.showResult('The lookup index could not be reached. Try again later.', 'error');
            } finally {
                this.searchBtn.disabled = false;
            }
        }

        showResult(message, type) {
            if (!this.searchResult) return;
            this.searchResult.textContent = message;
            this.searchResult.className = `search-result ${type}`;
        }
    }

    class ClipboardManager {
        constructor() {
            document.querySelectorAll('.copy-btn').forEach(btn => {
                btn.addEventListener('click', () => this.copy(btn));
            });
        }

        async copy(btn) {
            const el = document.getElementById(btn.dataset.target);
            if (!el) return;
            const text = el.value !== undefined ? el.value : el.textContent;

            try {
                await navigator.clipboard.writeText(text);
            } catch (error) {
                if (typeof el.select === 'function') {
                    el.select();
                } else {
                    const range = document.createRange();
                    range.selectNodeContents(el);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                }
                document.execCommand('copy');
            }
            this.showCopied(btn);
        }

        showCopied(btn) {
            const original = btn.innerHTML;
            btn.classList.add('copied');
            btn.innerHTML = 'Copied';
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.innerHTML = original;
            }, 2000);
        }
    }

    class ScrollManager {
        constructor() {
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', e => {
                    const href = anchor.getAttribute('href');
                    if (href === '#') return;
                    const target = document.querySelector(href);
                    if (!target) return;
                    e.preventDefault();
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                });
            });

            this.backToTop = document.getElementById('backToTop');
            if (this.backToTop) {
                window.addEventListener('scroll', () => {
                    this.backToTop.classList.toggle('visible', window.pageYOffset > 300);
                }, { passive: true });
                this.backToTop.addEventListener('click', () => {
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                });
            }
        }
    }

    class MobileMenu {
        constructor() {
            this.btn = document.querySelector('.mobile-menu-btn');
            this.menu = document.querySelector('.nav-links');
            this.isOpen = false;

            if (this.btn) this.btn.addEventListener('click', () => this.toggle());
        }

        toggle() {
            this.isOpen = !this.isOpen;
            this.menu.style.display = this.isOpen ? 'flex' : '';
            this.btn.classList.toggle('active', this.isOpen);
            this.btn.setAttribute('aria-expanded', String(this.isOpen));
        }
    }

    // The theme follows the operating system preference and nothing else: there
    // is no toggle and no stored override. It is applied on load and kept in
    // sync live if the viewer switches their system between light and dark.
    class AutoThemeManager {
        constructor() {
            const query = window.matchMedia &&
                window.matchMedia('(prefers-color-scheme: dark)');

            this.apply(query ? query.matches : false);

            if (query) {
                const onChange = e => this.apply(e.matches);
                if (query.addEventListener) {
                    query.addEventListener('change', onChange);
                } else if (query.addListener) {
                    query.addListener(onChange);
                }
            }
        }

        apply(prefersDark) {
            document.documentElement.setAttribute(
                'data-theme', prefersDark ? 'dark' : 'light'
            );
        }
    }

    // Keeps long tables short until the reader asks for the rest. Given a tbody
    // and a threshold, it hides every row past the threshold and injects a
    // toggle button that reveals or re-hides them. Tables at or under the
    // threshold get no button. Safe to call repeatedly: any button it added on a
    // previous pass is removed first.
    function makeCollapsible(tbody, threshold) {
        if (!tbody) return;

        const wrapper = tbody.closest('.table-scroll') || tbody.parentElement;
        if (wrapper) {
            const existing = wrapper.parentElement &&
                wrapper.parentElement.querySelector(':scope > .show-all-btn');
            if (existing) existing.remove();
        }

        const rows = Array.from(tbody.querySelectorAll(':scope > tr'));
        const hideable = rows.filter(r => !r.querySelector('[colspan]'));
        if (hideable.length <= threshold) return;

        const hidden = hideable.slice(threshold);
        const setHidden = state => hidden.forEach(r => { r.hidden = state; });
        setHidden(true);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'show-all-btn';
        let expanded = false;
        const label = () => {
            btn.textContent = expanded ? 'Show fewer' : `Show all (${hideable.length})`;
            btn.setAttribute('aria-expanded', String(expanded));
        };
        label();

        btn.addEventListener('click', () => {
            expanded = !expanded;
            setHidden(!expanded);
            label();
        });

        if (wrapper && wrapper.parentElement) {
            wrapper.insertAdjacentElement('afterend', btn);
        }
    }

    function collapseLongTables() {
        makeCollapsible(document.getElementById('sources-body'), 10);
        makeCollapsible(document.getElementById('categories-body'), 10);
        makeCollapsible(document.getElementById('quality-body'), 10);
    }

    function init() {
        new StatsManager().init();
        // The source, category and quality tables are rendered asynchronously;
        // collapse them once their managers have populated the DOM.
        Promise.allSettled([
            new SourcesManager().init(),
            new QualityManager().init()
        ]).then(collapseLongTables);
        new DomainSearchManager();
        new ClipboardManager();
        new ScrollManager();
        new MobileMenu();
        new AutoThemeManager();

        const year = document.getElementById('footer-year');
        if (year) year.textContent = String(new Date().getFullYear());

        document.body.classList.add('loaded');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
