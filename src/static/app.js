'use strict';

const $ = (id) => document.getElementById(id);
const OBSTACLE_STATES = new Set(['OBSTACLE_STOP', 'EMERGENCY_STOP']);
const MAX_WAREHOUSE_CAPACITY = 50;

let latestDeviceOnline = false;
let refreshInProgress = false;
let currentWarehouseFilter = 'ALL';
let isEmergencyActive = false;

// HOÀN TOÀN KHÔNG LƯU TRỮ CŨ - Bắt đầu sạch sẽ từ mảng rỗng []
function getPersistentDeliveries(serverDeliveries) {
  return Array.isArray(serverDeliveries) ? serverDeliveries : [];
}

let cachedDeliveries = [];

let modalState = {
  activeWarehouse: 'ALL',
  mode: 'EXPORT',
  preset: 'ALL',
  fromDate: '',
  toDate: ''
};

const STATUS_LABELS = {
  RUN: 'Đang di chuyển',
  WAITING: 'Chờ khởi hành',
  WEIGHING: 'Đang cân hàng',
  OBSTACLE_STOP: 'Dừng do vật cản',
  EMERGENCY_STOP: 'DỪNG KHẨN CẤP',
  WAIT_UNLOAD: 'Chờ dỡ hàng',
  AT_KHO1: 'Đang ở Kho 1',
  AT_KHO2: 'Đang ở Kho 2',
  DELIVERED: 'Đã giao hàng',
  WIFI_LOST: 'Mất kết nối Wi-Fi'
};

const LOAD_LABELS = {
  LIGHT: 'Hàng nhẹ',
  HEAVY: 'Hàng nặng',
  NONE: 'Không có hàng',
  OTHER: 'Chưa phân loại',
  UNKNOWN: 'Chưa xác định'
};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function numberText(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '--';
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString('vi-VN', { minimumFractionDigits: 0, maximumFractionDigits: digits }) : '--';
}

function dateText(value) {
  if (!value) return '--';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).replace('T', ' ');
  return d.toLocaleString('vi-VN', { hour12: false });
}

function getStatusLabel(status) {
  return STATUS_LABELS[String(status || '').toUpperCase()] || status || 'Chưa có dữ liệu';
}

function getLoadLabel(level) {
  return LOAD_LABELS[String(level || '').toUpperCase()] || (level || 'Chưa xác định');
}

function showToast(msg) {
  const box = $('toastBox');
  if (!box) return;
  box.textContent = msg;
  box.classList.remove('hidden');
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => box.classList.add('hidden'), 3200);
}

function setPill(el, kind, text) {
  el.className = `connection-chip ${kind || ''}`.trim();
  const span = el.querySelector('span:last-child');
  if (span) span.textContent = text;
}

function renderEmergencyUI(state) {
  const status = String(state.status || '').toUpperCase();
  const estopActive = Boolean(state.emergency_stop) || status === 'EMERGENCY_STOP' || isEmergencyActive;
  const btnStop = $('btnEmergencyStop');
  const btnResume = $('btnResumeVehicle');

  if (btnResume) btnResume.classList.toggle('hidden', !estopActive);
  if (btnStop) btnStop.disabled = estopActive;
}

async function triggerEmergencyStop(stopNow) {
  if (!stopNow) {
    const ok = window.confirm('Xác nhận đường chạy đã an toàn và cho phép xe AGV tiếp tục di chuyển?');
    if (!ok) return;
  }
  isEmergencyActive = stopNow;
  try {
    const res = await fetch('/api/emergency', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        emergency_stop: stopNow,
        action: stopNow ? 'STOP' : 'RESUME',
        status: stopNow ? 'EMERGENCY_STOP' : 'WAITING',
        alert: stopNow ? 'Lệnh DỪNG KHẨN CẤP được kích hoạt từ Trung tâm điều khiển Web!' : ''
      })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showToast(stopNow ? '🛑 Đã gửi lệnh DỪNG KHẨN CẤP tới xe AGV!' : '▶ Đã mở khóa, cho phép xe AGV hoạt động lại!');
    await refresh();
  } catch (err) {
    renderEmergencyUI({ emergency_stop: stopNow, status: stopNow ? 'EMERGENCY_STOP' : 'WAITING' });
    renderObstacle({
      status: stopNow ? 'EMERGENCY_STOP' : 'WAITING',
      alert: stopNow ? 'Đã kích hoạt nút Dừng Khẩn Cấp trên giao diện điều khiển.' : ''
    });
    showToast(stopNow ? '🛑 Đã kích hoạt Dừng Khẩn Cấp.' : '▶ Đã hủy trạng thái Dừng Khẩn Cấp.');
  }
}

