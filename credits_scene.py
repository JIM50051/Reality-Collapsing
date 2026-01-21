import pygame, random, math
import numpy as np
from shared import Scene, draw_center_text, WHITE

class CreditsScene(Scene):
    def __init__(self, game, ending_mode=False):
        super().__init__(game)

        self.ending_mode = ending_mode
        self.credits = [
            "REALITY COLLAPSING",
            "A Game by James Griepentrog",
            "",
            "Programming: James Griepentrog",
            "",
            "Art: James Griepentrog",
            "",
            "Sound Effects: James Griepentrog",
            "",
            "Level Design: James Griepentrog",
            "",
            "Music Credits:",
            "All music in this game is sourced from Pixabay",
            "and is free to use under the CC0 license.",
            "",
            "Special Thanks: You!",
            "",
            "Thank you for playing!",
        ]


        self.scroll_speed = 40
        # Glitch particle system (lightweight)
        self.shards = []
        w, h = self.game.screen.get_size()
        if self.ending_mode:
            # Make credits spawn lower for portal cutscene
            self.scroll_y = h + len(self.credits) * 65
        else:
            self.scroll_y = 800
        self.reset()

        self.game.stop_music()
        self.game.play_music("credits.mp3")

        self.glitch_timer = 0
        self.glitch_interval = 0.18
        self.glitch_level = 1

        # Pre-allocated temporary surfaces (performance!)
        w, h = self.game.screen.get_size()
        self.temp = pygame.Surface((w, h)).convert()
        self.overlay = pygame.Surface((w, h), pygame.SRCALPHA)

    def reset(self):
        w, h = self.game.screen.get_size()
        if self.ending_mode:
            # Make credits spawn lower for portal cutscene
            self.scroll_y = h + len(self.credits) * 65
        else:
            self.scroll_y = 800
        self.done = False
        self.prompt_blink_timer = 0
        self.prompt_visible = True
        self.glitch_level = 1
        self.frame_count = 0
        self.shards.clear()

    # ----------------------------------------------------------------
    # OPTIMIZED GLITCH FUNCTIONS (NO PER-PIXEL OPERATIONS)
    # ----------------------------------------------------------------

    def glitch_static(self, surf, amount=80):
        # Single surface overlay instead of per-pixel set_at
        noise = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        arr = pygame.surfarray.pixels_alpha(noise)
        arr[:, :] = np.random.randint(0, 256, arr.shape, dtype=arr.dtype)
        del arr
        noise.set_alpha(random.randint(30, 70))
        surf.blit(noise, (0,0), special_flags=pygame.BLEND_SUB)

    def glitch_rgb_split(self, surf, amount=4):
        ox = random.randint(-amount, amount)
        oy = random.randint(-amount, amount)

        # Fast channel offset
        shifted = pygame.Surface(surf.get_size()).convert()
        shifted.blit(surf, (ox, oy))
        surf.blit(shifted, (0,0), special_flags=pygame.BLEND_ADD)

    def glitch_slices(self, surf, slices=4, max_shift=30):
        w, h = surf.get_size()
        for _ in range(slices):
            y = random.randint(0, h - 4)
            slice_h = random.randint(4, 20)
            # Clamp slice_h so y+slice_h does not exceed h
            if y + slice_h > h:
                slice_h = h - y
            if slice_h <= 0:
                continue
            shift = random.randint(-max_shift, max_shift)

            slc = surf.subsurface((0, y, w, slice_h)).copy()  # Copy to release lock
            surf.blit(slc, (shift, y))

    def glitch_scanlines(self, surf):
        w, h = surf.get_size()
        scan = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(scan, (0,0,0, random.randint(40,90)), (0,y), (w,y), 1)
        surf.blit(scan, (0,0))

    def glitch_screen_shake(self, surf):
        ox = random.randint(-3, 3)
        oy = random.randint(-3, 3)
        temp = surf.copy()
        surf.blit(temp, (ox, oy))

    def glitch_vhs(self, surf):
        w, h = surf.get_size()
        for _ in range(4):
            y = random.randint(0, h-1)
            bar_height = 2
            if y + bar_height > h:
                bar_height = h - y
            if bar_height <= 0:
                continue
            bar = surf.subsurface((0, y, w, bar_height)).copy()  # Copy to release lock
            sx = random.randint(-20, 20)
            surf.blit(bar, (sx, y))

    def glitch_meltdown(self, surf):
        # Fast shear transform
        offset = math.sin(self.frame_count * 0.2) * 5
        surf.scroll(dx=int(offset), dy=0)

    def glitch_wireframe(self, surf):
        w, h = surf.get_size()
        wire = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 50):
            pygame.draw.line(wire, (80,80,80,100), (0,y), (w,y))
        for x in range(0, w, 50):
            pygame.draw.line(wire, (80,80,80,100), (x,0), (x,h))
        surf.blit(wire, (0,0))

    def glitch_flash(self, surf):
        flash = pygame.Surface(surf.get_size())
        flash.fill((255,255,255))
        flash.set_alpha(random.randint(20, 120))
        surf.blit(flash, (0,0))

    def glitch_vortex(self, surf):
        # Lightweight rotational distortion using transforms
        angle = math.sin(self.frame_count * 0.05) * 3
        scaled = pygame.transform.rotozoom(surf, angle, 1.02)
        rect = scaled.get_rect(center=surf.get_rect().center)
        surf.blit(scaled, rect)

    def glitch_blackhole(self, surf):
        # Fast zoom-in/zoom-out effect
        scale = 1 + (math.sin(self.frame_count * 0.1) * 0.05)
        scaled = pygame.transform.rotozoom(surf, 0, scale)
        rect = scaled.get_rect(center=surf.get_rect().center)
        surf.blit(scaled, rect, special_flags=pygame.BLEND_SUB)

    def glitch_datamosh(self, surf):
        # Lightweight mosh: repeated slice blitting
        w, h = surf.get_size()
        slice_h = 6
        for _ in range(5):
            y = random.randint(0, h-1)
            # Clamp slice_h so y+slice_h does not exceed h
            actual_h = slice_h
            if y + actual_h > h:
                actual_h = h - y
            if actual_h <= 0:
                continue
            slc = surf.subsurface((0, y, w, actual_h)).copy()  # Copy to release lock
            surf.blit(slc, (random.randint(-30, 30), y))

    # ----------------------------------------------------------------
    # PARTICLES (SCREEN SHATTER)
    # ----------------------------------------------------------------
    class Shard:
        def __init__(self, x, y, color):
            self.x, self.y = x, y
            self.dx = random.uniform(-6, 6)
            self.dy = random.uniform(-10, -4)
            self.color = color
            self.gravity = 0.35
            self.size = random.randint(1, 3)

        def update(self):
            self.x += self.dx
            self.y += self.dy
            self.dy += self.gravity

        def draw(self, surf):
            pygame.draw.rect(surf, self.color, (int(self.x),int(self.y),self.size,self.size))

    def spawn_shatter(self, surf, count=120):
        w, h = surf.get_size()
        for _ in range(count):
            x = random.randint(0, w-1)
            y = random.randint(0, h-1)
            self.shards.append(self.Shard(x, y, surf.get_at((x,y))))

    # ----------------------------------------------------------------
    # UPDATE
    # ----------------------------------------------------------------
    def update(self, dt):
        self.frame_count += 1

        # Scroll
        if not self.done:
            self.scroll_y -= self.scroll_speed * dt

            # Use correct denominator for progress
            denom = 600 if not self.ending_mode else (self.game.screen.get_height() + len(self.credits) * 48)
            p = max(0, min(1, 1 - self.scroll_y / denom))
            if p > 0.2: self.glitch_level = 2
            if p > 0.4: self.glitch_level = 3
            if p > 0.6: self.glitch_level = 4
            if p > 0.75: self.glitch_level = 5
            if p > 0.85: self.glitch_level = 6
            if p > 0.92: self.glitch_level = 7

            if self.scroll_y < -len(self.credits)*48:
                self.done = True
                self.glitch_level = 8
                self.spawn_shatter(self.game.screen)
                # Auto-transition to victory screen if this is the ending credits
                if self.ending_mode:
                    import pygame
                    pygame.time.set_timer(pygame.USEREVENT + 99, 100, True)  # 0.1s delay (before prompt)
        else:
            self.prompt_blink_timer += dt
            if self.prompt_blink_timer >= 0.5:
                self.prompt_visible = not self.prompt_visible
                self.prompt_blink_timer = 0

        self.glitch_timer += dt

    # ----------------------------------------------------------------
    # DRAW
    # ----------------------------------------------------------------
    def draw(self, surface):
        w, h = surface.get_size()
        self.temp.fill((0,0,0))

        font = self.game.assets.font(36, True)
        y = int(self.scroll_y)
        for line in self.credits:
            draw_center_text(self.temp, font, line, y, WHITE)
            y += 48


        # Only apply glitches if enabled in settings
        if getattr(self.game.settings, '__getitem__', None) and self.game.settings["glitch_fx"]:
            lvl = self.glitch_level

            if lvl >= 1:
                self.glitch_scanlines(self.temp)
                if random.random() < 0.5: self.glitch_static(self.temp)

            if lvl >= 2:
                self.glitch_slices(self.temp)
                self.glitch_rgb_split(self.temp, 4)

            if lvl >= 3:
                self.glitch_screen_shake(self.temp)

            if lvl >= 4:
                self.glitch_vhs(self.temp)

            if lvl >= 5:
                self.glitch_meltdown(self.temp)
                self.glitch_wireframe(self.temp)

            if lvl >= 6:
                self.glitch_vortex(self.temp)
                self.glitch_datamosh(self.temp)

            if lvl >= 7:
                self.glitch_blackhole(self.temp)
                if random.random() < 0.5:
                    self.glitch_flash(self.temp)

            # FINAL COLLAPSE
            if lvl >= 8:
                self.glitch_vortex(self.temp)
                self.glitch_blackhole(self.temp)
                self.glitch_slices(self.temp, 8, 35)
                self.glitch_rgb_split(self.temp, 12)
                self.glitch_flash(self.temp)

        surface.blit(self.temp, (0,0))

        # Draw shatter particles
        if self.done:
            for shard in self.shards:
                shard.update()
                shard.draw(surface)

        # End prompt
        if self.done and self.prompt_visible:
            pfont = self.game.assets.font(28, True)
            # Render prompt to a temp surface for glitching
            prompt_surf = pygame.Surface((w, 50), pygame.SRCALPHA)
            prompt_surf.fill((0,0,0,0))
            draw_center_text(prompt_surf, pfont, "Press Enter to return to Title Screen", 25, WHITE)
            # Apply glitches if enabled
            if getattr(self.game.settings, '__getitem__', None) and self.game.settings["glitch_fx"]:
                self.glitch_scanlines(prompt_surf)
                if random.random() < 0.5: self.glitch_static(prompt_surf)
                self.glitch_slices(prompt_surf, 2, 12)
                self.glitch_rgb_split(prompt_surf, 3)
                self.glitch_screen_shake(prompt_surf)
            surface.blit(prompt_surf, (0, h - 125))

    def handle_event(self, event):
        if self.done:
            if self.ending_mode:
                # Only auto-advance to victory screen
                if event.type == pygame.USEREVENT + 99:
                    from main import VictoryScene
                    self.game.change_scene(VictoryScene)
            else:
                # Allow skipping title screen credits with any key
                if event.type == pygame.KEYDOWN:
                    from main import TitleScene
                    self.game.change_scene(TitleScene)
        elif not self.done and not self.ending_mode:
            # Allow skipping title screen credits while scrolling
            if event.type == pygame.KEYDOWN:
                self.done = True
                self.glitch_level = 8
                self.spawn_shatter(self.game.screen)
        # Ignore all key events during portal cutscene credits (ending_mode=True)

    def on_exit(self):
        pass
