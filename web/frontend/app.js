/* ─── State ─────────────────────────────────── */
const API = '';
let token = localStorage.getItem('token') || '';
let userRole = localStorage.getItem('role') || '';
let userName = localStorage.getItem('fullname') || '';
let currentPage = 1;
const PAGE_SIZE = 20;
let chartDay = null, chartType = null, chartVehicle = null;
let currentReviewMode = false;

/* ─── Nav config by role (no icons) ─────────── */
const NAV = {
  admin: [
    { id: 'dashboard', label: 'Dashboard', marker: '01' },
    { id: 'cameras', label: 'Quan ly Camera', marker: '02' },
    { id: 'violations', label: 'Tat ca Vi pham', marker: '03' },
    { id: 'review', label: 'Kiem duyet', marker: '04' },
  ],
  reviewer: [
    { id: 'review', label: 'Kiem duyet', marker: '01' },
    { id: 'violations', label: 'Vi pham', marker: '02' },
  ],
};

const PAGE_TITLES = {
  dashboard: 'Dashboard',
  cameras: 'Quan ly Camera',
  violations: 'Danh sach Vi pham',
  review: 'Kiem duyet Vi pham',
};

/* ─── Utils ─────────────────────────────────── */
const $ = id => document.getElementById(id);

function api(path, opts = {}) {
  return fetch(API + path, {
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  }).then(async r => {
    if (r.status === 401) { logout(); return; }
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || r.statusText); }
    return r.json();
  });
}

