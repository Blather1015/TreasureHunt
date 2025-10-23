#!/usr/bin/env python3
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

TREASURES_PER_ROUND = 5
POINTS_TO_WIN_ROUND = 2
ROUNDS_TO_WIN = 2

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
            pygame.draw.circle(surf, (255,255,255), (int(self.x), int(self.y)), self.r+3, 2)

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
        base_y = MARGIN + (GRID_ROWS * CELL - base_h)//2
        left_rect = pygame.Rect(MARGIN, base_y, CELL, base_h)
        right_rect = pygame.Rect(WIDTH - MARGIN - CELL, base_y, CELL, base_h)
        self.bases = [Base(0, left_rect), Base(1, right_rect)]

        # Players & coins
        p1_start = (MARGIN + 20, HEIGHT//2)
        p2_start = (WIDTH - MARGIN - 20, HEIGHT//2)
        self.coins = [
            Coin(*p1_start, P1_COLOR),
            Coin(*p2_start, P2_COLOR)
        ]

        self.round_scores = [0, 0]
        self.match_wins = [0, 0]

        self.turn = 0  # 0 or 1
        self.dragging = False
        self.drag_start = (0, 0)

        self.treasures: list[Treasure] = []
        self.round_over = False
        self.match_over = False
        self.message = "Flip: P1 starts!"
        self.start_round(starting_player=0)

    # ---------------------------
    def make_obstacles(self):
        rects = []
        # place 3 thin vertical pillars roughly in the middle columns
        cols = [2, 4, 6]
        for c in cols:
            x = MARGIN + c * CELL + CELL//2 - 8
            y = MARGIN + CELL//2
            rects.append(pygame.Rect(x, y, 16, CELL*3))
        # small horizontal bar in the middle
        rects.append(pygame.Rect(WIDTH//2 - 80, HEIGHT//2 - 10, 160, 20))
        return rects

    def start_round(self, starting_player=0):
        self.turn = starting_player
        self.round_over = False
        self.message = f"Round start: Player {self.turn+1}'s turn"
        # reset coins to edges
        self.coins[0].x, self.coins[0].y = MARGIN + 20, HEIGHT//2
        self.coins[1].x, self.coins[1].y = WIDTH - MARGIN - 20, HEIGHT//2
        for c in self.coins:
            c.vx = c.vy = 0.0
            c.resting = True
            c.carrying = None

        # spawn treasures at random grid cells not in base columns
        self.treasures = []
        occupied = set()
        attempts = 0
        while len(self.treasures) < TREASURES_PER_ROUND and attempts < 200:
            attempts += 1
            r = random.randrange(GRID_ROWS)
            c = random.randrange(GRID_COLS)
            # avoid base columns (0 and 8) to encourage travel
            if c in (0, GRID_COLS-1):
                continue
            if (r, c) in occupied:
                continue
            occupied.add((r, c))
            self.treasures.append(Treasure(r, c, None))

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
                if length(mouse[0]-coin.x, mouse[1]-coin.y) <= coin.r + 10:
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
    def update_logic(self):
        # Update physics
        for c in self.coins:
            c.update(self.obstacles)

        # Carrying treasure follows coin
        for c in self.coins:
            if c.carrying is not None:
                # if carried, treasure no longer occupies grid (float with coin)
                pass

        # Check coin-treasure pickup (only when not already carrying)
        for i, c in enumerate(self.coins):
            if c.carrying is None:
                for t in self.treasures:
                    if t.carried_by is None:
                        tx, ty = t.pos()
                        if length(c.x - tx, c.y - ty) <= c.r + 12:
                            c.carrying = t
                            t.carried_by = i
                            self.message = f"P{i+1} picked treasure!"
                            break

        # Check steal: collide with opponent carrying treasure
        c0, c1 = self.coins
        if c0.carrying is None and c1.carrying is not None:
            if length(c0.x - c1.x, c0.y - c1.y) <= STEAL_DISTANCE:
                c0.carrying, c1.carrying = c1.carrying, None
                if c0.carrying: c0.carrying.carried_by = 0
                self.message = "P1 stole!"
        elif c1.carrying is None and c0.carrying is not None:
            if length(c1.x - c0.x, c1.y - c0.y) <= STEAL_DISTANCE:
                c1.carrying, c0.carrying = c0.carrying, None
                if c1.carrying: c1.carrying.carried_by = 1
                self.message = "P2 stole!"

        # Score when entering own base
        for i, c in enumerate(self.coins):
            if c.carrying is not None:
                base = self.bases[i].rect
                if base.collidepoint(c.x, c.y):
                    # score
                    self.round_scores[i] += 1
                    # remove that treasure from the board
                    t = c.carrying
                    if t in self.treasures:
                        self.treasures.remove(t)
                    c.carrying = None
                    self.message = f"P{i+1} scored! ({self.round_scores[0]}-{self.round_scores[1]})"

                    # round end?
                    if self.round_scores[i] >= POINTS_TO_WIN_ROUND:
                        self.round_over = True
                        self.match_wins[i] += 1
                        self.message = f"Round won by P{i+1}! Match {self.match_wins[0]}-{self.match_wins[1]}"

                        if self.match_wins[i] >= ROUNDS_TO_WIN:
                            self.match_over = True
                            self.message = f"P{i+1} WINS THE MATCH! Press R to restart."
                    break

        # End of turn: when current coin stops moving and mouse is released
        # If no coin is moving anymore, switch turn (after a shot)
        if not self.any_moving():
            # Switch turn only once coins have come to rest AND player had attempted a shot
            # We detect by resting True and last message included 'shot' or 'picked/steal/score'
            # To keep it simple: if both coins resting, allow switching with ENTER or auto-switch if no dragging
            # Auto-switch:
            # Don't switch if dragging currently
            if not self.dragging and "shot" in self.message.lower() or "picked" in self.message.lower() or "stole" in self.message.lower() or "scored" in self.message.lower():
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
                # find carrier coin
                c = self.coins[t.carried_by]
                x, y = c.x, c.y
            pygame.draw.circle(surf, TREASURE_COLOR, (int(x), int(y)), 8)
            pygame.draw.circle(surf, (80, 60, 0), (int(x), int(y)), 8, 2)

    def draw_hud(self, surf):
        # Scores & round
        txt = f"Round Score  P1:{self.round_scores[0]}  P2:{self.round_scores[1]}   |   Match Wins  P1:{self.match_wins[0]}  P2:{self.match_wins[1]}"
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
            pygame.draw.line(surf, (255,255,255), (int(coin.x), int(coin.y)), mouse, 2)

        if self.round_over and not self.match_over:
            overlay = self.bigfont.render("Round Over! Press N for next round.", True, (255,255,255))
            surf.blit(overlay, (WIDTH//2 - overlay.get_width()//2, HEIGHT//2 - 50))

        if self.match_over:
            overlay = self.bigfont.render(self.message, True, (255,255,255))
            surf.blit(overlay, (WIDTH//2 - overlay.get_width()//2, HEIGHT//2 - 50))

        # Controls
        help1 = self.font.render("Drag from your coin to flick. SPACE: random nudge. N: next round. R: reset match.", True, (200,210,230))
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
            if e.key == pygame.K_n and self.round_over and not self.match_over:
                # next round, loser starts (or alternate)
                next_start = 1 if self.turn == 0 else 0
                self.round_scores = [0, 0]
                self.start_round(starting_player=next_start)
            elif e.key == pygame.K_r:
                # reset entire match
                self.match_wins = [0, 0]
                self.round_scores = [0, 0]
                self.match_over = False
                self.round_over = False
                self.start_round(starting_player=random.choice([0,1]))
            elif e.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ---------------------------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                self.handle_global_keys(e)

            if not self.round_over and not self.match_over:
                self.handle_shot_input(events)
                self.update_logic()

            self.draw()

if __name__ == "__main__":
    Game().run()