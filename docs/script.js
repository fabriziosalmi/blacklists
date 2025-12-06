// Modern Professional JavaScript for Domains Blacklist
// Fetches real-time statistics from GitHub API

(function () {
    'use strict';

    // Configuration
    const CONFIG = {
        GITHUB_API: 'https://api.github.com/repos/fabriziosalmi/blacklists',
        STATS_FILE: 'https://raw.githubusercontent.com/fabriziosalmi/blacklists/main/stats/daily_stats.json',
        CACHE_DURATION: 5 * 60 * 1000, // 5 minutes
        FALLBACK_DATA: {
            total_domains: 2943292,
            whitelisted_domains: 2267,
            blacklist_sources: 61
        }
    };

    // Utility Functions
    const utils = {
        formatNumber(num) {
            return new Intl.NumberFormat('en-US').format(num);
        },

        formatDate(dateString) {
            const date = new Date(dateString);
            const now = new Date();
            const diff = now - date;
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));

            if (days === 0) return 'Today';
            if (days === 1) return 'Yesterday';
            if (days < 7) return `${days} days ago`;

            return date.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
            });
        },

        formatTime(dateString) {
            const date = new Date(dateString);
            return date.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            }) + ' UTC';
        },

        async fetchWithCache(url, cacheKey) {
            const cached = localStorage.getItem(cacheKey);
            if (cached) {
                const { data, timestamp } = JSON.parse(cached);
                if (Date.now() - timestamp < CONFIG.CACHE_DURATION) {
                    return data;
                }
            }

            const response = await fetch(url);
            const data = await response.json();

            localStorage.setItem(cacheKey, JSON.stringify({
                data,
                timestamp: Date.now()
            }));

            return data;
        }
    };

    // Statistics Manager
    class StatsManager {
        constructor() {
            this.stats = null;
            this.release = null;
            this.chart = null;
        }

        async init() {
            try {
                await Promise.all([
                    this.fetchStats(),
                    this.fetchRelease()
                ]);
                this.updateUI();
                this.initChart();
            } catch (error) {
                console.error('Failed to load statistics:', error);
                this.useFallbackData();
            }
        }

        async fetchStats() {
            try {
                this.stats = await utils.fetchWithCache(
                    CONFIG.STATS_FILE,
                    'blacklist_stats'
                );
            } catch (error) {
                console.warn('Stats file not available, using fallback');
                this.stats = null;
            }
        }

        async fetchRelease() {
            try {
                this.release = await utils.fetchWithCache(
                    `${CONFIG.GITHUB_API}/releases/latest`,
                    'github_release'
                );
            } catch (error) {
                console.error('Failed to fetch release:', error);
            }
        }

        updateUI() {
            // Get stats data
            const totalDomains = this.stats?.total_domains || CONFIG.FALLBACK_DATA.total_domains;
            const whitelisted = this.stats?.whitelisted_domains || CONFIG.FALLBACK_DATA.whitelisted_domains;
            const sources = this.stats?.blacklist_sources || CONFIG.FALLBACK_DATA.blacklist_sources;

            // Update hero count
            const heroCount = document.getElementById('hero-count');
            if (heroCount) {
                heroCount.textContent = utils.formatNumber(totalDomains);
            }

            // Update stat cards
            this.updateElement('total-domains', utils.formatNumber(totalDomains));
            this.updateElement('sources-count', sources);
            this.updateElement('whitelisted-count', utils.formatNumber(whitelisted));

            // Update daily change
            if (this.stats?.changes?.daily) {
                const change = this.stats.changes.daily;
                const changeEl = document.getElementById('daily-change');
                if (changeEl) {
                    const sign = change.count >= 0 ? '+' : '';
                    changeEl.textContent = `${sign}${utils.formatNumber(change.count)} (${sign}${change.percentage}%) today`;
                    changeEl.className = 'stat-change ' + (change.count >= 0 ? 'positive' : 'negative');
                }
            }

            // Update last update time
            if (this.release) {
                const lastUpdate = document.getElementById('last-update');
                const updateTime = document.getElementById('update-time');

                if (lastUpdate) {
                    lastUpdate.textContent = utils.formatDate(this.release.published_at);
                }
                if (updateTime) {
                    updateTime.textContent = utils.formatTime(this.release.published_at);
                }
            }

            // Update growth stats
            if (this.stats?.changes) {
                const weekly = this.stats.changes.weekly;
                const monthly = this.stats.changes.monthly;

                if (weekly) {
                    const sign = weekly.count >= 0 ? '+' : '';
                    this.updateElement('weekly-growth',
                        `${sign}${utils.formatNumber(weekly.count)} (${sign}${weekly.percentage}%)`
                    );
                }

                if (monthly) {
                    const sign = monthly.count >= 0 ? '+' : '';
                    this.updateElement('monthly-growth',
                        `${sign}${utils.formatNumber(monthly.count)} (${sign}${monthly.percentage}%)`
                    );
                }

                // Calculate average daily
                if (monthly) {
                    const avgDaily = Math.round(monthly.count / 30);
                    this.updateElement('avg-daily', `~${utils.formatNumber(avgDaily)} domains/day`);
                }
            }

            // Update footer stats
            this.updateElement('footer-domains', `${utils.formatNumber(totalDomains)} domains`);
            this.updateElement('footer-sources', `${sources} sources`);
        }

        updateElement(id, value) {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        }

        useFallbackData() {
            this.updateElement('total-domains', utils.formatNumber(CONFIG.FALLBACK_DATA.total_domains));
            this.updateElement('sources-count', CONFIG.FALLBACK_DATA.blacklist_sources);
            this.updateElement('whitelisted-count', utils.formatNumber(CONFIG.FALLBACK_DATA.whitelisted_domains));
            this.updateElement('last-update', 'Recently');
        }

        initChart() {
            const canvas = document.getElementById('trendChart');
            if (!canvas || !window.Chart) return;

            // Generate sample trend data (last 30 days)
            const days = 30;
            const labels = [];
            const data = [];
            const baseValue = this.stats?.total_domains || CONFIG.FALLBACK_DATA.total_domains;
            const dailyGrowth = this.stats?.changes?.monthly?.count
                ? Math.round(this.stats.changes.monthly.count / 30)
                : 1500;

            for (let i = days; i >= 0; i--) {
                const date = new Date();
                date.setDate(date.getDate() - i);
                labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));

                // Simulate growth with some variance
                const variance = Math.random() * dailyGrowth * 0.3;
                const value = baseValue - (i * dailyGrowth) + variance;
                data.push(Math.round(value));
            }

            this.chart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: 'Total Domains',
                        data,
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: '#2563eb',
                        pointHoverBorderColor: '#fff',
                        pointHoverBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: '#1f2937',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            padding: 12,
                            displayColors: false,
                            callbacks: {
                                label: function (context) {
                                    return utils.formatNumber(context.parsed.y) + ' domains';
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            ticks: {
                                callback: function (value) {
                                    return utils.formatNumber(value);
                                }
                            },
                            grid: {
                                color: '#e5e7eb'
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 8
                            }
                        }
                    }
                }
            });
        }
    }

    // Copy to Clipboard
    class ClipboardManager {
        constructor() {
            this.initCopyButtons();
        }

        initCopyButtons() {
            document.querySelectorAll('.copy-btn').forEach(btn => {
                btn.addEventListener('click', () => this.copyToClipboard(btn));
            });
        }

        async copyToClipboard(btn) {
            const targetId = btn.dataset.target;
            const input = document.getElementById(targetId);

            if (!input) return;

            try {
                await navigator.clipboard.writeText(input.value);
                this.showCopied(btn);
            } catch (error) {
                // Fallback for older browsers
                input.select();
                document.execCommand('copy');
                this.showCopied(btn);
            }
        }

        showCopied(btn) {
            const originalText = btn.innerHTML;
            btn.classList.add('copied');
            btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg> Copied!';

            setTimeout(() => {
                btn.classList.remove('copied');
                btn.innerHTML = originalText;
            }, 2000);
        }
    }

    // Smooth Scrolling
    class ScrollManager {
        constructor() {
            this.initSmoothScroll();
            this.initBackToTop();
        }

        initSmoothScroll() {
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', (e) => {
                    const href = anchor.getAttribute('href');
                    if (href === '#') return;

                    e.preventDefault();
                    const target = document.querySelector(href);
                    if (target) {
                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                });
            });
        }

        initBackToTop() {
            const btn = document.getElementById('backToTop');
            if (!btn) return;

            window.addEventListener('scroll', () => {
                if (window.pageYOffset > 300) {
                    btn.classList.add('visible');
                } else {
                    btn.classList.remove('visible');
                }
            });

            btn.addEventListener('click', () => {
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
            });
        }
    }

    // Mobile Menu
    class MobileMenu {
        constructor() {
            this.btn = document.querySelector('.mobile-menu-btn');
            this.menu = document.querySelector('.nav-links');
            this.isOpen = false;

            if (this.btn) {
                this.btn.addEventListener('click', () => this.toggle());
            }
        }

        toggle() {
            this.isOpen = !this.isOpen;
            this.menu.style.display = this.isOpen ? 'flex' : 'none';
            this.btn.classList.toggle('active');
        }
    }

    // Initialize everything when DOM is ready
    function init() {
        const statsManager = new StatsManager();
        statsManager.init();

        new ClipboardManager();
        new ScrollManager();
        new MobileMenu();

        // Add loading animation
        document.body.classList.add('loaded');
    }

    // Wait for DOM and Chart.js to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();