function toast(msg, type = 'info') {
  let c = $('toast-container');
  if (!c) { c = document.createElement('div'); c.id = 'toast-container'; document.body.appendChild(c); }
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const prefix = type === 'success' ? '[OK]' : type === 'error' ? '[ERR]' : '[INFO]';
  t.innerHTML = `<span>${prefix}</span><span>${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

function fmtDate(s) {
  if (!s) return '—';
  const d = new Date(s);
  if (isNaN(d)) return s;
  return d.toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function statusBadge(s) {
  if (s === 1) return '<span class="badge approved">Da duyet</span>';
  if (s === -1) return '<span class="badge rejected">Tu choi</span>';
  return '<span class="badge pending">Cho duyet</span>';
}

function violationLabel(code) {
  const map = {
    DI_SAI_LAN: 'Di sai lan',
    DI_NGUOC_CHIEU: 'Di nguoc chieu',
    DE_VACH_PHAN_LAN: 'De vach phan lan',
    VUOT_DEN_DO: 'Vuot den do',
    WRONG_LANE: 'Sai lan',
    WRONG_WAY: 'Nguoc chieu',
    LINE_CROSSING: 'Vuot vach',
  };
  return map[code] || code;
}

/* ─── Clock ─────────────────────────────────── */
function startClock() {
  const el = $('topbar-time');
  const tick = () => { if (el) el.textContent = new Date().toLocaleTimeString('vi-VN'); };
  tick(); setInterval(tick, 1000);
}

/* ─── Auth ──────────────────────────────────── */
async function doLogin(e) {
  e.preventDefault();
  const u = $('login-username').value.trim();
  const p = $('login-password').value;
  const btn = $('login-btn');
  const errEl = $('login-error');
  errEl.classList.add('hidden');
  $('login-btn-text').textContent = 'Dang dang nhap...';
  $('login-spinner').classList.remove('hidden');
  btn.disabled = true;

  try {
    const form = new URLSearchParams();
    form.append('username', u);
    form.append('password', p);
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Dang nhap that bai');

    token = data.access_token;
    userRole = data.role;
    userName = data.full_name;
    localStorage.setItem('token', token);
    localStorage.setItem('role', userRole);
    localStorage.setItem('fullname', userName);
    enterApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    $('login-btn-text').textContent = 'Dang nhap';
    $('login-spinner').classList.add('hidden');
    btn.disabled = false;
  }
}

function logout() {
  localStorage.clear();
  token = ''; userRole = ''; userName = '';
  $('app').classList.add('hidden');
  $('login-screen').classList.remove('hidden');
}

/* ─── App Boot ──────────────────────────────── */
function enterApp() {
  $('login-screen').classList.add('hidden');
  $('app').classList.remove('hidden');
  buildSidebar();
  updateUserCard();
  startClock();
  const defaultPage = userRole === 'admin' ? 'dashboard' : 'review';
  navigate(defaultPage);
}

function buildSidebar() {
  const nav = $('sidebar-nav');
  nav.innerHTML = '';

  const label = document.createElement('div');
  label.className = 'nav-section-label';
  label.textContent = 'Navigation';
  nav.appendChild(label);

  (NAV[userRole] || NAV.reviewer).forEach(item => {
    const el = document.createElement('div');
    el.className = 'nav-item';
    el.dataset.page = item.id;
    el.innerHTML = `<span class="nav-marker">${item.marker}</span><span class="nav-label">${item.label}</span>`;
    el.addEventListener('click', () => navigate(item.id));
    nav.appendChild(el);
  });
}

function updateUserCard() {
  $('user-name').textContent = userName;
  $('user-avatar').textContent = userName.charAt(0).toUpperCase();
  const badge = $('user-role-badge');
  badge.textContent = userRole === 'admin' ? 'ADMIN' : 'REVIEWER';
  badge.className = `user-role-badge ${userRole !== 'admin' ? 'reviewer' : ''}`;
}

function setActiveNav(pageId) {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === pageId);
  });
}

/* ─── Router ────────────────────────────────── */
function navigate(pageId) {
  setActiveNav(pageId);
  $('page-title').textContent = PAGE_TITLES[pageId] || pageId;
  const area = $('content-area');
  area.innerHTML = '';
  currentPage = 1;
  ({
    dashboard: renderDashboard,
    cameras: renderCameras,
    violations: () => renderViolationsPage(false),
    review: () => renderViolationsPage(true),
  }[pageId] || (() => { }))();
}

/* ══════════════════ DASHBOARD PAGE ════════════════════ */
async function renderDashboard() {
  const area = $('content-area');
  area.innerHTML = `
    <div class="stats-grid" id="stats-grid">
      ${[1, 2, 3, 4].map(() => `<div class="stat-card"><div class="skeleton" style="width:100%;height:70px;"></div></div>`).join('')}
    </div>
    <div class="charts-grid">
      <div class="chart-card full">
        <div class="chart-header">
          <span class="chart-title">Vi pham theo ngay</span>
          <span class="chart-sub">7 ngay gan nhat</span>
        </div>
        <div class="chart-wrap"><canvas id="chart-day"></canvas></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><span class="chart-title">Phan loai vi pham</span></div>
        <div class="chart-wrap"><canvas id="chart-type"></canvas></div>
      </div>
      <div class="chart-card">
        <div class="chart-header"><span class="chart-title">Phuong tien vi pham</span></div>
        <div class="chart-wrap"><canvas id="chart-vehicle"></canvas></div>
      </div>
    </div>`;

  try {
    const [overview, byDay, byType, byVehicle] = await Promise.all([
      api('/api/stats/overview'),
      api('/api/stats/by-day?days=7'),
      api('/api/stats/by-type'),
      api('/api/stats/by-vehicle'),
    ]);

    $('stats-grid').innerHTML = `
      <div class="stat-card">
        <div class="stat-label">Tong vi pham</div>
        <div class="stat-value">${overview.total_violations}</div>
        <div class="stat-sub">Tat ca ban ghi</div>
      </div>
      <div class="stat-card pending">
        <div class="stat-label">Cho duyet</div>
        <div class="stat-value">${overview.pending}</div>
        <div class="stat-sub">Can xu ly</div>
      </div>
      <div class="stat-card approved">
        <div class="stat-label">Da duyet</div>
        <div class="stat-value">${overview.approved}</div>
        <div class="stat-sub">Da xu ly</div>
      </div>
      <div class="stat-card cameras">
        <div class="stat-label">Camera</div>
        <div class="stat-value">${overview.total_cameras}</div>
        <div class="stat-sub">Dang hoat dong</div>
      </div>`;

    /* Chart defaults — classic muted style */
    Chart.defaults.color = '#555e7a';
    Chart.defaults.font = { family: 'Inter', size: 11 };

    if (chartDay) chartDay.destroy();
    chartDay = new Chart($('chart-day'), {
      type: 'bar',
      data: {
        labels: byDay.labels,
        datasets: [{
          label: 'Vi pham',
          data: byDay.counts,
          backgroundColor: 'rgba(74,124,247,0.55)',
          borderColor: '#4a7cf7',
          borderWidth: 1,
          borderRadius: 2,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(44,49,72,0.8)' }, border: { color: '#2c3148' } },
          y: { beginAtZero: true, grid: { color: 'rgba(44,49,72,0.8)' }, border: { color: '#2c3148' }, ticks: { stepSize: 1 } }
        }
      }
    });

    const PIE_COLORS = ['#4a7cf7', '#d4a017', '#3dba6f', '#d94f4f', '#7aa3ff', '#8b92aa', '#555e7a', '#2c3148'];

    if (chartType) chartType.destroy();
    chartType = new Chart($('chart-type'), {
      type: 'doughnut',
      data: {
        labels: byType.labels.map(violationLabel),
        datasets: [{
          data: byType.counts,
          backgroundColor: PIE_COLORS,
          borderWidth: 1,
          borderColor: '#1e2230',
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { padding: 10, boxWidth: 10, font: { size: 11 } } } }
      }
    });

    if (chartVehicle) chartVehicle.destroy();
    chartVehicle = new Chart($('chart-vehicle'), {
      type: 'doughnut',
      data: {
        labels: byVehicle.labels,
        datasets: [{
          data: byVehicle.counts,
          backgroundColor: PIE_COLORS,
          borderWidth: 1,
          borderColor: '#1e2230',
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { padding: 10, boxWidth: 10, font: { size: 11 } } } }
      }
    });

  } catch (err) {
    toast('Loi tai dashboard: ' + err.message, 'error');
  }
}

/* ══════════════════ CAMERAS PAGE ══════════════════════ */
async function renderCameras() {
  const area = $('content-area');
  const isAdmin = userRole === 'admin';
  area.innerHTML = `
    ${isAdmin ? `
    <div class="add-camera-form">
      <h3>Them Camera moi</h3>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Ten camera</label>
          <input id="cam-name" class="form-input" placeholder="VD: CAM_01_NGU_TU_A" />
        </div>
        <div class="form-group">
          <label class="form-label">Tuyen vao</label>
          <input id="cam-in" class="form-input" placeholder="VD: Nguyen Trai" />
        </div>
        <div class="form-group">
          <label class="form-label">Tuyen ra</label>
          <input id="cam-out" class="form-input" placeholder="VD: Khuat Duy Tien" />
        </div>
      </div>
      <button class="btn-primary" id="add-cam-btn" style="margin-top:12px;padding:8px 18px">Them Camera</button>
    </div>` : ''}
    <div class="section-header">
      <h2 class="section-title">Danh sach Camera</h2>
    </div>
    <div class="camera-grid" id="camera-grid">
      ${[1, 2, 3].map(() => `<div class="camera-card"><div class="skeleton" style="height:100px;width:100%"></div></div>`).join('')}
    </div>`;

  if (isAdmin) $('add-cam-btn').addEventListener('click', addCamera);
  loadCameras();
}

async function loadCameras() {
  try {
    const cameras = await api('/api/cameras');
    const grid = $('camera-grid');
    if (!cameras.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">[ TRONG ]</div><p class="empty-text">Chua co camera nao</p></div>`;
      return;
    }
    grid.innerHTML = cameras.map(c => `
      <div class="camera-card">
        <div class="camera-status-line">
          <div class="camera-dot"></div>
          <span class="camera-status-text">Online</span>
        </div>
        <div class="camera-name">${c.ten_camera}</div>
        <div class="camera-route">
          ${c.tuyen_duong_vao || '—'} <span>&#x2192;</span> ${c.tuyen_duong_ra || '—'}
        </div>
        <div class="camera-id">ID: ${c.id}</div>
      </div>`).join('');
  } catch (err) { toast('Loi tai camera: ' + err.message, 'error'); }
}

