// Hero Grid Animation

// Full chromatic scale frequencies across octaves (C2 to C6)
// More notes = more variation when Smart Harmony is on
const tuningFrequencies = [
    // C notes
    65.41,   // C2
    130.81,  // C3
    261.63,  // C4 (middle C)
    523.25,  // C5
    // D notes
    73.42,   // D2
    146.83,  // D3
    293.66,  // D4
    587.33,  // D5
    // E notes
    82.41,   // E2
    164.81,  // E3
    329.63,  // E4
    659.25,  // E5
    // F notes
    87.31,   // F2
    174.61,  // F3
    349.23,  // F4
    698.46,  // F5
    // G notes
    98.00,   // G2
    196.00,  // G3
    392.00,  // G4
    783.99,  // G5
    // A notes
    110.00,  // A2
    220.00,  // A3
    440.00,  // A4 (concert pitch)
    880.00,  // A5
    // B notes
    123.47,  // B2
    246.94,  // B3
    493.88,  // B4
    987.77   // B5
];

// Color palette for grid cells
const cellColors = [
    '#e63946', '#f4a261', '#e9c46a', '#2a9d8f', '#264653',
    '#9b5de5', '#f15bb5', '#00bbf9', '#00f5d4', '#fee440'
];

// Audio context for synthesized notes - initialize once and keep alive
let audioContext = null;
let tuningEnabled = true;
let synthVolume = 0.5; // 0-1 range, default 50%
let smartHarmony = false; // When true, notes are harmonically intelligent

// Smart Harmony System
// Based on pentatonic scale (impossible to sound bad) with true probabilistic voicing
// Research-backed: Eno's generative principles, modal jazz, spectral music

// Pentatonic scale intervals (semitones from root) - no dissonance possible
// These are the "safe" intervals that always sound good together
const PENTATONIC_INTERVALS = [0, 2, 4, 7, 9]; // Major pentatonic: C D E G A

// Consonant voicing intervals in cents (100 cents = 1 semitone)
// Ordered by consonance (simpler frequency ratios = more consonant)
const CONSONANT_INTERVALS = {
    unison: 0,
    octave: 1200,
    fifth: 700,
    fourth: 500,
    majorThird: 400,
    minorThird: 300,
    majorSixth: 900,
    minorSixth: 800
};

// Get how many notes are currently sounding (not released)
function getPlayingCount() {
    let count = 0;
    activeNotes.forEach(note => {
        if (!note.released) count++;
    });
    return count;
}

// Determine voicing size (1, 2, or 3 notes) with true probability
function getVoicingSize() {
    const playingCount = getPlayingCount();
    const roll = Math.random();

    // Base probabilities: 50% single, 35% dyad, 15% triad
    // These shift dramatically based on density

    if (playingCount === 0) {
        // Nothing playing - can be rich
        if (roll < 0.40) return 1;      // 40% single
        if (roll < 0.75) return 2;      // 35% dyad
        return 3;                        // 25% triad
    } else if (playingCount === 1) {
        // One note - still room for richness
        if (roll < 0.50) return 1;      // 50% single
        if (roll < 0.85) return 2;      // 35% dyad
        return 3;                        // 15% triad
    } else if (playingCount === 2) {
        // Getting full - favor singles
        if (roll < 0.65) return 1;      // 65% single
        if (roll < 0.95) return 2;      // 30% dyad
        return 3;                        // 5% triad
    } else {
        // Dense - almost always single
        if (roll < 0.85) return 1;      // 85% single
        return 2;                        // 15% dyad, no triads
    }
}

// Pick consonant intervals for a chord voicing
function pickIntervals(size) {
    if (size === 1) return [0];

    const intervals = [0]; // Root always included
    const roll = Math.random();

    if (size >= 2) {
        // Pick second note - favor fifths and octaves heavily
        if (roll < 0.35) {
            intervals.push(CONSONANT_INTERVALS.fifth);           // Perfect 5th (most common)
        } else if (roll < 0.55) {
            intervals.push(CONSONANT_INTERVALS.octave);          // Octave
        } else if (roll < 0.70) {
            intervals.push(CONSONANT_INTERVALS.fourth);          // Perfect 4th
        } else if (roll < 0.80) {
            intervals.push(-CONSONANT_INTERVALS.fifth);          // 5th below (inverted)
        } else if (roll < 0.90) {
            intervals.push(CONSONANT_INTERVALS.majorThird);      // Major 3rd
        } else {
            intervals.push(CONSONANT_INTERVALS.minorThird);      // Minor 3rd
        }
    }

    if (size >= 3) {
        // Pick third note - add octave displacement or another consonance
        const roll2 = Math.random();
        if (roll2 < 0.30) {
            intervals.push(CONSONANT_INTERVALS.octave);          // Add octave
        } else if (roll2 < 0.50) {
            intervals.push(-CONSONANT_INTERVALS.octave);         // Octave below
        } else if (roll2 < 0.70) {
            intervals.push(CONSONANT_INTERVALS.fifth + CONSONANT_INTERVALS.octave); // 5th + octave
        } else if (roll2 < 0.85) {
            intervals.push(CONSONANT_INTERVALS.fourth);          // Add 4th if not there
        } else {
            intervals.push(CONSONANT_INTERVALS.fifth * 2);       // Stacked 5th (9th)
        }
    }

    return intervals;
}

