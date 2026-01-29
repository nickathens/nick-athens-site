// Hero Grid Animation

// Orchestral tuning frequencies - the actual notes you hear during tuning
// A440 is the reference, plus open string pitches for violin, viola, cello, bass
const tuningFrequencies = [
    440,    // A4 - concert pitch (oboe gives this)
    440,    // A4 - doubled for frequency since it's the main tuning note
    220,    // A3 - viola/cello A string
    110,    // A2 - double bass A string
    293.66, // D4 - violin D string
    146.83, // D3 - viola/cello D string
    196,    // G3 - violin/viola G string
    98,     // G2 - cello G string
    659.25, // E5 - violin E string
    329.63, // E4 - higher register tuning
    87.31,  // F2 - bass low notes
    65.41   // C2 - bass low C
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
// Based on the circle of fifths - all notes derived from A (440Hz)
// The harmonic "family" of notes that sound good together in orchestral tuning context
const harmonicFamily = {
    // Note name -> frequency ratios that work well with it
    // Using Pythagorean tuning (stacked perfect fifths)
    'A': { base: 440, fifthUp: 660, fifthDown: 293.33, octaveUp: 880, octaveDown: 220 },
    'E': { base: 330, fifthUp: 495, fifthDown: 220, octaveUp: 660, octaveDown: 165 },
    'D': { base: 293.66, fifthUp: 440, fifthDown: 196, octaveUp: 587.33, octaveDown: 146.83 },
    'G': { base: 196, fifthUp: 293.66, fifthDown: 130.81, octaveUp: 392, octaveDown: 98 }
};

// Convert frequency to nearest note in the circle of fifths
function frequencyToNote(freq) {
    // Normalize to octave 4 range (220-440 Hz equivalent)
    let normalized = freq;
    while (normalized < 200) normalized *= 2;
    while (normalized > 500) normalized /= 2;

    // Find closest note
    const notes = [
        { name: 'A', freq: 440 },
        { name: 'E', freq: 330 },
        { name: 'D', freq: 293.66 },
        { name: 'G', freq: 196 * 2 } // G in octave 4
    ];

    let closest = notes[0];
    let minDiff = Math.abs(normalized - notes[0].freq);

    for (const note of notes) {
        const diff = Math.abs(normalized - note.freq);
        if (diff < minDiff) {
            minDiff = diff;
            closest = note;
        }
    }

    return closest.name;
}

// Get harmonically compatible intervals based on what's already playing
function getSmartIntervals(baseFreq) {
    // If nothing is playing, return open fifth (orchestral default)
    if (activeNotes.size === 0) {
        return [0, 700]; // Root + perfect fifth
    }

    // Analyze currently playing notes
    const playingFreqs = [];
    activeNotes.forEach(note => {
        if (!note.released) {
            playingFreqs.push(note.baseFrequency);
        }
    });

    if (playingFreqs.length === 0) {
        return [0, 700];
    }

    // Get the note names of what's playing
    const playingNotes = playingFreqs.map(f => frequencyToNote(f));
    const newNote = frequencyToNote(baseFreq);

    // Determine the harmonic relationship
    // If the new note is a fifth away from existing notes, add octave for richness
    // If it's the same note family, add fifth + octave for power
    // If it's in the family but different, keep it open (just fifth)

    const sameFamily = playingNotes.includes(newNote);

    // Check if any playing note forms a fifth relationship with new note
    const fifthRelations = {
        'A': ['E', 'D'],
        'E': ['A', 'B'],
        'D': ['A', 'G'],
        'G': ['D', 'C']
    };

    const hasFifthRelation = playingNotes.some(n =>
        fifthRelations[newNote] && fifthRelations[newNote].includes(n)
    );

    // Build chord based on context
    if (playingFreqs.length >= 3) {
        // Already complex, keep new note simple for clarity
        return [0]; // Single note
    } else if (sameFamily) {
        // Same note family - add power chord for thickness
        return [0, 700, 1200]; // Root + 5th + octave
    } else if (hasFifthRelation) {
        // Fifth relationship - beautiful stacking, add ninth
        return [0, 700, 1400]; // Root + 5th + 9th
    } else {
        // Different but compatible - open voicing
        return [0, 700]; // Root + 5th
    }
}

// Active notes for modulation (cell element -> note object)
const activeNotes = new Map();

// Safety timeout - kill any note after 30 seconds max (prevents infinite drones)
const MAX_NOTE_DURATION = 30000;

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
        safetyTimeout: null,
        // Keep single-note compatibility
        get oscillator() { return this.oscillators[0]; },
        get filter() { return this.filters[0]; }
    };

    // Safety timeout - force release after MAX_NOTE_DURATION to prevent infinite drones
    note.safetyTimeout = setTimeout(() => {
        if (!note.released) {
            console.log('Safety timeout: forcing note release');
            releaseNote(note);
            fadeCell(cell, 2.5);
        }
    }, MAX_NOTE_DURATION);

    // Track this note
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

    // Clear safety timeout since we're releasing properly
    if (note.safetyTimeout) {
        clearTimeout(note.safetyTimeout);
        note.safetyTimeout = null;
    }

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
    activeNotes.forEach((note, cell) => {
        if (!note.released) {
            releaseNote(note);
            fadeCell(cell, 0.5); // Quick fade for emergency cleanup
        }
        // Also cleanup any lingering event handlers
        if (cell._cleanupHandlers) {
            cell._cleanupHandlers();
        }
    });
}

