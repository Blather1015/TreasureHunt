import pygame
import sys

# Initialize pygame
pygame.init()

# Set up the display
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("My First Pygame Window")

# Define colors
WHITE = (255, 255, 255)
RED = (200, 50, 50)

# Create a clock to control frame rate
clock = pygame.time.Clock()

# Game loop
while True:
    # 1. Handle events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    # 2. Update game state (movement, collisions, etc.)

    # 3. Draw
    screen.fill(WHITE)
    pygame.draw.circle(screen, RED, (WIDTH // 2, HEIGHT // 2), 50)

    # 4. Refresh the display
    pygame.display.flip()

    # 5. Limit FPS
    clock.tick(60)
