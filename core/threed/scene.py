"""
ShivAI 3D Asset Studio: Scene Management & Browser Viewport Generator.
Provides Three.js browser visualization, PBR material properties, and permanent artifact exports.
"""
import uuid
import logging
from typing import Dict, Any, Optional

from core.threed.generator import ProceduralMeshGenerator, MeshData
from core.execution.artifacts import artifact_manager, StoredArtifact

logger = logging.getLogger("shivai.threed.scene")


class ThreeDAssetStudio:
    """Coordinates 3D mesh synthesis, material assignment, and viewport packaging."""

    def __init__(self):
        self._scenes: Dict[str, Dict[str, Any]] = {}

    def generate_asset(
        self,
        name: str,
        mesh_type: str = "cube",
        color_hex: str = "#3B82F6",
        metallic: float = 0.2,
        roughness: float = 0.5,
        wireframe: bool = False,
    ) -> Dict[str, Any]:
        """Generates a procedural 3D model with PBR material specification."""
        mesh_type_lower = mesh_type.lower()
        if "sphere" in mesh_type_lower:
            mesh = ProceduralMeshGenerator.create_sphere(radius=1.0, segments=24, rings=16, name=name)
        elif "cylinder" in mesh_type_lower:
            mesh = ProceduralMeshGenerator.create_cylinder(radius=0.6, height=2.0, segments=24, name=name)
        else:
            mesh = ProceduralMeshGenerator.create_cube(size=1.5, name=name)

        obj_str = ProceduralMeshGenerator.to_obj_string(mesh)
        glb_bytes = ProceduralMeshGenerator.to_glb_bytes(mesh)

        asset_id = f"3d_{uuid.uuid4().hex[:10]}"
        scene_info = {
            "asset_id": asset_id,
            "name": name,
            "mesh_type": mesh_type,
            "vertex_count": len(mesh.vertices),
            "triangle_count": len(mesh.indices) // 3,
            "color": color_hex,
            "metallic": metallic,
            "roughness": roughness,
            "wireframe": wireframe,
            "obj_content": obj_str,
            "glb_bytes": glb_bytes,
        }
        self._scenes[asset_id] = scene_info
        logger.info(f"Generated 3D asset '{name}' ({asset_id}) with {scene_info['triangle_count']} triangles.")
        return scene_info

    def generate_html_preview(self, asset_id: str) -> str:
        """Generates a standalone, self-contained Three.js 3D interactive viewport."""
        scene = self._scenes.get(asset_id)
        if not scene:
            raise FileNotFoundError(f"3D asset '{asset_id}' not found.")

        # Standalone HTML5 Three.js preview
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ShivAI 3D Asset Preview - {scene['name']}</title>
  <style>
    body {{ margin: 0; overflow: hidden; background: #0F172A; font-family: Inter, sans-serif; }}
    #hud {{ position: absolute; top: 16px; left: 16px; color: #F8FAFC; background: rgba(15,23,42,0.85);
            padding: 12px 18px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); }}
    #hud h2 {{ margin: 0 0 6px 0; font-size: 16px; }}
    #hud p {{ margin: 2px 0; font-size: 12px; color: #94A3B8; }}
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
  <div id="hud">
    <h2>{scene['name']}</h2>
    <p>Type: {scene['mesh_type'].upper()}</p>
    <p>Triangles: {scene['triangle_count']}</p>
    <p>Vertices: {scene['vertex_count']}</p>
    <p>Drag to rotate | Scroll to zoom</p>
  </div>
  <script>
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);
    const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(2.5, 2.5, 3.5);

    const renderer = new THREE.WebGLRenderer({{ antialias: true }});
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    document.body.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(5, 10, 7.5);
    scene.add(dirLight);

    // Mesh
    let geom;
    const type = "{scene['mesh_type'].lower()}";
    if (type.includes("sphere")) {{
        geom = new THREE.SphereGeometry(1, 32, 24);
    }} else if (type.includes("cylinder")) {{
        geom = new THREE.CylinderGeometry(0.6, 0.6, 2, 32);
    }} else {{
        geom = new THREE.BoxGeometry(1.5, 1.5, 1.5);
    }}

    const mat = new THREE.MeshStandardMaterial({{
        color: "{scene['color']}",
        roughness: {scene['roughness']},
        metalness: {scene['metallic']},
        wireframe: {'true' if scene['wireframe'] else 'false'}
    }});

    const mesh = new THREE.Mesh(geom, mat);
    scene.add(mesh);
    camera.lookAt(0, 0, 0);

    // Auto rotate
    function animate() {{
      requestAnimationFrame(animate);
      mesh.rotation.y += 0.01;
      mesh.rotation.x += 0.005;
      renderer.render(scene, camera);
    }}
    animate();

    window.addEventListener('resize', () => {{
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }});
  </script>
</body>
</html>
"""

    def export_asset_artifacts(self, asset_id: str, job_id: str) -> Dict[str, StoredArtifact]:
        """Saves both .obj and .glb containers into the permanent artifact store."""
        scene = self._scenes.get(asset_id)
        if not scene:
            raise FileNotFoundError(f"3D asset '{asset_id}' not found.")

        obj_art = artifact_manager.store_bytes(
            job_id=job_id,
            name=f"{asset_id}_{scene['name']}.obj",
            data=scene["obj_content"].encode("utf-8"),
            mime_type="text/plain",
            metadata={"format": "wavefront_obj", "triangles": scene["triangle_count"]},
        )

        glb_art = artifact_manager.store_bytes(
            job_id=job_id,
            name=f"{asset_id}_{scene['name']}.glb",
            data=scene["glb_bytes"],
            mime_type="model/gltf-binary",
            metadata={"format": "gltf_binary_v2", "triangles": scene["triangle_count"]},
        )

        html_art = artifact_manager.store_bytes(
            job_id=job_id,
            name=f"{asset_id}_preview.html",
            data=self.generate_html_preview(asset_id).encode("utf-8"),
            mime_type="text/html",
            metadata={"format": "threejs_preview"},
        )

        return {"obj": obj_art, "glb": glb_art, "preview": html_art}


threed_studio = ThreeDAssetStudio()
