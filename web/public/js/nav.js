const navToggle = document.getElementById('nav-toggle');
const sideMenu = document.getElementById('side-menu');
const overlay = document.getElementById('menuOverlay');
if (navToggle && sideMenu && overlay) {
    let trapHandler;
    function openMenu() {
        navToggle.setAttribute('aria-expanded', 'true');
        sideMenu.classList.remove('hidden');
        overlay.classList.remove('hidden');
        const focusable = sideMenu.querySelectorAll('a, button');
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        trapHandler = (e) => {
            if (e.key === 'Tab') {
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            } else if (e.key === 'Escape') {
                closeMenu();
            }
        };
        document.addEventListener('keydown', trapHandler);
        if (first) first.focus();
    }
    function closeMenu() {
        navToggle.setAttribute('aria-expanded', 'false');
        sideMenu.classList.add('hidden');
        overlay.classList.add('hidden');
        document.removeEventListener('keydown', trapHandler);
        navToggle.focus();
    }
    navToggle.addEventListener('click', () => {
        const expanded = navToggle.getAttribute('aria-expanded') === 'true';
        expanded ? closeMenu() : openMenu();
    });
    overlay.addEventListener('click', closeMenu);
}