async function addCamera() {
  const name = $('cam-name').value.trim();
  if (!name) { toast('Vui long nhap ten camera', 'error'); return; }
  try {
    await api('/api/cameras', {
      method: 'POST',
      body: JSON.stringify({
        ten_camera: name,
        tuyen_vao: $('cam-in').value,
        tuyen_ra: $('cam-out').value
      })
    });
    toast('Da them camera thanh cong', 'success');
    $('cam-name').value = ''; $('cam-in').value = ''; $('cam-out').value = '';
    loadCameras();
  } catch (err) { toast('Loi: ' + err.message, 'error'); }
}

/* ══════════════════ VIOLATIONS PAGE ══════════════════ */
async function renderViolationsPage(reviewMode = false) {
  currentReviewMode = reviewMode;
  const area = $('content-area');
  area.innerHTML = `
    <div class="table-card">
      <div class="table-toolbar">
        <input id="f-bienso" class="filter-input" placeholder="Bien so..." />
        <select id="f-maloi" class="filter-select">
          <option value="">Tat ca vi pham</option>
          <option value="DI_SAI_LAN">Di sai lan</option>
          <option value="DI_NGUOC_CHIEU">Di nguoc chieu</option>
          <option value="DE_VACH_PHAN_LAN">De vach phan lan</option>
          <option value="VUOT_DEN_DO">Vuot den do</option>
        </select>
        <select id="f-loaixe" class="filter-select">
          <option value="">Tat ca phuong tien</option>
          <option value="CAR">O to</option>
          <option value="MOTORCYCLE">Xe may</option>
          <option value="TRUCK">Xe tai</option>
          <option value="BUS">Xe buyt</option>
        </select>
        <select id="f-trangthai" class="filter-select">
          <option value="">Tat ca trang thai</option>
          <option value="0">Cho duyet</option>
          <option value="1">Da duyet</option>
          <option value="-1">Tu choi</option>
        </select>
        <button id="f-btn" class="btn-primary" style="padding:7px 16px;font-size:12px">Tim kiem</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Thoi gian</th>
              <th>Camera</th>
              <th>Loai vi pham</th>
              <th>Phuong tien</th>
              <th>Bien so</th>
              <th>Trang thai</th>
              <th>Thao tac</th>
              <th>Bang chung</th>
            </tr>
          </thead>
          <tbody id="v-tbody">
            <tr><td colspan="8" style="text-align:center;padding:32px">
              <div class="spinner" style="margin:auto"></div>
            </td></tr>
          </tbody>
        </table>
      </div>
      <div class="table-pagination">
        <span class="pagination-info" id="v-page-info">—</span>
        <div class="pagination-btns">
          <button class="btn-page" id="v-prev">Trang truoc</button>
          <button class="btn-page" id="v-next">Trang sau</button>
        </div>
      </div>
    </div>`;

  const load = () => loadViolations(reviewMode);
  $('f-btn').addEventListener('click', () => { currentPage = 1; load(); });
  $('v-prev').addEventListener('click', () => { currentPage--; load(); });
  $('v-next').addEventListener('click', () => { currentPage++; load(); });
  load();
}

