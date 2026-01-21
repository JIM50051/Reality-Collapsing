import pygame
from shared import WHITE

DEFAULT_FONT = "Consolas"
SCREEN_SIZE = (1280, 800)

def show_seizure_warning(screen, duration=3.5):
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(DEFAULT_FONT, 48, bold=True)
    small_font = pygame.font.SysFont(DEFAULT_FONT, 28)
    warning_text = "SEIZURE WARNING"
    info_text = "This game contains flashing lights and patterns that may trigger seizures."
    continue_text = "Press any key to continue..."
    start_time = pygame.time.get_ticks()
    shown_continue = False
    while True:
        screen.fill((0, 0, 0))
        text_surface = font.render(warning_text, True, (255, 0, 0))
        info_surface = small_font.render(info_text, True, WHITE)
        cont_surface = small_font.render(continue_text, True, WHITE)
        screen.blit(text_surface, (SCREEN_SIZE[0]//2 - text_surface.get_width()//2, SCREEN_SIZE[1]//2 - 100))
        screen.blit(info_surface, (SCREEN_SIZE[0]//2 - info_surface.get_width()//2, SCREEN_SIZE[1]//2))
        if shown_continue:
            screen.blit(cont_surface, (SCREEN_SIZE[0]//2 - cont_surface.get_width()//2, SCREEN_SIZE[1]//2 + 80))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if shown_continue and (event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN):
                return
        if not shown_continue and (pygame.time.get_ticks() - start_time) > duration * 1000:
            shown_continue = True
        clock.tick(60)
