/* Bán tài liệu số: nút "Mua ngay" + trang checkout.
 * Giá, trạng thái và link tài liệu luôn lấy từ API. Trang này không bao giờ tự đặt "đã thanh toán".
 */
(function () {
  'use strict';

  // Địa chỉ backend. Chạy local thì tự dùng localhost:8000.
  var PROD_API = 'https://comtho-api.vercel.app'; // đổi khi có domain riêng (nhớ thêm domain web vào PUBLIC_ALLOWED_ORIGINS)
  var isLocal = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  var API = (window.SHOP_API || (isLocal ? 'http://localhost:8000' : PROD_API)) + '/api/v1';
  var POLL_MS = 4000;

  function vnd(n) { return new Intl.NumberFormat('vi-VN').format(n) + ' đ'; }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') node.textContent = attrs[k];
      else if (k === 'class') node.className = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function api(path, opts) {
    opts = opts || {};
    return fetch(API + path, {
      method: opts.method || 'GET',
      headers: Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {}),
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      cache: 'no-store',
      credentials: 'omit'
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) {
          var msg = typeof data.detail === 'string' ? data.detail : 'Có lỗi xảy ra, vui lòng thử lại.';
          if (res.status === 422) msg = 'Vui lòng kiểm tra lại họ tên và email.';
          var err = new Error(msg); err.status = res.status; throw err;
        }
        return data;
      });
    });
  }

  function saveToken(code, token) {
    try { sessionStorage.setItem('shop:' + code, token); } catch (e) { /* private mode */ }
  }
  function loadToken(code) {
    try { return sessionStorage.getItem('shop:' + code); } catch (e) { return null; }
  }

  /* ---------- Nút "Mua ngay" ---------- */

  // Nút có data-buy="<slug>". Nút ẩn sẵn (hidden) chỉ hiện khi lấy được giá;
  // nút dạng link luôn hiện, API lỗi thì vẫn đi theo href (trang đăng ký tư vấn).
  // data-buy-label: giữ nhãn cố định (vd "Mua Ngay"); không có thì hiện kèm giá.
  // Phần tử data-buy-price="<slug>" được điền giá bán thật.
  function initBuyButtons() {
    var slugs = {};
    document.querySelectorAll('[data-buy], [data-buy-price]').forEach(function (n) {
      slugs[n.getAttribute('data-buy') || n.getAttribute('data-buy-price')] = true;
    });
    Object.keys(slugs).forEach(function (slug) {
      api('/products/' + encodeURIComponent(slug)).then(function (product) {
        document.querySelectorAll('[data-buy-price="' + slug + '"]').forEach(function (n) {
          n.textContent = vnd(product.price);
        });
        document.querySelectorAll('[data-buy="' + slug + '"]').forEach(function (btn) {
          btn.textContent = btn.getAttribute('data-buy-label') || ('Mua tài liệu số · ' + vnd(product.price));
          btn.hidden = false;
          btn.addEventListener('click', function (e) { e.preventDefault(); openBuyDialog(product); });
        });
      }).catch(function () { /* chưa mở bán hoặc API lỗi: nút ẩn vẫn ẩn, link vẫn dẫn tới trang tư vấn */ });
    });
  }

  // Danh sách sản phẩm đang bán (cho ô "mua kèm"); tải một lần.
  var catalog = null;
  function loadCatalog() {
    if (!catalog) catalog = api('/products').catch(function () { return []; });
    return catalog;
  }

  var dialog;
  function openBuyDialog(product) {
    if (dialog) dialog.remove();
    var msg = el('p', { class: 'fr-form__msg', role: 'alert' });
    var submit = el('button', { type: 'submit', class: 'fr-btn fr-btn--gold', text: 'Tiếp tục thanh toán' });
    var addons = el('div', { class: 'shop-addons' });
    var total = el('strong', { class: 'shop-total__value', text: vnd(product.price) });
    var form = el('form', { class: 'shop-dialog__form', novalidate: '' }, [
      addons,
      el('div', { class: 'shop-total' }, [el('span', { text: 'Tổng thanh toán' }), total]),
      el('div', { class: 'form-group' }, [
        el('label', { class: 'form-label', for: 'shop-name', text: 'Họ và tên *' }),
        el('input', { id: 'shop-name', name: 'name', class: 'form-input', required: '', maxlength: '100', autocomplete: 'name', placeholder: 'Nguyễn Văn A' })
      ]),
      el('div', { class: 'form-group' }, [
        el('label', { class: 'form-label', for: 'shop-email', text: 'Email nhận tài liệu *' }),
        el('input', { id: 'shop-email', name: 'email', type: 'email', class: 'form-input', required: '', maxlength: '320', autocomplete: 'email', placeholder: 'ban@email.com' })
      ]),
      el('p', { class: 'shop-dialog__hint', text: 'Link tài liệu sẽ hiện ngay sau khi chuyển khoản thành công và được gửi vào email này.' }),
      el('div', { class: 'fr-form__foot' }, [submit]),
      msg
    ]);
    var close = el('button', { type: 'button', class: 'shop-dialog__close', 'aria-label': 'Đóng', text: '×' });
    dialog = el('dialog', { class: 'shop-dialog', 'aria-labelledby': 'shop-dialog-title' }, [
      close,
      el('span', { class: 'fr-eyebrow', text: 'Tài liệu số' }),
      el('h2', { id: 'shop-dialog-title', class: 'fr-form__title', text: product.name }),
      el('p', { class: 'shop-dialog__price', text: vnd(product.price) }),
      form
    ]);
    document.body.appendChild(dialog);
    close.addEventListener('click', function () { dialog.close(); });
    dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('close', function () { dialog.remove(); dialog = null; });

    // Ô "mua kèm" cho các tài liệu khác đang bán. Tổng tiền chỉ để hiển thị:
    // số tiền thật do máy chủ tính lại từ giá trong database.
    var extras = [];
    function selected() {
      return [product].concat(extras.filter(function (x) { return x.box.checked; }).map(function (x) { return x.product; }));
    }
    function updateTotal() {
      total.textContent = vnd(selected().reduce(function (sum, p) { return sum + p.price; }, 0));
    }
    loadCatalog().then(function (list) {
      list.filter(function (p) { return p.slug !== product.slug; }).forEach(function (p) {
        var box = el('input', { type: 'checkbox', name: 'addon', value: p.slug });
        box.addEventListener('change', updateTotal);
        addons.appendChild(el('label', { class: 'shop-addon' }, [
          box,
          el('span', { class: 'shop-addon__name', text: 'Mua kèm ' + p.name }),
          el('span', { class: 'shop-addon__price', text: '+' + vnd(p.price) })
        ]));
        extras.push({ product: p, box: box });
      });
      addons.hidden = !extras.length;
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var name = form.name.value.trim();
      var email = form.email.value.trim();
      form.name.classList.toggle('invalid', !name);
      form.email.classList.toggle('invalid', !form.email.checkValidity() || !email);
      if (!name || !email || !form.email.checkValidity()) {
        msg.className = 'fr-form__msg err';
        msg.textContent = 'Vui lòng nhập họ tên và email hợp lệ.';
        return;
      }
      submit.disabled = true;
      submit.textContent = 'Đang tạo đơn…';
      msg.textContent = '';
      var slugs = selected().map(function (p) { return p.slug; });
      var body = { customer_name: name, customer_email: email };
      if (slugs.length > 1) body.product_slugs = slugs; else body.product_slug = slugs[0];
      api('/orders', { method: 'POST', body: body })
        .then(function (order) {
          saveToken(order.code, order.access_token);
          location.href = 'checkout.html?code=' + encodeURIComponent(order.code);
        })
        .catch(function (err) {
          msg.className = 'fr-form__msg err';
          msg.textContent = err.status ? err.message : 'Không kết nối được máy chủ, vui lòng thử lại.';
          submit.disabled = false;
          submit.textContent = 'Tiếp tục thanh toán';
        });
    });
    dialog.showModal();
    form.name.focus();
  }

  /* ---------- Trang checkout ---------- */

  function initCheckout() {
    var root = document.getElementById('shopCheckout');
    if (!root) return;
    var code = (new URLSearchParams(location.search).get('code') || '').toUpperCase();
    var token = /^[A-Z0-9]{4,32}$/.test(code) ? loadToken(code) : null;
    var $ = function (id) { return document.getElementById(id); };
    var timer = null, countdown = null;

    function show(view) {
      ['viewLoading', 'viewPending', 'viewPaid', 'viewExpired', 'viewReview', 'viewMissing'].forEach(function (id) {
        $(id).hidden = id !== view;
      });
      var step = { viewPending: 2, viewReview: 3, viewPaid: 4 }[view] || 1;
      Array.prototype.forEach.call(root.querySelectorAll('.shop-steps li'), function (li, i) {
        li.classList.toggle('done', i + 1 < step || view === 'viewPaid');
        li.classList.toggle('current', i + 1 === step && view !== 'viewPaid');
      });
    }

    if (!token) { show('viewMissing'); return; }

    function startCountdown(expiresAt) {
      clearInterval(countdown);
      var end = new Date(expiresAt).getTime();
      function tick() {
        var left = Math.max(0, Math.floor((end - Date.now()) / 1000));
        $('payCountdown').textContent = String(Math.floor(left / 60)).padStart(2, '0') + ':' + String(left % 60).padStart(2, '0');
        if (!left) clearInterval(countdown);
      }
      tick();
      countdown = setInterval(tick, 1000);
    }

    function render(o) {
      document.querySelectorAll('[data-order-code]').forEach(function (n) { n.textContent = o.code; });
      document.querySelectorAll('[data-order-product]').forEach(function (n) { n.textContent = o.product_name; });
      document.querySelectorAll('[data-order-amount]').forEach(function (n) { n.textContent = vnd(o.amount); });

      if (o.status === 'pending' && o.payment) {
        var p = o.payment;
        $('payQr').src = p.qr_url;
        $('payBank').textContent = p.bank_code;
        $('payAccount').textContent = p.account_number;
        $('payName').textContent = p.account_name;
        $('payAmount').textContent = vnd(p.amount);
        $('payContent').textContent = p.content;
        root.querySelector('[data-copy="account"]').dataset.value = p.account_number;
        root.querySelector('[data-copy="amount"]').dataset.value = String(p.amount);
        root.querySelector('[data-copy="content"]').dataset.value = p.content;
        if ($('viewPending').hidden) startCountdown(o.expires_at);
        show('viewPending');
        return true; // tiếp tục hỏi trạng thái
      }
      clearInterval(countdown);
      var docs = (o.items && o.items.length) ? o.items : [{ name: o.product_name, drive_url: o.drive_url }];
      if (o.status === 'paid' && docs.every(function (d) { return d.drive_url; })) {
        var box = $('paidDocs');
        box.textContent = '';
        docs.forEach(function (d) {
          box.appendChild(el('div', { class: 'shop-doc' }, [
            el('div', { class: 'shop-doc__icon', 'aria-hidden': 'true', text: 'PDF' }),
            el('div', { class: 'shop-doc__body' }, [
              el('b', { text: d.name }),
              el('span', { class: 'shop-badge shop-badge--ok', text: 'Sẵn sàng' })
            ]),
            // href is an https Drive link from our API; el() sets it as a plain attribute
            el('a', { class: 'fr-btn fr-btn--gold', href: d.drive_url, target: '_blank', rel: 'noopener noreferrer', text: 'Mở tài liệu (Google Drive)' })
          ]));
        });
        $('paidEmail').hidden = !o.email_sent;
        show('viewPaid');
        return false;
      }
      if (o.status === 'needs_review') { show('viewReview'); return true; }
      show('viewExpired');
      return false;
    }

    function poll() {
      api('/orders/' + encodeURIComponent(code) + '/status', { headers: { Authorization: 'Bearer ' + token } })
        .then(function (o) {
          $('pollError').hidden = true;
          if (render(o)) timer = setTimeout(poll, POLL_MS);
        })
        .catch(function (err) {
          if (err.status === 404) { show('viewMissing'); return; }
          $('pollError').hidden = false; // mất mạng tạm thời: thử lại
          timer = setTimeout(poll, POLL_MS * 2);
        });
    }

    // Kiểm tra ngay khi khách quay lại tab (vừa chuyển khoản trên app ngân hàng)
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden && !$('viewPending').hidden) { clearTimeout(timer); poll(); }
    });

    root.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-copy]');
      if (!btn || !btn.dataset.value) return;
      var done = function () {
        var old = btn.textContent;
        btn.textContent = 'Đã chép';
        setTimeout(function () { btn.textContent = old; }, 1500);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(btn.dataset.value).then(done, function () {});
    });

    poll();
  }

  function init() { initBuyButtons(); initCheckout(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
