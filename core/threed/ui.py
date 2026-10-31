"""
ShivAI 3D Asset Studio & Three.js Viewport Interface.
Provides interactive 3D WebGL asset modeling, procedural geometry generation,
PBR material editing, orbit camera controls, and binary GLB/OBJ export.
"""

THREED_STUDIO_UI_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SHIV 3D Studio — 3D Asset Modeling & WebGL Viewport</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
  <!-- Three.js and OrbitControls -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/exporters/GLTFExporter.js"></script>
  <style>
    body { font-family: 'Inter', sans-serif; background-color: #07090e; color: #f1f5f9; }
    .glass-panel { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(100, 116, 139, 0.3); border-radius: 4px; }
  </style>
</head>
<body class="h-screen flex flex-col overflow-hidden">

  <!-- Top Navigation Header -->
  <header class="h-14 border-b border-slate-800 bg-slate-950/90 backdrop-blur px-4 flex items-center justify-between shrink-0 z-20">
    <div class="flex items-center space-x-4">
      <div class="flex items-center space-x-2.5">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
          <i class="fa-solid fa-cube text-white text-sm"></i>
        </div>
        <div>
          <span class="font-bold text-sm tracking-wide text-white">SHIV<span class="text-purple-400"> 3D STUDIO</span></span>
          <span class="text-[10px] bg-purple-500/10 text-purple-400 border border-purple-500/20 px-1.5 py-0.5 rounded ml-1 font-mono">WebGL Engine</span>
        </div>
      </div>
      <div class="h-5 w-px bg-slate-800"></div>
      <!-- Preset Model Generator -->
      <div class="flex items-center space-x-2 text-xs">
        <span class="text-slate-400">Quick Mesh:</span>
        <button onclick="loadMesh('rocket')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">🚀 Golden Rocket</button>
        <button onclick="loadMesh('sphere')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">🔮 Cyber Sphere</button>
        <button onclick="loadMesh('cube')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">🧊 Crystal Cube</button>
        <button onclick="loadMesh('torus')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">🍩 Plasma Torus</button>
      </div>
    </div>

    <!-- Right Header Actions -->
    <div class="flex items-center space-x-3 text-xs">
      <button onclick="toggleAutoRotate()" id="rotate-btn" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center space-x-1.5">
        <i class="fa-solid fa-arrows-rotate"></i>
        <span>Auto-Rotate</span>
      </button>
      <button onclick="exportGLB()" class="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-semibold flex items-center space-x-1.5 shadow-lg shadow-purple-500/20 transition">
        <i class="fa-solid fa-download"></i>
        <span>Export .GLB</span>
      </button>
      <a href="/admin" class="px-2.5 py-1 text-slate-400 hover:text-white transition">
        <i class="fa-solid fa-gauge-high mr-1"></i> Admin Hub
      </a>
    </div>
  </header>

  <!-- 3D Studio Workspace -->
  <div class="flex-1 flex overflow-hidden relative">

    <!-- 3D WebGL Canvas Area -->
    <div id="canvas-container" class="flex-1 w-full h-full relative cursor-grab active:cursor-grabbing">
      <!-- HUD Overlay -->
      <div class="absolute top-4 left-4 z-10 glass-panel p-3 rounded-xl pointer-events-none space-y-1 text-xs">
        <div class="font-bold text-white flex items-center space-x-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span id="model-name">Golden Rocket (Procedural)</span>
        </div>
        <div class="text-[11px] text-slate-400 font-mono space-y-0.5">
          <div>Vertices: <span id="stat-verts" class="text-slate-200">1,420</span></div>
          <div>Triangles: <span id="stat-tris" class="text-slate-200">2,840</span></div>
          <div>Lighting: <span class="text-purple-400">PBR Studio 3-Point</span></div>
        </div>
      </div>

      <!-- Viewport Interaction Instructions -->
      <div class="absolute bottom-4 left-4 z-10 text-[11px] text-slate-500 glass-panel px-3 py-1.5 rounded-lg pointer-events-none">
        Left-click + Drag to Rotate • Scroll to Zoom • Right-click to Pan
      </div>
    </div>

    <!-- Right Control & Inspector Sidebar -->
    <aside class="w-80 border-l border-slate-800 glass-panel flex flex-col shrink-0 z-10 overflow-y-auto p-4 space-y-5 text-xs">
      
      <!-- AI Generator Box -->
      <div class="p-3.5 rounded-xl bg-purple-950/20 border border-purple-500/20 space-y-2.5">
        <span class="text-[11px] font-bold uppercase tracking-wider text-purple-400 flex items-center space-x-1.5">
          <i class="fa-solid fa-wand-magic-sparkles"></i>
          <span>AI Procedural 3D Generator</span>
        </span>
        <input type="text" id="ai-3d-prompt" value="Golden rocket with thruster flare" class="w-full bg-slate-900/90 border border-slate-700 rounded-lg p-2 text-slate-200 text-xs">
        <button onclick="generateWithAI()" class="w-full py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg font-semibold transition">
          Generate 3D Model ⚡
        </button>
      </div>

      <!-- Mesh Geometry Controls -->
      <div class="space-y-3">
        <span class="font-bold uppercase tracking-wider text-slate-400 text-[11px]">Procedural Mesh</span>
        <div>
          <label class="block text-slate-400 mb-1">Base Geometry</label>
          <select id="mesh-selector" onchange="loadMesh(this.value)" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200">
            <option value="rocket">Multi-part Rocket</option>
            <option value="sphere">UV Sphere</option>
            <option value="cube">Box / Cube</option>
            <option value="cylinder">Cylinder</option>
            <option value="torus">Torus (Donut)</option>
            <option value="cone">Cone</option>
          </select>
        </div>
      </div>

      <!-- PBR Material Inspector -->
      <div class="space-y-3 border-t border-slate-800 pt-4">
        <span class="font-bold uppercase tracking-wider text-slate-400 text-[11px]">PBR Material Properties</span>
        
        <div>
          <label class="block text-slate-400 mb-1">Albedo Color</label>
          <div class="flex items-center space-x-2">
            <input type="color" id="mat-color" value="#f59e0b" onchange="updateMaterial()" class="w-8 h-8 rounded bg-transparent cursor-pointer border-0">
            <input type="text" id="mat-color-hex" value="#f59e0b" oninput="onHexInput(this.value)" class="flex-1 bg-slate-900 border border-slate-700 rounded-lg p-1.5 font-mono text-xs text-slate-200">
          </div>
        </div>

        <div>
          <div class="flex justify-between text-slate-400 mb-1">
            <span>Metallic</span>
            <span id="val-metallic" class="font-mono text-slate-200">0.85</span>
          </div>
          <input type="range" id="mat-metallic" min="0" max="1" step="0.05" value="0.85" oninput="updateMaterial()" class="w-full accent-purple-500">
        </div>

        <div>
          <div class="flex justify-between text-slate-400 mb-1">
            <span>Roughness</span>
            <span id="val-roughness" class="font-mono text-slate-200">0.20</span>
          </div>
          <input type="range" id="mat-roughness" min="0" max="1" step="0.05" value="0.20" oninput="updateMaterial()" class="w-full accent-purple-500">
        </div>

        <div class="flex items-center justify-between pt-1">
          <span class="text-slate-400">Wireframe Mode</span>
          <input type="checkbox" id="mat-wireframe" onchange="updateMaterial()" class="rounded accent-purple-500 w-4 h-4 cursor-pointer">
        </div>
      </div>

      <!-- Lighting & Environment -->
      <div class="space-y-3 border-t border-slate-800 pt-4">
        <span class="font-bold uppercase tracking-wider text-slate-400 text-[11px]">Environment & Lighting</span>
        <div>
          <div class="flex justify-between text-slate-400 mb-1">
            <span>Sunlight Intensity</span>
            <span id="val-sun" class="font-mono text-slate-200">1.2</span>
          </div>
          <input type="range" id="light-sun" min="0" max="3" step="0.1" value="1.2" oninput="updateLights()" class="w-full accent-purple-500">
        </div>
        <div class="flex items-center justify-between">
          <span class="text-slate-400">Ground Grid</span>
          <input type="checkbox" id="env-grid" checked onchange="toggleGrid(this.checked)" class="rounded accent-purple-500 w-4 h-4 cursor-pointer">
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="border-t border-slate-800 pt-4 space-y-2">
        <button onclick="resetCamera()" class="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg transition font-medium">
          <i class="fa-solid fa-camera-rotate mr-1"></i> Reset Camera View
        </button>
      </div>

    </aside>

  </div>

  <script>
    let scene, camera, renderer, controls;
    let currentMeshGroup = null;
    let mainMaterial = null;
    let dirLight, ambLight, gridHelper;
    let autoRotate = true;

    window.addEventListener('DOMContentLoaded', () => {
      initThreeJS();
      loadMesh('rocket');
    });

    function initThreeJS() {
      const container = document.getElementById('canvas-container');
      const width = container.clientWidth;
      const height = container.clientHeight;

      scene = new THREE.Scene();
      scene.background = new THREE.Color(0x07090e);
      scene.fog = new THREE.FogExp2(0x07090e, 0.035);

      camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
      camera.position.set(4, 3, 6);

      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      container.appendChild(renderer.domElement);

      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.autoRotate = autoRotate;
      controls.autoRotateSpeed = 2.0;

      // Lights
      ambLight = new THREE.AmbientLight(0xffffff, 0.5);
      scene.add(ambLight);

      dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
      dirLight.position.set(5, 10, 7);
      dirLight.castShadow = true;
      scene.add(dirLight);

      const purpleFill = new THREE.PointLight(0x8b5cf6, 1.5, 20);
      purpleFill.position.set(-5, 3, -3);
      scene.add(purpleFill);

      // Grid helper
      gridHelper = new THREE.GridHelper(20, 20, 0x6366f1, 0x1e293b);
      gridHelper.position.y = -1.2;
      scene.add(gridHelper);

      // Shared PBR Material
      mainMaterial = new THREE.MeshStandardMaterial({
        color: new THREE.Color('#f59e0b'),
        metalness: 0.85,
        roughness: 0.20,
      });

      window.addEventListener('resize', onWindowResize);
      animate();
    }

    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }

    function onWindowResize() {
      const container = document.getElementById('canvas-container');
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    }

    function loadMesh(type) {
      if (currentMeshGroup) {
        scene.remove(currentMeshGroup);
      }

      currentMeshGroup = new THREE.Group();
      document.getElementById('mesh-selector').value = type;

      if (type === 'rocket') {
        document.getElementById('model-name').innerText = 'Golden Rocket (Procedural)';
        // Fuselage
        const bodyGeo = new THREE.CylinderGeometry(0.5, 0.6, 2.2, 32);
        const body = new THREE.Mesh(bodyGeo, mainMaterial);
        body.position.y = 0.5;
        body.castShadow = true;
        currentMeshGroup.add(body);

        // Nose Cone
        const noseGeo = new THREE.ConeGeometry(0.5, 0.9, 32);
        const noseMat = mainMaterial.clone();
        noseMat.color.setHex(0xef4444);
        const nose = new THREE.Mesh(noseGeo, noseMat);
        nose.position.y = 2.05;
        currentMeshGroup.add(nose);

        // Thruster Cone
        const thrusterGeo = new THREE.ConeGeometry(0.35, 0.5, 24);
        const flameMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
        const thruster = new THREE.Mesh(thrusterGeo, flameMat);
        thruster.position.y = -0.85;
        currentMeshGroup.add(thruster);

        // 4 Fins
        const finGeo = new THREE.BoxGeometry(0.08, 0.6, 0.4);
        for (let i = 0; i < 4; i++) {
          const fin = new THREE.Mesh(finGeo, mainMaterial);
          const angle = (i * Math.PI) / 2;
          fin.position.set(Math.cos(angle) * 0.6, -0.2, Math.sin(angle) * 0.6);
          fin.rotation.y = -angle;
          currentMeshGroup.add(fin);
        }
      } else if (type === 'sphere') {
        document.getElementById('model-name').innerText = 'Cyber Sphere';
        const geo = new THREE.SphereGeometry(1.2, 48, 48);
        const mesh = new THREE.Mesh(geo, mainMaterial);
        mesh.castShadow = true;
        currentMeshGroup.add(mesh);
      } else if (type === 'cube') {
        document.getElementById('model-name').innerText = 'Crystal Cube';
        const geo = new THREE.BoxGeometry(1.6, 1.6, 1.6);
        const mesh = new THREE.Mesh(geo, mainMaterial);
        mesh.castShadow = true;
        currentMeshGroup.add(mesh);
      } else if (type === 'cylinder') {
        document.getElementById('model-name').innerText = 'Parametric Cylinder';
        const geo = new THREE.CylinderGeometry(0.8, 0.8, 2, 32);
        const mesh = new THREE.Mesh(geo, mainMaterial);
        mesh.castShadow = true;
        currentMeshGroup.add(mesh);
      } else if (type === 'torus') {
        document.getElementById('model-name').innerText = 'Plasma Torus';
        const geo = new THREE.TorusGeometry(1.0, 0.35, 24, 64);
        const mesh = new THREE.Mesh(geo, mainMaterial);
        mesh.castShadow = true;
        currentMeshGroup.add(mesh);
      } else if (type === 'cone') {
        document.getElementById('model-name').innerText = 'Geometric Cone';
        const geo = new THREE.ConeGeometry(1.0, 2.0, 32);
        const mesh = new THREE.Mesh(geo, mainMaterial);
        mesh.castShadow = true;
        currentMeshGroup.add(mesh);
      }

      scene.add(currentMeshGroup);
      updateCounts();
    }

    function updateCounts() {
      let verts = 0, tris = 0;
      currentMeshGroup.traverse(child => {
        if (child.isMesh && child.geometry) {
          verts += child.geometry.attributes.position ? child.geometry.attributes.position.count : 0;
          tris += child.geometry.index ? child.geometry.index.count / 3 : (child.geometry.attributes.position.count / 3);
        }
      });
      document.getElementById('stat-verts').innerText = verts.toLocaleString();
      document.getElementById('stat-tris').innerText = Math.round(tris).toLocaleString();
    }

    function updateMaterial() {
      const color = document.getElementById('mat-color').value;
      const metallic = parseFloat(document.getElementById('mat-metallic').value);
      const roughness = parseFloat(document.getElementById('mat-roughness').value);
      const wireframe = document.getElementById('mat-wireframe').checked;

      document.getElementById('mat-color-hex').value = color;
      document.getElementById('val-metallic').innerText = metallic.toFixed(2);
      document.getElementById('val-roughness').innerText = roughness.toFixed(2);

      mainMaterial.color.set(color);
      mainMaterial.metalness = metallic;
      mainMaterial.roughness = roughness;
      mainMaterial.wireframe = wireframe;
      mainMaterial.needsUpdate = true;
    }

    function onHexInput(hex) {
      if (/^#[0-9A-F]{6}$/i.test(hex)) {
        document.getElementById('mat-color').value = hex;
        updateMaterial();
      }
    }

    function updateLights() {
      const val = parseFloat(document.getElementById('light-sun').value);
      dirLight.intensity = val;
      document.getElementById('val-sun').innerText = val.toFixed(1);
    }

    function toggleGrid(show) {
      gridHelper.visible = show;
    }

    function toggleAutoRotate() {
      autoRotate = !autoRotate;
      controls.autoRotate = autoRotate;
      const btn = document.getElementById('rotate-btn');
      if (autoRotate) {
        btn.classList.add('bg-purple-600/30', 'text-purple-300', 'border-purple-500/40');
      } else {
        btn.classList.remove('bg-purple-600/30', 'text-purple-300', 'border-purple-500/40');
      }
    }

    function resetCamera() {
      camera.position.set(4, 3, 6);
      controls.target.set(0, 0, 0);
    }

    function exportGLB() {
      const exporter = new THREE.GLTFExporter();
      exporter.parse(
        currentMeshGroup,
        (gltf) => {
          const blob = new Blob([gltf], { type: 'model/gltf-binary' });
          const link = document.createElement('a');
          link.href = URL.createObjectURL(blob);
          link.download = (document.getElementById('model-name').innerText.replace(/[^a-zA-Z0-9]/g, '_')) + '.glb';
          link.click();
        },
        { binary: true }
      );
    }

    async function generateWithAI() {
      const prompt = document.getElementById('ai-3d-prompt').value.toLowerCase();
      if (prompt.includes('rocket')) {
        loadMesh('rocket');
        document.getElementById('mat-color').value = '#f59e0b';
      } else if (prompt.includes('sphere') || prompt.includes('orb')) {
        loadMesh('sphere');
        document.getElementById('mat-color').value = '#38bdf8';
      } else if (prompt.includes('cube') || prompt.includes('crystal')) {
        loadMesh('cube');
        document.getElementById('mat-color').value = '#a855f7';
      } else if (prompt.includes('donut') || prompt.includes('torus')) {
        loadMesh('torus');
        document.getElementById('mat-color').value = '#ec4899';
      } else {
        loadMesh('rocket');
      }
      updateMaterial();
    }
  </script>
</body>
</html>
"""
