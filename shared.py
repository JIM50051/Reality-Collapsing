import pygame
from typing import Any, Callable, Optional, Tuple

# Color constants
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
HOT_PINK = (255, 80, 80)

class Scene:
	def __init__(self, game: Any):
		self.game = game
	def on_enter(self):
		pass
	def on_exit(self):
		pass
	def handle_event(self, event):
		pass
	def update(self, dt: float):
		pass
	def draw(self, surface):
		pass

class InputState:
	def __init__(self):
		self.menu_up = False
		self.menu_down = False
		self.accept = False
		self.back = False
		self.pause = False
		self.shoot = False
		self.move_left = False
		self.move_right = False
		self.up = False
		self.down = False
		self.jump = False
		self.move_axis = 0.0
		self.vertical_axis = 0.0

class VerticalMenu:
	def __init__(self, *args, **kwargs):
		self.entries = args[0] if args and isinstance(args[0], list) else []
		self.selected = 0
		self.anim_progress = 0.0  # For highlight animation
		self.sound = kwargs.get('sound', None)

	def handle_event(self, event):
		# Allow navigation with WASD and arrow keys, and ESC to resume in pause menu
		if event.type == pygame.KEYDOWN:
			if event.key in (pygame.K_w, pygame.K_UP):
				self.selected = (self.selected - 1) % len(self.entries)
				if self.sound:
					self.sound.play_event("menu_move")
				return None
			elif event.key in (pygame.K_s, pygame.K_DOWN):
				self.selected = (self.selected + 1) % len(self.entries)
				if self.sound:
					self.sound.play_event("menu_move")
				return None
			elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
				entry = self.entries[self.selected]
				if getattr(entry, 'enabled', True):
					if self.sound:
						self.sound.play_event("menu_confirm")
					return entry.action()
				return None
			elif event.key == pygame.K_ESCAPE:
				# If ESC is pressed, try to resume if a Resume entry exists, else trigger selected
				for entry in self.entries:
					if callable(entry.label) and entry.label().lower() in ("resume", "continue"):
						if getattr(entry, 'enabled', True):
							if self.sound:
								self.sound.play_event("menu_confirm")
							return entry.action()
				# Otherwise, trigger selected entry
				entry = self.entries[self.selected]
				if getattr(entry, 'enabled', True):
					if self.sound:
						self.sound.play_event("menu_confirm")
					return entry.action()
				return None
		# (Mouse click handling for menu entries removed; keyboard navigation only)
		return None
	def draw(self, surface, assets=None, y=None, glitch_fx=False, return_rects=False):
		# Responsive, glitch-themed menu UI that always fits on screen
		import random
		if not hasattr(self, 'entries') or not self.entries:
			return
		# Calculate max font size and spacing to fit all entries
		max_height = surface.get_height() * 0.45  # Allow for logo and padding
		min_font = 18
		max_font = 36
		entry_count = len(self.entries)
		# Try largest font that fits
		for font_size in range(max_font, min_font-1, -1):
			spacing = int(font_size * 1.6)
			total_height = entry_count * spacing
			if total_height <= max_height:
				break
		else:
			font_size = min_font
			spacing = int(font_size * 1.6)
		font = assets.font(font_size, True) if assets and hasattr(assets, 'font') else pygame.font.SysFont("consolas", font_size, bold=True)
		menu_width = int(surface.get_width() * 0.34)
		menu_x = (surface.get_width() - menu_width) // 2
		# Center menu below logo, but keep on screen
		logo_bottom = int(surface.get_height() * 0.23) + 100  # Assume logo is at 23% and ~200px tall
		menu_y = y if y is not None else max(logo_bottom + 12, (surface.get_height() - (entry_count * spacing)) // 2)
		selected = getattr(self, 'selected', 0)
		# Draw menu background panel
		panel_rect = pygame.Rect(menu_x-24, menu_y-24, menu_width+48, spacing*entry_count+24)
		pygame.draw.rect(surface, (28, 28, 48, 220), panel_rect, border_radius=24)
		highlight_color1 = (90, 120, 255)
		highlight_color2 = (180, 80, 255)
		entry_rects = []
		for i, entry in enumerate(self.entries):
			text = entry.label() if callable(entry.label) else str(entry.label)
			enabled = getattr(entry, 'enabled', True)
			color = (255,255,255) if enabled else (128,128,128)
			rect_y = menu_y + i * spacing
			# Calculate rect for this entry (for mouse hit-testing)
			entry_rect = pygame.Rect(menu_x, rect_y - spacing//2 + 4, menu_width, spacing-8)
			entry_rects.append(entry_rect)
			# Glitch effect: random offset and color flicker for selected entry
			if i == selected:
				bg_rect = pygame.Rect(menu_x, rect_y - spacing//2 + 4, menu_width, spacing-8)
				highlight = pygame.Surface((menu_width, spacing-8), pygame.SRCALPHA)
				for y2 in range(spacing-8):
					ratio = y2 / float(spacing-9)
					color_blend = (
						int(highlight_color1[0] * (1-ratio) + highlight_color2[0] * ratio),
						int(highlight_color1[1] * (1-ratio) + highlight_color2[1] * ratio),
						int(highlight_color1[2] * (1-ratio) + highlight_color2[2] * ratio),
						180
					)
					highlight.fill(color_blend, rect=pygame.Rect(0, y2, menu_width, 1))
				highlight_shadow = pygame.Surface((menu_width+8, spacing), pygame.SRCALPHA)
				pygame.draw.ellipse(highlight_shadow, (0,0,0,80), highlight_shadow.get_rect())
				highlight_shadow_rect = highlight_shadow.get_rect(center=(surface.get_width()//2, rect_y+3))
				surface.blit(highlight_shadow, highlight_shadow_rect)
				surface.blit(highlight, (menu_x, rect_y-spacing//2+8))
			# Draw text with glitch effect if enabled
			if glitch_fx and i == selected:
				for _ in range(3):
					offset_x = random.randint(-3,3)
					offset_y = random.randint(-2,2)
					flicker_color = (
						min(255, color[0]+random.randint(-40,40)),
						min(255, color[1]+random.randint(-40,40)),
						min(255, color[2]+random.randint(-40,40))
					)
					shadow = font.render(text, True, (0,0,0))
					shadow_rect = shadow.get_rect(center=(surface.get_width() // 2 + offset_x, rect_y+3+offset_y))
					surface.blit(shadow, shadow_rect)
					rendered = font.render(text, True, flicker_color)
					rect = rendered.get_rect(center=(surface.get_width() // 2 + offset_x, rect_y+offset_y))
					surface.blit(rendered, rect)
			# Main text (with drop shadow)
			shadow = font.render(text, True, (0,0,0))
			shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, rect_y+3))
			surface.blit(shadow, shadow_rect)
			rendered = font.render(text, True, color)
			rect = rendered.get_rect(center=(surface.get_width() // 2, rect_y))
			surface.blit(rendered, rect)
			# Subtle underline for selected
			if i == selected:
				pygame.draw.line(surface, (255,255,255,80), (menu_x+24, rect_y+font_size//2), (menu_x+menu_width-24, rect_y+font_size//2), 2)
			# For non-selected, draw text with lighter shadow
			if i != selected and glitch_fx:
				for _ in range(2):
					offset_x = random.randint(-2,2)
					offset_y = random.randint(-1,1)
					shadow = font.render(text, True, (40,40,60))
					shadow_rect = shadow.get_rect(center=(surface.get_width() // 2 + offset_x, rect_y+2+offset_y))
					surface.blit(shadow, shadow_rect)
					rendered = font.render(text, True, color)
					rect = rendered.get_rect(center=(surface.get_width() // 2 + offset_x, rect_y+offset_y))
					surface.blit(rendered, rect)
			elif i != selected:
				shadow = font.render(text, True, (40,40,60))
				shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, rect_y+2))
				surface.blit(shadow, shadow_rect)
				rendered = font.render(text, True, color)
				rect = rendered.get_rect(center=(surface.get_width() // 2, rect_y))
				surface.blit(rendered, rect)
		# Store the last drawn entry rects for click alignment
		self._last_entry_rects = entry_rects
		if return_rects:
			return entry_rects
		selected = getattr(self, 'selected', 0)
		# Animate highlight position for smooth movement
		if not hasattr(self, '_last_selected'):
			self._last_selected = selected
		if self._last_selected != selected:
			self.anim_progress = 0.0
		self._last_selected = selected
		# Draw menu background panel
		panel_rect = pygame.Rect(menu_x-32, menu_y-60, menu_width+64, spacing*len(self.entries)+60)
		pygame.draw.rect(surface, (24, 24, 48, 220), panel_rect, border_radius=32)
		# Draw each entry
		highlight_color1 = (90, 120, 255)
		highlight_color2 = (180, 80, 255)
		for i, entry in enumerate(self.entries):
			text = entry.label() if callable(entry.label) else str(entry.label)
			enabled = getattr(entry, 'enabled', True)
			color = (255,255,255) if enabled else (128,128,128)
			rect_y = menu_y + i * spacing
			# Animated highlight for selected entry
			if i == selected:
				bg_rect = pygame.Rect(menu_x, rect_y - 36, menu_width, 64)
				# Gradient highlight
				highlight = pygame.Surface((menu_width, 64), pygame.SRCALPHA)
				for y2 in range(64):
					ratio = y2 / 63.0
					color_blend = (
						int(highlight_color1[0] * (1-ratio) + highlight_color2[0] * ratio),
						int(highlight_color1[1] * (1-ratio) + highlight_color2[1] * ratio),
						int(highlight_color1[2] * (1-ratio) + highlight_color2[2] * ratio),
						180
					)
					highlight.fill(color_blend, rect=pygame.Rect(0, y2, menu_width, 1))
				highlight_shadow = pygame.Surface((menu_width+8, 72), pygame.SRCALPHA)
				pygame.draw.ellipse(highlight_shadow, (0,0,0,80), highlight_shadow.get_rect())
				highlight_shadow_rect = highlight_shadow.get_rect(center=(surface.get_width()//2, rect_y+4))
				surface.blit(highlight_shadow, highlight_shadow_rect)
				surface.blit(highlight, (menu_x, rect_y-32))
			# Draw text with drop shadow
			shadow = font.render(text, True, (0,0,0))
			shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, rect_y+4))
			surface.blit(shadow, shadow_rect)
			rendered = font.render(text, True, color)
			rect = rendered.get_rect(center=(surface.get_width() // 2, rect_y))
			surface.blit(rendered, rect)
			# Draw a subtle underline for selected
			if i == selected:
				pygame.draw.line(surface, (255,255,255,80), (menu_x+40, rect_y+32), (menu_x+menu_width-40, rect_y+32), 3)
			# For non-selected, draw text with lighter shadow
			if i != selected:
				shadow = font.render(text, True, (40,40,60))
				shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, rect_y+3))
				surface.blit(shadow, shadow_rect)
				rendered = font.render(text, True, color)
				rect = rendered.get_rect(center=(surface.get_width() // 2, rect_y))
				surface.blit(rendered, rect)

class MenuEntry:
	def __init__(self, label: Callable[[], str], action: Callable[[], Any], enabled: Any = True):
		self.label = label
		self.action = action
		self.enabled = enabled

	def activate(self):
		if callable(self.action) and (not hasattr(self, 'enabled') or self.enabled):
			return self.action()
		return None

def draw_center_text(surface, font, text, y, color, *args, **kwargs):
	# Modern: draw text centered with drop shadow for readability
	if not hasattr(font, 'render'):
		return
	shadow = font.render(text, True, (0,0,0))
	shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, y+3))
	surface.blit(shadow, shadow_rect)
	rendered = font.render(text, True, color)
	rect = rendered.get_rect(center=(surface.get_width() // 2, y))
	surface.blit(rendered, rect)

def draw_glitch_text(surface, font, text, y, color, glitch_fx=False, *args, **kwargs):
	# Modern: draw text with drop shadow, and fake glitch effect if enabled
	if glitch_fx:
		import random
		for _ in range(3):
			offset = random.randint(-3,3)
			r = int(max(0, min(255, color[0])))
			g = int(max(0, min(255, color[1]+random.randint(-40,40))))
			b = int(max(0, min(255, color[2]+random.randint(-40,40))))
			glitch_color = (r, g, b)
			shadow = font.render(text, True, (0,0,0))
			shadow_rect = shadow.get_rect(center=(surface.get_width() // 2 + offset, y+3+offset))
			surface.blit(shadow, shadow_rect)
			rendered = font.render(text, True, glitch_color)
			rect = rendered.get_rect(center=(surface.get_width() // 2 + offset, y+offset))
			surface.blit(rendered, rect)
	# Main text
	shadow = font.render(text, True, (0,0,0))
	shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, y+3))
	surface.blit(shadow, shadow_rect)
	rendered = font.render(text, True, color)
	rect = rendered.get_rect(center=(surface.get_width() // 2, y))
	surface.blit(rendered, rect)
