// Hero Grid Animation
function initHeroGrid() {
    const grid = document.getElementById('heroGrid');
    if (!grid) return;

    const cols = window.innerWidth < 768 ? 7 : 11;
    const rows = window.innerWidth < 768 ? 11 : 9;

    grid.style.setProperty('--cols', cols);
    grid.style.setProperty('--rows', rows);

    // Clear existing cells
    grid.innerHTML = '';

    // Calculate center cell index
    const totalCells = cols * rows;
    const centerRow = Math.floor(rows / 2);
    const centerCol = Math.floor(cols / 2);
    const centerIndex = centerRow * cols + centerCol;

    // Create cells
    for (let i = 0; i < totalCells; i++) {
        const cell = document.createElement('div');
        cell.className = 'cell';

        // Center cell gets the logo
        if (i === centerIndex) {
            cell.classList.add('logo-cell');
            // Use img tag for animated webp
            const logoImg = document.createElement('img');
            logoImg.src = 'images/logo-animated.webp';
            logoImg.alt = 'Nick Athens';
            logoImg.className = 'logo-img';
            cell.appendChild(logoImg);
        } else {
            // Random initial state for non-logo cells
            if (Math.random() > 0.5) {
                cell.classList.add('off');
            }
        }
        grid.appendChild(cell);
    }

    // Animate cells (excluding logo cell)
    const cells = grid.querySelectorAll('.cell:not(.logo-cell)');

    function animateCells() {
        // Pick random cells to toggle
        const numToToggle = Math.floor(Math.random() * 5) + 3;

        for (let i = 0; i < numToToggle; i++) {
            const randomIndex = Math.floor(Math.random() * cells.length);
            cells[randomIndex].classList.toggle('off');
        }
    }

    // Run animation every 300ms
    setInterval(animateCells, 300);
}

// Mobile Navigation
function initMobileNav() {
    const toggle = document.querySelector('.nav-toggle');
    const links = document.querySelector('.nav-links');

    if (toggle && links) {
        toggle.addEventListener('click', () => {
            links.classList.toggle('active');
        });

        // Close menu when clicking a link
        links.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                links.classList.remove('active');
            });
        });
    }
}

// Smooth scroll offset for fixed nav
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const navHeight = document.querySelector('.nav').offsetHeight;
                const targetPosition = target.offsetTop - navHeight;
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// Film Player
function initFilmPlayer() {
    const miniPlayer = document.getElementById('miniPlayer');
    const miniPlayerFrame = document.getElementById('miniPlayerFrame');
    const miniPlayerTitle = document.getElementById('miniPlayerTitle');
    const miniPlayerClose = document.getElementById('miniPlayerClose');
    const filmCards = document.querySelectorAll('.film-card[data-playlist]');

    if (!miniPlayer || !filmCards.length) return;

    filmCards.forEach(card => {
        card.addEventListener('click', () => {
            const playlistId = card.dataset.playlist;
            const title = card.querySelector('h3').textContent;

            // Remove playing class from all cards
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));

            // Add playing class to clicked card
            card.classList.add('playing');

            // Update mini player
            miniPlayerTitle.textContent = title;
            miniPlayerFrame.src = `https://www.youtube.com/embed/videoseries?list=${playlistId}&autoplay=1`;

            // Show player with animation
            miniPlayer.style.display = 'block';
            requestAnimationFrame(() => {
                miniPlayer.classList.add('active');
            });
        });
    });

    // Close button
    miniPlayerClose.addEventListener('click', () => {
        miniPlayer.classList.remove('active');
        setTimeout(() => {
            miniPlayer.style.display = 'none';
            miniPlayerFrame.src = '';
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
        }, 300);
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initHeroGrid();
    initMobileNav();
    initSmoothScroll();
    initFilmPlayer();
});

// Reinitialize grid on resize
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(initHeroGrid, 250);
});
