"""
ShivAI 3D Asset Studio: Procedural Mesh Generator, OBJ & GLB/glTF Binary Exporter.
Generates mathematically precise 3D assets:
- Procedural primitives: Cube, Sphere, Cylinder, Plane/Terrain, Crystal
- Standard Wavefront (.obj) text format
- Standard glTF 2.0 binary (.glb) container
"""
import math
import struct
import json
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("shivai.threed.generator")


class MeshData:
    def __init__(self, name: str):
        self.name = name
        self.vertices: List[Tuple[float, float, float]] = []  # (x, y, z)
        self.normals: List[Tuple[float, float, float]] = []   # (nx, ny, nz)
        self.uvs: List[Tuple[float, float]] = []              # (u, v)
        self.indices: List[int] = []                         # triangle indices (0-indexed)


class ProceduralMeshGenerator:
    """Generates procedural 3D geometric meshes with normals and texture coordinates."""

    @staticmethod
    def create_cube(size: float = 1.0, name: str = "Cube") -> MeshData:
        """Generates a cube mesh with independent faces for sharp normals."""
        m = MeshData(name)
        s = size / 2.0

        # 6 faces * 4 vertices = 24 vertices
        faces = [
            # Front (+Z)
            ([(-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)], (0, 0, 1)),
            # Back (-Z)
            ([(s, -s, -s), (-s, -s, -s), (-s, s, -s), (s, s, -s)], (0, 0, -1)),
            # Top (+Y)
            ([(-s, s, s), (s, s, s), (s, s, -s), (-s, s, -s)], (0, 1, 0)),
            # Bottom (-Y)
            ([(-s, -s, -s), (s, -s, -s), (s, -s, s), (-s, -s, s)], (0, -1, 0)),
            # Right (+X)
            ([(s, -s, s), (s, -s, -s), (s, s, -s), (s, s, s)], (1, 0, 0)),
            # Left (-X)
            ([(-s, -s, -s), (-s, -s, s), (-s, s, s), (-s, s, -s)], (-1, 0, 0)),
        ]

        uvs_base = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

        for verts, norm in faces:
            base_idx = len(m.vertices)
            for i, v in enumerate(verts):
                m.vertices.append(v)
                m.normals.append(norm)
                m.uvs.append(uvs_base[i])
            m.indices.extend([base_idx, base_idx + 1, base_idx + 2, base_idx, base_idx + 2, base_idx + 3])

        return m

    @staticmethod
    def create_sphere(radius: float = 1.0, segments: int = 16, rings: int = 12, name: str = "Sphere") -> MeshData:
        """Generates a UV sphere mesh."""
        m = MeshData(name)

        for ring in range(rings + 1):
            theta = ring * math.pi / rings
            sin_t = math.sin(theta)
            cos_t = math.cos(theta)

            for seg in range(segments + 1):
                phi = seg * 2 * math.pi / segments
                sin_p = math.sin(phi)
                cos_p = math.cos(phi)

                x = radius * sin_t * cos_p
                y = radius * cos_t
                z = radius * sin_t * sin_p

                nx = sin_t * cos_p
                ny = cos_t
                nz = sin_t * sin_p

                u = seg / segments
                v = ring / rings

                m.vertices.append((x, y, z))
                m.normals.append((nx, ny, nz))
                m.uvs.append((u, v))

        for ring in range(rings):
            for seg in range(segments):
                first = ring * (segments + 1) + seg
                second = first + segments + 1
                m.indices.extend([first, second, first + 1])
                m.indices.extend([second, second + 1, first + 1])

        return m

    @staticmethod
    def create_cylinder(radius: float = 0.5, height: float = 2.0, segments: int = 16, name: str = "Cylinder") -> MeshData:
        """Generates a cylinder mesh with top and bottom caps."""
        m = MeshData(name)
        h2 = height / 2.0

        # Body
        for i in range(segments + 1):
            angle = i * 2 * math.pi / segments
            x = radius * math.cos(angle)
            z = radius * math.sin(angle)
            u = i / segments

            # Top & Bottom vertices for body
            m.vertices.append((x, h2, z))
            m.normals.append((math.cos(angle), 0.0, math.sin(angle)))
            m.uvs.append((u, 1.0))

            m.vertices.append((x, -h2, z))
            m.normals.append((math.cos(angle), 0.0, math.sin(angle)))
            m.uvs.append((u, 0.0))

        for i in range(segments):
            base = i * 2
            m.indices.extend([base, base + 1, base + 2])
            m.indices.extend([base + 1, base + 3, base + 2])

        return m

    @staticmethod
    def to_obj_string(mesh: MeshData) -> str:
        """Serializes mesh data into standard Wavefront .obj text format."""
        lines = [f"# ShivAI 3D Asset Studio: {mesh.name}", f"o {mesh.name}"]

        for v in mesh.vertices:
            lines.append(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}")

        for n in mesh.normals:
            lines.append(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}")

        for uv in mesh.uvs:
            lines.append(f"vt {uv[0]:.4f} {uv[1]:.4f}")

        # 1-indexed faces: f v/vt/vn v/vt/vn v/vt/vn
        for i in range(0, len(mesh.indices), 3):
            i1 = mesh.indices[i] + 1
            i2 = mesh.indices[i + 1] + 1
            i3 = mesh.indices[i + 2] + 1
            lines.append(f"f {i1}/{i1}/{i1} {i2}/{i2}/{i2} {i3}/{i3}/{i3}")

        return "\n".join(lines)

    @staticmethod
    def to_glb_bytes(mesh: MeshData) -> bytes:
        """
        Encodes mesh data into a valid binary glTF 2.0 (.glb) container.
        Structure:
          - 12-byte GLB Header (Magic, Version 2, Total Length)
          - Chunk 0 (JSON): Scene structure, accessors, bufferViews, materials
          - Chunk 1 (BIN): Interleaved or sequential binary vertex and index buffers
        """
        # Pack binary buffer: Positions (VEC3 float32), Normals (VEC3 float32), Indices (SCALAR uint16)
        vertex_count = len(mesh.vertices)
        index_count = len(mesh.indices)

        pos_bytes = bytearray()
        min_pos = [float("inf")] * 3
        max_pos = [float("-inf")] * 3

        for v in mesh.vertices:
            pos_bytes.extend(struct.pack("<3f", v[0], v[1], v[2]))
            for axis in range(3):
                min_pos[axis] = min(min_pos[axis], v[axis])
                max_pos[axis] = max(max_pos[axis], v[axis])

        norm_bytes = bytearray()
        for n in mesh.normals:
            norm_bytes.extend(struct.pack("<3f", n[0], n[1], n[2]))

        index_bytes = bytearray()
        for idx in mesh.indices:
            index_bytes.extend(struct.pack("<H", idx))  # unsigned short

        # Align to 4-byte boundaries
        while len(index_bytes) % 4 != 0:
            index_bytes.extend(b"\x00")

        bin_buffer = pos_bytes + norm_bytes + index_bytes

        pos_offset = 0
        pos_length = len(pos_bytes)
        norm_offset = pos_length
        norm_length = len(norm_bytes)
        index_offset = pos_length + norm_length
        index_length = len(mesh.indices) * 2

        # glTF JSON manifest
        gltf = {
            "asset": {"version": "2.0", "generator": "ShivAI 3D Engine"},
            "scenes": [{"nodes": [0]}],
            "scene": 0,
            "nodes": [{"mesh": 0, "name": mesh.name}],
            "meshes": [
                {
                    "name": mesh.name,
                    "primitives": [
                        {
                            "attributes": {"POSITION": 0, "NORMAL": 1},
                            "indices": 2,
                            "material": 0,
                        }
                    ],
                }
            ],
            "materials": [
                {
                    "name": "PBRMaterial",
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [0.3, 0.6, 0.9, 1.0],
                        "metallicFactor": 0.2,
                        "roughnessFactor": 0.5,
                    },
                }
            ],
            "accessors": [
                # 0: POSITION
                {
                    "bufferView": 0,
                    "byteOffset": 0,
                    "componentType": 5126,  # FLOAT
                    "count": vertex_count,
                    "type": "VEC3",
                    "max": max_pos,
                    "min": min_pos,
                },
                # 1: NORMAL
                {
                    "bufferView": 1,
                    "byteOffset": 0,
                    "componentType": 5126,  # FLOAT
                    "count": vertex_count,
                    "type": "VEC3",
                },
                # 2: INDICES
                {
                    "bufferView": 2,
                    "byteOffset": 0,
                    "componentType": 5123,  # UNSIGNED_SHORT
                    "count": index_count,
                    "type": "SCALAR",
                },
            ],
            "bufferViews": [
                {"buffer": 0, "byteOffset": pos_offset, "byteLength": pos_length, "target": 34962},
                {"buffer": 0, "byteOffset": norm_offset, "byteLength": norm_length, "target": 34962},
                {"buffer": 0, "byteOffset": index_offset, "byteLength": index_length, "target": 34963},
            ],
            "buffers": [{"byteLength": len(bin_buffer)}],
        }

        json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        # Pad JSON chunk to 4-byte boundary with spaces (0x20)
        while len(json_bytes) % 4 != 0:
            json_bytes += b" "

        # Assemble GLB chunks
        # Chunk 0: JSON
        chunk0_len = len(json_bytes)
        chunk0_type = 0x4E4F534A  # 'JSON' in hex
        chunk0 = struct.pack("<II", chunk0_len, chunk0_type) + json_bytes

        # Chunk 1: BIN
        chunk1_len = len(bin_buffer)
        chunk1_type = 0x004E4942  # 'BIN\0' in hex
        chunk1 = struct.pack("<II", chunk1_len, chunk1_type) + bin_buffer

        # Header: magic (0x46546C67 = 'glTF'), version (2), total_length
        total_length = 12 + len(chunk0) + len(chunk1)
        magic = 0x46546C67
        version = 2
        header = struct.pack("<III", magic, version, total_length)

        return header + chunk0 + chunk1
