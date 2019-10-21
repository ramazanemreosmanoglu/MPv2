import numpy as np

import gfx
import mp
import objreader

SHAPE_VS = """
#version 130

uniform mat4 u_view;
uniform mat4 u_projection;

in vec3 position;
in vec3 bary;
in vec2 texUV;
in vec3 normal;
in vec3 wires;

out vec3 vf_position;
out vec3 vf_bary;
out vec2 vf_texUV;
out vec3 vf_normal;
out vec3 vf_wires;

void main() {
	gl_Position = u_projection * u_view * vec4(position, 1);
	vf_position = position;
	vf_bary = bary;
	vf_texUV = texUV;
	vf_normal = normal;
	vf_wires = wires;
}
"""

SHAPE_FS = """
#version 130

#define MAX_BALLS 16

uniform vec4 u_balls[MAX_BALLS];
uniform float u_faceHighlight;

in vec3 vf_position;
in vec3 vf_bary;
in vec2 vf_texUV;
in vec3 vf_normal;
in vec3 vf_wires;

out vec4 fragColor;

float ball_highlight_factor() {
	float maxHighlight = -1. / 0.;

	for (int i = 0; i < MAX_BALLS; i++) {
		float radius = u_balls[i].w;
		if (radius == 0.0) continue;

		float dist = distance(vf_position, u_balls[i].xyz);
		float light_radius = radius * 4;

		// f(lr)=0, f(0)=1
		float hf = (-1 / light_radius) * (dist - light_radius);
		hf = pow(clamp(hf, 0, 1), 2);

		maxHighlight = max(maxHighlight, hf);
	}

	return clamp(maxHighlight, 0, 1);
}

void main() {
	vec3 wire_bary = (1 - vf_wires) + vf_bary;
	float edge_distance = min(wire_bary.x, min(wire_bary.y, wire_bary.z));
	float edge_distance_delta = fwidth(edge_distance);
	float edge = 1 - smoothstep(edge_distance_delta * .5, edge_distance_delta * 2, edge_distance);

	vec4 ball_highlight = vec4(1, 1, 1, ball_highlight_factor());

	float faceAlpha = mix(.1, .8, u_faceHighlight);

	vec4 faceColor = vec4(mix(vec3(0, 1, 0), ball_highlight.rgb, ball_highlight.a), max(faceAlpha, ball_highlight.a));
	vec4 wireColor = vec4(0, 1, 0, .8);
	fragColor = mix(faceColor, wireColor, edge);
}
"""

class Shape:
	def __init__(self, scene, radius):
		self.scene = scene
		self.radius = radius

		self.faces = []
		self.program = gfx.Program(SHAPE_VS, SHAPE_FS)

	def load_file(self, filename):
		with open(filename, 'r') as f:
			vertices, texcoords, normals = objreader.read_obj_np(f)

		bsrad = np.amax(np.linalg.norm(vertices, axis=2))

		for i, vf in enumerate(vertices):
			tf, nf = texcoords[i], normals[i]
			face = Face(self, i, vf / bsrad * self.radius, tf, nf)
			self.faces.append(face)

	def update(self, dt):
		with self.program:
			balls = [[b.pos[0], b.pos[1], b.pos[2], b.radius if b.enabled else 0.] for b in self.scene.balls.balls]
			self.program.set_uniform('u_balls', balls)
			self.program.set_uniform('u_view', self.scene.view)
			self.program.set_uniform('u_projection', self.scene.projection)

		for f in self.faces:
			f.update(dt)

class Face:
	def __init__(self, shape, index, vertices, texcoords, normals):
		self.shape = shape
		self.index = index
		self.triangles = []
		self.midpoint = sum(vertices) / len(vertices)
		self.normal = mp.triangle_normal(vertices[0:3])

		for i in range(1, len(vertices)-1):
			i0, i1, i2 = 0, i, i+1
			triangle = Triangle(self, vertices[[i0, i1, i2]], texcoords[[i0, i1, i2]], normals[[i0, i1, i2]], [True, i2==len(vertices)-1, i==1])
			self.triangles.append(triangle)

	def update(self, dt):
		pass

	def render(self):
		with self.shape.program:
			self.shape.program.set_uniform('u_faceHighlight', 0.)
			for t in self.triangles:
				t.render()

class Triangle:
	def __init__(self, face, vertices, texcoords=None, normals=None, wires=None):
		if texcoords is None: texcoords = [[0, 0], [0, 1], [1, 0]]
		if normals is None: normals = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
		if wires is None: wires = [True, True, True]

		self.face = face
		self.vertices = vertices
		self.texcoords = texcoords
		self.normals = normals
		self.wires = wires
		self.normal = mp.triangle_normal(self.vertices)

		self.vao = gfx.VAO()
		self.vertices_vbo = gfx.VBO.create_with_data(self.vertices)
		self.bary_vbo = gfx.VBO.create_with_data([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
		self.tex_vbo = gfx.VBO.create_with_data(self.texcoords)
		self.normals_vbo = gfx.VBO.create_with_data(self.normals)
		self.wires_vbo = gfx.VBO.create_with_data([self.wires, self.wires, self.wires])

		with self.vao:
			self.vao.set_vbo_as_attrib(0, self.vertices_vbo)
			self.vao.set_vbo_as_attrib(1, self.bary_vbo)
			self.vao.set_vbo_as_attrib(2, self.tex_vbo)
			self.vao.set_vbo_as_attrib(3, self.normals_vbo)
			self.vao.set_vbo_as_attrib(4, self.wires_vbo)

	def render(self):
		self.vao.draw_triangles()