function renderStatus(state, online) {
  const status = isEmergencyActive ? 'EMERGENCY_STOP' : String(state.status || 'UNKNOWN').toUpperCase();
  $('deviceId').textContent = state.device_id || 'AGV01';
  $('status').textContent = online || isEmergencyActive ? getStatusLabel(status) : (state.updated_at ? 'Mất kết nối với xe' : 'Chưa có dữ liệu');
  $('updatedAt').textContent = state.updated_at ? dateText(state.updated_at) : 'Chưa có dữ liệu';

  const dot = $('largeStatusDot');
  dot.className = 'large-status-dot';
  $('statusTag').className = 'metric-tag';

  if (status === 'EMERGENCY_STOP') {
    dot.classList.add('dot-danger');
    $('statusTag').classList.add('tag-red');
    $('statusTag').textContent = 'KHẨN CẤP';
    $('statusDescription').textContent = 'Xe đã dừng khẩn cấp theo lệnh từ người vận hành trên Web.';
  } else if (!online) {
    dot.classList.add('dot-offline');
    $('statusTag').classList.add('tag-gray');
    $('statusTag').textContent = 'OFFLINE';
    $('statusDescription').textContent = 'Chưa nhận được dữ liệu mới từ ESP32.';
  } else if (OBSTACLE_STATES.has(status)) {
    dot.classList.add('dot-danger');
    $('statusTag').classList.add('tag-red');
    $('statusTag').textContent = 'CẦN XỬ LÝ';
    $('statusDescription').textContent = 'Xe đã dừng do phát hiện vật cản trên đường đi.';
  } else if (status === 'RUN') {
    dot.classList.add('dot-running');
    $('statusTag').classList.add('tag-green');
    $('statusTag').textContent = 'ĐANG CHẠY';
    $('statusDescription').textContent = 'Xe đang thực hiện lộ trình tự động.';
  } else if (status === 'DELIVERED') {
    dot.classList.add('dot-delivered');
    $('statusTag').classList.add('tag-purple');
    $('statusTag').textContent = 'ĐÃ GIAO';
    $('statusDescription').textContent = 'Máy chủ đã ghi nhận chuyến giao hàng.';
  } else {
    dot.classList.add('dot-waiting');
    $('statusTag').classList.add('tag-blue');
    $('statusTag').textContent = 'ĐANG CHỜ';
    $('statusDescription').textContent = status === 'WAIT_UNLOAD'
      ? 'Xe đang chờ hoàn tất thao tác dỡ hàng.'
      : 'Xe đang chờ bước tiếp theo của quy trình.';
  }
}

function renderObstacle(state) {
  const status = isEmergencyActive ? 'EMERGENCY_STOP' : String(state.status || '').toUpperCase();
  const isEmergency = status === 'EMERGENCY_STOP' || Boolean(state.emergency_stop);
  const obstacleState = isEmergency || OBSTACLE_STATES.has(status) || /vật cản|obstacle/i.test(String(state.alert || ''));
  const box = $('alertBox');
  box.classList.toggle('hidden', !obstacleState);

  if (isEmergency) {
    $('alertKicker').textContent = 'LỆNH DỪNG KHẨN CẤP';
    $('alertState').textContent = 'ĐANG KHÓA XE';
    $('alertTitle').textContent = 'Xe AGV đã dừng khẩn cấp theo lệnh điều khiển';
    $('alertText').textContent = state.alert || 'Toàn bộ hành trình của xe đã tạm khóa. Nhấn "Cho phép chạy lại" khi đã xử lý xong.';
  } else if (obstacleState) {
    $('alertKicker').textContent = 'CẢNH BÁO AN TOÀN';
    $('alertState').textContent = 'XE ĐANG DỪNG';
    $('alertTitle').textContent = 'Phát hiện vật cản — xe đã dừng';
    $('alertText').textContent = state.alert || 'Xe đã dừng để bảo đảm an toàn. Đang chờ đường thoáng để tiếp tục.';
  }
}

