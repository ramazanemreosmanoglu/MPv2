import math
import numpy as np
import pygame
import pygame.freetype

import gfx
import midi
import mp

HUD_VS = """
#version 130

in vec2 position;
in vec2 texUV;

out vec2 vf_texUV;

void main() {
	gl_Position = vec4(2*position.x - 1, -(2*position.y - 1), 0, 1);
	vf_texUV = vec2(texUV.x, 1 - texUV.y);
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
		self.hudtex.load_array(np.zeros((surface_size[1], surface_size[0], 4), dtype=np.uint8), bgr=True)

		self.vao = gfx.VAO()
		vert, texc = self._get_shape(self.scene.size, self.rect)
		with self.vao:
			self.vao.create_vbo_attrib(0, vert)
			self.vao.create_vbo_attrib(1, texc)

		with self.program:
			self.program.set_uniform('t_hud', self.hudtex.number)

		self.font = pygame.freetype.Font('font/Roboto-Regular.ttf')
		self.music_font = pygame.freetype.Font('font/NotoMusic-Regular.ttf')
		self.symbols_font = pygame.freetype.Font('font/NotoSansSymbols2-Regular.ttf')
		self.bright_color = pygame.Color(0, 192, 192)
		self.dim_color = pygame.Color(0, 128, 128)
		self.bg_color = pygame.Color(0, 64, 64)
		self.font_color = self.bright_color

		self.elements = [
			Channel(self, self._get_rect(.02, -.048, .2, .022)),
			NoteLength(self, self._get_rect(.25, -.07, .2, .05)),
			DynamicText(self, self._get_rect(.4, -.09, .2, .02), lambda: "%s (%d)" % (self.scene.active_shape.name, self.scene.active_symmetry)),
			FaceMapping(self, self._get_rect(.5, -.035, .49, .015)),
		]

		def _add_text_with_slider(x, y, line, text, sval_getter):
			self.elements.append(Text  (self, (x*self.rect[2],     y*self.rect[3]+line*22+2, 130, 18), text))
			self.elements.append(Slider(self, (x*self.rect[2]+130, y*self.rect[3]+line*22,   200, 20), sval_getter))

		_add_text_with_slider(.02, .84, 0, "Sphere Count:",  lambda: self.scene.controller.controls['ball_count'].get_fraction())
		_add_text_with_slider(.02, .84, 1, "Sphere Speed:",  lambda: self.scene.controller.controls['ball_speed'].get_fraction())
		_add_text_with_slider(.02, .84, 2, "Sphere Radius:", lambda: self.scene.controller.controls['ball_radius'].get_fraction())

		self.active_rect = self._find_bounding_int_rect([e.rect for e in self.elements])

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

	def _find_bounding_int_rect(self, rects):
		xmin, ymin, xmax, ymax = None, None, None, None
		for rect in rects:
			xmin = mp.augmin(xmin, rect[0])
			ymin = mp.augmin(ymin, rect[1])
			xmax = mp.augmax(xmax, rect[0]+rect[2])
			ymax = mp.augmax(ymax, rect[1]+rect[3])
		xmin, ymin = math.floor(xmin), math.floor(ymin)
		xmax, ymax = math.ceil(xmax), math.ceil(ymax)
		return (xmin, ymin, xmax-xmin, ymax-ymin)

	def update(self, dt):
		for e in self.elements:
			e.update(dt)

	def render(self):
		self.surface.fill(pygame.Color(0, 0, 0, 0))
		if not self.enabled: return

		for e in self.elements:
			e.render()

		arr = np.frombuffer(self.surface.get_view().raw, dtype=np.uint8).reshape(self.surface.get_height(), self.surface.get_width(), 4)
		self.hudtex.load_subarray(arr, self.active_rect[0], self.active_rect[1], self.active_rect[2], self.active_rect[3], bgr=True)

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
	def __init__(self, hud, rect, text, halign='left', valign='top'):
		super().__init__(hud, rect)
		self.text = text
		self.halign = halign
		self.valign = valign

	def render(self):
		self.draw_text(self.text, halign=self.halign, valign=self.valign)

class DynamicText(Text):
	def __init__(self, hud, rect, text_getter, halign='center', valign='center'):
		super().__init__(hud, rect, '', halign, valign)
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

class FaceMapping(HudElement):
	def __init__(self, hud, rect):
		super().__init__(hud, rect)
		self.max_notes = self.hud.scene.max_symmetries

	def update(self, dt):
		mappings = [self.hud.scene.get_face_mapping(face[0]) for face in reversed(self.hud.scene.face_queue)]
		self.names = ["%s·%s" % (mapping[0], midi.get_note_name(mapping[1]).replace('♯', '#')) if mapping is not None else "·" for mapping in mappings]

	def render(self):
		xoff = 0
		for name in self.names:
			self.draw_text(name, x=xoff, valign='center')
			xoff += self.rect[2] / self.max_notes
