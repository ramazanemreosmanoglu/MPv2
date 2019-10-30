import numpy as np
import pygame
import pygame.freetype

import gfx

HUD_VS = """
#version 130

in vec2 position;
in vec2 texUV;

out vec2 vf_texUV;

void main() {
	gl_Position = vec4(2*position.x - 1, -(2*position.y - 1), 0, 1);
	vf_texUV = texUV;
}
"""

HUD_FS = """
#version 130

uniform sampler2D t_hud;

in vec2 vf_texUV;

out vec4 fragColor;

void main() {
	fragColor = texture2D(t_hud, vf_texUV);
}
"""

class Hud:
	def __init__(self, scene, rect):
		self.scene = scene
		self.rect = rect

		self.enabled = True
		surface_size = (2048, 2048)

		self.program = gfx.Program(HUD_VS, HUD_FS)
		self.surface = pygame.Surface(surface_size, flags=pygame.SRCALPHA, depth=32)
		self.hudtex = self.scene.create_texture()

		self.vao = gfx.VAO()
		vert, texc = self._get_shape(self.scene.size, self.rect)
		self.vertices_vbo = gfx.VBO.create_with_data(vert)
		self.texcoords_vbo = gfx.VBO.create_with_data(texc)

		with self.vao:
			self.vao.set_vbo_as_attrib(0, self.vertices_vbo)
			self.vao.set_vbo_as_attrib(1, self.texcoords_vbo)

		with self.program:
			self.program.set_uniform('t_hud', self.hudtex.number)

		self.font = pygame.freetype.Font("font/Roboto-Regular.ttf")
		self.music_font = pygame.freetype.Font("font/NotoMusic-Regular.ttf")
		self.bright_color = pygame.Color(0, 192, 192)
		self.dim_color = pygame.Color(0, 128, 128)
		self.bg_color = pygame.Color(0, 64, 64)
		self.font_color = self.bright_color

		self.elements = [
			Channel(self, self._get_rect(.02, -.048, .2, .022)),
			NoteLength(self, self._get_rect(.28, -.07, .2, .05)),
			DynamicText(self, self._get_rect(.4, -.15, .2, .02), lambda: "%s (%d)" % (self.scene.active_shape.name, self.scene.active_symmetry)),
		]

		def _add_text_with_slider(x, y, line, text, sval_getter):
			self.elements.append(Text  (self, (x*self.rect[2],     y*self.rect[3]+line*22+2, 130, 18), text))
			self.elements.append(Slider(self, (x*self.rect[2]+130, y*self.rect[3]+line*22,   200, 20), sval_getter))

		_add_text_with_slider(.02, .84, 0, "Sphere Count:",  lambda: self.scene.controller.controls['ball_count'].get_fraction())
		_add_text_with_slider(.02, .84, 1, "Sphere Speed:",  lambda: self.scene.controller.controls['ball_speed'].get_fraction())
		_add_text_with_slider(.02, .84, 2, "Sphere Radius:", lambda: self.scene.controller.controls['ball_radius'].get_fraction())

	def _get_rect(self, x, y, w, h):
		if x < 0: x = 1 + x
		if y < 0: y = 1 + y
		return (x * self.rect[2], y * self.rect[3], w * self.rect[2], h * self.rect[3])

	def _get_shape(self, scene_size, rect):
		xmin = rect[0] / scene_size[0]
		ymin = rect[1] / scene_size[1]
		xmax = (rect[0] + rect[2]) / scene_size[0]
		ymax = (rect[1] + rect[3]) / scene_size[1]
		tw = rect[2] / self.surface.get_width()
		th = rect[3] / self.surface.get_height()

		return ([
			[[xmin, ymin], [xmax, ymin], [xmin, ymax]],
			[[xmin, ymax], [xmax, ymin], [xmax, ymax]]
		], [
			[[0,  0], [tw,  0], [ 0, th]],
			[[0, th], [tw,  0], [tw, th]]
		])

	def update(self, dt):
		for e in self.elements:
			e.update(dt)

	def render(self):
		self.surface.fill(pygame.Color(0, 0, 0, 0))
		if not self.enabled: return

		for e in self.elements:
			e.render()

		with self.hudtex:
			arr = np.flip(np.frombuffer(self.surface.get_view().raw, dtype=np.uint8).reshape(self.surface.get_width(), self.surface.get_height(), 4), axis=0)
			self.hudtex.load_array(arr, bgr=True)

		with self.program:
			self.vao.draw_triangles()

