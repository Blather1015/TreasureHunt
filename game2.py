#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pygame
import random
import math
import os
import json
from dataclasses import dataclass

pygame.init()
pygame.mixer.init()

# CONFIG
GRID_ROWS = 5
GRID_COLS = 9
CELL = 90
MARGIN = 40

# Increased HEIGHT to make room for UI at the bottom
WIDTH = GRID_COLS * CELL + MARGIN * 2
HEIGHT = GRID_ROWS * CELL + MARGIN * 2 + 50 
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
TEXT = (230, 240, 250)

P1_COLOR = (230, 90, 80)
P2_COLOR = (90, 180, 230)

MAP_FOLDER = "maps"

# sounds
try:
    itemsound = pygame.mixer.Sound("sounds/itemcollect.mp3")
    bouncesound = pygame.mixer.Sound("sounds/bounce.mp3")
    FreezeItemSound = pygame.mixer.Sound("sounds/freeze.mp3")
    whirlpoolItemSound = pygame.mixer.Sound("sounds/whirlpool.mp3")
    getTreasureSound = pygame.mixer.Sound("sounds/treasure.mp3")
except:
    itemsound = pygame.mixer.Sound(buffer=bytearray())
    bouncesound = pygame.mixer.Sound(buffer=bytearray())
    FreezeItemSound = pygame.mixer.Sound(buffer=bytearray())
    whirlpoolItemSound = pygame.mixer.Sound(buffer=bytearray())
    getTreasureSound = pygame.mixer.Sound(buffer=bytearray())


