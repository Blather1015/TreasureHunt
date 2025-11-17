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
WIDTH = GRID_COLS * CELL + MARGIN * 2
HEIGHT = GRID_ROWS * CELL + MARGIN * 2 + 50
FPS = 120

TREASURES_PER_ROUND = 1
ROUNDS_TO_WIN = 2

FRICTION = 0.985
MIN_SPEED = 0.35
MAX_SHOT_POWER = 16.0
STEAL_DISTANCE = 33

# Colors (still used for HUD text & grid lines)
BG = (8, 20, 45)
GRID = (22, 50, 95)
TEXT = (230, 240, 250)

P1_COLOR = (230, 90, 80)   # just identity, coin uses texture
P2_COLOR = (90, 180, 230)

MAP_FOLDER = "maps"  # folder where pre-made maps are stored

itemsound = pygame.mixer.Sound("sounds/itemcollect.mp3")
bouncesound = pygame.mixer.Sound("sounds/bounce.mp3")
FreezeItemSound = pygame.mixer.Sound("sounds/freeze.mp3")
whirlpoolItemSound = pygame.mixer.Sound("sounds/whirlpool.mp3")
getTreasureSound = pygame.mixer.Sound("sounds/treasure.mp3")

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
    def __init__(self, x, y, color, red_img, blue_img):
        self.x = x
        self.y = y
        self.vx = self.vy = 0.0
        self.r = 14
        self.color = color
        self.carrying: Treasure | None = None
        self.resting = True

        # texture refs
        self.red_img = red_img
        self.blue_img = blue_img

    def draw(self, surf):
        img = self.red_img if self.color == P1_COLOR else self.blue_img
        rect = img.get_rect(center=(int(self.x), int(self.y)))
        surf.blit(img, rect)

    def update(self, obstacles):
        # friction & movement
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

        # Obstacle bounce
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

    def pos(self):
        return grid_to_px(self.row, self.col)

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

    def pos(self):
        return grid_to_px(self.row, self.col)

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

    def pos(self):
        return grid_to_px(self.row, self.col)

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
        pygame.display.set_caption("Treasure Hunt - Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 22)
        self.bigfont = pygame.font.SysFont("arial", 36, bold=True)

        # --- Load textures ---
        self.bg_img = pygame.image.load("assets/background.png").convert()
        self.bg_img = pygame.transform.scale(self.bg_img, (WIDTH, HEIGHT))

        # coins
        coin_red_raw = pygame.image.load("assets/coin_red.png").convert_alpha()
        coin_blue_raw = pygame.image.load("assets/coin_blue.png").convert_alpha()
        self.coin_red_img = pygame.transform.smoothscale(coin_red_raw, (40, 40))
        self.coin_blue_img = pygame.transform.smoothscale(coin_blue_raw, (40, 40))

        # treasure
        treasure_raw = pygame.image.load("assets/treasure.png").convert_alpha()
        self.treasure_img = pygame.transform.smoothscale(treasure_raw, (40, 40))

        # items
        extra_raw = pygame.image.load("assets/ExtraTurn.png").convert_alpha()
        stop_raw = pygame.image.load("assets/StopCoin.png").convert_alpha()
        redirect_raw = pygame.image.load("assets/ReDirect.png").convert_alpha()
        self.extra_img = pygame.transform.smoothscale(extra_raw, (40, 40))
        self.stop_img = pygame.transform.smoothscale(stop_raw, (40, 40))
        self.redirect_img = pygame.transform.smoothscale(redirect_raw, (40, 40))

        # sounds
        

        # wall texture
        wall_raw = pygame.image.load("assets/wall.png").convert_alpha()
        self.wall_img = wall_raw   # will scale per-rect in draw()

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
        self.message = "Flip: P1 starts!"
        self.randomDirect = True

        # Initialize first map (only changes on R)
        self.obstacles = self.load_random_map()

        # Items
        self.item_Extraturn: ItemExtraTurn | None = None
        self.item_StopCoin: ItemStopCoin | None = None
        self.item_ReDirect: ItemReDirect | None = None

        self.start_round(starting_player=0)

    # ---------------------------
    def load_random_map(self):
        map_files = [f for f in os.listdir(MAP_FOLDER)
                     if f.endswith(".json")] if os.path.exists(MAP_FOLDER) else []
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

        # Default fallback layout
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
    # Item spawn
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

    # ---------------------------
    def start_round(self, starting_player=0):
        self.turn = starting_player
        self.message = f"Round start: Player {self.turn+1}'s turn"
        self.awaiting_switch = False
        self.extra_turn = False
        self.total_turns = 0

        map_mid_y = (GRID_ROWS * CELL + MARGIN * 2) // 2
        self.coins[0].x, self.coins[0].y = MARGIN + 20, map_mid_y
        self.coins[1].x, self.coins[1].y = WIDTH - MARGIN - 20, map_mid_y
        for c in self.coins:
            c.vx = c.vy = 0
            c.resting = True
            c.carrying = None

        # Spawn treasure 
        candidate_cells = [(r, c) for r in range(1, 4)
                           for c in range(3, 6)]
        candidate_cells = [
            (r, c) for (r, c) in candidate_cells
            if not self._cell_center_blocked(r, c)
        ]
        self.treasures = []
        if candidate_cells:
            r, c = random.choice(candidate_cells)
            self.treasures.append(Treasure(row=r, col=c, carried_by=None))

        # Spawn items
        self.item_Extraturn = None
        self.item_StopCoin = None
        self.item_ReDirect = None
        # Spawn exactly ONE random item to start (optional, but makes map less empty)
        self.spawn_random_item_one_of_three()

    # ---------------------------
    def any_moving(self):
        return any(abs(c.vx) > 0.0 or abs(c.vy) > 0.0 for c in self.coins)

    def other(self, p):
        return 1 - p

    def handle_shot_input(self, events):
        if self.awaiting_switch or self.match_over:
            return
        coin = self.coins[self.turn]
        if not coin.resting:
            return

        mouse = pygame.mouse.get_pos()
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if length(mouse[0] - coin.x,
                          mouse[1] - coin.y) <= coin.r + 10:
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
        if dist == 0 or dist >= min_dist:
            return
        nx, ny = dx / dist, dy / dist
        overlap = min_dist - dist
        a.x -= nx * overlap * 0.5
        a.y -= ny * overlap * 0.5
        b.x += nx * overlap * 0.5
        b.y += ny * overlap * 0.5
        rvx, rvy = b.vx - a.vx, b.vy - a.vy
        vel_along_normal = rvx * nx + rvy * ny
        if vel_along_normal > 0:
            return
        restitution = 0.7
        j = -(1 + restitution) * vel_along_normal / 2
        impulse_x, impulse_y = j * nx, j * ny
        a.vx -= impulse_x
        a.vy -= impulse_y
        b.vx += impulse_x
        b.vy += impulse_y

    # ---------------------------
        # ---------------------------
    def update_logic(self):
        if self.match_over:
            return

        # --- SAVE LAST POSITIONS BEFORE MOVING ---
        last_positions = [(c.x, c.y) for c in self.coins]

        # 1. MOVE COINS
        for c in self.coins:
            c.update(self.obstacles)


        # 2. ITEM PICKUP (before collision pushes coins)
        self.check_item_pickup(last_positions)

        # 3. COLLISION
        self.resolve_coin_collision(self.coins[0], self.coins[1])


        # 4. Treasure pickup
        for i, c in enumerate(self.coins):
            if c.carrying is None:
                for t in self.treasures:
                    if t.carried_by is None:
                        tx, ty = t.pos()
                        if length(c.x - tx, c.y - ty) <= c.r + 12:
                            c.carrying = t
                            t.carried_by = i
                            getTreasureSound.play()
                            
                            # --- START FIX ---
                            if i == self.turn:
                                self.extra_turn = True
                                self.message = f"P{i+1} picked treasure! (+extra turn)"
                            else:
                                self.message = f"P{i+1} picked treasure!"
                            # --- END FIX ---
                            
                            break

        # 5. Steal
        attacker = self.coins[self.turn]
        defender = self.coins[self.other(self.turn)]
        if length(attacker.x - defender.x, attacker.y - defender.y) <= STEAL_DISTANCE:
            if attacker.carrying is None and defender.carrying is not None:
                attacker.carrying, defender.carrying = defender.carrying, None
                attacker.carrying.carried_by = self.turn
                self.extra_turn = True
                self.message = f"P{self.turn+1} stole! (+extra turn)"

        # 6. Scoring
        for i, c in enumerate(self.coins):
            if c.carrying is not None and self.bases[i].rect.collidepoint(c.x, c.y):
                self.match_wins[i] += 1
                self.message = f"P{i+1} scored! Match {self.match_wins[0]}-{self.match_wins[1]}"
                if c.carrying in self.treasures:
                    self.treasures.remove(c.carrying)
                c.carrying = None
                if self.match_wins[i] >= ROUNDS_TO_WIN:
                    self.match_over = True
                    self.awaiting_switch = False
                    self.message = f"P{i+1} WINS THE MATCH! Press R to restart."
                else:
                    self.start_round(starting_player=self.other(i))
                return

        # 7. Turn switch
        if not self.any_moving() and self.awaiting_switch and not self.dragging:
            if self.extra_turn:
                self.extra_turn = False
                self.message = f"P{self.turn+1} extra turn!"
            else:
                self.turn = self.other(self.turn)
                self.message = f"Turn: Player {self.turn+1}"
            self.awaiting_switch = False

            self.total_turns += 1
            # SPAWNING LOGIC: After 6 turns total, spawn 1 random item every 2 turns
            if self.total_turns >= 6 and self.total_turns % 2 == 0:
                self.spawn_random_item_one_of_three()
                self.message += " (New Item!)"


    # ---------------------------
        # ---------------------------
    def check_item_pickup(self, last_positions):
        items = [
            ("extra", "item_Extraturn"),
            ("stop", "item_StopCoin"),
            ("redirect", "item_ReDirect")
        ]

        for name, attr in items:
            item = getattr(self, attr)
            if not item:
                continue

            ix, iy = item.pos()

            touched = []

            # check which coin ENTERED the pickup radius
            for p, coin in enumerate(self.coins):
                bx, by = last_positions[p]     # last frame
                ax, ay = coin.x, coin.y        # this frame

                d_before = length(bx - ix, by - iy)
                d_now = length(ax - ix, ay - iy)

                # must cross into radius
                if d_before > coin.r + 12 and d_now <= coin.r + 12:
                    touched.append(p)

            if not touched:
                continue

            # the first coin that entered the zone this frame
            player = touched[0]
            c = self.coins[player]

            # remove item
            setattr(self, attr, None)

            # apply effect
            # apply effect
            if name == "extra":
                
                # --- START FIX ---
                if player == self.turn:
                    self.extra_turn = True
                    self.message = f"P{player+1} picked Extra Turn! (+extra turn)"
                else:
                    self.message = f"P{player+1} picked Extra Turn!"
                # --- END FIX ---
                
                itemsound.set_volume(0.19)
                itemsound.play()
                

            elif name == "stop":
                c.vx = 0
                c.vy = 0
                c.resting = True
                self.message = f"P{player+1} picked Icecube!"
                FreezeItemSound.set_volume(0.2)
                FreezeItemSound.play()

            elif name == "redirect":
                c.vx = random.uniform(5, 7) * (1 if player == 0 else -1)
                c.vy = random.uniform(-2, 2)
                c.resting = False
                self.awaiting_switch = True
                self.message = f"P{player+1} picked Whirlpool!"
                whirlpoolItemSound.set_volume(0.2)
                whirlpoolItemSound.play()



    # ---------------------------
    def draw(self):
        # background texture
        self.screen.blit(self.bg_img, (0, 0))

        # grid, bases, etc
        self.draw_grid(self.screen)
        self.draw_bases(self.screen)

        # obstacles with wall texture
        for r in self.obstacles:
            wall_scaled = pygame.transform.smoothscale(self.wall_img, (r.width, r.height))
            self.screen.blit(wall_scaled, r.topleft)

        # treasure texture
        self.draw_treasures(self.screen)

        # items
        if self.item_Extraturn:
            self.item_Extraturn.draw(self.screen)
        if self.item_StopCoin:
            self.item_StopCoin.draw(self.screen)
        if self.item_ReDirect:
            self.item_ReDirect.draw(self.screen)

        # coins
        for c in self.coins:
            c.draw(self.screen)

        # aiming line
        if self.dragging:
            coin = self.coins[self.turn]
            mouse = pygame.mouse.get_pos()
            pygame.draw.line(self.screen, (255, 255, 255),
                             (int(coin.x), int(coin.y)), mouse, 2)

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
            if t.carried_by is None:
                x, y = t.pos()
            else:
                c = self.coins[t.carried_by]
                x, y = c.x, c.y
            rect = self.treasure_img.get_rect(center=(int(x), int(y)))
            surf.blit(self.treasure_img, rect)

    def draw_hud(self, surf):
        def blit_with_bg(text, x, y, font, color=TEXT):
            label = font.render(text, True, color)
            bg_rect = label.get_rect(topleft=(x, y)).inflate(12, 8)
            pygame.draw.rect(surf, (0, 0, 0), bg_rect)
            surf.blit(label, (x, y))

        txt = f"Wins - Player 1:{self.match_wins[0]}  Player 2:{self.match_wins[1]} (Best of 3)"
        blit_with_bg(txt, MARGIN, 8, self.font)
        turn_text = "Player 1" if self.turn == 0 else "Player 2"
        txt_turn = f"Turn: {turn_text}"
        t_w, t_h = self.font.size(txt_turn)
        blit_with_bg(txt_turn, WIDTH - t_w - MARGIN, 8, self.font)

        bottom_y_start = HEIGHT - 50
        m_h = self.font.size(self.message)[1]
        blit_with_bg(self.message, MARGIN, bottom_y_start + 2, self.font)

        help_txt = "Drag = flick. SPACE = nudge. R = reset. ESC = quit. M = main menu"
        h_w, h_h = self.font.size(help_txt)
        blit_with_bg(help_txt, WIDTH - h_w - MARGIN, bottom_y_start + 2, self.font, (200, 210, 230))

    # ---------------------------
    def handle_global_keys(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                self.match_wins = [0, 0]
                self.match_over = False
                self.obstacles = self.load_random_map()  # NEW map only when R pressed
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
                    pygame.quit()
                    raise SystemExit
                self.handle_global_keys(e)
            self.handle_shot_input(events)
            self.update_logic()
            self.draw()

# ---------------------------
if __name__ == "__main__":
    Game().run()
