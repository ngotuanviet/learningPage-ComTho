/* Bán tài liệu số: nút "Mua ngay" + trang checkout.
 * Giá, trạng thái và link tài liệu luôn lấy từ API. Trang này không bao giờ tự đặt "đã thanh toán".
 */
(function () {
  'use strict';

  // Địa chỉ backend. Chạy local thì tự dùng localhost:8000.
  var PROD_API = 'https://comtho-api.vercel.app'; // đổi khi có domain riêng (nhớ thêm domain web vào PUBLIC_ALLOWED_ORIGINS)
  // Mặc định luôn dùng API thật (kể cả khi xem trang ở máy).
  // Lập trình viên thử với API local: mở trang kèm ?api=local (được nhớ trong tab này).
  function pickApi() {
    var wanted = new URLSearchParams(location.search).get('api');
    try {
      if (wanted === 'local' || wanted === 'prod') sessionStorage.setItem('shop:api', wanted);
      wanted = sessionStorage.getItem('shop:api');
    } catch (e) { /* private mode */ }
    return wanted === 'local' ? 'http://localhost:8000' : PROD_API;
  }
  var API = (window.SHOP_API || pickApi()) + '/api/v1';
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
          if (res.status === 422) msg = 'Vui lòng kiểm tra lại số điện thoại.';
          var err = new Error(msg); err.status = res.status; throw err;
        }
        return data;
      });
    });
  }

  // Kept in localStorage so the order survives switching to the bank app, the browser
  // closing the tab, or reopening the checkout link later (session copy as a fallback).
  function saveToken(code, token) {
    try { localStorage.setItem('shop:' + code, token); } catch (e) { /* private mode */ }
    try { sessionStorage.setItem('shop:' + code, token); } catch (e) { /* private mode */ }
  }
  function loadToken(code) {
    var t = null;
    try { t = localStorage.getItem('shop:' + code); } catch (e) { /* blocked */ }
    if (!t) { try { t = sessionStorage.getItem('shop:' + code); } catch (e) { /* blocked */ } }
    return t;
  }

  /* ---------- Nút "Mua ngay" ---------- */

  // Nút có data-buy="<slug>". Nút ẩn sẵn (hidden) chỉ hiện khi lấy được giá;
  // nút dạng link luôn hiện, API lỗi thì vẫn đi theo href (trang đăng ký tư vấn).
  // data-buy-label: giữ nhãn cố định (vd "Mua Ngay"); không có thì hiện kèm giá.
  // Phần tử data-buy-price="<slug>" được điền giá bán thật.
  // Khối data-deal="<slug>" được điền giá gốc (gạch), giá bán và % giảm.
  function percentOff(p) {
    return p.list_price && p.list_price > p.price ? Math.round((1 - p.price / p.list_price) * 100) : 0;
  }

  function renderDeal(box, p) {
    var off = percentOff(p);
    box.querySelectorAll('[data-deal-price]').forEach(function (n) { n.textContent = vnd(p.price); });
    box.querySelectorAll('[data-deal-list]').forEach(function (n) { n.textContent = vnd(p.list_price || p.price); });
    box.querySelectorAll('[data-deal-off]').forEach(function (n) { n.textContent = '-' + off + '%'; n.hidden = !off; });
    box.querySelectorAll('[data-deal-was]').forEach(function (n) { n.hidden = !off; });
  }

  function initBuyButtons() {
    var slugs = {};
    document.querySelectorAll('[data-buy], [data-buy-price], [data-deal]').forEach(function (n) {
      slugs[n.getAttribute('data-buy') || n.getAttribute('data-buy-price') || n.getAttribute('data-deal')] = true;
    });
    Object.keys(slugs).forEach(function (slug) {
      api('/products/' + encodeURIComponent(slug)).then(function (product) {
        document.querySelectorAll('[data-buy-price="' + slug + '"]').forEach(function (n) {
          n.textContent = vnd(product.price);
        });
        document.querySelectorAll('[data-deal="' + slug + '"]').forEach(function (box) { renderDeal(box, product); });
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

  // Giá gạch + giá bán + % giảm, dùng trong hộp mua (gói chính và gói mua kèm).
  function dealLine(p, cls, sign) {
    var off = percentOff(p);
    return el('span', { class: 'shop-dealline ' + cls }, [
      off ? el('s', { class: 'shop-dealline__was', text: vnd(p.list_price) }) : null,
      el('strong', { class: 'shop-dealline__now', text: (sign || '') + vnd(p.price) }),
      off ? el('em', { class: 'shop-dealline__off', text: '-' + off + '%' }) : null
    ]);
  }

  var dialog;
  function openBuyDialog(product) {
    if (dialog) dialog.remove();
    var msg = el('p', { class: 'fr-form__msg', role: 'alert' });
    var submit = el('button', { type: 'submit', class: 'fr-btn fr-btn--gold fr-btn--round', text: 'Tiếp tục thanh toán' });
    var addons = el('div', { class: 'shop-addons' });
    var total = el('strong', { class: 'shop-total__value', text: vnd(product.price) });
    var form = el('form', { class: 'shop-dialog__form', novalidate: '' }, [
      addons,
      el('div', { class: 'shop-total' }, [el('span', { text: 'Tổng thanh toán' }), total]),
      el('div', { class: 'form-group' }, [
        el('label', { class: 'form-label', for: 'shop-phone', text: 'Số điện thoại *' }),
        el('input', { id: 'shop-phone', name: 'phone', type: 'tel', inputmode: 'tel', class: 'form-input', required: '', maxlength: '20', autocomplete: 'tel', enterkeyhint: 'go', placeholder: '09xx xxx xxx' })
      ]),
      el('p', { class: 'shop-dialog__hint', text: 'Link tài liệu hiện ngay sau khi chuyển khoản thành công. Chúng tôi chỉ dùng số điện thoại để hỗ trợ khi bạn cần.' }),
      el('div', { class: 'fr-form__foot' }, [submit]),
      msg
    ]);
    var close = el('button', { type: 'button', class: 'shop-dialog__close', 'aria-label': 'Đóng', text: '×' });
    dialog = el('dialog', { class: 'shop-dialog', 'aria-labelledby': 'shop-dialog-title' }, [
      close,
      el('span', { class: 'fr-eyebrow', text: 'Tài liệu số' }),
      el('h2', { id: 'shop-dialog-title', class: 'fr-form__title', text: product.name }),
      dealLine(product, 'shop-dialog__price'),
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
          dealLine(p, 'shop-addon__price', '+')
        ]));
        extras.push({ product: p, box: box });
      });
      addons.hidden = !extras.length;
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var phoneInput = form.querySelector('#shop-phone');
      var phone = phoneInput.value.trim();
      // Same rule as the server: 10 digits starting with 03/05/07/08/09 (+84 allowed).
      var digits = phone.replace(/[\s.\-()]/g, '').replace(/^\+?84(?=\d{9}$)/, '0');
      var ok = /^0[35789]\d{8}$/.test(digits);
      phoneInput.classList.toggle('invalid', !ok);
      if (!ok) {
        msg.className = 'fr-form__msg err';
        msg.textContent = 'Vui lòng nhập số điện thoại hợp lệ (10 số, vd 0912 345 678).';
        phoneInput.focus();
        return;
      }
      submit.disabled = true;
      submit.textContent = 'Đang tạo đơn…';
      msg.textContent = '';
      var slugs = selected().map(function (p) { return p.slug; });
      var body = { customer_phone: digits };
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
    // Keep the field and the pay button visible above the on-screen keyboard.
    form.querySelector('#shop-phone').addEventListener('focus', function (e) {
      setTimeout(function () { e.target.scrollIntoView({ block: 'center', behavior: 'smooth' }); }, 300);
    });
    dialog.showModal();
    // Phones: no keyboard until the buyer taps the phone field.
    if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) form.querySelector('#shop-phone').focus();
    else { dialog.setAttribute('tabindex', '-1'); dialog.focus(); dialog.scrollTop = 0; }
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

    // "Lưu ảnh QR": the API returns the PNG (vietqr.app blocks direct browser downloads).
    // Fetched in advance so the tap can open the share sheet at once (iPhone needs that).
    var qrFile = null, qrFor = null;
    function prepareQrSave(code, url) {
      var btn = $('payQrSave');
      if (!btn) return;
      btn.dataset.fallback = url;
      if (qrFor === code) return;
      qrFor = code;
      fetch(API + '/orders/' + encodeURIComponent(code) + '/qr', { headers: { Authorization: 'Bearer ' + token }, cache: 'no-store', credentials: 'omit' })
        .then(function (r) { if (!r.ok) throw new Error(); return r.blob(); })
        .then(function (b) { qrFile = new File([b], 'QR-' + code + '.png', { type: 'image/png' }); })
        .catch(function () { qrFile = null; });
    }
    function saveQr() {
      var btn = $('payQrSave'), done = $('payQrSaved');
      function ok(text) { if (done) { done.textContent = text; done.hidden = false; } }
      if (!qrFile) { window.open(btn.dataset.fallback, '_blank', 'noopener'); ok('Ảnh QR đã mở ở thẻ mới: nhấn giữ ảnh → Lưu ảnh.'); return; }
      var touch = window.matchMedia('(pointer: coarse)').matches;
      if (touch && navigator.canShare && navigator.canShare({ files: [qrFile] })) {
        navigator.share({ files: [qrFile] })
          .then(function () { ok('Đã lưu. Mở app ngân hàng → Quét QR → chọn ảnh vừa lưu.'); })
          .catch(function (e) { if (e && e.name !== 'AbortError') download(); });
        return;
      }
      download();
      function download() {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(qrFile);
        a.download = qrFile.name;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
        ok(touch ? 'Đã tải ảnh QR. Mở app ngân hàng → Quét QR → chọn ảnh vừa lưu.' : 'Đã tải ảnh QR về máy (thư mục Tải xuống).');
      }
    }
    if ($('payQrSave')) $('payQrSave').addEventListener('click', function (e) { e.preventDefault(); saveQr(); });

    function render(o) {
      document.querySelectorAll('[data-order-code]').forEach(function (n) { n.textContent = o.code; });
      document.querySelectorAll('[data-order-product]').forEach(function (n) { n.textContent = o.product_name; });
      document.querySelectorAll('[data-order-amount]').forEach(function (n) { n.textContent = vnd(o.amount); });

      if (o.status === 'pending' && o.payment) {
        var p = o.payment;
        $('payQr').src = p.qr_url;
        prepareQrSave(o.code, p.qr_url);
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

  // ---- Popup chính sách bản quyền (link [data-policy]) ----
  var POLICY = [
    ['1. Quyền sở hữu', 'Toàn bộ nội dung tài liệu (công thức, định lượng, quy trình chế biến và vận hành, hình ảnh, video, biểu mẫu) thuộc quyền sở hữu của VFXGroup và được bảo hộ theo pháp luật Việt Nam về sở hữu trí tuệ.'],
    ['2. Phạm vi được sử dụng', 'Người mua được dùng tài liệu cho hoạt động kinh doanh của chính mình, được lưu trữ và in ấn để đào tạo nhân viên nội bộ.'],
    ['3. Hành vi bị nghiêm cấm', 'Sao chép, chia sẻ link tài liệu, đăng tải lên mạng, phân phối, mua bán, cho thuê hoặc khai thác thương mại tài liệu dưới bất kỳ hình thức nào khi chưa có sự đồng ý bằng văn bản của VFXGroup.'],
    ['4. Xử lý vi phạm', 'VFXGroup có quyền yêu cầu chấm dứt hành vi vi phạm, gỡ bỏ nội dung, bồi thường thiệt hại và xử lý theo quy định của pháp luật về sở hữu trí tuệ.'],
    ['5. Liên hệ', 'Cần sử dụng tài liệu ngoài phạm vi trên, vui lòng liên hệ hotline 097 538 88 86 để được hỗ trợ.']
  ];
  function openPolicy() {
    var close = el('button', { type: 'button', class: 'shop-dialog__close', 'aria-label': 'Đóng', text: '×' });
    var body = el('div', { class: 'shop-policy__body' }, POLICY.map(function (s) {
      return el('section', {}, [el('h3', { text: s[0] }), el('p', { text: s[1] })]);
    }));
    var dlg = el('dialog', { class: 'shop-dialog shop-policy', 'aria-labelledby': 'shop-policy-title' }, [
      close,
      el('p', { class: 'fr-eyebrow', text: 'VFXGroup' }),
      el('h2', { id: 'shop-policy-title', class: 'fr-form__title', text: 'Chính sách bản quyền và sử dụng tài liệu' }),
      body
    ]);
    close.addEventListener('click', function () { dlg.close(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener('close', function () { dlg.remove(); });
    document.body.appendChild(dlg);
    dlg.showModal();
  }
  function initPolicy() {
    document.querySelectorAll('[data-policy]').forEach(function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); openPolicy(); });
    });
  }

  function init() { initBuyButtons(); initCheckout(); initPolicy(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
