/**
 * Câu hook trên trang chủ (chuyển cảnh sang cau-chuyen.html)
 * và hiệu ứng đọc truyện: hiện dần từng dòng, thanh tiến độ cuộn.
 */
document.addEventListener('DOMContentLoaded', () => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── Trang chủ: bấm nút -> tối dần rồi sang trang câu chuyện ──
  const go = document.querySelector('.st-hook__btn');
  if (go) {
    const curtain = document.createElement('div');
    curtain.className = 'st-curtain';
    curtain.setAttribute('aria-hidden', 'true');
    document.body.appendChild(curtain);
    go.addEventListener('click', (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault();
      curtain.classList.add('on');
      setTimeout(() => { location.href = go.href; }, reduce ? 0 : 700);
    });
    // quay lại bằng nút Back (bfcache) thì bỏ màn tối
    window.addEventListener('pageshow', (e) => { if (e.persisted) curtain.classList.remove('on'); });
  }

  // ── Trang câu chuyện ──
  const items = document.querySelectorAll('.st-r');
  if (!items.length) return;
  if ('IntersectionObserver' in window && !reduce) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(en => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
    }, { threshold: 0.2, rootMargin: '0px 0px -8% 0px' });
    items.forEach(el => io.observe(el));
  } else {
    items.forEach(el => el.classList.add('in'));
  }

  const bar = document.querySelector('.st-bar');
  if (bar) {
    const upd = () => {
      const h = document.documentElement.scrollHeight - innerHeight;
      bar.style.transform = 'scaleX(' + (h > 0 ? Math.min(1, scrollY / h) : 0) + ')';
    };
    addEventListener('scroll', upd, { passive: true });
    addEventListener('resize', upd);
    upd();
  }
});