async function loadViolations(reviewMode) {
  const params = new URLSearchParams({
    limit: PAGE_SIZE,
    offset: (currentPage - 1) * PAGE_SIZE,
  });
  const bienso = $('f-bienso')?.value.trim();
  const maloi = $('f-maloi')?.value;
  const loaixe = $('f-loaixe')?.value;
  const ts = $('f-trangthai')?.value;
  if (bienso) params.set('bien_so', bienso);
  if (maloi) params.set('ma_loi', maloi);
  if (loaixe) params.set('loai_xe', loaixe);
  if (ts !== '') params.set('trang_thai', ts);

  const tbody = $('v-tbody');
  const cols = 8;
  tbody.innerHTML = `<tr><td colspan="${cols}" style="text-align:center;padding:32px"><div class="spinner" style="margin:auto"></div></td></tr>`;

  try {
    const res = await api(`/api/violations?${params}`);
    const { data, total } = res;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    $('v-page-info').textContent = `Trang ${currentPage} / ${totalPages}  —  Tong: ${total} ban ghi`;
    $('v-prev').disabled = currentPage <= 1;
    $('v-next').disabled = currentPage >= totalPages;

    if (!data.length) {
      tbody.innerHTML = `<tr><td colspan="${cols}">
        <div class="empty-state">
          <div class="empty-icon">[ TRONG ]</div>
          <p class="empty-text">Khong co du lieu phu hop</p>
        </div>
      </td></tr>`;
      return;
    }

    tbody.innerHTML = data.map(row => {
      const evidence = row.duong_dan_bang_chung;
      const evidenceCell = evidence
        ? `<button onclick="showEvidence('${row.id}')" class="btn-sm evidence-btn">Xem</button>`
        : `<span class="text-muted">—</span>`;

      const approveRejectBtns = row.trang_thai_duyet === 0
        ? `<button class="btn-sm approve" onclick="changeStatus('${row.id}', 1)">Duyet</button>
           <button class="btn-sm reject"  onclick="changeStatus('${row.id}', -1)">Tu choi</button>`
        : '';
      const deleteBtn = `<button class="btn-sm reject" onclick="deleteViolation('${row.id}')">Xoa</button>`;

      const actions = `<td>
        <div class="flex gap-2">
          ${approveRejectBtns}
          ${deleteBtn}
        </div>
      </td>`;

      return `<tr>
        <td class="muted font-mono">${fmtDate(row.thoi_gian_vi_pham)}</td>
        <td class="truncate" style="max-width:130px">${row.ten_camera || '—'}</td>
        <td>${violationLabel(row.ma_loi_vi_pham)}</td>
        <td class="muted">${row.loai_phuong_tien || '—'}</td>
        <td class="font-mono">${row.bien_so_xe || '—'}</td>
        <td>${statusBadge(row.trang_thai_duyet)}</td>
        ${actions}
        <td>${evidenceCell}</td>
      </tr>`;
    }).join('');

  } catch (err) {
    toast('Loi tai danh sach: ' + err.message, 'error');
  }
}

