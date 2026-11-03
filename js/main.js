/**
 * Cơm Đốt Thố Hội An — Brand & Franchise Interaction
 * Apple Precision × Starbucks Warmth
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Intersection Observer for Apple-like smooth scroll reveal
  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach(el => observer.observe(el));
  } else {
    // Fallback if IntersectionObserver not supported
    reveals.forEach(el => el.classList.add('visible'));
  }

  // 2. Transparent to Glass Navbar on scroll
  const nav = document.getElementById('nav');
  if (nav) {
    const handleScroll = () => {
      nav.classList.toggle('scrolled', window.scrollY > 60);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll(); // Initial check
  }

  // 3. Smooth Anchor Navigation with header offset
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href');
      if (targetId && targetId !== '#') {
        const target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });

          // Close mobile menu if open
          const navLinks = document.querySelector('.nav__links');
          if (navLinks && window.innerWidth <= 768) {
            navLinks.style.display = 'none';
          }
        }
      }
    });
  });

  // 4. Mobile Hamburger Toggle
  const menuBtn = document.getElementById('menuBtn');
  const navLinks = document.querySelector('.nav__links');
  if (menuBtn && navLinks) {
    menuBtn.addEventListener('click', () => {
      const isHidden = window.getComputedStyle(navLinks).display === 'none';
      navLinks.style.display = isHidden ? 'flex' : 'none';
      if (isHidden) {
        navLinks.style.flexDirection = 'column';
        navLinks.style.position = 'absolute';
        navLinks.style.top = '100%';
        navLinks.style.left = '0';
        navLinks.style.right = '0';
        navLinks.style.background = 'rgba(24, 19, 16, 0.98)';
        navLinks.style.backdropFilter = 'blur(20px)';
        navLinks.style.webkitBackdropFilter = 'blur(20px)';
        navLinks.style.padding = '2rem 1.5rem';
        navLinks.style.gap = '1.25rem';
        navLinks.style.borderBottom = '1px solid rgba(217, 167, 86, 0.2)';
      }
    });
  }

  // 5. Store Filter tabs interaction
  const storeTabs = document.querySelectorAll('.stores-tab');
  storeTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      storeTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
    });
  });

  // 6. Franchise Form Submission Handler
  const franchiseForm = document.getElementById('franchiseForm');
  if (franchiseForm) {
    franchiseForm.addEventListener('submit', (e) => {
      e.preventDefault();
      alert('Cảm ơn quý đối tác đã quan tâm! Ban phát triển nhượng quyền Cơm Đốt Thố Hội An sẽ liên hệ tư vấn chi tiết trong vòng 24 giờ làm việc.');
      franchiseForm.reset();
    });
  }
});
