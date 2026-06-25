/* ── ISARAL SaaS — home.js ── */

document.addEventListener('DOMContentLoaded', function () {

    /* ── Mobile Nav Toggle ── */
    const toggle = document.getElementById('navToggle');
    const navLinks = document.getElementById('navLinks');
    if (toggle && navLinks) {
        toggle.addEventListener('click', function () {
            navLinks.classList.toggle('open');
        });
        // Close on outside click
        document.addEventListener('click', function (e) {
            if (!toggle.contains(e.target) && !navLinks.contains(e.target)) {
                navLinks.classList.remove('open');
            }
        });
    }

    /* ── FAQ Accordion ── */
    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach(function (item) {
        const btn = item.querySelector('.faq-question');
        if (btn) {
            btn.addEventListener('click', function () {
                const isOpen = item.classList.contains('open');
                // Close all
                faqItems.forEach(function (i) { i.classList.remove('open'); });
                // Open clicked if it was closed
                if (!isOpen) { item.classList.add('open'); }
            });
        }
    });

    /* ── Sticky navbar shadow on scroll ── */
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', function () {
            if (window.scrollY > 10) {
                navbar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.12)';
            } else {
                navbar.style.boxShadow = '0 1px 0 #e5e7eb';
            }
        });
    }

});