// Main harmony function - returns intervals in cents
function getSmartIntervals(baseFreq) {
    const size = getVoicingSize();
    const intervals = pickIntervals(size);

    // Add subtle random variation to keep it interesting
    // Sometimes shift intervals up/down an octave for register variety
    if (Math.random() < 0.15 && intervals.length > 1) {
        // Occasionally drop root down an octave for width
        intervals[0] = -1200;
    }

    return intervals;
}

// Active notes - now tracked by pointerId for absolute reliability
// Key: pointerId, Value: note object
const notesByPointer = new Map();

// Also track by cell for legacy compatibility (cell -> note)
const activeNotes = new Map();

// Initialize audio context immediately on first user interaction
function ensureAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }
    return audioContext;
}

// Play a tuning note with modulation support (supports smart harmony)
// Returns note object for modulation control
function playTuningNote(cell) {
    if (!tuningEnabled) return null;

    const ctx = ensureAudioContext();
    const now = ctx.currentTime;

    // Pick a random orchestral tuning frequency
    const baseFrequency = tuningFrequencies[Math.floor(Math.random() * tuningFrequencies.length)];

    // Get chord voicing intervals - smart or single note
    const intervals = smartHarmony ? getSmartIntervals(baseFrequency) : [0];

    // Arrays to hold all oscillators/filters for the chord
    const oscillators = [];
    const filters = [];

    // Create a single gain node for the whole chord
    const gainNode = ctx.createGain();
    gainNode.connect(ctx.destination);

    // Calculate gain per voice (divide total gain among chord tones)
    const targetGain = (0.15 * synthVolume) / Math.sqrt(intervals.length);

    // Create an oscillator + filter for each interval in the chord
    intervals.forEach((cents, index) => {
        const oscillator = ctx.createOscillator();
        const filter = ctx.createBiquadFilter();

        // Use sawtooth wave - closer to string instrument timbre
        oscillator.type = 'sawtooth';

        // Calculate frequency from cents (100 cents = 1 semitone)
        const ratio = Math.pow(2, cents / 1200);
        oscillator.frequency.value = baseFrequency * ratio;

        // Add slight detune for more organic feel (like strings settling)
        // Each voice gets slightly different detune for richness
        oscillator.detune.value = (Math.random() - 0.5) * 15 + (index * 2);

        // Low-pass filter starts partially closed for modulation range
        filter.type = 'lowpass';
        filter.frequency.value = 1000;
        filter.Q.value = 1;

        // Chain: oscillator -> filter -> gain
        oscillator.connect(filter);
        filter.connect(gainNode);

        oscillator.start(now);

        oscillators.push(oscillator);
        filters.push(filter);
    });

    // Quick attack
    gainNode.gain.value = 0;
    gainNode.gain.setValueAtTime(0, now);
    gainNode.gain.linearRampToValueAtTime(targetGain * intervals.length, now + 0.02);

    // Note object for modulation (stores arrays for chord voices)
    const note = {
        oscillators, // Array of oscillators
        filters, // Array of filters
        gainNode,
        baseFrequency,
        baseDetunes: oscillators.map(osc => osc.detune.value),
        startTime: now,
        startX: null,
        startY: null,
        cell: cell,
        released: false,
        // Keep single-note compatibility
        get oscillator() { return this.oscillators[0]; },
        get filter() { return this.filters[0]; }
    };

    // Track this note by cell (for modulation lookups)
    activeNotes.set(cell, note);

    // Trigger discovery on first note
    onSynthDiscovered();

    return note;
}

// Update filter based on vertical drag (down = close to 200Hz, up = open to 8000Hz)
function updateFilterForDrag(note, deltaY) {
    if (!note || !note.filters || note.filters.length === 0) return;

    // Drag down (positive deltaY) closes filter to 200Hz
    // Drag up (negative deltaY) opens filter to 8000Hz
    // Full screen height = full range in either direction
    const screenHeight = window.innerHeight;
    const baseCutoff = 1000;
    const minCutoff = 200;
    const maxCutoff = 8000;

    // Normalize: -1 (full up) to +1 (full down) based on screen height
    const normalized = Math.max(-1, Math.min(1, deltaY / (screenHeight * 0.5)));

    let cutoff;
    if (normalized > 0) {
        // Dragging down - close filter (1000 -> 200)
        cutoff = baseCutoff * Math.pow(minCutoff / baseCutoff, normalized);
    } else {
        // Dragging up - open filter (1000 -> 8000)
        cutoff = baseCutoff * Math.pow(maxCutoff / baseCutoff, -normalized);
    }

    const now = note.filters[0].context.currentTime;
    note.filters.forEach(filter => {
        filter.frequency.setTargetAtTime(cutoff, now, 0.05);
    });
}

