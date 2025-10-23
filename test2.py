#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pygame
import random
import math
from dataclasses import dataclass

# ---------------------------
# CONFIG
# ---------------------------
GRID_ROWS = 5
GRID_COLS = 9
CELL = 90
MARGIN = 40
WIDTH = GRID_COLS * CELL + MARGIN * 2
HEIGHT = GRID_ROWS * CELL + MARGIN * 2
FPS = 60

TREASURES_PER_ROUND = 1          # only one treasure per round
ROUNDS_TO_WIN = 2                # best of 3

FRICTION = 0.985
MIN_SPEED = 0.35
MAX_SHOT_POWER = 16.0  # cap launch velocity
STEAL_DISTANCE = 28    # distance to trigger steal on collision

# Colors
BG = (8, 20, 45)
GRID = (22, 50, 95)
WALL = (30, 70, 120)
TREASURE_COLOR = (255, 215, 0)
P1_COLOR = (230, 90, 80)
P2_COLOR = (90, 180, 230)
BASE1_COLOR = (180, 40, 40)
BASE2_COLOR = (40, 140, 180)
TEXT = (230, 240, 250)
OBSTACLE_C = (120, 160, 200)

# ---------------------------
# Helpers
# ---------------------------
def grid_to_px(r, c):
    return (MARGIN + c * CELL + CELL // 2, MARGIN + r * CELL + CELL // 2)

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def length(vx, vy):
    return math.hypot(vx, vy)

# ---------------------------
# Entities
# ---------------------------
@dataclass
class Treasure:
    row: int
    col: int
    carried_by: int | None = None  # 0 or 1 for player index

    def pos(self):
        return grid_to_px(self.row, self.col)

@dataclass
class Base:
    # base is a rectangle covering 1x3 cells at each team's side
    owner: int
    rect: pygame.Rect

class Coin:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.r = 14
        self.color = color
        self.carrying: Treasure | None = None
        self.resting = True  # whether coin is stopped (turn ends when resting after a shot)

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.r)
        if self.carrying is not None:
            # draw small ring to indicate carrying
            pygame.draw.circle(surf, (255, 255, 255), (int(self.x), int(self.y)), self.r + 3, 2)

    def update(self, obstacles):
        # move with simple physics & friction, bounce off walls and obstacles
        if abs(self.vx) < MIN_SPEED and abs(self.vy) < MIN_SPEED:
            self.vx = 0.0
            self.vy = 0.0
            self.resting = True
            return

        self.resting = False
        # integrate
        self.x += self.vx
        self.y += self.vy
        self.vx *= FRICTION
        self.vy *= FRICTION

        # world bounds (bounce)
        if self.x - self.r < MARGIN:
            self.x = MARGIN + self.r
            self.vx *= -0.7
        if self.x + self.r > WIDTH - MARGIN:
            self.x = WIDTH - MARGIN - self.r
            self.vx *= -0.7
        if self.y - self.r < MARGIN:
            self.y = MARGIN + self.r
            self.vy *= -0.7
        if self.y + self.r > HEIGHT - MARGIN:
            self.y = HEIGHT - MARGIN - self.r
            self.vy *= -0.7

        # obstacle collisions (AABB reflect)
        for rect in obstacles:
            if rect.collidepoint(self.x, self.y):
                # compute minimal push out
                dx_left = abs((rect.left) - (self.x + self.r))
                dx_right = abs((rect.right) - (self.x - self.r))
                dy_top = abs((rect.top) - (self.y + self.r))
                dy_bottom = abs((rect.bottom) - (self.y - self.r))

                m = min(dx_left, dx_right, dy_top, dy_bottom)
                if m == dx_left:
                    self.x = rect.left - self.r
                    self.vx *= -0.7
                elif m == dx_right:
                    self.x = rect.right + self.r
                    self.vx *= -0.7
                elif m == dy_top:
                    self.y = rect.top - self.r
                    self.vy *= -0.7
                else:
                    self.y = rect.bottom + self.r
                    self.vy *= -0.7

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Treasure Flick (Best of 3)")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 22)
        self.bigfont = pygame.font.SysFont("arial", 36, bold=True)

        # Obstacles - create a few fixed AABBs inside the grid
        self.obstacles = self.make_obstacles()

        # Bases: left and right sides, 3 cells tall in center
        base_h = 3 * CELL
        base_y = MARGIN + (GRID_ROWS * CELL - base_h) // 2
        left_rect = pygame.Rect(MARGIN, base_y, CELL, base_h)
        right_rect = pygame.Rect(WIDTH - MARGIN - CELL, base_y, CELL, base_h)
        self.bases = [Base(0, left_rect), Base(1, right_rect)]

        # Players & coins
        p1_start = (MARGIN + 20, HEIGHT // 2)
        p2_start = (WIDTH - MARGIN - 20, HEIGHT // 2)
        self.coins = [
            Coin(*p1_start, P1_COLOR),
            Coin(*p2_start, P2_COLOR)
        ]

        # Match state
        self.match_wins = [0, 0]   # best of 3
        self.turn = 0              # 0 or 1
        self.extra_turn = False    # granted when picking up treasure

        self.dragging = False
        self.drag_start = (0, 0)

        self.treasures: list[Treasure] = []
        self.match_over = False
        self.message = "Flip: P1 starts!"
        self.start_round(starting_player=0)

    # ---------------------------
    def make_obstacles(self):
        rects = []
        # place 3 thin vertical pillars roughly in the middle columns
        cols = [2, 4, 6]
        for c in cols:
            x = MARGIN + c * CELL + CELL // 2 - 8
            y = MARGIN + CELL // 2
            rects.append(pygame.Rect(x, y, 16, CELL * 3))
        # small horizontal bar in the middle
        rects.append(pygame.Rect(WIDTH // 2 - 80, HEIGHT // 2 - 10, 160, 20))
        return rects

    def _cell_center_blocked(self, r, c):
        """True if the treasure center at this cell would be inside an obstacle."""
        x, y = grid_to_px(r, c)
        for rect in self.obstacles:
            if rect.collidepoint(x, y):
                return True
        return False

    def start_round(self, starting_player=0):
        self.turn = starting_player
        self.message = f"Round start: Player {self.turn+1}'s turn"

        # reset coins to edges
        self.coins[0].x, self.coins[0].y = MARGIN + 20, HEIGHT // 2
        self.coins[1].x, self.coins[1].y = WIDTH - MARGIN - 20, HEIGHT // 2
        for c in self.coins:
            c.vx = c.vy = 0.0
            c.resting = True
            c.carrying = None
        self.extra_turn = False

        # --- spawn exactly ONE treasure in the middle area, not in base columns, not in walls ---
        # "Middle" = rows 1..3, cols 3..5 (center block) on a 5x9 grid
        candidate_cells = [(r, c) for r in range(1, 4) for c in range(3, 6)]
        # Avoid base columns (0 and 8) by construction; also avoid obstacles
        candidate_cells = [(r, c) for (r, c) in candidate_cells if not self._cell_center_blocked(r, c)]

        self.treasures = []
        if candidate_cells:
            r, c = random.choice(candidate_cells)
            self.treasures.append(Treasure(r, c, None))
        else:
            # fallback: any non-base column cell whose center isn't blocked
            fallback = [(r, c) for r in range(GRID_ROWS) for c in range(GRID_COLS)
                        if c not in (0, GRID_COLS - 1) and not self._cell_center_blocked(r, c)]
            if fallback:
                r, c = random.choice(fallback)
                self.treasures.append(Treasure(r, c, None))
            # If still none, no treasure this round (very unlikely with current obstacles)

    # ---------------------------
    def any_moving(self):
        return any(abs(c.vx) > 0.0 or abs(c.vy) > 0.0 for c in self.coins)

    def other(self, p):
        return 1 - p

    # ---------------------------
    def handle_shot_input(self, events):
        coin = self.coins[self.turn]
        if not coin.resting:
            return  # can't shoot while moving

        mouse = pygame.mouse.get_pos()
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # only allow drag if click near your coin
                if length(mouse[0] - coin.x, mouse[1] - coin.y) <= coin.r + 10:
                    self.dragging = True
                    self.drag_start = mouse
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.dragging:
                self.dragging = False
                dx = mouse[0] - self.drag_start[0]
                dy = mouse[1] - self.drag_start[1]
                # shot vector opposite the drag (slingshot)
                vx = -dx / 10.0
                vy = -dy / 10.0
                speed = length(vx, vy)
                if speed > 0.1:
                    scale = min(1.0, MAX_SHOT_POWER / speed)
                    coin.vx = vx * scale
                    coin.vy = vy * scale
                    coin.resting = False
                    self.message = f"P{self.turn+1} shot!"
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE and coin.resting:
                # small nudge shot for keyboard users
                coin.vx = random.uniform(5, 7) * (1 if self.turn == 0 else -1)
                coin.vy = random.uniform(-2, 2)
                coin.resting = False
                self.message = f"P{self.turn+1} shot!"

    # ---------------------------
    def resolve_coin_collision(self, a, b):
        # vector from a -> b
        dx = b.x - a.x
        dy = b.y - a.y
        dist = math.hypot(dx, dy)
        min_dist = a.r + b.r
        if dist == 0 or dist >= min_dist:
            return  # no collision

        # Normalized collision normal
        nx = dx / dist
        ny = dy / dist

        # Push coins apart so they no longer overlap (split the correction)
        overlap = (min_dist - dist)
        a.x -= nx * overlap * 0.5
        a.y -= ny * overlap * 0.5
        b.x += nx * overlap * 0.5
        b.y += ny * overlap * 0.5

        # Relative velocity along the normal
        rvx = b.vx - a.vx
        rvy = b.vy - a.vy
        vel_along_normal = rvx * nx + rvy * ny

        # If they’re moving apart already, no bounce
        if vel_along_normal > 0:
            return

        # Elastic-ish bounce (match wall damping)
        restitution = 0.7

        # Equal masses => impulse scalar
        j = -(1 + restitution) * vel_along_normal
        j /= 2.0  # m1 = m2 = 1

        # Apply impulse in opposite directions
        impulse_x = j * nx
        impulse_y = j * ny
        a.vx -= impulse_x
        a.vy -= impulse_y
        b.vx += impulse_x
        b.vy += impulse_y

    # ---------------------------
    def update_logic(self):
        if self.match_over:
            return

        # Update physics
        for c in self.coins:
            c.update(self.obstacles)

        # Bounce P1 and P2 if they collide
        self.resolve_coin_collision(self.coins[0], self.coins[1])

        # Check coin-treasure pickup (only when not already carrying)
        for i, c in enumerate(self.coins):
            if c.carrying is None:
                for t in self.treasures:
                    if t.carried_by is None:
                        tx, ty = t.pos()
                        if length(c.x - tx, c.y - ty) <= c.r + 12:
                            c.carrying = t
                            t.carried_by = i
                            self.message = f"P{i+1} picked treasure! (+extra turn)"
                            # Grant ONE extra turn (consumed at switch time)
                            self.extra_turn = True
                            break

        # Steal on collision
        c0, c1 = self.coins
        if c0.carrying is None and c1.carrying is not None:
            if length(c0.x - c1.x, c0.y - c1.y) <= STEAL_DISTANCE:
                c0.carrying, c1.carrying = c1.carrying, None
                if c0.carrying:
                    c0.carrying.carried_by = 0
                self.message = "P1 stole!"
        elif c1.carrying is None and c0.carrying is not None:
            if length(c1.x - c0.x, c1.y - c0.y) <= STEAL_DISTANCE:
                c1.carrying, c0.carrying = c0.carrying, None
                if c1.carrying:
                    c1.carrying.carried_by = 1
                self.message = "P2 stole!"

        # Score when entering own base -> immediate round win and auto next round
        for i, c in enumerate(self.coins):
            if c.carrying is not None:
                base = self.bases[i].rect
                if base.collidepoint(c.x, c.y):
                    # Winner of the round
                    self.match_wins[i] += 1
                    self.message = f"P{i+1} scored! Round to P{i+1}. Match {self.match_wins[0]}-{self.match_wins[1]}"
                    # remove treasure
                    t = c.carrying
                    if t in self.treasures:
                        self.treasures.remove(t)
                    c.carrying = None

                    # Match end?
                    if self.match_wins[i] >= ROUNDS_TO_WIN:
                        self.match_over = True
                        self.message = f"P{i+1} WINS THE MATCH! Press R to restart."
                    else:
                        # Auto start next round; scorer starts
                        self.start_round(starting_player=i)
                    return  # stop further processing this frame

        # End of turn: switch when all coins are at rest and the player actually took action
        if not self.any_moving():
            if not self.dragging and any(k in self.message.lower() for k in ("shot", "picked", "stole", "scored")):
                if self.extra_turn:
                    # consume the extra turn instead of switching
                    self.extra_turn = False
                    self.message = f"P{self.turn+1} extra turn!"
                else:
                    self.turn = self.other(self.turn)

    # ---------------------------
    def draw_grid(self, surf):
        # grid cells
        for r in range(GRID_ROWS + 1):
            y = MARGIN + r * CELL
            pygame.draw.line(surf, GRID, (MARGIN, y), (WIDTH - MARGIN, y), 2)
        for c in range(GRID_COLS + 1):
            x = MARGIN + c * CELL
            pygame.draw.line(surf, GRID, (x, MARGIN), (x, HEIGHT - MARGIN), 2)

    def draw_bases(self, surf):
        pygame.draw.rect(surf, BASE1_COLOR, self.bases[0].rect, border_radius=10)
        pygame.draw.rect(surf, BASE2_COLOR, self.bases[1].rect, border_radius=10)

    def draw_obstacles(self, surf):
        for rect in self.obstacles:
            pygame.draw.rect(surf, OBSTACLE_C, rect, border_radius=6)

    def draw_treasures(self, surf):
        for t in self.treasures:
            if t.carried_by is None:
                x, y = t.pos()
            else:
                # follow carrier coin
                c = self.coins[t.carried_by]
                x, y = c.x, c.y
            pygame.draw.circle(surf, TREASURE_COLOR, (int(x), int(y)), 8)
            pygame.draw.circle(surf, (80, 60, 0), (int(x), int(y)), 8, 2)

    def draw_hud(self, surf):
        # Match wins only (round-based)
        txt = f"Match Wins  P1:{self.match_wins[0]}  P2:{self.match_wins[1]}  (Best of 3)"
        s = self.font.render(txt, True, TEXT)
        surf.blit(s, (MARGIN, 8))

        # Turn
        t = self.font.render(f"Turn: Player {self.turn+1}", True, TEXT)
        surf.blit(t, (WIDTH - t.get_width() - MARGIN, 8))

        # Message
        m = self.font.render(self.message, True, TEXT)
        surf.blit(m, (MARGIN, HEIGHT - m.get_height() - 8))

        if self.dragging:
            # draw aim line
            coin = self.coins[self.turn]
            mouse = pygame.mouse.get_pos()
            pygame.draw.line(surf, (255, 255, 255), (int(coin.x), int(coin.y)), mouse, 2)

        if self.match_over:
            overlay = self.bigfont.render(self.message, True, (255, 255, 255))
            surf.blit(overlay, (WIDTH // 2 - overlay.get_width() // 2, HEIGHT // 2 - 50))

        # Controls
        help1 = self.font.render("Drag to flick. SPACE=nudge. R=reset match. ESC=quit.", True, (200, 210, 230))
        surf.blit(help1, (MARGIN, HEIGHT - m.get_height() - 34))

    # ---------------------------
    def draw(self):
        self.screen.fill(BG)
        self.draw_grid(self.screen)
        self.draw_bases(self.screen)
        self.draw_obstacles(self.screen)
        self.draw_treasures(self.screen)

        for c in self.coins:
            c.draw(self.screen)

        self.draw_hud(self.screen)
        pygame.display.flip()

    # ---------------------------
    def handle_global_keys(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                # full reset
                self.match_wins = [0, 0]
                self.match_over = False
                self.start_round(starting_player=random.choice([0, 1]))
            elif e.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ---------------------------
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

if __name__ == "__main__":
    Game().run()
