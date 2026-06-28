document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    const toggle = document.querySelector('.menu-toggle');

    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            overlay?.classList.toggle('show');
        });
    }

    if (overlay && sidebar) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('show');
        });
    }

    document.querySelectorAll('.score-bar-fill[data-width]').forEach(bar => {
        const width = bar.getAttribute('data-width');
        if (width !== null) bar.style.width = width + '%';
    });

    if (document.querySelector('[data-live-stats]')) {
        refreshLiveStats();
        setInterval(refreshLiveStats, 8000);
    }
});

function switchTab(event, tabId) {
    const container = event.currentTarget.closest('.panel, .leaderboard-section, .container');
    const scope = container || document;

    scope.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    scope.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

    const target = document.getElementById(tabId + '-tab');
    if (target) target.classList.add('active');
    event.currentTarget.classList.add('active');
}

function showToast(message) {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-msg');
    if (!toast || !toastMsg) return;

    toastMsg.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function copyText(text, label = 'Copied') {
    navigator.clipboard.writeText(text).then(() => {
        showToast(`${label} copied to clipboard`);
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast(`${label} copied to clipboard`);
    });
}

async function refreshLiveStats() {
    try {
        const res = await fetch('/api/live_stats');
        if (!res.ok) return;
        const data = await res.json();

        document.querySelectorAll('[data-stat]').forEach(el => {
            const key = el.getAttribute('data-stat');
            if (data[key] !== undefined) {
                el.textContent = data[key];
                el.classList.add('stat-updated');
                setTimeout(() => el.classList.remove('stat-updated'), 600);
            }
        });

        if (window.scoreDistChart && data.score_distribution) {
            window.scoreDistChart.data.datasets[0].data = [
                data.score_distribution['0-20%'],
                data.score_distribution['21-40%'],
                data.score_distribution['41-60%'],
                data.score_distribution['61-80%'],
                data.score_distribution['81-100%'],
            ];
            window.scoreDistChart.update('none');
        }
    } catch (e) { /* ignore */ }
}