# ---------------------------
# Helpers
# ---------------------------
def grid_to_px(r, c):
    return (MARGIN + c * CELL + CELL // 2, MARGIN + r * CELL + CELL // 2)

def length(vx, vy):
    return math.hypot(vx, vy)

def dist_point_to_segment(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return length(px - x1, py - y1)

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return length(px - proj_x, py - proj_y)

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
    def __init__(self, x, y, color, red_img, blue_img):
        self.x = x
        self.y = y
        self.vx = self.vy = 0.0
        self.r = 14
        self.color = color
        self.carrying: Treasure | None = None
        self.resting = True
        self.red_img = red_img
        self.blue_img = blue_img

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
        map_bottom = GRID_ROWS * CELL + MARGIN

        if self.x - self.r < MARGIN:
            self.x = MARGIN + self.r
            self.vx *= -0.7
            bouncesound.play()
        if self.x + self.r > WIDTH - MARGIN:
            self.x = WIDTH - MARGIN - self.r
            self.vx *= -0.7
            bouncesound.play()
        if self.y - self.r < MARGIN:
            self.y = MARGIN + self.r
            self.vy *= -0.7
            bouncesound.play()
        if self.y + self.r > map_bottom: 
            self.y = map_bottom - self.r
            self.vy *= -0.7
            bouncesound.play()

        for rect in obstacles:
            if rect.collidepoint(self.x, self.y):
                dx_left = abs((rect.left) - (self.x + self.r))
                dx_right = abs((rect.right) - (self.x - self.r))
                dy_top = abs((rect.top) - (self.y + self.r))
                dy_bottom = abs((rect.bottom) - (self.y - self.r))
                m = min(dx_left, dx_right, dy_top, dy_bottom)
                if m == dx_left:
                    self.x = rect.left - self.r
                    self.vx *= -0.7
                    bouncesound.play()
                elif m == dx_right:
                    self.x = rect.right + self.r
                    self.vx *= -0.7
                    bouncesound.play()
                elif m == dy_top:
                    self.y = rect.top - self.r
                    self.vy *= -0.7
                    bouncesound.play()
                else:
                    self.y = rect.bottom + self.r
                    self.vy *= -0.7
                    bouncesound.play()

# Item Classes
@dataclass
class ItemExtraTurn:
    row: int
    col: int
    image: pygame.Surface
    carried_by: int | None = None
    def pos(self): return grid_to_px(self.row, self.col)
    def draw(self, surf):
        x, y = self.pos()
        rect = self.image.get_rect(center=(int(x), int(y)))
        surf.blit(self.image, rect)

@dataclass
class ItemStopCoin:
    row: int
    col: int
    image: pygame.Surface
    carried_by: int | None = None
    def pos(self): return grid_to_px(self.row, self.col)
    def draw(self, surf):
        x, y = self.pos()
        rect = self.image.get_rect(center=(int(x), int(y)))
        surf.blit(self.image, rect)

@dataclass
class ItemReDirect:
    row: int
    col: int
    image: pygame.Surface
    carried_by: int | None = None
    def pos(self): return grid_to_px(self.row, self.col)
    def draw(self, surf):
        x, y = self.pos()
        rect = self.image.get_rect(center=(int(x), int(y)))
        surf.blit(self.image, rect)

# ---------------------------
# Game
# ---------------------------
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Treasure Hunt")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 22)
        self.bigfont = pygame.font.SysFont("arial", 36, bold=True)

        # --- Load textures ---
        try:
            self.bg_img = pygame.image.load("assets/background.png").convert()
            self.bg_img = pygame.transform.scale(self.bg_img, (WIDTH, HEIGHT))

            coin_red_raw = pygame.image.load("assets/coin_red.png").convert_alpha()
            coin_blue_raw = pygame.image.load("assets/coin_blue.png").convert_alpha()
            self.coin_red_img = pygame.transform.smoothscale(coin_red_raw, (40, 40))
            self.coin_blue_img = pygame.transform.smoothscale(coin_blue_raw, (40, 40))

            treasure_raw = pygame.image.load("assets/treasure.png").convert_alpha()
            self.treasure_img = pygame.transform.smoothscale(treasure_raw, (40, 40))

            extra_raw = pygame.image.load("assets/ExtraTurn.png").convert_alpha()
            stop_raw = pygame.image.load("assets/StopCoin.png").convert_alpha()
            redirect_raw = pygame.image.load("assets/ReDirect.png").convert_alpha()
            self.extra_img = pygame.transform.smoothscale(extra_raw, (40, 40))
            self.stop_img = pygame.transform.smoothscale(stop_raw, (40, 40))
            self.redirect_img = pygame.transform.smoothscale(redirect_raw, (40, 40))

            wall_raw = pygame.image.load("assets/wall.png").convert_alpha()
            self.wall_img = wall_raw
        except FileNotFoundError as e:
            print(f"Error loading assets: {e}")
            self.bg_img = pygame.Surface((WIDTH, HEIGHT)); self.bg_img.fill(BG)
            self.coin_red_img = pygame.Surface((40, 40)); self.coin_red_img.fill(P1_COLOR)
            self.coin_blue_img = pygame.Surface((40, 40)); self.coin_blue_img.fill(P2_COLOR)
            self.treasure_img = pygame.Surface((40, 40)); self.treasure_img.fill((255, 215, 0))
            self.extra_img = pygame.Surface((40, 40)); self.extra_img.fill((0, 255, 0))
            self.stop_img = pygame.Surface((40, 40)); self.stop_img.fill((0, 0, 255))
            self.redirect_img = pygame.Surface((40, 40)); self.redirect_img.fill((128, 0, 128))
            self.wall_img = pygame.Surface((10, 10)); self.wall_img.fill(GRID)

        # --- Bases ---
        base_h = 3 * CELL
        base_y = MARGIN + (GRID_ROWS * CELL - base_h) // 2
        left_rect = pygame.Rect(MARGIN, base_y, CELL, base_h)
        right_rect = pygame.Rect(WIDTH - MARGIN - CELL, base_y, CELL, base_h)
        self.bases = [Base(0, left_rect), Base(1, right_rect)]

        # coins
        p1_start = (MARGIN + 20, (GRID_ROWS * CELL + MARGIN*2)//2)
        p2_start = (WIDTH - MARGIN - 20, (GRID_ROWS * CELL + MARGIN*2)//2)
        self.coins = [
            Coin(*p1_start, P1_COLOR, self.coin_red_img, self.coin_blue_img),
            Coin(*p2_start, P2_COLOR, self.coin_red_img, self.coin_blue_img),
        ]

        self.match_wins = [0, 0]
        self.turn = 0
        self.extra_turn = False
        self.awaiting_switch = False
        self.dragging = False
        self.drag_start = (0, 0)
        self.treasures: list[Treasure] = []
        self.match_over = False
        self.message = "Flip: Player starts!"
        
        # Turn counter for item spawning
        self.total_turns = 0

        # AI state
        self.ai_index = 1
        self.ai_thinking = False
        self.ai_think_until = 0

        self.obstacles = self.load_random_map()

        self.item_Extraturn: ItemExtraTurn | None = None
        self.item_StopCoin: ItemStopCoin | None = None
        self.item_ReDirect: ItemReDirect | None = None

        self.start_round(starting_player=0)

    # ---------------------------
    def load_random_map(self):
        map_files = [f for f in os.listdir(MAP_FOLDER) if f.endswith(".json")] if os.path.exists(MAP_FOLDER) else []
        if map_files:
            chosen = random.choice(map_files)
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

        rects = []
        cols = [2, 4, 6]
        for c in cols:
            x = MARGIN + c * CELL + CELL // 2 - 8
            y = MARGIN + CELL // 2
            rects.append(pygame.Rect(x, y, 16, CELL * 3))
        rects.append(pygame.Rect(WIDTH // 2 - 80, (GRID_ROWS*CELL)//2 + MARGIN - 10, 160, 20))
        return rects

    def _cell_center_blocked(self, r, c):
        x, y = grid_to_px(r, c)
        return any(rect.collidepoint(x, y) for rect in self.obstacles)

    # ---------------------------
    # Spawning
    # ---------------------------
    def spawn_random_item_one_of_three(self):
        """Spawns ONE random item type, if it's not already there."""
        choices = ["extra", "stop", "redirect"]
        choice = random.choice(choices)
        
        if choice == "extra":
            self.spawn_item_Extraturn()
        elif choice == "stop":
            self.spawn_item_StopCoin()
        elif choice == "redirect":
            self.spawn_item_ReDirect()

    def spawn_item_Extraturn(self):
        if self.item_Extraturn is not None: return
        self._try_spawn_item("item_Extraturn", ItemExtraTurn, self.extra_img)

    def spawn_item_StopCoin(self):
        if self.item_StopCoin is not None: return
        self._try_spawn_item("item_StopCoin", ItemStopCoin, self.stop_img)

    def spawn_item_ReDirect(self):
        if self.item_ReDirect is not None: return
        self._try_spawn_item("item_ReDirect", ItemReDirect, self.redirect_img)

    def _try_spawn_item(self, attr_name, cls, img):
        green_area = [(r, c) for r in range(0, 5) for c in range(2, 7)]
        green_area = [(r, c) for (r, c) in green_area if not self._cell_center_blocked(r, c)]
        if not green_area: return

        # Shuffle to try random spots
        random.shuffle(green_area)
        
        for (r, c) in green_area:
            x, y = grid_to_px(r, c)
            
            # Check against treasure
            if any(length(x-t.pos()[0], y-t.pos()[1]) <= t.r+16 for t in self.treasures): continue
            
            # Check against existing items (don't stack on top of ANY existing item)
            valid = True
            existing_items = [self.item_Extraturn, self.item_StopCoin, self.item_ReDirect]
            for item in existing_items:
                if item:
                    ix, iy = item.pos()
                    if length(x - ix, y - iy) < 10: # cell overlap check
                         valid = False
                         break
            
            if valid:
                setattr(self, attr_name, cls(r, c, img))
                return

    def start_round(self, starting_player=0):
        self.turn = starting_player
        self.message = f"Round start: Player {self.turn+1}'s turn"
        self.awaiting_switch = False
        self.extra_turn = False
        self.ai_thinking = False
        self.total_turns = 0  # Reset counter at start of round

        map_mid_y = (GRID_ROWS * CELL + MARGIN * 2) // 2
        self.coins[0].x, self.coins[0].y = MARGIN + 20, map_mid_y
        self.coins[1].x, self.coins[1].y = WIDTH - MARGIN - 20, map_mid_y
        for c in self.coins:
            c.vx = c.vy = 0
            c.resting = True
            c.carrying = None

        candidate_cells = [(r, c) for r in range(1, 4) for c in range(3, 6)]
        candidate_cells = [(r, c) for (r, c) in candidate_cells if not self._cell_center_blocked(r, c)]
        self.treasures = []
        if candidate_cells:
            r, c = random.choice(candidate_cells)
            self.treasures.append(Treasure(row=r, col=c, carried_by=None))

        # Clear all items
        self.item_Extraturn = None
        self.item_StopCoin = None
        self.item_ReDirect = None
        
        # Spawn exactly ONE random item to start (optional, but makes map less empty)
        self.spawn_random_item_one_of_three()

    def any_moving(self):
        return any(abs(c.vx) > 0.0 or abs(c.vy) > 0.0 for c in self.coins)

    def other(self, p):
        return 1 - p

    # ---------------------------
    # Input
    # ---------------------------
    def handle_shot_input(self, events):
        if self.awaiting_switch or self.match_over: return
        if self.turn != 0: return

        coin = self.coins[self.turn]
        if not coin.resting: return

        mouse = pygame.mouse.get_pos()
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if length(mouse[0] - coin.x, mouse[1] - coin.y) <= coin.r + 10:
                    self.dragging = True
                    self.drag_start = mouse
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.dragging:
                self.dragging = False
                dx = mouse[0] - self.drag_start[0]
                dy = mouse[1] - self.drag_start[1]
                vx, vy = -dx / 10.0, -dy / 10.0
                speed = length(vx, vy)
                if speed > 0.1:
                    scale = min(1.0, MAX_SHOT_POWER / speed)
                    coin.vx = vx * scale
                    coin.vy = vy * scale
                    coin.resting = False
                    self.awaiting_switch = True
                    self.message = f"Player shot!"
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE and coin.resting:
                coin.vx = random.uniform(5, 7)
                coin.vy = random.uniform(-2, 2)
                coin.resting = False
                self.awaiting_switch = True
                self.message = f"Player nudge!"

    def resolve_coin_collision(self, a, b):
        dx, dy = b.x - a.x, b.y - a.y
        dist = math.hypot(dx, dy)
        min_dist = a.r + b.r
        if dist == 0 or dist >= min_dist: return
        nx, ny = dx / dist, dy / dist
        overlap = min_dist - dist
        a.x -= nx * overlap * 0.5
        a.y -= ny * overlap * 0.5
        b.x += nx * overlap * 0.5
        b.y += ny * overlap * 0.5
        rvx, rvy = b.vx - a.vx, b.vy - a.vy
        vel_along_normal = rvx * nx + rvy * ny
        if vel_along_normal > 0: return
        j = -(1 + 0.7) * vel_along_normal / 2
        impulse_x, impulse_y = j * nx, j * ny
        a.vx -= impulse_x
        a.vy -= impulse_y
        b.vx += impulse_x
        b.vy += impulse_y

    # ---------------------------
    # AI
    # ---------------------------
    def line_hits_wall(self, x1, y1, x2, y2):
        for rect in self.obstacles:
            if rect.clipline((x1, y1), (x2, y2)): return True
        return False

    def get_closest_blocking_wall(self, x1, y1, x2, y2):
        closest_rect = None
        min_dist = float('inf')
        for rect in self.obstacles:
            clipped = rect.clipline(x1, y1, x2, y2)
            if clipped:
                ix, iy = clipped[0]
                d = math.hypot(ix - x1, iy - y1)
                if d < min_dist:
                    min_dist = d
                    closest_rect = rect
        return closest_rect

    def predict_future_position(self, x, y, vx, vy, frames=40):
        return x + vx * frames, y + vy * frames

    def choose_ai_target(self):
        player = self.coins[0]
        ai_coin = self.coins[1]
        
        # 1) Carry treasure -> Base
        for t in self.treasures:
            if t.carried_by == self.ai_index:
                base = self.bases[self.ai_index].rect
                return base.centerx, base.centery, "score"
        
        # 2) Opponent has treasure -> Attack
        for t in self.treasures:
            if t.carried_by == 0:
                # If close, aim directly. If far, predict.
                dist = length(player.x - ai_coin.x, player.y - ai_coin.y)
                if dist < 150:
                     return player.x, player.y, "attack"
                else:
                     tx, ty = self.predict_future_position(player.x, player.y, player.vx, player.vy)
                     return tx, ty, "attack"

        # 3) Free treasure -> Get it
        free_treasures = [t for t in self.treasures if t.carried_by is None]
        if free_treasures:
            best = None
            best_dist = None
            for t in free_treasures:
                tx, ty = t.pos()
                d = length(ai_coin.x - tx, ai_coin.y - ty)
                if best is None or d < best_dist:
                    best = t
                    best_dist = d
            return best.pos()[0], best.pos()[1], "treasure"
        
        return player.x, player.y, "attack"

    def adjust_target_for_walls(self, sx, sy, tx, ty):
        blocking_rect = self.get_closest_blocking_wall(sx, sy, tx, ty)
        if not blocking_rect:
            return tx, ty, False, length(tx - sx, ty - sy)

        offset = 25 
        r = blocking_rect
        candidates = [
            (r.left - offset, r.top - offset),
            (r.right + offset, r.top - offset),
            (r.left - offset, r.bottom + offset),
            (r.right + offset, r.bottom + offset)
        ]

        best_wx, best_wy = sx, sy
        best_dist_total = float('inf')
        found_path = False
        best_corner_dist = 0

        for (wx, wy) in candidates:
            map_bottom = GRID_ROWS * CELL + MARGIN
            if not (MARGIN < wx < WIDTH - MARGIN and MARGIN < wy < map_bottom):
                continue

            dist_to_corner = math.hypot(wx - sx, wy - sy)
            if dist_to_corner < 1: continue

            check_ratio = (dist_to_corner - 5) / dist_to_corner
            cx = sx + (wx - sx) * check_ratio
            cy = sy + (wy - sy) * check_ratio

            if not self.line_hits_wall(sx, sy, cx, cy):
                dist_corner_to_final = math.hypot(tx - wx, ty - wy)
                total_dist = dist_to_corner + dist_corner_to_final
                
                if total_dist < best_dist_total:
                    best_dist_total = total_dist
                    best_wx, best_wy = wx, wy
                    found_path = True
                    best_corner_dist = dist_to_corner

        if found_path:
            dx = best_wx - sx
            dy = best_wy - sy
            angle = math.atan2(dy, dx)
            project_dist = best_corner_dist + 60 
            final_x = sx + math.cos(angle) * project_dist
            final_y = sy + math.sin(angle) * project_dist
            return final_x, final_y, True, best_corner_dist

        return tx, ty, False, length(tx - sx, ty - sy)

    def scan_for_bad_items(self, sx, sy, tx, ty):
        bad_items = []
        if self.item_StopCoin: bad_items.append(self.item_StopCoin)
        if self.item_ReDirect: bad_items.append(self.item_ReDirect)
        
        for item in bad_items:
            ix, iy = item.pos()
            dist = dist_point_to_segment(ix, iy, sx, sy, tx, ty)
            if dist < 35: 
                return True
        return False

    def adjust_target_to_avoid_bad_items(self, sx, sy, tx, ty):
        if not self.scan_for_bad_items(sx, sy, tx, ty):
            return tx, ty
        
        dx, dy = tx - sx, ty - sy
        angle = math.atan2(dy, dx)
        dist = math.hypot(dx, dy)
        
        offsets = [10, -10, 20, -20, 30, -30]
        for deg in offsets:
            rad = math.radians(deg)
            new_angle = angle + rad
            nx = sx + math.cos(new_angle) * dist
            ny = sy + math.sin(new_angle) * dist
            
            if not self.line_hits_wall(sx, sy, nx, ny) and not self.scan_for_bad_items(sx, sy, nx, ny):
                return nx, ny
        return tx, ty

    def adjust_target_to_avoid_player(self, sx, sy, tx, ty):
        player = self.coins[0]
        px, py = player.x, player.y
        d = dist_point_to_segment(px, py, sx, sy, tx, ty)
        if d > player.r + 8: return tx, ty

        offset = 80
        candidates = [(tx + offset, ty), (tx - offset, ty), (tx, ty + offset), (tx, ty - offset)]
        for cx, cy in candidates:
            dd = dist_point_to_segment(px, py, sx, sy, cx, cy)
            if dd > player.r + 12 and not self.line_hits_wall(sx, sy, cx, cy):
                return cx, cy
        return tx, ty

    def update_ai(self):
        if self.match_over: return
        if self.turn != self.ai_index: 
            self.ai_thinking = False
            return
        if self.awaiting_switch: return

        ai_coin = self.coins[self.ai_index]
        if not ai_coin.resting: return

        now = pygame.time.get_ticks()
        if not self.ai_thinking:
            self.ai_thinking = True
            self.ai_think_until = now + random.randint(1000, 2000)
            self.message = "AI is thinking..."
            return
        if now < self.ai_think_until: return

        self.ai_thinking = False
        target_x, target_y, mode = self.choose_ai_target()

        target_x, target_y, is_corner_shot, dist_to_corner = self.adjust_target_for_walls(
            ai_coin.x, ai_coin.y, target_x, target_y
        )

        if mode == "score":
             if not is_corner_shot and self.line_hits_wall(ai_coin.x, ai_coin.y, target_x, target_y):
                  map_center_x = WIDTH // 2
                  map_center_y = (GRID_ROWS * CELL + MARGIN * 2) // 2
                  target_x, target_y = map_center_x, map_center_y
                  mode = "reposition"

        target_x, target_y = self.adjust_target_to_avoid_bad_items(
            ai_coin.x, ai_coin.y, target_x, target_y
        )

        if mode != "attack":
            target_x, target_y = self.adjust_target_to_avoid_player(ai_coin.x, ai_coin.y, target_x, target_y)

        dx = target_x - ai_coin.x
        dy = target_y - ai_coin.y
        dist_total = length(dx, dy)
        
        power = 0.0
        
        if mode == "reposition":
            power = min(MAX_SHOT_POWER, 10.0)
        elif is_corner_shot:
            base_p = min(MAX_SHOT_POWER, (dist_to_corner / 18.0) + 2.5)
            if mode == "score": power = min(7.0, base_p) 
            elif mode == "attack": power = min(9.0, base_p)
            else: power = base_p
        else:
            if mode == "score":
                power = min(10.0, dist_total / 25.0)
                power = max(power, 4.0) 
            elif mode == "attack":
                power = min(MAX_SHOT_POWER, (dist_total / 12.0) + 3.5)
            else:
                power = min(MAX_SHOT_POWER, dist_total / 15.0)

        if dist_total > 0:
            vx = dx / dist_total * power
            vy = dy / dist_total * power
        else:
            vx = vy = 0

        ai_coin.vx = vx
        ai_coin.vy = vy
        ai_coin.resting = False
        self.awaiting_switch = True

        msgs = {
            "attack": "AI attacks!", 
            "score": "AI goes to base!", 
            "treasure": "AI gets treasure!",
            "reposition": "AI repositions!"
        }
        self.message = msgs.get(mode, "AI moves!")

    # ---------------------------
    def update_logic(self):
        if self.match_over: return

        if self.turn == self.ai_index:
            self.update_ai()

        last_positions = [(c.x, c.y) for c in self.coins]

        for c in self.coins: c.update(self.obstacles)
        self.check_item_pickup(last_positions)
        self.resolve_coin_collision(self.coins[0], self.coins[1])

        # Treasure pickup
        for i, c in enumerate(self.coins):
            if c.carrying is None:
                for t in self.treasures:
                    if t.carried_by is None:
                        tx, ty = t.pos()
                        if length(c.x - tx, c.y - ty) <= c.r + 12:
                            c.carrying = t
                            t.carried_by = i
                            bonus_msg = ""
                            if i == self.turn:
                                self.extra_turn = True
                                bonus_msg = " (+extra turn)"
                            getTreasureSound.play()
                            who = "Player" if i == 0 else "AI"
                            self.message = f"{who} picked treasure!{bonus_msg}"
                            break

        # Steal
        atk = self.coins[self.turn]
        dfd = self.coins[self.other(self.turn)]
        if length(atk.x - dfd.x, atk.y - dfd.y) <= STEAL_DISTANCE:
            if atk.carrying is None and dfd.carrying is not None:
                atk.carrying, dfd.carrying = dfd.carrying, None
                atk.carrying.carried_by = self.turn
                self.extra_turn = True
                self.message = ("Player" if self.turn == 0 else "AI") + " stole! (+extra turn)"

        # Score
        for i, c in enumerate(self.coins):
            if c.carrying is not None and self.bases[i].rect.collidepoint(c.x, c.y):
                self.match_wins[i] += 1
                who = "Player" if i == 0 else "AI"
                self.message = f"{who} scored! Match {self.match_wins[0]}-{self.match_wins[1]}"
                if c.carrying in self.treasures: self.treasures.remove(c.carrying)
                c.carrying = None
                if self.match_wins[i] >= ROUNDS_TO_WIN:
                    self.match_over = True
                    self.awaiting_switch = False
                    self.message = f"{who} WINS! Press R to restart."
                else:
                    self.start_round(starting_player=self.other(i))
                return

        # Turn Switch
        if not self.any_moving() and self.awaiting_switch and not self.dragging:
            if self.extra_turn:
                self.extra_turn = False
                self.message = ("Player" if self.turn == 0 else "AI") + " extra turn!"
            else:
                self.turn = self.other(self.turn)
                self.message = f"Turn: {'Player' if self.turn == 0 else 'AI'}"
                
                self.total_turns += 1
                # SPAWNING LOGIC: After 6 turns total, spawn 1 random item every 2 turns
                if self.total_turns >= 6 and self.total_turns % 2 == 0:
                    self.spawn_random_item_one_of_three()
                    self.message += " (New Item!)"

            self.awaiting_switch = False
            if self.turn != self.ai_index: self.ai_thinking = False

    def check_item_pickup(self, last_positions):
        # ORDER MATTERS: Check them cleanly.
        items = [("extra", "item_Extraturn"), ("stop", "item_StopCoin"), ("redirect", "item_ReDirect")]
        
        for name, attr in items:
            item = getattr(self, attr)
            if not item: continue
            ix, iy = item.pos()
            
            touched = []
            for p, coin in enumerate(self.coins):
                bx, by = last_positions[p]
                ax, ay = coin.x, coin.y
                # Check crossing into radius
                if length(bx-ix, by-iy) > coin.r+12 and length(ax-ix, ay-iy) <= coin.r+12:
                    touched.append(p)
            
            if not touched: continue
            
            player_idx = touched[0]
            c = self.coins[player_idx]
            
            # Consume item
            setattr(self, attr, None)
            
            who = "Player" if player_idx==0 else "AI"
            
            if name == "extra":
                # PURELY EXTRA TURN, NO REDIRECT
                self.extra_turn = True
                self.message = f"{who} picked +Extra Turn!"
                itemsound.set_volume(0.19)
                itemsound.play()
                
            elif name == "stop":
                # STOP MOVEMENT
                c.vx = 0; c.vy = 0; c.resting = True
                self.message = f"{who} picked +Stop Coin!"
                FreezeItemSound.set_volume(0.2)
                FreezeItemSound.play()
                
            elif name == "redirect":
                # PURELY REDIRECT, NO EXTRA TURN
                c.vx = random.uniform(5, 7) * (1 if player_idx == 0 else -1)
                c.vy = random.uniform(-2, 2)
                c.resting = False
                self.awaiting_switch = True # Forces switch unless Extra Turn was ALSO active (unlikely)
                self.message = f"{who} picked +Redirect!"
                whirlpoolItemSound.set_volume(0.2)
                whirlpoolItemSound.play()

    # ---------------------------
    def draw(self):
        self.screen.blit(self.bg_img, (0, 0))
        self.draw_grid(self.screen)
        self.draw_bases(self.screen)
        for r in self.obstacles:
            wall_scaled = pygame.transform.smoothscale(self.wall_img, (r.width, r.height))
            self.screen.blit(wall_scaled, r.topleft)
        self.draw_treasures(self.screen)
        
        if self.item_Extraturn: self.item_Extraturn.draw(self.screen)
        if self.item_StopCoin: self.item_StopCoin.draw(self.screen)
        if self.item_ReDirect: self.item_ReDirect.draw(self.screen)
        
        for c in self.coins: c.draw(self.screen)
        if self.dragging and self.turn == 0:
            coin = self.coins[self.turn]
            mouse = pygame.mouse.get_pos()
            pygame.draw.line(self.screen, (255, 255, 255), (int(coin.x), int(coin.y)), mouse, 2)
        self.draw_hud(self.screen)
        pygame.display.flip()

    def draw_grid(self, surf):
        for r in range(GRID_ROWS + 1):
            y = MARGIN + r * CELL
            pygame.draw.line(surf, GRID, (MARGIN, y), (WIDTH - MARGIN, y), 2)
        for c in range(GRID_COLS + 1):
            x = MARGIN + c * CELL
            pygame.draw.line(surf, GRID, (x, MARGIN), (x, HEIGHT - 50 - MARGIN), 2)

    def draw_bases(self, surf):
        pygame.draw.rect(surf, (180, 40, 40), self.bases[0].rect, border_radius=10)
        pygame.draw.rect(surf, (40, 140, 180), self.bases[1].rect, border_radius=10)

    def draw_treasures(self, surf):
        for t in self.treasures:
            if t.carried_by is None: x, y = t.pos()
            else: c = self.coins[t.carried_by]; x, y = c.x, c.y
            rect = self.treasure_img.get_rect(center=(int(x), int(y)))
            surf.blit(self.treasure_img, rect)

    def draw_hud(self, surf):
        def blit_with_bg(text, x, y, font, color=TEXT):
            label = font.render(text, True, color)
            bg_rect = label.get_rect(topleft=(x, y)).inflate(12, 8)
            pygame.draw.rect(surf, (0, 0, 0), bg_rect)
            surf.blit(label, (x, y))

        txt = f"Wins - Player:{self.match_wins[0]}  AI:{self.match_wins[1]} (Best of 3)"
        blit_with_bg(txt, MARGIN, 8, self.font)
        turn_text = "Player" if self.turn == 0 else "AI"
        txt_turn = f"Turn: {turn_text}"
        t_w, t_h = self.font.size(txt_turn)
        blit_with_bg(txt_turn, WIDTH - t_w - MARGIN, 8, self.font)

        bottom_y_start = HEIGHT - 50
        m_h = self.font.size(self.message)[1]
        blit_with_bg(self.message, MARGIN, bottom_y_start + 2, self.font)

        help_txt = "Drag = flick. SPACE = nudge. R = reset. ESC = quit. M = main menu"
        h_w, h_h = self.font.size(help_txt)
        blit_with_bg(help_txt, WIDTH - h_w - MARGIN, bottom_y_start + 2, self.font, (200, 210, 230))

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
                pygame.quit(); os.system("python main.py"); raise SystemExit

    def run(self):
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT: pygame.quit(); raise SystemExit
                self.handle_global_keys(e)
            self.handle_shot_input(events)
            self.update_logic()
            self.draw()

if __name__ == "__main__":
    Game().run()