// Update pitch based on horizontal drag (5ths up/down)
function updatePitchForDrag(note, deltaX) {
    if (!note || !note.oscillators || note.oscillators.length === 0) return;

    // Full screen width = one 5th (700 cents), clamp to +/- 1 5th
    const screenWidth = window.innerWidth;
    const maxCents = 700;
    const cents = Math.max(-maxCents, Math.min(maxCents, (deltaX / (screenWidth * 0.5)) * maxCents));

    const now = note.oscillators[0].context.currentTime;
    note.oscillators.forEach((oscillator, index) => {
        const baseDetune = note.baseDetunes[index] || 0;
        oscillator.detune.setTargetAtTime(baseDetune + cents, now, 0.02);
    });
}

// Fade out note when released - 2.5 second fade
function releaseNote(note) {
    if (!note || !note.gainNode || note.released) return;
    note.released = true;

    const ctx = note.gainNode.context;
    const now = ctx.currentTime;
    const fadeTime = 2.5;

    // Cancel any scheduled gain changes and fade out over 2.5 seconds
    note.gainNode.gain.cancelScheduledValues(now);
    note.gainNode.gain.setValueAtTime(note.gainNode.gain.value, now);
    note.gainNode.gain.exponentialRampToValueAtTime(0.001, now + fadeTime);

    // Stop all oscillators after fade and disconnect all nodes
    setTimeout(() => {
        try {
            // Handle array of oscillators/filters (chord mode)
            if (note.oscillators) {
                note.oscillators.forEach(osc => {
                    try { osc.stop(); osc.disconnect(); } catch (e) {}
                });
            }
            if (note.filters) {
                note.filters.forEach(filter => {
                    try { filter.disconnect(); } catch (e) {}
                });
            }
            note.gainNode.disconnect();
        } catch (e) {
            // Already stopped/disconnected
        }
        activeNotes.delete(note.cell);
    }, fadeTime * 1000 + 50);

    return fadeTime;
}

// Force stop all active notes - emergency cleanup
function stopAllNotes() {
    // Release all notes tracked by pointer
    notesByPointer.forEach((note, pointerId) => {
        if (!note.released) {
            releaseNote(note);
            if (note.cell) fadeCell(note.cell, 0.5);
        }
    });
    notesByPointer.clear();

    // Also clean up any notes in activeNotes that might have been missed
    activeNotes.forEach((note, cell) => {
        if (!note.released) {
            releaseNote(note);
            fadeCell(cell, 0.5);
        }
    });
    activeNotes.clear();
}

// Release a specific pointer and its associated note
function releasePointer(pointerId) {
    const note = notesByPointer.get(pointerId);
    if (!note) return;

    notesByPointer.delete(pointerId);

    if (!note.released) {
        const fadeTime = releaseNote(note);
        if (note.cell) fadeCell(note.cell, fadeTime);
    }
}

// Convert hex to HSL
function hexToHsl(hex) {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;

    if (max === min) {
        h = s = 0;
    } else {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }
    return { h: h * 360, s: s * 100, l: l * 100 };
}

// Apply color to cell - stays on while holding
function activateCell(cell) {
    const color = cellColors[Math.floor(Math.random() * cellColors.length)];
    const wasOff = cell.classList.contains('off');

    // Store state for release - save both hex and HSL for modulation
    const hsl = hexToHsl(color);
    cell.dataset.activeColor = color;
    cell.dataset.baseHue = hsl.h;
    cell.dataset.baseSat = hsl.s;
    cell.dataset.baseLight = hsl.l;
    cell.dataset.wasOff = wasOff ? 'true' : 'false';

    // Clear any existing animation and set color immediately
    cell.style.transition = 'none';
    cell.style.backgroundColor = color;
    cell.style.opacity = '1';
    if (wasOff) cell.classList.remove('off');

    return color;
}

// Update cell color based on drag - synced with sound modulation
function updateCellColor(cell, deltaX, deltaY) {
    const baseHue = parseFloat(cell.dataset.baseHue);
    const baseSat = parseFloat(cell.dataset.baseSat);
    const baseLight = parseFloat(cell.dataset.baseLight);

    if (isNaN(baseHue)) return;

    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;

    // Vertical: filter modulation = warmth shift
    // Down (filter closes) = shift toward red/orange (warmer, -60 hue)
    // Up (filter opens) = shift toward blue/cyan (brighter, +60 hue)
    const vertNorm = Math.max(-1, Math.min(1, deltaY / (screenHeight * 0.5)));
    const hueShift = vertNorm * -60; // Down = warm (negative hue), Up = cool (positive hue)

    // Horizontal: pitch modulation = lightness/saturation
    // Right (pitch up) = brighter, more saturated
    // Left (pitch down) = darker, desaturated
    const horizNorm = Math.max(-1, Math.min(1, deltaX / (screenWidth * 0.5)));
    const lightShift = horizNorm * 15; // +/- 15% lightness
    const satShift = horizNorm * 20;   // +/- 20% saturation

    // Calculate new values with clamping
    const newHue = (baseHue + hueShift + 360) % 360;
    const newSat = Math.max(20, Math.min(100, baseSat + satShift));
    const newLight = Math.max(20, Math.min(80, baseLight + lightShift));

    cell.style.backgroundColor = `hsl(${newHue}, ${newSat}%, ${newLight}%)`;
}

