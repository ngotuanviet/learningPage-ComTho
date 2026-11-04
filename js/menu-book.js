/** Thực đơn dạng sổ: hai trang trên máy tính, một trang trên điện thoại. */
document.addEventListener('DOMContentLoaded', () => {
  const narrowScreen = matchMedia('(max-width: 640px)');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

  document.querySelectorAll('[data-menu-book]').forEach((book, bookIndex) => {
    const pages = [...book.querySelectorAll('.fr-mcell')];
    if (!pages.length) return;

    const labels = pages.map(page => page.closest('.fr-mrow').querySelector('.fr-mtag').textContent);
    const title = book.dataset.menuBook;
    let perView = narrowScreen.matches ? 1 : 2;
    let current = 0;
    let busy = false;
    let pointer = null;
    let suppressClickUntil = 0;
    let finishTurn = null;

    book.classList.add('fr-reader');
    book.setAttribute('role', 'region');
    book.setAttribute('aria-roledescription', 'quyển thực đơn');
    book.setAttribute('aria-label', `Thực đơn ${title}`);

    const caption = document.createElement('p');
    caption.className = 'fr-reader__caption';
    const stage = document.createElement('div');
    stage.className = 'fr-reader__stage';
    stage.id = `menu-book-${bookIndex + 1}`;
    stage.tabIndex = 0;
    stage.setAttribute('aria-label', `${title}. Dùng phím mũi tên trái hoặc phải để lật trang.`);

    pages.forEach((page, index) => {
      page.hidden = true;
      page.setAttribute('aria-label', `${title} — trang ${index + 1}: ${page.querySelector('img').alt}`);
      page.querySelector('img').draggable = false;
      stage.append(page);
    });

    const controls = document.createElement('div');
    controls.className = 'fr-reader__controls';
    const makeButton = (label, direction) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'fr-reader__button';
      button.setAttribute('aria-label', `${label} — ${title}`);
      button.setAttribute('aria-controls', stage.id);
      const icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="' + (direction < 0 ? 'm14 6-6 6 6 6' : 'm10 6 6 6-6 6') + '"/></svg>';
      button.innerHTML = direction < 0 ? `${icon}<span>${label}</span>` : `<span>${label}</span>${icon}`;
      button.addEventListener('click', () => goTo(current + direction * perView));
      return button;
    };
    const previous = makeButton('Trang trước', -1);
    const next = makeButton('Trang sau', 1);
    const counter = document.createElement('p');
    counter.className = 'fr-reader__counter';
    counter.setAttribute('role', 'status');
    counter.setAttribute('aria-live', 'polite');
    counter.setAttribute('aria-atomic', 'true');
    controls.append(previous, counter, next);

    const hint = document.createElement('p');
    hint.className = 'fr-reader__hint';
    hint.textContent = 'Vuốt sang trái để lật trang · Chạm ảnh để phóng to';
    book.replaceChildren(caption, stage, controls, hint);

    const lastStart = () => Math.floor((pages.length - 1) / perView) * perView;
    const show = (index, column) => {
      if (!pages[index]) return;
      pages[index].hidden = false;
      pages[index].style.gridColumn = String(column);
      pages[index].querySelector('img').loading = 'eager';
    };
    const hidePages = () => pages.forEach(page => { page.hidden = true; });
    const updateControls = () => {
      previous.disabled = busy || current === 0;
      next.disabled = busy || current === lastStart();
    };
    const render = () => {
      hidePages();
      for (let offset = 0; offset < perView; offset++) show(current + offset, offset + 1);
      book.dataset.page = String(current + 1);
      book.dataset.pagesPerView = String(perView);
      caption.textContent = labels[current];
      const end = Math.min(current + perView, pages.length);
      counter.textContent = `Trang ${current + 1}${end > current + 1 ? '–' + end : ''} / ${pages.length}`;
      updateControls();
      // Tải trước trang lân cận để lúc lật không xuất hiện ảnh trống.
      for (let index = Math.max(0, current - perView); index < Math.min(pages.length, current + perView * 2); index++) {
        pages[index].querySelector('img').loading = 'eager';
      }
    };

    const makeFace = (index, side) => {
      const face = document.createElement('span');
      face.className = `fr-reader__face fr-reader__face--${side}`;
      if (pages[index]) {
        const img = pages[index].querySelector('img').cloneNode();
        img.alt = '';
        img.loading = 'eager';
        face.append(img);
      }
      return face;
    };

    function goTo(index, animate = true) {
      if (busy) return;
      const target = Math.max(0, Math.min(lastStart(), index));
      if (target === current) return;
      if (!animate || reducedMotion.matches || !Element.prototype.animate) {
        current = target;
        render();
        return;
      }

      busy = true;
      updateControls();
      const forward = target > current;
      const leaf = document.createElement('div');
      leaf.className = `fr-reader__leaf${perView === 1 ? ' fr-reader__leaf--single' : forward ? ' fr-reader__leaf--right' : ' fr-reader__leaf--left'}`;
      leaf.setAttribute('aria-hidden', 'true');
      hidePages();

      let from = 0;
      let to = forward ? -180 : 180;
      if (perView === 2) {
        show(forward ? current : target, 1);
        show(forward ? target + 1 : current + 1, 2);
        leaf.append(makeFace(forward ? current + 1 : current, 'front'), makeFace(forward ? target : target + 1, 'back'));
      } else {
        show(forward ? target : current, 1);
        leaf.append(makeFace(forward ? current : target, 'front'), makeFace(forward ? target : current, 'back'));
        if (!forward) { from = -180; to = 0; }
      }

      stage.append(leaf);
      const animation = leaf.animate([
        { transform: `rotateY(${from}deg)` },
        { transform: `rotateY(${to}deg)` }
      ], { duration: 580, easing: 'cubic-bezier(0.32, 0.72, 0, 1)', fill: 'forwards' });

      let finished = false;
      finishTurn = () => {
        if (finished) return;
        finished = true;
        animation.cancel();
        leaf.remove();
        current = target;
        busy = false;
        finishTurn = null;
        render();
      };
      animation.finished.then(finishTurn, () => {});
    }

    stage.addEventListener('dragstart', event => event.preventDefault());
    stage.addEventListener('pointerdown', event => {
      if (!event.isPrimary || event.button !== 0 || busy) return;
      pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, time: performance.now(), dragging: false };
      suppressClickUntil = 0;
    });
    stage.addEventListener('pointermove', event => {
      if (!pointer || pointer.id !== event.pointerId) return;
      const dx = event.clientX - pointer.x;
      const dy = event.clientY - pointer.y;
      if (!pointer.dragging && Math.abs(dy) > 12 && Math.abs(dy) > Math.abs(dx)) {
        pointer = null;
        return;
      }
      if (Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.2) {
        pointer.dragging = true;
        stage.classList.add('is-dragging');
        if (!stage.hasPointerCapture(event.pointerId)) stage.setPointerCapture(event.pointerId);
      }
    });
    stage.addEventListener('pointerup', event => {
      if (!pointer || pointer.id !== event.pointerId) return;
      const dx = event.clientX - pointer.x;
      const dy = event.clientY - pointer.y;
      const dragged = pointer.dragging;
      const tap = !dragged && Math.abs(dx) < 10 && Math.abs(dy) < 10 && performance.now() - pointer.time < 500;
      pointer = null;
      stage.classList.remove('is-dragging');
      if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
      if (dragged) suppressClickUntil = performance.now() + 500;
      if (Math.abs(dx) >= Math.max(36, stage.clientWidth * 0.08) && Math.abs(dx) > Math.abs(dy) * 1.2) {
        goTo(current + (dx < 0 ? perView : -perView));
      } else if (tap && event.pointerType === 'touch') {
        // Sau khi kéo, một số trình duyệt không phát click tương thích cho lần chạm tiếp theo.
        const imageLink = event.target.closest('[data-lightbox]');
        if (imageLink && stage.contains(imageLink)) {
          imageLink.click();
          suppressClickUntil = performance.now() + 500;
        }
      }
    });
    stage.addEventListener('pointercancel', () => {
      pointer = null;
      stage.classList.remove('is-dragging');
    });
    stage.addEventListener('click', event => {
      if (performance.now() < suppressClickUntil || busy) {
        event.preventDefault();
        event.stopPropagation();
      }
    }, true);

    book.addEventListener('keydown', event => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const jumps = { ArrowLeft: current - perView, ArrowRight: current + perView, Home: 0, End: lastStart() };
      if (!(event.key in jumps)) return;
      event.preventDefault();
      goTo(jumps[event.key], event.key !== 'Home' && event.key !== 'End');
    });

    narrowScreen.addEventListener('change', () => {
      if (finishTurn) finishTurn();
      pointer = null;
      stage.classList.remove('is-dragging');
      perView = narrowScreen.matches ? 1 : 2;
      current = Math.floor(current / perView) * perView;
      render();
    });
    reducedMotion.addEventListener('change', () => { if (reducedMotion.matches && finishTurn) finishTurn(); });
    render();
  });
});
