#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pygame
import random
import math
import os
import json
from dataclasses import dataclass

# ---------------------------
# CONFIG
# ---------------------------
GRID_ROWS = 5
GRID_COLS = 9
CELL = 90
MARGIN = 40
WIDTH = GRID_COLS * CELL + MARGIN * 2 #1700
HEIGHT = GRID_ROWS * CELL + MARGIN * 2 #980
FPS = 120

TREASURES_PER_ROUND = 1
ROUNDS_TO_WIN = 2

FRICTION = 0.985
MIN_SPEED = 0.35
MAX_SHOT_POWER = 16.0
STEAL_DISTANCE = 33

# Colors
BG = (8, 20, 45)
GRID = (22, 50, 95)
TREASURE_COLOR = (255, 215, 0)
P1_COLOR = (230, 90, 80)
P2_COLOR = (90, 180, 230)
BASE1_COLOR = (180, 40, 40)
BASE2_COLOR = (40, 140, 180)
TEXT = (230, 240, 250)
OBSTACLE_C = (120, 160, 200)

MAP_FOLDER = "maps"  # folder where pre-made maps are stored



# ---------------------------
# Helpers
# ---------------------------
def grid_to_px(r, c):
    return (MARGIN + c * CELL + CELL // 2, MARGIN + r * CELL + CELL // 2)

def length(vx, vy):
    return math.hypot(vx, vy)

# ---------------------------
# Entities
# ---------------------------
@dataclass
class Treasure:
    row: int
    col: int
    r: int = 8  
    carried_by: int | None = None
    def pos(self):
        return grid_to_px(self.row, self.col)

@dataclass
class Base:
    owner: int
    rect: pygame.Rect

class Coin:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = self.vy = 0.0
        self.r = 14
        self.color = color
        self.carrying: Treasure | None = None
        self.resting = True

        

    def draw(self, surf):
        img = self.red_img if self.color == P1_COLOR else self.blue_img
        rect = img.get_rect(center=(int(self.x), int(self.y)))
        surf.blit(img, rect)



    def update(self, obstacles):
        if abs(self.vx) < MIN_SPEED and abs(self.vy) < MIN_SPEED:
            self.vx = self.vy = 0.0
            self.resting = True
            return
        self.resting = False
        self.x += self.vx
        self.y += self.vy
        self.vx *= FRICTION
        self.vy *= FRICTION

        # Wall bounce
        if self.x - self.r < MARGIN:
            self.x = MARGIN + self.r; self.vx *= -0.7
        if self.x + self.r > WIDTH - MARGIN:
            self.x = WIDTH - MARGIN - self.r; self.vx *= -0.7
        if self.y - self.r < MARGIN:
            self.y = MARGIN + self.r; self.vy *= -0.7
        if self.y + self.r > HEIGHT - MARGIN:
            self.y = HEIGHT - MARGIN - self.r; self.vy *= -0.7

        # Obstacle bounce
        for rect in obstacles:
            if rect.collidepoint(self.x, self.y):
                dx_left = abs((rect.left) - (self.x + self.r))
                dx_right = abs((rect.right) - (self.x - self.r))
                dy_top = abs((rect.top) - (self.y + self.r))
                dy_bottom = abs((rect.bottom) - (self.y - self.r))
                m = min(dx_left, dx_right, dy_top, dy_bottom)
                if m == dx_left:
                    self.x = rect.left - self.r; self.vx *= -0.7
                elif m == dx_right:
                    self.x = rect.right + self.r; self.vx *= -0.7
                elif m == dy_top:
                    self.y = rect.top - self.r; self.vy *= -0.7
                else:
                    self.y = rect.bottom + self.r; self.vy *= -0.7

# Item Class
@dataclass
class item_ExtraTurn:
    row: int
    col: int
    carried_by: int | None = None

    def pos(self):
        return grid_to_px(self.row, self.col)

    def draw(self, surf):
        x, y = self.pos()
        pygame.draw.circle(surf, (0, 255, 0), (int(x), int(y)), 8)  # Green item
        pygame.draw.circle(surf, (0, 200, 0), (int(x), int(y)), 8, 2)  # Outline

@dataclass
class item_StopCoin:
    row: int
    col: int
    carried_by: int | None = None

    def pos(self):
        return grid_to_px(self.row, self.col)

    def draw(self, surf):
        x, y = self.pos()
        pygame.draw.circle(surf, (255, 0, 186), (int(x), int(y)), 8)  # Green item
        pygame.draw.circle(surf, (164, 4, 121), (int(x), int(y)), 8, 2)  # Outline

@dataclass
class item_ReDirect:
    row: int
    col: int
    carried_by: int | None = None

    def pos(self):
        return grid_to_px(self.row, self.col)

    def draw(self, surf):
        x, y = self.pos()
        pygame.draw.circle(surf, (0, 255, 251), (int(x), int(y)), 8)  # Green item
        pygame.draw.circle(surf, (0, 154, 152), (int(x), int(y)), 8, 2)  # Outline

# ---------------------------
# Game
# ---------------------------
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Treasure Flick (Best of 3)")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 22)
        self.bigfont = pygame.font.SysFont("arial", 36, bold=True)

        self.bg_img = pygame.image.load("assets/background.png").convert()
        self.bg_img = pygame.transform.scale(self.bg_img, (WIDTH, HEIGHT))

        self.coin_red_img = pygame.image.load("assets/coin_red.png").convert_alpha()
        self.coin_blue_img = pygame.image.load("assets/coin_blue.png").convert_alpha()
        self.treasure_img = pygame.image.load("assets/treasure.png").convert_alpha()
        self.ExtraTurn_img = pygame.image.load("assets/ExtraTurn.png").convert_alpha()
        #self.wall_img = pygame.image.load("assets/wall.png").convert_alpha()

        base_h = 3 * CELL
        base_y = MARGIN + (GRID_ROWS * CELL - base_h)//2
        left_rect = pygame.Rect(MARGIN, base_y, CELL, base_h)
        right_rect = pygame.Rect(WIDTH - MARGIN - CELL, base_y, CELL, base_h)
        self.bases = [Base(0, left_rect), Base(1, right_rect)]

        p1_start = (MARGIN + 20, HEIGHT // 2)
        p2_start = (WIDTH - MARGIN - 20, HEIGHT // 2)
        self.coins = [Coin(*p1_start, P1_COLOR), Coin(*p2_start, P2_COLOR)]
        
        for c in self.coins:
            c.red_img = self.coin_red_img
            c.blue_img = self.coin_blue_img


        self.match_wins = [0, 0]
        self.turn = 0
        self.extra_turn = False
        self.awaiting_switch = False
        self.dragging = False
        self.drag_start = (0, 0)
        self.treasures: list[Treasure] = []
        self.match_over = False
        self.message = "Flip: P1 starts!"
        self.randomDirect = True

        # Initialize first map
        self.obstacles = self.load_random_map()

        # Spawn item
        self.item_Extraturn = None
        self.item_StopCoin = None
        self.item_ReDirect = None
        
        

        self.start_round(starting_player=0)

    # ---------------------------
    def load_random_map(self):
        """Load a random map from /maps folder or use default if missing."""
        map_files = [f for f in os.listdir(MAP_FOLDER)
                     if f.endswith(".json")] if os.path.exists(MAP_FOLDER) else []
        if map_files:
            chosen = random.choice(map_files)
            #chosen = "map2.json"
            path = os.path.join(MAP_FOLDER, chosen)
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    rects = []
                    for r in data.get("obstacles", []):
                        if len(r) == 4:
                            rects.append(pygame.Rect(r))
                    print(f"Loaded map: {chosen}")
                    return rects
            except Exception as e:
                print(f"Failed to load map {chosen}: {e}")

        # Default fallback layout
        rects = []
        cols = [2, 4, 6]
        for c in cols:
            x = MARGIN + c * CELL + CELL // 2 - 8
            y = MARGIN + CELL // 2
            rects.append(pygame.Rect(x, y, 16, CELL * 3))
        rects.append(pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2 - 10, 160, 20))

        return rects

    

    def _cell_center_blocked(self, r, c):
        x, y = grid_to_px(r, c)
        return any(rect.collidepoint(x, y) for rect in self.obstacles)

    # Item---------------------------------------


    def spawn_item_Extraturn(self):
        green_area = [(r, c) for r in range(0, 5) for c in range(2, 7)]
        green_area = [(r, c) for (r, c) in green_area if not self._cell_center_blocked(r, c)]
        if not green_area:
            return

        max_attempts = 100  # safety guard to avoid infinite loop
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            r, c = random.choice(green_area)
            x, y = grid_to_px(r, c)

            # --- Check 1: overlap with treasures ---
            too_close_to_treasure = any(
                length(x - t.pos()[0], y - t.pos()[1]) <= (t.r + 16) for t in self.treasures
            )

            # --- Check 2: overlap with StopCoin item ---
            too_close_to_stop = (
                self.item_StopCoin and length(x - self.item_StopCoin.pos()[0], y - self.item_StopCoin.pos()[1]) <= 16
            )

            # --- Check 3: overlap with ReDirect item ---
            too_close_to_stop = (
                self.item_ReDirect and length(x - self.item_ReDirect.pos()[0], y - self.item_ReDirect.pos()[1]) <= 16
            )

            # If everything passes, spawn the item
            if not (too_close_to_treasure):
                self.item_Extraturn = item_ExtraTurn(r, c)
                return

    def spawn_item_StopCoin(self):
        
        green_area = [(r, c) for r in range(0, 5) for c in range(2, 7)]
        green_area = [(r, c) for (r, c) in green_area if not self._cell_center_blocked(r, c)]
        if not green_area:
            return

        max_attempts = 100  # safety guard to avoid infinite loop
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            r, c = random.choice(green_area)
            x, y = grid_to_px(r, c)

            # --- Check 1: overlap with treasures ---
            too_close_to_treasure = any(
                length(x - t.pos()[0], y - t.pos()[1]) <= (t.r + 16) for t in self.treasures
            )

            # --- Check 2: overlap with ExtraTurn item ---
            too_close_to_extra = (
                self.item_Extraturn and length(x - self.item_Extraturn.pos()[0], y - self.item_Extraturn.pos()[1]) <= 16
            )

            # --- Check 3: overlap with ReDirect item ---
            too_close_to_stop = (
                self.item_ReDirect and length(x - self.item_ReDirect.pos()[0], y - self.item_ReDirect.pos()[1]) <= 16
            )

            # If everything passes, spawn the item
            if not (too_close_to_treasure or too_close_to_extra):
                self.item_StopCoin = item_StopCoin(r, c)
                return

    def spawn_item_ReDirect(self):
        """Spawn item_ReDirect in green area, ensuring it doesn't overlap with treasures or other items."""
        green_area = [(r, c) for r in range(0, 5) for c in range(2, 7)]
        green_area = [(r, c) for (r, c) in green_area if not self._cell_center_blocked(r, c)]
        if not green_area:
            return

        max_attempts = 100  # safety guard to avoid infinite loop
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            r, c = random.choice(green_area)
            x, y = grid_to_px(r, c)

            # --- Check 1: overlap with treasures ---
            too_close_to_treasure = any(
                length(x - t.pos()[0], y - t.pos()[1]) <= (t.r + 16) for t in self.treasures
            )

            # --- Check 2: overlap with ExtraTurn item ---
            too_close_to_extra = (
                self.item_Extraturn and length(x - self.item_Extraturn.pos()[0], y - self.item_Extraturn.pos()[1]) <= 16
            )

            # --- Check 3: overlap with StopCoin item ---
            too_close_to_stop = (
                self.item_StopCoin and length(x - self.item_StopCoin.pos()[0], y - self.item_StopCoin.pos()[1]) <= 16
            )

            # If everything passes, spawn the item
            if not (too_close_to_treasure or too_close_to_extra or too_close_to_stop):
                self.item_ReDirect = item_ReDirect(r, c)
                return

    # ---------------------------
    def start_round(self, starting_player=0):
        self.turn = starting_player
        self.message = f"Round start: Player {self.turn+1}'s turn"
        self.awaiting_switch = False
        self.extra_turn = False
        

        # Reset coins
        self.coins[0].x, self.coins[0].y = MARGIN + 20, HEIGHT // 2
        self.coins[1].x, self.coins[1].y = WIDTH - MARGIN - 20, HEIGHT // 2
        for c in self.coins:
            c.vx = c.vy = 0
            c.resting = True
            c.carrying = None

        

        # Spawn treasure
        candidate_cells = [(r, c) for r in range(1, 4) for c in range(3, 6)]
        candidate_cells = [(r, c) for (r, c) in candidate_cells if not self._cell_center_blocked(r, c)]
        self.treasures = []
        if candidate_cells:
            r, c = random.choice(candidate_cells)
            self.treasures.append(Treasure(row=r, col=c, carried_by=None))

        # Spawn items
        self.spawn_item_Extraturn()
        self.spawn_item_StopCoin()
        self.spawn_item_ReDirect()


       

    # ---------------------------
    def any_moving(self):
        return any(abs(c.vx) > 0.0 or abs(c.vy) > 0.0 for c in self.coins)

    def other(self, p): return 1 - p

    def handle_shot_input(self, events):
        if self.awaiting_switch or self.match_over: return
        coin = self.coins[self.turn]
        if not coin.resting: return
        mouse = pygame.mouse.get_pos()
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if length(mouse[0]-coin.x, mouse[1]-coin.y) <= coin.r+10:
                    self.dragging = True; self.drag_start = mouse
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.dragging:
                self.dragging = False
                dx, dy = mouse[0]-self.drag_start[0], mouse[1]-self.drag_start[1]
                vx, vy = -dx/10.0, -dy/10.0
                speed = length(vx, vy)
                if speed > 0.1:
                    scale = min(1.0, MAX_SHOT_POWER / speed)
                    coin.vx = vx * scale
                    coin.vy = vy * scale
                    coin.resting = False
                    self.awaiting_switch = True
                    self.message = f"P{self.turn+1} shot!"
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE and coin.resting:
                coin.vx = random.uniform(5, 7) * (1 if self.turn == 0 else -1)
                coin.vy = random.uniform(-2, 2)
                coin.resting = False
                self.awaiting_switch = True
                self.message = f"P{self.turn+1} shot!"

    # ---------------------------
    def resolve_coin_collision(self, a, b):
        dx, dy = b.x - a.x, b.y - a.y
        dist = math.hypot(dx, dy)
        min_dist = a.r + b.r
        if dist == 0 or dist >= min_dist: return
        nx, ny = dx/dist, dy/dist
        overlap = min_dist - dist
        a.x -= nx*overlap*0.5; a.y -= ny*overlap*0.5
        b.x += nx*overlap*0.5; b.y += ny*overlap*0.5
        rvx, rvy = b.vx - a.vx, b.vy - a.vy
        vel_along_normal = rvx*nx + rvy*ny
        if vel_along_normal > 0: return
        restitution = 0.7
        j = -(1 + restitution)*vel_along_normal/2
        impulse_x, impulse_y = j*nx, j*ny
        a.vx -= impulse_x; a.vy -= impulse_y
        b.vx += impulse_x; b.vy += impulse_y

    # ---------------------------
    def update_logic(self):
        if self.match_over: 
        
            return
        for c in self.coins: c.update(self.obstacles)
        self.resolve_coin_collision(self.coins[0], self.coins[1])
        

        # Pickup
        for i, c in enumerate(self.coins):
            if c.carrying is None:
                for t in self.treasures:
                    if t.carried_by is None:
                        tx, ty = t.pos()
                        if length(c.x - tx, c.y - ty) <= c.r + 12:
                            c.carrying = t; t.carried_by = i
                            self.extra_turn = True
                            self.message = f"P{i+1} picked treasure! (+extra turn)"
                            break

        # Check for item pickup
        if self.item_Extraturn:
            for i, c in enumerate(self.coins):
                if c.carrying is None:
                    item_x, item_y = self.item_Extraturn.pos()
                    if length(c.x - item_x, c.y - item_y) <= c.r + 12:
                        self.item_Extraturn = None  # Remove the item from the map
                        self.extra_turn = True
                        self.message = f"P{i+1} picked up the item! (+extra turn)"
                        break

        if self.item_StopCoin:
            for i, c in enumerate(self.coins):
                if c.carrying is None:
                    item_x, item_y = self.item_StopCoin.pos()
                    if length(c.x - item_x, c.y - item_y) <= c.r + 12:
                        self.item_StopCoin = None  # Remove the item from the map
                        c.vx = 0  # Set the velocity in the x direction to 0
                        c.vy = 0  # Set the velocity in the y direction to 0
                        c.resting = True
                        self.message = f"P{i+1} picked up the item! (+stop moving)"
                        break

        if self.item_ReDirect:
            for i, c in enumerate(self.coins):
                if c.carrying is None:
                    item_x, item_y = self.item_ReDirect.pos()
                    if length(c.x - item_x, c.y - item_y) <= c.r + 12:
                        self.item_ReDirect = None  # Remove the item from the map
                        c.vx = random.uniform(5, 7) * (1 if self.turn == 0 else -1)
                        c.vy = random.uniform(-2, 2)
                        c.resting = True
                        self.message = f"P{i+1} picked up the item! (+re directing)"
                        break

        # Steal
        attacker = self.coins[self.turn]
        defender = self.coins[self.other(self.turn)]
        if length(attacker.x - defender.x, attacker.y - defender.y) <= STEAL_DISTANCE:
            if attacker.carrying is None and defender.carrying is not None:
                attacker.carrying, defender.carrying = defender.carrying, None
                if attacker.carrying: attacker.carrying.carried_by = self.turn
                self.extra_turn = True
                self.message = f"P{self.turn+1} stole! (+extra turn)"

        

        # Scoring
        for i, c in enumerate(self.coins):
            if c.carrying is not None and self.bases[i].rect.collidepoint(c.x, c.y):
                self.match_wins[i] += 1
                self.message = f"P{i+1} scored! Match {self.match_wins[0]}-{self.match_wins[1]}"
                if c.carrying in self.treasures: self.treasures.remove(c.carrying)
                c.carrying = None
                if self.match_wins[i] >= ROUNDS_TO_WIN:
                    self.match_over = True
                    self.awaiting_switch = False
                    self.message = f"P{i+1} WINS THE MATCH! Press R to restart."
                else: self.start_round(starting_player=self.other(i))

                return



        # Turn switch
        if not self.any_moving() and self.awaiting_switch and not self.dragging:
            if self.extra_turn:
                self.extra_turn = False
                self.message = f"P{self.turn+1} extra turn!"
            else:
                self.turn = self.other(self.turn)
                self.message = f"Turn: Player {self.turn+1}"
            self.awaiting_switch = False

    # ---------------------------
    def draw(self):
        self.screen.blit(self.bg_img, (0, 0))
        self.draw_grid(self.screen)
        self.draw_bases(self.screen)
        for r in self.obstacles:
            pygame.draw.rect(self.screen, OBSTACLE_C, r, border_radius=6)
        self.draw_treasures(self.screen)
        if self.item_Extraturn:
            self.item_Extraturn.draw(self.screen)  # Draw the item
        if self.item_StopCoin:
            self.item_StopCoin.draw(self.screen)
        if self.item_ReDirect:
            self.item_ReDirect.draw(self.screen)
        for c in self.coins: c.draw(self.screen)
        if self.dragging:
            coin = self.coins[self.turn]
            mouse = pygame.mouse.get_pos()
            pygame.draw.line(self.screen, (255,255,255), (int(coin.x), int(coin.y)), mouse, 2)
        self.draw_hud(self.screen)
        pygame.display.flip()

    def draw_grid(self, surf):
        for r in range(GRID_ROWS + 1):
            y = MARGIN + r * CELL
            pygame.draw.line(surf, GRID, (MARGIN, y), (WIDTH - MARGIN, y), 2)
        for c in range(GRID_COLS + 1):
            x = MARGIN + c * CELL
            pygame.draw.line(surf, GRID, (x, MARGIN), (x, HEIGHT - MARGIN), 2)

    def draw_bases(self, surf):
        pygame.draw.rect(surf, BASE1_COLOR, self.bases[0].rect, border_radius=10)
        pygame.draw.rect(surf, BASE2_COLOR, self.bases[1].rect, border_radius=10)

    def draw_treasures(self, surf):
        for t in self.treasures:
            if t.carried_by is None:
                x, y = t.pos()
            else:
                c = self.coins[t.carried_by]
                x, y = c.x, c.y
            rect = self.treasure_img.get_rect(center=(int(x), int(y)))
            surf.blit(self.treasure_img, rect)


    def draw_hud(self, surf):
        txt = f"Match Wins P1:{self.match_wins[0]} P2:{self.match_wins[1]} (Best of 3)"
        surf.blit(self.font.render(txt, True, TEXT), (MARGIN, 8))
        t = self.font.render(f"Turn: Player {self.turn+1}", True, TEXT)
        surf.blit(t, (WIDTH - t.get_width() - MARGIN, 8))
        m = self.font.render(self.message, True, TEXT)
        surf.blit(m, (MARGIN, HEIGHT - m.get_height() - 8))
        help1 = self.font.render("Drag to flick. SPACE=nudge. R=reset. ESC=quit.", True, (200,210,230))
        surf.blit(help1, (MARGIN, HEIGHT - m.get_height() - 34))

    def handle_global_keys(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                self.match_wins = [0, 0]
                self.match_over = False
                self.obstacles = self.load_random_map()
                self.start_round(starting_player=random.choice([0, 1]))
            elif e.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            elif e.key == pygame.K_m:
                pygame.quit()                       
                os.system("python main.py")      
                raise SystemExit 

    def run(self):
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    pygame.quit(); raise SystemExit
                self.handle_global_keys(e)
            self.handle_shot_input(events)
            self.update_logic()
            self.draw()

# ---------------------------
if __name__ == "__main__":
    Game().run()