// Periodic cleanup - catch any orphaned notes every 5 seconds
setInterval(() => {
    if (audioContext) {
        const now = audioContext.currentTime;
        activeNotes.forEach((note, cell) => {
            // If a note has been playing for more than 15 seconds without interaction, kill it
            if (!note.released && (now - note.startTime) > 15) {
                console.log('Periodic cleanup: releasing orphaned note');
                releaseNote(note);
                fadeCell(cell, 0.5);
                if (cell._cleanupHandlers) {
                    cell._cleanupHandlers();
                }
            }
        });
    }
}, 5000);

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
        } else {
            // Random initial state for non-logo cells
            if (Math.random() > 0.5) {
                cell.classList.add('off');
            }

            // Unique ID for this cell's interaction tracking
            const cellId = i;

            function startNote(e, clientX, clientY) {
                e.preventDefault();

                // If there's already a note playing on this cell, release it first
                const existingNote = activeNotes.get(cell);
                if (existingNote && !existingNote.released) {
                    releaseNote(existingNote);
                    fadeCell(cell, 0.1); // Quick fade for the old note
                }

                const note = playTuningNote(cell);
                if (note) {
                    note.startX = clientX;
                    note.startY = clientY;
                    note.cellId = cellId;
                    activateCell(cell);
                }
            }

            function updateNote(clientX, clientY) {
                const note = activeNotes.get(cell);
                if (note && note.startX !== null && !note.released) {
                    const deltaX = clientX - note.startX;
                    const deltaY = clientY - note.startY;
                    updatePitchForDrag(note, deltaX);
                    updateFilterForDrag(note, deltaY);
                    updateCellColor(cell, deltaX, deltaY);
                }
            }

            function endNote() {
                const note = activeNotes.get(cell);
                if (note && !note.released) {
                    const fadeTime = releaseNote(note);
                    fadeCell(cell, fadeTime);
                }
            }

            // Store handlers on the cell element so we can clean them up
            cell._cleanupHandlers = null;

            // Mouse events - start on cell, track on document for full-screen drag
            cell.addEventListener('mousedown', (e) => {
                // Only respond to left mouse button (button 0)
                if (e.button !== 0) return;

                // Clean up any previous handlers that weren't properly removed
                if (cell._cleanupHandlers) {
                    cell._cleanupHandlers();
                }

                startNote(e, e.clientX, e.clientY);

                function onMouseMove(moveEvent) {
                    const note = activeNotes.get(cell);
                    if (note && !note.released) {
                        updateNote(moveEvent.clientX, moveEvent.clientY);
                    }
                }

                function onMouseUp(upEvent) {
                    // Release on any mouse button up
                    endNote();
                    cleanup();
                }

                function cleanup() {
                    document.removeEventListener('mousemove', onMouseMove);
                    document.removeEventListener('mouseup', onMouseUp);
                    document.removeEventListener('contextmenu', onContextMenu);
                    cell._cleanupHandlers = null;
                }

                // Also release on right-click context menu
                function onContextMenu() {
                    endNote();
                    cleanup();
                }

                cell._cleanupHandlers = cleanup;

                document.addEventListener('mousemove', onMouseMove);
                document.addEventListener('mouseup', onMouseUp);
                document.addEventListener('contextmenu', onContextMenu);
            });

            // Touch events - start on cell, track on document for full-screen drag
            cell.addEventListener('touchstart', (e) => {
                // Clean up any previous handlers that weren't properly removed
                if (cell._cleanupHandlers) {
                    cell._cleanupHandlers();
                }

                const touch = e.touches[0];
                startNote(e, touch.clientX, touch.clientY);

                // Track the touch identifier so we only respond to our touch
                const touchId = touch.identifier;

                function onTouchMove(moveEvent) {
                    // Find our specific touch
                    let ourTouch = null;
                    for (let i = 0; i < moveEvent.touches.length; i++) {
                        if (moveEvent.touches[i].identifier === touchId) {
                            ourTouch = moveEvent.touches[i];
                            break;
                        }
                    }

                    if (ourTouch) {
                        const note = activeNotes.get(cell);
                        if (note && !note.released) {
                            updateNote(ourTouch.clientX, ourTouch.clientY);
                        }
                    }
                }

                function onTouchEnd(endEvent) {
                    // Check if our specific touch ended
                    let ourTouchEnded = true;
                    for (let i = 0; i < endEvent.touches.length; i++) {
                        if (endEvent.touches[i].identifier === touchId) {
                            ourTouchEnded = false;
                            break;
                        }
                    }

                    if (ourTouchEnded) {
                        endNote();
                        cleanup();
                    }
                }

                function cleanup() {
                    document.removeEventListener('touchmove', onTouchMove);
                    document.removeEventListener('touchend', onTouchEnd);
                    document.removeEventListener('touchcancel', onTouchEnd);
                    cell._cleanupHandlers = null;
                }

                cell._cleanupHandlers = cleanup;

                document.addEventListener('touchmove', onTouchMove, { passive: false });
                document.addEventListener('touchend', onTouchEnd);
                document.addEventListener('touchcancel', onTouchEnd);
            }, { passive: false });
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
        // Grid tuning can play in parallel with music - no longer disabled

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

    // Volume slider
    if (volumeSlider) {
        volumeSlider.addEventListener('input', (e) => {
            audio.volume = e.target.value / 100;
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
            stoneBirdsPhoto.classList.add('playing');

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

// Initialize synth volume control
function initSynthVolume() {
    const slider = document.getElementById('synthVolumeSlider');
    if (!slider) return;

    // Set initial value
    slider.value = synthVolume * 100;

    slider.addEventListener('input', (e) => {
        synthVolume = e.target.value / 100;

        // Update any currently playing notes to the new volume
        activeNotes.forEach((note) => {
            if (!note.released && note.gainNode) {
                const intervals = chordVoicings[chordMode] || [0];
                const targetGain = (0.15 * synthVolume) / Math.sqrt(intervals.length) * intervals.length;
                note.gainNode.gain.setTargetAtTime(targetGain, note.gainNode.context.currentTime, 0.05);
            }
        });
    });
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

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initHeroGrid();
    initMobileNav();
    initSmoothScroll();
    initAudioPlayer();
    initSynthVolume();
    initSmartHarmony();
    initSynthManual();

    // Prime audio context on first interaction for instant response later
    const primeAudio = () => {
        ensureAudioContext();
        document.removeEventListener('mousedown', primeAudio);
        document.removeEventListener('touchstart', primeAudio);
    };
    document.addEventListener('mousedown', primeAudio, { once: true });
    document.addEventListener('touchstart', primeAudio, { once: true });
});

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

// Prevent right-click from causing stuck notes on the grid
document.addEventListener('contextmenu', (e) => {
    // If right-clicking on or near the grid, release all notes
    const grid = document.getElementById('heroGrid');
    if (grid && grid.contains(e.target)) {
        stopAllNotes();
    }
});