// Fade cell color when note is released - synced with audio fade
function fadeCell(cell, fadeTime) {
    const wasOff = cell.dataset.wasOff === 'true';

    // Start fade transition synced with audio
    requestAnimationFrame(() => {
        cell.style.transition = `background-color ${fadeTime}s ease-out, opacity ${fadeTime}s ease-out`;
        cell.style.backgroundColor = 'transparent';
        if (wasOff) {
            cell.style.opacity = '0';
        }
    });

    // Reset after animation completes
    setTimeout(() => {
        cell.style.transition = 'opacity 0.5s ease';
        cell.style.backgroundColor = '';
        cell.style.opacity = '';
        if (wasOff) cell.classList.add('off');
        delete cell.dataset.activeColor;
        delete cell.dataset.wasOff;
    }, fadeTime * 1000 + 50);
}

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

            // Click logo to trigger wave pattern
            cell.style.cursor = 'pointer';
            cell.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                playWavePattern();
            });
        } else {
            // Random initial state for non-logo cells
            if (Math.random() > 0.5) {
                cell.classList.add('off');
            }

            // Mark cell as interactive for global event handler
            cell.dataset.synthCell = 'true';

            // Prevent context menu on the cell
            cell.addEventListener('contextmenu', (e) => {
                e.preventDefault();
            });

            // Disable touch-action for smoother dragging
            cell.style.touchAction = 'none';

            // Prevent iOS Safari touch callout
            cell.style.webkitTouchCallout = 'none';
            cell.style.webkitUserSelect = 'none';
            cell.style.userSelect = 'none';
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
    const volumeSlider = document.getElementById('audioPlayerVolume');
    const filmCards = document.querySelectorAll('.film-card[data-tracks]');

    if (!player || !audio) return;

    let currentPlaylist = [];
    let currentIndex = 0;
    let isPlaying = false;

    // Set default volume to 50%
    audio.volume = 0.5;
    if (volumeSlider) {
        volumeSlider.value = 50;
    }

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
        // Stop any playing synth notes when opening the player
        stopAllNotes();

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
            document.querySelectorAll('.athos-ost-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.stone-birds-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.the-thread-photo.playing').forEach(c => c.classList.remove('playing'));
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

    // Volume slider and mute toggle
    let playerMuted = false;
    let playerVolumeBeforeMute = 0.5;
    const volumeIcon = document.getElementById('playerVolumeIcon');

    function updatePlayerVolumeIcon() {
        if (!volumeIcon) return;

        const speaker = volumeIcon.querySelector('.speaker');
        const waves = volumeIcon.querySelector('.waves');
        const muted = volumeIcon.querySelector('.muted');

        if (playerMuted) {
            speaker.style.display = 'none';
            waves.style.display = 'none';
            muted.style.display = 'block';
        } else {
            speaker.style.display = 'block';
            waves.style.display = 'block';
            muted.style.display = 'none';
        }
    }

    if (volumeSlider) {
        volumeSlider.addEventListener('input', (e) => {
            audio.volume = e.target.value / 100;

            // If unmuting via slider, update mute state
            if (playerMuted && audio.volume > 0) {
                playerMuted = false;
                updatePlayerVolumeIcon();
            }
        });
    }

    if (volumeIcon) {
        volumeIcon.addEventListener('click', () => {
            if (playerMuted) {
                // Unmute - restore previous volume
                playerMuted = false;
                audio.volume = playerVolumeBeforeMute;
                if (volumeSlider) volumeSlider.value = audio.volume * 100;
            } else {
                // Mute - save current volume and set to 0
                playerVolumeBeforeMute = audio.volume;
                playerMuted = true;
                audio.volume = 0;
                if (volumeSlider) volumeSlider.value = 0;
            }
            updatePlayerVolumeIcon();
        });
    }

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

            // Remove playing class from all cards and solo photos
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.embla-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.athos-ost-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.stone-birds-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.the-thread-photo.playing').forEach(c => c.classList.remove('playing'));
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

            // Remove playing class from all cards and solo photos
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.embla-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.athos-ost-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.stone-birds-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.the-thread-photo.playing').forEach(c => c.classList.remove('playing'));
            emblaPhoto.classList.add('playing');

            showPlayer(albumName, tracks);
            audio.play();
        });
    }

    // Athos OST photo click - supports multiple albums with random album selection
    const athosOstPhoto = document.querySelector('.athos-ost-photo');
    if (athosOstPhoto) {
        athosOstPhoto.addEventListener('click', () => {
            const albumsData = athosOstPhoto.dataset.albums;

            let tracks;
            let albumName = 'Athos OST';

            if (albumsData) {
                try {
                    const albums = JSON.parse(albumsData);
                    if (albums.length === 0) {
                        console.log('No albums yet');
                        return;
                    }
                    const randomAlbum = albums[Math.floor(Math.random() * albums.length)];
                    tracks = randomAlbum.tracks;
                    if (albums.length > 1) {
                        albumName = 'Athos OST - ' + randomAlbum.name;
                    }
                } catch (e) {
                    console.error('Invalid albums data');
                    return;
                }
            } else {
                return;
            }

            // Remove playing class from all cards and solo photos
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.embla-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.athos-ost-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.stone-birds-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.the-thread-photo.playing').forEach(c => c.classList.remove('playing'));
            athosOstPhoto.classList.add('playing');

            showPlayer(albumName, tracks);
            audio.play();
        });
    }

    // Stone Birds photo click - supports multiple albums with random album selection
    const stoneBirdsPhoto = document.querySelector('.stone-birds-photo');
    if (stoneBirdsPhoto) {
        stoneBirdsPhoto.addEventListener('click', () => {
            const albumsData = stoneBirdsPhoto.dataset.albums;

            let tracks;
            let albumName = 'Stone Birds';

            if (albumsData) {
                try {
                    const albums = JSON.parse(albumsData);
                    if (albums.length === 0) {
                        console.log('No albums yet');
                        return;
                    }
                    const randomAlbum = albums[Math.floor(Math.random() * albums.length)];
                    tracks = randomAlbum.tracks;
                    if (albums.length > 1) {
                        albumName = 'Stone Birds - ' + randomAlbum.name;
                    }
                } catch (e) {
                    console.error('Invalid albums data');
                    return;
                }
            } else {
                // Fallback to simple tracks data
                const tracksData = stoneBirdsPhoto.dataset.tracks;
                if (!tracksData) return;
                try {
                    tracks = JSON.parse(tracksData);
                    if (tracks.length === 0) {
                        console.log('No tracks yet');
                        return;
                    }
                } catch (e) {
                    return;
                }
            }

            // Remove playing class from all cards and solo photos
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.embla-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.athos-ost-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.stone-birds-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.the-thread-photo.playing').forEach(c => c.classList.remove('playing'));
            stoneBirdsPhoto.classList.add('playing');

            showPlayer(albumName, tracks);
            audio.play();
        });
    }

    // The Thread photo click
    const theThreadPhoto = document.querySelector('.the-thread-photo');
    if (theThreadPhoto) {
        theThreadPhoto.addEventListener('click', () => {
            const tracksData = theThreadPhoto.dataset.tracks;
            if (!tracksData) return;

            let tracks;
            try {
                tracks = JSON.parse(tracksData);
            } catch (e) {
                console.error('Failed to parse The Thread tracks data:', e);
                return;
            }

            // Remove playing class from all cards and solo photos
            document.querySelectorAll('.film-card.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.embla-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.athos-ost-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.stone-birds-photo.playing').forEach(c => c.classList.remove('playing'));
            document.querySelectorAll('.the-thread-photo.playing').forEach(c => c.classList.remove('playing'));
            theThreadPhoto.classList.add('playing');

            showPlayer('The Thread', tracks);
            audio.play();
        });
    }

    // Expose for external use
    window.audioPlayer = {
        show: showPlayer,
        hide: hidePlayer
    };
}