async function changeStatus(id, status) {
  try {
    await api(`/api/violations/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ trang_thai: status })
    });
    toast(status === 1 ? 'Da duyet vi pham' : 'Da tu choi vi pham', 'success');
    loadViolations(currentReviewMode);
  } catch (err) {
    toast('Loi cap nhat: ' + err.message, 'error');
  }
}

async function deleteViolation(id) {
  if (!confirm('Ban co chac chan muon xoa ban ghi vi pham nay?')) return;
  try {
    const res = await api(`/api/violations/${id}`, {
      method: 'DELETE'
    });
    if (res && res.success) {
      toast('Da xoa ban ghi vi pham thanh cong', 'success');
      loadViolations(currentReviewMode);
    } else {
      toast('Xoa that bai: khong tim thay ban ghi', 'error');
    }
  } catch (err) {
    toast('Loi xoa: ' + err.message, 'error');
    console.error('[deleteViolation] ID:', id, 'Error:', err);
  }
}

/* ── Expose inline-onclick handlers to global scope ── */
window.changeStatus = changeStatus;
window.deleteViolation = deleteViolation;

async function showEvidence(recordId) {
  const modal = $('evidence-modal');
  const body = $('modal-body');

  modal.classList.remove('hidden');
  body.innerHTML = '<div class="spinner" style="margin:40px auto"></div>';

  try {
    const res = await api(`/api/violations/${recordId}/evidence`);
    if (!res || !res.files || res.files.length === 0) {
      body.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">[ TRỐNG ]</div>
          <p class="empty-text">Không tìm thấy hình ảnh vi phạm.</p>
        </div>`;
      return;
    }

    const images = res.files.filter(f => f.type === 'image');
    const others = res.files.filter(f => f.type !== 'image' && f.type !== 'video');

    if (images.length === 0 && others.length === 0) {
      body.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">[ TRỐNG ]</div>
          <p class="empty-text">Không tìm thấy hình ảnh vi phạm.</p>
        </div>`;
      return;
    }

    let html = '<div class="evidence-gallery">';

    if (images.length > 0) {
      html += '<div class="evidence-section"><h4>Hình ảnh bằng chứng</h4><div class="image-grid">';
      images.forEach(img => {
        html += `
          <div class="evidence-item image-item">
            <a href="${img.url}" target="_blank" title="Click để phóng to">
              <img src="${img.url}" alt="${img.name}" class="evidence-media" />
            </a>
            <div class="evidence-name">${img.name}</div>
          </div>`;
      });
      html += '</div></div>';
    }

    if (others.length > 0) {
      html += '<div class="evidence-section"><h4>Tệp tin khác</h4>';
      others.forEach(oth => {
        html += `
          <div class="evidence-item other-item">
            <a href="${oth.url}" target="_blank" class="btn-primary" style="display:inline-block; margin-top:5px;">
              Tải xuống: ${oth.name}
            </a>
          </div>`;
      });
      html += '</div>';
    }

    html += '</div>';
    body.innerHTML = html;
  } catch (err) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">[ LỖI ]</div>
        <p class="empty-text" style="color:var(--red)">Lỗi khi tải bằng chứng: ${err.message}</p>
      </div>`;
  }
}

function closeEvidenceModal(e) {
  if (e && e.target.id === 'evidence-modal') {
    $('evidence-modal').classList.add('hidden');
  }
}

window.showEvidence = showEvidence;
window.closeEvidenceModal = closeEvidenceModal;

/* ─── Sidebar Toggle ─────────────────────────── */
$('sidebar-toggle').addEventListener('click', () => {
  $('sidebar').classList.toggle('collapsed');
});

/* ─── Logout ─────────────────────────────────── */
$('logout-btn').addEventListener('click', logout);

/* ─── Login form ─────────────────────────────── */
$('login-form').addEventListener('submit', doLogin);

/* ─── Boot — restore session ─────────────────── */
if (token) {
  api('/api/auth/me').then(me => {
    if (me) { userRole = me.role; userName = me.full_name; enterApp(); }
  }).catch(() => logout());
}
