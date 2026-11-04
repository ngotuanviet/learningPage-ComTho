/**
 * Website hợp tác & nhượng quyền: menu, tô sáng trang hiện tại, lightbox ảnh,
 * chọn sẵn hình thức hợp tác (?model=...), gửi form lên Google Sheet,
 * chọn cơ sở & bản đồ tương tác.
 *
 * Cách nối Google Sheet: xem google-apps-script.gs, deploy dạng Web app
 * rồi dán URL (kết thúc bằng /exec) vào biến dưới đây.
 */
const SHEET_ENDPOINT = 'https://script.google.com/macros/s/AKfycbwKFgITalc8h-fACaetp8MmA-STteicMLAR83sJn4_ysgkXVy5bL1gtdup91Ln4C2mxBg/exec';

document.addEventListener('DOMContentLoaded', () => {
  // ── Menu: mục của trang đang xem + hamburger ──
  const navLinks = document.getElementById('frLinks');
  const toggle = document.getElementById('frToggle');
  const here = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
  navLinks.querySelectorAll('a').forEach(a => {
    const file = (a.getAttribute('href') || '').split('?')[0].split('#')[0].toLowerCase();
    if (file === here && !a.classList.contains('nav__cta-mobile')) {
      a.classList.add('active');
      a.setAttribute('aria-current', 'page');
    }
  });
  const closeMenu = () => { navLinks.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); };
  toggle.addEventListener('click', () => {
    const open = navLinks.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });

  // ── Lightbox (trang Hệ thống nhà hàng) ──
  const box = document.getElementById('frLightbox');
  if (box) {
    const boxImg = box.querySelector('img');
    const closeBox = () => { box.hidden = true; boxImg.removeAttribute('src'); };
    document.addEventListener('click', (e) => {
      const a = e.target.closest('[data-lightbox]');
      if (a) { e.preventDefault(); boxImg.src = a.getAttribute('href'); boxImg.alt = a.querySelector('img')?.alt || ''; box.hidden = false; }
      else if (e.target === box || e.target.id === 'frLightboxClose') closeBox();
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !box.hidden) closeBox(); });
  }

  // ── Bản đồ tương tác & Chọn cơ sở (trang Hệ thống nhà hàng) ──
  const mapSection = document.getElementById('bando');
  if (mapSection) {
    const storeFrame = document.getElementById('storeMapFrame');
    const curBadge = document.getElementById('mapActiveBadge');
    const curName = document.getElementById('mapActiveName');
    const curAddr = document.getElementById('mapActiveAddr');
    const curCall = document.getElementById('mapActiveCall');
    const curDir = document.getElementById('mapActiveDir');
    const mapItems = mapSection.querySelectorAll('.fr-map-item');

    // Chuyển cơ sở đang hiển thị trên bản đồ
    const selectStore = (item, doScroll = false) => {
      if (!item) return;
      mapItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      const name = item.dataset.name || '';
      const addr = item.dataset.addr || '';
      const tag = item.dataset.tag || '';
      const tel = item.dataset.tel || '';
      const telDisplay = item.dataset.telDisplay || tel;
      const query = item.dataset.query || `Cơm Đốt Thố Hội An, ${addr}`;
      const isGold = item.dataset.gold === 'true';
      const mapPending = item.dataset.mapPending === 'true';

      if (curName) curName.textContent = name;
      if (curAddr) curAddr.textContent = addr + (mapPending ? ' — Vị trí chính xác đang cập nhật.' : '');
      if (curBadge) {
        curBadge.textContent = tag;
        curBadge.className = 'fr-map-info-tag' + (isGold ? ' fr-map-info-tag--gold' : '');
      }
      if (curCall) {
        curCall.href = 'tel:' + tel;
        curCall.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg> ${telDisplay}`;
      }
      if (curDir) {
        curDir.hidden = mapPending;
        if (mapPending) curDir.removeAttribute('href');
        else curDir.href = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(query)}`;
      }
      if (storeFrame) {
        storeFrame.title = `${mapPending ? 'Khu vực dự kiến' : 'Bản đồ'} ${name} — Cơm Đốt Thố Hội An`;
        storeFrame.src = `https://www.google.com/maps?q=${encodeURIComponent(query)}&z=${mapPending ? 12 : 17}&hl=vi&output=embed`;
      }

      if (doScroll) {
        mapSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    };

    // Click chọn cơ sở trong danh sách bên cạnh map
    mapItems.forEach(item => {
      item.addEventListener('click', () => selectStore(item, false));
    });

    selectStore([...mapItems].find(item => item.classList.contains('active')) || mapItems[0]);

    // Nút "Xem trên bản đồ" trên mỗi thẻ cơ sở phía trên
    document.querySelectorAll('[data-view-store]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const storeId = btn.dataset.viewStore;
        const targetItem = [...mapItems].find(it => it.dataset.storeId === storeId);
        if (targetItem) {
          selectStore(targetItem, true);
        }
      });
    });
  }

  // ── Hiện dần khi cuộn tới (các khối nội dung của mọi trang) ──
  if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const rvSel = '.fr-hop__title, .fr-hcard, .fr-groups li, .fr-mh, .fr-op, .fr-proc, .fr-split > *, .fr-head, .fr-store, .fr-shot, .fr-map, .fr-map-section, .fr-faq, .fr-form, .fr-chips, .fr-center, .fr-fine';
    const rvIo = new IntersectionObserver((entries) => {
      entries.forEach(en => {
        if (!en.isIntersecting) return;
        rvIo.unobserve(en.target);
        setTimeout(() => en.target.classList.add('fr-in'), 60);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -5% 0px' });
    document.querySelectorAll(rvSel).forEach(el => {
      if (el.closest('.fr-mrow')) return; // thực đơn dạng sách có hiệu ứng riêng
      const idx = [...el.parentElement.children].indexOf(el);
      // khối đã nằm trong màn hình khi mở trang: chờ phần tiêu đề chạy xong rồi mới hiện (đọc từ trên xuống)
      const inView = el.getBoundingClientRect().top < innerHeight * 0.95;
      el.style.setProperty('--d', ((inView ? 0.95 : 0) + (el.matches('.fr-mh') ? 0.45 : Math.min(idx, 5) * 0.12)).toFixed(2) + 's');
      el.classList.add('fr-rv');
      if (inView) {
        void el.offsetHeight; // chốt trạng thái ẩn trước, để chuyển động chắc chắn chạy
        setTimeout(() => el.classList.add('fr-in'), 40);
      } else {
        rvIo.observe(el);
      }
    });
  }

  // ── Thực đơn dạng sách: hai trang trượt từ hai bên vào khi cuộn tới (trang Bộ công thức) ──
  const books = document.querySelectorAll('.fr-mrow');
  if (books.length && 'IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(en => {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        // chờ một nhịp để trạng thái "trước" kịp hiện, nên hàng đầu tiên cũng có chuyển động
        setTimeout(() => en.target.querySelectorAll('.fr-pre').forEach(el => el.classList.remove('fr-pre')), 180);
      });
    }, { threshold: 0.15 });
    books.forEach(row => {
      row.querySelectorAll('.fr-book, .fr-mtag').forEach(el => el.classList.add('fr-pre'));
      io.observe(row);
    });
  }

  // ── Form tư vấn (trang Đăng ký) ──
  const form = document.getElementById('franchiseForm');
  if (!form) return;
  const msg = document.getElementById('frMsg');
  const btn = document.getElementById('frSubmit');
  const setMsg = (text, kind) => { msg.textContent = text; msg.className = 'fr-form__msg ' + (kind || ''); };

  // Chọn sẵn hình thức hợp tác từ ?model=
  const wanted = new URLSearchParams(location.search).get('model');
  if (wanted) {
    const opt = [...form.elements.model.options].find(o => o.textContent.trim() === wanted);
    if (opt) form.elements.model.value = opt.value || opt.textContent;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = new FormData(form);
    if (data.get('website')) return; // bot điền ô ẩn

    let ok = true;
    form.querySelectorAll('[required]').forEach(el => {
      const bad = !el.value.trim();
      el.classList.toggle('invalid', bad);
      if (bad) ok = false;
    });
    const phone = String(data.get('phone')).replace(/[\s.\-()]/g, '');
    if (!/^(\+?84|0)\d{9}$/.test(phone)) { form.elements.phone.classList.add('invalid'); ok = false; }
    const email = String(data.get('email')).trim();
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { form.elements.email.classList.add('invalid'); ok = false; }
    if (!ok) { setMsg('Vui lòng điền đủ thông tin bắt buộc và kiểm tra lại số điện thoại, email.', 'err'); return; }

    if (!SHEET_ENDPOINT) { setMsg('Form chưa được nối Google Sheet (thiếu SHEET_ENDPOINT).', 'err'); return; }

    btn.disabled = true;
    setMsg('Đang gửi...');
    try {
      const body = new URLSearchParams();
      ['name', 'phone', 'email', 'area', 'model', 'budget', 'note'].forEach(k => body.append(k, data.get(k) || ''));
      body.append('source', location.href);
      // no-cors: Apps Script không trả CORS header; request vẫn được ghi nhận
      await fetch(SHEET_ENDPOINT, { method: 'POST', mode: 'no-cors', body });
      setMsg('Đã gửi thành công. Chúng tôi sẽ liên hệ bạn trong 24 giờ làm việc.', 'ok');
      form.reset();
    } catch (err) {
      setMsg('Gửi chưa được, vui lòng thử lại hoặc gọi 097 538 88 86.', 'err');
    } finally {
      btn.disabled = false;
    }
  });
  form.addEventListener('input', (e) => e.target.classList.remove('invalid'));
});