// Initialize synth volume control
let synthMuted = false;
let synthVolumeBeforeMute = 0.5;

function updateSynthVolumeIcon() {
    const icon = document.getElementById('synthVolumeIcon');
    if (!icon) return;

    const speaker = icon.querySelector('.speaker');
    const waves = icon.querySelector('.waves');
    const muted = icon.querySelector('.muted');

    if (synthMuted) {
        speaker.style.display = 'none';
        waves.style.display = 'none';
        muted.style.display = 'block';
    } else {
        speaker.style.display = 'block';
        waves.style.display = 'block';
        muted.style.display = 'none';
    }
}

function initSynthVolume() {
    const slider = document.getElementById('synthVolumeSlider');
    const icon = document.getElementById('synthVolumeIcon');
    if (!slider) return;

    // Set initial value
    slider.value = synthVolume * 100;

    slider.addEventListener('input', (e) => {
        synthVolume = e.target.value / 100;

        // If unmuting via slider, update mute state
        if (synthMuted && synthVolume > 0) {
            synthMuted = false;
            updateSynthVolumeIcon();
        }

        // Update any currently playing notes to the new volume
        activeNotes.forEach((note) => {
            if (!note.released && note.gainNode) {
                const intervals = chordVoicings[chordMode] || [0];
                const targetGain = (0.15 * synthVolume) / Math.sqrt(intervals.length) * intervals.length;
                note.gainNode.gain.setTargetAtTime(targetGain, note.gainNode.context.currentTime, 0.05);
            }
        });
    });

    // Icon click toggles mute
    if (icon) {
        icon.addEventListener('click', () => {
            if (synthMuted) {
                // Unmute - restore previous volume
                synthMuted = false;
                synthVolume = synthVolumeBeforeMute;
                slider.value = synthVolume * 100;
            } else {
                // Mute - save current volume and set to 0
                synthVolumeBeforeMute = synthVolume;
                synthMuted = true;
                synthVolume = 0;
                slider.value = 0;
            }
            updateSynthVolumeIcon();

            // Update playing notes
            activeNotes.forEach((note) => {
                if (!note.released && note.gainNode) {
                    const intervals = chordVoicings[chordMode] || [0];
                    const targetGain = (0.15 * synthVolume) / Math.sqrt(intervals.length) * intervals.length;
                    note.gainNode.gain.setTargetAtTime(targetGain, note.gainNode.context.currentTime, 0.05);
                }
            });
        });
    }
}

