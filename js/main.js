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

// Audio Player
function initAudioPlayer() {
    const player = document.getElementById('audioPlayer');
    const audio = document.getElementById('audioElement');
    const projectEl = document.getElementById('audioPlayerProject');
    const titleEl = document.getElementById('audioPlayerTitle');
    const infoEl = document.getElementById('audioPlayerInfo');
    const progressBar = document.getElementById('audioPlayerProgressBar');
    const progressContainer = document.getElementById('audioPlayerProgress');
    const currentTimeEl = document.getElementById('audioPlayerCurrent');
    const durationEl = document.getElementById('audioPlayerDuration');
    const playBtn = document.getElementById('audioPlayerPlay');
    const prevBtn = document.getElementById('audioPlayerPrev');
    const nextBtn = document.getElementById('audioPlayerNext');
    const closeBtn = document.getElementById('audioPlayerClose');
    const playlistContainer = document.getElementById('audioPlayerPlaylist');
    const filmCards = document.querySelectorAll('.film-card[data-tracks]');

    if (!player || !audio) return;

    let currentPlaylist = [];
    let currentIndex = 0;
    let isPlaying = false;

    // Format time as m:ss
    function formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // Update play/pause button
    function updatePlayButton() {
        const playIcon = playBtn.querySelector('.play-icon');
        const pauseIcon = playBtn.querySelector('.pause-icon');
        playIcon.style.display = isPlaying ? 'none' : 'block';
        pauseIcon.style.display = isPlaying ? 'block' : 'none';
    }

    // Load track
    function loadTrack(index) {
        if (index < 0 || index >= currentPlaylist.length) return;
        currentIndex = index;
        const track = currentPlaylist[index];

        audio.src = track.src;
        titleEl.textContent = track.title;
        infoEl.textContent = `${index + 1} of ${currentPlaylist.length}`;

        // Update playlist UI
        playlistContainer.querySelectorAll('.audio-player-playlist-item').forEach((item, i) => {
            item.classList.toggle('active', i === index);
        });

        progressBar.style.width = '0%';
        currentTimeEl.textContent = '0:00';
    }

    // Play/pause
    function togglePlay() {
        if (isPlaying) {
            audio.pause();
        } else {
            audio.play();
        }
    }

    // Previous track
    function prevTrack() {
        if (audio.currentTime > 3) {
            audio.currentTime = 0;
        } else {
            loadTrack(currentIndex - 1);
            if (isPlaying) audio.play();
        }
    }

    // Next track
    function nextTrack() {
        if (currentIndex < currentPlaylist.length - 1) {
            loadTrack(currentIndex + 1);
            if (isPlaying) audio.play();
        }
    }

    // Build playlist UI
    function buildPlaylist(tracks) {
        playlistContainer.innerHTML = '';
        tracks.forEach((track, i) => {
            const item = document.createElement('div');
            item.className = 'audio-player-playlist-item' + (i === 0 ? ' active' : '');
            item.innerHTML = `
                <span class="audio-player-playlist-num">${i + 1}</span>
                <span class="audio-player-playlist-name">${track.title}</span>
                <span class="audio-player-playlist-duration">${track.duration || ''}</span>
            `;
            item.addEventListener('click', () => {
                loadTrack(i);
                audio.play();
            });
            playlistContainer.appendChild(item);
        });
    }

    // Show player with tracks
    function showPlayer(projectName, tracks) {
        currentPlaylist = tracks;
        projectEl.textContent = projectName;
        buildPlaylist(tracks);
        loadTrack(0);

        player.style.display = 'block';
        requestAnimationFrame(() => {
            player.classList.add('active');
        });
    }

    // Hide player
    function hidePlayer() {
        audio.pause();
        isPlaying = false;
        updatePlayButton();
        player.classList.remove('active');
        setTimeout(() => {
            player.style.display = 'none';
            audio.src = '';
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.embla-photo.playing').forEach(c => c.classList.remove('playing'));
        }, 300);
    }

    // Event listeners
    playBtn.addEventListener('click', togglePlay);
    prevBtn.addEventListener('click', prevTrack);
    nextBtn.addEventListener('click', nextTrack);
    closeBtn.addEventListener('click', hidePlayer);

    audio.addEventListener('play', () => {
        isPlaying = true;
        updatePlayButton();
    });

    audio.addEventListener('pause', () => {
        isPlaying = false;
        updatePlayButton();
    });

    audio.addEventListener('timeupdate', () => {
        if (audio.duration) {
            const progress = (audio.currentTime / audio.duration) * 100;
            progressBar.style.width = progress + '%';
            currentTimeEl.textContent = formatTime(audio.currentTime);
        }
    });

    audio.addEventListener('loadedmetadata', () => {
        durationEl.textContent = formatTime(audio.duration);
    });

    audio.addEventListener('ended', () => {
        if (currentIndex < currentPlaylist.length - 1) {
            nextTrack();
        } else {
            isPlaying = false;
            updatePlayButton();
        }
    });

    // Progress bar click to seek
    progressContainer.addEventListener('click', (e) => {
        const rect = progressContainer.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        audio.currentTime = percent * audio.duration;
    });

    // Film card clicks
    filmCards.forEach(card => {
        card.addEventListener('click', () => {
            const tracksData = card.dataset.tracks;
            const title = card.querySelector('h3').textContent;

            // Parse tracks JSON
            let tracks;
            try {
                tracks = JSON.parse(tracksData);
            } catch (e) {
                console.error('Invalid tracks data');
                return;
            }

            // Remove playing class from all cards and embla
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.embla-photo.playing').forEach(c => c.classList.remove('playing'));
            card.classList.add('playing');

            showPlayer(title, tracks);
            audio.play();
        });
    });

    // Embla photo click - supports multiple albums with random album selection
    const emblaPhoto = document.querySelector('.embla-photo');
    if (emblaPhoto) {
        emblaPhoto.addEventListener('click', () => {
            const albumsData = emblaPhoto.dataset.albums;
            const tracksData = emblaPhoto.dataset.tracks;

            let tracks;
            let albumName = 'Of Embla';

            // If albums data exists, pick a random album
            if (albumsData) {
                try {
                    const albums = JSON.parse(albumsData);
                    const randomAlbum = albums[Math.floor(Math.random() * albums.length)];
                    tracks = randomAlbum.tracks;
                    albumName = 'Of Embla - ' + randomAlbum.name;
                } catch (e) {
                    console.error('Invalid albums data');
                    return;
                }
            } else if (tracksData) {
                // Fallback to single tracks list
                try {
                    tracks = JSON.parse(tracksData);
                } catch (e) {
                    console.error('Invalid tracks data');
                    return;
                }
            } else {
                return;
            }

            // Remove playing class from all cards and embla
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.embla-photo.playing').forEach(c => c.classList.remove('playing'));
            emblaPhoto.classList.add('playing');

            showPlayer(albumName, tracks);
            audio.play();
        });
    }

    // Expose for external use
    window.audioPlayer = {
        show: showPlayer,
        hide: hidePlayer
    };
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initHeroGrid();
    initMobileNav();
    initSmoothScroll();
    initAudioPlayer();
});

// Reinitialize grid on resize
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(initHeroGrid, 250);
});