function renderStock(stock, deliveries) {
  const rows = Array.isArray(deliveries) ? deliveries : [];
  const kho1Rows = rows.filter((r) => String(r.warehouse || '').toUpperCase() === 'KHO1');
  const kho2Rows = rows.filter((r) => String(r.warehouse || '').toUpperCase() === 'KHO2');

  const kho1Count = Number(stock?.KHO1?.total ?? kho1Rows.length);
  const kho2Count = Number(stock?.KHO2?.total ?? kho2Rows.length);
  const totalCount = kho1Count + kho2Count;

  const kho1SumWeight = kho1Rows.reduce((acc, r) => acc + (Number(r.weight_before) || 0), 0);
  const kho2SumWeight = kho2Rows.reduce((acc, r) => acc + (Number(r.weight_before) || 0), 0);

  $('kho1Total').textContent = numberText(kho1Count, 0);
  $('kho2Total').textContent = numberText(kho2Count, 0);

  $('kho1Weight').textContent = `${numberText(kho1SumWeight)} g`;
  $('kho2Weight').textContent = `${numberText(kho2SumWeight)} g`;

  $('kho1LastTime').textContent = kho1Rows[0] ? dateText(kho1Rows[0].delivered_at) : 'Chưa có';
  $('kho2LastTime').textContent = kho2Rows[0] ? dateText(kho2Rows[0].delivered_at) : 'Chưa có';

  const cap1 = Math.min(100, Math.round((kho1Count / MAX_WAREHOUSE_CAPACITY) * 100));
  const cap2 = Math.min(100, Math.round((kho2Count / MAX_WAREHOUSE_CAPACITY) * 100));

  $('kho1Progress').style.width = `${cap1}%`;
  $('kho2Progress').style.width = `${cap2}%`;
  $('kho1CapTag').textContent = `${cap1}% SỨC CHỨA`;
  $('kho2CapTag').textContent = `${cap2}% SỨC CHỨA`;

  // Cập nhật số lượng trên các tab
  if ($('tabAll')) $('tabAll').textContent = `Tất cả (${totalCount})`;
  if ($('tabKho1')) $('tabKho1').textContent = `Kho 1 (${kho1Count})`;
  if ($('tabKho2')) $('tabKho2').textContent = `Kho 2 (${kho2Count})`;
}

function renderHistory(deliveries) {
  const allRows = Array.isArray(deliveries) ? deliveries : [];
  const kho1Count = allRows.filter(r => String(r.warehouse || '').toUpperCase() === 'KHO1').length;
  const kho2Count = allRows.filter(r => String(r.warehouse || '').toUpperCase() === 'KHO2').length;
  const totalCount = allRows.length;

  const rows = currentWarehouseFilter === 'ALL'
    ? allRows
    : allRows.filter((r) => String(r.warehouse || '').toUpperCase() === currentWarehouseFilter);

  if (allRows.length) {
    const latest = allRows[0];
    $('lastWarehouse').textContent = latest.warehouse === 'KHO1' ? 'Kho 1' : latest.warehouse === 'KHO2' ? 'Kho 2' : (latest.warehouse || '--');
    $('lastTrip').textContent = latest.trip_id || 'Chưa có';
  } else {
    $('lastWarehouse').textContent = '--';
    $('lastTrip').textContent = 'Chưa có';
  }

  // Ràng buộc chính xác số lượng hiển thị theo đúng số dòng thực tế đang render ra bảng
  $('historyCount').textContent = String(rows.length);
  $('historyFooter').textContent = currentWarehouseFilter === 'ALL'
    ? `Đang xem: Tất cả (${totalCount} kiện)`
    : `Đang lọc riêng: ${currentWarehouseFilter === 'KHO1' ? 'Kho 1' : 'Kho 2'} (${rows.length} kiện)`;

  if (!rows.length) {
    $('historyBody').innerHTML = `<tr><td colspan="6" class="empty-cell">
      <span class="empty-icon">▤</span>
      <strong>Chưa có lịch sử giao hàng</strong>
      <small>Dữ liệu sẽ xuất hiện khi xe AGV thực hiện chuyến giao hàng và gửi xác nhận.</small>
    </td></tr>`;
    return;
  }

  $('historyBody').innerHTML = rows.map((row) => {
    const warehouse = String(row.warehouse || '').toUpperCase();
    const warehouseLabel = warehouse === 'KHO1' ? 'Kho 1' : warehouse === 'KHO2' ? 'Kho 2' : warehouse;
    const loadLabel = getLoadLabel(row.load_level);
    return `<tr>
      <td class="date-cell">${esc(dateText(row.delivered_at))}</td>
      <td><span class="trip-code">${esc(row.trip_id)}</span></td>
      <td><span class="warehouse-pill ${warehouse === 'KHO1' ? 'wh-one' : 'wh-two'}">${esc(warehouseLabel)}</span></td>
      <td>${esc(loadLabel)}</td>
      <td class="weight-cell">${esc(numberText(row.weight_before))} <small>g</small></td>
      <td><span class="recorded-pill"><span></span>Đã ghi nhận</span></td>
    </tr>`;
  }).join('');
}