// Initialize smart harmony toggle
function initSmartHarmony() {
    const toggle = document.getElementById('harmonyToggle');
    if (!toggle) return;

    toggle.checked = smartHarmony;

    toggle.addEventListener('change', (e) => {
        smartHarmony = e.target.checked;
    });
}

// Track if synth has been discovered (for showing manual)
let synthDiscovered = localStorage.getItem('synthDiscovered') === 'true';
let firstNoteThisSession = !synthDiscovered;

// Show synth manual
function showSynthManual() {
    const manual = document.getElementById('synthManual');
    if (!manual) return;

    manual.style.display = 'flex';
    requestAnimationFrame(() => {
        manual.classList.add('active');
    });
}

// Hide synth manual
function hideSynthManual() {
    const manual = document.getElementById('synthManual');
    if (!manual) return;

    manual.classList.remove('active');
    setTimeout(() => {
        manual.style.display = 'none';
    }, 300);
}

// Initialize synth manual
function initSynthManual() {
    const manual = document.getElementById('synthManual');
    const closeBtn = document.getElementById('synthManualClose');

    if (!manual) return;

    // Close button
    if (closeBtn) {
        closeBtn.addEventListener('click', hideSynthManual);
    }

    // Click outside to close
    manual.addEventListener('click', (e) => {
        if (e.target === manual) {
            hideSynthManual();
        }
    });

    // Escape key to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && manual.classList.contains('active')) {
            hideSynthManual();
        }
    });
}

// Called when first note is played
function onSynthDiscovered() {
    if (firstNoteThisSession) {
        firstNoteThisSession = false;
        synthDiscovered = true;
        localStorage.setItem('synthDiscovered', 'true');
        // Show manual after a short delay so they hear the first note
        setTimeout(showSynthManual, 800);
    }
}

// Global pointer event handlers for synth - attached to document for reliability
function initGlobalSynthEvents() {
    // POINTERDOWN - start a note
    document.addEventListener('pointerdown', (e) => {
        // Only left mouse button or touch
        if (e.button !== 0) return;

        const cell = e.target.closest('[data-synth-cell="true"]');
        if (!cell) return;

        e.preventDefault();

        // If this pointer is already tracking something, release it first
        if (notesByPointer.has(e.pointerId)) {
            releasePointer(e.pointerId);
        }

        // If there's already a note playing on this cell, release it first
        const existingNote = activeNotes.get(cell);
        if (existingNote && !existingNote.released) {
            releaseNote(existingNote);
            fadeCell(cell, 0.1);
            // Also remove from notesByPointer if it's there
            notesByPointer.forEach((note, pid) => {
                if (note === existingNote) notesByPointer.delete(pid);
            });
        }

        // Play note
        const note = playTuningNote(cell);
        if (note) {
            note.startX = e.clientX;
            note.startY = e.clientY;
            note.pointerId = e.pointerId; // Store pointerId on the note itself

            // Track by pointer ID - this is the primary tracking mechanism
            notesByPointer.set(e.pointerId, note);

            activateCell(cell);
        }
    }, { passive: false });

    // POINTERMOVE - modulate the note
    document.addEventListener('pointermove', (e) => {
        const note = notesByPointer.get(e.pointerId);
        if (!note || note.released) return;

        if (note.startX !== null) {
            const deltaX = e.clientX - note.startX;
            const deltaY = e.clientY - note.startY;
            updatePitchForDrag(note, deltaX);
            updateFilterForDrag(note, deltaY);
            if (note.cell) updateCellColor(note.cell, deltaX, deltaY);
        }
    });

    // POINTERUP - release the note
    document.addEventListener('pointerup', (e) => {
        releasePointer(e.pointerId);
    });

    // POINTERCANCEL - release the note (browser interrupted)
    document.addEventListener('pointercancel', (e) => {
        releasePointer(e.pointerId);
    });

    // POINTERLEAVE on document - release if pointer leaves the window entirely
    document.addEventListener('pointerleave', (e) => {
        // Only if leaving the document itself (not just an element)
        if (e.target === document) {
            releasePointer(e.pointerId);
        }
    });

    // Right-click anywhere releases all notes
    document.addEventListener('contextmenu', (e) => {
        // Check if right-clicking on or near the grid
        const grid = document.getElementById('heroGrid');
        if (grid && grid.contains(e.target)) {
            e.preventDefault();
            stopAllNotes();
        }
    });

    // Extra safety: any click outside the grid area stops all notes
    document.addEventListener('click', (e) => {
        const grid = document.getElementById('heroGrid');
        if (grid && !grid.contains(e.target)) {
            // Clicked outside the grid - stop any stuck notes
            if (notesByPointer.size > 0 || activeNotes.size > 0) {
                stopAllNotes();
            }
        }
    }, true); // Use capture phase
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initHeroGrid();
    initMobileNav();
    initSmoothScroll();
    initAudioPlayer();
    initSynthVolume();
    initSmartHarmony();
    initSynthManual();
    initGlobalSynthEvents();

    // Prime audio context on first interaction for instant response later
    const primeAudio = () => {
        ensureAudioContext();
        document.removeEventListener('mousedown', primeAudio);
        document.removeEventListener('touchstart', primeAudio);
    };
    document.addEventListener('mousedown', primeAudio, { once: true });
    document.addEventListener('touchstart', primeAudio, { once: true });
});

