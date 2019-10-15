import pygame

import mb2gfx
import midi

SIZE = (int(1920*.8), int(1080*.8))

def main():
	pygame.init()
	pygame.display.set_caption("MusicBalls v2")
	pygame.display.set_mode(SIZE, pygame.DOUBLEBUF | pygame.OPENGL)
	scene = mb2gfx.Scene(SIZE)
	midi_handler = midi.MidiHandler(scene, 'Launchkey MK2 49 MIDI 1', 'FLUID Synth')

	clock = pygame.time.Clock()

	running = True
	while running:
		for ev in pygame.event.get():
			if ev.type == pygame.QUIT:
				running = False

			elif ev.type == pygame.KEYUP and ev.key == pygame.K_ESCAPE:
				running = False

			elif ev.type == pygame.KEYDOWN:
				scene.key_down(pygame.key.name(ev.key))

			elif ev.type == pygame.KEYUP:
				scene.key_up(pygame.key.name(ev.key))

		scene.update()
		scene.render()
		pygame.display.flip()
		pygame.display.set_caption("MusicBalls v2 - %.2f FPS" % (clock.get_fps(),))
		clock.tick(0)

if __name__ == '__main__':
	main()
