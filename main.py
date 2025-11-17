#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pygame
import sys

# Import your game files
from game import Game as TwoPlayerGame
from game2 import Game as SinglePlayerGame

pygame.init()

WIDTH, HEIGHT = 900, 600
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Treasure Hunt - Main Menu")
FONT_TITLE = pygame.font.SysFont("arial", 52, bold=True)
FONT_BTN = pygame.font.SysFont("arial", 32)
FONT_TEXT = pygame.font.SysFont("arial", 24)

BG_COLOR = (8, 20, 45)
BTN_COLOR = (40, 120, 200)
BTN_HOVER = (80, 160, 240)
TEXT_COLOR = (230, 240, 250)

clock = pygame.time.Clock()
bgm = pygame.mixer.Sound('sounds/bgm.mp3')
bgm.set_volume(0.19)
bgm.play(-1)

bg_img = pygame.image.load("assets/background.png").convert()

def draw_button(text, rect, mouse_pos):
    x, y, w, h = rect
    if x <= mouse_pos[0] <= x + w and y <= mouse_pos[1] <= y + h:
        color = BTN_HOVER
    else:
        color = BTN_COLOR
    pygame.draw.rect(SCREEN, color, rect, border_radius=12)
    label = FONT_BTN.render(text, True, (255, 255, 255))
    SCREEN.blit(label, (x + (w - label.get_width()) // 2,
                        y + (h - label.get_height()) // 2))
    return rect


def how_to_play_screen():
    """Simple 'How to Play' screen; press ESC or click Back to return."""
    running = True
    back_rect = pygame.Rect(WIDTH // 2 - 80, HEIGHT - 100, 160, 50)

    lines = [
        "Treasure Hunt Rules:",
        "",
        "- Drag from the ship and release to flick.",
        "- Collect the treasure and bring it to your base.",
        "- Items:",
        "    +1: Extra Turn",
        "    Ice cube: Freeze your ship",
        "    Whirlpool: Random redirect",
        "",
        "Press ESC or click BACK to go back."
    ]

    while running:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if back_rect.collidepoint(event.pos):
                    running = False

        SCREEN.fill(BG_COLOR)

        title = FONT_TITLE.render("How to Play", True, TEXT_COLOR)
        SCREEN.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))

        y = 130
        for line in lines:
            label = FONT_TEXT.render(line, True, TEXT_COLOR)
            SCREEN.blit(label, (80, y))
            y += 30

        mouse_pos = pygame.mouse.get_pos()
        draw_button("BACK", back_rect, mouse_pos)

        pygame.display.flip()


def choose_mode_popup():
    """Popup: choose 1P or 2P when Start is clicked."""
    popup_w, popup_h = 400, 260
    popup_x = (WIDTH - popup_w) // 2
    popup_y = (HEIGHT - popup_h) // 2
    popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)

    btn_1p = pygame.Rect(popup_x + 50, popup_y + 80, 300, 50)
    btn_2p = pygame.Rect(popup_x + 50, popup_y + 150, 300, 50)

    choosing = True
    while choosing:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                choosing = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if btn_1p.collidepoint(mx, my):
                    # Single player (vs AI BLUE)
                    game = SinglePlayerGame()
                    game.run()   # When game closes, program ends (SystemExit from game)
                elif btn_2p.collidepoint(mx, my):
                    # Two player local
                    game = TwoPlayerGame()
                    game.run()

        # Draw dark overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        SCREEN.blit(bg_img, (0, 0))

        # Popup box
        pygame.draw.rect(SCREEN, (30, 50, 90), popup_rect, border_radius=16)
        pygame.draw.rect(SCREEN, (120, 150, 210), popup_rect, 3, border_radius=16)

        title = FONT_TITLE.render("Select Mode", True, TEXT_COLOR)
        SCREEN.blit(title, (popup_x + (popup_w - title.get_width()) // 2,
                            popup_y + 20))

        mouse_pos = pygame.mouse.get_pos()
        draw_button("1 Player (vs AI BLUE)", btn_1p, mouse_pos)
        draw_button("2 Players (Local)", btn_2p, mouse_pos)

        pygame.display.flip()


def main_menu():
    start_rect = pygame.Rect(WIDTH // 2 - 140, 230, 280, 60)
    howto_rect = pygame.Rect(WIDTH // 2 - 140, 320, 280, 60)
    quit_rect = pygame.Rect(WIDTH // 2 - 140, 410, 280, 60)

    while True:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if start_rect.collidepoint(mx, my):
                    choose_mode_popup()
                    # NOTE: when the game runs and quits, the whole program ends.
                    # If you want to return here after a game, we can later adjust game.py/game2.py
                elif howto_rect.collidepoint(mx, my):
                    how_to_play_screen()
                elif quit_rect.collidepoint(mx, my):
                    pygame.quit()
                    sys.exit()

        SCREEN.blit(bg_img, (0, 0))

        title = FONT_TITLE.render("Treasure Hunt", True, TEXT_COLOR)
        SCREEN.blit(title, (WIDTH // 2 - title.get_width() // 2, 120))

        subtitle = FONT_TEXT.render("Pick a mode and start hunting!", True, TEXT_COLOR)
        SCREEN.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 180))

        mouse_pos = pygame.mouse.get_pos()
        draw_button("START", start_rect, mouse_pos)
        draw_button("HOW TO PLAY", howto_rect, mouse_pos)
        draw_button("QUIT", quit_rect, mouse_pos)

        pygame.display.flip()


if __name__ == "__main__":
    main_menu()