// Logo click patterns - multiple beautiful symmetrical patterns
// Each pattern uses its own tracking to not interfere with manual play

let waveInProgress = false;

function playWavePattern() {
    if (waveInProgress) return;
    waveInProgress = true;

    const grid = document.getElementById('heroGrid');
    if (!grid) {
        waveInProgress = false;
        return;
    }

    const cols = parseInt(grid.style.getPropertyValue('--cols')) || 11;
    const rows = parseInt(grid.style.getPropertyValue('--rows')) || 9;
    const centerRow = Math.floor(rows / 2);
    const centerCol = Math.floor(cols / 2);
    const allCells = grid.querySelectorAll('.cell');

    // Get cell at grid position
    function getCellAt(row, col) {
        if (row < 0 || row >= rows || col < 0 || col >= cols) return null;
        if (row === centerRow && col === centerCol) return null; // Logo cell
        const index = row * cols + col;
        const cell = allCells[index];
        return (cell && cell.dataset.synthCell === 'true') ? cell : null;
    }

    // Pattern generators - each returns array of "rings" (groups of cells to play simultaneously)

    // 1. Circular (Chebyshev distance) - expanding squares
    function patternCircular() {
        const rings = [];
        const maxDist = Math.max(centerRow, centerCol, rows - centerRow - 1, cols - centerCol - 1) + 1;
        for (let d = 1; d <= maxDist; d++) {
            const ring = [];
            for (let r = centerRow - d; r <= centerRow + d; r++) {
                for (let c = centerCol - d; c <= centerCol + d; c++) {
                    if (Math.max(Math.abs(r - centerRow), Math.abs(c - centerCol)) === d) {
                        const cell = getCellAt(r, c);
                        if (cell) ring.push(cell);
                    }
                }
            }
            if (ring.length > 0) rings.push(ring);
        }
        return rings;
    }

    // 2. Diamond (Manhattan distance) - expanding diamonds
    function patternDiamond() {
        const rings = [];
        const maxDist = centerRow + centerCol + 2;
        for (let d = 1; d <= maxDist; d++) {
            const ring = [];
            for (let r = 0; r < rows; r++) {
                for (let c = 0; c < cols; c++) {
                    if (Math.abs(r - centerRow) + Math.abs(c - centerCol) === d) {
                        const cell = getCellAt(r, c);
                        if (cell) ring.push(cell);
                    }
                }
            }
            if (ring.length > 0) rings.push(ring);
        }
        return rings;
    }

    // 3. Cross - axes first, then fills
    function patternCross() {
        const rings = [];
        const maxDist = Math.max(centerRow, centerCol, rows - centerRow - 1, cols - centerCol - 1) + 1;

        // First: expand along axes (up, down, left, right)
        for (let d = 1; d <= maxDist; d++) {
            const ring = [];
            // Up
            const up = getCellAt(centerRow - d, centerCol);
            if (up) ring.push(up);
            // Down
            const down = getCellAt(centerRow + d, centerCol);
            if (down) ring.push(down);
            // Left
            const left = getCellAt(centerRow, centerCol - d);
            if (left) ring.push(left);
            // Right
            const right = getCellAt(centerRow, centerCol + d);
            if (right) ring.push(right);

            if (ring.length > 0) rings.push(ring);
        }
        return rings;
    }

    // 4. X-pattern - diagonals only
    function patternX() {
        const rings = [];
        const maxDist = Math.max(centerRow, centerCol, rows - centerRow - 1, cols - centerCol - 1) + 1;

        for (let d = 1; d <= maxDist; d++) {
            const ring = [];
            // Top-left
            const tl = getCellAt(centerRow - d, centerCol - d);
            if (tl) ring.push(tl);
            // Top-right
            const tr = getCellAt(centerRow - d, centerCol + d);
            if (tr) ring.push(tr);
            // Bottom-left
            const bl = getCellAt(centerRow + d, centerCol - d);
            if (bl) ring.push(bl);
            // Bottom-right
            const br = getCellAt(centerRow + d, centerCol + d);
            if (br) ring.push(br);

            if (ring.length > 0) rings.push(ring);
        }
        return rings;
    }

    // 5. Horizontal sweep - columns fire left to right
    function patternHorizontalSweep() {
        const rings = [];
        for (let c = 0; c < cols; c++) {
            const ring = [];
            for (let r = 0; r < rows; r++) {
                const cell = getCellAt(r, c);
                if (cell) ring.push(cell);
            }
            if (ring.length > 0) rings.push(ring);
        }
        return rings;
    }

    // 6. Vertical sweep - rows fire top to bottom
    function patternVerticalSweep() {
        const rings = [];
        for (let r = 0; r < rows; r++) {
            const ring = [];
            for (let c = 0; c < cols; c++) {
                const cell = getCellAt(r, c);
                if (cell) ring.push(cell);
            }
            if (ring.length > 0) rings.push(ring);
        }
        return rings;
    }

    // 7. Star burst - cross then X alternating
    function patternStarburst() {
        const rings = [];
        const maxDist = Math.max(centerRow, centerCol, rows - centerRow - 1, cols - centerCol - 1) + 1;

        for (let d = 1; d <= maxDist; d++) {
            // Axes
            const axisRing = [];
            const up = getCellAt(centerRow - d, centerCol);
            if (up) axisRing.push(up);
            const down = getCellAt(centerRow + d, centerCol);
            if (down) axisRing.push(down);
            const left = getCellAt(centerRow, centerCol - d);
            if (left) axisRing.push(left);
            const right = getCellAt(centerRow, centerCol + d);
            if (right) axisRing.push(right);
            if (axisRing.length > 0) rings.push(axisRing);

            // Diagonals
            const diagRing = [];
            const tl = getCellAt(centerRow - d, centerCol - d);
            if (tl) diagRing.push(tl);
            const tr = getCellAt(centerRow - d, centerCol + d);
            if (tr) diagRing.push(tr);
            const bl = getCellAt(centerRow + d, centerCol - d);
            if (bl) diagRing.push(bl);
            const br = getCellAt(centerRow + d, centerCol + d);
            if (br) diagRing.push(br);
            if (diagRing.length > 0) rings.push(diagRing);
        }
        return rings;
    }

    // Pick a random pattern
    const patterns = [
        patternCircular,
        patternDiamond,
        patternCross,
        patternX,
        patternHorizontalSweep,
        patternVerticalSweep,
        patternStarburst
    ];

    const chosenPattern = patterns[Math.floor(Math.random() * patterns.length)];
    const rings = chosenPattern();

    // Ensure audio context is ready
    ensureAudioContext();

    // Timing
    const ringDelay = 140; // ms between rings (slower cascade)
    const noteDuration = 300; // how long each note plays (longer sustain)

    // Limit concurrent notes per ring to prevent overload
    const maxNotesPerRing = 6;

    // Track notes from this pattern separately using a unique base ID
    const patternBaseId = Date.now();
    let noteCounter = 0;

    // Play each ring
    rings.forEach((ring, ringIndex) => {
        setTimeout(() => {
            // If ring has too many cells, pick random subset
            let cellsToPlay = ring;
            if (ring.length > maxNotesPerRing) {
                cellsToPlay = [...ring].sort(() => Math.random() - 0.5).slice(0, maxNotesPerRing);
            }

            cellsToPlay.forEach(cell => {
                const note = playTuningNote(cell);
                if (note) {
                    activateCell(cell);

                    // Use unique negative ID for pattern notes (won't conflict with real pointers)
                    noteCounter++;
                    const fakePointerId = -(patternBaseId + noteCounter);
                    notesByPointer.set(fakePointerId, note);

                    // Release after duration
                    setTimeout(() => {
                        releasePointer(fakePointerId);
                    }, noteDuration);
                }
            });
        }, ringIndex * ringDelay);
    });

    // Reset flag after pattern completes
    const totalDuration = rings.length * ringDelay + noteDuration + 300;
    setTimeout(() => {
        waveInProgress = false;
    }, totalDuration);
}

// Reinitialize grid on resize
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(initHeroGrid, 250);
});

// Clean up notes when page loses focus or visibility (prevents stuck notes)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAllNotes();
    }
});

window.addEventListener('blur', () => {
    stopAllNotes();
});

// Safety: periodically check for orphaned notes (reduced to 15 second threshold)
setInterval(() => {
    if (!audioContext) return;

    const now = audioContext.currentTime;

    // Check notesByPointer (primary tracking)
    notesByPointer.forEach((note, pointerId) => {
        if (!note.released) {
            const age = now - note.startTime;
            if (age > 15) {
                console.log('Cleaning up orphaned note (by pointer):', pointerId);
                releasePointer(pointerId);
            }
        }
    });

    // Check activeNotes (secondary tracking) for any stragglers
    activeNotes.forEach((note, cell) => {
        if (!note.released) {
            const age = now - note.startTime;
            if (age > 15) {
                console.log('Cleaning up orphaned note (by cell)');
                releaseNote(note);
                fadeCell(cell, 0.5);
                activeNotes.delete(cell);
            }
        }
    });
}, 3000); // Check every 3 seconds
