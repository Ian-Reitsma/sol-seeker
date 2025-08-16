const navToggle = document.getElementById('nav-toggle');
const sideMenu = document.getElementById('side-menu');
const overlay = document.getElementById('menuOverlay');
if (navToggle && sideMenu && overlay) {
    function openMenu() {
        navToggle.setAttribute('aria-expanded', 'true');
        sideMenu.classList.remove('hidden');
        overlay.classList.remove('hidden');
        const firstLink = sideMenu.querySelector('a');
        if (firstLink) firstLink.focus();
    }
    function closeMenu() {
        navToggle.setAttribute('aria-expanded', 'false');
        sideMenu.classList.add('hidden');
        overlay.classList.add('hidden');
        navToggle.focus();
    }
    navToggle.addEventListener('click', () => {
        const expanded = navToggle.getAttribute('aria-expanded') === 'true';
        expanded ? closeMenu() : openMenu();
    });
    overlay.addEventListener('click', closeMenu);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeMenu();
    });
}