function filterRowsByModal(rows) {
  return rows.filter((r) => {
    if (modalState.activeWarehouse !== 'ALL') {
      const wh = String(r.warehouse || '').toUpperCase();
      if (wh !== modalState.activeWarehouse) return false;
    }
    if (!r.delivered_at) return true;
    const rDateStr = String(r.delivered_at).slice(0, 10);
    const todayStr = new Date().toISOString().slice(0, 10);

    if (modalState.preset === 'TODAY' || modalState.preset === 'QUICK_TODAY') {
      return rDateStr === todayStr;
    }
    if (modalState.preset === '7DAYS') {
      const d = new Date();
      d.setDate(d.getDate() - 7);
      return rDateStr >= d.toISOString().slice(0, 10);
    }
    if (modalState.preset === 'CUSTOM') {
      if (modalState.fromDate && rDateStr < modalState.fromDate) return false;
      if (modalState.toDate && rDateStr > modalState.toDate) return false;
    }
    return true;
  });
}

function updateModalPreview() {
  const filtered = filterRowsByModal(cachedDeliveries);
  const totalW = filtered.reduce((sum, r) => sum + (Number(r.weight_before) || 0), 0);
  $('previewCount').textContent = `${filtered.length} chuyến`;
  $('previewWeight').textContent = `${numberText(totalW)} g`;
}

function openReportModal(warehouseCode, mode) {
  modalState.activeWarehouse = warehouseCode;
  modalState.mode = mode;
  modalState.preset = 'ALL';
  modalState.fromDate = '';
  modalState.toDate = '';

  const whName = warehouseCode === 'ALL' ? 'Toàn bộ hệ thống' : (warehouseCode === 'KHO1' ? 'Kho 1' : 'Kho 2');
  $('modalTitle').textContent = mode === 'EXPORT' ? `Xuất Excel (CSV) — ${whName}` : `In phiếu kiểm kê — ${whName}`;
  $('btnConfirmModal').textContent = mode === 'EXPORT' ? '📥 Tải file CSV' : '🖨 In phiếu ngay';

  document.querySelectorAll('.preset-chip').forEach((c) => {
    c.classList.toggle('active', c.getAttribute('data-preset') === 'ALL');
  });
  $('filterFromDate').value = '';
  $('filterToDate').value = '';

  const todayStr = new Date().toLocaleDateString('vi-VN');
  $('todayDateLabel').textContent = `Lấy dữ liệu giao nhận trong ngày (${todayStr})`;

  updateModalPreview();
  $('reportModal').classList.remove('hidden');
}

function closeReportModal() {
  $('reportModal').classList.add('hidden');
}

