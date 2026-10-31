"""
ShivAI Creative Media & Multi-Track Video Editor Interface.
Provides visual multi-track sequencing, canvas preview playback, aspect ratio switcher,
AI image and voice generator integration, and timeline render manifest export.
"""

VIDEO_EDITOR_UI_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SHIV Editor — Multi-Track Media & Video Studio</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Inter', sans-serif; background-color: #080c14; color: #f1f5f9; }
    .glass-panel { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .timeline-track { background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.6); }
    ::-webkit-scrollbar-thumb { background: rgba(100, 116, 139, 0.4); border-radius: 4px; }
  </style>
</head>
<body class="h-screen flex flex-col overflow-hidden">

  <!-- Top Navigation Header -->
  <header class="h-14 border-b border-slate-800 bg-slate-950/90 backdrop-blur px-4 flex items-center justify-between shrink-0 z-20">
    <div class="flex items-center space-x-4">
      <div class="flex items-center space-x-2.5">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-pink-600 to-rose-500 flex items-center justify-center shadow-lg shadow-pink-500/20">
          <i class="fa-solid fa-film text-white text-sm"></i>
        </div>
        <div>
          <span class="font-bold text-sm tracking-wide text-white">SHIV<span class="text-pink-400"> EDITOR</span></span>
          <span class="text-[10px] bg-pink-500/10 text-pink-400 border border-pink-500/20 px-1.5 py-0.5 rounded ml-1 font-mono">Creative Suite</span>
        </div>
      </div>
      <div class="h-5 w-px bg-slate-800"></div>
      <!-- Aspect Ratio Switcher -->
      <div class="flex items-center space-x-1 bg-slate-900 p-0.5 rounded-lg border border-slate-800 text-xs">
        <button onclick="setRatio('16:9')" id="ratio-16-9" class="px-2.5 py-1 rounded bg-slate-800 text-white font-medium">16:9 (Landscape)</button>
        <button onclick="setRatio('9:16')" id="ratio-9-16" class="px-2.5 py-1 rounded text-slate-400 hover:text-white">9:16 (Shorts/Reels)</button>
        <button onclick="setRatio('1:1')" id="ratio-1-1" class="px-2.5 py-1 rounded text-slate-400 hover:text-white">1:1 (Square)</button>
      </div>
    </div>

    <!-- Right Actions -->
    <div class="flex items-center space-x-3 text-xs">
      <button onclick="exportProject()" class="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 text-white font-semibold flex items-center space-x-1.5 shadow-lg shadow-pink-500/20 transition">
        <i class="fa-solid fa-file-export"></i>
        <span>Export Manifest</span>
      </button>
      <a href="/admin" class="px-2.5 py-1 text-slate-400 hover:text-white transition">
        <i class="fa-solid fa-gauge-high mr-1"></i> Admin Hub
      </a>
    </div>
  </header>

  <!-- Main Split Body: Preview + Asset Drawer -->
  <div class="flex-1 flex overflow-hidden">

    <!-- Left Media Library & AI Generator Drawer -->
    <aside class="w-72 border-r border-slate-800 glass-panel flex flex-col shrink-0 overflow-y-auto p-4 space-y-4 text-xs">
      <span class="font-bold uppercase tracking-wider text-slate-400 text-[11px] flex items-center space-x-1.5">
        <i class="fa-solid fa-photo-film text-pink-400"></i>
        <span>Media & AI Asset Library</span>
      </span>

      <!-- AI FLUX Image Generator -->
      <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
        <div class="font-semibold text-slate-200 flex items-center justify-between">
          <span>AI Image Slide (FLUX)</span>
          <span class="text-[10px] text-pink-400 font-mono">Free</span>
        </div>
        <input type="text" id="ai-image-prompt" value="Cyberpunk futuristic city skyline at dusk" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 text-xs">
        <button onclick="generateImageClip()" class="w-full py-1.5 bg-pink-600 hover:bg-pink-500 text-white rounded-lg font-medium transition">
          Generate & Add to Timeline 🎨
        </button>
      </div>

      <!-- AI Neural TTS Voiceover -->
      <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
        <div class="font-semibold text-slate-200 flex items-center justify-between">
          <span>AI Voiceover (Neural)</span>
          <span class="text-[10px] text-indigo-400 font-mono">Edge-TTS</span>
        </div>
        <input type="text" id="ai-tts-text" value="Welcome to the future of multimodal creation with ShivAI." class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 text-xs">
        <button onclick="generateAudioTrack()" class="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition">
          Synthesize & Add Audio 🎙️
        </button>
      </div>

      <!-- Add Subtitle / Text Overlay -->
      <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
        <div class="font-semibold text-slate-200">Text & Subtitle Overlay</div>
        <input type="text" id="text-overlay-input" value="SHIV AI V2.0 ENGINE" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-slate-200 text-xs">
        <button onclick="addTextOverlay()" class="w-full py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg font-medium border border-slate-700 transition">
          Add Text Banner ✍️
        </button>
      </div>
    </aside>

    <!-- Center Preview Viewport -->
    <main class="flex-1 flex flex-col items-center justify-center p-6 bg-slate-950/40 relative">
      <!-- Player Canvas Viewport Container -->
      <div id="player-box" class="relative rounded-2xl overflow-hidden shadow-2xl border border-slate-800 bg-black flex items-center justify-center transition-all duration-300" style="width: 640px; height: 360px;">
        <!-- Background Slide Image -->
        <img id="player-bg" src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1280&q=80" class="w-full h-full object-cover">
        
        <!-- Live Text Overlay -->
        <div id="player-overlay" class="absolute bottom-8 px-6 py-2 rounded-xl bg-black/60 backdrop-blur-md border border-white/10 text-white font-bold text-lg tracking-wide uppercase shadow-2xl transition-all">
          SHIV AI V2.0 ENGINE
        </div>

        <!-- Center Play/Pause Watermark Button -->
        <button onclick="togglePlay()" class="absolute w-16 h-16 rounded-full bg-pink-600/80 hover:bg-pink-500 text-white flex items-center justify-center text-xl shadow-2xl transition transform hover:scale-110">
          <i id="play-center-icon" class="fa-solid fa-play ml-1"></i>
        </button>
      </div>

      <!-- Player Playback Controller Bar -->
      <div class="w-full max-w-xl mt-4 glass-panel px-4 py-2.5 rounded-xl flex items-center justify-between text-xs">
        <div class="flex items-center space-x-3">
          <button onclick="togglePlay()" class="text-slate-300 hover:text-white text-sm">
            <i id="play-bar-icon" class="fa-solid fa-play"></i>
          </button>
          <button onclick="stopPlayback()" class="text-slate-400 hover:text-white">
            <i class="fa-solid fa-stop"></i>
          </button>
          <span id="time-display" class="font-mono text-slate-300 text-[11px]">00:00.0 / 00:15.0</span>
        </div>
        <div class="flex-1 mx-4">
          <input type="range" id="scrubber" min="0" max="15" step="0.1" value="0" oninput="onScrub(this.value)" class="w-full accent-pink-500 cursor-pointer">
        </div>
        <div class="flex items-center space-x-2 text-slate-400">
          <i class="fa-solid fa-volume-high"></i>
          <span class="text-[10px] font-mono">100%</span>
        </div>
      </div>
    </main>

  </div>

  <!-- Bottom: Multi-Track Timeline Sequencing Drawer -->
  <footer class="h-60 border-t border-slate-800 bg-slate-950 flex flex-col shrink-0 z-10">
    <!-- Timeline Header & Time Ruler -->
    <div class="h-8 border-b border-slate-800/80 bg-slate-900/60 px-4 flex items-center justify-between text-[11px] text-slate-400 select-none">
      <div class="w-48 font-bold uppercase tracking-wider text-slate-500">Tracks</div>
      <div class="flex-1 flex justify-between font-mono text-[10px] px-2 text-slate-600">
        <span>00:00</span>
        <span>00:03</span>
        <span>00:06</span>
        <span>00:09</span>
        <span>00:12</span>
        <span>00:15</span>
      </div>
    </div>

    <!-- Timeline Tracks Area -->
    <div class="flex-1 p-3 overflow-y-auto space-y-2 text-xs">
      
      <!-- Track 1: Video / Visual Clips -->
      <div class="flex items-center h-12 rounded-lg timeline-track p-1">
        <div class="w-48 px-3 font-semibold text-slate-300 flex items-center space-x-2 shrink-0">
          <i class="fa-solid fa-video text-pink-400"></i>
          <span>Track 1: Video</span>
        </div>
        <div class="flex-1 h-full relative bg-slate-900/50 rounded flex items-center p-1 space-x-1">
          <div class="h-full w-2/5 rounded bg-pink-900/60 border border-pink-500/50 flex items-center px-3 space-x-2 shadow-sm">
            <i class="fa-solid fa-image text-pink-300 text-[10px]"></i>
            <span class="font-medium text-pink-200 truncate text-[11px]">Cyberpunk Skyline (FLUX)</span>
          </div>
          <div class="h-full w-3/5 rounded bg-pink-900/40 border border-pink-500/30 flex items-center px-3 space-x-2">
            <i class="fa-solid fa-image text-pink-300 text-[10px]"></i>
            <span class="font-medium text-pink-200 truncate text-[11px]">Neon Cityscape (05.0s - 15.0s)</span>
          </div>
        </div>
      </div>

      <!-- Track 2: Subtitles & Text Overlays -->
      <div class="flex items-center h-10 rounded-lg timeline-track p-1">
        <div class="w-48 px-3 font-semibold text-slate-300 flex items-center space-x-2 shrink-0">
          <i class="fa-solid fa-closed-captioning text-yellow-400"></i>
          <span>Track 2: Subtitle</span>
        </div>
        <div class="flex-1 h-full relative bg-slate-900/50 rounded flex items-center p-1">
          <div class="h-full w-1/3 ml-12 rounded bg-yellow-900/50 border border-yellow-500/40 flex items-center px-3 space-x-2">
            <i class="fa-solid fa-font text-yellow-300 text-[10px]"></i>
            <span class="font-medium text-yellow-200 truncate text-[10px]">SHIV AI V2.0 ENGINE</span>
          </div>
        </div>
      </div>

      <!-- Track 3: Audio / Voiceover -->
      <div class="flex items-center h-10 rounded-lg timeline-track p-1">
        <div class="w-48 px-3 font-semibold text-slate-300 flex items-center space-x-2 shrink-0">
          <i class="fa-solid fa-music text-indigo-400"></i>
          <span>Track 3: Audio</span>
        </div>
        <div class="flex-1 h-full relative bg-slate-900/50 rounded flex items-center p-1">
          <div class="h-full w-3/4 rounded bg-indigo-900/50 border border-indigo-500/40 flex items-center px-3 space-x-2">
            <i class="fa-solid fa-waveform text-indigo-300 text-[10px]"></i>
            <span class="font-medium text-indigo-200 truncate text-[10px]">Neural Voiceover Synthesis (12.0s)</span>
          </div>
        </div>
      </div>

    </div>
  </footer>

  <script>
    let isPlaying = false;
    let currentTime = 0;
    let totalDuration = 15;
    let playInterval = null;

    function setRatio(ratio) {
      const box = document.getElementById('player-box');
      document.querySelectorAll('[id^="ratio-"]').forEach(btn => {
        btn.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-white';
      });

      if (ratio === '16:9') {
        box.style.width = '640px';
        box.style.height = '360px';
        document.getElementById('ratio-16-9').className = 'px-2.5 py-1 rounded bg-slate-800 text-white font-medium';
      } else if (ratio === '9:16') {
        box.style.width = '240px';
        box.style.height = '426px';
        document.getElementById('ratio-9-16').className = 'px-2.5 py-1 rounded bg-slate-800 text-white font-medium';
      } else if (ratio === '1:1') {
        box.style.width = '380px';
        box.style.height = '380px';
        document.getElementById('ratio-1-1').className = 'px-2.5 py-1 rounded bg-slate-800 text-white font-medium';
      }
    }

    function togglePlay() {
      isPlaying = !isPlaying;
      updatePlayIcons();

      if (isPlaying) {
        playInterval = setInterval(() => {
          currentTime += 0.1;
          if (currentTime >= totalDuration) {
            currentTime = 0;
          }
          document.getElementById('scrubber').value = currentTime;
          updateTimeDisplay();
        }, 100);
      } else {
        clearInterval(playInterval);
      }
    }

    function stopPlayback() {
      isPlaying = false;
      clearInterval(playInterval);
      currentTime = 0;
      document.getElementById('scrubber').value = 0;
      updateTimeDisplay();
      updatePlayIcons();
    }

    function onScrub(val) {
      currentTime = parseFloat(val);
      updateTimeDisplay();
    }

    function updateTimeDisplay() {
      const curStr = currentTime < 10 ? `00:0${currentTime.toFixed(1)}` : `00:${currentTime.toFixed(1)}`;
      document.getElementById('time-display').innerText = `${curStr} / 00:15.0`;
    }

    function updatePlayIcons() {
      const cIcon = document.getElementById('play-center-icon');
      const bIcon = document.getElementById('play-bar-icon');
      if (isPlaying) {
        cIcon.className = 'fa-solid fa-pause';
        bIcon.className = 'fa-solid fa-pause';
      } else {
        cIcon.className = 'fa-solid fa-play ml-1';
        bIcon.className = 'fa-solid fa-play';
      }
    }

    async function generateImageClip() {
      const prompt = document.getElementById('ai-image-prompt').value;
      const btn = event.target;
      btn.innerText = 'Synthesizing with FLUX...';
      try {
        const res = await fetch('/v2/media/image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, aspect_ratio: '16:9' })
        });
        const data = await res.json();
        if (data.url) {
          document.getElementById('player-bg').src = data.url;
        }
        btn.innerText = 'Added to Timeline! ✅';
        setTimeout(() => { btn.innerText = 'Generate & Add to Timeline 🎨'; }, 2000);
      } catch (e) {
        btn.innerText = 'Failed: ' + e.message;
      }
    }

    async function generateAudioTrack() {
      const text = document.getElementById('ai-tts-text').value;
      const btn = event.target;
      btn.innerText = 'Synthesizing Voice...';
      try {
        const res = await fetch('/v2/voice/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, voice: 'en-US-ChristopherNeural' })
        });
        const blob = await res.blob();
        const audio = new Audio(URL.createObjectURL(blob));
        audio.play();
        btn.innerText = 'Voice Track Added! 🔊';
        setTimeout(() => { btn.innerText = 'Synthesize & Add Audio 🎙️'; }, 2000);
      } catch (e) {
        btn.innerText = 'Failed: ' + e.message;
      }
    }

    function addTextOverlay() {
      const text = document.getElementById('text-overlay-input').value;
      document.getElementById('player-overlay').innerText = text;
    }

    async function exportProject() {
      const payload = {
        name: 'ShivAI Creative Export',
        aspect_ratio: '16:9',
        fps: 30,
        clips: [{ name: 'Intro Slide', start_time: 0.0, end_time: 5.0 }],
        text_overlays: [{ text: document.getElementById('player-overlay').innerText, start_time: 1.0, end_time: 4.0 }]
      };

      try {
        const res = await fetch('/v2/studios/video/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const manifest = await res.json();
        const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'video_timeline_manifest.json';
        a.click();
      } catch (e) {
        alert('Export failed: ' + e.message);
      }
    }
  </script>
</body>
</html>
"""
