import os
import sys

import numpy as np
import math
import random
import time
import json
import colorsys
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

import pygame

# Optional PIL/Pillow support for GIF loading; gracefully degrade if not available
try:
    from PIL import Image, ImageSequence
except Exception:
    Image = None
    ImageSequence = None

    

# === Config / paths / constants ===
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 800
SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
FPS = 60
TITLE = "Reality Collapsing"
FONT_NAME = "Consolas"
PLAYER_WIDTH = 36
PLAYER_HEIGHT = 48

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "assets"
BACKGROUND_DIR = ASSET_DIR / "backgrounds"
OBJECT_DIR = ASSET_DIR / "objects"
PLATFORM_DIR = ASSET_DIR / "platforms"
HAT_DIR = ASSET_DIR / "hats"
TRAIL_DIR = ASSET_DIR / "trails"
INPUT_ICON_DIR = ASSET_DIR / "input buttons"
KB_ICON_DIR = INPUT_ICON_DIR / "Keyboard_Mouse" / "Retro"
MOUSE_ICON_DIR = KB_ICON_DIR
XGAMEPAD_ICON_DIR = INPUT_ICON_DIR / "XGamepad" / "Default"
SOUND_DIR = ASSET_DIR / "sounds"
MUSIC_DIR = ASSET_DIR / "music"
SAVE_FILE = BASE_DIR / "save_data.txt"
SETTINGS_FILE = BASE_DIR / "settings.json"

def load_object_image(filename: str) -> pygame.Surface:
    path = OBJECT_DIR / filename
    return pygame.image.load(str(path)).convert_alpha()

WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
HOT_PINK = (255, 80, 80)


# === Core scene/input/menu types ===
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
        self.shield = False
        self.dash = False
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
        self.sound = kwargs.get("sound", None)

    def handle_event(self, event):
        # Keyboard navigation; ESC tries to resume if a resume/continue entry exists
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_w, pygame.K_UP):
                self.selected = (self.selected - 1) % len(self.entries)
                if self.sound:
                    self.sound.play_event("menu_move")
                return None
            if event.key in (pygame.K_s, pygame.K_DOWN):
                self.selected = (self.selected + 1) % len(self.entries)
                if self.sound:
                    self.sound.play_event("menu_move")
                return None
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                entry = self.entries[self.selected]
                if getattr(entry, "enabled", True):
                    if self.sound:
                        self.sound.play_event("menu_confirm")
                    return entry.action()
                return None
            if event.key == pygame.K_ESCAPE:
                for entry in self.entries:
                    if callable(entry.label) and entry.label().lower() in ("resume", "continue"):
                        if getattr(entry, "enabled", True):
                            if self.sound:
                                self.sound.play_event("menu_confirm")
                            return entry.action()
                entry = self.entries[self.selected]
                if getattr(entry, "enabled", True):
                    if self.sound:
                        self.sound.play_event("menu_confirm")
                    return entry.action()
                return None
        # Mouse hover: update selected index to the item under the cursor
        if event.type == pygame.MOUSEMOTION and hasattr(self, "_last_entry_rects"):
            for idx, rect in enumerate(self._last_entry_rects):
                if rect.collidepoint(event.pos):
                    if idx != self.selected:
                        self.selected = idx
                        if self.sound:
                            self.sound.play_event("menu_move")
                    break
        # Mouse click support
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and hasattr(self, "_last_entry_rects"):
            for idx, rect in enumerate(self._last_entry_rects):
                if rect.collidepoint(event.pos):
                    entry = self.entries[idx]
                    if getattr(entry, "enabled", True):
                        self.selected = idx
                        if self.sound:
                            self.sound.play_event("menu_confirm")
                        return entry.action()
                    break
        return None

    def draw(self, surface, assets=None, y=None, glitch_fx=False, return_rects=False):
        import random

        if not hasattr(self, "entries") or not self.entries:
            return

        max_height = surface.get_height() * 0.45
        min_font = 18
        max_font = 36
        entry_count = len(self.entries)
        for font_size in range(max_font, min_font - 1, -1):
            spacing = int(font_size * 1.6)
            total_height = entry_count * spacing
            if total_height <= max_height:
                break
        else:
            font_size = min_font
            spacing = int(font_size * 1.6)
        font = assets.font(font_size, True) if assets and hasattr(assets, "font") else pygame.font.SysFont(
            "consolas", font_size, bold=True
        )
        menu_width = int(surface.get_width() * 0.34)
        menu_x = (surface.get_width() - menu_width) // 2
        logo_bottom = int(surface.get_height() * 0.23) + 100
        menu_y = y if y is not None else max(logo_bottom + 12, (surface.get_height() - (entry_count * spacing)) // 2)
        selected = getattr(self, "selected", 0)
        panel_rect = pygame.Rect(menu_x - 24, menu_y - 24, menu_width + 48, spacing * entry_count + 24)
        panel_color = getattr(self, "panel_color", (28, 28, 48, 220))
        panel_border_color = getattr(self, "panel_border_color", None)
        pygame.draw.rect(surface, panel_color, panel_rect, border_radius=24)
        if panel_border_color is not None:
            pygame.draw.rect(surface, panel_border_color, panel_rect, 2, border_radius=24)
        highlight_color1 = (90, 120, 255)
        highlight_color2 = (180, 80, 255)
        entry_rects = []
        for i, entry in enumerate(self.entries):
            text = entry.label() if callable(entry.label) else str(entry.label)
            enabled = getattr(entry, "enabled", True)
            color = (255, 255, 255) if enabled else (128, 128, 128)
            rect_y = menu_y + i * spacing
            entry_rect = pygame.Rect(menu_x, rect_y - spacing // 2 + 8, menu_width, spacing - 16)
            entry_rects.append(entry_rect)
            if i == selected:
                highlight_height = max(10, spacing - 16)
                highlight = pygame.Surface((menu_width, highlight_height), pygame.SRCALPHA)
                for y2 in range(highlight_height):
                    ratio = y2 / float(highlight_height - 1)
                    color_blend = (
                        int(highlight_color1[0] * (1 - ratio) + highlight_color2[0] * ratio),
                        int(highlight_color1[1] * (1 - ratio) + highlight_color2[1] * ratio),
                        int(highlight_color1[2] * (1 - ratio) + highlight_color2[2] * ratio),
                        180,
                    )
                    highlight.fill(color_blend, rect=pygame.Rect(0, y2, menu_width, 1))
                highlight_shadow = pygame.Surface((menu_width + 8, highlight_height + 6), pygame.SRCALPHA)
                pygame.draw.ellipse(highlight_shadow, (0, 0, 0, 60), highlight_shadow.get_rect())
                highlight_shadow_rect = highlight_shadow.get_rect(center=(surface.get_width() // 2, rect_y + 3))
                surface.blit(highlight_shadow, highlight_shadow_rect)
                surface.blit(highlight, (menu_x, rect_y - highlight_height // 2 + 4))
            if glitch_fx and i == selected:
                for _ in range(3):
                    offset_x = random.randint(-3, 3)
                    offset_y = random.randint(-2, 2)
                    flicker_color = (
                        min(255, color[0] + random.randint(-40, 40)),
                        min(255, color[1] + random.randint(-40, 40)),
                        min(255, color[2] + random.randint(-40, 40)),
                    )
                    shadow = font.render(text, True, (0, 0, 0))
                    shadow_rect = shadow.get_rect(center=(surface.get_width() // 2 + offset_x, rect_y + 3 + offset_y))
                    surface.blit(shadow, shadow_rect)
                    rendered = font.render(text, True, flicker_color)
                    rect = rendered.get_rect(center=(surface.get_width() // 2 + offset_x, rect_y + offset_y))
                    surface.blit(rendered, rect)
            shadow = font.render(text, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, rect_y + 3))
            surface.blit(shadow, shadow_rect)
            rendered = font.render(text, True, color)
            rect = rendered.get_rect(center=(surface.get_width() // 2, rect_y))
            surface.blit(rendered, rect)
            if i == selected:
                pygame.draw.line(
                    surface, (255, 255, 255, 80), (menu_x + 24, rect_y + font_size // 2), (menu_x + menu_width - 24, rect_y + font_size // 2), 2
                )
            if i != selected and glitch_fx:
                for _ in range(2):
                    offset_x = random.randint(-2, 2)
                    offset_y = random.randint(-1, 1)
                    shadow = font.render(text, True, (40, 40, 60))
                    shadow_rect = shadow.get_rect(center=(surface.get_width() // 2 + offset_x, rect_y + 2 + offset_y))
                    surface.blit(shadow, shadow_rect)
                    rendered = font.render(text, True, color)
                    rect = rendered.get_rect(center=(surface.get_width() // 2 + offset_x, rect_y + offset_y))
                    surface.blit(rendered, rect)
            elif i != selected:
                shadow = font.render(text, True, (40, 40, 60))
                shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, rect_y + 2))
                surface.blit(shadow, shadow_rect)
                rendered = font.render(text, True, color)
                rect = rendered.get_rect(center=(surface.get_width() // 2, rect_y))
                surface.blit(rendered, rect)
        self._last_entry_rects = entry_rects
        if return_rects:
            return entry_rects
        selected = getattr(self, "selected", 0)
        if not hasattr(self, "_last_selected"):
            self._last_selected = selected
        if self._last_selected != selected:
            self.anim_progress = 0.0
        self._last_selected = selected

    # Second pass drawing (legacy layout kept for compatibility)
        panel_rect = pygame.Rect(menu_x - 32, menu_y - 60, menu_width + 64, spacing * len(self.entries) + 60)
        pygame.draw.rect(surface, (24, 24, 48, 220), panel_rect, border_radius=32)
        highlight_color1 = (90, 120, 255)
        highlight_color2 = (180, 80, 255)
        for i, entry in enumerate(self.entries):
            text = entry.label() if callable(entry.label) else str(entry.label)
            enabled = getattr(entry, "enabled", True)
            color = (255, 255, 255) if enabled else (128, 128, 128)
            rect_y = menu_y + i * spacing
            if i == selected:
                highlight = pygame.Surface((menu_width, 64), pygame.SRCALPHA)
                for y2 in range(64):
                    ratio = y2 / 63.0
                    color_blend = (
                        int(highlight_color1[0] * (1 - ratio) + highlight_color2[0] * ratio),
                        int(highlight_color1[1] * (1 - ratio) + highlight_color2[1] * ratio),
                        int(highlight_color1[2] * (1 - ratio) + highlight_color2[2] * ratio),
                        180,
                    )
                    highlight.fill(color_blend, rect=pygame.Rect(0, y2, menu_width, 1))
                highlight_shadow = pygame.Surface((menu_width + 8, 72), pygame.SRCALPHA)
                pygame.draw.ellipse(highlight_shadow, (0, 0, 0, 80), highlight_shadow.get_rect())
                highlight_shadow_rect = highlight_shadow.get_rect(center=(surface.get_width() // 2, rect_y + 4))
                surface.blit(highlight_shadow, highlight_shadow_rect)
                surface.blit(highlight, (menu_x, rect_y - 32))
            shadow = font.render(text, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, rect_y + 4))
            surface.blit(shadow, shadow_rect)
            rendered = font.render(text, True, color)
            rect = rendered.get_rect(center=(surface.get_width() // 2, rect_y))
            surface.blit(rendered, rect)
            if i == selected:
                pygame.draw.line(surface, (255, 255, 255, 80), (menu_x + 40, rect_y + 32), (menu_x + menu_width - 40, rect_y + 32), 3)
            if i != selected:
                shadow = font.render(text, True, (40, 40, 60))
                shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, rect_y + 3))
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
        if callable(self.action) and (not hasattr(self, "enabled") or self.enabled):
            return self.action()
        return None


def draw_center_text(surface, font, text, y, color, *args, **kwargs):
    shadow = font.render(text, True, (0, 0, 0))
    shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, y + 3))
    surface.blit(shadow, shadow_rect)
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=(surface.get_width() // 2, y))
    surface.blit(rendered, rect)


def draw_glitch_text(surface, font, text, y, color, glitch_fx=False, *args, **kwargs):
    if glitch_fx:
        import random

        for _ in range(3):
            offset = random.randint(-3, 3)
            r = int(max(0, min(255, color[0])))
            g = int(max(0, min(255, color[1] + random.randint(-40, 40))))
            b = int(max(0, min(255, color[2] + random.randint(-40, 40))))
            glitch_color = (r, g, b)
            shadow = font.render(text, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(surface.get_width() // 2 + offset, y + 3 + offset))
            surface.blit(shadow, shadow_rect)
            rendered = font.render(text, True, glitch_color)
            rect = rendered.get_rect(center=(surface.get_width() // 2 + offset, y + offset))
            surface.blit(rendered, rect)
    shadow = font.render(text, True, (0, 0, 0))
    shadow_rect = shadow.get_rect(center=(surface.get_width() // 2, y + 3))
    surface.blit(shadow, shadow_rect)
    rendered = font.render(text, True, color)
    rect = rendered.get_rect(center=(surface.get_width() // 2, y))
    surface.blit(rendered, rect)


_INPUT_ICON_CACHE: Dict[Path, pygame.Surface] = {}
_INPUT_ICON_SCALED: Dict[Tuple[Path, int], pygame.Surface] = {}


def _load_input_icon(path: Path, height: int) -> Optional[pygame.Surface]:
    if height <= 0:
        return None
    key = (path, height)
    if key in _INPUT_ICON_SCALED:
        return _INPUT_ICON_SCALED[key].copy()
    base = _INPUT_ICON_CACHE.get(path)
    if base is None:
        if not path.exists():
            _INPUT_ICON_CACHE[path] = None
            return None
        try:
            base = pygame.image.load(str(path)).convert_alpha()
        except Exception:
            _INPUT_ICON_CACHE[path] = None
            return None
        _INPUT_ICON_CACHE[path] = base
    if base is None:
        return None
    scale = height / float(base.get_height())
    width = max(1, int(base.get_width() * scale))
    scaled = pygame.transform.smoothscale(base, (width, height))
    _INPUT_ICON_SCALED[key] = scaled
    return scaled.copy()


def _input_icon_paths_for_token(token: str, device: str) -> Optional[List[Path]]:
    key = token.upper()
    if key == "WASD":
        return [
            KB_ICON_DIR / "T_W_Key_Retro.png",
            KB_ICON_DIR / "T_A_Key_Retro.png",
            KB_ICON_DIR / "T_S_Key_Retro.png",
            KB_ICON_DIR / "T_D_Key_Retro.png",
        ]

    if device == "controller":
        controller_map = {
            "A": XGAMEPAD_ICON_DIR / "T_X_A_Color.png",
            "B": XGAMEPAD_ICON_DIR / "T_X_B_Color.png",
            "X": XGAMEPAD_ICON_DIR / "T_X_X_Color.png",
            "Y": XGAMEPAD_ICON_DIR / "T_X_Y_Color.png",
            "LB": XGAMEPAD_ICON_DIR / "T_X_LB.png",
            "RB": XGAMEPAD_ICON_DIR / "T_X_RB.png",
            "LT": XGAMEPAD_ICON_DIR / "T_X_LT.png",
            "RT": XGAMEPAD_ICON_DIR / "T_X_RT.png",
            "START": XGAMEPAD_ICON_DIR / "T_X_Share.png",
            "BACK": XGAMEPAD_ICON_DIR / "T_X_Share-1.png",
            "LSTICK": XGAMEPAD_ICON_DIR / "T_X_L_2D.png",
            "RSTICK": XGAMEPAD_ICON_DIR / "T_X_R_2D.png",
            "DPAD": XGAMEPAD_ICON_DIR / "T_X_Dpad.png",
            "UP": XGAMEPAD_ICON_DIR / "T_X_Dpad_Up.png",
            "DOWN": XGAMEPAD_ICON_DIR / "T_X_Dpad_Down.png",
            "LEFT": XGAMEPAD_ICON_DIR / "T_X_Dpad_Left.png",
            "RIGHT": XGAMEPAD_ICON_DIR / "T_X_Dpad_Right.png",
        }
        path = controller_map.get(key)
        return [path] if path else None

    keyboard_map = {
        "ENTER": KB_ICON_DIR / "T_Enter_Key_Retro.png",
        "ESC": KB_ICON_DIR / "T_Esc_Key_Retro.png",
        "ESCAPE": KB_ICON_DIR / "T_Esc_Key_Retro.png",
        "SPACE": KB_ICON_DIR / "T_Space_Key_Retro.png",
        "SHIFT": KB_ICON_DIR / "T_Shift_Key_Retro.png",
        "CTRL": KB_ICON_DIR / "T_Crtl_Key_Retro.png",
        "CONTROL": KB_ICON_DIR / "T_Crtl_Key_Retro.png",
        "TAB": KB_ICON_DIR / "T_Tab_Key_Retro.png",
        "BACKSPACE": KB_ICON_DIR / "T_BackSpace_Key_Retro.png",
        "DEL": KB_ICON_DIR / "T_Del_Key_Retro.png",
        "DELETE": KB_ICON_DIR / "T_Del_Key_Retro.png",
        "PGUP": KB_ICON_DIR / "T_PageUp_Key_Retro.png",
        "PGDN": KB_ICON_DIR / "T_PageDown_Key_Retro.png",
        "PAGEUP": KB_ICON_DIR / "T_PageUp_Key_Retro.png",
        "PAGEDOWN": KB_ICON_DIR / "T_PageDown_Key_Retro.png",
        "HOME": KB_ICON_DIR / "T_Home_Key_Retro.png",
        "END": KB_ICON_DIR / "T_End_Key_Retro.png",
        "UP": KB_ICON_DIR / "T_Up_Key_Retro.png",
        "DOWN": KB_ICON_DIR / "T_Down_Key_Retro.png",
        "LEFT": KB_ICON_DIR / "T_Left_Key_Retro.png",
        "RIGHT": KB_ICON_DIR / "T_Right_Key_Retro.png",
        "ARROWS": KB_ICON_DIR / "T_Cursor_Key_Retro.png",
        "ARROW": KB_ICON_DIR / "T_Cursor_Key_Retro.png",
        "MOUSE": MOUSE_ICON_DIR / "T_Mouse_Simple_Key_Retro.png",
        "CLICK": MOUSE_ICON_DIR / "T_Mouse_Left_Key_Retro.png",
        "LMB": MOUSE_ICON_DIR / "T_Mouse_Left_Key_Retro.png",
        "RMB": MOUSE_ICON_DIR / "T_Mouse_Right_Key_Retro.png",
        "KEY": KB_ICON_DIR / "T_Keyboard_Mouse_Key_Retro_Sprite.png",
    }
    path = keyboard_map.get(key)
    if path:
        return [path]
    if len(key) == 1 and key.isalpha():
        letter_path = KB_ICON_DIR / f"T_{key}_Key_Retro.png"
        return [letter_path]
    return None


def _tokenize_prompt(text: str) -> List[str]:
    return re.findall(r"\\s+|[A-Za-z0-9]+|[^\\w\\s]", text)


def draw_prompt_with_icons(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    y: int,
    color: Tuple[int, int, int],
    device: str = "keyboard",
    x: Optional[int] = None,
) -> None:
    icon_height = int(font.get_height() * 0.9)
    segments: List[Tuple[str, object]] = []
    for token in _tokenize_prompt(text):
        if token.isspace():
            segments.append(("text", token))
            continue
        if re.match(r"^[A-Za-z0-9]+$", token):
            paths = _input_icon_paths_for_token(token, device)
            if paths:
                for path in paths:
                    segments.append(("icon", path))
                continue
        segments.append(("text", token))

    surfaces: List[pygame.Surface] = []
    total_width = 0
    for seg_type, value in segments:
        if seg_type == "text":
            rendered = font.render(str(value), True, color)
        else:
            rendered = _load_input_icon(Path(value), icon_height)
            if rendered is None:
                rendered = font.render(str(value), True, color)
        surfaces.append(rendered)
        total_width += rendered.get_width()

    if x is None:
        cursor_x = (surface.get_width() - total_width) // 2
    else:
        cursor_x = x
    icon_gap = max(2, icon_height // 8)
    prev_icon = False
    for idx, rendered in enumerate(surfaces):
        is_icon = segments[idx][0] == "icon"
        if prev_icon and is_icon:
            cursor_x += icon_gap
        rect = rendered.get_rect()
        rect.midleft = (cursor_x, y)
        rect.centery = y
        surface.blit(rendered, rect)
        cursor_x += rendered.get_width()
        prev_icon = is_icon


# === Startup warning ===
def show_seizure_warning(screen, duration=3.5):
    # Ensure controllers are initialised so gamepad input works here
    try:
        pygame.joystick.init()
        for idx in range(pygame.joystick.get_count()):
            try:
                pygame.joystick.Joystick(idx).init()
            except Exception:
                pass
    except Exception:
        pass

    clock = pygame.time.Clock()
    font = pygame.font.SysFont(FONT_NAME, 48, bold=True)
    small_font = pygame.font.SysFont(FONT_NAME, 28)
    warning_text = "SEIZURE WARNING"
    info_text = "This game contains flashing lights and patterns that may trigger seizures."
    last_input_device = "keyboard"
    def continue_prompt():
        if last_input_device == "controller":
            return "Press A/Start to continue..."
        if last_input_device == "mouse":
            return "Click to continue..."
        return "Press any key to continue..."
    start_time = pygame.time.get_ticks()
    shown_continue = False
    while True:
        pygame.event.pump()  # ensure controller events get queued
        screen.fill((0, 0, 0))
        text_surface = font.render(warning_text, True, (255, 0, 0))
        info_surface = small_font.render(info_text, True, WHITE)
        screen.blit(text_surface, (SCREEN_SIZE[0]//2 - text_surface.get_width()//2, SCREEN_SIZE[1]//2 - 100))
        screen.blit(info_surface, (SCREEN_SIZE[0]//2 - info_surface.get_width()//2, SCREEN_SIZE[1]//2))
        if shown_continue:
            draw_prompt_with_icons(
                screen,
                small_font,
                continue_prompt(),
                SCREEN_SIZE[1] // 2 + 80,
                WHITE,
                device=last_input_device,
            )
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                last_input_device = "keyboard"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                last_input_device = "mouse"
            elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYAXISMOTION, pygame.JOYHATMOTION):
                last_input_device = "controller"
            # Allow keyboard, mouse, or controller buttons after the timer elapses
            if shown_continue and (
                event.type == pygame.KEYDOWN
                or event.type == pygame.MOUSEBUTTONDOWN
                or event.type == pygame.JOYBUTTONDOWN
                or (event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.5)
                or (event.type == pygame.JOYHATMOTION and event.value != (0, 0))
            ):
                return
        # Also accept left stick movement as input once continue is shown
        if shown_continue:
            try:
                for idx in range(pygame.joystick.get_count()):
                    js = pygame.joystick.Joystick(idx)
                    # Typical left stick axes 0/1
                    ax0 = js.get_axis(0)
                    ax1 = js.get_axis(1)
                    if abs(ax0) > 0.5 or abs(ax1) > 0.5:
                        return
            except Exception:
                pass
        if not shown_continue and (pygame.time.get_ticks() - start_time) > duration * 1000:
            shown_continue = True
        clock.tick(60)
        
# === Weather system ===
SNOW_PARTICLE: Dict[str, Any] = {
    "size": 3,
    "color": (255, 255, 255),
    "alpha": 180,
    "speed_range": (1, 2),
    "wind_influence": 0.8,
    "wiggle": 1.0,
}

RAIN_PARTICLE: Dict[str, Any] = {
    "size": 4,
    "color": (180, 200, 255),
    "alpha": 140,
    "speed_range": (7, 9),
    "wind_influence": 0.3,
    "wiggle": 0.2,
}

ASH_PARTICLE: Dict[str, Any] = {
    "size": 2,
    "color": (180, 100, 80),
    "alpha": 160,
    "speed_range": (1, 3),
    "wind_influence": 0.9,
    "wiggle": 1.2,
}


class WeatherParticle:
    def __init__(self, x: float, y: float, settings: Dict[str, Any]):
        self.pos = pygame.Vector2(x, y)
        self.settings = settings
        self.speed = random.uniform(*settings["speed_range"])
        self.wiggle_offset = random.uniform(0.0, math.tau)
        self.alpha = settings["alpha"]

    def update(self, dt: float, wind: float = 0.0) -> None:
        self.pos.y += self.speed * dt * 60.0
        wiggle = math.sin(self.wiggle_offset + pygame.time.get_ticks() * 0.001) * self.settings["wiggle"]
        self.pos.x += (wind * self.settings["wind_influence"] + wiggle) * dt * 60.0
        self.wiggle_offset += 0.1

    def draw(self, surface: pygame.Surface, camera_offset: Tuple[float, float] = (0.0, 0.0)) -> None:
        size = self.settings["size"]
        particle_surface = pygame.Surface((size, size), pygame.SRCALPHA)
        particle_surface.fill((*self.settings["color"], self.alpha))
        draw_pos = (int(self.pos.x - camera_offset[0]), int(self.pos.y - camera_offset[1]))
        surface.blit(particle_surface, draw_pos)


class WeatherSystem:
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.particles: List[WeatherParticle] = []
        self.weather_type: Optional[Dict[str, Any]] = None
        self.particle_count = 0
        self.wind = 0.0
        self.spawn_timer = 0.0
        self.active = False
        self.camera_offset = pygame.Vector2(0, 0)
        self._bounds_min_x = -50.0
        self._bounds_max_x = screen_width + 50.0
        self._bounds_min_y = -50.0
        self._bounds_max_y = screen_height + 50.0

    def set_weather(
        self,
        weather_type: Optional[Dict[str, Any]],
        particle_count: int = 100,
        camera_offset: Tuple[float, float] = (0.0, 0.0),
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> None:
        self.weather_type = weather_type
        self.particle_count = particle_count
        self.particles.clear()
        self.camera_offset.x, self.camera_offset.y = camera_offset
        if bounds is not None:
            min_x, max_x, min_y, max_y = bounds
            low_x, high_x = sorted((min_x, max_x))
            low_y, high_y = sorted((min_y, max_y))
            self._bounds_min_x = low_x - 80.0
            self._bounds_max_x = high_x + 80.0
            self._bounds_min_y = low_y - 120.0
            self._bounds_max_y = max(high_y + 120.0, self._bounds_min_y + 200.0)

        if weather_type:
            for _ in range(particle_count):
                start_y = random.uniform(self._bounds_min_y, self._bounds_max_y)
                self._spawn_particle(start_y)
        self.active = weather_type is not None

    def update(self, dt: float, camera_offset: Tuple[float, float] = (0.0, 0.0)) -> None:
        if not self.active or not self.weather_type:
            return

        self.camera_offset.x, self.camera_offset.y = camera_offset
        self.wind = math.sin(pygame.time.get_ticks() * 0.001) * 0.5
        self.spawn_timer += dt
        if self.spawn_timer >= 0.1:
            self.spawn_timer = 0.0
            particles_needed = self.particle_count - len(self.particles)
            for _ in range(min(particles_needed, 5)):
                top_y = max(self.camera_offset.y - 80.0, self._bounds_min_y - 80.0)
                self._spawn_particle(top_y)

        remaining: List[WeatherParticle] = []
        for particle in self.particles:
            particle.update(dt, self.wind)
            if (
                self._bounds_min_x - 100.0 < particle.pos.x < self._bounds_max_x + 100.0
                and self._bounds_min_y - 200.0 < particle.pos.y < self._bounds_max_y + 200.0
            ):
                remaining.append(particle)
            # Removed unexpected indent here

    def draw(self, surface: pygame.Surface, camera_offset: Tuple[float, float]) -> None:
        if not self.active:
            return
        for particle in self.particles:
            particle.draw(surface, camera_offset)

    def _spawn_particle(self, y_pos: float) -> None:
        if not self.weather_type:
            return
        min_x = self._bounds_min_x
        max_x = self._bounds_max_x
        x = random.uniform(min_x, max_x)
        particle = WeatherParticle(x, y_pos, self.weather_type)
        self.particles.append(particle)


WINDOW_MODES: Tuple[str, ...] = ("windowed", "borderless", "fullscreen")

WINDOW_MODE_LABELS: Dict[str, str] = {
    "windowed": "Windowed",
    "borderless": "Borderless",
    "fullscreen": "Fullscreen",
}


DEFAULT_KEY_MAP = {
    "move_left": pygame.K_a,
    "move_right": pygame.K_d,
    "up": pygame.K_w,
    "down": pygame.K_s,
    "jump": pygame.K_SPACE,
    "shoot": pygame.K_f,
    "shield": pygame.K_LSHIFT,
    "dash": pygame.K_e,
    "pause": pygame.K_ESCAPE,
    "accept": pygame.K_RETURN,
    "back": pygame.K_ESCAPE,
    "menu_up": pygame.K_UP,
    "menu_down": pygame.K_DOWN,
}

DEFAULT_CONTROLLER_MAP = {
    "move_axis_x": 0,
    "move_axis_y": 1,
    "jump": 0, # A button
    "shoot": 2, # X button
    "shield": 3, # Y button
    "dash": 5, # RB button
    "pause": 7, # Start button
    "accept": 0, # A button
    "back": 1, # B button
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "music": True,
    "sfx": True,
    "glitch_fx": True,
    "window_mode": "windowed",
    "key_map": DEFAULT_KEY_MAP,
    "controller_map": DEFAULT_CONTROLLER_MAP,
    "character": "player",  # default character
    "skills": {
        "rapid_charge": False,
        "blast_radius": False,
        "shield_pulse": False,
        "reflective_shield": False,
        "stagger": False,
        "extra_health_levels": 0,
    },
}

DEFAULT_COSMETICS: Dict[str, Any] = {
    "outfit": "None",
    "trail": "None",
    "hat": "None",
    "owned_outfits": ["None"],
    "owned_trails": ["None"],
    "owned_hats": ["None"],
}

OUTFIT_COLORS: Dict[str, Tuple[int, int, int]] = {
    "None": (160, 220, 255),
    "Neon Runner": (120, 255, 220),
    "Crimson Armor": (240, 90, 90),
    "Midnight": (90, 110, 200),
    "Gold": (240, 200, 90),
    "Verdant": (80, 170, 110),
    "Stone": (140, 140, 150),
    "Dune": (210, 180, 120),
    "Thorn": (90, 160, 110),
    "Frost": (150, 190, 230),
    "Ember": (210, 100, 70),
    "Sky": (160, 210, 245),
    "Circuit": (90, 210, 210),
    "Spectral": (180, 160, 220),
    "Void": (150, 80, 170),
}

TRAIL_COLORS: Dict[str, Tuple[int, int, int]] = {
    "None": (200, 240, 255),
    "Glitter": (255, 220, 120),
    "Cyber": (120, 255, 200),
    "Ghost": (200, 200, 255),
    "Inferno": (255, 140, 80),
    "Verdant": (120, 220, 140),
    "Stone": (180, 180, 190),
    "Dune": (240, 210, 150),
    "Thorn": (130, 210, 150),
    "Frost": (200, 230, 255),
    "Ember": (255, 140, 90),
    "Sky": (180, 230, 255),
    "Circuit": (120, 255, 230),
    "Spectral": (210, 190, 255),
    "Void": (230, 140, 240),
}

TRAIL_STYLES: Dict[str, Dict[str, Any]] = {
    "Glitter": {"life": 0.5, "size": 18, "jitter": 6, "count": 4, "tex_scale": 0.8},
    "Cyber": {"life": 0.45, "size": 18, "jitter": 3, "count": 1, "tex_scale": 0.9},
    "Ghost": {"life": 0.7, "size": 22, "jitter": 2, "count": 1, "tex_scale": 1.0},
    "Inferno": {"life": 0.38, "size": 20, "jitter": 5, "count": 2, "tex_scale": 0.9},
    "Verdant": {"life": 0.5, "size": 20, "jitter": 4, "count": 1, "tex_scale": 0.9},
    "Stone": {"life": 0.6, "size": 18, "jitter": 2, "count": 1, "tex_scale": 0.9},
    "Dune": {"life": 0.52, "size": 19, "jitter": 4, "count": 1, "tex_scale": 0.9},
    "Thorn": {"life": 0.5, "size": 19, "jitter": 4, "count": 1, "tex_scale": 0.9},
    "Frost": {"life": 0.58, "size": 20, "jitter": 3, "count": 1, "tex_scale": 0.9},
    "Ember": {"life": 0.45, "size": 20, "jitter": 5, "count": 2, "tex_scale": 0.9},
    "Sky": {"life": 0.5, "size": 19, "jitter": 4, "count": 1, "tex_scale": 0.9},
    "Circuit": {"life": 0.45, "size": 18, "jitter": 3, "count": 1, "tex_scale": 0.9},
    "Spectral": {"life": 0.75, "size": 22, "jitter": 2, "count": 1, "tex_scale": 1.0},
    "Void": {"life": 0.62, "size": 20, "jitter": 3, "count": 1, "tex_scale": 0.9},
}

HAT_COLORS: Dict[str, Tuple[int, int, int]] = {
    "None": (200, 200, 200),
    "Wizard": (120, 80, 200),
    "Pilot": (200, 120, 60),
    "Halo": (255, 230, 120),
    "Viking": (180, 120, 80),
    "Verdant": (120, 200, 140),
    "Stone": (160, 160, 170),
    "Dune": (220, 180, 120),
    "Thorn": (110, 190, 130),
    "Frost": (170, 210, 240),
    "Ember": (220, 120, 80),
    "Sky": (170, 220, 250),
    "Circuit": (100, 220, 220),
    "Spectral": (190, 170, 230),
    "Void": (170, 90, 190),
}

BG_COLORS = [
    (100, 200, 100),
    (80, 80, 100),
    (210, 190, 100),
    (40, 120, 40),
    (200, 220, 255),
    (150, 60, 40),
    (160, 200, 255),
    (60, 60, 100),
    (100, 80, 50),
    (180, 0, 180),
]

WORLD_SPECIALS: Dict[int, str] = {
    1: "coin",
    2: "rock",
    3: "quicksand",
    4: "spike",
    5: "icicle",
    6: "lava",
    7: "wind",
    8: "electric",
    9: "ghost",
    10: "glitch",
}

# Options for ambient/world-appropriate objects (will be chosen randomly per spawn)
WORLD_THEME_OBJECTS: Dict[int, List[str]] = {
    1: ["coin"],
    2: ["rock", "coin"],
    3: ["quicksand", "rock"],
    4: ["spike", "coin"],
    5: ["icicle", "coin"],
    6: ["lava", "rock"],
    7: ["wind", "coin"],
    8: ["electric", "coin"],
    9: ["ghost", "coin"],
    10: ["glitch", "coin"],
}

# Portal lightning colors by world
WORLD_PORTAL_COLORS: Dict[int, Tuple[int, int, int]] = {
    1: (120, 220, 255),
    2: (255, 180, 80),
    3: (230, 200, 120),
    4: (120, 200, 120),
    5: (180, 220, 255),
    6: (255, 120, 80),
    7: (200, 220, 255),
    8: (120, 255, 220),
    9: (180, 140, 255),
    10: (220, 120, 255),
}

SPECIAL_TOOL_LABELS: Dict[str, str] = {
    "coin": "Bonus Coin",
    "rock": "Falling Rock",
    "quicksand": "Quicksand",
    "spike": "Spike",
    "icicle": "Icicle",
    "lava_bubble": "Lava Bubble",
    "wind_orb": "Wind Orb",
    "electric_tile": "Electric Tile",
    "ghost_orb": "Ghost Orb",
    "glitch_cube": "Glitch Cube",
}

ENEMY_COLORS = [
    (200, 80, 80),
    (180, 130, 90),
    (210, 180, 60),
    (90, 160, 110),
    (120, 150, 220),
    (220, 100, 50),
    (120, 200, 220),
    (220, 80, 180),
    (200, 120, 240),
    (255, 180, 255),
]

TOWER_NAMES = [
    "Tower of Growth",
    "Tower of Stone",
    "Tower of Dunes",
    "Tower of Nature",
    "Tower of Frost",
    "Tower of Flame",
    "Tower of Air",
    "Tower of Circuits",
    "Tower of Echoes",
    "Tower of Corruption",
]

BOSS_NAMES = [
    "Forest Golem",         # World 1 - Plant/Nature
    "Crystal Golem", # World 2 - Stone/Rock
    "Sand Serpant",  # World 3 - Sand/Desert
    "Mushroom Fungi",  # World 4 - Forest/Thorns
    "Frost Yeti",    # World 5 - Ice/Snow
    "Flame Dragon",      # World 6 - Fire/Lava
    "Sky Serpant",    # World 7 - Wind/Air
    "Cyber Golem",     # World 8 - Electric
    "Ghost Of The Ancient Past",   # World 9 - Ghost/Spirit
    "The Void Wraith",      # World 10 - Glitch/Corruption
]

BOSS_ANIMATION_STATES: Tuple[str, ...] = ("idle", "attack1", "attack2", "death")

@dataclass(frozen=True)
class BossProfile:
    max_health: int
    hover_speed: float
    sway_radius: float
    vertical_sway: float
    sway_frequency: float
    vertical_frequency: float
    short_cooldown: float
    long_cooldown: float
    ground_speed: float = 60.0
    patrol_range: float = 140.0


DEFAULT_BOSS_PROFILE = BossProfile(
    max_health=12,
    hover_speed=0.02,
    sway_radius=60,
    vertical_sway=12,
    sway_frequency=0.7,
    vertical_frequency=1.0,
    short_cooldown=2.0,
    long_cooldown=3.5,
    ground_speed=70.0,
    patrol_range=150.0,
)

# Increased boss health for all worlds to make bosses harder to kill
BOSS_PROFILES: Dict[int, BossProfile] = {
    1: BossProfile(32, 0.017, 78, 18, 0.55, 1.25, 1.6, 4.2, 60.0, 160.0),
    2: BossProfile(44, 0.015, 54, 9, 0.5, 0.8, 2.6, 4.9, 70.0, 150.0),
    3: BossProfile(36, 0.019, 82, 14, 0.68, 0.9, 2.2, 4.5, 65.0, 140.0),
    4: BossProfile(38, 0.018, 72, 16, 0.62, 1.05, 2.0, 4.0, 72.0, 150.0),
    5: BossProfile(40, 0.016, 66, 10, 0.8, 1.4, 2.4, 4.6, 68.0, 130.0),
    6: BossProfile(48, 0.02, 70, 12, 0.9, 1.1, 1.8, 3.8, 80.0, 170.0),
    7: BossProfile(42, 0.023, 90, 20, 0.5, 1.5, 1.7, 4.3, 75.0, 160.0),
    8: BossProfile(46, 0.021, 64, 12, 0.75, 1.0, 1.9, 3.7, 70.0, 140.0),
    9: BossProfile(40, 0.019, 76, 18, 0.6, 1.6, 2.1, 4.4, 78.0, 180.0),
    10: BossProfile(52, 0.022, 88, 20, 0.95, 1.3, 1.5, 3.6, 85.0, 200.0),
}

BOSS_VISUALS: Dict[int, Dict[str, Any]] = {
    1: {
        "primary": (74, 168, 86),
        "secondary": (46, 104, 58),
        "accent": (214, 238, 140),
        "detail": (32, 80, 42),
    },
    2: {
        "primary": (0, 0, 0),  # Add a primary color or use the correct value
        "secondary": (88, 84, 90),
        "accent": (214, 214, 220),
        "detail": (60, 56, 64),
    },
    3: {
        "primary": (218, 188, 122),
        "secondary": (168, 140, 80),
        "accent": (248, 220, 156),
        "detail": (120, 96, 58),
    },
    4: {
        "primary": (112, 174, 128),
        "secondary": (64, 108, 74),
        "accent": (190, 226, 160),
        "detail": (52, 80, 54),
    },
    5: {
        "primary": (168, 216, 236),
        "secondary": (120, 178, 228),
        "accent": (230, 246, 255),
        "detail": (90, 140, 200),
    },
    6: {
        "primary": (226, 86, 40),
        "secondary": (150, 38, 24),
        "accent": (255, 202, 88),
        "detail": (92, 18, 12),
    },
    7: {
        "primary": (184, 220, 244),
        "secondary": (134, 180, 230),
        "accent": (240, 252, 255),
        "detail": (94, 146, 210),
    },
    8: {
        "primary": (58, 92, 170),
        "secondary": (34, 54, 112),
        "accent": (132, 230, 242),
        "detail": (68, 216, 174),
    },
    9: {
        "primary": (176, 138, 226),
        "secondary": (104, 74, 160),
        "accent": (236, 200, 250),
        "detail": (76, 48, 120),
    },
    10: {
        "primary": (214, 68, 222),
        "secondary": (44, 18, 84),
        "accent": (90, 220, 248),
        "detail": (24, 8, 54),
    },
}

def _mix_colors(color_a: Tuple[int, int, int], color_b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(color_a[i] * (1.0 - t) + color_b[i] * t) for i in range(3))


def _brighten(color: Tuple[int, int, int], amount: int) -> Tuple[int, int, int]:
    return tuple(min(255, max(0, c + amount)) for c in color)


BOSS_SPAWN_THEMES: Dict[int, Dict[str, Any]] = {
    1: {"shape": "leaf", "beam": _brighten(BOSS_VISUALS[1]["accent"], 40), "particle": BOSS_VISUALS[1]["accent"], "highlight": BOSS_VISUALS[1]["detail"]},
    2: {"shape": "stone", "beam": _brighten(BOSS_VISUALS[2]["accent"], 30), "particle": BOSS_VISUALS[2]["accent"], "highlight": BOSS_VISUALS[2]["detail"]},
    3: {"shape": "sand", "beam": _brighten(BOSS_VISUALS[3]["accent"], 45), "particle": BOSS_VISUALS[3]["accent"], "highlight": BOSS_VISUALS[3]["detail"]},
    4: {"shape": "spore", "beam": _brighten(BOSS_VISUALS[4]["accent"], 35), "particle": BOSS_VISUALS[4]["accent"], "highlight": BOSS_VISUALS[4]["detail"]},
    5: {"shape": "snow", "beam": _mix_colors(BOSS_VISUALS[5]["accent"], WHITE, 0.4), "particle": BOSS_VISUALS[5]["accent"], "highlight": BOSS_VISUALS[5]["detail"]},
    6: {"shape": "ember", "beam": _brighten(BOSS_VISUALS[6]["accent"], 50), "particle": BOSS_VISUALS[6]["accent"], "highlight": BOSS_VISUALS[6]["detail"]},
    7: {"shape": "gust", "beam": _mix_colors(BOSS_VISUALS[7]["accent"], WHITE, 0.35), "particle": BOSS_VISUALS[7]["accent"], "highlight": BOSS_VISUALS[7]["detail"]},
    8: {"shape": "spark", "beam": _brighten(BOSS_VISUALS[8]["accent"], 55), "particle": BOSS_VISUALS[8]["accent"], "highlight": BOSS_VISUALS[8]["detail"]},
    9: {"shape": "wisp", "beam": _mix_colors(BOSS_VISUALS[9]["accent"], WHITE, 0.3), "particle": BOSS_VISUALS[9]["accent"], "highlight": BOSS_VISUALS[9]["detail"]},
    10: {"shape": "glitch", "beam": _brighten(BOSS_VISUALS[10]["accent"], 60), "particle": BOSS_VISUALS[10]["accent"], "highlight": BOSS_VISUALS[10]["detail"]},
}

DEFAULT_SPAWN_THEME: Dict[str, Any] = {
    "shape": "spark",
    "beam": (220, 180, 255),
    "particle": (200, 160, 240),
    "highlight": (120, 80, 160),
}

DEV_CONSOLE_CODE = [pygame.K_SLASH]

PLAYER_SPAWN = (100, 450)

# ---------------------------------------------------------------------------
# Settings / progress management
# ---------------------------------------------------------------------------


# === Settings / progress / assets ===
class SettingsManager:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text())
        except Exception as exc:
            print(f"[Settings] Failed to load settings: {exc}")
            return

        for key, default in DEFAULT_SETTINGS.items():
            if key not in loaded:
                continue
            value = loaded[key]
            if isinstance(default, bool):
                self.data[key] = bool(value)
            elif isinstance(default, int):
                try:
                    self.data[key] = int(value)
                except Exception:
                    self.data[key] = default
            elif isinstance(default, float):
                try:
                    self.data[key] = float(value)
                except Exception:
                    self.data[key] = default
            elif isinstance(default, str):
                self.data[key] = str(value)
            else:
                self.data[key] = value

    def save(self) -> None:
        try:
            self.path.write_text(json.dumps(self.data, indent=2))
        except Exception as exc:
            print(f"[Settings] Failed to save settings: {exc}")

    def toggle(self, key: str) -> bool:
        current = self.data.get(key, DEFAULT_SETTINGS.get(key))
        if not isinstance(current, bool):
            raise TypeError(f"Setting '{key}' is not boolean and cannot be toggled.")
        self.data[key] = not current
        self.save()
        return self.data[key]

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown setting '{key}'.")
        self.data[key] = value
        self.save()

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key, DEFAULT_SETTINGS.get(key))


class ProgressManager:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.world = 1
        self.level = 1
        # persisted player color (r,g,b) or None
        self.player_color: Optional[Tuple[int, int, int]] = None
        self.coins = 0
        self.skills: Dict[str, Any] = DEFAULT_SETTINGS["skills"].copy()
        self.cosmetics: Dict[str, Any] = DEFAULT_COSMETICS.copy()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            self.world = int(data.get("world", 1))
            self.level = int(data.get("level", 1))
            pc = data.get("player_color")
            if isinstance(pc, (list, tuple)) and len(pc) == 3:
                try:
                    self.player_color = (int(pc[0]), int(pc[1]), int(pc[2]))
                except Exception:
                    self.player_color = None
            else:
                self.player_color = None
            self.coins = int(data.get("coins", 0))
            skills = data.get("skills", {})
            if isinstance(skills, dict):
                base = DEFAULT_SETTINGS["skills"].copy()
                base.update(skills)
                self.skills = base
            cosmetics = data.get("cosmetics", {})
            if isinstance(cosmetics, dict):
                base_c = DEFAULT_COSMETICS.copy()
                base_c.update(cosmetics)
                # Migrate Default to None and ensure owned lists include None
                if base_c.get("outfit") == "Default":
                    base_c["outfit"] = "None"
                if base_c.get("trail") == "Default":
                    base_c["trail"] = "None"
                if base_c.get("hat") == "Default":
                    base_c["hat"] = "None"
                if "owned_outfits" in base_c:
                    owned_outfits = list(base_c["owned_outfits"])
                    owned_outfits = ["None" if name == "Default" else name for name in owned_outfits]
                    if "None" not in owned_outfits:
                        owned_outfits.insert(0, "None")
                    base_c["owned_outfits"] = owned_outfits
                if "owned_trails" in base_c:
                    owned_trails = list(base_c["owned_trails"])
                    owned_trails = ["None" if name == "Default" else name for name in owned_trails]
                    if "None" not in owned_trails:
                        owned_trails.insert(0, "None")
                    base_c["owned_trails"] = owned_trails
                if "owned_hats" in base_c:
                    owned_hats = list(base_c["owned_hats"])
                    owned_hats = ["None" if name == "Default" else name for name in owned_hats]
                    if "None" not in owned_hats:
                        owned_hats.insert(0, "None")
                    base_c["owned_hats"] = owned_hats
                self.cosmetics = base_c
            # Load speedrun timer data if present
            game = getattr(self, 'game', None)
            if game is not None:
                if "speedrun_active" in data:
                    game.speedrun_active = bool(data["speedrun_active"])
                if "speedrun_start" in data:
                    game.speedrun_start = float(data["speedrun_start"])
                if "speedrun_pause_accum" in data:
                    game.speedrun_pause_accum = float(data["speedrun_pause_accum"])
                if "speedrun_paused" in data:
                    game.speedrun_paused = bool(data["speedrun_paused"])
        except Exception as exc:
            print(f"[Save] Failed to read save file: {exc}")
            self.world, self.level = 1, 1
            self.player_color = None
            self.coins = 0

    def save(self, world: int, level: int, player_color: Optional[Tuple[int, int, int]] = None, coins: Optional[int] = None, skills: Optional[Dict[str, Any]] = None, cosmetics: Optional[Dict[str, Any]] = None) -> None:
        """Persist world, level, coins, optional player_color, and selected character/form if available, plus speedrun timer data."""
        self.world, self.level = world, level
        if coins is not None:
            self.coins = int(coins)
        if skills is not None:
            self.skills = skills
        if cosmetics is not None:
            self.cosmetics = cosmetics
        if player_color is not None:
            try:
                self.player_color = (int(player_color[0]), int(player_color[1]), int(player_color[2]))
            except Exception:
                self.player_color = None
        payload: Dict[str, Any] = {"world": self.world, "level": self.level, "coins": self.coins}
        payload["skills"] = self.skills
        payload["cosmetics"] = self.cosmetics
        if self.player_color is not None:
            payload["player_color"] = list(self.player_color)
        game = getattr(self, 'game', None)
        if game is not None:
            selected_character = getattr(game, 'selected_character', None)
            selected_form = getattr(game, 'selected_form', None)
            if selected_character is not None:
                payload["character"] = selected_character
            if selected_form is not None:
                payload["form"] = selected_form
            # Save speedrun timer data
            payload["speedrun_active"] = getattr(game, "speedrun_active", False)
            payload["speedrun_start"] = getattr(game, "speedrun_start", 0.0)
            payload["speedrun_pause_accum"] = getattr(game, "speedrun_pause_accum", 0.0)
            payload["speedrun_paused"] = getattr(game, "speedrun_paused", False)
        try:
            self.path.write_text(json.dumps(payload))
        except Exception as exc:
            print(f"[Save] Failed to write save file: {exc}")

    def reset(self) -> None:
        # Clearing progress also clears saved player color and coins
        self.player_color = None
        self.coins = 0
        self.skills = DEFAULT_SETTINGS["skills"].copy()
        self.cosmetics = DEFAULT_COSMETICS.copy()
        self.save(1, 1, player_color=None, coins=0, cosmetics=self.cosmetics)


class AssetCache:
    def __init__(self):
        # ...existing code...
        self.last_scene = None
        # ...existing code...
        self._backgrounds: Dict[int, pygame.Surface] = {}
        self._platform_bases: Dict[int, pygame.Surface] = {}
        self._platform_scaled: Dict[Tuple[int, Tuple[int, int]], pygame.Surface] = {}
        self._fonts: Dict[Tuple[int, bool], pygame.font.Font] = {}
        self._icon: Optional[pygame.Surface] = None
        self._enemy_textures: Dict[int, pygame.Surface] = {}
        self._boss_textures: Dict[int, pygame.Surface] = {}
        self._boss_projectiles: Dict[int, pygame.Surface] = {}
        self._boss_animation_frames: Dict[int, Dict[str, List[pygame.Surface]]] = {}
        self._portal_textures: Dict[Tuple[int, str], pygame.Surface] = {}
        self._hat_textures: Dict[str, pygame.Surface] = {}
        self._hat_scaled: Dict[Tuple[str, Tuple[int, int]], pygame.Surface] = {}
        self._trail_textures: Dict[str, pygame.Surface] = {}
        self._trail_scaled: Dict[Tuple[str, Tuple[int, int]], pygame.Surface] = {}
        self._title_logo_frames: Optional[List[pygame.Surface]] = None
        self._title_logo_durations: Optional[List[float]] = None
        self._title_logo_static: Optional[pygame.Surface] = None

    def font(self, size: int, bold: bool = True) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.SysFont(FONT_NAME, size, bold=bold)
        return self._fonts[key]

    def icon(self) -> Optional[pygame.Surface]:
        if self._icon is not None:
            return self._icon
        path = BACKGROUND_DIR / "title_logo.png"
        if path.exists():
            try:
                self._icon = pygame.image.load(path).convert_alpha()
            except Exception as exc:
                print(f"[Assets] Failed to load icon: {exc}")
                self._icon = None
        return self._icon

    def background(self, bg: str) -> pygame.Surface:
        # Accepts a string background name (e.g., 'grass', 'flame', etc.)
        # Map names to color or file
            BG_NAME_TO_INDEX = {
                'grass': 1,
                'cave': 2,
                'desert': 3,
                'forest': 4,
                'snow': 5,
                'flame': 6,
                'sky': 7,
                'circuit': 8,
                'ancient ruins': 9,
                'glitch': 10,
            }
            idx = 1
            # Try to convert to int if possible, else map string
            try:
                idx = int(bg)
            except (ValueError, TypeError):
                idx = BG_NAME_TO_INDEX.get(str(bg).lower(), 1)
            idx = max(1, min(idx, len(BG_COLORS)))
            if idx not in self._backgrounds:
                path = BACKGROUND_DIR / f"world{idx}.png"
                if path.exists():
                    try:
                        image = pygame.image.load(path).convert()
                        image = pygame.transform.scale(image, SCREEN_SIZE)
                    except Exception as exc:
                        print(f"[Assets] Failed to load background {path}: {exc}")
                        image = pygame.Surface(SCREEN_SIZE)
                        image.fill(BG_COLORS[idx - 1])
                else:
                    image = pygame.Surface(SCREEN_SIZE)
                    image.fill(BG_COLORS[idx - 1])
                self._backgrounds[idx] = image
            return self._backgrounds[idx].copy()

    def platform_texture(self, world: int, size: Tuple[int, int]) -> pygame.Surface:
        key = (world, size)
        if key in self._platform_scaled:
            return self._platform_scaled[key].copy()

        base = self._platform_bases.get(world)
        if base is None:
            path = PLATFORM_DIR / f"platform{world}.png"
            if path.exists():
                try:
                    base = pygame.image.load(path).convert_alpha()
                except Exception as exc:
                    print(f"[Assets] Failed to load platform {path}: {exc}")
                    base = None
            if base is None:
                base = pygame.Surface((64, 16))
                base.fill((100, 60, 30))
            self._platform_bases[world] = base

        scaled = pygame.transform.smoothscale(base, size)
        self._platform_scaled[key] = scaled
        return scaled.copy()

    def enemy_texture(self, world: int) -> pygame.Surface:
        world = max(1, min(world, len(ENEMY_COLORS)))
        if world not in self._enemy_textures:
            path = ASSET_DIR / "enemies" / f"world{world}" / "enemy.png"
            texture: Optional[pygame.Surface] = None
            if path.exists():
                try:
                    texture = pygame.image.load(path).convert_alpha()
                except Exception as exc:
                    print(f"[Assets] Failed to load enemy {path}: {exc}")
            if texture is None:
                texture = pygame.Surface((34, 34), pygame.SRCALPHA)
                color = ENEMY_COLORS[world - 1]
                pygame.draw.circle(texture, color, (17, 17), 16)
                pygame.draw.circle(texture, (255, 255, 255, 200), (12, 12), 6)
                pygame.draw.circle(texture, (0, 0, 0), (20, 20), 4)
            self._enemy_textures[world] = texture
        return self._enemy_textures[world].copy()

    def boss_texture(self, world: int) -> pygame.Surface:
        """
        Return a representative boss surface for the requested world.
        Loads the first idle frame from disk. No procedural fallback.
        """
        world = max(1, min(world, len(BG_COLORS)))
        cached = self._boss_textures.get(world)
        if cached is not None:
            return cached.copy()

        animations = self._boss_animation_frames.get(world)
        if animations is None:
            animations = self._load_boss_frames(world)
            if animations is not None:
                self._boss_animation_frames[world] = animations

        idle_frames = animations["idle"] if animations and "idle" in animations else []
        if idle_frames:
            base_surface = idle_frames[0]
        else:
            raise RuntimeError(f"No boss idle frames found for world {world}. Boss asset missing.")

        self._boss_textures[world] = base_surface.copy()
        return self._boss_textures[world].copy()

    def boss_animation_frames(self, world: int) -> Dict[str, List[pygame.Surface]]:
        """
        Load boss animation frames. Only loads PNG assets. No procedural fallback.
        """
        world = max(1, min(world, len(BG_COLORS)))
        animations = self._boss_animation_frames.get(world)
        if animations is None:
            animations = self._load_boss_frames(world)
            if animations is None:
                raise RuntimeError(f"No boss animation frames found for world {world}. Boss asset missing.")
            self._boss_animation_frames[world] = animations
        return self._clone_animation_frames(animations)

    def boss_projectile_texture(self, world: int) -> pygame.Surface:
        """
        Loads boss projectile texture from asset file. No procedural fallback.
        """
        world = max(1, min(world, len(BG_COLORS)))
        if world not in self._boss_projectiles:
            base_dir = ASSET_DIR / "bosses" / f"world{world}"
            # Try to load projectile frame(s) by convention
            for idx in range(1, 10):
                path = base_dir / f"world{world}_boss_projectile_{idx}.png"
                if path.exists():
                    try:
                        texture = pygame.image.load(path).convert_alpha()
                        self._boss_projectiles[world] = texture
                        break
                    except Exception as exc:
                        print(f"[Assets] Failed to load boss projectile {path}: {exc}")
            else:
                raise RuntimeError(f"No boss projectile asset found for world {world}.")
        return self._boss_projectiles[world].copy()

    @staticmethod
    def _clone_animation_frames(animations: Dict[str, List[pygame.Surface]]) -> Dict[str, List[pygame.Surface]]:
        return {state: [frame.copy() for frame in frames] for state, frames in animations.items()}

    def _load_boss_frames(self, world: int) -> Optional[Dict[str, List[pygame.Surface]]]:
        frames = self._load_boss_frames_from_dir(world)
        if not frames:
            frames = self._load_boss_frames_from_sheet(world)
        if frames:
            return frames
        return self._generate_boss_fallback_frames(world)

    def _load_boss_frames_from_dir(self, world: int) -> Optional[Dict[str, List[pygame.Surface]]]:
        base_dir = ASSET_DIR / "bosses" / f"world{world}"
        if not base_dir.exists():
            return None
        animations: Dict[str, List[pygame.Surface]] = {}
        for state in BOSS_ANIMATION_STATES:
            frames: List[pygame.Surface] = []
            index = 1
            while True:
                path = base_dir / f"world{world}_boss_{state}_{index}.png"
                if not path.exists():
                    break
                try:
                    frame = pygame.image.load(path).convert_alpha()
                except Exception as exc:
                    print(f"[Assets] Failed to load boss frame {path}: {exc}")
                    return None
                frames.append(frame)
                index += 1
            animations[state] = frames
        if all(not frames for frames in animations.values()):
            return None
        return animations

    def _generate_boss_fallback_frames(self, world: int) -> Dict[str, List[pygame.Surface]]:
        """Create placeholder boss animations using themed colors when assets are missing."""
        visuals = BOSS_VISUALS.get(world, {})
        primary = visuals.get("primary", (140, 140, 200))
        secondary = visuals.get("secondary", (80, 80, 120))
        accent = visuals.get("accent", (255, 200, 120))
        size = (96, 96)

        def make_frame(scale: float, pulse: int) -> pygame.Surface:
            surf = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.circle(surf, secondary, (48, 60), int(34 * scale))
            pygame.draw.circle(surf, primary, (48, 52), int(28 * scale))
            pygame.draw.circle(surf, accent, (48, 40), int(max(8, 14 * scale)))
            if pulse > 0:
                pygame.draw.circle(surf, (255, 255, 255, 60), (48, 52), int(30 * scale + pulse), width=2)
            return surf

        idle = [make_frame(1.0 + 0.02 * i, 0) for i in range(6)]
        walk = [make_frame(1.05 + 0.03 * math.sin(i / 2), 4) for i in range(6)]
        attack1 = [make_frame(1.1 + 0.05 * math.sin(i / 2), 8) for i in range(6)]
        attack2 = [make_frame(1.15 + 0.06 * math.sin(i / 1.5), 10) for i in range(6)]
        death = [make_frame(max(0.2, 1.0 - 0.08 * i), 0) for i in range(6)]

        return {
            "idle": idle,
            "walk": walk,
            "attack1": attack1,
            "attack2": attack2,
            "death": death,
        }

    def _load_boss_frames_from_sheet(self, world: int) -> Optional[Dict[str, List[pygame.Surface]]]:
        sheet_path = ASSET_DIR / "bosses" / f"boss_world{world}.png"
        if not sheet_path.exists():
            return None
        try:
            sheet = pygame.image.load(sheet_path).convert_alpha()
        except Exception as exc:
            print(f"[Assets] Failed to load boss sheet {sheet_path}: {exc}")
            return None

        columns = 4
        rows = 4
        frame_w = sheet.get_width() // columns
        frame_h = sheet.get_height() // rows
        if frame_w <= 0 or frame_h <= 0:
            return None

        animations: Dict[str, List[pygame.Surface]] = {}
        for row, state in enumerate(BOSS_ANIMATION_STATES):
            frames: List[pygame.Surface] = []
            for col in range(columns):
                rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
                frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                frames.append(frame)
            animations[state] = frames
        return animations


    def portal_texture(self, world: int, variant: str = "normal") -> pygame.Surface:
        world = max(1, min(world, len(BG_COLORS)))
        base_key = (world, "base")
        if base_key not in self._portal_textures:
            texture = self._create_portal_circle(world)
            self._portal_textures[base_key] = texture

        if variant == "normal":
            return self._portal_textures[base_key].copy()

        key = (world, variant)
        if key not in self._portal_textures:
            base = self._portal_textures[base_key].copy()
            overlay = pygame.Surface(base.get_size(), pygame.SRCALPHA)
            w, h = base.get_size()
            core_rect = pygame.Rect(int(w * 0.25), int(h * 0.3), int(w * 0.5), int(h * 0.45))

            if variant == "boss_locked":
                pygame.draw.line(overlay, (255, 60, 60, 220), core_rect.topleft, core_rect.bottomright, width=4)
                pygame.draw.line(overlay, (255, 60, 60, 220), core_rect.bottomleft, core_rect.topright, width=4)
            elif variant == "boss_active":
                glow_color = (255, 255, 255, 180)
                for radius in range(3):
                    inflate = radius * 6
                    rect = core_rect.inflate(inflate, inflate)
                    pygame.draw.ellipse(overlay, glow_color, rect, width=2)
                pygame.draw.ellipse(overlay, (255, 255, 255, 220), core_rect, width=0)
            else:
                self._portal_textures[key] = base
                return self._portal_textures[key].copy()

            base.blit(overlay, (0, 0))
            self._portal_textures[key] = base

        return self._portal_textures[key].copy()

    def hat_texture(self, hat: str, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        key = (hat, size)
        if key in self._hat_scaled:
            return self._hat_scaled[key].copy()

        base = self._hat_textures.get(hat)
        if base is None:
            path = HAT_DIR / f"{hat}.png"
            if path.exists():
                try:
                    base = pygame.image.load(path).convert_alpha()
                except Exception as exc:
                    print(f"[Assets] Failed to load hat {path}: {exc}")
                    base = None
            self._hat_textures[hat] = base

        if base is None:
            return None

        scaled = pygame.transform.smoothscale(base, size)
        self._hat_scaled[key] = scaled
        return scaled.copy()

    def trail_texture(self, trail: str, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        key = (trail, size)
        if key in self._trail_scaled:
            return self._trail_scaled[key].copy()

        base = self._trail_textures.get(trail)
        if base is None:
            path = TRAIL_DIR / f"{trail}.png"
            if path.exists():
                try:
                    base = pygame.image.load(path).convert_alpha()
                except Exception as exc:
                    print(f"[Assets] Failed to load trail {path}: {exc}")
                    base = None
            self._trail_textures[trail] = base

        if base is None:
            return None

        scaled = pygame.transform.smoothscale(base, size)
        self._trail_scaled[key] = scaled
        return scaled.copy()

    def _ensure_title_logo_assets(self) -> None:
        target_width = 420

        if self._title_logo_frames is None or self._title_logo_durations is None:
            frames: List[pygame.Surface] = []
            durations: List[float] = []
            gif_path = BACKGROUND_DIR / "title_logo.gif"
            if gif_path.exists():
                gif_frames, gif_durations = load_gif_frames(gif_path)
                frames.extend(gif_frames)
                durations.extend(gif_durations)

            processed_frames: List[pygame.Surface] = []
            for surface in frames:
                width, height = surface.get_size()
                if width != target_width and width > 0:
                    scale = target_width / width
                    target_height = max(1, int(height * scale))
                    surface = pygame.transform.smoothscale(surface, (target_width, target_height))
                processed_frames.append(surface.convert_alpha())

            if processed_frames:
                self._title_logo_frames = processed_frames
                self._title_logo_durations = durations or [0.1] * len(processed_frames)
            else:
                self._title_logo_frames = []
                self._title_logo_durations = []

        if self._title_logo_static is None:
            surface: Optional[pygame.Surface]
            png_path = BACKGROUND_DIR / "title_logo.png"
            if png_path.exists():
                try:
                    surface = pygame.image.load(png_path).convert_alpha()
                except Exception as exc:
                    print(f"[Assets] Failed to load static title logo {png_path}: {exc}")
                    surface = None
            else:
                surface = None

            if surface is None:
                surface = pygame.Surface((360, 140), pygame.SRCALPHA)
                draw_center_text(surface, pygame.font.SysFont(FONT_NAME, 36, bold=True), TITLE, surface.get_height() // 2, WHITE)

            width, height = surface.get_size()
            if width != target_width and width > 0:
                scale = target_width / width
                target_height = max(1, int(height * scale))
                surface = pygame.transform.smoothscale(surface, (target_width, target_height))
            self._title_logo_static = surface.convert_alpha()

    def title_logo_frames(self, animated: bool = True) -> Tuple[List[pygame.Surface], List[float]]:
        self._ensure_title_logo_assets()
        if animated and self._title_logo_frames:
            durations = self._title_logo_durations or [0.1] * len(self._title_logo_frames)
            return [frame.copy() for frame in self._title_logo_frames], list(durations)

        if self._title_logo_static is not None:
            return [self._title_logo_static.copy()], [0.2]

        if self._title_logo_frames:
            durations = self._title_logo_durations or [0.1] * len(self._title_logo_frames)
            return [frame.copy() for frame in self._title_logo_frames], list(durations)

        fallback_surface = pygame.Surface((420, 160), pygame.SRCALPHA)
        draw_center_text(fallback_surface, pygame.font.SysFont(FONT_NAME, 36, bold=True), TITLE, fallback_surface.get_height() // 2, WHITE)
        return [fallback_surface], [0.2]

    def _create_portal_circle(self, world: int) -> pygame.Surface:
        size = 96
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        radius = center

        base_color = BG_COLORS[world - 1]
        accent = ENEMY_COLORS[(world - 1) % len(ENEMY_COLORS)]
        glow = (
            min(255, base_color[0] + 60),
            min(255, base_color[1] + 60),
            min(255, base_color[2] + 60),
        )

        for r in range(radius, 0, -1):
            t = r / radius
            lerp = 1.0 - t
            color = (
                int(base_color[0] * t + accent[0] * lerp),
                int(base_color[1] * t + accent[1] * lerp),
                int(base_color[2] * t + accent[2] * lerp),
                int(255 * (t ** 1.2)),
            )
            pygame.draw.circle(surface, color, (center, center), r)

        pygame.draw.circle(surface, (*glow, 180), (center, center), int(radius * 0.86), width=6)
        pygame.draw.circle(surface, (255, 255, 255, 200), (center, center), int(radius * 0.65), width=2)
        pygame.draw.circle(surface, (255, 255, 255, 80), (center, center), int(radius * 0.95), width=1)

        inner = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(inner, (20, 24, 48, 180), (center, center), int(radius * 0.55))
        surface.blit(inner, (0, 0))

        return surface


# ---------------------------------------------------------------------------
# Sound management
# ---------------------------------------------------------------------------

DEFAULT_SFX_EVENTS: Dict[str, Tuple[str, ...]] = {
    "player_jump": ("player_jump.wav",),
    "player_land": ("player_land.wav",),
    "player_hurt": ("player_hurt.wav",),
    "player_death": ("player_death.wav",),
    "player_respawn": ("player_respawn.wav",),
    "coin_pickup": ("coin_pickup.wav",),
    "quicksand": ("quicksand.wav",),
    "hazard_hit": ("hazard_hit.wav",),
    "checkpoint": ("checkpoint.wav",),
    "portal_unlock": ("portal_unlock.wav",),
    "level_complete": ("level_complete.wav",),
    "menu_move": ("menu_move.flac",),
    "menu_confirm": ("menu_confirm.wav",),
    "boss_roar": ("boss_roar.wav",),
    "boss_hit": ("boss_hit.wav",),
    "boss_defeat": ("boss_defeat.wav",),
    "projectile_fire": ("projectile_fire.wav",),
    "projectile_hit": ("projectile_hit.ogg",),
    "world_transition": ("world_transition.wav",),
    "glitch": ("glitch_effect.wav",),
    # Cutscene SFX
    "collapse_explosion": ("collapse_explosion.wav",),
    "collapse_boom": ("collapse_boom.wav",),
}


class SoundManager:
    """Centralised sound-effect loader and dispatcher that honours player settings."""

    def __init__(self, settings: SettingsManager):
        self.settings = settings
        self._cache: Dict[str, Optional[pygame.mixer.Sound]] = {}
        self._missing: Set[str] = set()
        # Remove wind and rumble events from SFX event map
        self._event_map: Dict[str, Tuple[str, ...]] = {k: v for k, v in DEFAULT_SFX_EVENTS.items() if k not in ("collapse_rumble", "collapse_wind")}
        # Preload all SFX at startup
        for files in self._event_map.values():
            for sound_file in files:
                self._load(sound_file)

    def register_event(self, event: str, *sound_files: str) -> None:
        if sound_files:
            self._event_map[event] = tuple(sound_files)

    def play(self, sound_file: str, *, volume: float = 1.0, loops: int = 0) -> None:
        if not self._should_play():
            return
        sound = self._load(sound_file)
        if sound is None:
            return
        volume = max(0.0, min(volume, 1.0))
        previous = sound.get_volume()
        try:
            sound.set_volume(volume)
            sound.play(loops=loops)
        except Exception as exc:
            print(f"[SFX] Failed to play {sound_file}: {exc}")
        finally:
            sound.set_volume(previous)

    def play_event(self, event: str, *, volume: float = 1.0, loops: int = 0) -> None:
        if not self._should_play():
            return
        candidates = self._event_map.get(event)
        if not candidates:
            candidates = (event,)
        names = list(candidates)
        if len(names) > 1:
            random.shuffle(names)
        for name in names:
            sound = self._load(name)
            if sound is None:
                continue
            volume = max(0.0, min(volume, 1.0))
            previous = sound.get_volume()
            try:
                sound.set_volume(volume)
                sound.play(loops=loops)
            except Exception as exc:
                print(f"[SFX] Failed to play {name}: {exc}")
            finally:
                sound.set_volume(previous)
            break

    def stop_all(self) -> None:
        if pygame.mixer.get_init():
            pygame.mixer.stop()

    def _should_play(self) -> bool:
        return self.settings["sfx"] and pygame.mixer.get_init()

    def _load(self, sound_file: str) -> Optional[pygame.mixer.Sound]:
        cached = self._cache.get(sound_file)
        if cached is not None:
            return cached
        if sound_file in self._missing:
            return None
        path = SOUND_DIR / sound_file
        if not path.exists():
            self._missing.add(sound_file)
            return None
        try:
            sound = pygame.mixer.Sound(path.resolve().as_posix())
        except Exception as exc:
            print(f"[SFX] Failed to load {path}: {exc}")
            sound = None
        self._cache[sound_file] = sound
        if sound is None:
            self._missing.add(sound_file)
        return sound


# ---------------------------------------------------------------------------
# GIF helper
# ---------------------------------------------------------------------------


# === FX helpers / transitions ===
def load_gif_frames(path: Path) -> Tuple[List[pygame.Surface], List[float]]:
    frames: List[pygame.Surface] = []
    durations: List[float] = []
    
    if Image is None or ImageSequence is None:
        print("[Assets] PIL/Pillow not available - GIF loading disabled")
        return frames, durations
    
    if not path.exists():
        print(f"[Assets] GIF file not found: {path}")
        return frames, durations
        
    try:
        with Image.open(str(path.resolve())) as gif:
            palette = gif.getpalette()
            for raw_frame in ImageSequence.Iterator(gif):
                frame_palette = getattr(raw_frame, "palette", None)
                if palette and frame_palette is None:
                    raw_frame.putpalette(palette)

                rgba_frame = raw_frame.convert("RGBA")
                data = rgba_frame.tobytes()
                surface = pygame.image.frombuffer(data, rgba_frame.size, "RGBA").convert_alpha()
                frames.append(surface.copy())

                duration_ms = raw_frame.info.get("duration", gif.info.get("duration", 100))
                durations.append(max(10, duration_ms) / 1000.0)
                
    except (OSError, IOError) as exc:
        print(f"[Assets] Failed to open GIF file {path}: {exc}")
        return [], []
    except Exception as exc:
        print(f"[Assets] Error processing GIF {path}: {exc}")
        return [], []
        
    if not frames:
        print(f"[Assets] No valid frames found in GIF: {path}")
        return [], []
        
    return frames, durations


# ---------------------------------------------------------------------------
# Rendering helpers and glitch effects
# ---------------------------------------------------------------------------


def format_time(seconds: float) -> str:
    total_ms = int(seconds * 1000)
    minutes = total_ms // 60000
    secs = (total_ms // 1000) % 60
    millis = total_ms % 1000
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def glitch_flash(screen: pygame.Surface, clock: pygame.time.Clock, duration: float, enabled: bool) -> None:
    if not enabled:
        return
    start = time.time()
    while time.time() - start < duration:
        screen.fill((random.randint(0, 255), 0, random.randint(0, 255)))
        pygame.display.flip()
        clock.tick(FPS)


def fade_screen(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    to_black: bool = True,
    duration: float = 0.5,
) -> None:
    overlay = pygame.Surface(SCREEN_SIZE)
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed >= duration:
            break
        alpha = int(255 * (elapsed / duration))
        if not to_black:
            alpha = 255 - alpha
        overlay.fill((0, 0, 0))
        overlay.set_alpha(alpha)
        screen.blit(overlay, (0, 0))
        pygame.display.flip()
        clock.tick(FPS)


def apply_stacked_glitch(surface: pygame.Surface, started: float, duration: float = 1.0) -> bool:
    if time.time() - started > duration:
        return False

    if random.random() < 0.3:
        arr = pygame.surfarray.pixels3d(surface)
        arr[:] = 255 - arr[:]
        del arr

    if random.random() < 0.4:
        offset = random.randint(2, 6)
        layers = [surface.copy() for _ in range(3)]
        surface.blit(layers[0], (-offset, 0))
        surface.blit(layers[1], (offset, 0))
        surface.blit(layers[2], (0, offset))

    if random.random() < 0.8:
        noise = pygame.Surface(SCREEN_SIZE)
        for _ in range(2000):
            noise.set_at(
                (random.randint(0, SCREEN_WIDTH - 1), random.randint(0, SCREEN_HEIGHT - 1)),
                (random.randint(150, 255), random.randint(150, 255), random.randint(150, 255)),
            )
        surface.blit(noise, (0, 0), special_flags=pygame.BLEND_ADD)

    if random.random() < 0.6:
        crack_surface = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        for _ in range(10):
            color = random.choice(
                [
                    (255, 0, 180, 220),
                    (0, 255, 240, 220),
                    (255, 120, 0, 220),
                    (180, 0, 255, 220),
                ]
            )
            start = (
                random.randint(0, SCREEN_WIDTH - 1),
                random.randint(0, SCREEN_HEIGHT - 1),
            )
            points = [start]
            segments = random.randint(4, 7)
            for _ in range(segments):
                last = points[-1]
                next_point = (
                    int(max(0, min(SCREEN_WIDTH - 1, last[0] + random.randint(-60, 60)))),
                    int(max(0, min(SCREEN_HEIGHT - 1, last[1] + random.randint(-45, 45)))),
                )
                points.append(next_point)
            pygame.draw.lines(crack_surface, color, False, points, random.randint(2, 4))
            if random.random() < 0.4:
                glow = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                pygame.draw.lines(glow, (*color[:3], 120), False, points, 10)
                crack_surface.blit(glow, (0, 0))
        surface.blit(crack_surface, (0, 0), special_flags=pygame.BLEND_ADD)



# ---------------------------------------------------------------------------
# Color wheel helper
# ---------------------------------------------------------------------------
COLOR_WHEEL_RADIUS = 140
def generate_color_wheel(radius: int = COLOR_WHEEL_RADIUS) -> pygame.Surface:
    diameter = radius * 2
    surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    for y in range(diameter):
        for x in range(diameter):
            dx = x - radius
            dy = y - radius
            dist = math.hypot(dx, dy)
            if dist > radius:
                continue
            angle = math.atan2(-dy, dx) % math.tau
            hue = angle / math.tau
            saturation = min(1.0, dist / radius)
            r, g, b = colorsys.hsv_to_rgb(hue, saturation, 1.0)
            surface.set_at((x, y), (int(r * 255), int(g * 255), int(b * 255), 255))
    return surface


class ColorWheelScene(Scene):

    def __init__(self, game):
        super().__init__(game)
        self.wheel_surface: Optional[pygame.Surface] = None
        self.wheel_rect: Optional[pygame.Rect] = None
        self.selection_pos: Optional[Tuple[int, int]] = None
        self.selected_color: Tuple[int, int, int] = self.game.player_color
        self.dragging = False
        self.confirm_rect = pygame.Rect(0, 0, 220, 56)
        self.back_rect = pygame.Rect(0, 0, 180, 48)
        self.hovered_button = None

    def on_enter(self) -> None:
        # Stop any previous music (including title theme) before playing world music
        self.game.stop_music()
        self.game.pause_speedrun(False)
        # Only call _refresh_world if it exists
        if hasattr(self, '_refresh_world'):
            self._refresh_world()
        self.wheel_surface = generate_color_wheel(COLOR_WHEEL_RADIUS)
        wheel_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)
        self.wheel_rect = self.wheel_surface.get_rect(center=wheel_center)
        self.selection_pos = self._pos_from_color(self.selected_color)
        self.confirm_rect.center = (SCREEN_WIDTH // 2 + 180, SCREEN_HEIGHT - 110)
        self.back_rect.center = (SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT - 110)
        self.dragging = False
        self.hovered_button = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.game.sound.play_event("menu_confirm")
                self.game.change_scene("TitleScene")
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._finalize_selection()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.confirm_rect.collidepoint(event.pos):
                self._finalize_selection()
                return
            if self.back_rect.collidepoint(event.pos):
                self.game.sound.play_event("menu_confirm")
                self.game.change_scene("TitleScene")
                return
            if self._update_selection(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            # Button hover effect
            if self.confirm_rect.collidepoint(event.pos):
                self.hovered_button = "confirm"
            elif self.back_rect.collidepoint(event.pos):
                self.hovered_button = "back"
            else:
                self.hovered_button = None
            if self.dragging:
                self._update_selection(event.pos)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((18, 18, 38))
        title_font = self.game.assets.font(54, True)
        draw_glitch_text(
            surface,
            title_font,
            "CHOOSE YOUR COLOR",
            90,
            WHITE,
            self.game.settings["glitch_fx"],
        )

        # Draw color wheel
        if self.wheel_surface and self.wheel_rect:
            surface.blit(self.wheel_surface, self.wheel_rect)
            if self.selection_pos:
                pygame.draw.circle(surface, WHITE, self.selection_pos, 12, width=4)
                pygame.draw.circle(surface, BLACK, self.selection_pos, 18, width=2)

        # Color preview
        preview_rect = pygame.Rect(0, 0, 180, 180)
        preview_rect.center = (SCREEN_WIDTH // 2 + 180, SCREEN_HEIGHT // 2 - 40)
        pygame.draw.rect(surface, (40, 40, 60), preview_rect, border_radius=18)
        pygame.draw.rect(surface, self.selected_color, preview_rect.inflate(-32, -32), border_radius=16)
        pygame.draw.rect(surface, WHITE, preview_rect, width=3, border_radius=18)

        info_font = self.game.assets.font(22, False)
        draw_prompt_with_icons(
            surface,
            info_font,
            "Click the wheel to select a color.",
            SCREEN_HEIGHT // 2 + 120,
            WHITE,
            device=getattr(self.game, "last_input_device", "mouse"),
        )
        device = getattr(self.game, "last_input_device", "keyboard")
        if device == "controller":
            prompt_text = "Press A to continue, B to return."
        elif device == "mouse":
            prompt_text = "Click Continue or Back to return."
        else:
            prompt_text = "Press ENTER or Continue to start, ESC or Back to return."
        draw_prompt_with_icons(
            surface,
            info_font,
            prompt_text,
            SCREEN_HEIGHT // 2 + 150,
            WHITE,
            device=device,
        )

        # Draw buttons with hover effect
        self._draw_button(surface, self.confirm_rect, "Continue", self.hovered_button == "confirm")
        self._draw_button(surface, self.back_rect, "Back", self.hovered_button == "back")

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, label: str, highlighted: bool) -> None:
        base_color = (120, 180, 255) if highlighted else (80, 80, 120)
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if hover:
            base_color = tuple(min(255, c + 40) for c in base_color)
        pygame.draw.rect(surface, base_color, rect, border_radius=14)
        pygame.draw.rect(surface, WHITE, rect, width=3, border_radius=14)
        font = self.game.assets.font(28, True)
        text = font.render(label, True, WHITE)
        surface.blit(text, text.get_rect(center=rect.center))

    def _finalize_selection(self) -> None:
        self.game.sound.play_event("menu_confirm")
        self.game.player_color = self.selected_color
        self.game.world1_intro_shown = False
        self.game.progress.reset()
        self.game.start_speedrun()
        from main import GameplayScene
        self.game.change_scene(GameplayScene, world=1, level=1)

    def _update_selection(self, pos: Tuple[int, int]) -> bool:
        if not self.wheel_rect or not self.wheel_surface:
            return False
        local = (pos[0] - self.wheel_rect.left, pos[1] - self.wheel_rect.top)
        radius = COLOR_WHEEL_RADIUS
        dx = local[0] - radius
        dy = local[1] - radius
        if math.hypot(dx, dy) > radius:
            return False
        try:
            color = self.wheel_surface.get_at((int(local[0]), int(local[1])))[:3]
        except IndexError:
            return False
        self.selected_color = color
        self.selection_pos = (self.wheel_rect.left + int(local[0]),
                              self.wheel_rect.top + int(local[1]))
        return True

    def _pos_from_color(self, color: Tuple[int, int, int]) -> Tuple[int, int]:
        if not self.wheel_rect:
            return (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)
        r, g, b = [c / 255.0 for c in color]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        angle = h * math.tau
        distance = min(1.0, max(0.0, s)) * COLOR_WHEEL_RADIUS
        local_x = COLOR_WHEEL_RADIUS + int(math.cos(angle) * distance)
        local_y = COLOR_WHEEL_RADIUS - int(math.sin(angle) * distance)
        return (self.wheel_rect.left + local_x, self.wheel_rect.top + local_y)



def apply_dynamic_glitch(surface: pygame.Surface, strength: float) -> None:
    strength = max(0.2, min(strength, 2.0))
    tear_count = max(3, int(4 * strength))
    max_shift = int(12 * strength)
    max_height = int(25 + 80 * strength)

    for _ in range(tear_count):
        h = random.randint(8, max_height)
        y = random.randint(0, max(0, SCREEN_HEIGHT - h))
        shift = random.randint(-max_shift, max_shift)

        slice_rect = pygame.Rect(0, y, SCREEN_WIDTH, h)
        slice_copy = surface.subsurface(slice_rect).copy()
        surface.blit(slice_copy, (shift, y))

        overlay = pygame.Surface((SCREEN_WIDTH, h), pygame.SRCALPHA)
        color = random.choice(
            [
                (255, 0, 160, 110),
                (0, 220, 255, 110),
                (255, 180, 0, 90),
                (180, 0, 255, 90),
                (0, 255, 128, 90),
            ]
        )
        overlay.fill(color)
        surface.blit(overlay, (0, y), special_flags=pygame.BLEND_RGBA_ADD)

    noise = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
    for _ in range(int(600 * strength)):
        nx = random.randint(0, SCREEN_WIDTH - 1)
        ny = random.randint(0, SCREEN_HEIGHT - 1)
        noise.set_at((nx, ny), random.choice([(255, 0, 220, 120), (0, 255, 230, 90), (255, 200, 0, 100)]))
    surface.blit(noise, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)





# --- Unique World Transition Cutscenes ---
def play_world_transition(game: "Game", from_world: int, to_world: int) -> None:
    # Route to unique cutscene for each world transition (except 9->10 and final)
    if from_world == 1 and to_world == 2:
        play_transition_1_to_2(game)
    elif from_world == 2 and to_world == 3:
        play_transition_2_to_3(game)
    elif from_world == 3 and to_world == 4:
        play_transition_3_to_4(game)
    elif from_world == 4 and to_world == 5:
        play_transition_4_to_5(game)
    elif from_world == 5 and to_world == 6:
        play_transition_5_to_6(game)
    elif from_world == 6 and to_world == 7:
        play_transition_6_to_7(game)
    elif from_world == 7 and to_world == 8:
        play_transition_7_to_8(game)
    elif from_world == 8 and to_world == 9:
        play_transition_8_to_9(game)
    elif from_world == 9 and to_world == 10:
        # Special glitch portal cutscene handled elsewhere
        pass
    else:
        # Fallback: original transition
        play_default_world_transition(game, from_world, to_world)


def play_default_world_transition(game: "Game", from_world: int, to_world: int) -> None:
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    new_color = BG_COLORS[min(to_world - 1, len(BG_COLORS) - 1)]
    title_font = game.assets.font(44, True)
    subtitle_font = game.assets.font(24, False)
    subtitle = TOWER_NAMES[to_world - 1] if 1 <= to_world <= len(TOWER_NAMES) else ""
    start = time.time()
    duration = 2.6
    half = duration / 2
    while game.running and time.time() - start < duration:
        elapsed = time.time() - start
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                game.pause_speedrun(False)
                return
        game.screen.fill((0, 0, 0))
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.fill(new_color)
        overlay.set_alpha(120)
        game.screen.blit(overlay, (0, 0))
        if elapsed < half:
            alpha = int(min(1.0, elapsed / (half * 0.7)) * 255)
            text = f"World {from_world} Complete"
            render = title_font.render(text, True, WHITE)
            render.set_alpha(alpha)
            game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20)))
        else:
            alpha = int(min(1.0, (elapsed - half) / (half * 0.7)) * 255)
            text = f"Entering World {to_world}"
            render = title_font.render(text, True, WHITE)
            render.set_alpha(alpha)
            game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20)))
            if subtitle:
                sub = subtitle_font.render(subtitle, True, WHITE)
                sub.set_alpha(alpha)
                game.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30)))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

# --- Unique cutscene implementations ---
def play_transition_1_to_2(game):
    # Forest to Stone: vines recede, stone rises
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    bg1 = game.assets.background(1)
    bg2 = game.assets.background(2)
    font = game.assets.font(44, True)
    start = time.time()
    duration = 4.5  # Longer duration
    extra_fx_time = 1.2  # Extra time for dramatic effects
    vines_color = (60, 180, 80)
    stone_color = (120, 120, 140)
    while game.running and time.time() - start < duration + extra_fx_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
        elapsed = time.time() - start
        t = min(1.0, elapsed / duration)
        # Blend backgrounds
        game.screen.blit(bg1, (0, 0))
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.blit(bg2, (0, int((1-t)*SCREEN_HEIGHT)))
        overlay.set_alpha(int(180 * t))
        game.screen.blit(overlay, (0, 0))
        # Animate vines receding (green rectangles, now animated with sway)
        for i in range(8):
            y = int(SCREEN_HEIGHT * (i+1) / 9)
            width = int(SCREEN_WIDTH * (1-t))
            sway = int(10 * math.sin(elapsed * 2 + i))
            pygame.draw.rect(game.screen, vines_color, (0, y + sway, width, 8))
        # Stone rises with shake
        for i in range(6):
            x = int(SCREEN_WIDTH * (i+1) / 7)
            height = int(SCREEN_HEIGHT * t)
            shake = int(4 * math.sin(elapsed * 3 + i))
            pygame.draw.rect(game.screen, stone_color, (x + shake, SCREEN_HEIGHT-height, 16, height))
        # Dramatic flash as stone emerges
        if t > 0.85:
            flash_alpha = int(180 * (t-0.85)/0.15)
            if flash_alpha > 0:
                flash = pygame.Surface(SCREEN_SIZE)
                flash.fill((255,255,255))
                flash.set_alpha(min(255, flash_alpha))
                game.screen.blit(flash, (0,0))
        # Text
        alpha = int(255 * t)
        text = "The forest recedes..."
        render = font.render(text, True, WHITE)
        render.set_alpha(alpha)
        game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH//2, 120)))
        text2 = "Stone towers emerge."
        render2 = font.render(text2, True, WHITE)
        render2.set_alpha(alpha)
        game.screen.blit(render2, render2.get_rect(center=(SCREEN_WIDTH//2, 180)))
        # Extra dramatic pause and shimmer after transition
        if elapsed > duration:
            shimmer_alpha = int(120 * (1 - (elapsed-duration)/extra_fx_time))
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(30):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (200,255,200,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

def play_transition_2_to_3(game):
    # Stone to Sand: stone cracks, sand blows in
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    bg1 = game.assets.background(2)
    bg2 = game.assets.background(3)
    font = game.assets.font(44, True)
    start = time.time()
    duration = 4.5
    extra_fx_time = 1.2
    while game.running and time.time() - start < duration + extra_fx_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
        elapsed = time.time() - start
        t = min(1.0, elapsed / duration)
        game.screen.blit(bg1, (0, 0))
        # Cracks animate with jitter
        for i in range(8):
            x = int(SCREEN_WIDTH * (i+1) / 9)
            y1 = int(SCREEN_HEIGHT * 0.3)
            y2 = int(SCREEN_HEIGHT * (0.3 + 0.4 * t))
            jitter = int(4 * math.sin(elapsed * 3 + i))
            pygame.draw.line(game.screen, (180, 180, 180), (x + jitter, y1), (x + jitter, y2), 2)
        # Sand overlay
        sand_overlay = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        sand_overlay.fill((220, 200, 120, int(120 * t)))
        game.screen.blit(sand_overlay, (0, 0))
        # Sand blows in (more, with wind effect)
        for i in range(80):
            sx = int(random.uniform(0, SCREEN_WIDTH))
            sy = int(SCREEN_HEIGHT * (1-t) + random.uniform(-30, 30))
            wind = int(20 * math.sin(elapsed * 2 + i))
            pygame.draw.circle(game.screen, (230, 210, 140), (sx + wind, sy), random.randint(2, 5))
        # Fade in new bg
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.blit(bg2, (0, 0))
        overlay.set_alpha(int(180 * t))
        game.screen.blit(overlay, (0, 0))
        # Dramatic sand shimmer at end
        if t > 0.85:
            shimmer_alpha = int(120 * (t-0.85)/0.15)
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(40):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (255,255,200,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        # Text
        alpha = int(255 * t)
        text = "Stone crumbles..."
        render = font.render(text, True, WHITE)
        render.set_alpha(alpha)
        game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH//2, 120)))
        text2 = "Sand sweeps in."
        render2 = font.render(text2, True, WHITE)
        render2.set_alpha(alpha)
        game.screen.blit(render2, render2.get_rect(center=(SCREEN_WIDTH//2, 180)))
        # Extra dramatic pause and shimmer after transition
        if elapsed > duration:
            shimmer_alpha = int(120 * (1 - (elapsed-duration)/extra_fx_time))
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(30):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (255,255,200,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

def play_transition_3_to_4(game):
    # Sand to Nature: sandstorm fades, mushrooms/thorns grow
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    bg1 = game.assets.background(3)
    bg2 = game.assets.background(4)
    font = game.assets.font(44, True)
    start = time.time()
    duration = 4.5
    extra_fx_time = 1.2
    while game.running and time.time() - start < duration + extra_fx_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
        elapsed = time.time() - start
        t = min(1.0, elapsed / duration)
        game.screen.blit(bg1, (0, 0))
        # Sandstorm swirls
        for i in range(80):
            sx = int(random.uniform(0, SCREEN_WIDTH))
            sy = int(random.uniform(0, SCREEN_HEIGHT))
            swirl = int(10 * math.sin(elapsed * 2 + i))
            alpha = int(80 * (1-t))
            pygame.draw.circle(game.screen, (230, 210, 140, alpha), (sx + swirl, sy), random.randint(2, 6))
        # Mushrooms/thorns grow, animated
        for i in range(16):
            base_x = int(SCREEN_WIDTH * (i+1) / 17)
            grow = math.sin(elapsed * 2 + i) * 0.1 + 1.0
            h = int(SCREEN_HEIGHT * t * random.uniform(0.2, 0.5) * grow)
            pygame.draw.rect(game.screen, (120, 200, 120), (base_x, SCREEN_HEIGHT-h, 12, h))
            pygame.draw.ellipse(game.screen, (180, 80, 180), (base_x-8, SCREEN_HEIGHT-h-16, 28, 20))
        # Fade in new bg
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.blit(bg2, (0, 0))
        overlay.set_alpha(int(180 * t))
        game.screen.blit(overlay, (0, 0))
        # Dramatic nature shimmer at end
        if t > 0.85:
            shimmer_alpha = int(120 * (t-0.85)/0.15)
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(40):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (180,255,180,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        # Text
        alpha = int(255 * t)
        text = "Sandstorm fades..."
        render = font.render(text, True, WHITE)
        render.set_alpha(alpha)
        game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH//2, 120)))
        text2 = "Nature reclaims the land."
        render2 = font.render(text2, True, WHITE)
        render2.set_alpha(alpha)
        game.screen.blit(render2, render2.get_rect(center=(SCREEN_WIDTH//2, 180)))
        # Extra dramatic pause and shimmer after transition
        if elapsed > duration:
            shimmer_alpha = int(120 * (1 - (elapsed-duration)/extra_fx_time))
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(30):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (180,255,180,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

def play_transition_4_to_5(game):
    # Nature to Frost: frost creeps in, snow falls
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    bg1 = game.assets.background(4)
    bg2 = game.assets.background(5)
    font = game.assets.font(44, True)
    start = time.time()
    duration = 4.5
    extra_fx_time = 1.2
    while game.running and time.time() - start < duration + extra_fx_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
        elapsed = time.time() - start
        t = min(1.0, elapsed / duration)
        game.screen.blit(bg1, (0, 0))
        # Frost overlay creeps in from edges
        frost = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        frost_alpha = int(120 * t)
        for i in range(0, SCREEN_WIDTH, 40):
            pygame.draw.rect(frost, (180, 220, 255, frost_alpha), (i, 0, 40, int(SCREEN_HEIGHT * t)))
        game.screen.blit(frost, (0, 0))
        # Snow (more, animated)
        for i in range(120):
            sx = int(random.uniform(0, SCREEN_WIDTH))
            sy = int((random.uniform(0, SCREEN_HEIGHT) + elapsed * 60) % SCREEN_HEIGHT)
            pygame.draw.circle(game.screen, (255, 255, 255), (sx, sy), random.randint(2, 5))
        # Fade in new bg
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.blit(bg2, (0, 0))
        overlay.set_alpha(int(180 * t))
        game.screen.blit(overlay, (0, 0))
        # Dramatic frost shimmer at end
        if t > 0.85:
            shimmer_alpha = int(120 * (t-0.85)/0.15)
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(40):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (200,255,255,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        # Text
        alpha = int(255 * t)
        text = "Nature freezes..."
        render = font.render(text, True, WHITE)
        render.set_alpha(alpha)
        game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH//2, 120)))
        text2 = "Frost covers the land."
        render2 = font.render(text2, True, WHITE)
        render2.set_alpha(alpha)
        game.screen.blit(render2, render2.get_rect(center=(SCREEN_WIDTH//2, 180)))
        # Extra dramatic pause and shimmer after transition
        if elapsed > duration:
            shimmer_alpha = int(120 * (1 - (elapsed-duration)/extra_fx_time))
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(30):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (200,255,255,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

def play_transition_5_to_6(game):
    # Frost to Flame: ice cracks, fire spreads
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    bg1 = game.assets.background(5)
    bg2 = game.assets.background(6)
    font = game.assets.font(44, True)
    start = time.time()
    duration = 4.5
    extra_fx_time = 1.2
    while game.running and time.time() - start < duration + extra_fx_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
        elapsed = time.time() - start
        t = min(1.0, elapsed / duration)
        game.screen.blit(bg1, (0, 0))
        # Ice cracks animate
        for i in range(14):
            x = int(SCREEN_WIDTH * (i+1) / 15)
            y1 = int(SCREEN_HEIGHT * 0.7)
            y2 = int(SCREEN_HEIGHT * (0.7 - 0.5 * t))
            shake = int(4 * math.sin(elapsed * 2 + i))
            pygame.draw.line(game.screen, (200, 240, 255), (x + shake, y1), (x + shake, y2), 3)
        # Fire overlay
        fire = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        fire.fill((255, 80, 40, int(120 * t)))
        game.screen.blit(fire, (0, 0))
        # Fire sparks (more, animated)
        for i in range(60):
            sx = int(random.uniform(0, SCREEN_WIDTH))
            sy = int((random.uniform(0, SCREEN_HEIGHT) + elapsed * 80) % SCREEN_HEIGHT)
            pygame.draw.circle(game.screen, (255, 180, 80), (sx, sy), random.randint(2, 4))
        # Fade in new bg
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.blit(bg2, (0, 0))
        overlay.set_alpha(int(180 * t))
        game.screen.blit(overlay, (0, 0))
        # Dramatic fire shimmer at end
        if t > 0.85:
            shimmer_alpha = int(120 * (t-0.85)/0.15)
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(40):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (255,200,100,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        # Text
        alpha = int(255 * t)
        text = "Ice cracks..."
        render = font.render(text, True, WHITE)
        render.set_alpha(alpha)
        game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH//2, 120)))
        text2 = "Flames erupt."
        render2 = font.render(text2, True, WHITE)
        render2.set_alpha(alpha)
        game.screen.blit(render2, render2.get_rect(center=(SCREEN_WIDTH//2, 180)))
        # Extra dramatic pause and shimmer after transition
        if elapsed > duration:
            shimmer_alpha = int(120 * (1 - (elapsed-duration)/extra_fx_time))
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(30):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (255,200,100,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

def play_transition_6_to_7(game):
    # Flame to Air: smoke rises, wind blows
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    bg1 = game.assets.background(6)
    bg2 = game.assets.background(7)
    font = game.assets.font(44, True)
    start = time.time()
    duration = 4.5
    extra_fx_time = 1.2
    while game.running and time.time() - start < duration + extra_fx_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
        elapsed = time.time() - start
        t = min(1.0, elapsed / duration)
        game.screen.blit(bg1, (0, 0))
        # Smoke (more, animated)
        for i in range(80):
            sx = int(random.uniform(0, SCREEN_WIDTH))
            sy = int(SCREEN_HEIGHT * (1-t) + random.uniform(-30, 30))
            drift = int(10 * math.sin(elapsed * 2 + i))
            pygame.draw.circle(game.screen, (120, 120, 120, int(80 * (1-t))), (sx + drift, sy), random.randint(4, 8))
        # Wind overlay (animated)
        wind = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        wind.fill((180, 220, 255, int(80 * t)))
        for i in range(10):
            wx = int(SCREEN_WIDTH * (i+1) / 11)
            wy = int(SCREEN_HEIGHT * 0.5 + 40 * math.sin(elapsed * 2 + i))
            pygame.draw.line(wind, (200, 240, 255, 80), (wx, wy), (wx, wy+80), 4)
        game.screen.blit(wind, (0, 0))
        # Fade in new bg
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.blit(bg2, (0, 0))
        overlay.set_alpha(int(180 * t))
        game.screen.blit(overlay, (0, 0))
        # Dramatic wind shimmer at end
        if t > 0.85:
            shimmer_alpha = int(120 * (t-0.85)/0.15)
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(40):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (200,240,255,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        # Text
        alpha = int(255 * t)
        text = "Flames die out..."
        render = font.render(text, True, WHITE)
        render.set_alpha(alpha)
        game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH//2, 120)))
        text2 = "Winds howl."
        render2 = font.render(text2, True, WHITE)
        render2.set_alpha(alpha)
        game.screen.blit(render2, render2.get_rect(center=(SCREEN_WIDTH//2, 180)))
        # Extra dramatic pause and shimmer after transition
        if elapsed > duration:
            shimmer_alpha = int(120 * (1 - (elapsed-duration)/extra_fx_time))
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(30):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (200,240,255,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

def play_transition_7_to_8(game):
    # Air to Circuits: wind fades, electric arcs
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    bg1 = game.assets.background(7)
    bg2 = game.assets.background(8)
    font = game.assets.font(44, True)
    start = time.time()
    duration = 4.5
    extra_fx_time = 1.2
    while game.running and time.time() - start < duration + extra_fx_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
        elapsed = time.time() - start
        t = min(1.0, elapsed / duration)
        game.screen.blit(bg1, (0, 0))
        # Wind lines fade and animate
        for i in range(16):
            x1 = int(SCREEN_WIDTH * (i+1) / 17)
            y1 = int(SCREEN_HEIGHT * 0.2 + 20 * math.sin(elapsed * 2 + i))
            y2 = int(SCREEN_HEIGHT * (0.2 + 0.5 * (1-t)))
            pygame.draw.line(game.screen, (180, 220, 255), (x1, y1), (x1, y2), 3)
        # Electric arcs (more, animated)
        for i in range(14):
            points = [(int(SCREEN_WIDTH * (i+1) / 15), int(SCREEN_HEIGHT * 0.7))]
            for _ in range(6):
                last = points[-1]
                points.append((last[0] + random.randint(-20, 20), last[1] - random.randint(10, 30)))
            pygame.draw.lines(game.screen, (80, 200, 255), False, points, 2)
        # Fade in new bg
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.blit(bg2, (0, 0))
        overlay.set_alpha(int(180 * t))
        game.screen.blit(overlay, (0, 0))
        # Dramatic electric shimmer at end
        if t > 0.85:
            shimmer_alpha = int(120 * (t-0.85)/0.15)
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(40):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (80,200,255,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        # Text
        alpha = int(255 * t)
        text = "Winds subside..."
        render = font.render(text, True, WHITE)
        render.set_alpha(alpha)
        game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH//2, 120)))
        text2 = "Electricity surges."
        render2 = font.render(text2, True, WHITE)
        render2.set_alpha(alpha)
        game.screen.blit(render2, render2.get_rect(center=(SCREEN_WIDTH//2, 180)))
        # Extra dramatic pause and shimmer after transition
        if elapsed > duration:
            shimmer_alpha = int(120 * (1 - (elapsed-duration)/extra_fx_time))
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(30):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (80,200,255,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

def play_transition_8_to_9(game):
    # Circuits to Echoes: electric fades, ghostly wisps
    game.pause_speedrun(True)
    game.stop_music()
    game.sound.play_event("world_transition")
    bg1 = game.assets.background(8)
    bg2 = game.assets.background(9)
    font = game.assets.font(44, True)
    start = time.time()
    duration = 4.5
    extra_fx_time = 1.2
    while game.running and time.time() - start < duration + extra_fx_time:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
        elapsed = time.time() - start
        t = min(1.0, elapsed / duration)
        game.screen.blit(bg1, (0, 0))
        # Electric sparks fade and animate
        for i in range(40):
            sx = int(random.uniform(0, SCREEN_WIDTH))
            sy = int(random.uniform(0, SCREEN_HEIGHT))
            flicker = int(8 * math.sin(elapsed * 3 + i))
            alpha = int(180 * (1-t))
            pygame.draw.circle(game.screen, (80, 200, 255, alpha), (sx + flicker, sy), random.randint(2, 5))
        # Ghostly wisps (more, animated)
        for i in range(18):
            base_x = int(SCREEN_WIDTH * (i+1) / 19)
            y = int(SCREEN_HEIGHT * (0.2 + 0.6 * t * random.random()))
            drift = int(10 * math.sin(elapsed * 2 + i))
            pygame.draw.ellipse(game.screen, (200, 200, 255, 80), (base_x-20 + drift, y, 40, 16))
        # Fade in new bg
        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.blit(bg2, (0, 0))
        overlay.set_alpha(int(180 * t))
        game.screen.blit(overlay, (0, 0))
        # Dramatic ghost shimmer at end
        if t > 0.85:
            shimmer_alpha = int(120 * (t-0.85)/0.15)
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(40):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (200,200,255,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        # Text
        alpha = int(255 * t)
        text = "Electricity fades..."
        render = font.render(text, True, WHITE)
        render.set_alpha(alpha)
        game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH//2, 120)))
        text2 = "Ghostly echoes appear."
        render2 = font.render(text2, True, WHITE)
        render2.set_alpha(alpha)
        game.screen.blit(render2, render2.get_rect(center=(SCREEN_WIDTH//2, 180)))
        # Extra dramatic pause and shimmer after transition
        if elapsed > duration:
            shimmer_alpha = int(120 * (1 - (elapsed-duration)/extra_fx_time))
            if shimmer_alpha > 0:
                shimmer = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
                for i in range(30):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(shimmer, (200,200,255,shimmer_alpha), (x,y), random.randint(2,6))
                game.screen.blit(shimmer, (0,0))
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)


def flash_unlock_message(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    assets: AssetCache,
    text: str,
    sound: Optional["SoundManager"] = None,
) -> None:
    font = assets.font(36, True)
    if sound:
        sound.play_event("portal_unlock")
    for _ in range(60):
        screen.fill((random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
        draw_center_text(screen, font, text, SCREEN_HEIGHT // 2, WHITE)
        pygame.display.flip()
        clock.tick(FPS)


# ---------------------------------------------------------------------------
# Level entities
# ---------------------------------------------------------------------------



# Utility to list available character folders
def list_character_folders():
    char_dir = ASSET_DIR / "characters"
    if not char_dir.exists():
        return []
    return [f.name for f in char_dir.iterdir() if f.is_dir()]


# === Entities: player / platforms / enemies / bosses / objects ===
class Player(pygame.sprite.Sprite):
    def __init__(
        self,
        spawn: Tuple[int, int],
        sound: Optional["SoundManager"] = None,
        color: Optional[Tuple[int, int, int]] = None,
        character_name: str = "player",
        form_name: Optional[str] = None,
    ):
        super().__init__()
        self.spawn = pygame.Vector2(spawn)
        self.character_name = character_name
        self.form_name = form_name
        self.animations = self._load_frames()
        # Only apply color tint if character is 'player'
        if self.character_name == "player" and color:
            self.tint_color: Optional[Tuple[int, int, int]] = color
            self._apply_color_tint(self.tint_color)
        else:
            self.tint_color = None
        self.state = "idle"
        self.prev_state = self.state
        self.frame_index = 0
        self.anim_timer = 0
        self.image = self.animations[self.state][self.frame_index]
        self.rect = self.image.get_rect(topleft=spawn)
        self.velocity = pygame.Vector2(0, 0)
        self.on_ground = False
        self.facing_right = True
        self.accel = 0.6
        self.friction = 0.82
        self.max_speed = 6
        self.jump_speed = -12
        self.base_max_health = 5
        self.gravity = 0.5
        self.max_fall = 10
        self.slow_frames = 0
        self.can_fly = False
        self.fly_speed = 6
        self.max_health = 5
        self.health = self.max_health
        self.invuln_frames = 0
        self.sound = sound
        self._was_on_ground = False
        self.in_quicksand = False  # Track if player is in quicksand

    def _load_frames(self) -> Dict[str, List[pygame.Surface]]:
        # If self.form_name exists, load outfit assets when available, else use character/form folders.
        char_dir = ASSET_DIR / "characters" / self.character_name
        if hasattr(self, "form_name") and self.form_name:
            if self.character_name == "player":
                outfit_dir = ASSET_DIR / "outfits" / self.form_name
                if outfit_dir.exists():
                    char_dir = outfit_dir
                else:
                    char_dir = char_dir / self.form_name
            else:
                char_dir = char_dir / self.form_name
        animations: Dict[str, List[pygame.Surface]] = {}

        # Try new structure: state/frame.png (e.g., idle/0.png)
        if char_dir.exists():
            for state_dir in char_dir.iterdir():
                if not state_dir.is_dir():
                    continue
                state = state_dir.name
                frames = []
                for frame_path in sorted(state_dir.glob("*.png")):
                    try:
                        frame = pygame.image.load(frame_path).convert_alpha()
                        frames.append(frame)
                    except Exception as exc:
                        print(f"[Player] Failed to load frame {frame_path}: {exc}")
                if frames:
                    animations[state] = frames

        # Fallback: try flat structure state_frame.png
        if not animations and char_dir.exists():
            for image_path in sorted(char_dir.glob("*.png")):
                stem = image_path.stem
                if "_" not in stem:
                    continue
                state, _ = stem.split("_", 1)
                try:
                    frame = pygame.image.load(image_path).convert_alpha()
                except Exception as exc:
                    print(f"[Player] Failed to load frame {image_path}: {exc}")
                    continue
                animations.setdefault(state, []).append(frame)

        if not animations:
            # Final fallback: try idle/0.png
            idle_path = char_dir / "idle" / "0.png"
            if idle_path.exists():
                try:
                    frame = pygame.image.load(idle_path).convert_alpha()
                    animations = {"idle": [frame]}
                except Exception as exc:
                    print(f"[Player] Failed to load fallback idle frame {idle_path}: {exc}")
            else:
                fallback = pygame.Surface((36, 48), pygame.SRCALPHA)
                fallback.fill((160, 220, 255))
                animations = {"idle": [fallback]}

        if "idle" not in animations:
            animations["idle"] = animations[next(iter(animations))]

        return animations

    def respawn(self) -> None:
        self.rect.topleft = self.spawn.xy
        self.velocity.xy = (0, 0)
        self.on_ground = False
        self.state = "idle"
        self.prev_state = "idle"
        self.frame_index = 0
        self.anim_timer = 0
        self.image = self.animations.get("idle", [self.image])[0]
        self.health = self.max_health
        self.invuln_frames = 0
        self._was_on_ground = False
        # Ensure flight cheat persists after respawn
        try:
            import main
            if hasattr(main, 'game_instance') and hasattr(main.game_instance, 'flight_cheat_enabled'):
                if main.game_instance.flight_cheat_enabled and hasattr(self, 'enable_flight'):
                    self.enable_flight()
        except Exception:
            pass
        if self.sound:
            self.sound.play_event("player_respawn")

    def enable_flight(self) -> None:
        print("[DEBUG] Player.enable_flight() called")
        if not self.can_fly:
            print("[DEBUG] Player can_fly set to True")
            self.can_fly = True
            self.velocity.y = 0

    def disable_flight(self) -> None:
        """Disable flight if currently enabled."""
        if self.can_fly:
            self.can_fly = False

    def apply_quicksand(self) -> None:
        if self.slow_frames == 0 and self.sound:
            self.sound.play_event("quicksand")
        self.slow_frames = 6
        self.in_quicksand = True


    def take_damage(self, amount: int = 1) -> None:
        if self.invuln_frames > 0:
            return
        self.health = max(0, self.health - amount)
        self.invuln_frames = int(FPS * 0.6)
        if self.sound:
            if self.health <= 0:
                self.sound.play_event("player_death")
            else:
                self.sound.play_event("player_hurt")

    def alive(self) -> bool:
        return self.health > 0

    def update(self, platforms: Iterable[pygame.sprite.Sprite], input_state: Optional["InputState"] = None) -> None:
        controller = input_state or InputState()
        was_on_ground = self.on_ground
        if self.invuln_frames > 0:
            self.invuln_frames -= 1

        horizontal_axis = controller.move_axis
        move_left = controller.move_left or horizontal_axis <= -0.35
        move_right = controller.move_right or horizontal_axis >= 0.35

        if move_left and not move_right:
            self.velocity.x -= self.accel
            self.facing_right = False
        elif move_right and not move_left:
            self.velocity.x += self.accel
            self.facing_right = True
        else:
            self.velocity.x *= self.friction
            if abs(self.velocity.x) < 0.2:
                self.velocity.x = 0

        if self.slow_frames > 0:
            self.velocity.x *= 0.7
            self.slow_frames -= 1
        else:
            # If not in quicksand anymore, stop the quicksand sound
            if self.in_quicksand:
                if self.sound:
                    self.sound.stop_all()  # Stops all sounds, or you can implement a more targeted stop
                self.in_quicksand = False

        self.velocity.x = max(-self.max_speed, min(self.max_speed, self.velocity.x))

        jump_input = controller.jump
        jump_pressed = getattr(controller, "jump_pressed", False)
        down_input = controller.down

        if self.can_fly:
            self.velocity.y = 0
            vertical_axis = controller.vertical_axis
            if controller.up or vertical_axis <= -0.35 or jump_input:
                self.velocity.y = -self.fly_speed
            elif controller.down or vertical_axis >= 0.35 or down_input:
                self.velocity.y = self.fly_speed
        else:
            # Allow jump only from the ground (no mid-air jumps)
            if (jump_pressed or jump_input) and self.on_ground:
                self.velocity.y = self.jump_speed
                self.on_ground = False
                if self.sound:
                    self.sound.play_event("player_jump")
            # No bonus movement skills: only single jump when grounded

            self.velocity.y += self.gravity
            if self.velocity.y > self.max_fall:
                self.velocity.y = self.max_fall

        self.rect.x += int(self.velocity.x)
        for platform in platforms:
            if self.rect.colliderect(platform.rect):
                if self.velocity.x > 0:
                    self.rect.right = platform.rect.left
                elif self.velocity.x < 0:
                    self.rect.left = platform.rect.right
                self.velocity.x = 0

        self.rect.y += int(self.velocity.y)
        self.on_ground = False
        for platform in platforms:
            if self.rect.colliderect(platform.rect):
                if self.velocity.y > 0:
                    self.rect.bottom = platform.rect.top
                    self.velocity.y = 0
                    self.on_ground = True
                elif self.velocity.y < 0:
                    self.rect.top = platform.rect.bottom
                    self.velocity.y = 0

        if self.can_fly:
            if abs(self.velocity.y) > 0.1:
                self.state = "jump" if self.velocity.y < 0 else "fall"
            elif abs(self.velocity.x) > 1:
                self.state = "run"
            else:
                self.state = "idle"
        elif not self.on_ground:
            self.state = "jump" if self.velocity.y < 0 else "fall"
        elif abs(self.velocity.x) > 1:
            self.state = "run"
        else:
            self.state = "idle"

        # If the player has fallen well below the visible play area, restart them at spawn
        # Use a small buffer below the screen so minor off-screen movement
        # doesn't trigger a restart.
        if self.rect.top > SCREEN_HEIGHT + 200:
            # Reset player to spawn point and reset their state (position, velocity, etc)
            if self.sound:
                self.sound.play_event("player_death")
            self.respawn()
            return

        if self.on_ground and not was_on_ground and self.sound:
            self.sound.play_event("player_land")

        self._was_on_ground = self.on_ground

        if self.state != self.prev_state:
            self.prev_state = self.state
            self.frame_index = 0
            self.anim_timer = 0

        self._animate()

    def _animate(self) -> None:
        frames = self.animations.get(self.state, self.animations["idle"])
        self.anim_timer += 1
        speed_lookup = {
            "idle": 12,
            "run": 5,
            "jump": 10,
            "fall": 10,
        }
        base_speed = speed_lookup.get(self.state, 8)
        if self.anim_timer >= base_speed:
            self.anim_timer = 0
            self.frame_index = (self.frame_index + 1) % len(frames)

        frame = frames[self.frame_index]
        if not self.facing_right:
            frame = pygame.transform.flip(frame, True, False)
        self.image = frame

    def _apply_color_tint(self, color: Tuple[int, int, int]) -> None:
        tinted: Dict[str, List[pygame.Surface]] = {}
        for state, frames in self.animations.items():
            tinted_frames: List[pygame.Surface] = []
            for frame in frames:
                tinted_frames.append(self._tint_surface(frame, color))
            tinted[state] = tinted_frames
        self.animations = tinted

    @staticmethod
    def _tint_surface(surface: pygame.Surface, color: Tuple[int, int, int]) -> pygame.Surface:
        tinted = surface.copy()
        tint_overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        r, g, b = color
        tint_overlay.fill((r, g, b, 255))
        tinted.blit(tint_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return tinted


class Platform(pygame.sprite.Sprite):
    def __init__(self, x, y, width=64, height=16, world_num=None, asset_cache=None, *args, **kwargs):
        super().__init__()
        # Set the platform image for this world
        if asset_cache and hasattr(asset_cache, 'platform_texture') and world_num is not None:
            self.image = asset_cache.platform_texture(world_num, (width, height))
        else:
            # fallback: blank surface
            self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.world_num = world_num
        self.asset_cache = asset_cache
        # Ensure all moving platform attributes exist for update()
        self.speed_mod = 1.0
        self.float_y = float(self.rect.y)
        self.base_y = float(self.rect.y)
        self.direction = 1
        self.broken = False
        self.carry_sprites = set()

    def update(self) -> None:
        self.prev_rect = self.rect.copy()
        move_y = 0.0
        move_x = 0.0
        if self.speed_mod != 1.0 and not self.broken:
            self.float_y += self.direction * self.speed_mod
            if self.float_y - self.base_y > 20:
                self.float_y = self.base_y + 20
                self.direction *= -1
            elif self.float_y - self.base_y < -20:
                self.float_y = self.base_y - 20
                self.direction *= -1
            new_y = int(round(self.float_y))
            move_y = new_y - self.rect.y
            self.rect.y = new_y
        else:
            self.float_y = self.rect.y

        self.move_vector = pygame.Vector2(move_x, move_y)
        # Move any sprites that are attached/carried by this platform so they
        # follow platform motion (e.g., spikes placed on moving platforms).
        if (move_x != 0 or move_y != 0) and getattr(self, "carry_sprites", None):
            to_remove = []
            for spr in list(self.carry_sprites):
                try:
                    spr.rect.x += int(move_x)
                    spr.rect.y += int(move_y)
                except Exception:
                    # If sprite is dead or missing rect, schedule removal
                    to_remove.append(spr)
            for spr in to_remove:
                try:
                    self.carry_sprites.discard(spr)
                except Exception:
                    pass


class MovingPlatform(Platform):
    """Platform that oscillates along one axis for more advanced traversal challenges."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        world_num: int,
        asset_cache: AssetCache,
        *,
        horizontal: bool = True,
        amplitude: float = 64.0,
        speed: float = 1.2,
        phase_offset: float = 0.0,
    ):
        super().__init__(x, y, width, height, world_num, asset_cache)
        self._anchor = pygame.Vector2(self.rect.topleft)
        self._horizontal = horizontal
        self._amplitude = amplitude
        self._speed = speed
        self._phase = phase_offset

    def update(self) -> None:
        self.prev_rect = self.rect.copy()
        self._phase += self._speed
        oscillation = math.sin(self._phase / FPS * math.tau) * self._amplitude
        if self._horizontal:
            new_x = int(self._anchor.x + oscillation)
            move_x = new_x - self.rect.x
            self.rect.x = new_x
            move_y = 0
        else:
            new_y = int(self._anchor.y + oscillation)
            move_y = new_y - self.rect.y
            self.rect.y = new_y
            move_x = 0
        self.move_vector = pygame.Vector2(move_x, move_y)


class BlinkingPlatform(Platform):
    """Platform that alternates between solid and intangible states on a timer."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        world_num: int,
        asset_cache: AssetCache,
        *,
        on_frames: int = 90,
        off_frames: int = 60,
        phase_offset: int = 0,
    ):
        super().__init__(x, y, width, height, world_num, asset_cache)
        # Ensure self.image exists
        if not hasattr(self, "image") or self.image is None:
            self.image = pygame.Surface((width, height), pygame.SRCALPHA)
            self.image.fill((200, 200, 200))
        self._anchor = pygame.Vector2(self.rect.topleft)
        self._on_frames = max(12, on_frames)
        self._off_frames = max(12, off_frames)
        self._cycle = self._on_frames + self._off_frames
        self._timer = phase_offset % self._cycle
        self._active = True
        self._hidden_offset = pygame.Vector2(0, SCREEN_HEIGHT * 2)
        self.image.set_alpha(255)

    @property
    def active(self) -> bool:
        return self._active

    def update(self) -> None:
        self.prev_rect = self.rect.copy()
        self._timer = (self._timer + 1) % self._cycle
        should_be_active = self._timer < self._on_frames
        if should_be_active != self._active:
            self._active = should_be_active
            self.image.set_alpha(255 if self._active else 90)
        if self._active:
            self.rect.topleft = (int(self._anchor.x), int(self._anchor.y))
        else:
            self.rect.topleft = (
                int(self._anchor.x),
                int(self._anchor.y + self._hidden_offset.y),
            )
        self.move_vector = pygame.Vector2(0, 0)


class PathPlatform(Platform):
    """A platform that moves along a predefined path."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        world_num: int,
        asset_cache: AssetCache,
        *,
        path: List[Tuple[int, int]],
        speed: float = 2.0,
    ):
        super().__init__(x, y, width, height, world_num, asset_cache)
        self.path = [pygame.Vector2(p) for p in path] if path else []
        self.speed = speed
        self.target_index = 1 if len(self.path) > 1 else 0
        self.pos = pygame.Vector2(self.rect.center)
        self.move_vector = pygame.Vector2(0, 0)

    def update(self) -> None:
        self.prev_rect = self.rect.copy()
        if len(self.path) < 2:
            self.move_vector = pygame.Vector2(0, 0)
            return

        target = self.path[self.target_index]
        direction = target - self.pos
        distance = direction.length()

        if distance < self.speed:
            self.pos = target
            self.target_index = (self.target_index + 1) % len(self.path)
        else:
            self.pos += direction.normalize() * self.speed

        new_center = (int(self.pos.x), int(self.pos.y))
        move_x = new_center[0] - self.rect.centerx
        move_y = new_center[1] - self.rect.centery
        self.rect.center = new_center
        self.move_vector = pygame.Vector2(move_x, move_y)


class Coin(pygame.sprite.Sprite):
    effect = "collect"

    def __init__(self, center_x: int, center_y: int):
        super().__init__()
        try:
            self.image = pygame.image.load(OBJECT_DIR / "coin.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(self.image, (255, 215, 0), (10, 10), 10)
        self.rect = self.image.get_rect(center=(center_x, center_y))
        self.timer = 0

    def update(self) -> None:
        pass


class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, speed=2, world=1, assets=None):
        super().__init__()
        self.rect = pygame.Rect(x, y, 32, 32)
        self.speed = speed
        self.world = world
        self.assets = assets
    def update(self):
        self.rect.x += self.speed
        if self.rect.left < 0 or self.rect.right > 800:  # Assuming 800 is screen width
            self.speed *= -1

# --- World-Specific Enemies ---
class JungleSnake(Enemy):
    def __init__(self, x, y, speed=2, world=1, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((32, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (60, 180, 60), (0, 0, 32, 16))
        pygame.draw.circle(self.image, (40, 120, 40), (8, 8), 6)
        pygame.draw.circle(self.image, (0, 0, 0), (12, 8), 2)

class StoneGolem(Enemy):
    def __init__(self, x, y, speed=1, world=2, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((28, 32), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (120, 110, 100), (0, 8, 28, 24))
        pygame.draw.rect(self.image, (80, 70, 60), (4, 20, 20, 8))
        pygame.draw.circle(self.image, (180, 170, 160), (14, 14), 10)
        pygame.draw.circle(self.image, (0, 0, 0), (10, 14), 2)

class Mummy(Enemy):
    def __init__(self, x, y, speed=2, world=3, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (220, 220, 180), (0, 0, 32, 32))
        for i in range(0, 32, 6):
            pygame.draw.line(self.image, (180, 180, 140), (0, i), (32, i), 2)
        pygame.draw.circle(self.image, (0, 0, 0), (10, 12), 3)
        pygame.draw.circle(self.image, (0, 0, 0), (22, 12), 3)

class VineBeast(Enemy):
    def __init__(self, x, y, speed=2, world=4, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((32, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (60, 200, 80), (0, 8, 32, 16))
        pygame.draw.line(self.image, (30, 120, 40), (8, 16), (24, 16), 3)
        pygame.draw.circle(self.image, (0, 0, 0), (12, 16), 2)

class SnowWolf(Enemy):
    def __init__(self, x, y, speed=3, world=5, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((36, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (220, 240, 255), (0, 8, 36, 16))
        pygame.draw.circle(self.image, (220, 240, 255), (8, 12), 8)
        pygame.draw.polygon(self.image, (180, 180, 200), [(30, 8), (36, 12), (30, 16)])
        pygame.draw.circle(self.image, (0, 0, 0), (12, 16), 2)

class FireDragon(Enemy):
    def __init__(self, x, y, speed=3, world=6, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((36, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (255, 80, 40), (0, 8, 36, 16))
        pygame.draw.circle(self.image, (255, 180, 40), (8, 12), 8)
        pygame.draw.polygon(self.image, (255, 120, 0), [(30, 8), (36, 12), (30, 16)])
        pygame.draw.circle(self.image, (0, 0, 0), (12, 16), 2)

class SkyHawk(Enemy):
    def __init__(self, x, y, speed=4, world=7, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((32, 20), pygame.SRCALPHA)
        pygame.draw.polygon(self.image, (180, 220, 255), [(0, 10), (16, 0), (32, 10), (16, 20)])
        pygame.draw.circle(self.image, (255, 255, 255), (16, 10), 4)
        pygame.draw.circle(self.image, (0, 0, 0), (20, 10), 2)

class CyberDrone(Enemy):
    def __init__(self, x, y, speed=2, world=8, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (80, 255, 255), (0, 8, 28, 12))
        pygame.draw.rect(self.image, (40, 200, 255), (8, 12, 12, 8))
        pygame.draw.circle(self.image, (0, 0, 0), (14, 14), 2)

class Phantom(Enemy):
    def __init__(self, x, y, speed=2, world=9, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((28, 32), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (180, 180, 255, 180), (0, 0, 28, 32))
        pygame.draw.circle(self.image, (255, 255, 255, 200), (14, 12), 8)
        pygame.draw.circle(self.image, (0, 0, 0), (10, 16), 2)

class GlitchBug(Enemy):
    def __init__(self, x, y, speed=2, world=10, assets=None):
        super().__init__(x, y, speed, world, assets)
        self.image = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (200, 80, 255), (0, 8, 24, 8))
        pygame.draw.circle(self.image, (255, 255, 255), (12, 12), 8)
        pygame.draw.circle(self.image, (0, 0, 0), (16, 12), 2)

class DefaultEnemy(Enemy):
    def __init__(self, x, y, speed=2, world=1, assets=None):
        super().__init__(x, y, speed, world, assets)

def create_enemy(x, y, world, speed=2, assets=None):
    if world == 1:
        return JungleSnake(x, y, speed, world, assets)
    elif world == 2:
        return StoneGolem(x, y, speed, world, assets)
    elif world == 3:
        return Mummy(x, y, speed, world, assets)
    elif world == 4:
        return VineBeast(x, y, speed, world, assets)
    elif world == 5:
        return SnowWolf(x, y, speed, world, assets)
    elif world == 6:
        return FireDragon(x, y, speed, world, assets)
    elif world == 7:
        return SkyHawk(x, y, speed, world, assets)
    elif world == 8:
        return CyberDrone(x, y, speed, world, assets)
    elif world == 9:
        return Phantom(x, y, speed, world, assets)
    elif world == 10:
        return GlitchBug(x, y, speed, world, assets)
    else:
        return DefaultEnemy(x, y, speed, world, assets)
    effect = "kill"

    def __init__(self, x: int, y: int, speed: int = 2, world: int = 1, assets: Optional[AssetCache] = None):
        super().__init__()
        if assets is not None:
            self.image = assets.enemy_texture(world)
        else:
            self.image = pygame.Surface((30, 30))
            self.image.fill(ENEMY_COLORS[(world - 1) % len(ENEMY_COLORS)])
        self.rect = self.image.get_rect(topleft=(x, y))
        # Ensure enemies always move: pick a non-zero speed with random direction
        base_speed = max(2, abs(speed))
        self.speed = base_speed if random.random() < 0.5 else -base_speed

    def update(self) -> None:
        if self.speed == 0:
            self.speed = 2
        self.rect.x += self.speed
        if self.rect.left < 0 or self.rect.right > SCREEN_WIDTH:
            self.speed *= -1


class Portal(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        # (Removed) self.image = load_object_image("portal_placeholder.png")
        self.rect = pygame.Rect(x - 32, y - 32, 64, 64)

    def _variant(self) -> str:
        if self.portal_type == "boss":
            return "boss_active" if self.active else "boss_locked"
        return "normal"

    def set_active(self, active: bool) -> None:
        if self.portal_type != "boss":
            return
        if self.active == active:
            return
        self.active = active
        self.image = self.assets.portal_texture(self.world, self._variant())
        self.base_image = self.image.copy()
        self.rect = self.image.get_rect(center=self.rect.center)

    def update(self, dt: float = 1 / FPS) -> None:
        self._anim_timer += dt
        angle = (self._anim_timer * 40.0) % 360
        pulse = 1.0 + 0.08 * math.sin(self._anim_timer * 6.0)
        new_image = pygame.transform.rotozoom(self.base_image, angle, pulse)
        center = self.rect.center
        electric = new_image.copy()
        arc_surface = pygame.Surface(electric.get_size(), pygame.SRCALPHA)
        arc_count = 3
        for _ in range(arc_count):
            x1 = random.randint(0, arc_surface.get_width() - 1)
            y1 = random.randint(0, arc_surface.get_height() - 1)
            x2 = x1 + random.randint(-24, 24)
            y2 = y1 + random.randint(-24, 24)
            r, g, b = self.lightning_color
            color = (r, g, b, random.randint(140, 230))
            pygame.draw.line(arc_surface, color, (x1, y1), (x2, y2), width=2)
        electric.blit(arc_surface, (0, 0), special_flags=pygame.BLEND_ADD)
        self.image = electric
        self.rect = self.image.get_rect(center=center)


class Boss(pygame.sprite.Sprite):
    def __init__(self, center_x: int, center_y: int, world: int, assets: AssetCache):
        super().__init__()
        self.world = world
        self.assets = assets
        self.animations = assets.boss_animation_frames(world)
        if "walk" not in self.animations:
            if "attack1" in self.animations:
                self.animations["walk"] = [frame.copy() for frame in self.animations["attack1"]]
            elif "idle" in self.animations:
                self.animations["walk"] = [frame.copy() for frame in self.animations["idle"]]
        idle_frames = self.animations.get("idle")
        if idle_frames:
            base_image = idle_frames[0].copy()
        else:
            base_image = assets.boss_texture(world).copy()
            self.animations.setdefault("idle", [base_image.copy()])
        self.image = base_image
        self.rect = self.image.get_rect(midbottom=(center_x, center_y))
        self.name = BOSS_NAMES[world - 1] if 1 <= world <= len(BOSS_NAMES) else f"W{world} Guardian"
        self._animation_state = "idle"
        self._anim_frame_index = 0
        self._anim_timer = 0.0
        self._animation_speed = 0.12
        self._animation_loop = True
        self._animation_hold_until: Optional[int] = None

        profile = BOSS_PROFILES.get(world, DEFAULT_BOSS_PROFILE)
        # Scale health upward by world and add a small global multiplier
        self.max_health = int(profile.max_health * (1.1 + 0.08 * (world - 1)))
        self.health = self.max_health
        self._short_base_cd = profile.short_cooldown
        self._long_base_cd = profile.long_cooldown
        self.walk_speed = profile.ground_speed
        self.walk_range = profile.patrol_range
        self.walk_direction = 1
        self.walk_enabled = self.walk_speed > 0
        self._current_motion = "idle"
        try:
            self.projectile_surface = assets.boss_projectile_texture(world)
        except Exception:
            # Fallback simple projectile if asset missing
            surf = pygame.Surface((18, 18), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 200, 120), (9, 9), 9)
            pygame.draw.circle(surf, (255, 255, 255), (9, 9), 5)
            self.projectile_surface = surf
        self.facing_direction = 1
        self.phase = 1
        self.enraged = False

        self.reset_anchor((center_x, center_y))
        self.short_cooldown = random.uniform(max(0.3, self._short_base_cd * 0.3), self._short_base_cd)
        self.long_cooldown = random.uniform(max(0.6, self._long_base_cd * 0.4), self._long_base_cd)
        self._set_animation_state("idle", force=True)

    def _set_image(self, surface: pygame.Surface) -> None:
        if hasattr(self, "rect"):
            center = self.rect.center
            bottom = self.rect.bottom
        else:
            center = (surface.get_width() // 2, surface.get_height() // 2)
            bottom = center[1]
        self.image = surface
        self.rect = self.image.get_rect(center=center)
        self.rect.bottom = bottom

    def reset_anchor(self, center: Tuple[float, float]) -> None:
        """Recenter the boss on a ground point and reset patrol origin."""
        vector = pygame.Vector2(center)
        self.position = pygame.Vector2(vector)
        self._home = pygame.Vector2(vector)
        self._patrol_origin = pygame.Vector2(vector)
        self.rect.midbottom = (int(vector.x), int(vector.y))
        self.walk_direction = 1
        alive = getattr(self, "health", 1) > 0
        if alive:
            self.walk_enabled = self.walk_speed > 0
        self._set_facing(1)

    def _refresh_current_frame(self) -> None:
        frame = self._get_animation_frame(self._animation_state, self._anim_frame_index)
        if frame is not None:
            self._set_image(frame)

    def _get_animation_frame(self, state: str, index: int) -> Optional[pygame.Surface]:
        frames = self.animations.get(state)
        if not frames:
            return None
        frame = frames[index % len(frames)]
        if self.facing_direction < 0:
            frame = pygame.transform.flip(frame, True, False)
        return frame

    def _set_facing(self, direction: int) -> None:
        direction = 1 if direction >= 0 else -1
        if direction == self.facing_direction:
            return
        self.facing_direction = direction
        self._refresh_current_frame()

    def _set_animation_state(
        self,
        state: str,
        *,
        speed: Optional[float] = None,
        loop: bool = True,
        hold: Optional[float] = None,
        force: bool = False,
    ) -> None:
        frames = self.animations.get(state)
        if not frames:
            return
        if state == self._animation_state and not force:
            return
        self._animation_state = state
        self._current_motion = state
        self._animation_loop = loop
        if speed is not None:
            self._animation_speed = speed
        self._anim_frame_index = 0
        self._anim_timer = 0.0
        self._refresh_current_frame()
        self._animation_hold_until = (
            pygame.time.get_ticks() + int(hold * 1000) if hold is not None else None
        )

    def _update_animation(self, dt: float) -> None:
        frames = self.animations.get(self._animation_state)
        if not frames:
            return
        self._anim_timer += dt
        if self._anim_timer >= self._animation_speed:
            self._anim_timer -= self._animation_speed
            if self._anim_frame_index < len(frames) - 1:
                self._anim_frame_index += 1
            elif self._animation_loop:
                self._anim_frame_index = 0
            self._refresh_current_frame()
        if (
            self._animation_hold_until is not None
            and self._animation_state not in ("idle", "death")
            and pygame.time.get_ticks() >= self._animation_hold_until
        ):
            self._set_animation_state("idle", force=True)

    def _trigger_death_animation(self) -> None:
        if "death" not in self.animations:
            return
        self.walk_enabled = False
        self._set_animation_state("death", speed=0.16, loop=False, hold=None, force=True)

    def _apply_ground_motion(self, dt: float) -> None:
        if not self.walk_enabled or self.walk_speed <= 0:
            self._update_motion_state("idle")
            self.position.y = self._patrol_origin.y
            return
        self._set_facing(self.walk_direction)
        self.position.y = self._patrol_origin.y
        self.position.x += self.walk_speed * self.walk_direction * dt
        left = self._patrol_origin.x - self.walk_range
        right = self._patrol_origin.x + self.walk_range
        if self.position.x <= left:
            self.position.x = left
            self.walk_direction = 1
            self._set_facing(self.walk_direction)
        elif self.position.x >= right:
            self.position.x = right
            self.walk_direction = -1
            self._set_facing(self.walk_direction)
        self._update_motion_state("walk")

    def _update_motion_state(self, desired: str) -> None:
        if self._animation_state == "death":
            return
        if desired not in self.animations:
            desired = "idle"
        if desired == self._current_motion:
            return
        self._current_motion = desired
        self._set_animation_state(desired)

    def update(self) -> None:
        dt = 1 / FPS
        if not self.defeated():
            self._apply_ground_motion(dt)
            # Phase/enrage scaling based on remaining health
            health_ratio = self.health / max(1, self.max_health)
            new_phase = 3 if health_ratio < 0.35 else 2 if health_ratio < 0.7 else 1
            if new_phase != self.phase:
                self.phase = new_phase
                # Increase aggression on phase shifts
                self._short_base_cd *= 0.85
                self._long_base_cd *= 0.9
                self.walk_speed *= 1.05
                self._reset_short_cooldown()
                self._reset_long_cooldown()
            if not self.enraged and health_ratio < 0.4:
                self.enraged = True
                self.walk_speed *= 1.1
                self._short_base_cd *= 0.8
                self._long_base_cd *= 0.8
                self._reset_short_cooldown()
                self._reset_long_cooldown()
        self.rect.centerx = int(self.position.x)
        self.rect.bottom = int(self.position.y)
        self._home = pygame.Vector2(self.position)
        self.short_cooldown = max(0.0, self.short_cooldown - dt)
        self.long_cooldown = max(0.0, self.long_cooldown - dt)
        if hasattr(self, "stagger_timer") and self.stagger_timer > 0:
            self.stagger_timer = max(0.0, self.stagger_timer - dt)
        self._update_animation(dt)

    def perform_attacks(self, player: "Player", projectiles: pygame.sprite.Group) -> None:
        if self.defeated():
            return
        # Use long cooldown for heavy attacks, short for lighter spam
        if self.long_cooldown <= 0.0 and getattr(self, "stagger_timer", 0) <= 0:
            self._heavy_attack(player, projectiles)
        elif self.short_cooldown <= 0.0:
            self._basic_projectile_attack(player, projectiles)

    def take_damage(self, amount: int = 1) -> None:
        if self.health <= 0:
            return
        self.health = max(0, self.health - amount)
        if self.health <= 0:
            # Stop boss music immediately on boss defeat
            if hasattr(self, 'assets') and hasattr(self, 'game'):
                self.game.stop_music()
            self._trigger_death_animation()

    def defeated(self) -> bool:
        return self.health <= 0

    def _reset_short_cooldown(self, duration: Optional[float] = None) -> None:
        base = duration if duration is not None else self._short_base_cd
        jitter = random.uniform(-0.2, 0.2) * base
        self.short_cooldown = max(0.35, base + jitter)

    def _reset_long_cooldown(self, duration: Optional[float] = None) -> None:
        base = duration if duration is not None else self._long_base_cd
        jitter = random.uniform(-0.15, 0.15) * base
        self.long_cooldown = max(0.8, base + jitter)

    @staticmethod
    def _clamp_x(x: int) -> int:
        return max(40, min(SCREEN_WIDTH - 40, x))

    def _projectile_colors(self) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        design = BOSS_VISUALS.get(self.world, {})
        accent = design.get("accent", ENEMY_COLORS[(self.world - 1) % len(ENEMY_COLORS)])
        detail = design.get("detail", WHITE)
        return accent, detail

    def _distance_to_player(self, player: "Player") -> float:
        return pygame.Vector2(player.rect.center).distance_to(pygame.Vector2(self.rect.center))

    def _spawn_projectile(
        self,
        surface: pygame.Surface,
        center: Tuple[int, int],
        velocity: pygame.Vector2,
        projectiles: pygame.sprite.Group,
        extra_update: Optional[Callable[[pygame.sprite.Sprite], None]] = None,
        kill_margin: int = 60,
    ) -> pygame.sprite.Sprite:
        projectile = pygame.sprite.Sprite()
        cx, cy = center
        projectile.image = surface
        projectile.rect = surface.get_rect(center=(int(cx), int(cy)))
        projectile.velocity = pygame.Vector2(velocity)
        projectile.pos = pygame.Vector2(projectile.rect.center)

        def update(self_projectile: pygame.sprite.Sprite) -> None:
            if extra_update:
                extra_update(self_projectile)
            self_projectile.pos += self_projectile.velocity
            self_projectile.rect.center = (int(self_projectile.pos.x), int(self_projectile.pos.y))
            if (
                self_projectile.rect.right < -kill_margin
                or self_projectile.rect.left > SCREEN_WIDTH + kill_margin
                or self_projectile.rect.bottom < -kill_margin
                or self_projectile.rect.top > SCREEN_HEIGHT + kill_margin
            ):
                self_projectile.kill()

        projectile.update = update.__get__(projectile, pygame.sprite.Sprite)
        projectiles.add(projectile)
        return projectile

    @staticmethod
    def _gravity_update(gravity: float) -> Callable[[pygame.sprite.Sprite], None]:
        def _update(self_projectile: pygame.sprite.Sprite) -> None:
            self_projectile.velocity.y += gravity

        return _update

    def clear_attack_timers(self) -> None:
        """Convenience helper for resetting cooldowns once new patterns are added."""
        self.short_cooldown = 0.0
        self.long_cooldown = 0.0

    def _basic_projectile_attack(self, player: "Player", projectiles: pygame.sprite.Group) -> None:
        if not self.projectile_surface:
            return
        origin = pygame.Vector2(self.rect.centerx, self.rect.centery - self.rect.height * 0.3)
        target = pygame.Vector2(player.rect.center)
        direction = target - origin
        if direction.length_squared() == 0:
            direction = pygame.Vector2(self.walk_direction, -0.2)
        direction = direction.normalize()
        speed = 6.0 + self.world * 0.45 + (0.8 if self.enraged else 0)
        velocity = direction * speed
        # Fire a small spread based on world/phase
        spread_count = max(1, 1 + (self.world // 4) + max(0, self.phase - 1))
        angle_step = 10
        base_angle = math.degrees(math.atan2(direction.y, direction.x))
        for i in range(spread_count):
            offset = (i - (spread_count - 1) / 2) * angle_step
            rad = math.radians(base_angle + offset)
            vel = pygame.Vector2(math.cos(rad), math.sin(rad)) * speed
            self._spawn_projectile(
                self.projectile_surface,
                (int(origin.x), int(origin.y)),
                vel,
                projectiles,
            )
        self.short_cooldown = max(0.5, self._short_base_cd * 0.8)
        if "attack1" in self.animations:
            self._set_animation_state("attack1", force=True, hold=0.4)

    def _heavy_attack(self, player: "Player", projectiles: pygame.sprite.Group) -> None:
        """World-scaled heavy attack: mix of rain, dash, and volleys."""
        choice_pool = []
        choice_pool.append(self._volley_attack)
        if self.world >= 3:
            choice_pool.append(self._rain_attack)
        if self.world >= 5:
            choice_pool.append(self._dash_attack)
        attack_fn = random.choice(choice_pool)
        attack_fn(player, projectiles)
        self._reset_long_cooldown()
        # Add a small short cooldown buffer so heavy attacks don't chain instantly
        self.short_cooldown = max(self.short_cooldown, 0.6)

    def _volley_attack(self, player: "Player", projectiles: pygame.sprite.Group) -> None:
        """Fan volley that scales with world/phase."""
        origin = pygame.Vector2(self.rect.centerx, self.rect.centery - self.rect.height * 0.35)
        target = pygame.Vector2(player.rect.center)
        base_dir = (target - origin).normalize() if target != origin else pygame.Vector2(self.walk_direction, 0)
        volleys = max(2, 1 + (self.world // 3) + max(0, self.phase - 1))
        angle_step = 8 + max(0, 3 - self.world // 2)
        speed = 6.5 + self.world * 0.4 + (1.0 if self.enraged else 0)
        base_angle = math.degrees(math.atan2(base_dir.y, base_dir.x))
        for i in range(volleys):
            offset = (i - (volleys - 1) / 2) * angle_step
            rad = math.radians(base_angle + offset)
            vel = pygame.Vector2(math.cos(rad), math.sin(rad)) * speed
            self._spawn_projectile(self.projectile_surface, (int(origin.x), int(origin.y)), vel, projectiles)
        if "attack2" in self.animations:
            self._set_animation_state("attack2", force=True, hold=0.5)

    def _rain_attack(self, player: "Player", projectiles: pygame.sprite.Group) -> None:
        """Spawn falling projectiles from above the player area."""
        columns = max(3, 2 + self.world // 3 + max(0, self.phase - 1))
        spacing = SCREEN_WIDTH // max(4, columns + 1)
        top_y = -40
        speed = 5.0 + 0.5 * self.world
        for i in range(columns):
            x = 40 + i * spacing + random.randint(-12, 12)
            vel = pygame.Vector2(0, speed + random.uniform(-0.6, 0.6))
            self._spawn_projectile(self.projectile_surface, (x, top_y), vel, projectiles)
        self._reset_short_cooldown(1.2)
        if "attack2" in self.animations:
            self._set_animation_state("attack2", force=True, hold=0.6)

    def _dash_attack(self, player: "Player", projectiles: pygame.sprite.Group) -> None:
        """Quick ground dash toward player with a small shockwave projectile."""
        direction = 1 if player.rect.centerx >= self.rect.centerx else -1
        self._set_facing(direction)
        dash_distance = 180 + 12 * self.world
        # Move instantly; if collision logic existed we'd integrate, but here we slide
        self.position.x = self._clamp_x(int(self.position.x + dash_distance * direction))
        self.rect.centerx = int(self.position.x)
        # Shockwave
        speed = 7.0 + self.world * 0.4
        shock_dir = pygame.Vector2(direction, 0)
        for offset in (-1, 0, 1):
            vel = pygame.Vector2(direction, 0.08 * offset) * speed
            origin = (self.rect.centerx, self.rect.centery - 20)
            self._spawn_projectile(self.projectile_surface, origin, vel, projectiles)
        self._set_animation_state("attack2", force=True, hold=0.35)
        self._reset_short_cooldown(0.8)


class Goal(pygame.sprite.Sprite):
    def __init__(self, x, y, world=None, assets=None, portal_type=None, active=True):
        super().__init__()
        # Set the portal image for this world as the goal image
        if assets and hasattr(assets, 'portal_texture') and world is not None:
            self.image = assets.portal_texture(world, variant=portal_type or "normal")
            # Resize to 64x64 if needed
            if self.image.get_width() != 64 or self.image.get_height() != 64:
                self.image = pygame.transform.smoothscale(self.image, (64, 64))
        else:
            # fallback: blank surface
            self.image = pygame.Surface((64, 64), pygame.SRCALPHA)
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.portal_type = portal_type or "normal"
        self.active = active
        self.base_image = self.image.copy()
        self._anim_timer = 0.0
        self.world = world or 1
        self.lightning_color = WORLD_PORTAL_COLORS.get(self.world, (180, 220, 255))

class PlayerProjectile(pygame.sprite.Sprite):
    def __init__(self, x: int, y: int, facing_right: bool):
        super().__init__()
        self.image = pygame.Surface((16, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, CYAN, self.image.get_rect())
        pygame.draw.ellipse(self.image, WHITE, self.image.get_rect().inflate(-4, -2))
        self.rect = self.image.get_rect(center=(x, y))
        speed = 12
        self.velocity_x = speed if facing_right else -speed

    def update(self) -> None:
        self.rect.x += self.velocity_x
        if self.rect.right < 0 or self.rect.left > SCREEN_WIDTH:
            self.kill()
class Spike(pygame.sprite.Sprite):
    effect = "kill"
    _ASSETS: Dict[int, Dict[str, pygame.Surface]] = {}

    @classmethod
    def _load_assets(cls, world: int) -> Dict[str, pygame.Surface]:
        if world in cls._ASSETS:
            return cls._ASSETS[world]

        assets = {}
        size = (32, 16)
        spike_path = OBJECT_DIR / "spike.png"
        
        if spike_path.exists():
            try:
                sheet = pygame.image.load(spike_path).convert_alpha()
                # Load each direction from sprite sheet (up, down, left, right) - assumes horizontal strip
                for i, direction in enumerate(["up", "down", "left", "right"]): # This assumes a horizontal strip
                    sprite = pygame.Surface(size, pygame.SRCALPHA)
                    sprite.blit(sheet, (0, 0), (i * size[0], 0, *size))
                    assets[direction] = sprite
            except Exception as e:
                print(f"Failed to load spike assets for world {world}: {e}")
        
        if not assets:
            # Fallback to generated spikes with world-themed colors
            world_theme = WORLD_THEMES.get(world)
            base_color = (180, 180, 180)
            highlight_color = (220, 220, 220)
            if world_theme:
                bg_color = world_theme.background_color
                # Derive spike color from background to match theme
                try:
                    hue, sat, val = colorsys.rgb_to_hsv(*(c/255 for c in bg_color))
                    spike_rgb = colorsys.hsv_to_rgb(hue, min(1.0, sat + 0.2), max(0.2, val - 0.3))
                    base_color = tuple(int(x * 255) for x in spike_rgb)
                    highlight_color = _brighten(base_color, 40)
                except Exception:
                    pass
            
            up = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.polygon(up, base_color, [(0, 16), (16, 0), (32, 16)])
            pygame.draw.line(up, highlight_color, (16, 2), (2, 15), 2)
            assets["up"] = up
            
            down = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.polygon(down, base_color, [(0, 0), (16, 16), (32, 0)])
            pygame.draw.line(down, highlight_color, (16, 14), (2, 1), 2)
            assets["down"] = down
            
            left = pygame.Surface((16, 32), pygame.SRCALPHA)
            pygame.draw.polygon(left, base_color, [(16, 0), (0, 16), (16, 32)])
            pygame.draw.line(left, highlight_color, (14, 2), (1, 16), 2)
            assets["left"] = left
            
            right = pygame.Surface((16, 32), pygame.SRCALPHA)
            pygame.draw.polygon(right, base_color, [(0, 0), (16, 16), (0, 32)])
            pygame.draw.line(right, highlight_color, (2, 2), (15, 16), 2)
            assets["right"] = right
        
        cls._ASSETS[world] = assets
        return assets

    def __init__(self, x: int, y: int, direction: str = "up", world: int = 1):
        super().__init__()
        assets = self._load_assets(world)
        self.image = assets.get(direction, assets.get("up"))
        if not self.image: # Ultimate fallback
            self.image = pygame.Surface((32,16))
            self.image.fill(RED)
        self.rect = self.image.get_rect(topleft=(x, y))


class FallingRock(pygame.sprite.Sprite):
    effect = "kill"

    def __init__(self, x: int, y: int):
        super().__init__()
        try:
            self.image = pygame.image.load(OBJECT_DIR / "rock.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((24, 24), pygame.SRCALPHA)
            # Main rock shape
            pygame.draw.circle(self.image, (100, 90, 80), (12, 12), 12)
            # Cracks and details
            pygame.draw.line(self.image, (70, 60, 50), (5, 5), (18, 18), 2)
            pygame.draw.circle(self.image, (130, 120, 110), (8, 16), 3)
            # Outline
            pygame.draw.circle(self.image, (50, 40, 30), (12, 12), 12, 1)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.fall_speed = 0

    def update(self) -> None:
        # Increase rock fall frequency in world 2
        fall_chance = 0.01
        try:
            import main
            if hasattr(main, 'game_instance') and hasattr(main.game_instance, 'current_world'):
                if main.game_instance.current_world == 2:
                    fall_chance = 0.04  # 4x more frequent in world 2
        except Exception:
            pass
        if self.fall_speed == 0 and random.random() < fall_chance:
            self.fall_speed = 6
        self.rect.y += self.fall_speed
        if self.rect.top > SCREEN_HEIGHT:
            self.kill()


class QuicksandTile(pygame.sprite.Sprite):
    effect = "slow"

    def __init__(self, x: int, y: int):
        super().__init__()
        try:
            self.image = pygame.image.load(OBJECT_DIR / "quicksand.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((32, 16), pygame.SRCALPHA)
            base_color = (190, 160, 90)
            highlight = (220, 190, 120)
            self.image.fill(base_color)
            # Add some texture
            for i in range(10):
                self.image.set_at((random.randint(0, 31), random.randint(0, 15)), highlight)
        self.rect = self.image.get_rect(topleft=(x, y))


class Icicle(pygame.sprite.Sprite):
    effect = "kill"

    def __init__(self, x: int, y: int):
        super().__init__()
        try:
            self.image = pygame.image.load(OBJECT_DIR / "icicle.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((16, 32), pygame.SRCALPHA)
            # Gradient fill for icy look
            for i in range(32):
                alpha = 255 - (i * 6)
                color = (180, 220, 255, alpha)
                pygame.draw.line(self.image, color, (0, i), (15, i))
            pygame.draw.polygon(self.image, (220, 240, 255), [(0, 0), (8, 32), (16, 0)])
        self.rect = self.image.get_rect(topleft=(x, y))


class LavaBubble(pygame.sprite.Sprite):
    effect = "kill"
    _ASSETS: Dict[int, List[pygame.Surface]] = {}

    @classmethod
    def load_assets(cls, world: int, force_reload: bool = False) -> None:
        if world in cls._ASSETS and not force_reload:
            return
        try:
            sheet = pygame.image.load(str(ASSET_DIR / "objects" / "lava_bubble.png")).convert_alpha()
            frames = []
            for i in range(4):  # 4 animation frames
                frames.append(sheet.subsurface((i * 32, 0, 32, 32)))
            cls._ASSETS[world] = frames
        except (pygame.error, FileNotFoundError):
            # Fallback: Create animated procedural bubble
            frames = []
            for i in range(4):
                surface = pygame.Surface((32, 32), pygame.SRCALPHA)
                pulse = 1.0 + 0.1 * math.sin(i / 4 * math.tau)
                pygame.draw.circle(surface, (255, 100, 0, 100), (16, 16), int(14 * pulse))
                pygame.draw.circle(surface, (255, 180, 40), (16, 16), int(11 * pulse))
                pygame.draw.circle(surface, (255, 255, 150), (16, 16), int(5 * pulse))
                frames.append(surface)
            cls._ASSETS[world] = frames

    def __init__(self, x: int, y: int, world: int = 1):
        super().__init__()
        self.world = world
        self.load_assets(world)
        self.frame = 0
        self.frame_timer = 0
        self.image = self._ASSETS[world][0]
        self.rect = self.image.get_rect(topleft=(x, y))
        self.base_y = y
        self.bob_offset = 0
        self.bob_speed = 2


class WindOrb(pygame.sprite.Sprite):
    effect = "boost"

    def __init__(self, x: int, y: int):
        super().__init__()
        self.base_pos = pygame.Vector2(x, y)
        try:
            self.image = pygame.image.load(OBJECT_DIR / "wind_orb.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((24, 24), pygame.SRCALPHA)
            # Outer transparent layer
            pygame.draw.circle(self.image, (150, 255, 255, 80), (12, 12), 12)
            # Inner core with some detail
            pygame.draw.circle(self.image, (220, 255, 255), (12, 12), 8)
            pygame.draw.line(self.image, (180, 240, 240), (6, 12), (18, 12), 2)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.timer = random.randint(0, 60)

    def update(self) -> None:
        self.timer = (self.timer + 1) % 120
        offset = math.sin(self.timer / 120 * math.tau) * 4
        self.rect.topleft = (self.base_pos.x, self.base_pos.y + offset)


class ElectricTile(pygame.sprite.Sprite):
    effect = "kill"

    def __init__(self, x: int, y: int):
        super().__init__()
        try:
            self.inactive_image = pygame.image.load(OBJECT_DIR / "electric_tile.png").convert_alpha()
        except pygame.error:
            self.inactive_image = pygame.Surface((32, 16), pygame.SRCALPHA)
            self.inactive_image.fill((40, 40, 80))
            # Add some circuit-like lines
            pygame.draw.rect(self.inactive_image, (80, 180, 255), (0, 6, 32, 4))
            pygame.draw.line(self.inactive_image, (80, 180, 255), (4, 0), (4, 15), 1)
            pygame.draw.line(self.inactive_image, (80, 180, 255), (28, 0), (28, 15), 1)
        
        self.active_image = self.inactive_image.copy()
        pygame.draw.rect(self.active_image, (255, 255, 100), (0, 0, 32, 16))
        self.image = self.inactive_image
        self.rect = self.image.get_rect(topleft=(x, y))


class Boost(pygame.sprite.Sprite):
    effect = "boost"

    def __init__(self, x: int, y: int):
        super().__init__()
        try:
            self.image = pygame.image.load(OBJECT_DIR / "boost.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((32, 16), pygame.SRCALPHA)
            self.image.fill((255, 200, 60))
            pygame.draw.polygon(self.image, (255, 255, 255), [(0, 16), (16, 0), (32, 16)])
        self.rect = self.image.get_rect(topleft=(x, y))

    def update(self):
        pass

class Spring(pygame.sprite.Sprite):
    effect = "spring"
    def __init__(self, x: int, y: int):
        super().__init__()
        try:
            self.image = pygame.image.load(OBJECT_DIR / "spring.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((24, 16), pygame.SRCALPHA)
            self.image.fill((180, 255, 180))
            pygame.draw.rect(self.image, (100, 200, 100), (4, 4, 16, 8))
            pygame.draw.line(self.image, (80, 80, 80), (4, 12), (20, 12), 2)
        self.rect = self.image.get_rect(topleft=(x, y))
    def update(self):
        pass
    def bounce(self, player):
        # Apply a strong upward velocity to the player
        player.velocity.y = -15  # Adjust as needed for game feel

    def __init__(self, x: int, y: int):
        super().__init__()
        try:
            self.image = pygame.image.load(OBJECT_DIR / "ghost_orb.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((24, 24), pygame.SRCALPHA)
            # Draw a wisp-like shape
            pygame.draw.circle(self.image, (200, 100, 255, 50), (12, 12), 11)
            pygame.draw.circle(self.image, (220, 150, 255, 100), (12, 12), 8)
            pygame.draw.circle(self.image, (255, 255, 255, 150), (12, 12), 4)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.timer = random.randint(0, 90)

    def update(self) -> None:
        self.timer = (self.timer + 1) % 90
        alpha = 120 + int(math.sin(self.timer / 90 * math.tau) * 60)
        self.image.set_alpha(alpha)


class GlitchCube(pygame.sprite.Sprite):
    effect = "kill"

    def __init__(self, x: int, y: int):
        super().__init__()
        try:
            self.image = pygame.image.load(OBJECT_DIR / "glitch_cube.png").convert_alpha()
        except pygame.error:
            self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.timer = 0
        self.update()

    def update(self) -> None:
        self.timer += 1
        if pygame.time.get_ticks() % 2 == 0: # to make it less flashy
            return
        # Draw random glitchy rects on top of the image
        for _ in range(2):
            color = random.choice([CYAN, MAGENTA, (255, 255, 0)])
            w, h = random.randint(1, 5), random.randint(1, 5)
            px, py = random.randint(0, 18), random.randint(0, 18)
            pygame.draw.rect(self.image, color, (px, py, w, h))


class SpecialTile(pygame.sprite.Sprite):
    def __init__(self, x: int, y: int, effect: str = "collect", assets: Optional[AssetCache] = None):
        super().__init__()
        self.effect = effect
        self.image = pygame.Surface((32, 32))
        self.rect = self.image.get_rect(topleft=(x,y))
        if self.effect == "collect":
            self.image.fill((255, 255, 0)) # yellow
        elif self.effect == "kill":
            self.image.fill((255, 0, 0)) # red
        elif self.effect == "boost":
            self.image.fill((0, 255, 255)) # cyan
        else:
            self.image.fill((128, 128, 128)) # grey


# ---------------------------------------------------------------------------
# Level generation helpers
# ---------------------------------------------------------------------------


@dataclass
class JumpPhysics:
    """Calculates exact player movement capabilities for level generation."""
    jump_speed: float
    gravity: float
    max_speed: float
    
    @staticmethod
    def from_player(player: Player) -> 'JumpPhysics':
        return JumpPhysics(
            jump_speed=abs(player.jump_speed),
            gravity=player.gravity,
            max_speed=player.max_speed
        )
    
    @property
    def max_jump_height(self) -> float:
        """Maximum height achievable with a perfect jump."""
        return (self.jump_speed ** 2) / (2 * self.gravity)
    
    @property
    def total_air_time(self) -> float:
        """Time spent in air during a maximum height jump."""
        return (self.jump_speed / self.gravity) * 2
    
    @property
    def max_jump_distance(self) -> float:
        """Maximum horizontal distance covered during a jump at max speed."""
        return self.max_speed * self.total_air_time
    
    def can_reach(self, from_pos: Tuple[float, float], to_pos: Tuple[float, float]) -> bool:
        """Determines if a jump between two points is physically possible."""
        dx = abs(to_pos[0] - from_pos[0])
        dy = to_pos[1] - from_pos[1]

        if dy < -self.max_jump_height:
            return False

        max_horizontal = self.max_speed * self.total_air_time
        if dx > max_horizontal:
            return False

        return True


@dataclass
class WorldTheme:
    """Defines the visual and gameplay elements for a specific world type."""
    name: str
    background_color: Tuple[int, int, int]
    platform_style: str
    hazard_types: List[str]
    decoration_types: List[str]
    music_track: str
    
    def create_hazard(self, x: int, y: int, difficulty: float) -> Optional[pygame.sprite.Sprite]:
        """Creates a world-specific hazard at the given position."""
        if not self.hazard_types:
            return None
        
        hazard_type = random.choice(self.hazard_types)
        if hazard_type == "spike":
            return Spike(x, y)
        elif hazard_type == "lava":
            return LavaBubble(x, y)
        elif hazard_type == "icicle":
            return Icicle(x, y)
        elif hazard_type == "wind":
            return WindOrb(x, y)
        elif hazard_type == "electric":
            return ElectricTile(x, y)
        elif hazard_type == "ghost":
            return GhostOrb(x, y)
        return None


# Define the theme for each world
WORLD_THEMES = {
    1: WorldTheme(  # Nature/Forest
        name="Verdant Outskirts",
        background_color=(100, 200, 100),
        platform_style="grass",
        hazard_types=["spike"],
        decoration_types=["vine", "flower"],
    music_track="world1.mp3"
    ),
    2: WorldTheme(  # Stone/Mountain
        name="Rocky Heights",
        background_color=(80, 80, 100),
        platform_style="stone",
        hazard_types=["spike", "rock"],
        decoration_types=["crystal", "torch"],
    music_track="world2.mp3"
    ),
    3: WorldTheme(  # Desert/Sand
        name="Shifting Sands",
        background_color=(210, 190, 100),
        platform_style="sandstone",
        hazard_types=["quicksand", "rock"],
        decoration_types=["cactus", "bones"],
    music_track="world3.mp3"
    ),
    4: WorldTheme(  # Deep Forest
        name="Mystic Grove",
        background_color=(40, 120, 40),
        platform_style="wood",
        hazard_types=["spike", "wind"],
        decoration_types=["mushroom", "firefly"],
    music_track="world4.mp3"
    ),
    5: WorldTheme(  # Ice/Snow
        name="Frozen Peaks",
        background_color=(200, 220, 255),
        platform_style="ice",
        hazard_types=["icicle"],
        decoration_types=["snow", "crystal"],
    music_track="world5.mp3"
    ),
    6: WorldTheme(  # Fire/Volcanic
        name="Molten Core",
        background_color=(150, 60, 40),
        platform_style="volcanic",
        hazard_types=["lava"],
        decoration_types=["ember", "smoke"],
    music_track="world6.mp3"
    ),
    7: WorldTheme(  # Sky/Wind
        name="Cloud Kingdom",
        background_color=(160, 200, 255),
        platform_style="cloud",
        hazard_types=["wind"],
        decoration_types=["cloud", "bird"],
    music_track="world7.mp3"
    ),
    8: WorldTheme(  # Tech/Electric
        name="Circuit Maze",
        background_color=(60, 60, 100),
        platform_style="tech",
        hazard_types=["electric"],
        decoration_types=["wire", "screen"],
    music_track="world8.mp3"
    ),
    9: WorldTheme(  # Ghost/Spirit
        name="Spirit Realm",
        background_color=(100, 80, 50),
        platform_style="spectral",
        hazard_types=["ghost"],
        decoration_types=["wisp", "rune"],
    music_track="world9.mp3"
    ),
    10: WorldTheme(  # Glitch/Corruption
        name="Data Corruption",
        background_color=(180, 0, 180),
        platform_style="glitch",
        hazard_types=["glitch"],
        decoration_types=["artifact", "static"],
    music_track="world10.mp3"
    ),
}


class Hazard(pygame.sprite.Sprite):
    """Base class for all hazards in the game."""
    def __init__(self, x: int, y: int):
        super().__init__()
        self.image = pygame.Surface((32, 32))
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.animation_frame = 0
        self.animation_speed = 0.2
        self.is_deadly = True

    def update(self):
        """Update the hazard's state and animation."""
        self.animation_frame += self.animation_speed
        if self.animation_frame >= 4:
            self.animation_frame = 0


class Spike(Hazard):
    """A simple spike hazard that causes instant death on contact.

    This implementation supports world-themed assets and directional
    variants (up/down/left/right). It loads per-world sprite sheets from
    `assets/objects/world{n}/spike.png` when available and falls back to a
    generated triangle if not.
    """
    _ASSETS: Dict[int, Dict[str, pygame.Surface]] = {}

    @classmethod
    def _load_assets(cls, world: int) -> Dict[str, pygame.Surface]:
        if world in cls._ASSETS:
            return cls._ASSETS[world]

        assets: Dict[str, pygame.Surface] = {}
        size = (32, 16)
        spike_path = ASSET_DIR / "objects" / f"world{world}" / "spike.png"
        fallback_path = OBJECT_DIR / "spike.png"
        if spike_path.exists():
            try:
                sheet = pygame.image.load(spike_path).convert_alpha()
                # Load each direction from sprite sheet (up, down, left, right) - assumes horizontal strip
                for i, direction in enumerate(["up", "down", "left", "right"]): # This assumes a horizontal strip
                    sprite = pygame.Surface(size, pygame.SRCALPHA)
                    sprite.blit(sheet, (0, 0), (i * size[0], 0, *size))
                    assets[direction] = sprite
            except Exception as e:
                print(f"Failed to load spike assets for world {world}: {e}")
        elif fallback_path.exists():
            try:
                base = pygame.image.load(str(fallback_path)).convert_alpha()
                base = pygame.transform.smoothscale(base, size)
                assets["up"] = base
                assets["down"] = pygame.transform.rotate(base, 180)
                assets["left"] = pygame.transform.rotate(base, 90)
                assets["right"] = pygame.transform.rotate(base, -90)
            except Exception as e:
                print(f"Failed to load spike fallback asset: {e}")

        if not assets:
            # Fallback to generated spikes with world-themed colors
            world_theme = WORLD_THEMES.get(world)
            base_color = (180, 180, 180)
            highlight_color = (220, 220, 220)
            if world_theme:
                bg_color = world_theme.background_color
                try:
                    hue, sat, val = colorsys.rgb_to_hsv(bg_color[0]/255, bg_color[1]/255, bg_color[2]/255)
                    spike_rgb = colorsys.hsv_to_rgb(hue, min(1.0, sat + 0.2), max(0.2, val - 0.3))
                    base_color = tuple(int(x * 255) for x in spike_rgb)
                    highlight_color = _brighten(base_color, 40)
                except Exception:
                    pass
            
            up = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.polygon(up, base_color, [(0, 16), (16, 0), (32, 16)])
            pygame.draw.line(up, highlight_color, (16, 2), (2, 15), 2)
            assets["up"] = up
            
            down = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.polygon(down, base_color, [(0, 0), (16, 16), (32, 0)])
            pygame.draw.line(down, highlight_color, (16, 14), (2, 1), 2)
            assets["down"] = down
            
            left = pygame.Surface((16, 32), pygame.SRCALPHA)
            pygame.draw.polygon(left, base_color, [(16, 0), (0, 16), (16, 32)])
            pygame.draw.line(left, highlight_color, (14, 2), (1, 16), 2)
            assets["left"] = left
            
            right = pygame.Surface((16, 32), pygame.SRCALPHA)
            pygame.draw.polygon(right, base_color, [(0, 0), (16, 16), (0, 32)])
            pygame.draw.line(right, highlight_color, (2, 2), (15, 16), 2)
            assets["right"] = right

        cls._ASSETS[world] = assets
        return assets

    def __init__(self, x: int, y: int, direction: str = "up", world: int = 1):
        super().__init__(x, y)
        assets = self._load_assets(world)
        # pick image for direction, default to 'up' if missing
        self.image = assets.get(direction, assets.get("up"))
        if not self.image: # Ultimate fallback
            self.image = pygame.Surface((32,16))
            self.image.fill(RED)
        self.rect = self.image.get_rect(topleft=(x, y))


class LavaBubble(Hazard):
    _ASSETS: Dict[int, List[pygame.Surface]] = {}

    @classmethod
    def _load_assets(cls, world: int) -> List[pygame.Surface]:
        if world in cls._ASSETS:
            return cls._ASSETS[world]
        frames = []
        orb_path = ASSET_DIR / "objects" / f"world{world}" / "lava_bubble.png"
        fallback_path = OBJECT_DIR / "lava_bubble.png"
        if orb_path.exists():
            try:
                sheet = pygame.image.load(orb_path).convert_alpha()
                for i in range(4):
                    frames.append(sheet.subsurface((i * 32, 0, 32, 32)))
            except Exception as e:
                print(f"Failed to load orb assets for world {world}: {e}")
        elif fallback_path.exists():
            try:
                sheet = pygame.image.load(str(fallback_path)).convert_alpha()
                for i in range(4):
                    frames.append(sheet.subsurface((i * 32, 0, 32, 32)))
            except Exception as e:
                print(f"Failed to load lava bubble fallback asset: {e}")
        if not frames:
            # Fallback: animated procedural orb
            for i in range(4):
                surface = pygame.Surface((32, 32), pygame.SRCALPHA)
                pulse = 1.0 + 0.1 * math.sin(i / 4 * math.tau)
                pygame.draw.circle(surface, (255, 100, 0, 100), (16, 16), int(14 * pulse))
                pygame.draw.circle(surface, (255, 180, 40), (16, 16), int(11 * pulse))
                pygame.draw.circle(surface, (255, 255, 150), (16, 16), int(5 * pulse))
                frames.append(surface)
        cls._ASSETS[world] = frames
        return frames

    def __init__(self, x: int, y: int, direction: str = "up", world: int = 1):
        super().__init__(x, y)
        self.world = world
        self.direction = direction
        self.assets = self._load_assets(world)
        self.frame = 0
        self.frame_timer = 0
        self.image = self.assets[0] if self.assets else pygame.Surface((32, 32))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.base_y = y
        self.bob_offset = 0
        self.bob_speed = 2

    def update(self):
        # Animate orb
        num_frames = len(self.assets)
        self.frame_timer = (self.frame_timer + 1) % 8
        if self.frame_timer == 0 and num_frames > 0:
            self.frame = (self.frame + 1) % num_frames
        if num_frames > 0:
            self.image = self.assets[self.frame % num_frames]
        # Bob up and down
        self.bob_offset = math.sin(pygame.time.get_ticks() * 0.003) * 4
        self.rect.y = self.base_y + self.bob_offset


class WindOrb(Hazard):
    """A floating orb that creates wind currents and is deadly like a spike."""
    _ASSETS: Dict[int, List[pygame.Surface]] = {}

    @classmethod
    def _load_assets(cls, world: int) -> List[pygame.Surface]:
        if world in cls._ASSETS:
            return cls._ASSETS[world]
        frames = []
        orb_path = ASSET_DIR / "objects" / "wind_orb.png"
        if orb_path.exists():
            try:
                sheet = pygame.image.load(orb_path).convert_alpha()
                for i in range(4):
                    frames.append(sheet.subsurface((i * 32, 0, 32, 32)))
            except Exception as e:
                print(f"Failed to load wind orb assets for world {world}: {e}")
        if not frames:
            for i in range(4):
                surface = pygame.Surface((32, 32), pygame.SRCALPHA)
                pygame.draw.circle(surface, (150, 255, 255, 120), (16, 16), 14)
                pygame.draw.circle(surface, (220, 255, 255), (16, 16), 11)
                pygame.draw.circle(surface, (255, 255, 255), (16, 16), 5)
                frames.append(surface)
        cls._ASSETS[world] = frames
        return frames

    def __init__(self, x: int, y: int, world: int = 1):
        super().__init__(x, y)
        self.world = world
        self.assets = self._load_assets(world)
        self.frame = 0
        self.frame_timer = 0
        self.image = self.assets[0] if self.assets else pygame.Surface((32, 32))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.initial_x = x
        self.initial_y = y
        self.angle = 0
        self.orbit_radius = 20
        self.orbit_speed = 2
        self.is_deadly = True

    def update(self):
        # Animate orb
        num_frames = len(self.assets)
        self.frame_timer = (self.frame_timer + 1) % 8
        if self.frame_timer == 0 and num_frames > 0:
            self.frame = (self.frame + 1) % num_frames
        if num_frames > 0:
            self.image = self.assets[self.frame % num_frames]
        # Orbit in a circular pattern
        self.angle = (self.angle + self.orbit_speed) % 360
        self.rect.x = self.initial_x + math.cos(math.radians(self.angle)) * self.orbit_radius
        self.rect.y = self.initial_y + math.sin(math.radians(self.angle)) * self.orbit_radius


class Icicle(Hazard):
    """An icicle that falls when the player gets near."""
    _ASSETS: List[pygame.Surface] = []

    @classmethod
    def _load_assets(cls):
        if cls._ASSETS:
            return cls._ASSETS
        frames = []
        icicle_path = ASSET_DIR / "objects" / "icicle.png"
        if icicle_path.exists():
            try:
                sheet = pygame.image.load(icicle_path).convert_alpha()
                for i in range(4):
                    frames.append(sheet.subsurface((i * 32, 0, 32, 32)))
            except Exception as e:
                print(f"Failed to load icicle assets: {e}")
        if not frames:
            for i in range(4):
                surface = pygame.Surface((32, 32), pygame.SRCALPHA)
                pygame.draw.polygon(surface, (200, 220, 255), [(16, 0), (0, 32), (32, 32)])
                pygame.draw.line(surface, (255, 255, 255), (16, 0), (16, 32), 2)
                frames.append(surface)
        cls._ASSETS = frames
        return frames

    def __init__(self, x: int, y: int):
        super().__init__(x, y)
        self.assets = self._load_assets()
        self.frame = 0
        self.frame_timer = 0
        self.image = self.assets[0] if self.assets else pygame.Surface((32, 32))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.falling = False
        self.fall_speed = 0
        self.is_deadly = True

    def update(self):
        # Animate icicle
        num_frames = len(self.assets)
        self.frame_timer = (self.frame_timer + 1) % 8
        if self.frame_timer == 0 and num_frames > 0:
            self.frame = (self.frame + 1) % num_frames
        if num_frames > 0:
            self.image = self.assets[self.frame % num_frames]
        if self.falling:
            self.fall_speed += 0.5
            self.rect.y += self.fall_speed


class ElectricTile(Hazard):
    """An electrified tile that periodically activates."""
    def __init__(self, x: int, y: int):
        super().__init__(x, y)
        self._inactive_image = None
        self._active_image = None
        tile_path = OBJECT_DIR / "electric_tile.png"
        if tile_path.exists():
            try:
                base = pygame.image.load(str(tile_path)).convert_alpha()
                base = pygame.transform.smoothscale(base, (32, 32))
                self._inactive_image = base
                active = base.copy()
                active.fill((255, 255, 120, 160), special_flags=pygame.BLEND_RGBA_ADD)
                self._active_image = active
            except Exception:
                self._inactive_image = None
                self._active_image = None
        if self._inactive_image is None:
            self.image.fill((100, 100, 255))
            self._inactive_image = self.image.copy()
            active = self.image.copy()
            active.fill((255, 255, 0))
            self._active_image = active
        self.active = False
        self.timer = 0
        self.cycle_time = 120  # frames

    def update(self):
        super().update()
        self.timer += 1
        if self.timer >= self.cycle_time:
            self.timer = 0
            self.active = not self.active
        self.is_deadly = self.active
        if self.active:
            self.image = self._active_image
        else:
            self.image = self._inactive_image


class GhostOrb(Hazard):
    """A ghost orb that follows the player."""
    _ASSETS: List[pygame.Surface] = []

    @classmethod
    def _load_assets(cls):
        if cls._ASSETS:
            return cls._ASSETS
        frames = []
        ghost_path = ASSET_DIR / "objects" / "ghost_orb.png"
        if ghost_path.exists():
            try:
                sheet = pygame.image.load(ghost_path).convert_alpha()
                for i in range(4):
                    frames.append(sheet.subsurface((i * 32, 0, 32, 32)))
            except Exception as e:
                print(f"Failed to load ghost orb assets: {e}")
        if not frames:
            for i in range(4):
                surface = pygame.Surface((32, 32), pygame.SRCALPHA)
                pygame.draw.circle(surface, (200, 200, 255, 120), (16, 16), 14)
                pygame.draw.circle(surface, (255, 255, 255), (16, 16), 11)
                frames.append(surface)
        cls._ASSETS = frames
        return frames

    def __init__(self, x: int, y: int):
        super().__init__(x, y)
        self.assets = self._load_assets()
        self.frame = 0
        self.frame_timer = 0
        self.image = self.assets[0] if self.assets else pygame.Surface((32, 32))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.speed = 2
        self.target = None
        self.is_deadly = True

    def update(self):
        # Animate ghost orb
        num_frames = len(self.assets)
        self.frame_timer = (self.frame_timer + 1) % 8
        if self.frame_timer == 0 and num_frames > 0:
            self.frame = (self.frame + 1) % num_frames
        if num_frames > 0:
            self.image = self.assets[self.frame % num_frames]
        if self.target:
            dx = self.target.rect.centerx - self.rect.centerx
            dy = self.target.rect.centery - self.rect.centery
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                self.rect.x += (dx / dist) * self.speed
                self.rect.y += (dy / dist) * self.speed


class Checkpoint(pygame.sprite.Sprite):
    """A checkpoint that saves the player's progress."""
    def __init__(self, x: int, y: int):
        super().__init__()
        self.inactive_image = pygame.Surface((32, 64), pygame.SRCALPHA)
        pygame.draw.rect(self.inactive_image, (80, 120, 200, 150), self.inactive_image.get_rect(), border_radius=4)
        self.active_image = pygame.Surface((32, 64), pygame.SRCALPHA)
        pygame.draw.rect(self.active_image, (100, 220, 255), self.active_image.get_rect(), border_radius=4)
        pygame.draw.rect(self.active_image, (255, 255, 255), self.active_image.get_rect().inflate(-8, -8), border_radius=4)
        self.image = self.inactive_image
        self.rect = self.image.get_rect()
        self.rect.x = x - 16  # Center horizontally
        self.rect.y = y
        self.active = False
        
    def activate(self):
        """Activates this checkpoint."""
        self.active = True
        self.image = self.active_image
        
    def update(self):
        """Updates the checkpoint's animation."""
        if self.active:
            # Add subtle glow animation
            alpha = 128 + math.sin(time.time() * 5) * 60
            self.image.set_alpha(int(alpha))




@dataclass
class LevelContent:
    platforms: pygame.sprite.Group = field(default_factory=pygame.sprite.Group)
    enemies: pygame.sprite.Group = field(default_factory=pygame.sprite.Group)
    coins: pygame.sprite.Group = field(default_factory=pygame.sprite.Group)
    spikes: pygame.sprite.Group = field(default_factory=pygame.sprite.Group)
    specials: pygame.sprite.Group = field(default_factory=pygame.sprite.Group)
    checkpoints: pygame.sprite.Group = field(default_factory=pygame.sprite.Group)
    goal: Optional[Goal] = None
    boss: Optional[Boss] = None
    boss_projectiles: pygame.sprite.Group = field(default_factory=pygame.sprite.Group)
    min_y: float = 0
    max_y: float = SCREEN_HEIGHT
    min_x: float = 0
    max_x: float = SCREEN_WIDTH
    _spawn_cells: Dict[Tuple[int, int], Set[str]] = field(default_factory=dict)

    def _cells_for(self, x: float, y: float, radius: float) -> Iterable[Tuple[int, int]]:
        cell_size = 32
        min_x = int((x - radius) // cell_size)
        max_x = int((x + radius) // cell_size)
        min_y = int((y - radius) // cell_size)
        max_y = int((y + radius) // cell_size)
        for cx in range(min_x, max_x + 1):
            for cy in range(min_y, max_y + 1):
                yield (cx, cy)

    def reserve_area(self, tag: str, x: float, y: float, radius: float, force: bool = False) -> bool:
        protected = {"platform", "boss", "portal"}
        cells = list(self._cells_for(x, y, radius))
        if not force and tag not in protected:
            for cell in cells:
                occupants = self._spawn_cells.get(cell)
                if occupants and occupants.intersection({"platform", "boss", "portal", "enemy", "coin", "special", "hazard"}):
                    return False

        for cell in cells:
            self._spawn_cells.setdefault(cell, set()).add(tag)
        return True

    def reserve_rect(self, tag: str, rect: pygame.Rect, force: bool = False) -> bool:
        radius = max(rect.width, rect.height) / 2
        return self.reserve_area(tag, rect.centerx, rect.centery, radius, force)


def create_world_object(world: int, x: int, y: int) -> pygame.sprite.Sprite:
    options = WORLD_THEME_OBJECTS.get(world) or [WORLD_SPECIALS.get(world, "coin")]
    name = random.choice(options)
    if name == "spike":
        return Spike(x, y, world=world)
    if name == "rock":
        return FallingRock(x, y)
    if name == "quicksand":
        return QuicksandTile(x, y)
    if name == "icicle":
        return Icicle(x, y)
    if name == "lava":
        return LavaBubble(x, y, world=world)
    if name == "wind":
        return WindOrb(x, y, world=world)
    if name == "electric":
        return ElectricTile(x, y)
    if name == "ghost":
        return GhostOrb(x, y)
    if name == "glitch":
        return GlitchCube(x, y)
    return Coin(x, y)



# ---------------------------------------------------------------------------
# Menu primitives
# ---------------------------------------------------------------------------

def _draw_glitch_overlay(surface: pygame.Surface) -> None:
    # Shared glitch pops/scanlines used by pause and settings menus
    if random.random() < 0.18:
        for _ in range(random.randint(2, 5)):
            w = random.randint(60, 320)
            h = random.randint(8, 32)
            x = random.randint(0, SCREEN_WIDTH - w)
            y = random.randint(0, SCREEN_HEIGHT - h)
            color = (
                random.randint(180, 255),
                random.randint(0, 255),
                random.randint(180, 255),
                random.randint(80, 180),
            )
            glitch_rect = pygame.Surface((w, h), pygame.SRCALPHA)
            glitch_rect.fill(color)
            surface.blit(glitch_rect, (x, y), special_flags=pygame.BLEND_RGBA_ADD)
    if random.random() < 0.12:
        for _ in range(random.randint(2, 6)):
            y = random.randint(0, SCREEN_HEIGHT - 1)
            color = (
                random.randint(180, 255),
                random.randint(0, 255),
                random.randint(180, 255),
                random.randint(60, 120),
            )
            pygame.draw.rect(surface, color, (0, y, SCREEN_WIDTH, random.randint(2, 6)))


# === Menus / cutscenes ===
def run_settings_menu(game: "Game", title: str = "SETTINGS") -> None:
    def toggle_music() -> None:
        enabled = game.settings.toggle("music")
        if not enabled:
            game.stop_music()
        else:
            if getattr(game, "_last_music", None):
                # Resume from last position if available
                pos = getattr(game, "_music_resume_pos", 0.0)
                game.play_music(str(game._last_music), start=pos)

    def toggle_sfx() -> None:
        enabled = game.settings.toggle("sfx")
        if not enabled:
            game.sound.stop_all()

    def toggle_glitch() -> None:
        game.settings.toggle("glitch_fx")

    def cycle_window_mode() -> None:
        current = str(game.settings["window_mode"]).lower()
        try:
            index = WINDOW_MODES.index(current)
        except ValueError:
            index = 0
        next_mode = WINDOW_MODES[(index + 1) % len(WINDOW_MODES)]
        game.settings.set("window_mode", next_mode)
        game.apply_window_mode(next_mode)

    menu = VerticalMenu(
        [
            MenuEntry(
                lambda: f"Music: {'On' if game.settings['music'] else 'Off'}",
                toggle_music,
            ),
            MenuEntry(
                lambda: f"Sound FX: {'On' if game.settings['sfx'] else 'Off'}",
                toggle_sfx,
            ),
            MenuEntry(
                lambda: f"Glitch FX: {'On' if game.settings['glitch_fx'] else 'Off'}",
                toggle_glitch,
            ),
            MenuEntry(
                lambda: f"Display Mode: {WINDOW_MODE_LABELS.get(str(game.settings['window_mode']).lower(), 'Windowed')}",
                cycle_window_mode,
            ),
            MenuEntry(lambda: "Back", lambda: "exit"),
        ],
        sound=game.sound,
    )

    key_map = game.settings.data if hasattr(game.settings, 'data') else game.settings
    back_keys = set([
        key_map.get("back", pygame.K_ESCAPE),
        key_map.get("pause", pygame.K_ESCAPE),
        pygame.K_ESCAPE
    ])
    while game.running:
        # Poll controller so menu navigation works on gamepads even outside the main loop
        game._poll_controller()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return
            if event.type == pygame.KEYDOWN and event.key in back_keys:
                pygame.event.clear((pygame.KEYDOWN, pygame.KEYUP))
                return
            result = menu.handle_event(event)
            if callable(result):
                # If a menu entry returns a callable, treat it as a new menu to open
                return result()
            if result == "exit":
                pygame.event.clear((pygame.KEYDOWN, pygame.KEYUP))
                return


        # Settings background: solid black always
        game.screen.fill((0, 0, 0))

        if game.settings["glitch_fx"]:
            _draw_glitch_overlay(game.screen)

        # Glitchy title and menu text only if glitch_fx is enabled
        title_font = game.assets.font(54, True)
        draw_glitch_text(game.screen, title_font, title, 140, WHITE, game.settings["glitch_fx"])
        menu.draw(game.screen, game.assets, SCREEN_HEIGHT // 2 + 40, game.settings["glitch_fx"])

        # No info at the bottom

        pygame.display.flip()
        game.clock.tick(FPS)


def run_pause_menu(scene: "GameplayScene") -> str:
    result_holder = {"value": "resume"}

    def resume() -> str:
        result_holder["value"] = "resume"
        return "exit"

    def open_settings() -> None:
        run_settings_menu(scene.game, title="SETTINGS")

    def open_shops() -> str:
        result_holder["value"] = "shops"
        return "exit"

    def to_menu() -> str:
        result_holder["value"] = "menu"
        return "exit"

    def quit_game() -> str:
        result_holder["value"] = "quit"
        return "exit"

    menu = VerticalMenu(
        [
            MenuEntry(lambda: "Resume", resume),
            MenuEntry(lambda: "Settings", lambda: open_settings()),
            MenuEntry(lambda: "Shops", open_shops),
            MenuEntry(lambda: "Main Menu", to_menu),
            MenuEntry(lambda: "Quit Game", quit_game),
        ],
        sound=scene.game.sound,
    )
    menu.panel_color = (20, 30, 55, 230)
    menu.panel_border_color = (200, 220, 255)

    scene.game.pause_speedrun(True)
    # Do not clear flight cheat; gameplay will reapply if enabled
    if hasattr(scene, 'player') and hasattr(scene.player, 'disable_flight'):
        scene.player.disable_flight()

    while scene.game.running:
        # Poll controller so pause menu can be driven by gamepads
        scene.game._poll_controller()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                scene.game.quit()
                scene.game.pause_speedrun(False)
                return "quit"
            result = menu.handle_event(event)
            if callable(result):
                return result()
            if result == "exit":
                scene.game.pause_speedrun(False)
                return result_holder["value"]

        # Solid black background
        scene.game.screen.fill((0, 0, 0))

        if scene.game.settings["glitch_fx"]:
            _draw_glitch_overlay(scene.game.screen)

        # Large, glitchy title
        title_font = scene.game.assets.font(54, True)
        draw_glitch_text(
            scene.game.screen,
            title_font,
            "PAUSED",
            140,
            WHITE,
            scene.game.settings["glitch_fx"],
        )

        # Glitchy menu text if glitch_fx is enabled
        menu.draw(
            scene.game.screen,
            scene.game.assets,
            SCREEN_HEIGHT // 2 + 40,
            scene.game.settings["glitch_fx"],
        )
        if scene.game.settings["glitch_fx"]:
            # Add subtle scanlines and RGB split over the UI area to match glitch theme
            _draw_glitch_overlay(scene.game.screen)

        # No info at the bottom

        pygame.display.flip()
        scene.game.clock.tick(FPS)

    scene.game.pause_speedrun(False)
    return "quit"


# ---------------------------------------------------------------------------
# Cutscenes
# ---------------------------------------------------------------------------


def play_glitch_portal_cutscene(game: "Game") -> None:
    game.pause_speedrun(True)
    game.sound.play_event("glitch")
    glitch_flash(game.screen, game.clock, 0.25, game.settings["glitch_fx"])
    for frame in range(180):
        game.screen.fill((random.randint(0, 50), 0, random.randint(0, 50)))
        for i in range(10):
            pygame.draw.circle(
                game.screen,
                (random.randint(100, 255), 0, random.randint(100, 255)),
                (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2),
                60 + i * 4,
                1,
            )
        if frame > 90:
            draw_glitch_text(
                game.screen,
                game.assets.font(36, True),
                "REALITY FRACTURED",
                SCREEN_HEIGHT // 2,
                WHITE,
                game.settings["glitch_fx"],
            )
        pygame.display.flip()
        game.clock.tick(FPS)
    game.pause_speedrun(False)

def play_first_entry_cutscene(game: "Game") -> None:
    """
    New opening cutscene: diagnostics -> portal spin-up -> reality breach.
    Skippable via keyboard/mouse/controller after text appears.
    """
    # Clear any lingering input suppression so A/Start works immediately
    game._suppress_accept_until = 0.0
    # Ensure no stale suppression blocks the prompt
    game._suppress_accept_until = 0.0
    game.pause_speedrun(True)
    clock = game.clock
    try:
        game.sound.play_event("world_transition")
    except Exception:
        pass

    background = game.assets.background(1)
    overlay = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
    portal_tex = game.assets.portal_texture(10)
    title_font = game.assets.font(46, True)
    body_font = game.assets.font(24, False)
    hint_font = game.assets.font(18, False)

    beats = [
        ("Signal Found: Node W1", 0.0),
        ("Stability: CRITICAL ??? Portal bootstrapping...", 1.4),
        ("Objective: Reach the tower core before collapse.", 2.8),
    ]
    start_time = time.time()
    duration = 7.5
    can_skip = False
    last_device = game.last_input_device

    while game.running:
        elapsed = time.time() - start_time
        if elapsed >= duration:
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                game.pause_speedrun(False)
                return
            # Always allow immediate accept via controller/keyboard/mouse once this scene is active
            if event.type == pygame.JOYBUTTONDOWN and event.button in (0, 7):
                elapsed = duration
                break
            if event.type in (pygame.KEYDOWN, pygame.KEYUP):
                last_device = "keyboard"
                game.last_input_device = "keyboard"
            elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYAXISMOTION, pygame.JOYHATMOTION):
                last_device = "controller"
                game.last_input_device = "controller"
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                last_device = "mouse"
                game.last_input_device = "mouse"
            if can_skip and (
                event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.JOYBUTTONDOWN)
                or (event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.5)
                or (event.type == pygame.JOYHATMOTION and event.value != (0, 0))
            ):
                elapsed = duration  # force exit after drawing once
                break

        # Fallback: if the event queue missed it, poll device states when skipping is allowed
        if can_skip:
            keys = pygame.key.get_pressed()
            mouse_buttons = pygame.mouse.get_pressed(num_buttons=3)
            controller_pressed = False
            for js in game.gamepads:
                try:
                    if any(js.get_button(i) for i in range(js.get_numbuttons())):
                        controller_pressed = True
                        break
                    if js.get_numhats() > 0:
                        hx, hy = js.get_hat(0)
                        if hx != 0 or hy != 0:
                            controller_pressed = True
                            break
                    # Consider strong stick tilt as intent to continue
                    if js.get_numaxes() >= 2:
                        if abs(js.get_axis(0)) > 0.6 or abs(js.get_axis(1)) > 0.6:
                            controller_pressed = True
                            break
                except Exception:
                    continue
            if (
                any(keys)
                or any(mouse_buttons)
                or controller_pressed
            ):
                elapsed = duration

        # Base layer
        game.screen.blit(background, (0, 0))

        # Darken and color tint
        overlay.fill((8, 16, 24, 190))
        game.screen.blit(overlay, (0, 0))

        # Portal spin-up
        pulse = 1.0 + 0.15 * math.sin(elapsed * 7.5)
        portal_scale = max(0.4, 1.3 - elapsed * 0.08)
        portal_surf = pygame.transform.smoothscale(
            portal_tex,
            (
                max(10, int(portal_tex.get_width() * portal_scale * pulse)),
                max(10, int(portal_tex.get_height() * portal_scale * pulse)),
            ),
        )
        portal_rect = portal_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        game.screen.blit(portal_surf, portal_rect, special_flags=pygame.BLEND_ADD)

        # Glitch/scanlines
        if game.settings["glitch_fx"]:
            _draw_glitch_overlay(game.screen)

        # Header
        header_alpha = min(255, int(max(0.0, elapsed / 0.5) * 255))
        header = title_font.render("BOOTSTRAPPING REALITY COLLAPSING", True, WHITE)
        header.set_alpha(header_alpha)
        game.screen.blit(header, header.get_rect(center=(SCREEN_WIDTH // 2, 140)))

        # Beat text
        for idx, (text, delay) in enumerate(beats):
            if elapsed >= delay:
                alpha = min(255, int(min(1.0, (elapsed - delay) / 0.7) * 255))
                render = body_font.render(text, True, WHITE)
                render.set_alpha(alpha)
                y = 240 + idx * 52
                game.screen.blit(render, render.get_rect(center=(SCREEN_WIDTH // 2, y)))

        # Hint
        # No hint text; cutscene ends on input without on-screen prompt

        # Subtle vignette
        vignette = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        for i in range(10):
            alpha = int(8 * (i + 1))
            pygame.draw.rect(vignette, (0, 0, 0, alpha), (i * 6, i * 6, SCREEN_WIDTH - i * 12, SCREEN_HEIGHT - i * 12), width=6)
        game.screen.blit(vignette, (0, 0))

        pygame.display.flip()
        clock.tick(FPS)

    # Suppress immediate accept in the next scene and clear any leftover inputs
    game._suppress_accept_until = time.time() + 0.4
    pygame.event.clear()
    game.pause_speedrun(False)
def play_final_cutscene(game: "Game") -> None:
    game.pause_speedrun(True)
    # Use SoundManager for SFX
    rumble_playing = False
    boom_played = False
    wind_played = False
    if game.settings["sfx"]:
        game.sound.play_event("collapse_rumble", loops=-1)
        rumble_playing = True

    blocks = [
        pygame.Rect(
            random.randint(0, SCREEN_WIDTH),
            random.randint(0, SCREEN_HEIGHT),
            20,
            20,
        )
        for _ in range(100)
    ]
    cracks: List[List[Tuple[int, int]]] = []
    start_time = time.time()
    shake_timer = 0
    zoom_factor = 1.0
    phase = 0
    # boom_played and wind_played already set above

    while game.running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                game.pause_speedrun(False)
                return

        elapsed = time.time() - start_time
        frame = pygame.Surface(SCREEN_SIZE)
        frame.fill((10, 10, 20))

        for idx, rect in enumerate(blocks):
            if idx % 2 == 0:
                rect.x += random.choice([-2, -1, 1, 2])
                rect.y += random.choice([-2, -1, 1, 2])
            pygame.draw.rect(
                frame,
                (
                    random.randint(80, 255),
                    random.randint(0, 255),
                    random.randint(80, 255),
                ),
                rect,
            )

        if elapsed > 3 and len(cracks) < 30 and random.random() < 0.15:
            cracks.append(
                [
                    (
                        random.randint(0, SCREEN_WIDTH),
                        random.randint(0, SCREEN_HEIGHT),
                    )
                ]
            )
        for crack in cracks:
            if len(crack) < 8 and random.random() < 0.25:
                last = crack[-1]
                crack.append(
                    (
                        last[0] + random.randint(-25, 25),
                        last[1] + random.randint(-25, 25),
                    )
                )
            if len(crack) >= 2:
                pygame.draw.lines(frame, WHITE, False, crack, 2)

        if elapsed > 8 and phase == 0:
            if rumble_playing:
                game.sound.stop_all()
                rumble_playing = False
            game.sound.play_event("collapse_explosion")
            shake_timer = 90
            zoom_factor = 1.4
            phase = 1
            fade_start = time.time()

        if phase >= 1:
            fade_elapsed = time.time() - fade_start
            offset = (
                random.randint(-6, 6),
                random.randint(-6, 6),
            ) if shake_timer > 0 else (0, 0)
            shake_timer = max(0, shake_timer - 1)

            zoomed = pygame.transform.smoothscale(
                frame,
                (
                    int(SCREEN_WIDTH * zoom_factor),
                    int(SCREEN_HEIGHT * zoom_factor),
                ),
            )
            game.screen.fill(BLACK)
            game.screen.blit(
                zoomed,
                (
                    (SCREEN_WIDTH - zoomed.get_width()) // 2 + offset[0],
                    (SCREEN_HEIGHT - zoomed.get_height()) // 2 + offset[1],
                ),
            )

            if fade_elapsed > 0.3 and not boom_played:
                game.sound.play_event("collapse_boom")
                boom_played = True
                for _ in range(60):
                    x = random.randint(0, SCREEN_WIDTH)
                    y = random.randint(0, SCREEN_HEIGHT)
                    pygame.draw.circle(
                        game.screen,
                        (255, random.randint(80, 200), 0),
                        (x, y),
                        random.randint(3, 8),
                    )
            # Play wind/ethereal sound at fadeout
            if fade_elapsed > 4.5 and not wind_played:
                game.sound.play_event("collapse_wind")
                wind_played = True

            if fade_elapsed < 1.5:
                flash = pygame.Surface(SCREEN_SIZE)
                flash.fill((255, 255, 255))
                flash.set_alpha(int(255 * (1 - fade_elapsed / 1.5)))
                game.screen.blit(flash, (0, 0))

            if fade_elapsed > 2.0:
                zoom_factor += 0.02
            if fade_elapsed > 5.0:
                fade = pygame.Surface(SCREEN_SIZE)
                fade.fill((255, 255, 255))
                # Fully white fade faster and to 100%
                fade.set_alpha(int(255 * min((fade_elapsed - 5.0) / 1.0, 1)))
                game.screen.blit(fade, (0, 0))
                if fade_elapsed > 6.5:
                    break
        else:
            game.screen.blit(frame, (0, 0))

        pygame.display.flip()
        game.clock.tick(40)

    game.sound.stop_all()
    game.pause_speedrun(False)


def conclude_campaign(game: "Game") -> None:
    """Run the finale sequence and return the player to the victory screen."""
    play_final_cutscene(game)
    game.progress.reset()
    if SAVE_FILE.exists():
        try:
            SAVE_FILE.unlink()
        except Exception as exc:
            print(f"[Save] Failed to clear save file: {exc}")
    # Go to credits scene after the finale
    # Go to title screen after the finale
    game.change_scene(TitleScene)


class DevConsole:

    def _handle_active_key(self, event):
        # Robust key handling for console input
        if event.key == pygame.K_ESCAPE:
            self._close()
        elif event.key == pygame.K_RETURN:
            self._execute_current_line()
        elif event.key == pygame.K_BACKSPACE:
            self.input_buffer = self.input_buffer[:-1]
        elif event.key == pygame.K_TAB:
            self._autocomplete()
        elif event.key == pygame.K_UP:
            self._history_up()
        elif event.key == pygame.K_DOWN:
            self._history_down()
        # Ignore other control keys
        elif event.key < 256 and not event.mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT):
            # Only add printable ASCII
            char = event.unicode
            if char and char.isprintable():
                self.input_buffer += char

    def _autocomplete(self):
        # Simple autocomplete for commands
        if not self.input_buffer:
            return
        matches = [cmd for cmd in self.commands if cmd.startswith(self.input_buffer)]
        if matches:
            self.input_buffer = matches[0]

    def _history_up(self):
        if not self.history:
            return
        if not hasattr(self, '_history_index'):
            self._history_index = len(self.history)
        self._history_index = max(0, self._history_index - 1)
        self.input_buffer = self.history[self._history_index][0].lstrip('> ').strip()

    def _history_down(self):
        if not self.history or not hasattr(self, '_history_index'):
            return
        self._history_index = min(len(self.history) - 1, self._history_index + 1)
        self.input_buffer = self.history[self._history_index][0].lstrip('> ').strip()
        if self._history_index == len(self.history) - 1:
            self.input_buffer = ''

    BG_COLOR = (12, 14, 28)
    HEADER_COLOR = (110, 170, 255)
    DIVIDER_COLOR = (70, 90, 140)
    PROMPT_COLOR = (195, 230, 255)
    TEXT_COLOR = (230, 230, 240)
    ERROR_COLOR = (255, 120, 120)
    INFO_COLOR = (160, 220, 180)

    def __init__(self, game):
        self.game = game
        self.active = False
        self.input_buffer = ""
        self.history = []
        self.max_history = 100
        self._blink_timer = 0.0
        self._blink_visible = True
        self.vertical_anchor = 0.0
        self._anchor_target = 0.0
        self._anchor_speed = 6.0
        self._code_buffer = []
        self.unlocked = False  # Set to True after secret code is entered once
        self.dragging = False
        self.commands = {
            "/help": (self._cmd_help, "List all commands"),
            "/clear": (self._cmd_clear, "Clear the console history"),
            "/close": (self._cmd_close, "Close the console"),
            "/setworld": (self._cmd_setworld, "Go to a specific world/level: /setworld <world> [level]"),
            "/levelselect": (self._cmd_levelselect, "Open the level select screen"),
            # ...existing code...
        }

    def _open(self) -> None:
        self.active = True
        pygame.key.start_text_input()
        self.input_buffer = ""
        self._anchor_target = 1.0
        try:
            # When console is opened, suppress immediate subsequent ESC handling by the game
            self.game._suppress_escape_until = time.time() + 0.25
        except Exception:
            pass

    def _update_code_sequence(self, key: int) -> bool:
        self._code_buffer.append(key)
        max_len = len(DEV_CONSOLE_CODE)
        if len(self._code_buffer) > max_len:
            self._code_buffer = self._code_buffer[-max_len:]
        if self._code_buffer == DEV_CONSOLE_CODE:
            self._code_buffer.clear()
            self.unlocked = True
            if not self.active:
                self._open()
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        width, height = surface.get_size()
        console_height = min(260, max(220, int(height * 0.45)))
        movable_space = max(0, height - console_height)
        anchor = max(0.0, min(1.0, self.vertical_anchor))
        top_offset = int((1.0 - anchor) * movable_space)
        rect = pygame.Rect(0, top_offset, width, console_height)
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill((*self.BG_COLOR, 228))

        header_font = self.game.assets.font(20, True)
        body_font = self.game.assets.font(18, False)
        hint_font = self.game.assets.font(16, False)

        padding = 14
        header = header_font.render("Developer Console", True, self.HEADER_COLOR)
        overlay.blit(header, (padding, padding))

        divider_y = padding + header.get_height() + 6
        pygame.draw.line(overlay, self.DIVIDER_COLOR, (padding, divider_y), (rect.width - padding, divider_y), 1)

        y = divider_y + 10
        for text, color in self.history[-self.max_history :]:
            render = body_font.render(text, True, color)
            overlay.blit(render, (padding, y))
            y += render.get_height() + 4

        prompt_text = f"> {self.input_buffer}"
        if self._blink_visible:
            prompt_text += "_"
        prompt_render = body_font.render(prompt_text, True, self.PROMPT_COLOR)
        prompt_y = rect.height - padding - prompt_render.get_height()
        overlay.blit(prompt_render, (padding, prompt_y))

        hint_lines = [
            "ENTER run | ESC close | TAB autocomplete",
            "PgUp/PgDn move console | HOME top | END bottom",
        ]
        hint_y = prompt_y - 6
        for text in hint_lines:
            hint_y -= hint_font.get_height()
            draw_prompt_with_icons(
                overlay,
                hint_font,
                text,
                hint_y + hint_font.get_height() // 2,
                (150, 180, 210),
                device="keyboard",
                x=padding,
            )

        surface.blit(overlay, rect.topleft)
    def update(self, dt: float) -> None:
        if not self.active:
            return
        self._blink_timer += dt
        if self._blink_timer >= 0.5:
            self._blink_timer = 0.0
            self._blink_visible = not self._blink_visible
        if abs(self.vertical_anchor - self._anchor_target) > 1e-4:
            delta = self._anchor_speed * dt
            if self.vertical_anchor < self._anchor_target:
                self.vertical_anchor = min(self._anchor_target, self.vertical_anchor + delta)
            else:
                self.vertical_anchor = max(self._anchor_target, self.vertical_anchor - delta)
    def handle_event(self, event: pygame.event.Event) -> bool:
        # Failsafe: ensure dragging attribute always exists
        if not hasattr(self, 'dragging'):
            self.dragging = False
        # Activation: backtick/tilde key
        if event.type == pygame.KEYDOWN:
            if not self.active and event.key == getattr(pygame, 'K_BACKQUOTE', None):
                self._open()
                return True
            if self.active:
                self._handle_active_key(event)
                return True
        elif event.type == pygame.TEXTINPUT:
            if self.active and event.text:
                self.input_buffer += event.text
                return True
        return False
    """Developer console for executing debug commands."""

    BG_COLOR = (12, 14, 28)
    HEADER_COLOR = (110, 170, 255)
    DIVIDER_COLOR = (70, 90, 140)
    PROMPT_COLOR = (195, 230, 255)
    TEXT_COLOR = (230, 230, 240)
    ERROR_COLOR = (255, 120, 120)
    INFO_COLOR = (160, 220, 180)

    def __init__(self, game):
        self.game = game
        self.active = False
        self.input_buffer = ""
        self.history = []
        self.max_history = 100
        self._blink_timer = 0.0
        self._blink_visible = True
        self.vertical_anchor = 0.0
        self._anchor_target = 0.0
        self._anchor_speed = 6.0
        self._code_buffer = []
        self.unlocked = False  # Set to True after secret code is entered once
        self.commands = {
            "/help": (self._cmd_help, "List all commands"),
            "/clear": (self._cmd_clear, "Clear the console history"),
            "/close": (self._cmd_close, "Close the console"),
            "/setworld": (self._cmd_setworld, "Go to a specific world/level: /setworld <world> [level]"),
            "/levelselect": (self._cmd_levelselect, "Open the level select screen"),
            "/heal": (self._cmd_heal, "Restore player health"),
            "/flight": (self._cmd_flight, "Toggle or set flight: /flight [on|off]"),
            "/skipboss": (self._cmd_skipboss, "Defeat the current boss instantly"),
            "/glitchfx": (self._cmd_glitchfx, "Toggle glitch FX"),
            "/music": (self._cmd_music, "Play or stop music: /music <track|stop>"),
            "/where": (self._cmd_where, "Show current scene/world/level info"),
            "/spawn": (self._cmd_spawn, "Spawn an enemy, coin, or spike: /spawn <enemy|coin|spike> [x] [y]"),
            "/leveleditor": (self._cmd_leveleditor, "Open the level editor (developer only)"),
        }
    def _cmd_leveleditor(self, _args: list) -> str:
        # Enable in-place editing of the current level without switching scenes
        scene = self.game.scene
        if not hasattr(scene, 'enable_level_editing'):
            return "Level editing is only available during gameplay."
        try:
            scene.enable_level_editing()
            return "Level editor enabled for current level."
        except Exception as exc:
            return f"Failed to enable level editor: {exc}"


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log(self, text: str, color: Optional[Tuple[int, int, int]] = None) -> None:
        self.history.append((text, color or self.TEXT_COLOR))
        if len(self.history) > 120:
            self.history = self.history[-120:]

    def _update_code_sequence(self, key: int) -> bool:
        self._code_buffer.append(key)
        max_len = len(DEV_CONSOLE_CODE)
        if len(self._code_buffer) > max_len:
            self._code_buffer = self._code_buffer[-max_len:]
        if self._code_buffer == DEV_CONSOLE_CODE:
            self._code_buffer.clear()
            if not self.active:
                self._open()
            return True
        return False

        self._log("Commands: " + ", ".join(sorted(self.commands)), self.INFO_COLOR)

    def _close(self) -> None:
        pygame.key.stop_text_input()
        self.active = False
        self.input_buffer = ""
        self._anchor_target = 0.0
        try:
            # When console is closed via ESC, suppress immediate subsequent ESC handling by the game
            self.game._suppress_escape_until = time.time() + 0.25
        except Exception:
            pass

    def _execute_current_line(self) -> None:
        line = self.input_buffer
        self._log(f"> {line}", self.PROMPT_COLOR)
        stripped = line.strip()
        self.input_buffer = ""
        if not stripped:
            return

        parts = stripped.split()
        command = parts[0].lower()
        args = parts[1:]
        # Require / prefix for all commands
        if not command.startswith("/"):
            error_msg = f"Commands must start with '/'. Try '/help'."
            self._log(error_msg, self.ERROR_COLOR)
            print(f"[DevConsole] {error_msg}")
            return
        entry = self.commands.get(command)
        if not entry:
            error_msg = f"Unknown command: {command}"
            self._log(error_msg, self.ERROR_COLOR)
            print(f"[DevConsole] {error_msg}")
            return
        handler, _ = entry
        try:
            result = handler(args)
            if isinstance(result, (list, tuple)):
                for item in result:
                    self._log(str(item), self.INFO_COLOR)
            elif result:
                self._log(str(result), self.INFO_COLOR)
        except Exception as exc:
            error_msg = f"Command failed: {exc}"
            self._log(error_msg, self.ERROR_COLOR)
            print(f"[DevConsole] {error_msg}")

    def _autocomplete(self) -> None:
        fragment = self.input_buffer.strip()
        if not fragment:
            return
        matches = [name for name in self.commands if name.startswith(fragment.lower())]
        if len(matches) == 1:
            self.input_buffer = matches[0] + " "
        elif matches:
            self._log("Matches: " + ", ".join(matches), self.INFO_COLOR)

    def _adjust_vertical_anchor(self, delta: float) -> None:
        self._anchor_target = max(0.0, min(1.0, self._anchor_target + delta))

    # ------------------------------------------------------------------
    # Command implementations
    # ------------------------------------------------------------------

    def _cmd_help(self, _args: List[str]) -> List[str]:
        lines = []
        for name, (_, desc) in sorted(self.commands.items()):
            lines.append(f"{name} - {desc}")
        return lines

    def _cmd_clear(self, _args: List[str]) -> None:
        self.history.clear()
        self._log("History cleared.", self.INFO_COLOR)

    def _cmd_close(self, _args: List[str]) -> str:
        self._close()
        return "Console closed."

    def _cmd_setworld(self, args: List[str]) -> str:
        if not args:
            return "Usage: setworld <world> [level]"
        try:
            world = int(args[0])
            level = int(args[1]) if len(args) > 1 else 1
        except ValueError:
            return "World and level must be numbers."
        world = max(1, min(10, world))
        level = max(1, min(10, level))
        self.game.change_scene(GameplayScene, world=world, level=level)
        return f"Loading world {world}, level {level}."

    def _cmd_levelselect(self, _args: List[str]) -> str:
        self.game.change_scene(LevelSelectScene)
        return "Opening level select."

    def _cmd_heal(self, _args: List[str]) -> str:
        scene = self.game.scene
        player = getattr(scene, "player", None)
        if not player or not hasattr(player, "health"):
            return "No player to heal."
        player.health = player.max_health
        if hasattr(player, "invuln_frames"):
            player.invuln_frames = 0
        return "Player health restored."

    def _cmd_flight(self, args: List[str]) -> str:
        scene = self.game.scene
        player = getattr(scene, "player", None)
        if not player or not hasattr(player, "enable_flight"):
            return "No controllable player in this scene."
        state = args[0].lower() if args else "toggle"
        if state in {"on", "enable"}:
            player.enable_flight()
            return "Flight enabled."
        if state in {"off", "disable"}:
            player.disable_flight()
            return "Flight disabled."
        if getattr(player, "can_fly", False):
            player.disable_flight()
            return "Flight disabled."
        player.enable_flight()
        return "Flight enabled."

    def _cmd_skipboss(self, _args: List[str]) -> str:
        scene = self.game.scene
        if isinstance(scene, BossArenaScene):
            scene._handle_boss_defeated()
            return "Boss defeated."
        return "Not currently in a boss arena."

    def _cmd_glitchfx(self, _args: List[str]) -> str:
        new_value = self.game.settings.toggle("glitch_fx")
        return f"Glitch FX {'enabled' if new_value else 'disabled'}."

    def _cmd_music(self, args: List[str]) -> str:
        if not args:
            return "Usage: music <track|stop>"
        if args[0].lower() == "stop":
            self.game.stop_music()
            return "Music stopped."
        track = args[0]
        # Only allow .mp3 for music
        if not track.endswith(".mp3"):
            track += ".mp3"
        self.game.play_music(track)
        return f"Playing {track}."

    def _cmd_where(self, _args: List[str]) -> List[str]:
        scene = self.game.scene
        lines = [f"Scene: {scene.__class__.__name__}"]
        if isinstance(scene, GameplayScene):
            lines.append(f"World {scene.world}, Level {scene.level}")
        elif isinstance(scene, BossArenaScene):
            lines.append(f"Boss Arena - World {scene.world}, Level {scene.level}")
        return lines

    def _cmd_spawn(self, args: List[str]) -> str:
        if not args:
            return "Usage: spawn <enemy|coin|spike> [x] [y]"
        scene = self.game.scene
        if not isinstance(scene, GameplayScene):
            return "Spawn command is only available during gameplay."

        spawn_type = args[0].lower()
        player = getattr(scene, "player", None)
        default_x, default_y = (scene.player.rect.center if player else (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))

        try:
            x = int(args[1]) if len(args) > 1 else default_x
            y = int(args[2]) if len(args) > 2 else default_y
        except ValueError:
            return "Coordinates must be numbers."

        spawned: Optional[pygame.sprite.Sprite] = None
        if spawn_type == "enemy":
            spawned = create_enemy(x - 16, y - 24, scene.world, speed=2, assets=self.game.assets)
            scene.content.enemies.add(spawned)
        elif spawn_type == "coin":
            spawned = Coin(x, y)
            scene.content.coins.add(spawned)
        elif spawn_type in {"spike", "hazard"}:
            spawned = Spike(x - 16, y - 16, world=scene.world)
            scene.content.spikes.add(spawned)
        else:
            return "Supported spawn types: enemy, coin, spike"

        return f"Spawned {spawn_type} at ({spawned.rect.centerx}, {spawned.rect.centery})."

# ---------------------------------------------------------------------------
# Level Generation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScalarRange:
    easy: float
    hard: float

    def lerp(self, t: float) -> float:
        return self.easy + (self.hard - self.easy) * t


@dataclass(frozen=True)
class GeneratorSettings:
    gap_min: ScalarRange = ScalarRange(80, 170)
    gap_max: ScalarRange = ScalarRange(130, 240)
    width_min: ScalarRange = ScalarRange(140, 90)
    width_max: ScalarRange = ScalarRange(200, 150)
    vertical_variance: ScalarRange = ScalarRange(50, 160)
    section_count: ScalarRange = ScalarRange(8, 16)
    branch_chance: ScalarRange = ScalarRange(0.05, 0.2)
    collectible_rate: ScalarRange = ScalarRange(0.5, 0.25)
    hazard_rate: ScalarRange = ScalarRange(0.1, 0.38)
    world_object_rate: ScalarRange = ScalarRange(0.06, 0.26)
    moving_rate: ScalarRange = ScalarRange(0.04, 0.24)
    blinking_rate: ScalarRange = ScalarRange(0.0, 0.14)
    checkpoint_interval: ScalarRange = ScalarRange(1200, 600)
    min_platform_y: int = 140
    max_platform_y: int = SCREEN_HEIGHT - 140
    base_platform_height: int = 32
    rng_seed: Optional[int] = None


@dataclass(frozen=True)
class WorldRule:
    hazard_keys: Tuple[str, ...]
    vertical_bias: float = 0.0
    gap_multiplier: float = 1.0
    object_multiplier: float = 1.0


class LevelGenerator:

    def generate_from_dict(self, data: dict) -> LevelContent:
        # Create a LevelContent from editor JSON data
        content = LevelContent()
        # Platforms
        for plat in data.get("platforms", []):
            x, y, w, h = plat["x"], plat["y"], plat["w"], plat["h"]
            p = Platform(x, y, w, h, world=1, assets=self.assets)
            content.platforms.add(p)
        # Enemies
        for enemy in data.get("enemies", []):
            x, y, w, h = enemy["x"], enemy["y"], enemy["w"], enemy["h"]
            # Use create_enemy for world-specific enemy
            e = create_enemy(x, y, 1, speed=2, assets=self.assets)
            content.enemies.add(e)
        # Specials (objects)
        for obj in data.get("specials", []):
            x, y, w, h = obj["x"], obj["y"], obj["w"], obj["h"]
            s = SpecialTile(x, y, w, h, world_num=1, asset_cache=self.assets)
            content.specials.add(s)
        # Goal
        if data.get("goal"):
            g = data["goal"]
            content.goal = Goal(g["x"], g["y"], world=1, assets=self.assets)
        # Boss
        if data.get("boss"):
            b = data["boss"]
            content.boss = Boss(b["x"], b["y"], world=1, assets=self.assets)
        # Bounds
        content.min_x = min((p.x for p in content.platforms), default=0)
        content.max_x = max((p.x + p.width for p in content.platforms), default=SCREEN_WIDTH)
        content.min_y = min((p.y for p in content.platforms), default=0)
        content.max_y = max((p.y + p.height for p in content.platforms), default=SCREEN_HEIGHT)
        return content
    """Procedural parkour generator with deterministic, scalable difficulty."""

    WORLD_RULES: Dict[int, WorldRule] = {
        0: WorldRule(("spike",)),
        1: WorldRule(("spike",), vertical_bias=0.25, object_multiplier=0.8),
        2: WorldRule(("spike", "rock"), vertical_bias=0.18),
        3: WorldRule(("quicksand", "spike"), vertical_bias=0.10, gap_multiplier=1.05),
        4: WorldRule(("wind", "spike"), vertical_bias=0.22),
        5: WorldRule(("icicle", "spike"), vertical_bias=0.32, gap_multiplier=1.10),
        8: WorldRule(("electric", "spike"), vertical_bias=0.20, gap_multiplier=1.12),
        6: WorldRule(("lava", "spike"), vertical_bias=0.16, gap_multiplier=1.15, object_multiplier=1.30),
        7: WorldRule(("wind", "spike"), vertical_bias=0.24, gap_multiplier=1.05),
        9: WorldRule(("ghost", "spike"), vertical_bias=0.26),
        10: WorldRule(("glitch", "spike"), vertical_bias=0.35, gap_multiplier=1.18, object_multiplier=1.35),
    }

    HAZARD_BUILDERS: Dict[str, Callable[[Platform, random.Random], Optional[pygame.sprite.Sprite]]] = {
        "spike": lambda platform, _rng: Spike(
            platform.rect.centerx - 16,
            platform.rect.top - 16,
            world=getattr(platform, "world_num", 1),
        ),
        "lava": lambda platform, _rng: LavaBubble(
            platform.rect.centerx - 16,
            platform.rect.top - 32,
            world=getattr(platform, "world_num", 1),
        ),
        "icicle": lambda platform, _rng: Icicle(platform.rect.centerx - 16, platform.rect.top - 32),
        "wind": lambda platform, _rng: WindOrb(
            platform.rect.centerx - 16,
            platform.rect.top - 96,
            world=getattr(platform, "world_num", 1),
        ),
        "electric": lambda platform, _rng: ElectricTile(platform.rect.centerx - 16, platform.rect.top - 20),
        "rock": lambda platform, _rng: FallingRock(platform.rect.centerx - 12, platform.rect.top - 48),
        "quicksand": lambda platform, _rng: QuicksandTile(platform.rect.centerx - 16, platform.rect.top - 8),
        "ghost": lambda platform, _rng: GhostOrb(platform.rect.centerx - 16, platform.rect.top - 80),
        "glitch": lambda platform, _rng: GlitchCube(platform.rect.centerx - 10, platform.rect.top - 24),
    }

    def __init__(self, assets: AssetCache, settings: Optional[GeneratorSettings] = None):
        self.assets = assets
        self.settings = settings or GeneratorSettings()
        self.physics = JumpPhysics(jump_speed=12, gravity=0.5, max_speed=6)

    def generate(
        self,
        world: int,
        level: int,
        *,
        variant: int = 0,
        seed: Optional[int] = None,
        difficulty_override: Optional[float] = None,
    ) -> LevelContent:
        # Always make the 10th level a vertical tower
        mode = "tower" if level % 10 == 0 else "default"
        difficulty = (
            max(0.0, min(1.0, difficulty_override))
            if difficulty_override is not None
            else self._difficulty_for(world, level, mode)
        )
        # Make runs feel fresh: if no seed provided, use high-entropy source (time_ns).
        if seed is None:
            seed = time.time_ns() ^ random.randrange(1, 1_000_000_000)
        return self.generate_level(world, difficulty, mode=mode, variant=variant, seed=seed)

    def generate_level(
        self,
        world: int,
        difficulty: float,
        *,
        mode: str = "default",
        variant: int = 0,
        seed: Optional[int] = None,
    ) -> LevelContent:
        rng_seed = seed if seed is not None else time.time_ns()
        rng = random.Random(rng_seed)
        content = LevelContent()
        rule = self.WORLD_RULES.get(world, self.WORLD_RULES[0])

        main_path = self._build_main_path(content, world, difficulty, mode, rule, rng)
        if not main_path:
            self._finalize_bounds(content)
            return content

        if mode == "tower":
            self._place_goal(content, main_path[-1], world, rng, portal_type="boss", active=False)
        else:
            self._place_goal(content, main_path[-1], world, rng)
        # Tower levels (every 10th) are longer: force extra sections and checkpoints
        self._place_checkpoints(content, main_path, difficulty, mode=mode)
        self._finalize_bounds(content)
        return content

    def _build_main_path(
        self,
        content: LevelContent,
        world: int,
        difficulty: float,
        mode: str,
        rule: WorldRule,
        rng: random.Random,
    ) -> List[Platform]:
        settings = self.settings
        min_y = settings.min_platform_y
        max_y = settings.max_platform_y
        if mode == "tower":
            min_y = max(60, min_y - 80)
            max_y = min(max_y + 20, SCREEN_HEIGHT - 80)

        gap_min = int(settings.gap_min.lerp(difficulty) * rule.gap_multiplier)
        gap_max = int(settings.gap_max.lerp(difficulty) * rule.gap_multiplier)
        max_gap_allowed = int(self.physics.max_jump_distance * 0.85)
        gap_max = min(max_gap_allowed, max(gap_min + 12, gap_max))
        gap_min = max(40, min(gap_min, gap_max - 12))

        width_min = int(settings.width_min.lerp(difficulty))
        width_max = int(settings.width_max.lerp(difficulty))
        if width_max < width_min + 16:
            width_max = width_min + 16

        vertical_variance = int(settings.vertical_variance.lerp(difficulty))
        if mode == "tower":
            vertical_variance = int(vertical_variance * 1.45)

        branch_chance = max(0.0, min(0.35, settings.branch_chance.lerp(difficulty)))
        if mode == "tower":
            branch_chance *= 0.4

        section_count = int(round(settings.section_count.lerp(difficulty)))
        if mode == "tower":
            # Make 10th levels significantly longer
            section_count = int(section_count * 1.9)

        start_width = max(width_max, 200)
        start_x = PLAYER_SPAWN[0] - start_width // 2
        start_y = self._clamp_vertical_target(PLAYER_SPAWN[1] + 20, min_y, max_y)
        start_platform = Platform(
            start_x,
            start_y,
            start_width,
            settings.base_platform_height,
            world,
            self.assets,
        )
        content.platforms.add(start_platform)

        path: List[Platform] = [start_platform]
        previous = start_platform

        for index in range(section_count):
            next_platform = self._build_next_platform(
                previous,
                world,
                difficulty,
                mode,
                rule,
                rng,
                gap_min,
                gap_max,
                width_min,
                width_max,
                vertical_variance,
                min_y,
                max_y,
            )
            content.platforms.add(next_platform)
            path.append(next_platform)
            self._decorate_platform(
                content,
                next_platform,
                world,
                difficulty,
                rule,
                rng,
                index + 1,
                section_count,
            )

            if rng.random() < branch_chance:
                self._maybe_add_branch_path(
                    content,
                    next_platform,
                    world,
                    difficulty,
                    rule,
                    rng,
                    gap_min,
                    gap_max,
                    width_min,
                    width_max,
                    vertical_variance,
                    min_y,
                    max_y,
                )

            previous = next_platform

        self._enforce_path_spacing(path)
        return path

    def _build_next_platform(
        self,
        previous: Platform,
        world: int,
        difficulty: float,
        mode: str,
        rule: WorldRule,
        rng: random.Random,
        gap_min: int,
        gap_max: int,
        width_min: int,
        width_max: int,
        vertical_variance: int,
        min_y: int,
        max_y: int,
    ) -> Platform:
        bias = int(vertical_variance * rule.vertical_bias)
        if mode == "tower":
            bias += int(vertical_variance * (0.5 + 0.2 * difficulty))

        max_gap = gap_max
        max_center_gap = int(self.physics.max_jump_distance * 0.75)
        min_gap_pixels = 40

        for _ in range(8):
            width = rng.randint(width_min, width_max)
            delta = rng.randint(-vertical_variance, vertical_variance) - bias
            target_y = previous.rect.y + delta
            max_rise = int(self.physics.max_jump_height * 0.75)
            if previous.rect.top - target_y > max_rise:
                target_y = previous.rect.top - max_rise
            if target_y - previous.rect.top > max_rise:
                target_y = previous.rect.top + max_rise
            target_y = self._clamp_vertical_target(int(target_y), min_y, max_y)

            max_gap_by_center = max_center_gap - (previous.rect.width // 2 + width // 2)
            effective_gap_max = max(min_gap_pixels, min(max_gap, max_gap_by_center))
            gap = rng.randint(min_gap_pixels, max(effective_gap_max, min_gap_pixels))

            left = previous.rect.right + gap
            candidate = self._create_platform(left, target_y, width, world, difficulty, rng)

            min_center = previous.rect.right + min_gap_pixels + candidate.rect.width // 2
            max_center = previous.rect.centerx + max_center_gap
            if min_center > max_center:
                min_center = max_center
            desired_center = min(candidate.rect.centerx, max_center)
            desired_center = max(desired_center, min_center)
            candidate.rect.centerx = int(desired_center)
            candidate.prev_rect = candidate.rect.copy()
            if isinstance(candidate, MovingPlatform):
                candidate._anchor.x = candidate.rect.x
            if isinstance(candidate, BlinkingPlatform):
                candidate._anchor.x = candidate.rect.x

            if self._jump_possible(previous, candidate):
                return candidate
            max_gap = max(gap_min + 12, int(max_gap * 0.85))

        fallback_gap = max(gap_min, int(gap_min * 1.1))
        left = previous.rect.right + fallback_gap
        width = max(width_min, int((width_min + width_max) / 2))
        safe_y = self._clamp_vertical_target(previous.rect.y, min_y, max_y)
        fallback = Platform(
            left,
            safe_y,
            width,
            self.settings.base_platform_height,
            world,
            self.assets,
        )
        min_center = previous.rect.right + min_gap_pixels + fallback.rect.width // 2
        max_center = previous.rect.centerx + max_center_gap
        if min_center > max_center:
            min_center = max_center
        desired_center = min(fallback.rect.centerx, max_center)
        desired_center = max(desired_center, min_center)
        fallback.rect.centerx = int(desired_center)
        fallback.prev_rect = fallback.rect.copy()
        return fallback

    def _enforce_path_spacing(self, path: List[Platform]) -> None:
        max_center_gap = int(self.physics.max_jump_distance * 0.75)
        min_gap_pixels = 32
        for previous, current in zip(path, path[1:]):
            min_center = previous.rect.right + min_gap_pixels + current.rect.width // 2
            max_center = previous.rect.centerx + max_center_gap
            if min_center > max_center:
                min_center = max_center
            desired_center = min(current.rect.centerx, max_center)
            desired_center = max(desired_center, min_center)
            if int(desired_center) != current.rect.centerx:
                current.rect.centerx = int(desired_center)
                current.prev_rect = current.rect.copy()
                if isinstance(current, MovingPlatform):
                    current._anchor.x = current.rect.x
                if isinstance(current, BlinkingPlatform):
                    current._anchor.x = current.rect.x
            max_rise = int(self.physics.max_jump_height * 0.75)
            if previous.rect.top - current.rect.top > max_rise:
                current.rect.top = previous.rect.top - max_rise
                current.rect.y = current.rect.top
            if current.rect.top - previous.rect.top > max_rise:
                current.rect.top = previous.rect.top + max_rise
                current.rect.y = current.rect.top
            if isinstance(current, MovingPlatform):
                current._anchor.y = current.rect.y
            if isinstance(current, BlinkingPlatform):
                current._anchor.y = current.rect.y
            current.prev_rect = current.rect.copy()

    def _create_platform(
        self,
        left: int,
        top: int,
        width: int,
        world: int,
        difficulty: float,
        rng: random.Random,
    ) -> Platform:
        moving_rate = max(0.0, min(0.6, self.settings.moving_rate.lerp(difficulty)))
        blinking_rate = max(0.0, min(0.4, self.settings.blinking_rate.lerp(difficulty)))
        height = self.settings.base_platform_height
        roll = rng.random()

        if roll < blinking_rate and difficulty > 0.35:
            on_frames = rng.randrange(70, 120)
            off_frames = rng.randrange(40, 90)
            phase = rng.randrange(0, on_frames + off_frames)
            return BlinkingPlatform(
                left,
                top,
                width,
                height,
                world,
                self.assets,
                on_frames=on_frames,
                off_frames=off_frames,
                phase_offset=phase,
            )

        roll -= blinking_rate
        if roll < moving_rate:
            horizontal = rng.random() < 0.7
            amplitude = rng.uniform(36, 72 if horizontal else 48)
            # Scale moving platform speed by world so early worlds are slower
            # and later worlds ramp up slightly. base_factor for world 1 is
            # intentionally < 1.0 to make early levels slower.
            base_factor = 0.6
            per_world_increase = 0.05
            factor = max(0.3, min(1.6, base_factor + (max(1, world) - 1) * per_world_increase))
            # Choose a nominal speed then scale by factor
            nominal = rng.uniform(0.8, 1.6)
            speed = nominal * factor
            phase = rng.uniform(0.0, math.tau)
            return MovingPlatform(
                left,
                top,
                width,
                height,
                world,
                self.assets,
                horizontal=horizontal,
                amplitude=amplitude,
                speed=speed,
                phase_offset=phase,
            )

        speed_mod = 1.0
        if rng.random() < 0.15 * difficulty:
            speed_mod = rng.uniform(0.7, 1.6)
        return Platform(left, top, width, height, world, self.assets, speed_mod=speed_mod)

    def _decorate_platform(
        self,
        content: LevelContent,
        platform: Platform,
        world: int,
        difficulty: float,
        rule: WorldRule,
        rng: random.Random,
        index: int,
        total: int,
    ) -> None:
        if total <= 0:
            return
        progress = index / max(1, total)

        hazard_rate = min(0.85, self.settings.hazard_rate.lerp(difficulty) * (0.5 + progress))
        if rng.random() < hazard_rate:
            hazard_key = rng.choice(rule.hazard_keys)
            builder = self.HAZARD_BUILDERS.get(hazard_key)
            if builder:
                hazard = builder(platform, rng)
                self._add_hazard(content, hazard)

        collectible_rate = max(0.05, self.settings.collectible_rate.lerp(difficulty) * (1.1 - 0.5 * progress))
        if rng.random() < collectible_rate:
            count = 1 if platform.rect.width < 120 else 2 + (1 if rng.random() < 0.35 else 0)
            spacing = platform.rect.width // (count + 1)
            for i in range(count):
                coin = Coin(platform.rect.left + spacing * (i + 1), platform.rect.top - 28)
                self._try_add_sprite(content, "coin", coin, content.coins)

        object_rate = min(
            0.75,
            self.settings.world_object_rate.lerp(difficulty) * rule.object_multiplier * (0.6 + 0.4 * progress),
        )
        placed_hazard = False
        if rng.random() < object_rate:
            world_object = self._spawn_world_object(world, platform)
            if isinstance(world_object, Spike):
                added = self._try_add_sprite(content, "spike", world_object, content.spikes)
                placed_hazard = placed_hazard or added
            else:
                added = self._try_add_sprite(content, "special", world_object, content.specials)
                placed_hazard = placed_hazard or isinstance(world_object, Spike)
            # If we successfully placed a sprite on a moving platform, make it follow
            try:
                if added and isinstance(platform, MovingPlatform):
                    platform.carry_sprites.add(world_object)
            except Exception:
                pass

        # --- ENEMY SPAWN LOGIC ---
        # Only spawn enemies on sufficiently large, non-moving platforms
        enemy_spawn_chance = 0.18 + 0.12 * difficulty  # 18-30% chance, scales with difficulty
        min_platform_width = 90
        if (
            platform.rect.width >= min_platform_width
            and not isinstance(platform, (MovingPlatform, BlinkingPlatform))
            and not placed_hazard
            and rng.random() < enemy_spawn_chance
        ):
            # Place enemy at random x on platform
            enemy_x = rng.randint(platform.rect.left + 8, platform.rect.right - 40)
            enemy_y = platform.rect.top - 28
            enemy = create_enemy(enemy_x, enemy_y, world, speed=2, assets=self.assets)
            self._try_add_sprite(content, "enemy", enemy, content.enemies)


    def _maybe_add_branch_path(
        self,
        content: LevelContent,
        origin: Platform,
        world: int,
        difficulty: float,
        rule: WorldRule,
        rng: random.Random,
        gap_min: int,
        gap_max: int,
        width_min: int,
        width_max: int,
        vertical_variance: int,
        min_y: int,
        max_y: int,
    ) -> None:
        branch_gap = rng.randint(max(40, gap_min // 2), max(60, int(gap_max * 0.6)))
        left = origin.rect.right + branch_gap
        target_y = self._clamp_vertical_target(
            origin.rect.y - rng.randint(40, max(80, vertical_variance)),
            min_y,
            max_y,
        )
        width = max(64, int(width_min * 0.7))
        branch = Platform(left, target_y, width, self.settings.base_platform_height, world, self.assets)
        if not self._jump_possible(origin, branch):
            return
        content.platforms.add(branch)
        self._decorate_platform(content, branch, world, difficulty, rule, rng, 0, 1)
        reward = Coin(branch.rect.centerx, branch.rect.top - 36)
        self._try_add_sprite(content, "coin", reward, content.coins)

    def _spawn_world_object(self, world: int, platform: Platform) -> Optional[pygame.sprite.Sprite]:
        sprite = create_world_object(world, platform.rect.centerx - 16, platform.rect.top - 32)
        if not hasattr(sprite, "rect"):
            return sprite
        if isinstance(sprite, QuicksandTile):
            sprite.rect.midtop = (platform.rect.centerx, platform.rect.top)
        else:
            sprite.rect.midbottom = (platform.rect.centerx, platform.rect.top - 4)
        return sprite

    def _add_hazard(self, content: LevelContent, hazard: Optional[pygame.sprite.Sprite]) -> None:
        if hazard is None or not hasattr(hazard, "rect"):
            return
        if isinstance(hazard, Spike):
            self._try_add_sprite(content, "spike", hazard, content.spikes)
        else:
            self._try_add_sprite(content, "hazard", hazard, content.specials)

    def _try_add_sprite(
        self,
        content: LevelContent,
        tag: str,
        sprite: Optional[pygame.sprite.Sprite],
        group: pygame.sprite.Group,
        *,
        force: bool = False,
    ) -> bool:
        if sprite is None or not hasattr(sprite, "rect"):
            return False
        if content.reserve_rect(tag, sprite.rect, force=force):
            group.add(sprite)
            return True
        sprite.kill()
        return False

    def _place_goal(
        self,
        content: LevelContent,
        last_platform: Platform,
        world: int,
        rng: random.Random,
        *,
        portal_type: str = "normal",
        active: bool = True,
    ) -> None:
        max_gap = int(self.physics.max_jump_distance * 0.7)
        gap = min(max_gap, max(60, last_platform.rect.width))
        width = max(140, int(last_platform.rect.width * 0.9))
        target_y = last_platform.rect.y
        for _ in range(4):
            left = last_platform.rect.right + gap
            goal_platform = Platform(
                left,
                target_y,
                width,
                self.settings.base_platform_height,
                world,
                self.assets,
            )
            min_center = last_platform.rect.right + 32 + goal_platform.rect.width // 2
            max_center = last_platform.rect.centerx + int(self.physics.max_jump_distance * 0.75)
            if min_center > max_center:
                min_center = max_center
            desired_center = min(goal_platform.rect.centerx, max_center)
            desired_center = max(desired_center, min_center)
            goal_platform.rect.centerx = int(desired_center)
            goal_platform.prev_rect = goal_platform.rect.copy()
            if self._jump_possible(last_platform, goal_platform):
                content.platforms.add(goal_platform)
                goal = Goal(
                    goal_platform.rect.centerx,
                    goal_platform.rect.top,
                    world,
                    self.assets,
                    portal_type=portal_type,
                    active=active,
                )
                content.goal = goal
                return
            gap = max(40, int(gap * 0.75))
        goal = Goal(
            last_platform.rect.centerx,
            last_platform.rect.top,
            world,
            self.assets,
            portal_type=portal_type,
            active=active,
        )
        content.goal = goal

    def _place_checkpoints(
        self,
        content: LevelContent,
        path: List[Platform],
        difficulty: float,
        *,
        mode: str = "default",
    ) -> None:
        if len(path) < 2:
            return

        if mode == "tower":
            highest = min(p.rect.top for p in path)
            lowest = max(p.rect.top for p in path)
            vertical_span = max(0, lowest - highest)
            if vertical_span < 180:
                return
            steps = max(1, vertical_span // 220)
            for step in range(1, steps + 1):
                progress = step / (steps + 1)
                target_y = lowest - vertical_span * progress
                platform = min(path, key=lambda p: abs(p.rect.top - target_y))
                checkpoint = Checkpoint(platform.rect.centerx, platform.rect.top - 62)
                self._try_add_sprite(content, "checkpoint", checkpoint, content.checkpoints, force=True)
            return

        interval = int(self.settings.checkpoint_interval.lerp(difficulty))
        total_span = path[-1].rect.centerx - path[0].rect.centerx
        if total_span <= interval * 1.1:
            if difficulty < 0.5:
                return
            count = 1
        else:
            count = max(1, total_span // interval)
        for i in range(1, count + 1):
            progress = i / (count + 1)
            target_x = path[0].rect.centerx + total_span * progress
            platform = min(path, key=lambda p: abs(p.rect.centerx - target_x))
            checkpoint = Checkpoint(platform.rect.centerx, platform.rect.top - 62)
            self._try_add_sprite(content, "checkpoint", checkpoint, content.checkpoints, force=True)

    def _finalize_bounds(self, content: LevelContent) -> None:
        xs: List[int] = []
        ys: List[int] = []
        for group in (
            content.platforms,
            content.spikes,
            content.specials,
            content.coins,
            content.checkpoints,
        ):
            for sprite in group:
                if hasattr(sprite, "rect"):
                    rect = sprite.rect
                    xs.extend((rect.left, rect.right))
                    ys.extend((rect.top, rect.bottom))
        if content.goal:
            rect = content.goal.rect
            xs.extend((rect.left, rect.right))
            ys.extend((rect.top, rect.bottom))

        if xs and ys:
            padding = 120
            content.min_x = min(xs) - padding
            content.max_x = max(xs) + padding
            content.min_y = min(ys) - padding
            content.max_y = max(ys) + padding
        else:
            content.min_x = 0
            content.max_x = SCREEN_WIDTH
            content.min_y = 0
            content.max_y = SCREEN_HEIGHT

        # --- Level Checker: Ensure no objects/enemies spawn inside platforms or each other ---
        def move_above_platform(sprite, platforms):
            # Move sprite above the highest platform it collides with
            for plat in platforms:
                if sprite.rect.colliderect(plat.rect):
                    sprite.rect.bottom = plat.rect.top
        # Check enemies
        for enemy in list(content.enemies):
            for plat in content.platforms:
                if enemy.rect.colliderect(plat.rect):
                    move_above_platform(enemy, content.platforms)
            # Check for overlap with other enemies
            for other in content.enemies:
                if other is not enemy and enemy.rect.colliderect(other.rect):
                    enemy.rect.y = other.rect.top - enemy.rect.height
        # Check coins
        for coin in list(content.coins):
            for plat in content.platforms:
                if coin.rect.colliderect(plat.rect):
                    move_above_platform(coin, content.platforms)
        # Check specials
        for special in list(content.specials):
            for plat in content.platforms:
                if special.rect.colliderect(plat.rect):
                    move_above_platform(special, content.platforms)
        # Check spikes
        for spike in list(content.spikes):
            for plat in content.platforms:
                if spike.rect.colliderect(plat.rect):
                    # Attach spike to platform if it's a moving platform
                    if hasattr(plat, 'carry_sprites'):
                        plat.carry_sprites.add(spike)
                    move_above_platform(spike, [plat])

    def _derive_seed(self, world: int, level: int, variant: int) -> int:
        base = (world * 10007) + (level * 389) + variant * 7919
        if self.settings.rng_seed is not None:
            base ^= self.settings.rng_seed
        return base

    def _difficulty_for(self, world: int, level: int, mode: str) -> float:
        if mode == "tower":
            return 1.0
        if level <= 1:
            return 0.0
        max_progress = (10 - 1) + (10 - 1) / 10.0
        progress = max(0.0, (world - 1) + (level - 1) / 10.0)
        scaled = min(1.0, progress / max_progress)
        rule = self.WORLD_RULES.get(world, self.WORLD_RULES[0])
        return max(0.0, min(1.0, scaled * rule.gap_multiplier * 0.9 + scaled * 0.1))

    @staticmethod
    def _clamp_vertical_target(target: int, min_y: int, max_y: int) -> int:
        return max(min_y, min(max_y, target))

    def _jump_possible(self, start: Platform, target: Platform) -> bool:
        from_pos = (start.rect.centerx, start.rect.top)
        to_pos = (target.rect.centerx, target.rect.top)
        return self.physics.can_reach(from_pos, to_pos)


# === Scenes ===
class CreditScene(Scene):
    def __init__(self, game: "Game"):
        super().__init__(game)
        self.timer = 0.0
        self.minimum_display = 2.0
        self.prompt_visible = False
        self.fade = 0.0

    def on_enter(self) -> None:
        self.game.pause_speedrun(True)
        self.timer = 0.0
        self.prompt_visible = False
        self.fade = 0.0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
        if self.prompt_visible:
            if event.type == pygame.KEYDOWN:
                self.game.last_input_device = "keyboard"
                key_map = self.game.settings["key_map"]
                accept_key = key_map.get("accept", pygame.K_RETURN)
                if event.key in (accept_key, pygame.K_SPACE, pygame.K_ESCAPE):
                    self.game._suppress_accept_until = time.time() + 0.5
                    self.game.change_scene(TitleScene)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.game.last_input_device = "mouse"
                self.game._suppress_accept_until = time.time() + 0.5
                self.game.change_scene(TitleScene)
            elif event.type == pygame.JOYBUTTONDOWN:
                self.game.last_input_device = "controller"
                if event.button in (0, 7):  # A or Start
                    self.game._suppress_accept_until = time.time() + 0.5
                    self.game.change_scene(TitleScene)
            elif event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.6:
                self.game.last_input_device = "controller"
                self.game._suppress_accept_until = time.time() + 0.5
                self.game.change_scene(TitleScene)

    def update(self, dt: float) -> None:
        self.timer += dt
        self.fade = min(1.0, self.fade + dt * 0.6)
        if self.timer >= self.minimum_display:
            self.prompt_visible = True

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 20))

        overlay = pygame.Surface(SCREEN_SIZE)
        overlay.fill((30, 0, 50))
        overlay.set_alpha(int(120 * self.fade))
        surface.blit(overlay, (0, 0))

        title_font = self.game.assets.font(56, True)
        subtitle_font = self.game.assets.font(28, False)
        prompt_font = self.game.assets.font(20, False)

        draw_center_text(surface, title_font, "Reality Collapsing", SCREEN_HEIGHT // 2 - 80, WHITE)
        draw_center_text(surface, subtitle_font, "Created by", SCREEN_HEIGHT // 2 - 10, CYAN)
        draw_center_text(surface, title_font, "James Griepentrog", SCREEN_HEIGHT // 2 + 60, WHITE)

        if self.prompt_visible:
            device = getattr(self.game, "last_input_device", "keyboard")
            if device == "controller":
                prompt = "Press A/Start to continue"
            elif device == "mouse":
                prompt = "Click to continue"
            else:
                prompt = "Press Enter/Space to continue"
            draw_prompt_with_icons(surface, prompt_font, prompt, SCREEN_HEIGHT - 80, WHITE, device=device)


class CharacterCreationScene(Scene):
    def __init__(self, game: "Game"):
        super().__init__(game)
        # Only color wheel selection, no player select
        self.character_list = ["player"]
        self.selected_character_idx = 0
        self.preview_image = self._load_preview_image()
        self.preview_tinted: Optional[pygame.Surface] = None
        self.preview_pos = (SCREEN_WIDTH // 2 - 240, SCREEN_HEIGHT // 2 - 40)
        self.selected_color = self.game.player_color
        self.wheel_surface = generate_color_wheel(COLOR_WHEEL_RADIUS)
        wheel_center = (SCREEN_WIDTH // 2 + 220, SCREEN_HEIGHT // 2 - 40)
        self.wheel_rect = self.wheel_surface.get_rect(center=wheel_center)
        self.selection_pos = self._pos_from_color(self.selected_color)
        self.confirm_rect = pygame.Rect(0, 0, 220, 56)
        self.back_rect = pygame.Rect(0, 0, 180, 48)
        # Button rectangles (size + position)
        self.confirm_rect = pygame.Rect(0, 0, 220, 56)
        self.back_rect = pygame.Rect(0, 0, 180, 48)

        # Setting button positions
        self.confirm_rect.center = (SCREEN_WIDTH // 2 + 220, SCREEN_HEIGHT - 110)
        self.back_rect.center = (SCREEN_WIDTH // 2 - 220, SCREEN_HEIGHT - 110)
        self.dragging = False
        self.hover_confirm = False
        self.hover_back = False
        self._update_preview_tint()

    def _get_character_list(self):
        char_dir = Path("assets/characters")
        if not char_dir.exists():
            return ["player"]
        return [f.name for f in char_dir.iterdir() if f.is_dir()]

    def _select_character(self, idx):
        self.selected_character_idx = idx
        char = self.character_list[idx]
        if char == "player":
            self.selecting_character = False
            self.selecting_form = False
            # Set default color for character if needed
            self.selected_color = self.game.player_color
            self.wheel_surface = generate_color_wheel(COLOR_WHEEL_RADIUS)
            wheel_center = (SCREEN_WIDTH // 2 + 220, SCREEN_HEIGHT // 2 - 40)
            self.wheel_rect = self.wheel_surface.get_rect(center=wheel_center)
            self.selection_pos = self._pos_from_color(self.selected_color)
            self.confirm_rect.center = (SCREEN_WIDTH // 2 + 220, SCREEN_HEIGHT - 110)
            self.back_rect.center = (SCREEN_WIDTH // 2 - 220, SCREEN_HEIGHT - 110)
            self.dragging = False
            self._update_preview_tint()

    def _load_preview_image(self) -> pygame.Surface:
        # Try to load the idle pose for the player; fall back to a simple silhouette
        default = pygame.Surface((120, 140), pygame.SRCALPHA)
        base_rect = default.get_rect()
        pygame.draw.rect(default, (200, 200, 220, 60), base_rect, border_radius=12)
        pygame.draw.rect(default, (200, 200, 220, 180), base_rect.inflate(-12, -12), border_radius=12)
        try:
            path = ASSET_DIR / "characters" / "player" / "idle_0.png"
            if path.exists():
                img = pygame.image.load(str(path)).convert_alpha()
                return pygame.transform.smoothscale(img, (120, 140))
        except Exception as exc:
            print(f"[CharacterCreation] Failed to load preview: {exc}")
        return default

    def _tint_surface(self, surface: pygame.Surface, color: Tuple[int, int, int]) -> pygame.Surface:
        tinted = surface.copy()
        tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        tint.fill((*color, 0))
        tinted.blit(tint, (0, 0), special_flags=pygame.BLEND_MULT)
        return tinted

    def _update_preview_tint(self) -> None:
        self.preview_tinted = self._tint_surface(self.preview_image, self.selected_color)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._update_selection(event.pos):
                self.dragging = True
                self._update_preview_tint()
            elif self.confirm_rect.collidepoint(event.pos):
                self._finalize_selection()
            elif self.back_rect.collidepoint(event.pos):
                self.game.change_scene(TitleScene)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            if self._update_selection(event.pos):
                self._update_preview_tint()

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._finalize_selection()
            elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.game.change_scene(TitleScene)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self._nudge_selection(-0.06, 0.0)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._nudge_selection(0.06, 0.0)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self._nudge_selection(0.0, -0.05)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._nudge_selection(0.0, 0.05)

        if event.type == pygame.JOYBUTTONDOWN:
            if event.button in (0, 7):  # A or Start
                self._finalize_selection()
            elif event.button in (1, 2, 6):  # B / X / Back -> leave
                self.game.change_scene(TitleScene)
        if event.type == pygame.JOYAXISMOTION and event.axis in (0, 1):
            # Use left stick to orbit the wheel
            if not hasattr(self, "_axis_state"):
                self._axis_state = {0: 0.0, 1: 0.0}
            self._axis_state[event.axis] = event.value
            x = self._axis_state.get(0, 0.0)
            y = self._axis_state.get(1, 0.0)
            if abs(x) > 0.15 or abs(y) > 0.15:
                # Slow stick orbiting for finer control
                self._nudge_selection(x * 0.06, y * 0.06)

    def _nudge_selection(self, dx: float, dy: float) -> None:
        # Adjust hue with dx and saturation with dy
        r, g, b = [c / 255.0 for c in self.selected_color]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        h = (h + dx) % 1.0
        s = min(1.0, max(0.0, s - dy))
        r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
        self.selected_color = (int(r2 * 255), int(g2 * 255), int(b2 * 255))
        self.selection_pos = self._pos_from_color(self.selected_color)
        self._update_preview_tint()

    def update(self, dt: float) -> None:  # noqa: ARG002
        # Update hover states for mouse-driven highlighting
        mouse_pos = pygame.mouse.get_pos()
        self.hover_confirm = self.confirm_rect.collidepoint(mouse_pos)
        self.hover_back = self.back_rect.collidepoint(mouse_pos)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((14, 14, 30))

        title_font = self.game.assets.font(48, True)
        # Only show color wheel UI before entering the level
        draw_glitch_text(
            surface,
            title_font,
            "CHOOSE YOUR COLOR",
            90,
            WHITE,
            self.game.settings["glitch_fx"],
        )
        # Preview frame on the left
        preview_frame = pygame.Rect(0, 0, 220, 260)
        preview_frame.center = self.preview_pos
        pygame.draw.rect(surface, (30, 30, 60), preview_frame, border_radius=16)
        pygame.draw.rect(surface, (120, 140, 220), preview_frame, 3, border_radius=16)
        if self.preview_tinted:
            img_rect = self.preview_tinted.get_rect(center=self.preview_pos)
            surface.blit(self.preview_tinted, img_rect)

        if self.wheel_surface and self.wheel_rect:
            surface.blit(self.wheel_surface, self.wheel_rect)
            # Selection indicator
            if self.selection_pos:
                pygame.draw.circle(surface, WHITE, self.selection_pos, 6, 2)

        # Draw confirm and back buttons using the new method
        self._draw_button(surface, self.confirm_rect, "Confirm", self.hover_confirm)
        self._draw_button(surface, self.back_rect, "Back", self.hover_back)

        # Controls hint
        hint_font = self.game.assets.font(20, False)
        device = getattr(self.game, "last_input_device", "keyboard")
        if device == "controller":
            hint = "LStick / Dpad to orbit | A to confirm | B to cancel"
        elif device == "mouse":
            hint = "Click/drag the wheel | Click Confirm or Back"
        else:
            hint = "Arrow keys to orbit | Enter to confirm | Esc to cancel"
        draw_prompt_with_icons(surface, hint_font, hint, SCREEN_HEIGHT - 50, (170, 170, 200), device=device)

    # Drawing the button (appearance)
    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, label: str, highlighted: bool) -> None:
        # Base colors
        base_color = (90, 120, 210) if highlighted else (80, 80, 120)

        # Hover brightness effect
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if hover:
            base_color = tuple(min(255, c + 25) for c in base_color)

        # Draw the button shape
        pygame.draw.rect(surface, base_color, rect, border_radius=12)

        # Outline
        pygame.draw.rect(surface, WHITE, rect, width=2, border_radius=12)

        # Label
        font = self.game.assets.font(24, True)
        text = font.render(label, True, WHITE)
        surface.blit(text, text.get_rect(center=rect.center))


    def _finalize_selection(self) -> None:
        self.game.sound.play_event("menu_confirm")
        self.game.player_color = self.selected_color
        self.game.selected_character = self.character_list[self.selected_character_idx]
        self.game.world1_intro_shown = False
        self.game.progress.reset()
        self.game.start_speedrun()
        self.game.change_scene(GameplayScene, world=1, level=1)

    def _update_selection(self, pos: Tuple[int, int]) -> bool:
        if not self.wheel_rect or not self.wheel_surface:
            return False
        local = (pos[0] - self.wheel_rect.left, pos[1] - self.wheel_rect.top)
        radius = COLOR_WHEEL_RADIUS
        dx = local[0] - radius
        dy = local[1] - radius
        if math.hypot(dx, dy) > radius:
            return False
        try:
            color = self.wheel_surface.get_at((int(local[0]), int(local[1])))[:3]
        except IndexError:
            return False
        self.selected_color = color
        self.selection_pos = (self.wheel_rect.left + int(local[0]), self.wheel_rect.top + int(local[1]))
        return True

    def _pos_from_color(self, color: Tuple[int, int, int]) -> Tuple[int, int]:
        if not self.wheel_rect:
            return (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)
        r, g, b = [c / 255.0 for c in color]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        angle = h * math.tau
        distance = min(1.0, max(0.0, s)) * COLOR_WHEEL_RADIUS
        local_x = COLOR_WHEEL_RADIUS + int(math.cos(angle) * distance)
        local_y = COLOR_WHEEL_RADIUS - int(math.sin(angle) * distance)
        return (self.wheel_rect.left + local_x, self.wheel_rect.top + local_y)


class CreditsScene(Scene):
    def __init__(self, game, ending_mode: bool = False):
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
        self.shards: List["CreditsScene.Shard"] = []
        w, h = self.game.screen.get_size()
        # Start below the bottom edge so credits scroll up onto the screen (matches title screen behavior)
        self.scroll_y = h - 40  # lowered spawn height so they begin visible sooner
        self.reset()

        self.game.stop_music()
        self.game.play_music("credits.mp3")

        self.glitch_timer = 0
        self.glitch_interval = 0.18
        self.glitch_level = 1

        w, h = self.game.screen.get_size()
        self.temp = pygame.Surface((w, h)).convert()
        self.overlay = pygame.Surface((w, h), pygame.SRCALPHA)

    def reset(self):
        w, h = self.game.screen.get_size()
        # Keep spawn below the viewport so the first lines scroll into view
        self.scroll_y = h - 40
        self.done = False
        self.prompt_blink_timer = 0
        self.prompt_visible = True
        self.glitch_level = 1
        self.frame_count = 0
        self.shards.clear()
        self.exit_triggered = False

    def glitch_static(self, surf, amount=80):
        noise = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        arr = pygame.surfarray.pixels_alpha(noise)
        arr[:, :] = np.random.randint(0, 256, arr.shape, dtype=arr.dtype)
        del arr
        noise.set_alpha(random.randint(30, 70))
        surf.blit(noise, (0, 0), special_flags=pygame.BLEND_SUB)

    def glitch_rgb_split(self, surf, amount=4):
        ox = random.randint(-amount, amount)
        oy = random.randint(-amount, amount)
        shifted = pygame.Surface(surf.get_size()).convert()
        shifted.blit(surf, (ox, oy))
        surf.blit(shifted, (0, 0), special_flags=pygame.BLEND_ADD)

    def glitch_slices(self, surf, slices=4, max_shift=30):
        w, h = surf.get_size()
        for _ in range(slices):
            y = random.randint(0, h - 4)
            slice_h = random.randint(4, 20)
            if y + slice_h > h:
                slice_h = h - y
            if slice_h <= 0:
                continue
            shift = random.randint(-max_shift, max_shift)
            slc = surf.subsurface((0, y, w, slice_h)).copy()
            surf.blit(slc, (shift, y))

    def glitch_scanlines(self, surf):
        w, h = surf.get_size()
        scan = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(scan, (0, 0, 0, random.randint(40, 90)), (0, y), (w, y), 1)
        surf.blit(scan, (0, 0))

    def glitch_screen_shake(self, surf):
        ox = random.randint(-3, 3)
        oy = random.randint(-3, 3)
        temp = surf.copy()
        surf.blit(temp, (ox, oy))

    def glitch_vhs(self, surf):
        w, h = surf.get_size()
        for _ in range(4):
            y = random.randint(0, h - 1)
            bar_height = 2
            if y + bar_height > h:
                bar_height = h - y
            if bar_height <= 0:
                continue
            bar = surf.subsurface((0, y, w, bar_height)).copy()
            sx = random.randint(-20, 20)
            surf.blit(bar, (sx, y))

    def glitch_meltdown(self, surf):
        offset = math.sin(self.frame_count * 0.2) * 5
        surf.scroll(dx=int(offset), dy=0)

    def glitch_wireframe(self, surf):
        w, h = surf.get_size()
        wire = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 50):
            pygame.draw.line(wire, (80, 80, 80, 100), (0, y), (w, y))
        for x in range(0, w, 50):
            pygame.draw.line(wire, (80, 80, 80, 100), (x, 0), (x, h))
        surf.blit(wire, (0, 0))

    def glitch_flash(self, surf):
        flash = pygame.Surface(surf.get_size())
        flash.fill((255, 255, 255))
        flash.set_alpha(random.randint(20, 120))
        surf.blit(flash, (0, 0))

    def glitch_vortex(self, surf):
        angle = math.sin(self.frame_count * 0.05) * 3
        scaled = pygame.transform.rotozoom(surf, angle, 1.02)
        rect = scaled.get_rect(center=surf.get_rect().center)
        surf.blit(scaled, rect)

    def glitch_blackhole(self, surf):
        scale = 1 + (math.sin(self.frame_count * 0.1) * 0.05)
        scaled = pygame.transform.rotozoom(surf, 0, scale)
        rect = scaled.get_rect(center=surf.get_rect().center)
        surf.blit(scaled, rect, special_flags=pygame.BLEND_SUB)

    def glitch_datamosh(self, surf):
        w, h = surf.get_size()
        slice_h = 6
        for _ in range(5):
            y = random.randint(0, h - 1)
            actual_h = slice_h if y + slice_h <= h else h - y
            if actual_h <= 0:
                continue
            slc = surf.subsurface((0, y, w, actual_h)).copy()
            surf.blit(slc, (random.randint(-30, 30), y))

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
            pygame.draw.rect(surf, self.color, (int(self.x), int(self.y), self.size, self.size))

    def spawn_shatter(self, surf, count=120):
        w, h = surf.get_size()
        for _ in range(count):
            x = random.randint(0, w - 1)
            y = random.randint(0, h - 1)
            self.shards.append(self.Shard(x, y, surf.get_at((x, y))))

    def update(self, dt):
        self.frame_count += 1
        if not self.done:
            self.scroll_y -= self.scroll_speed * dt
            denom = 600 if not self.ending_mode else (self.game.screen.get_height() + len(self.credits) * 48)
            p = max(0, min(1, 1 - self.scroll_y / denom))
            if p > 0.2:
                self.glitch_level = 2
            if p > 0.4:
                self.glitch_level = 3
            if p > 0.6:
                self.glitch_level = 4
            if p > 0.75:
                self.glitch_level = 5
            if p > 0.85:
                self.glitch_level = 6
            if p > 0.92:
                self.glitch_level = 7
            if self.scroll_y < -len(self.credits) * 48:
                self.done = True
                self.glitch_level = 8
                self.spawn_shatter(self.game.screen)
        else:
            self.prompt_blink_timer += dt
            if self.prompt_blink_timer >= 0.5:
                self.prompt_visible = not self.prompt_visible
                self.prompt_blink_timer = 0
        self.glitch_timer += dt

    def draw(self, surface):
        w, h = surface.get_size()
        self.temp.fill((0, 0, 0))
        font = self.game.assets.font(36, True)
        y = int(self.scroll_y)
        for line in self.credits:
            draw_center_text(self.temp, font, line, y, WHITE)
            y += 48
        if getattr(self.game.settings, "__getitem__", None) and self.game.settings["glitch_fx"]:
            lvl = self.glitch_level
            if lvl >= 1:
                self.glitch_scanlines(self.temp)
                if random.random() < 0.5:
                    self.glitch_static(self.temp)
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
            if lvl >= 8:
                self.glitch_vortex(self.temp)
                self.glitch_blackhole(self.temp)
                self.glitch_slices(self.temp, 8, 35)
                self.glitch_rgb_split(self.temp, 12)
                self.glitch_flash(self.temp)
        surface.blit(self.temp, (0, 0))
        if self.done:
            for shard in self.shards:
                shard.update()
                shard.draw(surface)
        if self.done and self.prompt_visible:
            pfont = self.game.assets.font(28, True)
            prompt_surf = pygame.Surface((w, 50), pygame.SRCALPHA)
            prompt_surf.fill((0, 0, 0, 0))
            device = getattr(self.game, "last_input_device", "keyboard")
            if device == "controller":
                prompt_text = "Press A/Start to return to Title Screen"
            elif device == "mouse":
                prompt_text = "Click to return to Title Screen"
            else:
                prompt_text = "Press Enter to return to Title Screen"
            draw_prompt_with_icons(prompt_surf, pfont, prompt_text, 25, WHITE, device=device)
            if getattr(self.game.settings, "__getitem__", None) and self.game.settings["glitch_fx"]:
                self.glitch_scanlines(prompt_surf)
                if random.random() < 0.5:
                    self.glitch_static(prompt_surf)
                self.glitch_slices(prompt_surf, 2, 12)
                self.glitch_rgb_split(prompt_surf, 3)
                self.glitch_screen_shake(prompt_surf)
            surface.blit(prompt_surf, (0, h - 125))

    def handle_event(self, event):
        if self.done:
            if getattr(self, "exit_triggered", False):
                return
            if self.ending_mode:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    self.exit_triggered = True
                    self.game._suppress_accept_until = time.time() + 0.5
                    self.game.change_scene(TitleScene)
                elif event.type == pygame.JOYBUTTONDOWN and event.button in (0, 7):  # A or Start
                    self.exit_triggered = True
                    self.game._suppress_accept_until = time.time() + 0.5
                    self.game.change_scene(TitleScene)
            else:
                if event.type == pygame.KEYDOWN:
                    self.exit_triggered = True
                    self.game._suppress_accept_until = time.time() + 0.5
                    self.game.change_scene(TitleScene)
                elif event.type == pygame.JOYBUTTONDOWN and event.button in (0, 7):  # A or Start
                    self.exit_triggered = True
                    self.game._suppress_accept_until = time.time() + 0.5
                    self.game.change_scene(TitleScene)
        elif not self.done and not self.ending_mode:
            if event.type == pygame.KEYDOWN:
                self.done = True
                self.glitch_level = 8
                self.spawn_shatter(self.game.screen)

    def on_exit(self):
        pass


class TitleScene(Scene):
    def open_level_selector(self) -> None:
        from main import LevelSelectScene
        self.game.sound.play_event("menu_confirm")
        self.game.change_scene(LevelSelectScene)

    def open_shops_menu(self) -> None:
        self.game.sound.play_event("menu_confirm")
        self.game.change_scene(ShopsHubScene)

    # Secret flight code: down down up up right left right left a b enter
    _flight_code = [
        pygame.K_DOWN, pygame.K_DOWN, pygame.K_UP, pygame.K_UP,
        pygame.K_RIGHT, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_LEFT,
        pygame.K_a, pygame.K_b, pygame.K_RETURN
    ]
    _flight_progress = 0
    # Controller flight code: up, down, up, down, A (d-pad + button)
    _flight_code_controller = ["up", "down", "up", "down", "a"]
    _flight_progress_controller = 0
    # Konami code: up up down down left right left right b a enter
    _konami_code = [
        pygame.K_UP, pygame.K_UP, pygame.K_DOWN, pygame.K_DOWN,
        pygame.K_LEFT, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_RIGHT,
        pygame.K_b, pygame.K_a, pygame.K_RETURN
    ]
    _konami_progress = 0

    def __init__(self, game: "Game"):
        super().__init__(game)
        self.bg_anim_time = 0.0
        self.bg_glitch_timer = 0.0
        self.bg_glitch_active = False
        self.background_color = (0, 0, 0)
        self.logo_frames = []
        self.logo_durations = []
        self.logo_frame_index = 0
        self.logo_frame_timer = 0.0
        self.logo_rect = pygame.Rect(0, 0, 0, 0)
        self.logo_animated = False
        self._refresh_logo_assets()
        self.menu = VerticalMenu(
            [
                MenuEntry(lambda: " Start New Game", self.start_new_game),
                MenuEntry(
                    lambda: " Continue",
                    self.continue_game,
                    enabled=lambda: SAVE_FILE.exists(),
                ),
                MenuEntry(lambda: " Shops", self.open_shops_menu),
                MenuEntry(lambda: " View Credits", self.play_credits),
                MenuEntry(lambda: " Settings", self.open_settings),
                MenuEntry(lambda: " Quit", self.quit_game),
            ],
            sound=self.game.sound,
        )

    def play_final_cutscene_from_menu(self) -> None:
        self.teleport_final_boss_defeated()

    def teleport_final_boss_defeated(self) -> None:
        self.game.sound.play_event("menu_confirm")
        # Go to final boss level, then instantly defeat the boss
        from main import BossArenaScene
        def after_scene_change():
            scene = self.game.scene
            if isinstance(scene, BossArenaScene):
                scene.boss.health = 0
                scene.state = "explosion"
                scene.explosion_timer = scene.explosion_duration
        self.game.change_scene(BossArenaScene, world=10, level=10)
        # Schedule boss defeat after scene loads
        pygame.time.set_timer(pygame.USEREVENT + 42, 100, True)
        # Patch the game event loop to handle this one-off event
        orig_handle_event = self.game.scene.handle_event
        def patched_handle_event(event):
            if event.type == pygame.USEREVENT + 42:
                after_scene_change()
            return orig_handle_event(event)
        self.game.scene.handle_event = patched_handle_event

    def play_credits(self) -> None:
        self.game.sound.play_event("menu_confirm")
        self.game.change_scene(CreditsScene, ending_mode=False)


    def start_new_game(self) -> None:
        game = self.game
        # If save data exists, show confirm/cancel popup
        if SAVE_FILE.exists() and SAVE_FILE.stat().st_size > 0:
            self._show_confirm_new_game_popup()
        else:
            self._do_start_new_game()

    def _do_start_new_game(self) -> None:
        game = self.game
        game.sound.play_event("menu_confirm")
        game.world1_intro_shown = False
        game.progress.reset()
        from main import CharacterCreationScene
        game.change_scene(CharacterCreationScene)

    def _show_confirm_new_game_popup(self) -> None:
        # Draw the main menu in the background, then overlay a centered popup
        running = True
        menu = VerticalMenu([
            MenuEntry(lambda: "Start New Game", lambda: "confirm"),
            MenuEntry(lambda: "Cancel", lambda: "cancel"),
        ])
        clock = self.game.clock
        glitch_fx = self.game.settings["glitch_fx"]
        while running and self.game.running:
            # Poll controller to allow confirm/cancel via gamepad
            self.game._poll_controller()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.game.quit()
                    return
                result = menu.handle_event(event)
                if result == "confirm":
                    self._do_start_new_game()
                    return
                elif result == "cancel":
                    return

            # Redraw the main menu in the background
            self.draw(self.game.screen)




            # Draw taller popup overlay, but keep menu position as before
            popup_w, popup_h = 640, 440
            popup_x = (SCREEN_WIDTH - popup_w) // 2
            popup_y = (SCREEN_HEIGHT - popup_h) // 2
            popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
            overlay = pygame.Surface((popup_w, popup_h), pygame.SRCALPHA)
            overlay.fill((20, 20, 30, 240))
            pygame.draw.rect(overlay, (90, 120, 255, 180), overlay.get_rect(), width=5, border_radius=22)
            self.game.screen.blit(overlay, (popup_x, popup_y))

            # Glitchy warning text
            font = self.game.assets.font(38, True)
            draw_glitch_text(self.game.screen, font, "START NEW GAME?", popup_y + 74, WHITE, glitch_fx)
            font2 = self.game.assets.font(24, True)
            draw_center_text(self.game.screen, font2, "This will erase your current progress.", popup_y + 140, WHITE, glitch_fx)

            # Draw the confirm/cancel menu at the original position (as before)
            menu_y = popup_y + 250
            menu.draw(self.game.screen, self.game.assets, menu_y, glitch_fx)

            pygame.display.flip()
            clock.tick(FPS)

    def continue_game(self) -> None:
        self.game.progress.load()
        if not self.game.speedrun_active:
            self.game.start_speedrun()
        self.game.change_scene(
            GameplayScene,
            world=self.game.progress.world,
            level=self.game.progress.level,
        )

    def open_settings(self) -> None:
        run_settings_menu(self.game)

    def open_level_editor(self) -> None:
        # Disabled: Level editor is not accessible from the title screen
        pass
    def open_cosmetics_shop(self) -> None:
        from main import CosmeticsShopScene
        self.game.sound.play_event("menu_confirm")
        self.game.change_scene(CosmeticsShopScene)

    def open_skills_shop(self) -> None:
        from main import SkillsShopScene
        self.game.sound.play_event("menu_confirm")
        self.game.change_scene(SkillsShopScene)

    def quit_game(self) -> None:
        self.game.quit()

    def on_enter(self) -> None:
        self.game.pause_speedrun(True)
        self.game.stop_speedrun()
        self.game.play_music("title_theme.mp3")
        self._refresh_logo_assets()


    def on_exit(self) -> None:
        # Stop title music when leaving title screen, except when going to credits
        # CreditsScene will start its own music if needed
        if getattr(self.game, 'scene', None) and not isinstance(self.game.scene, type(self)):
            self.game.stop_music()

    def handle_event(self, event: pygame.event.Event) -> None:
        # Only allow level select code (Konami code) in title screen
        if event.type == pygame.KEYDOWN:
            if event.key == self._konami_code[self._konami_progress]:
                self._konami_progress += 1
                if self._konami_progress == len(self._konami_code):
                    self._konami_progress = 0
                    self.game.sound.play_event("menu_confirm")
                    from main import LevelSelectScene
                    self.game.change_scene(LevelSelectScene)
                    return
            else:
                if event.key == self._konami_code[0]:
                    self._konami_progress = 1
                else:
                    self._konami_progress = 0
            # Flight cheat via keyboard sequence
            if event.key == self._flight_code[self._flight_progress]:
                self._flight_progress += 1
                if self._flight_progress == len(self._flight_code):
                    self._flight_progress = 0
                    self.game.flight_cheat_enabled = True
                    self.game.sound.play_event("menu_confirm")
            else:
                self._flight_progress = 1 if event.key == self._flight_code[0] else 0
        # Controller flight code: use d-pad up/down and button A (assume button 0)
        if event.type == pygame.JOYHATMOTION:
            hat_dir = event.value  # (x, y)
            token = None
            if hat_dir == (0, 1):
                token = "up"
            elif hat_dir == (0, -1):
                token = "down"
            if token is not None:
                if token == self._flight_code_controller[self._flight_progress_controller]:
                    self._flight_progress_controller += 1
                else:
                    self._flight_progress_controller = 1 if token == self._flight_code_controller[0] else 0
        elif event.type == pygame.JOYBUTTONDOWN:
            btn_token = "a" if event.button == 0 else None
            if btn_token is not None:
                if btn_token == self._flight_code_controller[self._flight_progress_controller]:
                    self._flight_progress_controller += 1
                else:
                    self._flight_progress_controller = 1 if btn_token == self._flight_code_controller[0] else 0
        if self._flight_progress_controller == len(self._flight_code_controller):
            self._flight_progress_controller = 0
            self.game.flight_cheat_enabled = True
            try:
                self.game.sound.play_event("menu_confirm")
            except Exception:
                pass
        result = self.menu.handle_event(event)
        if result == "exit":
            self.game.quit()

    def update(self, dt: float) -> None:
        current_mode = bool(self.game.settings["glitch_fx"])
        if current_mode != self.logo_animated:
            self._refresh_logo_assets()

        # Animate background
        self.bg_anim_time += dt
        if current_mode:
            self.bg_glitch_timer += dt
            if self.bg_glitch_timer > random.uniform(1.2, 2.5):
                self.bg_glitch_active = not self.bg_glitch_active
                self.bg_glitch_timer = 0.0

        # Animate logo
        if len(self.logo_frames) > 1 and len(self.logo_durations) > self.logo_frame_index:
            duration = max(0.01, self.logo_durations[self.logo_frame_index])
            self.logo_frame_timer += dt
            while self.logo_frame_timer >= duration:
                self.logo_frame_timer -= duration
                self.logo_frame_index = (self.logo_frame_index + 1) % len(self.logo_frames)
                if len(self.logo_durations) > self.logo_frame_index:
                    duration = max(0.01, self.logo_durations[self.logo_frame_index])
                else:
                    duration = 0.1

    def draw(self, surface: pygame.Surface) -> None:
        # Draw animated GIF background (title_logo.gif)
        t = self.bg_anim_time
        gif_frames = self.logo_frames if self.logo_frames else []
        if gif_frames:
            frame = gif_frames[self.logo_frame_index % len(gif_frames)]
            # Center the GIF background
            bg_rect = frame.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120))
            surface.fill(self.background_color)
            surface.blit(frame, bg_rect)
        else:
            surface.fill(self.background_color)

        # Glitch/noise overlays (unchanged)
        if self.game.settings["glitch_fx"]:
            noise = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for _ in range(400):
                nx = random.randint(0, SCREEN_WIDTH - 1)
                ny = random.randint(0, SCREEN_HEIGHT - 1)
                alpha = random.randint(30, 80)
                noise.set_at((nx, ny), (255, 255, 255, alpha))
            surface.blit(noise, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            if self.bg_glitch_active:
                glitch = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                for _ in range(6):
                    gy = random.randint(0, SCREEN_HEIGHT - 1)
                    gh = random.randint(8, 32)
                    color = (
                        random.randint(180, 255),
                        random.randint(0, 255),
                        random.randint(180, 255),
                        random.randint(60, 120),
                    )
                    pygame.draw.rect(glitch, color, (0, gy, SCREEN_WIDTH, gh))
                surface.blit(glitch, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Animated logo with glitch flicker (drawn above background, nothing overlaps)
        if self.logo_frames:
            frame = self.logo_frames[self.logo_frame_index % len(self.logo_frames)]
            rect = frame.get_rect(center=self.logo_rect.center)
            if self.game.settings["glitch_fx"] and random.random() < 0.08:
                flicker = pygame.Surface(rect.size, pygame.SRCALPHA)
                for _ in range(40):
                    fx = random.randint(0, rect.width - 1)
                    fy = random.randint(0, rect.height - 1)
                    flicker.set_at((fx, fy), (255, 255, 255, random.randint(60, 180)))
                frame = frame.copy()
                frame.blit(flicker, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            surface.blit(frame, rect)

        # Menu and info: ensure nothing overlaps the logo area (logo is centered at y = SCREEN_HEIGHT//2 - 120)
        logo_bottom = self.logo_rect.bottom if self.logo_rect else (SCREEN_HEIGHT // 2 - 120 + 80)
        menu_y = logo_bottom + 20  # Move buttons up by reducing the offset
        t = self.bg_anim_time
        entry_rects: List[pygame.Rect] = []
        for idx, entry in enumerate(self.menu.entries):
            is_selected = (self.menu.selected == idx)
            font = self.game.assets.font(36 if is_selected else 28, True)
            text = entry.label() if callable(entry.label) else str(entry.label)
            color = (255, 255, 255) if is_selected else (180, 180, 200)
            y = menu_y + idx * 54
            if is_selected:
                y += int(6 * math.sin(t * 2.2 + idx))
            if self.game.settings["glitch_fx"] and is_selected and random.random() < 0.12:
                color = (
                    random.randint(200, 255),
                    random.randint(100, 255),
                    random.randint(200, 255),
                )
            render = font.render(text, True, color)
            rect = render.get_rect(center=(SCREEN_WIDTH // 2, y))
            surface.blit(render, rect)
            # Store hit-rects so the menu can react to mouse hover/click like settings menu
            padded = rect.inflate(32, 18)
            entry_rects.append(padded)
        # Update cached rects for mouse input
        self.menu._last_entry_rects = entry_rects

        # Subtle bottom info (well below logo)
        info_font = self.game.assets.font(18, False)
        draw_center_text(surface, info_font, "v1.0  |  Reality Collapsing  |  by James Griepentrog", SCREEN_HEIGHT - 36, (120, 120, 160))

    def _refresh_logo_assets(self) -> None:
        animated = bool(self.game.settings["glitch_fx"])
        frames, durations = self.game.assets.title_logo_frames(animated=animated)
        if not frames:
            fallback = pygame.Surface((420, 160), pygame.SRCALPHA)
            draw_center_text(fallback, self.game.assets.font(32, True), TITLE, fallback.get_height() // 2, WHITE)
            frames = [fallback]
            durations = [0.2]

        self.logo_frames = frames
        self.logo_durations = durations or [0.1]
        self.logo_frame_index = 0
        self.logo_frame_timer = 0.0
        self.logo_animated = animated
        first_frame = self.logo_frames[0]
        # Move the title logo higher by decreasing the y value (e.g., -180 instead of -120)
        self.logo_rect = first_frame.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 180))

class LevelSelectScene(Scene):
    def __init__(self, game: "Game"):
        super().__init__(game)
        self.world = self.game.progress.world
        self.level = self.game.progress.level
        self.blink = 0
        self.max_world = 10
        self.max_level = 10
        self.boss_world = 11  # Special value for boss levels
        self.boss_levels = 10

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.game.change_scene(TitleScene)
            elif event.key == pygame.K_RETURN:
                if self.world == self.boss_world:
                    self.game.change_scene(BossArenaScene, world=self.level, level=self.level)
                else:
                    self.game.change_scene(GameplayScene, world=self.world, level=self.level)
            elif event.key in (pygame.K_UP, pygame.K_w):
                if self.world == self.boss_world:
                    self.level = self.level + 1 if self.level < self.boss_levels else 1
                else:
                    self.level = self.level + 1 if self.level < self.max_level else 1
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.world == self.boss_world:
                    self.level = self.level - 1 if self.level > 1 else self.boss_levels
                else:
                    self.level = self.level - 1 if self.level > 1 else self.max_level
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                if self.world == 1:
                    self.world = self.boss_world
                    self.level = 1
                elif self.world == self.boss_world:
                    self.world = self.max_world
                    self.level = self.max_level
                else:
                    self.world = self.world - 1
                    self.level = 1
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                if self.world == self.max_world:
                    self.world = self.boss_world
                    self.level = 1
                elif self.world == self.boss_world:
                    self.world = 1
                    self.level = 1
                else:
                    self.world = self.world + 1
                    self.level = 1
        if event.type == pygame.JOYHATMOTION:
            hx, hy = event.value
            # Up/Down already come in via injected KEYDOWN events; only handle left/right here to avoid double steps
            if hx == -1:
                if self.world == 1:
                    self.world = self.boss_world
                    self.level = 1
                elif self.world == self.boss_world:
                    self.world = self.max_world
                    self.level = self.max_level
                else:
                    self.world = self.world - 1
                    self.level = 1
            elif hx == 1:
                if self.world == self.max_world:
                    self.world = self.boss_world
                    self.level = 1
                elif self.world == self.boss_world:
                    self.world = 1
                    self.level = 1
                else:
                    self.world = self.world + 1
                    self.level = 1

    def update(self, dt: float) -> None:
        self.blink = (self.blink + 1) % 60

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 20))
        font_big = self.game.assets.font(40, True)
        font_mid = self.game.assets.font(32, True)
        font_small = self.game.assets.font(22, False)

        draw_glitch_text(surface, font_big, "LEVEL SELECT", 120, WHITE, self.game.settings["glitch_fx"])
        if self.world == self.boss_world:
            draw_glitch_text(surface, font_mid, "Boss Fights", 260, WHITE, self.game.settings["glitch_fx"])
            draw_glitch_text(surface, font_mid, f"Boss {self.level}", 320, WHITE, self.game.settings["glitch_fx"])
        else:
            draw_glitch_text(surface, font_mid, f"World {self.world}", 260, WHITE, self.game.settings["glitch_fx"])
            draw_glitch_text(surface, font_mid, f"Level {self.level}", 320, WHITE, self.game.settings["glitch_fx"])

        if self.blink < 30:
            device = getattr(self.game, "last_input_device", "keyboard")
            if device == "controller":
                prompt_text = "A to start  |  B to return"
            else:
                prompt_text = "ENTER to start  |  ESC to return"
            draw_prompt_with_icons(surface, font_small, prompt_text, 520, WHITE, device=device)



class CosmeticsShopScene(Scene):
    """Cosmetics shop for outfits, hats, and trails."""
    def __init__(self, game: "Game"):
        super().__init__(game)
        self.outfit_costs = {
            "None": 0,
            "Neon Runner": 15,
            "Crimson Armor": 20,
            "Midnight": 20,
            "Gold": 25,
            "Verdant": 8,
            "Stone": 10,
            "Dune": 12,
            "Thorn": 14,
            "Frost": 16,
            "Ember": 18,
            "Sky": 20,
            "Circuit": 22,
            "Spectral": 24,
            "Void": 26,
        }
        self.hat_costs = {
            "None": 0,
            "Wizard": 12,
            "Pilot": 10,
            "Halo": 18,
            "Viking": 16,
            "Verdant": 8,
            "Stone": 10,
            "Dune": 12,
            "Thorn": 14,
            "Frost": 16,
            "Ember": 18,
            "Sky": 20,
            "Circuit": 22,
            "Spectral": 24,
            "Void": 26,
        }
        self.trail_costs = {
            "None": 0,
            "Glitter": 12,
            "Cyber": 15,
            "Ghost": 15,
            "Inferno": 18,
            "Verdant": 8,
            "Stone": 10,
            "Dune": 12,
            "Thorn": 14,
            "Frost": 16,
            "Ember": 18,
            "Sky": 20,
            "Circuit": 22,
            "Spectral": 24,
            "Void": 26,
        }
        self.tabs = [("outfit", "Outfits"), ("hat", "Hats"), ("trail", "Trails")]
        self.active_tab = "outfit"
        self._tab_rects: List[pygame.Rect] = []
        self.items: List[Tuple[str, int]] = []
        self._item_rects: List[pygame.Rect] = []
        self._item_cache: Dict[Tuple[str, str, Tuple[int, int]], pygame.Surface] = {}
        self._grid_cols = 1
        self.selected_index = 0
        self.scroll_row = 0
        self._grid_rows = 1
        self._visible_rows = 1
        self._refresh_items()

    def _owned(self, kind: str) -> List[str]:
        key_map = {
            "outfit": "owned_outfits",
            "trail": "owned_trails",
            "hat": "owned_hats",
        }
        key = key_map.get(kind, "")
        return list(self.game.cosmetics.get(key, []))

    def _tab_costs(self) -> Dict[str, Dict[str, int]]:
        return {
            "outfit": self.outfit_costs,
            "hat": self.hat_costs,
            "trail": self.trail_costs,
        }

    def _switch_tab(self, tab_key: str) -> None:
        if tab_key == self.active_tab:
            return
        self.active_tab = tab_key
        self.selected_index = 0
        self._refresh_items()

    def _status(self, kind: str, name: str, cost: int) -> str:
        owned = name in self._owned(kind)
        selected = self.game.cosmetics.get(kind, "None") == name
        if selected:
            return "Selected"
        elif owned or cost == 0:
            return "Owned"
        return f"{cost} coins"

    def _refresh_items(self) -> None:
        costs = self._tab_costs().get(self.active_tab, {})
        self.items = [(name, cost) for name, cost in costs.items()]
        if self.selected_index >= len(self.items):
            self.selected_index = max(0, len(self.items) - 1)
        self.scroll_row = 0

    def _clamp_scroll(self) -> None:
        max_scroll = max(0, self._grid_rows - self._visible_rows)
        self.scroll_row = max(0, min(self.scroll_row, max_scroll))

    def _ensure_selected_visible(self) -> None:
        row = self.selected_index // max(1, self._grid_cols)
        visible_rows = max(1, self._visible_rows)
        if row < self.scroll_row:
            self.scroll_row = row
        elif row >= self.scroll_row + visible_rows:
            self.scroll_row = row - visible_rows + 1
        self._clamp_scroll()

    def _item_surface(self, kind: str, name: str, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        key = (kind, name, size)
        cached = self._item_cache.get(key)
        if cached is not None:
            return cached
        surface: Optional[pygame.Surface] = None
        if kind == "outfit":
            if name == "None":
                surface = pygame.Surface(size, pygame.SRCALPHA)
                line_width = max(6, min(size) // 10)
                pad = max(10, min(size) // 6)
                pygame.draw.line(surface, (220, 60, 60, 255), (pad, pad), (size[0] - pad, size[1] - pad), line_width)
                pygame.draw.line(surface, (220, 60, 60, 255), (size[0] - pad, pad), (pad, size[1] - pad), line_width)
            else:
                base_dir = ASSET_DIR / "outfits" / name
                if base_dir.exists():
                    png_path = base_dir / "idle_0.png"
                    if not png_path.exists():
                        options = sorted(base_dir.glob("*.png"))
                        png_path = options[0] if options else png_path
                    if png_path.exists():
                        try:
                            surface = pygame.image.load(str(png_path)).convert_alpha()
                        except Exception as exc:
                            print(f"[Assets] Failed to load outfit preview {png_path}: {exc}")
        elif kind == "hat":
            if name == "None":
                surface = pygame.Surface(size, pygame.SRCALPHA)
                line_width = max(6, min(size) // 10)
                pad = max(10, min(size) // 6)
                pygame.draw.line(surface, (220, 60, 60, 255), (pad, pad), (size[0] - pad, size[1] - pad), line_width)
                pygame.draw.line(surface, (220, 60, 60, 255), (size[0] - pad, pad), (pad, size[1] - pad), line_width)
            else:
                png_path = HAT_DIR / f"{name}.png"
                if png_path.exists():
                    try:
                        surface = pygame.image.load(str(png_path)).convert_alpha()
                    except Exception as exc:
                        print(f"[Assets] Failed to load hat preview {png_path}: {exc}")
        elif kind == "trail":
            if name == "None":
                surface = pygame.Surface(size, pygame.SRCALPHA)
                line_width = max(6, min(size) // 10)
                pad = max(10, min(size) // 6)
                pygame.draw.line(surface, (220, 60, 60, 255), (pad, pad), (size[0] - pad, size[1] - pad), line_width)
                pygame.draw.line(surface, (220, 60, 60, 255), (size[0] - pad, pad), (pad, size[1] - pad), line_width)
            else:
                surface = self.game.assets.trail_texture(name, size)

        if surface is not None and surface.get_size() != size:
            surface = pygame.transform.smoothscale(surface, size)
        self._item_cache[key] = surface
        return surface

    def _buy_or_select(self, kind: str, name: str, cost: int) -> None:
        coins = getattr(self.game.progress, "coins", 0)
        owned_map = {
            "outfit": "owned_outfits",
            "trail": "owned_trails",
            "hat": "owned_hats",
        }
        owned_key = owned_map.get(kind, "")
        owned = self.game.cosmetics.get(owned_key, [])
        if name in owned or cost == 0:
            self.game.cosmetics[kind] = name
        else:
            if coins < cost:
                self.game.sound.play_event("menu_move")
                return
            coins -= cost
            owned.append(name)
            self.game.cosmetics[owned_key] = owned
            self.game.cosmetics[kind] = name
            self.game.progress.coins = coins
        # Apply tint immediately if outfit changed
        if kind == "outfit":
            self.game.player_color = OUTFIT_COLORS.get(name, self.game.player_color)
        if kind == "hat":
            # no immediate sprite change beyond overlay color
            pass
        self.game.progress.save(
            self.game.progress.world,
            self.game.progress.level,
            getattr(self.game, "player_color", None),
            coins=coins,
            skills=self.game.skills,
            cosmetics=self.game.cosmetics,
        )
        self._apply_live_cosmetics()
        self._refresh_items()

    def _apply_live_cosmetics(self) -> None:
        """Apply cosmetics to the active gameplay scene when shops are opened from pause."""
        scene = getattr(self.game, "_pause_return_scene", None)
        if not scene or not hasattr(scene, "player"):
            return
        player = scene.player
        outfit_form = self.game.active_outfit_form()
        player_color = self.game.active_outfit_color()
        if outfit_form:
            player_color = None
        player.form_name = outfit_form
        player.animations = player._load_frames()
        if player.character_name == "player" and player_color:
            player.tint_color = player_color
            player._apply_color_tint(player_color)
        else:
            player.tint_color = None
        current_frames = player.animations.get(player.state) or player.animations.get("idle")
        if current_frames:
            current_center = player.rect.center
            player.image = current_frames[player.frame_index % len(current_frames)]
            player.rect = player.image.get_rect(center=current_center)
        if hasattr(scene, "trail_style"):
            scene.trail_style = self.game.active_trail_style()
            scene.trail_color = scene.trail_style["color"] if scene.trail_style else None
            scene._player_trail = []
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            pause_scene = getattr(self.game, "_pause_return_scene", None)
            if pause_scene:
                action = run_pause_menu(pause_scene)
                if action == "menu":
                    self.game.change_scene(TitleScene)
                elif action == "quit":
                    self.game.quit()
                elif action == "shops":
                    self.game.change_scene(ShopsHubScene, return_scene=pause_scene)
                else:
                    self.game.scene = pause_scene
            else:
                self.game.change_scene(TitleScene)
        else:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._tab_rects:
                for idx, rect in enumerate(self._tab_rects):
                    if rect.collidepoint(event.pos):
                        self._switch_tab(self.tabs[idx][0])
                        return
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    idx = event.key - pygame.K_1
                    if 0 <= idx < len(self.tabs):
                        self._switch_tab(self.tabs[idx][0])
                        return
                if not self.items:
                    return
                if event.key in (pygame.K_a, pygame.K_LEFT):
                    self.selected_index = max(0, self.selected_index - 1)
                elif event.key in (pygame.K_d, pygame.K_RIGHT):
                    self.selected_index = min(len(self.items) - 1, self.selected_index + 1)
                elif event.key in (pygame.K_w, pygame.K_UP):
                    self.selected_index = max(0, self.selected_index - self._grid_cols)
                elif event.key in (pygame.K_s, pygame.K_DOWN):
                    self.selected_index = min(len(self.items) - 1, self.selected_index + self._grid_cols)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    name, cost = self.items[self.selected_index]
                    self._buy_or_select(self.active_tab, name, cost)
                self._ensure_selected_visible()
            elif event.type == pygame.MOUSEMOTION and self._item_rects:
                for idx, rect in enumerate(self._item_rects):
                    if rect.collidepoint(event.pos):
                        if idx != self.selected_index:
                            self.selected_index = idx
                            self.game.sound.play_event("menu_move")
                            self._ensure_selected_visible()
                        break
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._item_rects:
                for idx, rect in enumerate(self._item_rects):
                    if rect.collidepoint(event.pos):
                        self.selected_index = idx
                        name, cost = self.items[idx]
                        self._buy_or_select(self.active_tab, name, cost)
                        self._ensure_selected_visible()
                        break
            elif event.type == pygame.MOUSEWHEEL:
                if event.y != 0:
                    self.scroll_row = max(0, self.scroll_row - event.y)
                    self._clamp_scroll()

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((12, 12, 28))
        if self.game.settings["glitch_fx"]:
            _draw_glitch_overlay(surface)
        title_font = self.game.assets.font(48, True)
        draw_glitch_text(surface, title_font, "COSMETICS SHOP", 70, WHITE, self.game.settings["glitch_fx"])
        info_font = self.game.assets.font(24, False)
        coins = getattr(self.game.progress, "coins", 0)
        draw_center_text(surface, info_font, f"Coins: {coins}", 130, (255, 223, 70))
        tab_font = self.game.assets.font(22, True)
        self._tab_rects = []
        tab_width = 180
        tab_height = 40
        tab_gap = 16
        total_width = tab_width * len(self.tabs) + tab_gap * (len(self.tabs) - 1)
        start_x = (SCREEN_WIDTH - total_width) // 2
        tab_y = 170
        for idx, (key, label) in enumerate(self.tabs):
            x = start_x + idx * (tab_width + tab_gap)
            rect = pygame.Rect(x, tab_y, tab_width, tab_height)
            self._tab_rects.append(rect)
            is_active = key == self.active_tab
            base_color = (40, 50, 80) if not is_active else (90, 120, 200)
            border_color = (120, 140, 200) if not is_active else (220, 240, 255)
            pygame.draw.rect(surface, base_color, rect, border_radius=10)
            pygame.draw.rect(surface, border_color, rect, 2, border_radius=10)
            tab_render = tab_font.render(label, True, WHITE)
            tab_rect = tab_render.get_rect(center=rect.center)
            surface.blit(tab_render, tab_rect)
        current = self.game.assets.font(20, False)
        current_text = (
            f"Outfit: {self.game.cosmetics.get('outfit', 'None')}  |  "
            f"Hat: {self.game.cosmetics.get('hat', 'None')}  |  "
            f"Trail: {self.game.cosmetics.get('trail', 'None')}"
        )
        draw_center_text(surface, current, current_text, 230, (200, 220, 255))
        # Items grid below the tab row
        self._item_rects = []
        grid_top = 270
        grid_width = SCREEN_WIDTH - 240
        grid_height = SCREEN_HEIGHT - 140 - grid_top
        gap = 22
        min_item_width = 140
        min_item_height = 140
        item_count = max(1, len(self.items))
        max_cols = max(1, min(item_count, grid_width // (min_item_width + gap)))
        cols = max_cols
        rows = (item_count + cols - 1) // cols
        item_width = max(min_item_width, (grid_width - gap * (cols - 1)) // cols)
        item_height = max(min_item_height, (grid_height - gap * (rows - 1)) // rows)
        self._grid_cols = cols
        self._grid_rows = rows
        self._visible_rows = rows
        self.scroll_row = 0
        total_row_width = cols * item_width + (cols - 1) * gap
        start_x = (SCREEN_WIDTH - total_row_width) // 2
        name_font = self.game.assets.font(18, True)
        status_font = self.game.assets.font(16, False)
        image_dim = max(64, min(item_width, item_height) - 70)
        image_size = (image_dim, image_dim)
        for idx, (name, cost) in enumerate(self.items):
            col = idx % cols
            row = idx // cols
            x = start_x + col * (item_width + gap)
            y = grid_top + row * (item_height + gap)
            rect = pygame.Rect(x, y, item_width, item_height)
            self._item_rects.append(rect)
            selected = idx == self.selected_index
            box_color = (28, 32, 54) if not selected else (60, 80, 140)
            border = (80, 90, 130) if not selected else (220, 230, 255)
            pygame.draw.rect(surface, box_color, rect, border_radius=14)
            pygame.draw.rect(surface, border, rect, 2, border_radius=14)
            name_render = name_font.render(name, True, WHITE)
            name_rect = name_render.get_rect(center=(rect.centerx, rect.top + 24))
            surface.blit(name_render, name_rect)
            preview = self._item_surface(self.active_tab, name, image_size)
            if preview is not None:
                preview_rect = preview.get_rect(center=(rect.centerx, rect.centery - 6))
                surface.blit(preview, preview_rect)
            status = self._status(self.active_tab, name, cost)
            status_render = status_font.render(status, True, (200, 220, 255))
            status_rect = status_render.get_rect(center=(rect.centerx, rect.bottom - 26))
            surface.blit(status_render, status_rect)


class SkillsShopScene(Scene):
    """Skills shop with purchasable upgrades."""
    def __init__(self, game: "Game"):
        super().__init__(game)
        self.costs = {
            "rapid_charge": 5,
            "blast_radius": 8,
            "shield_pulse": 6,
            "reflective_shield": 6,
            "stagger": 7,
            "extra_health": 5,  # per level
        }
        self._rebuild_menu()

    def _rebuild_menu(self) -> None:
        entries = [
            MenuEntry(lambda: self._label("Rapid Charge", "rapid_charge"), lambda: self._buy_skill("rapid_charge")),
            MenuEntry(lambda: self._label("Blast Radius", "blast_radius"), lambda: self._buy_skill("blast_radius")),
            MenuEntry(lambda: self._label("Shield Pulse", "shield_pulse"), lambda: self._buy_skill("shield_pulse")),
            MenuEntry(lambda: self._label("Reflective Shield", "reflective_shield"), lambda: self._buy_skill("reflective_shield")),
            MenuEntry(lambda: self._label("Stagger", "stagger"), lambda: self._buy_skill("stagger")),
            MenuEntry(self._extra_health_label, self._buy_extra_health),
            MenuEntry(lambda: "Back", lambda: "exit"),
        ]
        self.menu = VerticalMenu(entries, sound=self.game.sound)

    def _label(self, name: str, key: str) -> str:
        owned = self.game.skills.get(key, False)
        return f"{name} [{'Owned' if owned else f'Cost {self.costs.get(key, 0)}'}]"

    def _extra_health_label(self) -> str:
        lvl = int(self.game.skills.get("extra_health_levels", 0) or 0)
        status = "Maxed" if lvl >= 25 else f"Cost {self.costs.get('extra_health', 5)}"
        return f"Extra Health (Lv {lvl}/25) [{status}]"

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            pause_scene = getattr(self.game, "_pause_return_scene", None)
            if pause_scene:
                action = run_pause_menu(pause_scene)
                if action == "menu":
                    self.game.change_scene(TitleScene)
                elif action == "quit":
                    self.game.quit()
                elif action == "shops":
                    self.game.change_scene(ShopsHubScene, return_scene=pause_scene)
                else:
                    self.game.scene = pause_scene
            else:
                self.game.change_scene(TitleScene)
        else:
            result = self.menu.handle_event(event)
            if callable(result):
                result()
                return
            if result == "exit":
                if self.return_scene:
                    action = run_pause_menu(self.return_scene)
                    if action == "menu":
                        self.game.change_scene(TitleScene)
                    elif action == "quit":
                        self.game.quit()
                    else:
                        self.game.scene = self.return_scene
                else:
                    self.game.change_scene(TitleScene)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 24))
        if self.game.settings["glitch_fx"]:
            _draw_glitch_overlay(surface)
        title_font = self.game.assets.font(48, True)
        draw_glitch_text(surface, title_font, "SKILLS SHOP", 140, WHITE, self.game.settings["glitch_fx"])
        info_font = self.game.assets.font(22, False)
        coins = getattr(self.game.progress, "coins", 0)
        draw_center_text(surface, info_font, f"Coins: {coins}", 200, (255, 223, 70))
        draw_center_text(surface, info_font, "Select a skill to purchase. Purchased skills stay active.", 230, (200, 200, 230))
        # Position menu a bit lower under the instruction text
        self.menu.draw(surface, self.game.assets, 320, self.game.settings["glitch_fx"])

    def _buy_skill(self, key: str):
        if self.game.skills.get(key):
            return
        cost = self.costs.get(key, 5)
        coins = getattr(self.game.progress, "coins", 0)
        if coins < cost:
            return
        coins -= cost
        self.game.skills[key] = True
        self.game.progress.coins = coins
        self.game.progress.save(self.game.progress.world, self.game.progress.level, getattr(self.game, "player_color", None), coins=coins, skills=self.game.skills, cosmetics=self.game.cosmetics)
        self._rebuild_menu()
        self.game.sound.play_event("menu_confirm")

    def _buy_extra_health(self):
        current = int(self.game.skills.get("extra_health_levels", 0) or 0)
        if current >= 25:
            return
        cost = self.costs.get("extra_health", 5)
        coins = getattr(self.game.progress, "coins", 0)
        if coins < cost:
            return
        coins -= cost
        current += 1
        self.game.skills["extra_health_levels"] = current
        # Apply to player if present
        if hasattr(self.game.scene, "player"):
            try:
                self.game.scene.player.max_health += 1
                self.game.scene.player.health = min(self.game.scene.player.health + 1, self.game.scene.player.max_health)
            except Exception:
                pass
        self.game.progress.coins = coins
        self.game.progress.save(self.game.progress.world, self.game.progress.level, getattr(self.game, "player_color", None), coins=coins, skills=self.game.skills, cosmetics=self.game.cosmetics)
        self._rebuild_menu()
        self.game.sound.play_event("menu_confirm")


class ShopsHubScene(Scene):
    """Hub menu to pick between Cosmetics and Skills shops."""
    def __init__(self, game: "Game", return_scene: Optional["GameplayScene"] = None):
        super().__init__(game)
        self.return_scene = return_scene
        self.game._pause_return_scene = return_scene
        self.menu = VerticalMenu(
            [
                MenuEntry(lambda: "Cosmetics Shop", self._open_cosmetics),
                MenuEntry(lambda: "Skills Shop", self._open_skills),
                MenuEntry(lambda: "Back", lambda: "exit"),
            ],
            sound=self.game.sound,
        )

    def _open_cosmetics(self):
        self.game.sound.play_event("menu_confirm")
        self.game.change_scene(CosmeticsShopScene)

    def _open_skills(self):
        self.game.sound.play_event("menu_confirm")
        self.game.change_scene(SkillsShopScene)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.return_scene:
                action = run_pause_menu(self.return_scene)
                if action == "menu":
                    self.game.change_scene(TitleScene)
                elif action == "quit":
                    self.game.quit()
                elif action == "shops":
                    self.game.change_scene(ShopsHubScene, return_scene=self.return_scene)
                else:
                    self.game.scene = self.return_scene
            else:
                self.game.change_scene(TitleScene)
        else:
            result = self.menu.handle_event(event)
            if callable(result):
                return result()
            if result == "exit":
                if self.return_scene:
                    action = run_pause_menu(self.return_scene)
                    if action == "menu":
                        self.game.change_scene(TitleScene)
                    elif action == "quit":
                        self.game.quit()
                    elif action == "shops":
                        self.game.change_scene(ShopsHubScene, return_scene=self.return_scene)
                    else:
                        self.game.scene = self.return_scene
                else:
                    self.game.change_scene(TitleScene)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((12, 12, 26))
        if self.game.settings["glitch_fx"]:
            _draw_glitch_overlay(surface)
        title_font = self.game.assets.font(48, True)
        draw_glitch_text(surface, title_font, "SHOPS", 140, WHITE, self.game.settings["glitch_fx"])
        info_font = self.game.assets.font(22, False)
        draw_center_text(surface, info_font, "Choose a shop to enter.", 220, (200, 200, 230))
        self.menu.draw(surface, self.game.assets, SCREEN_HEIGHT // 2 + 40, self.game.settings["glitch_fx"])


class GameplayScene(Scene):

    def __init__(self, game: "Game", world: int, level: int):
        super().__init__(game)
        self.world = world
        self.level = level

        # progress trackers
        self.flight_progress = 0
        self.konami_progress = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        # DO NOT call super().handle_event(event)
        # Place any additional event handling for gameplay here if needed
        pass

    def update(self, dt: float) -> None:
        # Failsafe: always enable flight if cheat is active
        if getattr(self.game, "flight_cheat_enabled", False):
            if hasattr(self, "player") and hasattr(self.player, "can_fly") and not self.player.can_fly:
                print("[DEBUG] Failsafe: Enabling flight in update() because cheat is active.")
                if hasattr(self.player, "enable_flight"):
                    self.player.enable_flight()
        # ...existing code...
    def enable_level_editing(self):
        if hasattr(self, '_level_editor_enabled') and self._level_editor_enabled:
            return
        self._level_editor_enabled = True
        self._level_editor_hide_ui = True
        self._level_editor_flight = True
        if hasattr(self.player, 'enable_flight'):
            self.player.enable_flight()
        self._level_editor_saved = False

    def disable_level_editing(self):
        self._level_editor_enabled = False
        self._level_editor_hide_ui = False
        self._level_editor_flight = False
        if hasattr(self.player, 'disable_flight'):
            self.player.disable_flight()
    def draw_level_editor_toolbox(self, surface):
        # Toolbox at bottom center, icon-only, no names
        object_types = [
            ("cursor", (255, 255, 255), "cursor.png"),
            ("platform", (180, 180, 180), "platform.png"),
            ("coin", (255, 220, 60), "coin.png"),
            ("spike", (220, 80, 80), "spike.png"),
            ("boost", (255, 200, 60), "boost.png"),
            ("spring", (180, 255, 180), "spring.png"),
            ("wind_orb", (80, 200, 255), "wind_orb.png"),
            ("icicle", (200, 220, 255), "icicle.png"),
            ("electric_tile", (100, 100, 255), "electric_tile.png"),
            ("ghost_orb", (150, 150, 200), "ghost_orb.png"),
            ("checkpoint", (100, 220, 255), "checkpoint.png"),
        ]
        icon_size = 48
        spacing = 18
        total_width = len(object_types) * (icon_size + spacing) + spacing
        screen_w = surface.get_width()
        y = surface.get_height() - icon_size - 24
        x_start = (screen_w - total_width) // 2 + spacing
        # Store clickable rects for mouse interaction
        if not hasattr(self, '_toolbox_rects'):
            self._toolbox_rects = []
        self._toolbox_rects.clear()
        # Draw toolbox background bar
        bar_rect = pygame.Rect(x_start - spacing, y - 12, total_width, icon_size + 24)
        shadow = pygame.Surface((bar_rect.width + 8, bar_rect.height + 8), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0,0,0,80), shadow.get_rect(), border_radius=18)
        surface.blit(shadow, (bar_rect.x + 4, bar_rect.y + 4))
        pygame.draw.rect(surface, (38, 44, 60), bar_rect, border_radius=18)
        # Draw each tool icon
        for idx, (obj_type, color, icon_file) in enumerate(object_types):
            x = x_start + idx * (icon_size + spacing)
            rect = pygame.Rect(x, y, icon_size, icon_size)
            self._toolbox_rects.append((rect, obj_type))
            is_selected = getattr(self, '_level_editor_selected_tool', 'platform') == obj_type
            # Button background
            pygame.draw.rect(surface, (60, 70, 100) if is_selected else (48, 54, 74), rect, border_radius=12)
            if is_selected:
                pygame.draw.rect(surface, (110, 170, 255), rect, 3, border_radius=12)
            # Icon
            icon = None
            try:
                icon = pygame.image.load(str(OBJECT_DIR / icon_file)).convert_alpha()
                icon = pygame.transform.smoothscale(icon, (36, 36))
            except Exception:
                pass
            icon_rect = pygame.Rect(rect.x + 6, rect.y + 6, 36, 36)
            if icon:
                surface.blit(icon, icon_rect)
            else:
                pygame.draw.rect(surface, color, icon_rect, border_radius=8)
    def handle_level_editor_mouse(self, event):
        # Handle mouse clicks for toolbox selection and object placement/deletion
        if not hasattr(event, 'pos'):
            return
        mouse_pos = event.pos
        # Toolbox selection (always on left click)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, obj_type in getattr(self, '_toolbox_rects', []):
                if rect.collidepoint(mouse_pos):
                    self._level_editor_selected_tool = obj_type
                    return
        # If cursor tool is selected, enable drag/move only (no placement)
        if getattr(self, '_level_editor_selected_tool', 'platform') == 'cursor':
            return
        # Place object (left click, not on toolbox)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, obj_type in getattr(self, '_toolbox_rects', []):
                if rect.collidepoint(mouse_pos):
                    return  # Don't place if clicking toolbox
            self.place_level_editor_object(mouse_pos)
        # Delete object (right click, not on toolbox)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            for rect, obj_type in getattr(self, '_toolbox_rects', []):
                if rect.collidepoint(mouse_pos):
                    return  # Don't delete if clicking toolbox
            self.delete_level_editor_object(mouse_pos)

    def place_level_editor_object(self, pos):
        # Place the selected object at the given position
        tool = getattr(self, '_level_editor_selected_tool', 'platform')
        x, y = pos
        if tool == 'platform':
            rect = pygame.Rect(x-50, y-10, 100, 20)
            self.content.platforms.add(Platform(rect.x, rect.y, rect.width, rect.height, self.world, self.game.assets))
        elif tool == 'coin':
            self.content.coins.add(Coin(x, y))
        elif tool == 'spike':
            # Use correct direction and world if needed
            self.content.specials.add(Spike(x, y, direction="up", world=self.world))
        elif tool == 'boost':
            self.content.specials.add(Boost(x, y))
        elif tool == 'spring':
            self.content.specials.add(Spring(x, y))
        elif tool == 'wind_orb':
            self.content.specials.add(WindOrb(x, y))
        elif tool == 'icicle':
            self.content.specials.add(Icicle(x, y))
        elif tool == 'electric_tile':
            self.content.specials.add(ElectricTile(x, y))
        elif tool == 'ghost_orb':
            self.content.specials.add(GhostOrb(x, y))
        elif tool == 'checkpoint':
            self.content.specials.add(Checkpoint(x, y))

    def delete_level_editor_object(self, pos):
        # Delete the object under the cursor (platform, coin, or special)
        x, y = pos
        # Check platforms
        for plat in list(self.content.platforms):
            if plat.rect.collidepoint(x, y):
                self.content.platforms.remove(plat)
                return
        # Check coins
        for coin in list(self.content.coins):
            if coin.rect.collidepoint(x, y):
                self.content.coins.remove(coin)
                return
        # Check specials
        for special in list(self.content.specials):
            if special.rect.collidepoint(x, y):
                self.content.specials.remove(special)
                return

    def draw_level_editor_controls(self, surface):
        # Draw controls overlay at the top left
        font = pygame.font.SysFont("consolas", 18)
        controls = [
            "LMB Select Tool",
            "LMB Add Object",
            "RMB Delete Object",
            "Ctrl+S Save",
            "Esc Exit Editor (revert if not saved)",
            "P Playtest/Return",
            "WASD/Arrows Pan Camera",
            "Mouse Move/Select/Drag"
        ]
        y = 10
        for ctrl in controls:
            draw_prompt_with_icons(surface, font, ctrl, y + font.get_height() // 2, (255, 255, 255), device="keyboard", x=18)
            y += font.get_height() + 4
    def enable_level_editing(self):
        if hasattr(self, '_level_editor_enabled') and self._level_editor_enabled:
            return
        self._level_editor_enabled = True
        self._level_editor_hide_ui = True
        self._level_editor_flight = True
        self._level_editor_saved = False
        # Save a deep copy of the current level state for revert
        import copy
        self._level_editor_backup = copy.deepcopy(self.content)
        if hasattr(self.player, 'enable_flight'):
            self.player.enable_flight()

    def disable_level_editing(self, revert=False):
        self._level_editor_enabled = False
        self._level_editor_hide_ui = False
        self._level_editor_flight = False
        if revert and hasattr(self, '_level_editor_backup'):
            self.content = self._level_editor_backup
            self._level_editor_backup = None
        if hasattr(self.player, 'disable_flight'):
            self.player.disable_flight()
        # --- Respawn all coins when exiting editor ---
        if not revert:
            self._respawn_all_coins()
        # Only save to .lvl file if editor was closed with Ctrl+S (not on revert or playtest exit)
        if getattr(self, '_level_editor_saved', False):
            self._level_editor_saved = False  # Reset flag after saving
            if hasattr(self, 'save_level'):
                self.save_level()

    def _respawn_all_coins(self):
        """Respawn all coins to their original positions from the level file."""
        # Only run if not in editor or playtest
        path = getattr(self, 'level_path', None)
        if not path or not hasattr(self, 'content'):
            return
        # Persistence removed; nothing to reload
    def handle_event(self, event: pygame.event.Event) -> None:
        # ...existing code...
        if hasattr(self, '_level_editor_enabled') and self._level_editor_enabled:
            self.handle_level_editor_mouse(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f:
                    # Toggle flight
                    if hasattr(self.player, 'can_fly') and self.player.can_fly:
                        self.player.disable_flight()
                    else:
                        self.player.enable_flight()
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    # Save and exit edit mode
                    self.save_level() if hasattr(self, 'save_level') else None
                    self._level_editor_saved = True
                    self.disable_level_editing(revert=False)
                elif event.key == pygame.K_ESCAPE:
                    # Exit and revert if not saved
                    self.disable_level_editing(revert=not getattr(self, '_level_editor_saved', False))
                elif event.key == pygame.K_p:
                    # Enter playtest mode
                    self._level_editor_playtest = True
                    if hasattr(self.player, 'disable_flight'):
                        self.player.disable_flight()
            return
        if hasattr(self, '_level_editor_playtest') and self._level_editor_playtest:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                # Return to editor mode
                self._level_editor_playtest = False
                if hasattr(self.player, 'enable_flight'):
                    self.player.enable_flight()
            return
        # ...existing code...
    def update(self, dt: float) -> None:
        # Ensure flight cheat is always applied if enabled
        if hasattr(self.game, "flight_cheat_enabled") and self.game.flight_cheat_enabled:
            if hasattr(self.player, "can_fly") and not self.player.can_fly:
                if hasattr(self.player, "enable_flight"):
                    self.player.enable_flight()
        # If in playtest mode, check for reaching portal
        if hasattr(self, '_level_editor_playtest') and self._level_editor_playtest:
            if self.content.goal and self.player.rect.colliderect(self.content.goal.rect):
                self._level_editor_playtest = False
                if hasattr(self.player, 'enable_flight'):
                    self.player.enable_flight()
        # ...existing code...
    def enable_level_editing(self):
        # Attach a LevelEditorScene-like editor to this scene for in-place editing
        if hasattr(self, '_level_editor_enabled') and self._level_editor_enabled:
            return  # Already enabled
        self._level_editor_enabled = True
        # Add editor state/logic as needed (e.g., toggles, UI, object manipulation)
        # You may want to expose editor controls in handle_event, update, and draw
        # For now, just set the flag; you can expand this with full editor logic
    @classmethod
    def from_custom_level(cls, game, path):
        # Load level data from custom file and spawn at the editor's spawn_point
        with open(path, "r") as f:
            data = json.load(f)
        # Use world 1 by default for custom levels, or infer from background if needed
        world = 1
        background = data.get("background", "grass")
        world_map = {
            "grass": 1, "cave": 2, "desert": 3, "forest": 4, "snow": 5,
            "flame": 6, "sky": 7, "circuit": 8, "temple": 9, "glitch": 10,
        }
        world = world_map.get(background, 1)
        # Level number is arbitrary for custom
        level = 1
        scene = cls(game, world, level)
        # Overwrite content with custom data
        scene.content = game.level_generator.generate_from_dict(data)
        # Set player spawn to the custom spawn_point
        spawn = tuple(data.get("spawn_point", (100, 450)))
        # Load character from settings
        settings_mgr = SettingsManager(SETTINGS_FILE)
        character_name = settings_mgr.data.get("character", "player")
        outfit_form = game.active_outfit_form()
        player_color = game.active_outfit_color()
        if outfit_form:
            player_color = None
        scene.player = Player(
            spawn,
            game.sound,
            color=player_color,
            character_name=character_name,
            form_name=outfit_form,
        )
        scene._apply_player_skills()
        scene.trail_style = game.active_trail_style()
        scene.trail_color = scene.trail_style["color"] if scene.trail_style else None
        scene._player_trail = []
        scene._snap_camera_to_player()
        return scene

    def _apply_player_skills(self) -> None:
        """Sync unlocked skills to the active player instance (movement + health)."""
        if not hasattr(self, "player"):
            return
        self.player.skills = getattr(self.game, "skills", {})
        extra_hp = int(self.player.skills.get("extra_health_levels", 0) or 0)
        base_hp = getattr(self.player, "base_max_health", self.player.max_health)
        self.player.max_health = base_hp + extra_hp
        self.player.health = self.player.max_health
    def __init__(self, game: "Game", world: int, level: int):
        super().__init__(game)
        self.world = world
        self.level = level
        self.background = self.game.assets.background(self.world)
        self._background_variants = self._generate_background_variants(self.background)
        self.content = game.level_generator.generate(self.world, self.level)
        if self.content.goal is None:
            self.content.goal = Goal(700, 520, self.world, self.game.assets)
        self.is_tower = self.level % 10 == 0
        spawn_point = self._compute_spawn_point()
        # Use selected character if set, else fallback to settings or default
        character_name = getattr(self.game, "selected_character", None)
        form_name = getattr(self.game, "selected_form", None)
        if not character_name:
            settings_mgr = SettingsManager(SETTINGS_FILE)
            character_name = settings_mgr.data.get("character", "player")
        if not form_name:
            form_name = None
        outfit_form = self.game.active_outfit_form()
        if form_name is None:
            form_name = outfit_form
        player_color = self.game.active_outfit_color()
        if form_name == outfit_form and outfit_form:
            player_color = None
        self.player = Player(
            spawn_point,
            self.game.sound,
            color=player_color,
            character_name=character_name,
            form_name=form_name,
        )
        self._apply_player_skills()
        self.trail_style = self.game.active_trail_style()
        self.trail_color = self.trail_style["color"] if self.trail_style else None
        self._player_trail: List[Dict[str, Any]] = []
        # Enable flight cheat if unlocked
        if hasattr(self.game, "flight_cheat_enabled") and self.game.flight_cheat_enabled:
            if hasattr(self.player, "enable_flight"):
                self.player.enable_flight()
        self.tower_timer = 3.0 if self.is_tower else 0
        self.glitch_active = False
        self.glitch_started = 0.0
        self.camera_y = 0.0
        self.camera_x = 0.0
        self.top_bound = 0.0
        self.bottom_bound = 0.0
        # Initialize weather system
        self.weather = WeatherSystem(SCREEN_WIDTH, SCREEN_HEIGHT)
        self._set_world_weather()
        self.left_bound = 0.0
        self.right_bound = 0.0
        self.dynamic_glitch_active = False
        self.dynamic_glitch_end = 0.0
        self.dynamic_glitch_strength = 0.0
        self._update_bounds()

    def on_enter(self) -> None:
        # Stop any previous music (including title theme) before playing world music
        self.game.stop_music()
        self._refresh_world()

    def _set_world_weather(self) -> None:
        """Set weather effects based on the current world"""
        bounds = (
            float(getattr(self.content, "min_x", 0.0)),
            float(getattr(self.content, "max_x", SCREEN_WIDTH)),
            float(getattr(self.content, "min_y", 0.0)),
            float(getattr(self.content, "max_y", SCREEN_HEIGHT)),
        )
        offset = (self.camera_x, self.camera_y)
        if self.world == 5:  # Frozen Peaks - Snow
            self.weather.set_weather(SNOW_PARTICLE, 150, camera_offset=offset, bounds=bounds)
        elif self.world == 6:  # Molten Core - Ash
            self.weather.set_weather(ASH_PARTICLE, 80, camera_offset=offset, bounds=bounds)
        elif self.world == 7:  # Air/Wind - Light snow
            self.weather.set_weather(SNOW_PARTICLE, 50, camera_offset=offset, bounds=bounds)
        else:
            self.weather.set_weather(None, camera_offset=offset, bounds=bounds)

    def _refresh_world(self) -> None:
        self.background = self.game.assets.background(self.world)
        self._background_variants = self._generate_background_variants(self.background)
        self.content = self.game.level_generator.generate(self.world, self.level)
        if self.content.goal is None:
            self.content.goal = Goal(700, 520, self.world, self.game.assets)
        self.game.play_music(f"world{self.world}.mp3")
        self.is_tower = self.level % 10 == 0
        spawn_point = self._compute_spawn_point()
        self.player.spawn = pygame.Vector2(spawn_point)
        self.player.respawn()
        self._apply_player_skills()
        self.tower_timer = 3.0 if self.is_tower else 0
        self.dynamic_glitch_active = False
        self.dynamic_glitch_end = 0.0
        self.dynamic_glitch_strength = 0.0
        self._update_bounds()
        self._snap_camera_to_player()
        # Update weather for new world
        self._set_world_weather()
        # Portal open SFX removed
        if self.world == 1 and self.level == 1 and not self.game.world1_intro_shown:
            play_first_entry_cutscene(self.game)
            self.game.world1_intro_shown = True

    def handle_event(self, event: pygame.event.Event) -> None:
        if hasattr(self, '_level_editor_enabled') and self._level_editor_enabled:
            # Editor mode: block all normal UI, handle only editor controls
            self.handle_level_editor_mouse(event)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f:
                    # Toggle flight
                    if hasattr(self.player, 'can_fly') and self.player.can_fly:
                        self.player.disable_flight()
                    else:
                        self.player.enable_flight()
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    # Save and exit edit mode
                    self.save_level() if hasattr(self, 'save_level') else None
                    self.disable_level_editing()
                # Block all other keys from normal game UI
            # Block all other UI events
            return
        # ...existing code...
        if event.type == pygame.QUIT:
            self.game.quit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                action = run_pause_menu(self)
                if action == "menu":
                    self.game.change_scene(TitleScene)
                elif action == "shops":
                    self.game._pause_return_scene = self
                    self.game.change_scene(ShopsHubScene, return_scene=self)
                elif action == "quit":
                    self.game.quit()

    def _update_bounds(self) -> None:
        padding_left = SCREEN_WIDTH * 0.25
        padding_right = SCREEN_WIDTH * 0.25
        self.left_bound = max(0, self.content.min_x - padding_left)
        self.right_bound = max(self.left_bound, self.content.max_x - SCREEN_WIDTH + padding_right)

        if self.is_tower:
            padding_top = SCREEN_HEIGHT * 0.3
            padding_bottom = SCREEN_HEIGHT * 0.1
            self.top_bound = min(self.content.min_y - padding_top, -SCREEN_HEIGHT)
            self.bottom_bound = max(self.content.max_y - SCREEN_HEIGHT + padding_bottom, 0)
            if self.top_bound > self.bottom_bound:
                self.top_bound = self.bottom_bound
        else:
            self.top_bound = 0
            self.bottom_bound = 0

    def _compute_spawn_point(self) -> Tuple[int, int]:
        platforms = list(self.content.platforms)
        if not platforms:
            return PLAYER_SPAWN

        thin = [spr for spr in platforms if spr.rect.height <= 24]
        candidates = thin if thin else platforms

        if self.is_tower:
            sprite = max(candidates, key=lambda spr: spr.rect.y)
        else:
            sprite = min(candidates, key=lambda spr: spr.rect.x)

        x = sprite.rect.centerx - PLAYER_WIDTH / 2
        y = sprite.rect.top - PLAYER_HEIGHT - 5
        return int(x), int(y)

    def _clamp_camera(self, value: float) -> float:
        if self.top_bound == self.bottom_bound:
            return self.bottom_bound
        return max(self.top_bound, min(self.bottom_bound, value))

    def _clamp_camera_x(self, value: float) -> float:
        if self.left_bound == self.right_bound:
            return self.left_bound
        return max(self.left_bound, min(self.right_bound, value))

    def _snap_camera_to_player(self) -> None:
        self.camera_x = self._clamp_camera_x(self.player.rect.centerx - SCREEN_WIDTH * 0.4)
        if self.is_tower:
            self.camera_y = self._clamp_camera(self.player.rect.centery - SCREEN_HEIGHT * 0.45)
        else:
            self.camera_y = 0

    def _update_camera(self) -> None:
        target_x = self._clamp_camera_x(self.player.rect.centerx - SCREEN_WIDTH * 0.4)
        self.camera_x += (target_x - self.camera_x) * 0.2
        if abs(target_x - self.camera_x) < 0.3:
            self.camera_x = target_x

        if self.is_tower:
            target_y = self._clamp_camera(self.player.rect.centery - SCREEN_HEIGHT * 0.45)
            self.camera_y += (target_y - self.camera_y) * 0.2
            if abs(target_y - self.camera_y) < 0.3:
                self.camera_y = target_y
        else:
            self.camera_y = 0

    def _update_dynamic_glitch(self) -> None:
        if self.dynamic_glitch_active and time.time() > self.dynamic_glitch_end:
            self.dynamic_glitch_active = False

        base_chance = 0.0
        if self.world <= 5:
            base_chance = 0.005 / max(1, self.world)
        elif 6 <= self.world <= 9:
            base_chance = 0.02 + (self.world - 6) * 0.01
        else:
            base_chance = 0.09

        if self.is_tower:
            base_chance += 0.01

        trigger_count = 0
        if self.world <= 5:
            trigger_count = 1 if not hasattr(self, "_world_glitch_count") else max(0, 1 - self._world_glitch_count)
        elif 6 <= self.world <= 9:
            trigger_count = 1
        else:
            trigger_count = 5

        if not hasattr(self, "_world_glitch_count"):
            self._world_glitch_count = 0

        # Ensure _world_glitch_seen is a dict. In some runs it may be accidentally
        # set to another type (for example a set) which would cause an
        # AttributeError when calling .get() or assigning by key. If the value
        # is an iterable of keys (set/list/tuple) convert it to a dict preserving
        # those keys with a default count of 1. Otherwise replace with a fresh
        # dict.
        if not hasattr(self, "_world_glitch_seen") or not isinstance(self._world_glitch_seen, dict):
            raw = getattr(self, "_world_glitch_seen", None)
            if isinstance(raw, (set, list, tuple)):
                try:
                    # preserve previously-seen worlds by giving them count 1
                    self._world_glitch_seen = {k: 1 for k in raw}
                except Exception:
                    self._world_glitch_seen = {}
            else:
                self._world_glitch_seen = {}

        key = (self.world, self.level)
        current_count = self._world_glitch_seen.get(key, 0)

        if current_count < trigger_count and not self.dynamic_glitch_active:
            chance = base_chance
            if random.random() < chance:
                self.dynamic_glitch_strength = min(1.5, 0.3 + self.world * 0.12)
                duration = 0.3 + min(1.0, 0.4 * self.dynamic_glitch_strength)
                self.dynamic_glitch_end = time.time() + duration
                self.dynamic_glitch_active = True
                self.game.sound.play_event("glitch")
                self._world_glitch_seen[key] = current_count + 1

    def _generate_background_variants(self, base: pygame.Surface) -> List[pygame.Surface]:
        variants: List[pygame.Surface] = []
        variants.append(base.copy())
        variants.append(pygame.transform.flip(base, True, False))
        variants.append(base.copy())
        variants.append(pygame.transform.flip(base, True, False))
        return variants

    def _draw_background(self, surface: pygame.Surface) -> None:
        if not getattr(self, "_background_variants", None):
            self._background_variants = self._generate_background_variants(self.background)
        bg_height = self.background.get_height()
        bg_width = self.background.get_width()
        tiles_needed = int(SCREEN_HEIGHT / bg_height) + 3
        base_y_index = int(self.camera_y // bg_height) - 1

        x_tiles = int(SCREEN_WIDTH / bg_width) + 3
        base_x_index = int(self.camera_x // bg_width) - 1

        for yi in range(base_y_index, base_y_index + tiles_needed):
            y = -self.camera_y + yi * bg_height
            for xi in range(base_x_index, base_x_index + x_tiles):
                x = -self.camera_x + xi * bg_width
                variant = self._background_variants[(xi + yi) & 1]
                surface.blit(variant, (x, y))

    def _draw_group(self, surface: pygame.Surface, group: pygame.sprite.Group) -> None:
        for sprite in group:
            surface.blit(sprite.image, sprite.rect.move(-self.camera_x, -self.camera_y))

    def _update_player_trail(self, dt: float) -> None:
        if not getattr(self, "trail_style", None):
            return
        speed = abs(self.player.velocity.x) + abs(self.player.velocity.y)
        if speed > 0.5:
            style = self.trail_style
            life = float(style.get("life", 0.45))
            size = int(style.get("size", 12))
            jitter = int(style.get("jitter", 4))
            count = int(style.get("count", 1))
            direction = pygame.Vector2(self.player.velocity)
            if direction.length() > 0.1:
                direction = direction.normalize()
            else:
                direction = pygame.Vector2(0, 1)
            for _ in range(max(1, count)):
                pos = pygame.Vector2(self.player.rect.center)
                if jitter:
                    pos.x += random.randint(-jitter, jitter)
                    pos.y += random.randint(-jitter, jitter)
                self._player_trail.append(
                    {
                        "pos": pos,
                        "life": life,
                        "max_life": life,
                        "size": size,
                        "angle": random.uniform(0, math.tau),
                        "dir": direction,
                    }
                )
        alive: List[Dict[str, Any]] = []
        for t in self._player_trail:
            t["life"] -= dt
            if t["life"] > 0:
                alive.append(t)
        self._player_trail = alive

    def _draw_player_trail(self, surface: pygame.Surface) -> None:
        if not getattr(self, "trail_style", None) or not getattr(self, "_player_trail", None):
            return
        style = self.trail_style
        base = style.get("color", self.trail_color)
        trail_name = style.get("name")
        for t in self._player_trail:
            life_ratio = max(0.0, t["life"] / max(0.01, t["max_life"]))
            alpha = int(200 * life_ratio)
            size = max(4, int(t["size"] * max(0.6, life_ratio)))
            if trail_name:
                tex_scale = float(style.get("tex_scale", 0.6))
                tex_size = max(14, int(size * tex_scale))
                tex = self.game.assets.trail_texture(trail_name, (tex_size, tex_size))
            else:
                tex = None
            x = int(t["pos"].x - self.camera_x)
            y = int(t["pos"].y - self.camera_y)
            if tex is not None:
                direction = t.get("dir") or pygame.Vector2(0, 1)
                for step in range(3):
                    step_alpha = max(0, int(alpha * (1.0 - step * 0.25)))
                    draw = tex.copy()
                    draw.set_alpha(step_alpha)
                    offset = direction * (-step * max(4, tex.get_width() * 0.6))
                    rect = draw.get_rect(center=(x + int(offset.x), y + int(offset.y)))
                    surface.blit(draw, rect)
            else:
                pygame.draw.circle(surface, (*base, alpha), (x, y), max(2, size // 3))

    def _draw_hat(self, surface: pygame.Surface, target_rect: pygame.Rect, offset: Tuple[int, int] = (0, 0)) -> None:
        hat_name = self.game.cosmetics.get("hat", "Default")
        color = self.game.active_hat_color()
        hat_width = int(target_rect.width * 0.9)
        hat_height = max(10, target_rect.height // 3)
        top = target_rect.top + offset[1] - hat_height + 6
        left = target_rect.left + offset[0] + (target_rect.width - hat_width) // 2
        if hat_width > 0 and hat_height > 0:
            hat_img = self.game.assets.hat_texture(hat_name, (hat_width, hat_height))
            if hat_img is not None:
                surface.blit(hat_img, (left, top))
                return
        if not color:
            return
        brim_height = max(4, hat_height // 5)
        brim_rect = pygame.Rect(left - 6, top + hat_height - brim_height, hat_width + 12, brim_height)
        crown_rect = pygame.Rect(left, top, hat_width, hat_height - brim_height)
        # Brim
        pygame.draw.rect(surface, (*color, 230), brim_rect, border_radius=4)
        # Crown with a subtle highlight band
        pygame.draw.rect(surface, (*color, 230), crown_rect, border_radius=6)
        band_height = max(3, brim_height - 1)
        band_rect = pygame.Rect(crown_rect.left, crown_rect.centery - band_height // 2, crown_rect.width, band_height)
        pygame.draw.rect(surface, (255, 255, 255, 180), band_rect, border_radius=3)
        # Slight top curve/rounded cap
        cap_rect = crown_rect.inflate(-crown_rect.width * 0.2, -brim_height * 1.2)
        pygame.draw.ellipse(surface, (*color, 200), cap_rect)

    def update(self, dt: float) -> None:
        self.content.platforms.update()
        self._carry_with_platforms()
        # Block player movement if dev_console is active
        if hasattr(self.game, "dev_console") and getattr(self.game.dev_console, "active", False):
            neutral_input = InputState()  # All controls False/neutral
            self.player.update(self.content.platforms, neutral_input)
        else:
            self.player.update(self.content.platforms, self.game.input_state)
        self._update_player_trail(dt)
        self.content.enemies.update()
        self.content.specials.update()
        self.content.coins.update()
        if self.content.goal:
            self.content.goal.update(dt)
        # Update weather effects
        self.weather.update(dt, (self.camera_x, self.camera_y))

        sound = self.game.sound

        if pygame.sprite.spritecollideany(self.player, self.content.enemies):
            sound.play_event("player_death")
            self.player.respawn()
            self._snap_camera_to_player()

        if any(self.player.rect.colliderect(spike.rect) for spike in self.content.spikes):
            sound.play_event("hazard_hit")
            self.player.respawn()
            self._snap_camera_to_player()

        specials_hit = pygame.sprite.spritecollide(self.player, self.content.specials, False)
        for special in specials_hit:
            effect = getattr(special, "effect", "collect")
            # Kill if effect is 'kill', or is deadly, or is a LavaBubble
            if effect == "kill" or getattr(special, "is_deadly", False) or isinstance(special, LavaBubble):
                sound.play_event("hazard_hit")
                self.player.respawn()
                self._snap_camera_to_player()
                break
            elif effect == "spring":
                if hasattr(special, "bounce"):
                    special.bounce(self.player)
                sound.play_event("jump")
            elif effect == "slow":
                self.player.apply_quicksand()

        if not hasattr(self, "coins_collected_count"):
            # Load from progress if available
            self.coins_collected_count = getattr(self.game.progress, "coins", 0)
        coins_collected = pygame.sprite.spritecollide(self.player, self.content.coins, dokill=True)
        if coins_collected:
            self.coins_collected_count += len(coins_collected)
            self.game.progress.coins = self.coins_collected_count
            self.game.progress.save(self.game.progress.world, self.game.progress.level, getattr(self.game, "player_color", None), coins=self.coins_collected_count, skills=self.game.skills, cosmetics=self.game.cosmetics)
            sound.play_event("coin_pickup")

        goal = self.content.goal
        if goal and self.player.rect.colliderect(goal.rect):
            sound.play_event("portal_enter")
            if goal.portal_type == "boss":
                self.game.change_scene(BossArenaScene, world=self.world, level=self.level)
                return
            self._advance_level()

        if self.is_tower and self.tower_timer > 0:
            self.tower_timer -= dt

        self._update_dynamic_glitch()
        self._update_camera()

    def _carry_with_platforms(self) -> None:
        for platform in self.content.platforms:
            if not hasattr(platform, "prev_rect"):
                continue
            move_x = platform.rect.x - platform.prev_rect.x
            move_y = platform.rect.y - platform.prev_rect.y
            if move_x == 0 and move_y == 0:
                continue
            if self.player.velocity.y >= 0 and self._sprite_on_platform(self.player, platform):
                self.player.rect.move_ip(move_x, move_y)
            for sprite in self.content.coins:
                if self._sprite_on_platform(sprite, platform):
                    sprite.rect.move_ip(move_x, move_y)
            for sprite in self.content.specials:
                if self._sprite_on_platform(sprite, platform):
                    sprite.rect.move_ip(move_x, move_y)
            if self.content.goal and self._sprite_on_platform(self.content.goal, platform):
                self.content.goal.rect.move_ip(move_x, move_y)

    @staticmethod
    def _sprite_on_platform(sprite: Optional[pygame.sprite.Sprite], platform: Platform, tolerance: int = 6) -> bool:
        if sprite is None or not hasattr(sprite, "rect"):
            return False
        sprite_rect = sprite.rect
        prev_top = platform.prev_rect.top
        if sprite_rect.bottom < prev_top - tolerance or sprite_rect.bottom > prev_top + tolerance:
            return False
        if sprite_rect.right <= platform.rect.left + 1 or sprite_rect.left >= platform.rect.right - 1:
            return False
        return True

    def _draw_tutorial_overlay(self, surface: pygame.Surface) -> None:
        font = self.game.assets.font(20, False)
        device = getattr(self.game, "last_input_device", "keyboard")
        hints = [
            "Move with A / D or Arrow Keys",
            "Press SPACE to jump",
            "Collect coins to guide your path",
            "Portals lead to the next challenge",
        ]
        for idx, text in enumerate(hints):
            y = 32 + idx * 28
            if "Press" in text or "Move with" in text or "Arrow" in text:
                draw_prompt_with_icons(surface, font, text, y + font.get_height() // 2, WHITE, device=device, x=32)
            else:
                render = font.render(text, True, WHITE)
                surface.blit(render, (32, y))

    def _advance_level(self) -> None:
        self.game.sound.play_event("level_complete")
        if self.world == 10 and self.level == 10:
            conclude_campaign(self.game)
            return

        previous_world = self.world
        self.level += 1
        if self.level > 10:
            self.world += 1
            self.level = 1
            if self.world > 10:
                self.world = 10
                self.level = 1
            else:
                play_world_transition(self.game, previous_world, self.world)
                if self.world == 10:
                    play_glitch_portal_cutscene(self.game)

        # Persist progress along with the player's selected color
        self.game.progress.save(self.world, self.level, getattr(self.game, "player_color", None), coins=self.game.progress.coins, skills=self.game.skills, cosmetics=self.game.cosmetics)
        self._refresh_world()

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        self._draw_group(surface, self.content.platforms)
        self._draw_group(surface, self.content.spikes)
        self._draw_group(surface, self.content.specials)
        self._draw_group(surface, self.content.enemies)
        self._draw_group(surface, self.content.coins)
        self.weather.draw(surface, (self.camera_x, self.camera_y))
        if self.content.goal:
            surface.blit(self.content.goal.image, self.content.goal.rect.move(-self.camera_x, -self.camera_y))
        self._draw_player_trail(surface)
        surface.blit(self.player.image, self.player.rect.move(-self.camera_x, -self.camera_y))
        self._draw_hat(surface, self.player.rect, offset=(-self.camera_x, -self.camera_y))

        # Draw only editor UI if in edit mode
        if hasattr(self, '_level_editor_enabled') and self._level_editor_enabled:
            self.draw_level_editor_toolbox(surface)
            self.draw_level_editor_controls(surface)
            return

        # ...existing UI overlays, coin counter, etc...
        font = self.game.assets.font(28, True)
        coin_text = f"Coins: {getattr(self, 'coins_collected_count', 0)}"
        render = font.render(coin_text, True, (255, 223, 70))
        shadow = font.render(coin_text, True, (60, 60, 60))
        x = surface.get_width() - render.get_width() - 24
        y = 16
        surface.blit(shadow, (x + 2, y + 2))
        surface.blit(render, (x, y))

        if self.tower_timer > 0 and 1 <= self.world <= len(TOWER_NAMES):
            draw_glitch_text(
                surface,
                self.game.assets.font(36, True),
                TOWER_NAMES[self.world - 1],
                80,
                WHITE,
                self.game.settings["glitch_fx"],
            )

        draw_center_text(
            surface,
            self.game.assets.font(24, True),
            f"World {self.world} - Level {self.level}",
            30,
            WHITE,
        )

        if self.world == 10 and self.game.settings["glitch_fx"]:
            if not self.glitch_active and random.random() < 0.01:
                self.glitch_active = True
                self.glitch_started = time.time()
            if self.glitch_active:
                self.glitch_active = apply_stacked_glitch(surface, self.glitch_started)
            if random.random() < 0.015:
                draw_glitch_text(
                    surface,
                    self.game.assets.font(28, True),
                    "REALITY CORRUPTED",
                    SCREEN_HEIGHT // 2,
                    RED,
                    True,
                )

        if self.dynamic_glitch_active and self.game.settings["glitch_fx"]:
            apply_dynamic_glitch(surface, self.dynamic_glitch_strength)

        if self.game.speedrun_active:
            timer_font = self.game.assets.font(22, True)
            timer_text = format_time(self.game.speedrun_time())
            timer_render = timer_font.render(timer_text, True, WHITE)
            shadow = timer_font.render(timer_text, True, (0, 0, 0))
            surface.blit(shadow, (18, 14))
            surface.blit(timer_render, (16, 12))


class VerdantGuardianBoss(pygame.sprite.Sprite):
    """Boss that uses a 4x4 spritesheet (idle, two attacks, death) with lightweight AI."""

    FRAME_SIZE = 128
    GRID_SIZE = 4
    ANIMATION_RANGES = {
        "idle": (0, 4),
        "attack1": (4, 8),
        "attack2": (8, 12),
        "death": (12, 16),
    }
    ANIMATION_SPEEDS = {
        "idle": 180,
        "attack1": 110,
        "attack2": 90,
        "death": 160,
    }

    def __init__(
        self,
        position: Tuple[int, int],
        world: int = 1,
        *,
        assets: Optional[AssetCache] = None,
        max_hp: int = 120,
        attack_damage: Tuple[int, int] = (10, 16),
    ):
        super().__init__()
        self.world = world
        self.max_hp = max_hp
        self.hp = max_hp
        self.attack_damage: Dict[str, int] = {"attack1": attack_damage[0], "attack2": attack_damage[1]}
        self.attack_cooldowns: Dict[str, int] = {"attack1": 2200, "attack2": 3200}  # milliseconds
        self.last_attack_times: Dict[str, int] = {"attack1": 0, "attack2": 0}
        self.attack_durations: Dict[str, int] = {"attack1": 900, "attack2": 1200}
        self.attack_windups: Dict[str, int] = {"attack1": 350, "attack2": 650}
        self.idle_duration_range: Tuple[int, int] = (1400, 2400)
        self.state = "idle"
        self.state_start_time = pygame.time.get_ticks()
        self.next_action_time = self.state_start_time + random.randint(*self.idle_duration_range)
        self._attack_action_fired = False
        self._hover_phase = random.random() * math.tau
        self._hover_radius = 12
        self._hover_speed = 1.4  # radians per second

        if assets is not None:
            self.animations = assets.boss_animation_frames(world)
        else:
            spritesheet = self._load_spritesheet(world)
            self.animations = self._slice_spritesheet(spritesheet)
        self.image = self.animations[self.state][0]
        self.rect = self.image.get_rect(center=position)
        self.pos = pygame.Vector2(position)
        self.origin = pygame.Vector2(position)
        self.current_frame_index = 0
        self.last_frame_time = pygame.time.get_ticks()

        self.projectiles: List[Dict[str, Any]] = []
        self.projectile_speed = 320.0  # pixels per second
        self.projectile_lifetime = 2.5  # seconds
        self.projectile_surface = self._build_projectile_surface()

    def _load_spritesheet(self, world: int) -> pygame.Surface:
        sheet_path = ASSET_DIR / "bosses" / f"boss_world{world}.png"
        if not sheet_path.exists():
            print(f"[Boss] Missing spritesheet at {sheet_path}. Using placeholder.")
            placeholder = pygame.Surface(
                (self.FRAME_SIZE * self.GRID_SIZE, self.FRAME_SIZE * self.GRID_SIZE),
                pygame.SRCALPHA,
            )
            placeholder.fill((20, 90, 40))
            pygame.draw.rect(placeholder, (0, 0, 0), placeholder.get_rect(), 4)
            return placeholder
        return pygame.image.load(str(sheet_path)).convert_alpha()

    def _slice_spritesheet(self, sheet: pygame.Surface) -> Dict[str, List[pygame.Surface]]:
        frames: List[pygame.Surface] = []
        for row in range(self.GRID_SIZE):
            for col in range(self.GRID_SIZE):
                rect = pygame.Rect(
                    col * self.FRAME_SIZE,
                    row * self.FRAME_SIZE,
                    self.FRAME_SIZE,
                    self.FRAME_SIZE,
                )
                frames.append(sheet.subsurface(rect).copy())

        animations: Dict[str, List[pygame.Surface]] = {}
        for state, (start, end) in self.ANIMATION_RANGES.items():
            animations[state] = frames[start:end]
        return animations

    def _build_projectile_surface(self) -> pygame.Surface:
        surface = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(surface, (60, 200, 120, 240), (9, 9), 8)
        pygame.draw.circle(surface, (255, 255, 255, 220), (9, 9), 3)
        return surface

    def take_damage(self, amount: int) -> None:
        if self.state == "death":
            return
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            self._enter_state("death")

    def shoot_projectile(self, target_pos: Optional[Tuple[int, int]]) -> None:
        # Placeholder projectile logic; projectiles are dictionaries so callers can hook into them easily.
        if target_pos is None:
            direction = pygame.Vector2(random.choice([-1, 1]), random.uniform(-0.3, 0.3))
        else:
            direction = pygame.Vector2(target_pos) - self.pos
            if direction.length_squared() == 0:
                direction = pygame.Vector2(1, 0)
        direction = direction.normalize()
        projectile = {
            "pos": pygame.Vector2(self.rect.center),
            "velocity": direction * self.projectile_speed,
            "damage": self.attack_damage.get(self.state, 0),
            "life": self.projectile_lifetime,
        }
        self.projectiles.append(projectile)

    def _enter_state(self, state: str) -> None:
        self.state = state
        self.state_start_time = pygame.time.get_ticks()
        self.current_frame_index = 0
        self.last_frame_time = self.state_start_time
        self.image = self.animations[state][0]
        self._attack_action_fired = False
        if state == "idle":
            self.next_action_time = self.state_start_time + random.randint(*self.idle_duration_range)
        elif state == "death":
            self.projectiles.clear()

    def _select_attack(self, now: int) -> Optional[str]:
        choices = [
            name
            for name in ("attack1", "attack2")
            if now - self.last_attack_times[name] >= self.attack_cooldowns[name]
        ]
        if not choices:
            self.next_action_time = now + 240
            return None
        choice = random.choice(choices)
        self.last_attack_times[choice] = now
        return choice

    def _advance_animation(self, now: int) -> None:
        frames = self.animations[self.state]
        speed = self.ANIMATION_SPEEDS.get(self.state, 150)
        if now - self.last_frame_time < speed:
            return
        self.last_frame_time = now
        if self.state == "death" and self.current_frame_index >= len(frames) - 1:
            self.image = frames[-1]
            return
        self.current_frame_index = (self.current_frame_index + 1) % len(frames)
        self.image = frames[self.current_frame_index]

    def _update_projectiles(self, dt: float) -> None:
        alive: List[Dict[str, Any]] = []
        for projectile in self.projectiles:
            projectile["life"] -= dt
            projectile["pos"] += projectile["velocity"] * dt
            if projectile["life"] > 0:
                alive.append(projectile)
        self.projectiles = alive

    def _update_ai(self, now: int, player_pos: Optional[Tuple[int, int]]) -> None:
        if self.state == "death":
            return

        if self.state == "idle":
            if now >= self.next_action_time:
                attack = self._select_attack(now)
                if attack:
                    self._enter_state(attack)
            return

        # Attack logic
        windup = self.attack_windups.get(self.state, 0)
        if not self._attack_action_fired and now - self.state_start_time >= windup:
            self.shoot_projectile(player_pos)
            self._attack_action_fired = True

        duration = self.attack_durations.get(self.state, 600)
        if now - self.state_start_time >= duration:
            self._enter_state("idle")

    def _update_hover(self, dt: float) -> None:
        self._hover_phase = (self._hover_phase + self._hover_speed * dt) % math.tau
        offset = math.sin(self._hover_phase) * self._hover_radius
        self.pos.x = self.origin.x
        self.pos.y = self.origin.y + offset
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def update(self, dt: float, player_pos: Optional[Tuple[int, int]] = None) -> None:
        """Advance animation, AI, and placeholder projectile motion."""
        self._update_hover(dt)
        now = pygame.time.get_ticks()
        if self.hp <= 0 and self.state != "death":
            self._enter_state("death")
        self._update_ai(now, player_pos)
        self._advance_animation(now)
        self._update_projectiles(dt)

    def draw(self, surface: pygame.Surface, camera_offset: Tuple[int, int] = (0, 0)) -> None:
        draw_pos = self.rect.move(-camera_offset[0], -camera_offset[1])
        surface.blit(self.image, draw_pos)
        for projectile in self.projectiles:
            proj_pos = projectile["pos"] - pygame.Vector2(camera_offset)
            surface.blit(
                self.projectile_surface,
                self.projectile_surface.get_rect(center=(int(proj_pos.x), int(proj_pos.y))),
            )


class BossArenaScene(Scene):
    def __init__(self, game: "Game", world: int, level: int):
        super().__init__(game)
        self.world = world
        self.level = level
        self.background = self.game.assets.background(world)
        self.platforms = pygame.sprite.Group()
        ground = Platform(0, 520, SCREEN_WIDTH, 40, world, self.game.assets)
        self.platforms.add(ground)
        spawn = (ground.rect.centerx - PLAYER_WIDTH // 2, ground.rect.top - PLAYER_HEIGHT)
        settings_mgr = SettingsManager(SETTINGS_FILE)
        character_name = settings_mgr.data.get("character", "player")
        outfit_form = self.game.active_outfit_form()
        player_color = self.game.active_outfit_color()
        if outfit_form:
            player_color = None
        self.player = Player(
            spawn,
            self.game.sound,
            color=player_color,
            character_name=character_name,
            form_name=outfit_form,
        )
        self.player.spawn = pygame.Vector2(spawn)
        self.player.respawn()
        self.player.skills = getattr(self.game, "skills", {})
        # Apply extra health skill
        extra_hp_levels = int(self.game.skills.get("extra_health_levels", 0))
        base_hp = getattr(self.player, "base_max_health", self.player.max_health)
        self.player.max_health = base_hp + extra_hp_levels
        self.player.health = self.player.max_health
        self.player.can_fly = False
        self.player_projectiles = pygame.sprite.Group()
        self.boss_projectiles = pygame.sprite.Group()
        boss_y = ground.rect.top
        self.boss = Boss(ground.rect.centerx, boss_y, world, self.game.assets)
        self.boss_origin = pygame.Vector2(self.boss.rect.midbottom)
        self.shoot_cooldown = 0.0
        self.shield_active = False
        self.shield_timer = 0.0
        self.shield_cooldown = 0.0
        self.shield_duration = 10.0
        self.shield_recharge = 15.0
        self.beam_cooldown = 0.0
        self.shoot_hold = 0.0
        self.shoot_charging = False
        self._shoot_prev = False
        self.trail_style = self.game.active_trail_style()
        self.trail_color = self.trail_style["color"] if self.trail_style else None
        self._player_trail: List[Dict[str, Any]] = []
        self.state = "intro"
        self.explosion_timer = 0.0
        self.explosion_duration = 1.5
        self.explosion_pos: Optional[Tuple[int, int]] = None
        self.explosion_particles: List[Dict[str, Any]] = []
        self.exit_portal: Optional[Goal] = None
        self.exit_portal_base: Optional[pygame.Surface] = None
        self.portal_spawn_time: Optional[float] = None
        self.portal_spawn_duration: float = 0.6
        self.message_timer = 2.0
        self.is_final_boss = self.world == 10 and self.level == 10
        self.final_portal_ready = False
        self.spawn_theme = BOSS_SPAWN_THEMES.get(self.world, DEFAULT_SPAWN_THEME)
        self.spawn_beams: List[Dict[str, Any]] = []
        self.intro_timer = 0.0
        self.intro_duration = 0.0
        self.boss_spawn_alpha = 0.0
        self.spawn_fade_start = 0.0
        self.pending_roar = True
        self._init_spawn_animation()

        # Stop current music and play this world's music
        self._previous_music = getattr(self.game, "_last_music", None)
        self.game.stop_music()
        self.game.play_music(f"world{self.world}.mp3")
    def on_exit(self) -> None:
        # Restore world music after boss fight ends
        if hasattr(self, "world"):
            self.game.stop_music()
            self.game.play_music(f"world{self.world}.mp3")
        else:
            # fallback: play last music if available
            if getattr(self, "_previous_music", None):
                self.game.stop_music()
                self.game.play_music(str(self._previous_music))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                action = run_pause_menu(self)
                if action == "menu":
                    self.game.change_scene(TitleScene)
                elif action == "shops":
                    self.game._pause_return_scene = self
                    self.game.change_scene(ShopsHubScene, return_scene=self)
                elif action == "quit":
                    self.game.quit()
            elif event.key == self.game.settings["key_map"].get("shield", pygame.K_LSHIFT) and self.state in ("fight", "exit"):
                self._activate_shield()
        elif event.type == pygame.JOYBUTTONDOWN and self.state in ("fight", "exit"):
            shoot_btn = self.game.settings["controller_map"].get("shoot", 2)
            shield_btn = self.game.settings["controller_map"].get("shield", 3)
            if event.button == shield_btn:
                self._activate_shield()

    def update(self, dt: float) -> None:
        self.shoot_cooldown = max(0.0, self.shoot_cooldown - dt)
        # Shield timers and mutual exclusion with shooting
        if self.shield_active:
            self.shield_timer = max(0.0, self.shield_timer - dt)
            if self.shield_timer <= 0:
                self.shield_active = False
                self.shield_cooldown = self.shield_recharge
        else:
            self.shield_cooldown = max(0.0, self.shield_cooldown - dt)

        # Shooting logic: charge while held, fire on release (tap = normal shot, hold = big blast)
        if self.state == "fight":
            shooting = self.game.input_state.shoot
            if shooting and not self._shoot_prev:
                # start charge
                if self.beam_cooldown <= 0:
                    self.shoot_charging = True
                    self.shoot_hold = 0.0
                else:
                    # Normal shots while beam is on cooldown
                    if self.shoot_cooldown <= 0:
                        self._fire_projectile()
            if shooting and self.shoot_charging:
                self.shoot_hold += dt
                # Auto-fire kamehameha once fully charged (no release needed)
                max_charge = 5.0
                if self.shoot_hold >= max_charge and self.shoot_cooldown <= 0:
                    self._fire_kamehameha()
                    self.shoot_charging = False
                    self.shoot_hold = 0.0
            # Disable shield input while charging up the beam
            if self.shoot_charging:
                self.shield_active = False
            if (not shooting) and self._shoot_prev and self.shoot_charging:
                if self.shoot_cooldown <= 0:
                    charge_threshold = 0.7
                    if self.game.skills.get("rapid_charge"):
                        charge_threshold = 0.45
                    if self.shoot_hold >= charge_threshold:
                        self._fire_charge_blast()
                    else:
                        self._fire_projectile()
                self.shoot_charging = False
                self.shoot_hold = 0.0
            self._shoot_prev = shooting

        if self.message_timer > 0:
            self.message_timer -= dt

        self.platforms.update()
        self.player.update(self.platforms, self.game.input_state)
        self._update_player_trail(dt)
        self.player_projectiles.update()
        self.boss_projectiles.update()
        self._update_explosion_effects(dt)
        if self.exit_portal and self.portal_spawn_time is None:
            self.exit_portal.update(dt)
        if self.beam_cooldown > 0:
            self.beam_cooldown = max(0.0, self.beam_cooldown - dt)

        if self.state == "intro":
            self._update_spawn_animation(dt)

        if self.state == "fight":
            self.boss.update()
            self.boss.perform_attacks(self.player, self.boss_projectiles)
            hits = pygame.sprite.spritecollide(self.boss, self.player_projectiles, dokill=True)
            if hits:
                self.game.sound.play_event("boss_hit")
                # Sum projectile damage (defaults to 1) and apply blast bonuses
                damage = sum(getattr(h, "damage", 1) for h in hits)
                if damage <= 0:
                    damage = 0
                if self.game.skills.get("blast_radius"):
                    for h in hits:
                        if getattr(h, "is_charged", False):
                            damage += 2
                            self._charged_blast_effect(pygame.Vector2(h.rect.center))
                self.boss.take_damage(damage)
                # Apply stagger if skill unlocked and stagger not active
                if self.game.skills.get("stagger") and getattr(self.boss, "stagger_timer", 0) <= 0:
                    self.boss.stagger_timer = 1.5
                    self.boss.short_cooldown *= 1.25
                    self.boss.long_cooldown *= 1.25
                if self.boss.defeated():
                    self._handle_boss_defeated()

        if self.state == "fight" and self.boss.health > 0 and self.player.rect.colliderect(self.boss.rect):
            self.player.take_damage(1)
            self._bump_player_from_boss()

        if self.state == "fight" and pygame.sprite.spritecollide(self.player, self.boss_projectiles, dokill=True):
            self.game.sound.play_event("projectile_hit")
            self.player.take_damage(1)
        # Shield blocks boss projectiles while active
        if self.shield_active:
            shield_rect = self.player.rect.inflate(30, 30)
            for proj in list(self.boss_projectiles):
                if proj.rect.colliderect(shield_rect):
                    if self.game.skills.get("reflective_shield"):
                        # Bounce back toward boss and convert to player projectile so it can deal damage
                        vel = pygame.Vector2(getattr(proj, "velocity", pygame.Vector2(-6, 0)))
                        if vel.length_squared() == 0:
                            vel = pygame.Vector2(-6, 0)
                        vel.x = -vel.x
                        vel.y = max(-2.0, -abs(vel.y))  # send slightly upward
                        proj.velocity = vel
                        proj.rect.move_ip(int(proj.velocity.x), int(proj.velocity.y))
                        proj.bounced = True
                        proj.damage = getattr(proj, "damage", 1)
                        if proj in self.boss_projectiles:
                            self.boss_projectiles.remove(proj)
                        self.player_projectiles.add(proj)
                    else:
                        proj.kill()

        if not self.player.alive():
            # On death, restore shield immediately
            self.shield_active = False
            self.shield_timer = 0.0
            self.shield_cooldown = 0.0
            self.beam_cooldown = 0.0
            self._handle_player_defeat()

        if self.state == "explosion":
            self.explosion_timer -= dt
            if self.explosion_timer <= 0:
                self._after_explosion()

        if self.exit_portal and self.player.rect.colliderect(self.exit_portal.rect):
            # If final boss, play portal entry transition, then portal collapse cutscene
            if self.is_final_boss:
                portal_center = self.exit_portal.rect.center
                # Play player jump-in-portal transition
                self.game.stop_music()
                self._play_portal_entry_transition(portal_center)
                # Gather all objects and backgrounds to suck in
                objects = list(self.platforms) + [self.player, self.boss] + list(self.player_projectiles) + list(self.boss_projectiles)
                backgrounds = [self.background] if hasattr(self, 'background') else []
                play_portal_collapse_cutscene(self.game, portal_center, objects, backgrounds)
                self.game.change_scene(CreditsScene, ending_mode=True)
            else:
                self._complete_stage()

    def _play_portal_entry_transition(self, portal_center):
        """Animate the player jumping into the portal before the final cutscene (longer version)."""
        player = self.player
        screen = self.game.screen
        clock = pygame.time.Clock()
        frames = 54  # was 30, now 54 for longer transition (~0.9s at 60fps)
        start_pos = player.rect.center
        end_pos = portal_center
        for i in range(frames):
            t = i / (frames - 1)
            # Ease in
            interp = t * t * (3 - 2 * t)
            cx = int(start_pos[0] + (end_pos[0] - start_pos[0]) * interp)
            cy = int(start_pos[1] + (end_pos[1] - start_pos[1]) * interp)
            # Draw scene
            screen.blit(self.background, (0, 0))
            for platform in self.platforms:
                screen.blit(platform.image, platform.rect)
            # Draw portal
            portal_img = self.game.assets.portal_texture(10)
            portal_rect = portal_img.get_rect(center=portal_center)
            screen.blit(portal_img, portal_rect)
            # Draw player jumping in
            player_img = player.image
            scale = 1.0 - 0.5 * t  # shrink as entering
            player_img_scaled = pygame.transform.smoothscale(player_img, (int(player.rect.width * scale), int(player.rect.height * scale)))
            player_rect = player_img_scaled.get_rect(center=(cx, cy))
            screen.blit(player_img_scaled, player_rect)
            pygame.display.flip()
            clock.tick(60)
        # Fade to white more slowly
        fade_frames = 24  # was 12, now 24 for slower fade (~0.4s)
        for i in range(fade_frames):
            alpha = int(255 * (i / (fade_frames - 1)))
            fade = pygame.Surface(screen.get_size())
            fade.fill((255, 255, 255))
            fade.set_alpha(alpha)
            screen.blit(fade, (0, 0))
            pygame.display.flip()
            clock.tick(60)

    def _charged_blast_effect(self, center: pygame.Vector2) -> None:
        """Small AoE clear when a charged shot lands (Blast Radius skill)."""
        radius = 120.0
        cleared = 0
        for proj in list(self.boss_projectiles):
            if pygame.Vector2(proj.rect.center).distance_to(center) <= radius:
                proj.kill()
                cleared += 1
        # Add a handful of transient particles for feedback
        for _ in range(10):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(5.0, 10.0)
            vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed * 0.8
            particle = {
                "pos": pygame.Vector2(center),
                "vel": vel,
                "life": random.uniform(0.3, 0.6),
                "size": random.randint(2, 4),
                "color": (200, 240, 255),
            }
            self.explosion_particles.append(particle)
        if cleared > 0:
            try:
                self.game.sound.play_event("menu_move")
            except Exception:
                pass

    def _activate_shield(self) -> None:
        """Turn on the temporary shield if off cooldown."""
        if self.shield_cooldown > 0 or self.shield_active or self.state not in ("fight", "exit"):
            return
        self.shield_active = True
        self.shield_timer = self.shield_duration
        # Optional SFX hook
        try:
            self.game.sound.play_event("menu_confirm")
        except Exception:
            pass
        if self.game.skills.get("shield_pulse"):
            self._trigger_shield_pulse()

    def _trigger_shield_pulse(self) -> None:
        """Clear nearby boss projectiles and briefly slow the boss when the shield comes up."""
        center = pygame.Vector2(self.player.rect.center)
        radius = 140.0
        cleared = 0
        for proj in list(self.boss_projectiles):
            if pygame.Vector2(proj.rect.center).distance_to(center) <= radius:
                proj.kill()
                cleared += 1
        if getattr(self.boss, "stagger_timer", 0) < 0.5:
            self.boss.stagger_timer = 0.5
        if cleared > 0:
            try:
                self.game.sound.play_event("menu_move")
            except Exception:
                pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.background, (0, 0))
        for platform in self.platforms:
            surface.blit(platform.image, platform.rect)

        self._draw_spawn_effects(surface)

        if self.exit_portal:
            self._draw_exit_portal(surface)

        for projectile in self.boss_projectiles:
            surface.blit(projectile.image, projectile.rect)
        for projectile in self.player_projectiles:
            surface.blit(projectile.image, projectile.rect)

        self._draw_boss(surface)

        self._draw_player_trail(surface)
        surface.blit(self.player.image, self.player.rect)
        self._draw_hat(surface, self.player.rect, offset=(0, 0))
        if self.shoot_charging and self.state == "fight" and self.beam_cooldown <= 0:
            self._draw_charge_orb(surface)
        if self.shield_active:
            # Force-field shield tinted to the player's color
            tint = getattr(self.game, "player_color", (120, 200, 255))
            base_color = (int(tint[0]), int(tint[1]), int(tint[2]))
            alpha_main = 140
            alpha_glow = 70
            shield_rect = self.player.rect.inflate(36, 36)
            # Main ring
            ring = pygame.Surface(shield_rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(ring, (*base_color, alpha_main), ring.get_rect(), width=4)
            # Inner glow
            glow = pygame.Surface(shield_rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*base_color, alpha_glow), glow.get_rect().inflate(-6, -6))
            ring.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)
            surface.blit(ring, shield_rect)
            if self.game.skills.get("shield_pulse"):
                pulse = pygame.Surface(shield_rect.size, pygame.SRCALPHA)
                pygame.draw.ellipse(pulse, (*base_color, 40), pulse.get_rect().inflate(14, 14), width=6)
                surface.blit(pulse, shield_rect.move(-7, -7))
        self._draw_health_bars(surface)
        self._draw_explosion(surface)
        self._draw_particles(surface)
        # Persistent input hint that adapts to last input device
        device = getattr(self.game, "last_input_device", "keyboard")
        if device == "controller":
            if self.shield_cooldown > 0:
                prompt_text = f"Press X to fire  |  Shield Cooldown: {self.shield_cooldown:0.1f}s"
            else:
                prompt_text = "Press X to fire  |  Press Y to shield"
            cooldown_text = f"Shield CD: {self.shield_cooldown:0.1f}s"
        else:
            if self.shield_cooldown > 0:
                prompt_text = f"Press F to fire  |  Shield Cooldown: {self.shield_cooldown:0.1f}s"
            else:
                prompt_text = "Press F to fire  |  Press Shift to shield"
        prompt_font = self.game.assets.font(20, True)
        draw_prompt_with_icons(
            surface,
            prompt_font,
            prompt_text,
            SCREEN_HEIGHT - 60,
            WHITE,
            device=device,
        )
        # Draw beam cooldown just below prompts
        cd_font = self.game.assets.font(18, False)
        beam_cd_text = f"Beam Cooldown: {self.beam_cooldown:0.1f}s" if self.beam_cooldown > 0 else "Beam Ready"
        beam_color = (120, 255, 160) if self.beam_cooldown <= 0 else (255, 0, 0)
        beam_render = cd_font.render(beam_cd_text, True, beam_color)
        surface.blit(beam_render, beam_render.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 36)))

    def _draw_exit_portal(self, surface: pygame.Surface) -> None:
        if not self.exit_portal or not self.exit_portal_base:
            return
        if self.portal_spawn_time is None:
            surface.blit(self.exit_portal.image, self.exit_portal.rect)
            return

        elapsed = time.time() - self.portal_spawn_time
        if elapsed >= self.portal_spawn_duration:
            self.portal_spawn_time = None
            surface.blit(self.exit_portal.image, self.exit_portal.rect)
            return

        t = max(0.0, min(1.0, elapsed / self.portal_spawn_duration))
        eased = t * t * (3 - 2 * t)  # smoothstep easing
        base = self.exit_portal_base
        width, height = base.get_size()
        scaled_w = max(4, int(width * eased))
        scaled_h = max(4, int(height * eased))
        scaled = pygame.transform.smoothscale(base, (scaled_w, scaled_h))
        draw_rect = scaled.get_rect(center=self.exit_portal.rect.center)
        surface.blit(scaled, draw_rect)

    def _draw_charge_orb(self, surface: pygame.Surface) -> None:
        """Expanding orb effect while charging; no beam shown until fire."""
        ratio = min(1.0, (self.shoot_hold or 0.0) / 5.0)
        if ratio <= 0:
            return
        center = self.player.rect.center
        max_radius = 90
        radius = int(24 + (max_radius - 24) * ratio)
        orb = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        # outer glow
        pygame.draw.circle(orb, (60, 160, 255, 80), (radius, radius), radius)
        # mid glow
        pygame.draw.circle(orb, (120, 200, 255, 120), (radius, radius), int(radius * 0.72))
        # core
        pygame.draw.circle(orb, (200, 240, 255, 180), (radius, radius), int(radius * 0.45))
        surface.blit(orb, orb.get_rect(center=center))

    def _fire_projectile(self) -> None:
        if self.state != "fight" or self.shoot_cooldown > 0:
            return
        spawn_x = self.player.rect.right if self.player.facing_right else self.player.rect.left
        spawn_y = self.player.rect.centery - 10
        projectile = PlayerProjectile(spawn_x, spawn_y, self.player.facing_right)
        projectile.damage = 0.5
        self.player_projectiles.add(projectile)
        self.shoot_cooldown = 0.20
        self.game.sound.play_event("projectile_fire")

    def _fire_charge_blast(self) -> None:
        """Fire a heavy blast after holding shoot; higher damage, slower speed."""
        if self.state != "fight":
            return
        spawn_x = self.player.rect.right if self.player.facing_right else self.player.rect.left
        spawn_y = self.player.rect.centery - 10
        projectile = PlayerProjectile(spawn_x, spawn_y, self.player.facing_right)
        # Scale up the projectile
        projectile.image = pygame.transform.smoothscale(projectile.image, (32, 16))
        projectile.rect = projectile.image.get_rect(center=projectile.rect.center)
        projectile.damage = 4
        projectile.is_charged = True
        projectile.velocity_x = 14 if self.player.facing_right else -14
        self.player_projectiles.add(projectile)
        # Longer cooldown after a charged shot
        self.shoot_cooldown = 0.5
        try:
            self.game.sound.play_event("menu_confirm")
        except Exception:
            pass

    def _fire_kamehameha(self) -> None:
        """Massive beam after a 5s charge; very high damage and speed."""
        if self.state != "fight" or self.shoot_cooldown > 0:
            return
        spawn_x = self.player.rect.right if self.player.facing_right else self.player.rect.left
        spawn_y = self.player.rect.centery - 10
        # Create a large rounded beam
        width, height = 220, 72
        beam = pygame.sprite.Sprite()
        beam.image = pygame.Surface((width, height), pygame.SRCALPHA)
        # Layered ellipses for glow + core
        for i, alpha in enumerate((90, 130, 180, 255)):
            shrink = i * 10
            color = (80 + i * 40, 180 + i * 15, 255)
            pygame.draw.ellipse(beam.image, (*color, alpha), beam.image.get_rect().inflate(-shrink, -shrink // 2))
        beam.rect = beam.image.get_rect(center=(spawn_x, spawn_y))
        speed = 34
        beam.velocity_x = speed if self.player.facing_right else -speed
        beam.damage = 24
        beam.is_charged = True

        def update(self_proj: pygame.sprite.Sprite) -> None:
            self_proj.rect.x += int(self_proj.velocity_x)
            if self_proj.rect.right < -50 or self_proj.rect.left > SCREEN_WIDTH + 50:
                self_proj.kill()

        beam.update = update.__get__(beam, pygame.sprite.Sprite)
        self.player_projectiles.add(beam)
        # Longer cooldown after beam
        self.shoot_cooldown = 1.5
        self.beam_cooldown = 60.0
        try:
            self.game.sound.play_event("boss_defeat")
        except Exception:
            pass

    def _bump_player_from_boss(self) -> None:
        if self.player.rect.centerx < self.boss.rect.centerx:
            self.player.rect.right = self.boss.rect.left - 10
            self.player.velocity.x = -6
        else:
            self.player.rect.left = self.boss.rect.right + 10
            self.player.velocity.x = 6
        self.player.velocity.y = -8
        self.player.on_ground = False
        # Shield pulse knockback if active
        if self.shield_active and self.game.skills.get("shield_pulse"):
            self.player.velocity.y = -10

    def _handle_player_defeat(self) -> None:
        self.player.respawn()
        self.player_projectiles.empty()
        self.boss_projectiles.empty()
        self.shoot_cooldown = 0.0
        self.boss.health = self.boss.max_health
        self.boss.reset_anchor(self.boss_origin)
        self.boss.short_cooldown = 1.0
        self.boss.long_cooldown = 1.5
        self.state = "fight"
        self.explosion_timer = 0.0
        self.explosion_pos = None
        self.explosion_particles.clear()
        self.exit_portal = None
        self.spawn_beams.clear()
        self.boss_spawn_alpha = 1.0
        self.pending_roar = False

    def _handle_boss_defeated(self) -> None:
        self.state = "explosion"
        self.explosion_duration = 1.8
        self.explosion_timer = self.explosion_duration
        self.explosion_pos = self.boss.rect.center
        self.explosion_particles = []
        for _ in range(150):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(160, 320)
            vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * (speed * 0.016)
            life = random.uniform(0.6, 1.4)
            size = random.randint(3, 7)
            color = random.choice(
                [
                    (255, 240, 180),
                    (255, 200, 140),
                    (255, 150, 100),
                    (255, 255, 255),
                ]
            )
            self.explosion_particles.append(
                {"pos": pygame.Vector2(self.explosion_pos), "vel": vel, "life": life, "size": size, "color": color}
            )
        self.boss.health = 0
        self.boss_projectiles.empty()
        self.game.sound.play_event("boss_defeat")
        self.spawn_beams.clear()

    def _after_explosion(self) -> None:
        ground = next(iter(self.platforms), None)
        if ground is None:
            return

        if self.is_final_boss:
            portal_world = self.world
            self.final_portal_ready = True
        else:
            portal_world = min(10, self.world + 1)
            self.final_portal_ready = False

        self.exit_portal = Goal(ground.rect.centerx, ground.rect.top, portal_world, self.game.assets)
        self.exit_portal_base = self.exit_portal.base_image.copy()
        self.portal_spawn_time = time.time()
        self.state = "exit"
        self.explosion_pos = None
        self.explosion_particles.clear()
        self.game.sound.play_event("portal_unlock")

    def _complete_stage(self) -> None:
        self.game.sound.play_event("level_complete")
        if self.is_final_boss and self.final_portal_ready:
            conclude_campaign(self.game)
            return

        previous_world = self.world
        next_world = min(10, self.world + 1)
        play_world_transition(self.game, previous_world, next_world)
        if next_world == 10:
            play_glitch_portal_cutscene(self.game)
        # Save next world progress and current player color
        self.game.progress.save(next_world, 1, getattr(self.game, "player_color", None), coins=self.game.progress.coins, skills=self.game.skills, cosmetics=self.game.cosmetics)
        self.game.change_scene(GameplayScene, world=next_world, level=1)

    def _draw_health_bars(self, surface: pygame.Surface) -> None:
        # Player health
        base_bar_width = 200
        extra_hp_levels = int(self.game.skills.get("extra_health_levels", 0))
        bar_width = base_bar_width + max(0, extra_hp_levels) * 4  # widen bar as max health increases
        bar_height = 18
        x = 30
        y = 24
        pygame.draw.rect(surface, (40, 40, 60), pygame.Rect(x - 4, y - 4, bar_width + 8, bar_height + 8), border_radius=8)
        pygame.draw.rect(surface, (120, 120, 140), pygame.Rect(x, y, bar_width, bar_height), border_radius=6)
        if self.player.max_health > 0:
            fill = int(bar_width * (self.player.health / self.player.max_health))
            pygame.draw.rect(surface, (80, 220, 120), pygame.Rect(x, y, fill, bar_height), border_radius=6)
        label = self.game.assets.font(20, True).render("Player", True, WHITE)
        surface.blit(label, (x, y - 24))

        # Boss health
        boss_bar_width = SCREEN_WIDTH - 120
        boss_bar_height = 20
        bx = 60
        by = 60
        pygame.draw.rect(surface, (60, 30, 30), pygame.Rect(bx - 4, by - 4, boss_bar_width + 8, boss_bar_height + 8), border_radius=10)
        pygame.draw.rect(surface, (120, 50, 50), pygame.Rect(bx, by, boss_bar_width, boss_bar_height), border_radius=8)
        if self.boss.max_health > 0:
            boss_fill = int(boss_bar_width * max(0, self.boss.health) / self.boss.max_health)
            pygame.draw.rect(surface, (255, 100, 80), pygame.Rect(bx, by, boss_fill, boss_bar_height), border_radius=8)
        boss_label = self.game.assets.font(22, True).render(self.boss.name.upper(), True, WHITE)
        surface.blit(boss_label, (SCREEN_WIDTH // 2 - boss_label.get_width() // 2, by - 28))

    def _draw_explosion(self, surface: pygame.Surface) -> None:
        if self.explosion_pos is None or self.explosion_timer <= 0:
            return
        progress = 1.0 - (self.explosion_timer / self.explosion_duration)
        radius = int(80 + 220 * progress)
        colors = [(255, 245, 200), (255, 200, 140), (255, 150, 110), (255, 255, 255)]
        for idx, color in enumerate(colors):
            r = max(30, radius - idx * 35)
            width = max(1, 8 - idx * 2)
            pygame.draw.circle(surface, color, self.explosion_pos, r, width=width)

    def _draw_particles(self, surface: pygame.Surface) -> None:
        for particle in self.explosion_particles:
            pos = (int(particle["pos"].x), int(particle["pos"].y))
            pygame.draw.circle(surface, particle["color"], pos, particle["size"])

    def _update_player_trail(self, dt: float) -> None:
        if not self.trail_style:
            return
        # Append a trail point each frame while the player is moving
        speed = abs(self.player.velocity.x) + abs(self.player.velocity.y)
        if speed > 0.5:
            style = self.trail_style
            life = float(style.get("life", 0.45))
            size = int(style.get("size", 12))
            jitter = int(style.get("jitter", 4))
            count = int(style.get("count", 1))
            direction = pygame.Vector2(self.player.velocity)
            if direction.length() > 0.1:
                direction = direction.normalize()
            else:
                direction = pygame.Vector2(0, 1)
            for _ in range(max(1, count)):
                pos = pygame.Vector2(self.player.rect.center)
                if jitter:
                    pos.x += random.randint(-jitter, jitter)
                    pos.y += random.randint(-jitter, jitter)
                self._player_trail.append(
                    {
                        "pos": pos,
                        "life": life,
                        "max_life": life,
                        "size": size,
                        "angle": random.uniform(0, math.tau),
                        "dir": direction,
                    }
                )
        alive: List[Dict[str, Any]] = []
        for t in self._player_trail:
            t["life"] -= dt
            if t["life"] > 0:
                alive.append(t)
        self._player_trail = alive

    def _draw_player_trail(self, surface: pygame.Surface) -> None:
        if not self.trail_style or not self._player_trail:
            return
        style = self.trail_style
        base = style.get("color", self.trail_color)
        trail_name = style.get("name")
        for t in self._player_trail:
            life_ratio = max(0.0, t["life"] / max(0.01, t["max_life"]))
            alpha = int(220 * life_ratio)
            size = max(4, int(t["size"] * max(0.6, life_ratio)))
            if trail_name:
                tex_scale = float(style.get("tex_scale", 0.6))
                tex_size = max(14, int(size * tex_scale))
                tex = self.game.assets.trail_texture(trail_name, (tex_size, tex_size))
            else:
                tex = None
            x = int(t["pos"].x)
            y = int(t["pos"].y)
            if tex is not None:
                direction = t.get("dir") or pygame.Vector2(0, 1)
                for step in range(3):
                    step_alpha = max(0, int(alpha * (1.0 - step * 0.25)))
                    draw = tex.copy()
                    draw.set_alpha(step_alpha)
                    offset = direction * (-step * max(4, tex.get_width() * 0.6))
                    rect = draw.get_rect(center=(x + int(offset.x), y + int(offset.y)))
                    surface.blit(draw, rect)
            else:
                pygame.draw.circle(surface, (*base, alpha), (x, y), max(2, size // 3))

    def _draw_hat(self, surface: pygame.Surface, target_rect: pygame.Rect, offset: Tuple[int, int] = (0, 0)) -> None:
        hat_name = self.game.cosmetics.get("hat", "Default")
        color = self.game.active_hat_color()
        hat_width = target_rect.width
        hat_height = max(10, target_rect.height // 4)
        top = target_rect.top + offset[1] - hat_height + 4
        left = target_rect.left + offset[0]
        if hat_width > 0 and hat_height > 0:
            hat_img = self.game.assets.hat_texture(hat_name, (hat_width, hat_height))
            if hat_img is not None:
                surface.blit(hat_img, (left, top))
                return
        if not color:
            return
        brim_rect = pygame.Rect(left, top + hat_height - 6, hat_width, 6)
        crown_rect = pygame.Rect(left + hat_width * 0.2, top, hat_width * 0.6, hat_height - 6)
        pygame.draw.rect(surface, (*color, 220), brim_rect, border_radius=2)
        pygame.draw.rect(surface, (*color, 220), crown_rect, border_radius=3)

    def _draw_spawn_effects(self, surface: pygame.Surface) -> None:
        if not self.spawn_beams:
            return
        current_time = self.intro_timer
        for beam in self.spawn_beams:
            if current_time < beam["delay"]:
                continue
            progress = max(0.0, min(1.0, beam.get("progress", 0.0)))
            if progress <= 0.0:
                continue
            start_y = beam["start"]
            end_y = beam["end"]
            current_end = start_y + (end_y - start_y) * progress
            thickness = max(4, int(beam.get("thickness", 12)))
            width_main = thickness + 6
            length = int(abs(current_end - start_y))
            if length <= 0:
                continue

            beam_surface = pygame.Surface((width_main, length), pygame.SRCALPHA)
            main_rect = pygame.Rect((width_main - thickness) // 2, 0, thickness, length)
            pygame.draw.rect(beam_surface, (*beam["color"], int(180 * progress)), main_rect)

            inner_rect = main_rect.inflate(-max(0, thickness - 4), 0)
            if inner_rect.width > 0:
                pygame.draw.rect(beam_surface, (*beam["accent"], int(220 * progress)), inner_rect)

            glow_rect = main_rect.inflate(int(thickness * 0.6), 0)
            if glow_rect.width > 0:
                pygame.draw.rect(beam_surface, (*beam["accent"], int(90 * progress)), glow_rect, width=1)

            draw_x = int(beam["x"] - width_main / 2)
            draw_y = int(start_y)
            surface.blit(beam_surface, (draw_x, draw_y))

            if progress >= 1.0:
                glow_radius = 26
                glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow_surface, (*beam["accent"], 200), (glow_radius, glow_radius), glow_radius)
                pygame.draw.circle(glow_surface, (*beam["highlight"], 230), (glow_radius, glow_radius), glow_radius // 2)
                surface.blit(glow_surface, (int(beam["x"] - glow_radius), int(end_y - glow_radius // 2)))

            for particle in beam["particles"]:
                self._draw_spawn_particle(surface, particle)

    def _draw_spawn_particle(self, surface: pygame.Surface, particle: Dict[str, Any]) -> None:
        life_ratio = max(0.0, min(1.0, particle["life"] / particle["max_life"]))
        alpha = int(255 * life_ratio)
        if alpha <= 0:
            return
        size = int(particle["size"])
        shape = particle["shape"]
        color = particle["color"]
        pos = particle["pos"]
        surf_size = size * 2 + 6
        part_surface = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = (surf_size // 2, surf_size // 2)

        if shape == "leaf":
            points = [
                (center[0], center[1] - size),
                (center[0] + size, center[1]),
                (center[0], center[1] + size),
                (center[0] - size, center[1]),
            ]
            pygame.draw.polygon(part_surface, (*color, alpha), points)
            pygame.draw.line(part_surface, (*self.spawn_theme["highlight"], alpha), (center[0], center[1] - size), (center[0], center[1] + size), 2)
        elif shape == "stone":
            rect = pygame.Rect(0, 0, size + 4, size + 4)
            rect.center = center
            pygame.draw.rect(part_surface, (*color, alpha), rect)
        elif shape == "sand":
            pygame.draw.circle(part_surface, (*color, alpha), center, size)
        elif shape == "spore":
            pygame.draw.circle(part_surface, (*color, int(alpha * 0.7)), center, size + 2)
            pygame.draw.circle(part_surface, (*self.spawn_theme["highlight"], alpha), center, size - 1)
        elif shape == "snow":
            pygame.draw.circle(part_surface, (*color, alpha), center, size)
            pygame.draw.circle(part_surface, (255, 255, 255, alpha), center, max(1, size - 2))
        elif shape == "ember":
            pygame.draw.circle(part_surface, (*color, alpha), center, size)
            pygame.draw.circle(part_surface, (*self.spawn_theme["highlight"], int(alpha * 0.8)), center, max(1, size - 2))
        elif shape == "gust":
            pygame.draw.ellipse(part_surface, (*color, alpha), pygame.Rect(center[0] - size, center[1] - size // 2, size * 2, size))
        elif shape == "spark":
            pygame.draw.line(part_surface, (*color, alpha), (center[0] - size, center[1]), (center[0] + size, center[1]), 2)
            pygame.draw.line(part_surface, (*color, alpha), (center[0], center[1] - size), (center[0], center[1] + size), 2)
        elif shape == "wisp":
            pygame.draw.circle(part_surface, (*color, int(alpha * 0.6)), center, size + 2)
            pygame.draw.circle(part_surface, (*self.spawn_theme["highlight"], alpha), center, max(1, size - 1))
        elif shape == "glitch":
            for _ in range(3):
                w = random.randint(2, size + 2)
                h = random.randint(2, size + 2)
                ox = random.randint(-size, size)
                oy = random.randint(-size, size)
                rect = pygame.Rect(center[0] + ox, center[1] + oy, w, h)
                pygame.draw.rect(part_surface, (*color, alpha), rect)
        else:
            pygame.draw.circle(part_surface, (*color, alpha), center, size)

        surface.blit(part_surface, (int(pos.x - surf_size / 2), int(pos.y - surf_size / 2)))

    def _draw_boss(self, surface: pygame.Surface) -> None:
        if self.state == "explosion" or self.boss.health <= 0:
            return
        image = self.boss.image
        if self.state == "intro" and self.boss_spawn_alpha < 1.0:
            image = self.boss.image.copy()
            image.set_alpha(int(255 * max(0.0, min(1.0, self.boss_spawn_alpha))))
        surface.blit(image, self.boss.rect)

    def _init_spawn_animation(self) -> None:
        ground = next(iter(self.platforms), None)
        if ground is None:
            self.state = "fight"
            self.boss_spawn_alpha = 1.0
            if self.pending_roar:
                try:
                    self.game.sound.play_event("boss_roar")
                except Exception:
                    pass
                self.pending_roar = False
            return

        rng = random.Random(self.world * 733 + self.level * 19)
        if self.world >= 9:
            beam_count = 5
        elif self.world >= 5:
            beam_count = 4
        else:
            beam_count = 3
        if self.world in (6, 8, 10):
            beam_count += 1
        beam_count = max(3, min(6, beam_count))

        start_y = -220
        end_y = ground.rect.top
        self.spawn_beams.clear()
        total_duration = 0.0

        for idx in range(beam_count):
            offset = (idx - (beam_count - 1) / 2) * 70
            jitter = rng.uniform(-18, 18)
            beam_x = self.boss.rect.centerx + offset + jitter
            delay = max(0.0, idx * 0.22 + rng.uniform(0.0, 0.14))
            duration = 1.3 + rng.uniform(-0.1, 0.32)
            total_duration = max(total_duration, delay + duration)
            self.spawn_beams.append(
                {
                    "x": beam_x,
                    "start": start_y,
                    "end": end_y,
                    "duration": duration,
                    "delay": delay,
                    "progress": 0.0,
                    "color": self.spawn_theme.get("beam", DEFAULT_SPAWN_THEME["beam"]),
                    "accent": self.spawn_theme.get("particle", DEFAULT_SPAWN_THEME["particle"]),
                    "highlight": self.spawn_theme.get("highlight", DEFAULT_SPAWN_THEME["highlight"]),
                    "particles": [],
                    "emit_timer": rng.uniform(0.02, 0.08),
                    "thickness": 10 + rng.uniform(-1.5, 3.5),
                    "finished": False,
                }
            )

        self.spawn_fade_start = total_duration
        self.intro_duration = total_duration + 0.9
        self.intro_timer = 0.0
        self.boss_spawn_alpha = 0.0

    def _update_spawn_animation(self, dt: float) -> None:
        if not self.spawn_beams:
            self.boss_spawn_alpha = 1.0
            return

        self.intro_timer += dt
        all_finished = True
        for beam in self.spawn_beams:
            if self.intro_timer < beam["delay"]:
                all_finished = False
                self._update_beam_particles(beam, dt)
                continue
            elapsed = self.intro_timer - beam["delay"]
            duration = max(0.1, beam["duration"])
            progress = max(0.0, min(1.0, elapsed / duration))
            beam["progress"] = progress
            if progress < 1.0:
                all_finished = False

            beam["emit_timer"] -= dt
            while beam["emit_timer"] <= 0 and progress > 0.0:
                self._emit_beam_particle(beam, progress)
                beam["emit_timer"] += 0.07

            if progress >= 1.0 and not beam["finished"]:
                self._emit_ground_burst(beam)
                beam["finished"] = True

            self._update_beam_particles(beam, dt)

        fade_elapsed = max(0.0, self.intro_timer - self.spawn_fade_start)
        if self.spawn_fade_start <= 0.0:
            self.boss_spawn_alpha = min(1.0, self.boss_spawn_alpha + dt * 2.0)
        else:
            self.boss_spawn_alpha = max(self.boss_spawn_alpha, min(1.0, fade_elapsed / 0.8))

        if all_finished and self.intro_timer >= self.intro_duration:
            self.state = "fight"
            self.boss_spawn_alpha = 1.0
            self.intro_timer = 0.0
            self.spawn_beams.clear()
            if self.pending_roar:
                try:
                    self.game.sound.play_event("boss_roar")
                except Exception:
                    pass
                self.pending_roar = False
            self.boss.short_cooldown = max(self.boss.short_cooldown, 0.8)
            self.boss.long_cooldown = max(self.boss.long_cooldown, 1.2)

    def _emit_beam_particle(self, beam: Dict[str, Any], current_progress: float) -> None:
        shape = self.spawn_theme.get("shape", "spark")
        base_color = beam.get("accent", DEFAULT_SPAWN_THEME["particle"])
        span = beam["end"] - beam["start"]
        t = random.uniform(0.0, max(0.05, current_progress))
        pos = pygame.Vector2(beam["x"] + random.uniform(-8, 8), beam["start"] + span * t)
        life = random.uniform(0.45, 0.9)
        velocity = pygame.Vector2(0, random.uniform(80, 160))

        if shape == "snow":
            velocity = pygame.Vector2(random.uniform(-20, 20), random.uniform(60, 100))
        elif shape == "ember":
            velocity = pygame.Vector2(random.uniform(-30, 30), random.uniform(120, 200))
        elif shape == "gust":
            velocity = pygame.Vector2(random.uniform(-140, 140), random.uniform(50, 120))
        elif shape == "spark":
            angle = random.uniform(-0.6, 0.6)
            speed = random.uniform(150, 220)
            velocity = pygame.Vector2(math.sin(angle), math.cos(angle)) * speed
        elif shape == "glitch":
            velocity = pygame.Vector2(random.uniform(-180, 180), random.uniform(40, 160))
        elif shape == "wisp":
            velocity = pygame.Vector2(random.uniform(-50, 50), random.uniform(90, 160))
        elif shape == "leaf":
            velocity = pygame.Vector2(random.uniform(-70, 70), random.uniform(80, 140))

        particle = {
            "pos": pos,
            "vel": velocity,
            "life": life,
            "max_life": life,
            "size": random.randint(3, 6),
            "color": base_color,
            "shape": shape,
        }
        beam["particles"].append(particle)

    def _emit_ground_burst(self, beam: Dict[str, Any]) -> None:
        shape = self.spawn_theme.get("shape", "spark")
        base_color = self.spawn_theme.get("particle", DEFAULT_SPAWN_THEME["particle"])
        burst_count = 14 if shape not in ("spark", "glitch") else 18
        for _ in range(burst_count):
            angle = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
            speed = random.uniform(160, 260)
            velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
            if shape == "snow":
                velocity *= 0.6
            if shape == "gust":
                velocity.x *= 1.4
            if shape == "glitch":
                velocity.x *= random.uniform(0.4, 1.4)
            pos = pygame.Vector2(beam["x"] + random.uniform(-18, 18), beam["end"])
            life = random.uniform(0.6, 1.2)
            particle = {
                "pos": pos,
                "vel": velocity,
                "life": life,
                "max_life": life,
                "size": random.randint(4, 7),
                "color": base_color,
                "shape": shape,
            }
            beam["particles"].append(particle)

    def _update_beam_particles(self, beam: Dict[str, Any], dt: float) -> None:
        remaining: List[Dict[str, Any]] = []
        gravity = 80
        for particle in beam["particles"]:
            particle["life"] -= dt
            if particle["life"] <= 0:
                continue
            shape = particle["shape"]
            if shape == "ember":
                particle["vel"].y -= gravity * 0.6 * dt
            elif shape == "snow":
                particle["vel"].x += math.sin(pygame.time.get_ticks() * 0.003) * 6 * dt
                particle["vel"].y += gravity * 0.4 * dt
            elif shape == "gust":
                particle["vel"].x *= 0.98
                particle["vel"].y += gravity * 0.35 * dt
            elif shape == "spark":
                particle["vel"] *= 0.97
            elif shape == "glitch":
                if random.random() < 0.1:
                    particle["vel"].x *= -1
            else:
                particle["vel"].y += gravity * 0.5 * dt

            particle["pos"] += particle["vel"] * dt * 0.6
            remaining.append(particle)
        beam["particles"] = remaining

    def _update_explosion_effects(self, dt: float) -> None:
        if not self.explosion_particles:
            return
        decay = 0.9
        remaining: List[Dict[str, Any]] = []
        for particle in self.explosion_particles:
            particle["life"] -= dt
            if particle["life"] <= 0:
                continue
            particle["pos"] += particle["vel"]
            particle["vel"] *= decay
            remaining.append(particle)
        self.explosion_particles = remaining


class VictoryScene(Scene):
    def __init__(self, game: "Game"):
        super().__init__(game)
        self.blink = 0

    def on_enter(self) -> None:
        self.game.play_music("credits.mp3")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.game.quit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.game.change_scene(TitleScene)

    def update(self, dt: float) -> None:
        self.blink = (self.blink + 1) % 60

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        temp = pygame.Surface((w, h)).convert()
        temp.fill((0,0,0))

        font_big = self.game.assets.font(40, True)
        font_mid = self.game.assets.font(30, True)
        font_small = self.game.assets.font(22, False)

        draw_center_text(temp, font_big, "REALITY HAS COLLAPSED", 250, WHITE)
        draw_center_text(temp, font_mid, "YOU WIN", 320, WHITE)
        draw_prompt_with_icons(temp, font_small, "Press ENTER to return to Main Menu", 450, WHITE, device=getattr(self.game, "last_input_device", "keyboard"))


        # Use only level 8 glitches from CreditsScene for performance and style
        if getattr(self.game.settings, '__getitem__', None) and self.game.settings["glitch_fx"]:
            # Level 8: vortex, blackhole, heavy slices/rgb/flash
            self.glitch_vortex(temp)
            self.glitch_blackhole(temp)
            self.glitch_slices(temp, 8, 35)
            self.glitch_rgb_split(temp, 12)
            self.glitch_flash(temp)

        surface.blit(temp, (0,0))

    # --- Glitch helpers (copied from CreditsScene) ---
    def glitch_static(self, surf, amount=80):
        noise = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        arr = pygame.surfarray.pixels_alpha(noise)
        arr[:, :] = np.random.randint(0, 256, arr.shape, dtype=arr.dtype)
        del arr
        noise.set_alpha(random.randint(30, 70))
        surf.blit(noise, (0,0), special_flags=pygame.BLEND_SUB)

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
            bar = surf.subsurface((0, y, w, bar_height)).copy()
            sx = random.randint(-20, 20)
            surf.blit(bar, (sx, y))

    def glitch_meltdown(self, surf):
        offset = math.sin(self.blink * 0.2) * 5
        surf.scroll(dx=int(offset), dy=0)

    def glitch_wireframe(self, surf):
        w, h = surf.get_size()
        wire = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 50):
            pygame.draw.line(wire, (80,80,80,100), (0,y), (w,y))
        for x in range(0, w, 50):
            pygame.draw.line(wire, (80,80,80,100), (x,0), (x,h))
        surf.blit(wire, (0,0))

    def glitch_datamosh(self, surf):
        w, h = surf.get_size()
        slice_h = 6
        for _ in range(5):
            y = random.randint(0, h-1)
            actual_h = slice_h
            if y + actual_h > h:
                actual_h = h - y
            if actual_h <= 0:
                continue
            slc = surf.subsurface((0, y, w, actual_h)).copy()
            surf.blit(slc, (random.randint(-30, 30), y))

    # --- Glitch helpers (copied from CreditsScene) ---
    def glitch_vortex(self, surf):
        # No tilt, just a slight scale effect
        angle = 0
        scaled = pygame.transform.rotozoom(surf, angle, 1.02)
        rect = scaled.get_rect(center=surf.get_rect().center)
        surf.blit(scaled, rect)

    def glitch_blackhole(self, surf):
        scale = 1 + (math.sin(self.blink * 0.1) * 0.05)
        scaled = pygame.transform.rotozoom(surf, 0, scale)
        rect = scaled.get_rect(center=surf.get_rect().center)
        surf.blit(scaled, rect, special_flags=pygame.BLEND_SUB)

    def glitch_slices(self, surf, slices=4, max_shift=30):
        w, h = surf.get_size()
        for _ in range(slices):
            y = random.randint(0, h - 4)
            slice_h = random.randint(4, 20)
            if y + slice_h > h:
                slice_h = h - y
            if slice_h <= 0:
                continue
            shift = random.randint(-max_shift, max_shift)
            slc = surf.subsurface((0, y, w, slice_h)).copy()
            surf.blit(slc, (shift, y))

    def glitch_rgb_split(self, surf, amount=4):
        ox = random.randint(-amount, amount)
        oy = random.randint(-amount, amount)
        shifted = pygame.Surface(surf.get_size()).convert()
        shifted.blit(surf, (ox, oy))
        surf.blit(shifted, (0,0), special_flags=pygame.BLEND_ADD)

    def glitch_flash(self, surf):
        flash = pygame.Surface(surf.get_size())
        flash.fill((255,255,255))
        flash.set_alpha(random.randint(20, 120))
        surf.blit(flash, (0,0))

# --- Portal Collapse Cutscene (new) ---
def play_portal_collapse_cutscene(game: "Game", portal_pos: Tuple[int, int], objects: list, backgrounds: list) -> None:
    """
    Finale: the portal awakens, pulls reality inside-out, detonates, then drops into the credits.
    Uses sounds if available; gracefully degrades otherwise.
    """
    game.pause_speedrun(True)
    clock = pygame.time.Clock()
    TARGET_FPS = 60

    for cue in ("portal_open", "collapse_rumble"):
        try:
            game.sound.play_event(cue)
        except Exception:
            pass

    portal_tex = game.assets.portal_texture(10)
    bg_surfs = [bg.copy().convert() for bg in backgrounds] if backgrounds else []
    obj_surfs = [obj.image.copy() if hasattr(obj, "image") else obj.copy() for obj in objects] if objects else []

    debris: list[dict] = []
    for _ in range(260):
        vel = pygame.Vector2(random.uniform(-3, 3), random.uniform(-3, 3)) * random.uniform(6, 18)
        debris.append({
            "pos": pygame.Vector2(portal_pos),
            "vel": vel,
            "life": random.uniform(0.5, 1.5),
            "color": (
                random.randint(180, 255),
                random.randint(120, 255),
                random.randint(200, 255),
            ),
        })

    start = time.time()
    duration = 10.0
    inversion_triggered = False
    explosion_triggered = False

    while game.running:
        now = time.time() - start
        t = min(now / duration, 1.0)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.quit()
                return

        portal_pulse = min(1.0, t / 0.35)
        suck_t = max(0.0, min(1.0, (t - 0.2) / 0.6))
        invert_t = max(0.0, min(1.0, (t - 0.6) / 0.25))
        explode_t = max(0.0, min(1.0, (t - 0.8) / 0.2))

        game.screen.fill((6, 4, 12))

        if bg_surfs:
            for idx, bg in enumerate(bg_surfs):
                angle = math.sin(t * 2.0 + idx) * 2.5
                scale = 1.0 + 0.08 * math.sin(t * 3.0 + idx)
                bg_scaled = pygame.transform.rotozoom(bg, angle, scale)
                rect = bg_scaled.get_rect(center=portal_pos)
                game.screen.blit(bg_scaled, rect)
        else:
            band_h = SCREEN_HEIGHT // 12
            for i in range(12):
                shade = 20 + i * 12
                pygame.draw.rect(game.screen, (shade, 0, shade + 20), (0, i * band_h, SCREEN_WIDTH, band_h))

        if game.settings["glitch_fx"]:
            for _ in range(14):
                y = random.randint(0, SCREEN_HEIGHT - 6)
                h = random.randint(2, 6)
                pygame.draw.rect(game.screen, (random.randint(120, 255), 0, random.randint(120, 255)), (0, y, SCREEN_WIDTH, h), width=0)

        for obj in obj_surfs:
            rect = obj.get_rect()
            angle = random.random() * math.tau
            radius = (1 - suck_t) * max(SCREEN_WIDTH, SCREEN_HEIGHT) * 0.75
            cx = int(portal_pos[0] + math.cos(angle) * radius)
            cy = int(portal_pos[1] + math.sin(angle) * radius)
            scale = max(0.22, 1.2 - suck_t)
            obj_scaled = pygame.transform.smoothscale(obj, (max(2, int(rect.width * scale)), max(2, int(rect.height * scale))))
            obj_rect = obj_scaled.get_rect(center=(cx, cy))
            game.screen.blit(obj_scaled, obj_rect)

        pulse_scale = 1.0 + 0.22 * math.sin(t * 8.0)
        portal_surf = pygame.transform.smoothscale(portal_tex, (int(portal_tex.get_width() * pulse_scale), int(portal_tex.get_height() * pulse_scale)))
        portal_rect = portal_surf.get_rect(center=portal_pos)
        game.screen.blit(portal_surf, portal_rect, special_flags=pygame.BLEND_ADD)

        if invert_t > 0 and not inversion_triggered:
            inversion_triggered = True
            try:
                game.sound.play_event("glitch_effect")
            except Exception:
                pass
        if invert_t > 0:
            inv_alpha = int(140 * invert_t)
            inv = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            inv.fill((255, 255, 255, inv_alpha))
            game.screen.blit(inv, (0, 0), special_flags=pygame.BLEND_SUB)

        if explode_t > 0 and not explosion_triggered:
            explosion_triggered = True
            try:
                game.sound.play_event("collapse_boom")
            except Exception:
                pass
        if explode_t > 0:
            flash_alpha = max(0, 255 - int(explode_t * 255))
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 240, 255, flash_alpha))
            game.screen.blit(flash, (0, 0))
            alive = []
            for d in debris:
                d["life"] -= 1 / TARGET_FPS
                if d["life"] <= 0:
                    continue
                d["pos"] += d["vel"]
                d["vel"] *= 0.9
                pygame.draw.rect(game.screen, d["color"], (int(d["pos"].x), int(d["pos"].y), 3, 3))
                alive.append(d)
            debris = alive

        vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(12):
            alpha = int(12 * (i + 1))
            pygame.draw.rect(vignette, (0, 0, 0, alpha), (i * 4, i * 4, SCREEN_WIDTH - i * 8, SCREEN_HEIGHT - i * 8), width=6)
        game.screen.blit(vignette, (0, 0))

        pygame.display.flip()
        clock.tick(TARGET_FPS)

        if t >= 1.0 and not debris:
            break

    game.change_scene(CreditsScene, ending_mode=True)


# ---------------------------------------------------------------------------
# Game controller
# ---------------------------------------------------------------------------


class LevelEditorScene(Scene):
    def __init__(self, game, world, level):
        super().__init__(game)
        self.editor_world = world
        self.editor_level = level
        self.level_path = None
        self.selected_tool = "platform"  # platform, coin, special
        self.cursor_pos = [100, 100]
        self.platforms = []  # List of rects (x, y, w, h)
        self.coins = []      # List of (x, y)
        self.specials = []   # List of (x, y)
        self.goal = None     # (x, y)
        self.selected_object = None  # (type, index)
        self.drag_offset = (0, 0)
        self.is_dragging = False
        self.camera_x = 0
        self.camera_y = 0
        self._camera_move = {"left": False, "right": False, "up": False, "down": False}
        self.load_current_level()

    def load_current_level(self):
        # Always use the world/level passed to the editor
        world = self.editor_world
        level = self.editor_level
        self.level_path = None  # No file persistence; purely procedural
        # 1. Generate the procedural level
        generator = self.game.level_generator
        procedural = generator.generate(world, level)
        # 2. Load procedural objects into editor
        self.platforms = [pygame.Rect(p.rect.x, p.rect.y, p.rect.width, p.rect.height) for p in list(getattr(procedural, 'platforms', []))]
        self.coins = [(c.rect.centerx, c.rect.centery) for c in getattr(procedural, 'coins', [])]
        self.specials = [(s.rect.x, s.rect.y) for s in getattr(procedural, 'specials', [])]
        self.goal = (procedural.goal.rect.x, procedural.goal.rect.y) if getattr(procedural, 'goal', None) else None
        self.enemies = []
        self.spikes = []
        self._other_sections = {}

    def save_level(self):
        # No-op: persistence removed; levels are fully procedural
        print("[Level Editor] Save disabled (levels folder unused)")

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_a, pygame.K_LEFT):
                self._camera_move["left"] = True
            elif event.key in (pygame.K_d, pygame.K_RIGHT):
                self._camera_move["right"] = True
            elif event.key in (pygame.K_w, pygame.K_UP):
                self._camera_move["up"] = True
            elif event.key in (pygame.K_s, pygame.K_DOWN):
                self._camera_move["down"] = True
            elif event.key == pygame.K_ESCAPE:
                # Cleanly exit the editor
                self.game.scene = self.game.last_scene
            elif event.key == pygame.K_p:
                # Playtest from level start
                self._playtest_mode = not getattr(self, '_playtest_mode', False)
                if self._playtest_mode:
                    # Reset player to level start
                    self.player.rect.topleft = self._compute_spawn_point()
                else:
                    # Return to editor mode
                    pass
            elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                self.save_level()
            elif event.key == pygame.K_TAB:
                # Cycle tool
                tools = ["platform", "coin", "special"]
                idx = tools.index(self.selected_tool)
                self.selected_tool = tools[(idx + 1) % len(tools)]
            elif event.key == pygame.K_SPACE:
                if self.selected_tool == "platform":
                    # Use procedural platform size
                    generator = self.game.level_generator
                    settings = generator.settings if hasattr(generator, 'settings') else None
                    difficulty = generator._difficulty_for(self.editor_world, self.editor_level, "tower" if self.editor_level % 10 == 0 else "default") if hasattr(generator, '_difficulty_for') else 0.0
                    width = 100
                    height = 20
                    if settings:
                        width = int(settings.width_min.lerp(difficulty))
                        height = getattr(settings, 'base_platform_height', 32)
                    plat = pygame.Rect(self.cursor_pos[0], self.cursor_pos[1], width, height)
                    self.platforms.append(plat)
                elif self.selected_tool == "coin":
                    self.coins.append(tuple(self.cursor_pos))
                elif self.selected_tool == "special":
                    self.specials.append(tuple(self.cursor_pos))
            elif event.key == pygame.K_DELETE:
                if self.selected_tool == "platform":
                    for plat in self.platforms:
                        if plat.collidepoint(self.cursor_pos):
                            self.platforms.remove(plat)
                            break
                elif self.selected_tool == "coin":
                    for coin in self.coins:
                        cx, cy = coin
                        if abs(cx - self.cursor_pos[0]) < 16 and abs(cy - self.cursor_pos[1]) < 16:
                            self.coins.remove(coin)
                            break
                elif self.selected_tool == "special":
                    for obj in self.specials:
                        ox, oy = obj
                        if abs(ox - self.cursor_pos[0]) < 20 and abs(oy - self.cursor_pos[1]) < 20:
                            self.specials.remove(obj)
                            break
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_a, pygame.K_LEFT):
                self._camera_move["left"] = False
            elif event.key in (pygame.K_d, pygame.K_RIGHT):
                self._camera_move["right"] = False
            elif event.key in (pygame.K_w, pygame.K_UP):
                self._camera_move["up"] = False
            elif event.key in (pygame.K_s, pygame.K_DOWN):
                self._camera_move["down"] = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.cursor_pos = list(event.pos)
            # Always allow drag/move if cursor tool is selected
            found = False
            if getattr(self, '_level_editor_selected_tool', 'platform') == 'cursor':
                # Try to select an object under the cursor
                for idx, plat in enumerate(self.platforms):
                    if plat.collidepoint(self.cursor_pos):
                        self.selected_object = ("platform", idx)
                        self.drag_offset = (self.cursor_pos[0] - plat.x, self.cursor_pos[1] - plat.y)
                        self.is_dragging = True
                        found = True
                        break
                if not found:
                    for idx, (cx, cy) in enumerate(self.coins):
                        if abs(cx - self.cursor_pos[0]) < 16 and abs(cy - self.cursor_pos[1]) < 16:
                            self.selected_object = ("coin", idx)
                            self.drag_offset = (self.cursor_pos[0] - cx, self.cursor_pos[1] - cy)
                            self.is_dragging = True
                            found = True
                            break
                if not found:
                    for idx, (ox, oy) in enumerate(self.specials):
                        if abs(ox - self.cursor_pos[0]) < 20 and abs(oy - self.cursor_pos[1]) < 20:
                            self.selected_object = ("special", idx)
                            self.drag_offset = (self.cursor_pos[0] - ox, self.cursor_pos[1] - oy)
                            self.is_dragging = True
                            found = True
                            break
                if not found:
                    self.selected_object = None
            else:
                self.selected_object = None
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.is_dragging = False
            self.selected_object = None
        elif event.type == pygame.MOUSEMOTION:
            self.cursor_pos = list(event.pos)
            if self.is_dragging and self.selected_object:
                obj_type, idx = self.selected_object
                if obj_type == "platform":
                    plat = self.platforms[idx]
                    plat.x = self.cursor_pos[0] - self.drag_offset[0]
                    plat.y = self.cursor_pos[1] - self.drag_offset[1]
                elif obj_type == "coin":
                    self.coins[idx] = (self.cursor_pos[0] - self.drag_offset[0], self.cursor_pos[1] - self.drag_offset[1])
                elif obj_type == "special":
                    self.specials[idx] = (self.cursor_pos[0] - self.drag_offset[0], self.cursor_pos[1] - self.drag_offset[1])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.is_dragging = False
            self.selected_object = None
        elif event.type == pygame.MOUSEMOTION:
            self.cursor_pos = list(event.pos)
            if self.is_dragging and self.selected_object:
                obj_type, idx = self.selected_object
                if obj_type == "platform":
                    plat = self.platforms[idx]
                    plat.x = self.cursor_pos[0] - self.drag_offset[0]
                    plat.y = self.cursor_pos[1] - self.drag_offset[1]
                elif obj_type == "coin":
                    self.coins[idx] = (self.cursor_pos[0] - self.drag_offset[0], self.cursor_pos[1] - self.drag_offset[1])
                elif obj_type == "special":
                    self.specials[idx] = (self.cursor_pos[0] - self.drag_offset[0], self.cursor_pos[1] - self.drag_offset[1])

    def update(self, dt):
        # Smooth camera movement
        speed = int(400 * dt)
        prev_camera_x = self.camera_x
        prev_camera_y = self.camera_y
        if self._camera_move["left"]:
            self.camera_x -= speed
        if self._camera_move["right"]:
            self.camera_x += speed
        if self._camera_move["up"]:
            self.camera_y -= speed
        if self._camera_move["down"]:
            self.camera_y += speed
        # If the camera moved and the mouse is not being moved, update the cursor to follow the mouse
        if (self.camera_x != prev_camera_x or self.camera_y != prev_camera_y):
            # Get the current mouse position in screen coordinates
            mouse_x, mouse_y = pygame.mouse.get_pos()
            # Update cursor_pos to be at the world position under the mouse
            self.cursor_pos = [mouse_x + self.camera_x, mouse_y + self.camera_y]

    def draw(self, surface):
        surface.fill((30, 30, 40))
        # Load assets if not already loaded
        # Always reload platform asset for the current world
        world = getattr(self.game, "world", 1)
        platform_asset_path = PLATFORM_DIR / f'platform{world}.png'
        try:
            self._platform_img = pygame.image.load(str(platform_asset_path)).convert_alpha()
        except Exception:
            self._platform_img = None
        if not hasattr(self, '_coin_img'):
            try:
                self._coin_img = pygame.image.load(str(OBJECT_DIR / 'coin.png')).convert_alpha()
            except Exception:
                self._coin_img = None
        if not hasattr(self, '_special_img'):
            try:
                self._special_img = pygame.image.load(str(OBJECT_DIR / 'spike.png')).convert_alpha()
            except Exception:
                self._special_img = None
        # Draw all platforms
        for plat in self.platforms:
            draw_x = plat.x - self.camera_x
            draw_y = plat.y - self.camera_y
            if self._platform_img:
                img = pygame.transform.scale(self._platform_img, (plat.w, plat.h))
                surface.blit(img, (draw_x, draw_y))
            else:
                pygame.draw.rect(surface, (100, 200, 255), pygame.Rect(draw_x, draw_y, plat.w, plat.h))
        # Draw all coins
        for x, y in self.coins:
            draw_x = x - self.camera_x
            draw_y = y - self.camera_y
            if self._coin_img:
                rect = self._coin_img.get_rect(center=(draw_x, draw_y))
                surface.blit(self._coin_img, rect)
            else:
                pygame.draw.circle(surface, (255, 255, 80), (draw_x, draw_y), 10)
        # Draw all specials (objects)
        for x, y in self.specials:
            draw_x = x - self.camera_x
            draw_y = y - self.camera_y
            if self._special_img:
                rect = self._special_img.get_rect(center=(draw_x, draw_y))
                surface.blit(self._special_img, rect)
            else:
                pygame.draw.rect(surface, (255, 120, 40), (draw_x-10, draw_y-10, 20, 20))
        # Draw goal
        if self.goal:
            gx, gy = self.goal
            pygame.draw.circle(surface, (80, 255, 120), (gx - self.camera_x, gy - self.camera_y), 16, 3)
        # Draw cursor
        color = (255, 80, 80)
        cursor_x = self.cursor_pos[0] - self.camera_x
        cursor_y = self.cursor_pos[1] - self.camera_y
        # Draw asset preview at cursor (semi-transparent)
        preview_alpha = 128
        tool = self.selected_tool
        if tool == "cursor":
            # Draw the cursor icon at the cursor position
            try:
                cursor_img = pygame.image.load(str(OBJECT_DIR / 'cursor.png')).convert_alpha()
                cursor_img.set_alpha(preview_alpha)
                rect = cursor_img.get_rect(center=(cursor_x, cursor_y))
                surface.blit(cursor_img, rect)
            except Exception:
                pygame.draw.polygon(surface, (255,255,255,preview_alpha), [(cursor_x-12, cursor_y-12), (cursor_x+12, cursor_y), (cursor_x, cursor_y+4), (cursor_x-4, cursor_y+12)])
        elif tool == "platform":
            if self._platform_img:
                img = pygame.transform.scale(self._platform_img, (100, 20)).copy()
                img.set_alpha(preview_alpha)
                surface.blit(img, (cursor_x, cursor_y))
            pygame.draw.rect(surface, color, (cursor_x, cursor_y, 100, 20), 2)
        elif tool == "coin":
            if self._coin_img:
                img = self._coin_img.copy()
                img.set_alpha(preview_alpha)
                rect = img.get_rect(center=(cursor_x, cursor_y))
                surface.blit(img, rect)
            pygame.draw.circle(surface, color, (cursor_x, cursor_y), 12, 2)
        elif tool == "special":
            # For now, use spike asset for preview; can expand for more types
            if self._special_img:
                img = self._special_img.copy()
                img.set_alpha(preview_alpha)
                rect = img.get_rect(center=(cursor_x, cursor_y))
                surface.blit(img, rect)
            pygame.draw.rect(surface, color, (cursor_x-12, cursor_y-12, 24, 24), 2)
        # Optionally: add more elifs for other object types if needed
        # Draw UI text
        font = pygame.font.SysFont("consolas", 28)
        draw_prompt_with_icons(
            surface,
            font,
            f"Level Editor: Tool=[{self.selected_tool}] Tab=Cycle Ctrl+S=Save Space=Add Del=Remove Esc=Exit | WASD/Arrows=Pan",
            40,
            (255, 255, 255),
            device=getattr(self.game, "last_input_device", "keyboard"),
        )


# === Game loop / application ===
class Game:
    def open_level_editor(self) -> None:
        # Launch the level editor scene for the current world/level
        self.last_scene = getattr(self, "scene", None)
        self.scene = LevelEditorScene(self, getattr(self, "world", 1), getattr(self, "level", 1))
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        show_seizure_warning(self.screen)
        try:
            pygame.mixer.init()
        except Exception as exc:
            print(f"[Audio] Mixer init failed: {exc}")
        pygame.joystick.init()

        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.assets = AssetCache()
        self.level_generator = LevelGenerator(self.assets)
        # Dev console disabled
        self.dev_console = None
        self.gamepads: List[pygame.joystick.Joystick] = []
        self.input_state = InputState()
        self.window_mode: str = "windowed"

        self.settings = SettingsManager(SETTINGS_FILE)
        self.apply_window_mode(self.settings["window_mode"])
        self.sound = SoundManager(self.settings)
        self.progress = ProgressManager(SAVE_FILE)
        self.progress.game = self  # Allow ProgressManager to access game.selected_character and game.selected_form
        # Load saved player color if present, otherwise use default
        default_color = (160, 220, 255)
        self.player_color = tuple(self.progress.player_color) if getattr(self.progress, "player_color", None) else default_color
        self.skills = self.progress.skills.copy()
        self.cosmetics = self.progress.cosmetics.copy()
        self.running = True
        self.speedrun_active = False
        self.speedrun_start = 0.0
        self.speedrun_pause_accum = 0.0
        self.speedrun_paused = False
        self.speedrun_pause_start = 0.0
        self.world1_intro_shown = False
        self.current_music = None
        self._last_music = None
        self._prev_controller_state = InputState()
        self.last_input_device: str = "keyboard"
        self._suppress_accept_until = 0.0

        self._refresh_gamepads()
        self.scene = CreditScene(self)
        self.scene.on_enter()
        # Short timestamp to ignore stray ESC events immediately after closing the console
        self._suppress_escape_until = 0.0

    def active_outfit_color(self) -> Tuple[int, int, int]:
        """Resolve the current outfit tint color."""
        outfit = self.cosmetics.get("outfit", "None") if hasattr(self, "cosmetics") else "None"
        return OUTFIT_COLORS.get(outfit, self.player_color)

    def active_outfit_form(self) -> Optional[str]:
        """Return outfit asset folder name if one exists for the selected outfit."""
        outfit = self.cosmetics.get("outfit", "None") if hasattr(self, "cosmetics") else "None"
        if outfit == "None":
            return None
        outfit_dir = ASSET_DIR / "outfits" / outfit
        return outfit if outfit_dir.exists() else None

    def active_trail_color(self) -> Optional[Tuple[int, int, int]]:
        trail = self.cosmetics.get("trail", "None") if hasattr(self, "cosmetics") else "None"
        if trail == "None":
            return None
        return TRAIL_COLORS.get(trail, None)

    def active_trail_style(self) -> Optional[Dict[str, Any]]:
        trail = self.cosmetics.get("trail", "None") if hasattr(self, "cosmetics") else "None"
        if trail == "None":
            return None
        style = TRAIL_STYLES.get(trail, {})
        return {
            "name": trail,
            "color": TRAIL_COLORS.get(trail, (200, 240, 255)),
            "life": style.get("life", 0.45),
            "size": style.get("size", 12),
            "jitter": style.get("jitter", 4),
            "count": style.get("count", 1),
            "tex_scale": style.get("tex_scale", 0.6),
        }

    def active_hat_color(self) -> Optional[Tuple[int, int, int]]:
        hat = self.cosmetics.get("hat", "None") if hasattr(self, "cosmetics") else "None"
        if hat == "None":
            return None
        return HAT_COLORS.get(hat, None)

    def change_scene(self, scene_cls: Callable[..., Scene], *args, **kwargs) -> None:
        self.scene.on_exit()
        # If scene_cls is a lambda or callable, call it to get the scene instance
        if callable(scene_cls) and not isinstance(scene_cls, type):
            new_scene = scene_cls(self)
        elif isinstance(scene_cls, Scene):
            new_scene = scene_cls
        else:
            new_scene = scene_cls(self, *args, **kwargs)
        # Pause speedrun unless entering GameplayScene
        if new_scene.__class__.__name__ != "GameplayScene":
            self.pause_speedrun(True)
        self.scene = new_scene
        if hasattr(self.scene, "on_enter"):
            self.scene.on_enter()
        self.scene.on_exit()
        # If scene_cls is a lambda or callable, call it to get the scene instance
        if callable(scene_cls) and not isinstance(scene_cls, type):
            self.scene = scene_cls(self)
        elif isinstance(scene_cls, Scene):
            self.scene = scene_cls
        else:
            self.scene = scene_cls(self, *args, **kwargs)
        if hasattr(self.scene, "on_enter"):
            self.scene.on_enter()

    def _refresh_gamepads(self) -> None:
        self.gamepads = []
        try:
            count = pygame.joystick.get_count()
        except pygame.error:
            count = 0
        for index in range(count):
            try:
                joystick = pygame.joystick.Joystick(index)
                joystick.init()
            except pygame.error as exc:
                print(f"[Input] Failed to init gamepad {index}: {exc}")
                continue
            self.gamepads.append(joystick)

    def _post_controller_events(self, prev_controller_state: InputState, controller_state: InputState) -> None:
        menu_up_pressed = controller_state.menu_up and not prev_controller_state.menu_up
        menu_down_pressed = controller_state.menu_down and not prev_controller_state.menu_down
        accept_pressed = controller_state.accept and not prev_controller_state.accept
        back_pressed = controller_state.back and not prev_controller_state.back
        pause_pressed = controller_state.pause and not prev_controller_state.pause
        shoot_pressed = controller_state.shoot and not prev_controller_state.shoot
        shield_pressed = controller_state.shield and not prev_controller_state.shield

        current_scene = getattr(self, "scene", None)
        is_title = current_scene.__class__.__name__ == "TitleScene" if current_scene else False
        is_boss_scene = current_scene.__class__.__name__ == "BossArenaScene" if current_scene else False

        if menu_up_pressed:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        if menu_down_pressed:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        if accept_pressed:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        if back_pressed and not is_title:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        if pause_pressed and not back_pressed and not is_title:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        if shoot_pressed:
            # Map controller shoot (X button) to keyboard F; if in boss scene, also flag last input device
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f))
            if is_boss_scene:
                self.last_input_device = "controller"
        if shield_pressed:
            # Map shield to a dedicated key event (use 'g' as shield key)
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_g))
            if is_boss_scene:
                self.last_input_device = "controller"

    def _poll_controller(self) -> None:
        prev = self.input_state
        state = InputState()
        
        prev_c_state = self._prev_controller_state
        c_state = InputState()

        key_map = self.settings["key_map"]
        controller_map = self.settings["controller_map"]
        keys = pygame.key.get_pressed()

        state.move_left = keys[key_map["move_left"]] or keys[pygame.K_LEFT]
        state.move_right = keys[key_map["move_right"]] or keys[pygame.K_RIGHT]
        state.up = keys[key_map["up"]] or keys[pygame.K_UP]
        state.down = keys[key_map["down"]] or keys[pygame.K_DOWN]
        state.jump = keys[key_map["jump"]] or keys[pygame.K_w] or keys[pygame.K_UP]
        state.shoot = keys[key_map["shoot"]]
        state.shield = keys[key_map.get("shield", pygame.K_LSHIFT)]
        state.dash = keys[key_map.get("dash", pygame.K_e)]
        state.pause = keys[key_map["pause"]]
        state.accept = keys[key_map["accept"]]
        state.back = keys[key_map["back"]]
        state.menu_up = keys[key_map["menu_up"]]
        state.menu_down = keys[key_map["menu_down"]]

        if self.gamepads:
            joystick = self.gamepads[0]
            
            axis0 = joystick.get_axis(controller_map["move_axis_x"])
            axis1 = joystick.get_axis(controller_map["move_axis_y"])
            state.move_axis = axis0
            state.vertical_axis = axis1
            
            state.move_left = state.move_left or axis0 <= -0.35
            state.move_right = state.move_right or axis0 >= 0.35
            state.up = state.up or axis1 <= -0.35
            state.down = state.down or axis1 >= 0.35

            state.jump = state.jump or joystick.get_button(controller_map.get("jump", 0))
            # Shooter uses X button (index 2) by default; also consider square/cross variants if mapped differently
            shoot_button_index = controller_map.get("shoot", 2)
            if joystick.get_numbuttons() > shoot_button_index:
                state.shoot = state.shoot or joystick.get_button(shoot_button_index)
            shield_button_index = controller_map.get("shield", 3)
            if joystick.get_numbuttons() > shield_button_index:
                state.shield = state.shield or joystick.get_button(shield_button_index)
            dash_button_index = controller_map.get("dash", 5)
            if joystick.get_numbuttons() > dash_button_index:
                state.dash = state.dash or joystick.get_button(dash_button_index)
            
            c_state.pause = joystick.get_button(controller_map["pause"])
            c_state.accept = joystick.get_button(controller_map["accept"])
            c_state.back = joystick.get_button(controller_map["back"])
            
            if joystick.get_numhats() > 0:
                hat_x, hat_y = joystick.get_hat(0)
                c_state.menu_up = hat_y == 1
                c_state.menu_down = hat_y == -1
        
        state.pause = state.pause or c_state.pause
        state.accept = state.accept or c_state.accept
        state.back = state.back or c_state.back
        state.menu_up = state.menu_up or c_state.menu_up
        state.menu_down = state.menu_down or c_state.menu_down

        state.jump_pressed = state.jump and not prev.jump
        state.shoot_pressed = state.shoot and not prev.shoot
        state.shield_pressed = state.shield and not prev.shield
        state.dash_pressed = state.dash and not prev.dash
        state.pause_pressed = state.pause and not prev.pause
        state.accept_pressed = state.accept and not prev.accept
        state.back_pressed = state.back and not prev.back
        state.menu_up_pressed = state.menu_up and not prev.menu_up
        state.menu_down_pressed = state.menu_down and not prev.menu_down

        self.input_state = state
        self._post_controller_events(prev_c_state, c_state)
        self._prev_controller_state = c_state
        # Detect active controller input
        if (
            c_state.pause
            or c_state.accept
            or c_state.back
            or abs(c_state.move_axis) > 0.35
            or abs(c_state.vertical_axis) > 0.35
        ):
            self.last_input_device = "controller"

    def apply_window_mode(self, mode: Optional[str] = None) -> None:
        requested = str(mode if mode is not None else self.settings["window_mode"]).lower()
        normalized = requested if requested in WINDOW_MODES else "windowed"
        if requested != normalized:
            try:
                self.settings.set("window_mode", normalized)
            except Exception:
                pass

        flag_options = {
            "windowed": 0,
            "borderless": pygame.NOFRAME | pygame.RESIZABLE,
            "fullscreen": pygame.FULLSCREEN,
        }

        flags = flag_options.get(normalized, 0)

        try:
            self.screen = pygame.display.set_mode(SCREEN_SIZE, flags)
        except pygame.error as exc:
            print(f"[Display] Failed to apply '{normalized}' mode ({exc}). Falling back to windowed.")
            normalized = "windowed"
            self.screen = pygame.display.set_mode(SCREEN_SIZE)
            try:
                self.settings.set("window_mode", normalized)
            except Exception:
                pass
        pygame.display.set_caption(TITLE)
        icon = self.assets.icon()
        if icon:
            pygame.display.set_icon(icon)
        self.window_mode = normalized

    def quit(self) -> None:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.sound.stop_all()
        self.running = False

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._poll_controller()
            re_poll = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                    break
                if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                    self._refresh_gamepads()
                    re_poll = True
                    continue
                # Suppress ESC KEYDOWN events that occur right after the console was closed
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if getattr(self, "_suppress_escape_until", 0.0) > time.time():
                        # drop this ESC event
                        continue
                if event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN):
                    # Suppress accept/back inputs right after scene changes
                    if getattr(self, "_suppress_accept_until", 0.0) > time.time():
                        continue
                if event.type in (pygame.KEYDOWN, pygame.KEYUP):
                    self.last_input_device = "keyboard"
                elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYAXISMOTION, pygame.JOYHATMOTION):
                    self.last_input_device = "controller"
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                    self.last_input_device = "mouse"
                if self.dev_console and self.dev_console.active:
                    self.dev_console.handle_event(event)
                else:
                    self.scene.handle_event(event)
                if not self.running:
                    break

            if not self.running:
                break


            # DevConsole disabled: only update and draw scene
            if re_poll:
                self._poll_controller()
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def start_speedrun(self) -> None:
        self.speedrun_active = True
        self.speedrun_start = time.time()
        self.speedrun_pause_accum = 0.0
        self.speedrun_paused = False
        self.speedrun_pause_start = 0.0

    def stop_speedrun(self) -> None:
        self.speedrun_active = False
        self.speedrun_paused = False
        self.speedrun_pause_start = 0.0
        self.speedrun_pause_accum = 0.0

    def pause_speedrun(self, pause: bool) -> None:
        if not self.speedrun_active:
            return
        if pause and not self.speedrun_paused:
            self.speedrun_paused = True
            self.speedrun_pause_start = time.time()
        elif not pause and self.speedrun_paused:
            self.speedrun_pause_accum += time.time() - self.speedrun_pause_start
            self.speedrun_pause_start = 0.0
            self.speedrun_paused = False

    def speedrun_time(self) -> float:
        if not self.speedrun_active:
            return 0.0
        elapsed = time.time() - self.speedrun_start - self.speedrun_pause_accum
        if self.speedrun_paused:
            elapsed -= time.time() - self.speedrun_pause_start
        return max(0.0, elapsed)

    def play_music(self, track: str, loop: int = -1, start: float = 0.0) -> None:
        if not self.settings["music"]:
            self.stop_music()
            return

        path = Path(track)
        if not path.is_absolute():
            path = MUSIC_DIR / track
        if self.current_music == path and pygame.mixer.music.get_busy():
            return
        if not path.exists():
            print(f"[Music] Missing track: {path}")
            return
        # Only allow .mp3 for music
        if not str(path).lower().endswith(".mp3"):
            print(f"[Music] Refusing to play non-mp3 music: {path}")
            return
        try:
            pygame.mixer.music.load(str(path))
            # Use start argument if supported (pygame 2.0+)
            try:
                pygame.mixer.music.play(loop, start)
            except TypeError:
                pygame.mixer.music.play(loop)
            self.current_music = path
            self._last_music = path
            self._music_resume_pos = 0.0
        except Exception as exc:
            print(f"[Music] Failed to play {path}: {exc}")
            self.current_music = None

    def stop_music(self) -> None:
        try:
            # Save current position before stopping
            if pygame.mixer.music.get_busy():
                self._music_resume_pos = pygame.mixer.music.get_pos() / 1000.0
            else:
                self._music_resume_pos = 0.0
            pygame.mixer.music.stop()
        except Exception:
            pass
        if self.current_music is not None:
            self._last_music = self.current_music
        self.current_music = None


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