function executeModalAction() {
  const rows = filterRowsByModal(cachedDeliveries);
  if (!rows.length) {
    showToast('⚠️ Không có dữ liệu nào trong khoảng thời gian đã chọn để trích xuất!');
    return;
  }

  if (modalState.mode === 'EXPORT') {
    const headers = ['STT', 'Thời gian giao', 'Mã chuyến', 'Kho nhận', 'Phân loại hàng', 'Khối lượng (g)', 'Trạng thái'];
    const csvLines = [
      headers.join(','),
      ...rows.map((r, idx) => {
        const whName = String(r.warehouse || '').toUpperCase() === 'KHO1' ? 'Kho 1' : 'Kho 2';
        const cells = [
          idx + 1,
          dateText(r.delivered_at),
          r.trip_id || '',
          whName,
          getLoadLabel(r.load_level),
          Number(r.weight_before) || 0,
          'Đã nhập kho'
        ];
        return cells.map((val) => `"${String(val).replace(/"/g, '""')}"`).join(',');
      })
    ];

    const blob = new Blob(['\uFEFF' + csvLines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    a.href = url;
    a.download = `Bao_Cao_Kho_${modalState.activeWarehouse}_${timestamp}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`✅ Đã tải xuống file Excel cho ${modalState.activeWarehouse}!`);
  } else {
    const whTitle = modalState.activeWarehouse === 'KHO1' ? 'KHO 1 — HÀNG NHẸ' : (modalState.activeWarehouse === 'KHO2' ? 'KHO 2 — HÀNG NẶNG' : 'TOÀN BỘ KHO HÀNG');
    const totalWeight = rows.reduce((sum, r) => sum + (Number(r.weight_before) || 0), 0);

    const win = window.open('', '_blank', 'width=900,height=700');
    if (!win) {
      showToast('⚠️ Vui lòng cho phép mở cửa sổ Pop-up trên trình duyệt để in phiếu!');
      return;
    }

    const tableRows = rows.map((r, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${esc(dateText(r.delivered_at))}</td>
        <td><strong>${esc(r.trip_id)}</strong></td>
        <td>${esc(r.warehouse || '')}</td>
        <td>${esc(getLoadLabel(r.load_level))}</td>
        <td style="text-align:right">${esc(numberText(r.weight_before))} g</td>
      </tr>`).join('');

    win.document.write(`<!doctype html>
    <html lang="vi">
    <head>
      <meta charset="utf-8">
      <title>Phiếu Kiểm Kê ${whTitle}</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 30px; color: #111; }
        h1 { margin: 4px 0; font-size: 22px; }
        .meta { margin-bottom: 20px; font-size: 13px; color: #444; }
        .summary { display: flex; gap: 30px; background: #f3f6fb; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
        th { background: #eaeff7; }
        .sign { margin-top: 40px; display: flex; justify-content: space-between; padding: 0 40px; font-size: 13px; text-align: center; }
      </style>
    </head>
    <body>
      <h1>PHIẾU TRÍCH XUẤT DỮ LIỆU ${whTitle}</h1>
      <div class="meta">Hệ thống điều hành AGV · Thời gian trích xuất: ${new Date().toLocaleString('vi-VN')}</div>
      <div class="summary">
        <div>Tổng số kiện đã lọc: <strong>${rows.length} kiện</strong></div>
        <div>Tổng khối lượng tích lũy: <strong>${numberText(totalWeight)} g</strong></div>
      </div>
      <table>
        <thead>
          <tr><th>STT</th><th>Thời gian nhập kho</th><th>Mã chuyến</th><th>Kho nhận</th><th>Phân loại</th><th style="text-align:right">Khối lượng</th></tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
      <div class="sign">
        <div><strong>Người lập biểu</strong><br><br><br><br>(Ký, ghi rõ họ tên)</div>
        <div><strong>Quản lý kho</strong><br><br><br><br>(Ký, ghi rõ họ tên)</div>
      </div>
      <script>window.onload = () => { window.print(); };<\/script>
    </body>
    </html>`);
    win.document.close();
  }

  closeReportModal();
}

async function refresh() {
  if (refreshInProgress) return;
  refreshInProgress = true;
  try {
    const response = await fetch('/api/status', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const state = data.state || {};
    latestDeviceOnline = Boolean(data.device_online);

    // Lấy trực tiếp dữ liệu mới nhất từ server, không dùng localStorage cũ
    cachedDeliveries = Array.isArray(data.deliveries) ? data.deliveries : [];

    if (typeof state.emergency_stop === 'boolean') {
      isEmergencyActive = state.emergency_stop;
    }

    setPill($('serverConnection'), 'chip-ok', 'Máy chủ hoạt động');
    setPill($('vehicleConnection'), latestDeviceOnline ? 'chip-ok' : 'chip-offline', latestDeviceOnline ? 'Xe AGV đang kết nối' : 'Xe chưa kết nối');

    $('weight').textContent = numberText(state.weight_g);
    $('loadLevel').textContent = `Loại hàng: ${getLoadLabel(state.load_level)}`;
    const weight = Number(state.weight_g);
    $('weightTrack').style.width = Number.isFinite(weight) && weight > 0 ? `${Math.max(4, Math.min(100, (weight / 120) * 100))}%` : '0%';
    $('weightTrack').classList.toggle('weight-over', Number.isFinite(weight) && weight > 120);

    renderEmergencyUI(state);
    renderStatus(state, latestDeviceOnline);
    renderObstacle(state);
    renderStock(data.stock || {}, cachedDeliveries);
    renderHistory(cachedDeliveries);
  } catch (error) {
    setPill($('serverConnection'), 'chip-error', 'Không kết nối được máy chủ');
    setPill($('vehicleConnection'), 'chip-offline', 'Chưa xác định trạng thái xe');
    $('status').textContent = 'Không nhận được dữ liệu';
    $('statusDescription').textContent = 'Kiểm tra máy chủ và kết nối mạng.';
    $('largeStatusDot').className = 'large-status-dot dot-offline';
    latestDeviceOnline = false;
  } finally {
    refreshInProgress = false;
  }
}

function bindEvents() {
  $('btnEmergencyStop').addEventListener('click', () => triggerEmergencyStop(true));
  $('btnResumeVehicle').addEventListener('click', () => triggerEmergencyStop(false));
  $('btnExportAll').addEventListener('click', () => openReportModal('ALL', 'EXPORT'));

  document.querySelectorAll('[data-export]').forEach((btn) => {
    btn.addEventListener('click', () => openReportModal(btn.getAttribute('data-export'), 'EXPORT'));
  });

  document.querySelectorAll('[data-print]').forEach((btn) => {
    btn.addEventListener('click', () => openReportModal(btn.getAttribute('data-print'), 'PRINT'));
  });

  document.querySelectorAll('[data-filter]').forEach((btn) => {
    btn.addEventListener('click', () => {
      currentWarehouseFilter = btn.getAttribute('data-filter');
      document.querySelectorAll('.filter-tab').forEach((t) => {
        t.classList.toggle('active', t.getAttribute('data-tab') === currentWarehouseFilter);
      });
      renderHistory(cachedDeliveries);
      $('historySection').scrollIntoView({ behavior: 'smooth' });
    });
  });

  document.querySelectorAll('.filter-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      currentWarehouseFilter = tab.getAttribute('data-tab');
      document.querySelectorAll('.filter-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      renderHistory(cachedDeliveries);
    });
  });

  $('btnCloseModal').addEventListener('click', closeReportModal);
  $('btnCancelModal').addEventListener('click', closeReportModal);

  document.querySelectorAll('.preset-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.preset-chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      modalState.preset = chip.getAttribute('data-preset');
      updateModalPreview();
    });
  });

  $('filterFromDate').addEventListener('change', (e) => {
    modalState.fromDate = e.target.value;
    modalState.preset = 'CUSTOM';
    document.querySelectorAll('.preset-chip').forEach((c) => c.classList.remove('active'));
    updateModalPreview();
  });

  $('filterToDate').addEventListener('change', (e) => {
    modalState.toDate = e.target.value;
    modalState.preset = 'CUSTOM';
    document.querySelectorAll('.preset-chip').forEach((c) => c.classList.remove('active'));
    updateModalPreview();
  });

  $('btnQuickToday').addEventListener('click', () => {
    modalState.preset = 'QUICK_TODAY';
    executeModalAction();
  });

  $('btnConfirmModal').addEventListener('click', executeModalAction);
}

bindEvents();
refresh();
setInterval(refresh, 1500);