class HudElement:
	def __init__(self, hud, rect):
		self.hud = hud
		self.rect = rect

	def update(self, dt):
		pass

	def render(self):
		self.hud.surface.fill(pygame.Color(255, 0, 255), self.rect)

	def draw_rect(self, x, y, w, h, color=None):
		if color is None: color = self.hud.bg_color
		self.hud.surface.fill(color, (self.rect[0] + x, self.rect[1] + y, w, h))

	def draw_text(self, text, x=0, y=0, font=None, color=None, halign='left', valign='top'):
		if font is None: font = self.hud.font
		if color is None: color = self.hud.font_color
		surf, rect = font.render(text, size=self.rect[3], fgcolor=color)
		if halign == 'right':
			posx = self.rect[0] + self.rect[2] - rect[2]
		elif halign == 'center' or halign == 'middle':
			posx = self.rect[0] + (self.rect[2] - rect[2]) / 2
		else:
			posx = self.rect[0]
		if valign == 'bottom':
			posy = self.rect[1] + self.rect[3] - rect[3]
		elif valign == 'center' or valign == 'middle':
			posy = self.rect[1] + (self.rect[3] - rect[3]) / 2
		else:
			posy = self.rect[1]
		self.hud.surface.blit(surf, (posx + x, posy + y))

class Slider(HudElement):
	def __init__(self, hud, rect, value_getter, line_width=2, slider_width=4):
		super().__init__(hud, rect)
		self.x, self.y, self.width, self.height = rect
		self.value_getter = value_getter
		self.line_width = line_width
		self.slider_width = slider_width

		self.slider_pos = None

	def update(self, dt):
		val = self.value_getter()
		if val is None or val < 0. or val > 1.:
			self.slider_pos = None
		else:
			self.slider_pos = val

	def render(self):
		w, h, lw = self.width, self.height, self.line_width
		self.draw_rect(0, 0, w, h, self.hud.dim_color)
		self.draw_rect(lw, lw, w - 2*lw, h - 2*lw, self.hud.bg_color)
		if self.slider_pos is not None:
			sx = lw + (w - 2*lw - self.slider_width) * self.slider_pos
			self.draw_rect(sx, lw, self.slider_width, h - 2*lw, self.hud.bright_color)

class Text(HudElement):
	def __init__(self, hud, rect, text):
		super().__init__(hud, rect)
		self.text = text

	def render(self):
		self.draw_text(self.text)

class DynamicText(Text):
	def __init__(self, hud, rect, text_getter):
		super().__init__(hud, rect, '')
		self.text_getter = text_getter

	def update(self, dt):
		self.text = self.text_getter()

class Channel(HudElement):
	def render(self):
		self.draw_text(self.hud.scene.controller.current_channel['name'])

class NoteLength(HudElement):
	SYMBOLS = ['𝅘𝅥𝅰', '𝅘𝅥𝅯', '𝅘𝅥𝅮', '𝅘𝅥', '𝅗𝅥', '𝅝', '𝅄']

	def update(self, dt):
		self.length_index = self.hud.scene.controller.controls['note_length'].get()

	def render(self):
		xoff = 0
		for i, symbol in enumerate(self.SYMBOLS):
			color = self.hud.bright_color if i == self.length_index else self.hud.bg_color
			self.draw_text(symbol, color=color, font=self.hud.music_font, x=xoff, valign='bottom')
			xoff += self.rect[2] / len(self.SYMBOLS)
