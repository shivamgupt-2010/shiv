"""
ShivAI Codespaces Web IDE Interface.
Provides a rich browser-based development environment with:
- Project file tree explorer
- In-browser code editor with instant saving and AST patching
- Split-screen live preview iframe with responsive device toggles
- Sandboxed terminal console with command execution and output streaming
- 1-click ZIP project download and new app scaffolding
"""

CODESPACES_UI_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SHIV Codespaces — Cloud Development Studio</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Inter', sans-serif; background-color: #090d16; color: #f1f5f9; }
    .code-font { font-family: 'Fira Code', monospace; }
    .glass { background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card { background: rgba(30, 41, 59, 0.6); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.06); }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.6); }
    ::-webkit-scrollbar-thumb { background: rgba(100, 116, 139, 0.4); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(100, 116, 139, 0.7); }
    .active-file { background: rgba(99, 102, 241, 0.2); border-left: 2px solid #818cf8; color: #fff; }
  </style>
</head>
<body class="h-screen flex flex-col overflow-hidden">

  <!-- Top Navigation Header -->
  <header class="h-14 border-b border-slate-800 bg-slate-950/90 backdrop-blur px-4 flex items-center justify-between shrink-0 z-20">
    <div class="flex items-center space-x-4">
      <div class="flex items-center space-x-2.5">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <i class="fa-solid fa-code text-white text-sm"></i>
        </div>
        <div>
          <span class="font-bold text-sm tracking-wide text-white">SHIV<span class="text-indigo-400"> CODESPACES</span></span>
          <span class="text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-1.5 py-0.5 rounded ml-1 font-mono">IDE v2.0</span>
        </div>
      </div>

      <div class="h-5 w-px bg-slate-800"></div>

      <!-- Workspace Selector -->
      <div class="flex items-center space-x-2">
        <label class="text-xs text-slate-400">Workspace:</label>
        <select id="codespace-select" onchange="onCodespaceChange()" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
          <option value="">Loading workspaces...</option>
        </select>
        <button onclick="openNewModal()" class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 shadow-sm transition">
          <i class="fa-solid fa-plus text-[10px]"></i>
          <span>New Project</span>
        </button>
      </div>
    </div>

    <!-- Right Actions -->
    <div class="flex items-center space-x-3">
      <button onclick="saveCurrentFile()" id="save-btn" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 shadow-sm transition">
        <i class="fa-solid fa-floppy-disk text-xs"></i>
        <span>Save (Ctrl+S)</span>
      </button>
      <button onclick="downloadZip()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium flex items-center space-x-1.5 border border-slate-700 transition">
        <i class="fa-solid fa-file-zipper text-xs"></i>
        <span>Download ZIP</span>
      </button>
      <a id="ext-preview-link" href="#" target="_blank" class="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition">
        <i class="fa-solid fa-arrow-up-right-from-square text-xs"></i>
        <span>Launch App</span>
      </a>
      <a href="/admin" class="px-2.5 py-1 text-slate-400 hover:text-white text-xs transition">
        <i class="fa-solid fa-gauge-high mr-1"></i> Admin Hub
      </a>
    </div>
  </header>

  <!-- Main IDE Split Layout -->
  <div class="flex-1 flex overflow-hidden">

    <!-- 1. Left Sidebar: File Explorer Tree -->
    <aside class="w-64 border-r border-slate-800 bg-slate-950/70 flex flex-col shrink-0">
      <div class="p-3 border-b border-slate-800/80 flex items-center justify-between">
        <span class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
          <i class="fa-regular fa-folder-open text-indigo-400"></i>
          <span>Explorer</span>
        </span>
        <div class="flex items-center space-x-1">
          <button onclick="promptNewFile()" title="New File" class="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white text-xs">
            <i class="fa-solid fa-file-circle-plus"></i>
          </button>
          <button onclick="refreshFiles()" title="Refresh" class="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white text-xs">
            <i class="fa-solid fa-rotate-right"></i>
          </button>
        </div>
      </div>
      <div id="files-tree" class="flex-1 overflow-y-auto p-2 space-y-0.5 text-xs text-slate-300">
        <div class="p-4 text-center text-slate-500 italic">No files loaded</div>
      </div>
      <div class="p-2 border-t border-slate-800/80 bg-slate-900/40 text-[11px] text-slate-500 flex justify-between items-center">
        <span id="cs-status-indicator">Connected</span>
        <span id="file-count">0 files</span>
      </div>
    </aside>

    <!-- 2. Center: Code Editor Pane -->
    <div class="flex-1 flex flex-col min-w-0 bg-slate-950/40 border-r border-slate-800">
      <!-- Editor Tabs & Breadcrumb -->
      <div class="h-9 border-b border-slate-800 bg-slate-900/60 px-3 flex items-center justify-between shrink-0">
        <div class="flex items-center space-x-2 text-xs">
          <span id="current-file-icon"><i class="fa-regular fa-file-code text-indigo-400"></i></span>
          <span id="current-file-name" class="font-mono text-slate-200 font-medium">index.html</span>
          <span id="dirty-indicator" class="w-2 h-2 rounded-full bg-amber-400 hidden" title="Unsaved changes"></span>
        </div>
        <div class="flex items-center space-x-3 text-xs text-slate-400">
          <span id="cursor-pos">Ln 1, Col 1</span>
          <button onclick="formatCode()" class="hover:text-indigo-400 transition" title="Format indentation">
            <i class="fa-solid fa-wand-magic-sparkles mr-1"></i> Format
          </button>
        </div>
      </div>

      <!-- Editor Body -->
      <div class="flex-1 relative overflow-hidden flex">
        <textarea id="code-editor" class="flex-1 w-full h-full bg-[#070b14] text-slate-200 code-font text-xs p-4 focus:outline-none resize-none selection:bg-indigo-500/30 leading-relaxed" spellcheck="false" placeholder="Select or open a file to start editing..."></textarea>
      </div>

      <!-- Bottom Drawer: Terminal Console -->
      <div id="terminal-drawer" class="h-44 border-t border-slate-800 bg-slate-950 flex flex-col shrink-0">
        <div class="h-7 bg-slate-900/80 border-b border-slate-800 px-3 flex items-center justify-between text-xs">
          <div class="flex items-center space-x-2">
            <i class="fa-solid fa-terminal text-emerald-400 text-[10px]"></i>
            <span class="font-bold uppercase tracking-wider text-slate-400 text-[10px]">Sandboxed Terminal</span>
          </div>
          <div class="flex items-center space-x-2 text-[10px]">
            <button onclick="clearTerminal()" class="text-slate-400 hover:text-white">Clear</button>
            <button onclick="toggleTerminal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-chevron-down"></i></button>
          </div>
        </div>
        <div id="terminal-logs" class="flex-1 p-2.5 overflow-y-auto code-font text-[11px] text-emerald-400/90 leading-tight space-y-1">
          <div class="text-slate-500">[ShivAI Sandbox Environment Ready. Type bash/cmd commands below]</div>
        </div>
        <div class="p-1.5 border-t border-slate-800/80 flex items-center bg-slate-900/40">
          <span class="text-emerald-400 code-font text-xs px-2">$</span>
          <input type="text" id="terminal-input" onkeydown="onTerminalKey(event)" placeholder="Enter command (e.g. dir, ls, python -V, echo test)..." class="flex-1 bg-transparent code-font text-xs text-slate-200 focus:outline-none">
          <button onclick="runCommand()" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-mono">Run</button>
        </div>
      </div>
    </div>

    <!-- 3. Right: Live Interactive Web Preview -->
    <div id="preview-container" class="w-[45%] flex flex-col shrink-0 bg-slate-950/80">
      <!-- Preview Header Controls -->
      <div class="h-9 border-b border-slate-800 bg-slate-900/80 px-3 flex items-center justify-between shrink-0">
        <div class="flex items-center space-x-2 text-xs">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span class="font-bold text-slate-300">Live Preview</span>
        </div>
        <!-- Device Switcher -->
        <div class="flex items-center space-x-1 bg-slate-950 p-0.5 rounded border border-slate-800">
          <button onclick="setPreviewSize('100%')" title="Desktop" class="px-2 py-0.5 rounded text-xs text-slate-400 hover:text-white hover:bg-slate-800">
            <i class="fa-solid fa-desktop"></i>
          </button>
          <button onclick="setPreviewSize('768px')" title="Tablet" class="px-2 py-0.5 rounded text-xs text-slate-400 hover:text-white hover:bg-slate-800">
            <i class="fa-solid fa-tablet-screen-button"></i>
          </button>
          <button onclick="setPreviewSize('375px')" title="Mobile" class="px-2 py-0.5 rounded text-xs text-slate-400 hover:text-white hover:bg-slate-800">
            <i class="fa-solid fa-mobile-screen"></i>
          </button>
        </div>
        <button onclick="reloadPreview()" class="text-slate-400 hover:text-white text-xs" title="Refresh Preview">
          <i class="fa-solid fa-rotate-right"></i>
        </button>
      </div>

      <!-- Preview Iframe Viewport -->
      <div class="flex-1 bg-slate-900/30 flex items-center justify-center p-2 overflow-auto">
        <div id="preview-wrapper" class="w-full h-full bg-white rounded shadow-xl overflow-hidden transition-all duration-300">
          <iframe id="preview-frame" class="w-full h-full border-0" src="about:blank"></iframe>
        </div>
      </div>
    </div>

  </div>

  <!-- Modal: Create New Project -->
  <div id="new-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center hidden">
    <div class="glass-card max-w-md w-full p-6 rounded-2xl shadow-2xl space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="text-base font-bold text-white flex items-center space-x-2">
          <i class="fa-solid fa-wand-magic-sparkles text-indigo-400"></i>
          <span>Create New Codespace</span>
        </h3>
        <button onclick="closeNewModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="space-y-3 text-xs">
        <div>
          <label class="block text-slate-300 mb-1">Project Name</label>
          <input type="text" id="new-cs-name" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-200" value="CyberPortfolio">
        </div>
        <div>
          <label class="block text-slate-300 mb-1">Scaffold Template</label>
          <select id="new-cs-template" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-200">
            <option value="html5_app">HTML5 + Tailwind CSS Responsive Web App</option>
            <option value="python_fastapi">Python FastAPI Microservice</option>
          </select>
        </div>
        <div>
          <label class="block text-slate-300 mb-1">Description</label>
          <input type="text" id="new-cs-desc" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-200" value="Interactive web experience built with ShivAI.">
        </div>
      </div>
      <div class="pt-2 flex justify-end space-x-2">
        <button onclick="closeNewModal()" class="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 text-xs font-medium hover:bg-slate-700">Cancel</button>
        <button onclick="createCodespaceSubmit()" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">Scaffold Project</button>
      </div>
    </div>
  </div>

  <script>
    let currentCodespaceId = null;
    let activeFilePath = 'index.html';
    let fileContents = {};
    let isDirty = false;

    // Initialize IDE
    window.addEventListener('DOMContentLoaded', async () => {
      await loadWorkspaces();
      setupShortcuts();
      setupEditorListeners();
    });

    async function loadWorkspaces() {
      try {
        const res = await fetch('/v2/codespaces');
        const data = await res.json();
        const select = document.getElementById('codespace-select');
        select.innerHTML = '';

        if (!data || data.length === 0) {
          // Auto create a default project if none exist
          const createRes = await fetch('/v2/codespaces', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: 'WebStudio Demo', template: 'html5_app', description: 'Default ShivAI Web App' })
          });
          const newCs = await createRes.json();
          const opt = document.createElement('option');
          opt.value = newCs.codespace_id;
          opt.innerText = newCs.name;
          select.appendChild(opt);
          currentCodespaceId = newCs.codespace_id;
        } else {
          data.forEach(cs => {
            const opt = document.createElement('option');
            opt.value = cs.codespace_id;
            opt.innerText = `${cs.name} (${cs.template})`;
            select.appendChild(opt);
          });
          currentCodespaceId = data[0].codespace_id;
        }

        await refreshFiles();
        reloadPreview();
      } catch (e) {
        logTerminal('Failed to load workspaces: ' + e.message, 'error');
      }
    }

    async function onCodespaceChange() {
      currentCodespaceId = document.getElementById('codespace-select').value;
      await refreshFiles();
      reloadPreview();
    }

    async function refreshFiles() {
      if (!currentCodespaceId) return;
      try {
        const res = await fetch(`/v2/codespaces/${currentCodespaceId}/files`);
        const files = await res.json();
        renderFileTree(files);
        document.getElementById('file-count').innerText = `${files.length} files`;

        // Automatically open index.html or first file
        const preferred = files.find(f => f.name === 'index.html') || files[0];
        if (preferred) {
          openFile(preferred.path);
        }
      } catch (e) {
        logTerminal('Error fetching files: ' + e.message, 'error');
      }
    }

    function renderFileTree(files) {
      const tree = document.getElementById('files-tree');
      tree.innerHTML = '';
      files.forEach(f => {
        const item = document.createElement('div');
        const isActive = f.path === activeFilePath;
        item.className = `px-2 py-1.5 rounded cursor-pointer flex items-center justify-between group hover:bg-slate-800/60 transition ${isActive ? 'active-file' : ''}`;
        
        let iconClass = 'fa-regular fa-file-code text-slate-400';
        if (f.name.endsWith('.html')) iconClass = 'fa-brands fa-html5 text-orange-400';
        else if (f.name.endsWith('.css')) iconClass = 'fa-brands fa-css3-alt text-cyan-400';
        else if (f.name.endsWith('.js')) iconClass = 'fa-brands fa-js text-yellow-400';
        else if (f.name.endsWith('.py')) iconClass = 'fa-brands fa-python text-blue-400';
        else if (f.name.endsWith('.json')) iconClass = 'fa-solid fa-code text-emerald-400';

        item.innerHTML = `
          <div class="flex items-center space-x-2 truncate">
            <i class="${iconClass}"></i>
            <span class="truncate">${f.name}</span>
          </div>
          <span class="text-[10px] text-slate-500 opacity-0 group-hover:opacity-100 transition">${(f.size_bytes / 1024).toFixed(1)}k</span>
        `;
        item.onclick = () => openFile(f.path);
        tree.appendChild(item);
      });
    }

    async function openFile(filePath) {
      activeFilePath = filePath;
      document.getElementById('current-file-name').innerText = filePath;
      try {
        const res = await fetch(`/v2/codespaces/${currentCodespaceId}/files?file_path=${encodeURIComponent(filePath)}`);
        const data = await res.json();
        document.getElementById('code-editor').value = data.content;
        fileContents[filePath] = data.content;
        setDirty(false);
        logTerminal(`Opened file: ${filePath}`);
        
        // Re-render tree active state
        document.querySelectorAll('#files-tree > div').forEach(el => {
          if (el.innerText.includes(filePath.split('/').pop())) {
            el.classList.add('active-file');
          } else {
            el.classList.remove('active-file');
          }
        });
      } catch (e) {
        logTerminal('Failed to read file: ' + e.message, 'error');
      }
    }

    async function saveCurrentFile() {
      if (!currentCodespaceId || !activeFilePath) return;
      const content = document.getElementById('code-editor').value;
      const saveBtn = document.getElementById('save-btn');
      saveBtn.innerText = 'Saving...';
      try {
        const res = await fetch(`/v2/codespaces/${currentCodespaceId}/files`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: activeFilePath, content })
        });
        if (res.ok) {
          setDirty(false);
          saveBtn.innerHTML = '<i class="fa-solid fa-check mr-1"></i> Saved!';
          setTimeout(() => { saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk mr-1"></i> Save (Ctrl+S)'; }, 1500);
          logTerminal(`Successfully saved: ${activeFilePath}`);
          reloadPreview();
        } else {
          throw new Error('Save failed with status ' + res.status);
        }
      } catch (e) {
        logTerminal('Save error: ' + e.message, 'error');
        saveBtn.innerText = 'Save Failed!';
      }
    }

    function setDirty(val) {
      isDirty = val;
      const dot = document.getElementById('dirty-indicator');
      if (val) dot.classList.remove('hidden');
      else dot.classList.add('hidden');
    }

    function reloadPreview() {
      if (!currentCodespaceId) return;
      const url = `/v2/codespaces/${currentCodespaceId}/preview?t=` + Date.now();
      document.getElementById('preview-frame').src = url;
      document.getElementById('ext-preview-link').href = url;
    }

    function setPreviewSize(width) {
      const wrap = document.getElementById('preview-wrapper');
      wrap.style.width = width;
    }

    function setupShortcuts() {
      window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
          e.preventDefault();
          saveCurrentFile();
        }
      });
    }

    function setupEditorListeners() {
      const editor = document.getElementById('code-editor');
      editor.addEventListener('input', () => setDirty(true));
      editor.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
          e.preventDefault();
          const start = editor.selectionStart;
          const end = editor.selectionEnd;
          editor.value = editor.value.substring(0, start) + '  ' + editor.value.substring(end);
          editor.selectionStart = editor.selectionEnd = start + 2;
        }
      });
    }

    // Terminal runner
    async function runCommand() {
      const input = document.getElementById('terminal-input');
      const cmd = input.value.trim();
      if (!cmd || !currentCodespaceId) return;
      input.value = '';
      logTerminal(`$ ${cmd}`);

      try {
        const res = await fetch(`/v2/codespaces/${currentCodespaceId}/terminal`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: cmd })
        });
        const data = await res.json();
        if (data.stdout) logTerminal(data.stdout);
        if (data.stderr) logTerminal(data.stderr, 'error');
        logTerminal(`[Process exited with code ${data.exit_code} in ${(data.execution_time_seconds || 0.05).toFixed(2)}s]`, 'dim');
      } catch (e) {
        logTerminal('Execution failed: ' + e.message, 'error');
      }
    }

    function onTerminalKey(e) {
      if (e.key === 'Enter') runCommand();
    }

    function logTerminal(msg, type = 'info') {
      const logs = document.getElementById('terminal-logs');
      const line = document.createElement('div');
      if (type === 'error') line.className = 'text-rose-400';
      else if (type === 'dim') line.className = 'text-slate-500 text-[10px]';
      else line.className = 'text-emerald-400';
      line.innerText = msg;
      logs.appendChild(line);
      logs.scrollTop = logs.scrollHeight;
    }

    function clearTerminal() {
      document.getElementById('terminal-logs').innerHTML = '';
    }

    function toggleTerminal() {
      const drawer = document.getElementById('terminal-drawer');
      if (drawer.style.height === '30px') {
        drawer.style.height = '176px';
      } else {
        drawer.style.height = '30px';
      }
    }

    function downloadZip() {
      if (!currentCodespaceId) return;
      window.open(`/v2/codespaces/${currentCodespaceId}/download`, '_blank');
    }

    // Modal creation
    function openNewModal() { document.getElementById('new-modal').classList.remove('hidden'); }
    function closeNewModal() { document.getElementById('new-modal').classList.add('hidden'); }

    async function createCodespaceSubmit() {
      const name = document.getElementById('new-cs-name').value;
      const template = document.getElementById('new-cs-template').value;
      const description = document.getElementById('new-cs-desc').value;
      closeNewModal();

      try {
        const res = await fetch('/v2/codespaces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, template, description })
        });
        const newCs = await res.json();
        await loadWorkspaces();
        document.getElementById('codespace-select').value = newCs.codespace_id;
        onCodespaceChange();
      } catch (e) {
        alert('Failed to scaffold project: ' + e.message);
      }
    }

    async function promptNewFile() {
      const name = prompt('Enter new file name (e.g. style.css, script.js, utils.py):');
      if (!name || !currentCodespaceId) return;
      await fetch(`/v2/codespaces/${currentCodespaceId}/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: name, content: '// ' + name + '\n' })
      });
      await refreshFiles();
      openFile(name);
    }
  </script>
</body>
</html>
"""
