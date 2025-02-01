import pygame
import sys
import random
import json
import math
import datetime
from pygame.locals import *
from pygame import gfxdraw

pygame.init()
pygame.mixer.init()

# ----------------------------------------------------------------------------------
# CONSTANTS & GLOBALS
# ----------------------------------------------------------------------------------
WIDTH = 1280
HEIGHT = 720
CELL_SIZE = 24
FPS = 60
lore_timer = 0
lore_alpha = 0
lore_rain_particles = []
lore_fade_duration = 60

WHITE = (255, 255, 255)
NEON_BLUE = (0, 153, 255)
NEON_PINK = (255, 0, 127)
NEON_GREEN = (57, 255, 20)
DARK_BG = (15, 15, 25)
PARTICLE_COLORS = [(0, 255, 255), (255, 0, 255), (255, 255, 0)]

screen = pygame.display.set_mode((WIDTH, HEIGHT), DOUBLEBUF | HWSURFACE)
pygame.display.set_caption("Neon Snake")
clock = pygame.time.Clock()

# Game States
INTRO = -1 
MENU = 0
PLAYING = 1
GAME_OVER = 2
HIGH_SCORES = 3
MICROTRANSACTIONS = 4
CREDIT_CARD_FORM = 5
LORE = 6

current_state = INTRO   # Start in INTRO

# Power-up types
SPEED_BOOST = 0
SLOW_DOWN = 1
REVERSE_CONTROLS = 2
EXTRA_POINTS = 3
SHIELD = 4

def get_resource_path(relative_path):
    """ Get the correct path for resources, works for both development and PyInstaller .exe """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# Load fonts/sounds (falling back if missing)
try:
    font = pygame.font.Font(get_resource_path("resources/Orbitron-Medium.ttf"), 24)
    title_font = pygame.font.Font(get_resource_path("resources/Orbitron-Bold.ttf"), 72)
    
    bg_music = pygame.mixer.music.load(get_resource_path("resources/cyberpunk.mp3"))
    eat_sound = pygame.mixer.Sound(get_resource_path("resources/synth_beep.wav"))
    game_over_sound = pygame.mixer.Sound(get_resource_path("resources/low_boom.wav"))
    powerup_sound = pygame.mixer.Sound(get_resource_path("resources/power_up.mp3"))

except Exception as e:
    print(f"Missing assets: {e}")
    font = pygame.font.SysFont("arial", 24)
    title_font = pygame.font.SysFont("impact", 72)
    eat_sound = pygame.mixer.Sound(None)
    game_over_sound = pygame.mixer.Sound(None)
    powerup_sound = pygame.mixer.Sound(None)

# ----------------------------------------------------------------------------------
# MENU & BACKGROUND PARTICLES
# ----------------------------------------------------------------------------------
MENU_PARTICLES = []
GRID_POINTS = []
SCANLINE_Y = 0
TITLE_GLOW_PHASE = 0
HOLOGRAM_ANGLE = 0


LORE_PARTICLE_COUNT = 100  # tweak to your preference
lore_rain_particles = []
for _ in range(LORE_PARTICLE_COUNT):
    lore_rain_particles.append({
        "pos": [random.randint(0, WIDTH), random.randint(-HEIGHT, 0)],  # start negative y so they slowly appear
        "speed": random.uniform(2, 5),
        "brightness": random.randint(80, 255),
        "size": random.randint(1, 2)  # line thickness
    })

# Initialize menu-floating particles
for _ in range(200):
    MENU_PARTICLES.append({
        "pos": [random.randint(0, WIDTH), random.randint(0, HEIGHT)],
        "vel": [random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5)],
        "size": random.randint(1, 3),
        "color": random.choice(PARTICLE_COLORS),
        "alpha": random.randint(50, 150)
    })

# Grid points used for background
for gx in range(0, WIDTH, 40):
    for gy in range(0, HEIGHT, 40):
        GRID_POINTS.append((gx, gy))

# For "matrix rain" backgrounds on other screens
background_particles = []
for _ in range(100):
    background_particles.append({
        "pos": [random.randint(0, WIDTH), random.randint(0, HEIGHT)],
        "speed": random.uniform(1, 3),
        "brightness": random.randint(50, 255),
        "size": random.randint(1, 2)
    })

# ----------------------------------------------------------------------------------
# PARTICLE CLASS
# ----------------------------------------------------------------------------------
class Particle:
    def __init__(self, position, color, velocity, lifespan, size=4, glow=True):
        self.position = list(position)
        self.color = color
        self.velocity = list(velocity)
        self.lifespan = lifespan
        self.age = 0
        self.size = size
        self.glow = glow

    def update(self):
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        self.velocity[0] *= 0.98
        self.velocity[1] *= 0.98
        self.age += 1

    def draw(self, surface):
        alpha = 255 * (1 - self.age / self.lifespan)
        if alpha < 0:
            alpha = 0

        if self.glow:
            for i in range(3, 0, -1):
                radius = self.size + i * 2
                gfxdraw.filled_circle(
                    surface,
                    int(self.position[0]),
                    int(self.position[1]),
                    radius,
                    (*self.color, int(alpha // (i + 1)))
                )

        gfxdraw.filled_circle(
            surface,
            int(self.position[0]),
            int(self.position[1]),
            self.size,
            (*self.color, int(alpha))
        )

# ----------------------------------------------------------------------------------
# SNAKE (with sub-step movement)
# ----------------------------------------------------------------------------------
class Snake:
    def __init__(self):
        self.reset()
        
    def reset(self):
        start_x = (WIDTH // CELL_SIZE // 2) * CELL_SIZE
        start_y = (HEIGHT // CELL_SIZE // 2) * CELL_SIZE
        self.body = [(start_x, start_y)]
        
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.length = 1
        self.speed = 5
        
        self.score = 0
        self.power_up = None
        self.power_up_timer = 0
        self.shield = False
        self.trail_particles = []
        
    def move(self, game):
        """ Move the snake one cell (CELL_SIZE) in sub-steps of 1 pixel each. """
        if self.power_up_timer > 0:
            self.power_up_timer -= 1
            if self.power_up_timer == 0:
                self.remove_power_up()
        
        self.direction = self.next_direction
        dx, dy = self.direction
        old_x, old_y = self.body[0]

        if dx == 0 and dy == 0:
            return

        steps = CELL_SIZE
        dx_pixel = dx
        dy_pixel = dy
        current_x = old_x
        current_y = old_y

        for _ in range(steps):
            # Move 1 pixel
            new_x = (current_x + dx_pixel) % WIDTH
            new_y = (current_y + dy_pixel) % HEIGHT
            current_x, current_y = new_x, new_y

            # Check for food at each pixel step
            game.check_food_collision_at(current_x, current_y)

        # Snap final position to the grid
        final_x = (current_x // CELL_SIZE) * CELL_SIZE
        final_y = (current_y // CELL_SIZE) * CELL_SIZE
        self.body.insert(0, (final_x, final_y))

        # Debug print final head
        print(f"[DEBUG] Snake final head = {self.body[0]}  (sub-steps from ({old_x},{old_y}))")

        # Particle trail from old position
        for _ in range(3):
            self.trail_particles.append(
                Particle(
                    (old_x + CELL_SIZE // 2, old_y + CELL_SIZE // 2),
                    random.choice(PARTICLE_COLORS),
                    (random.uniform(-1, 1), random.uniform(-1, 1)),
                    random.randint(15, 25),
                    size=2,
                    glow=True
                )
            )

        if len(self.body) > self.length:
            self.body.pop()
            
    def check_collision(self):
        if not self.shield:
            return len(self.body) != len(set(self.body))
        return False
    
    def apply_power_up(self, power_type):
        # Remove any existing power-up
        if self.power_up is not None:
            self.remove_power_up()
        
        if power_type == SPEED_BOOST:
            self.speed *= 1.5
            self.power_up = SPEED_BOOST
            self.power_up_timer = 30 * FPS  # 30 seconds
        elif power_type == SHIELD:
            self.shield = True
            self.power_up = SHIELD
            self.power_up_timer = 30 * FPS
        elif power_type == -1:  # Extra Life
            self.has_extra_life_active = True
        if powerup_sound:
            powerup_sound.play()
            
    def remove_power_up(self):
        if self.power_up == SPEED_BOOST:
            self.speed /= 1.5
        elif self.power_up == SHIELD:
            self.shield = False
        self.power_up = None
        self.power_up_timer = 0

# ----------------------------------------------------------------------------------
# FOOD
# ----------------------------------------------------------------------------------
class Food:
    def __init__(self):
        self.position = (0, 0)
        self.color = NEON_GREEN
        self.animation_time = 0
        self.spawn()
        
    def spawn(self):
        self.position = (
            random.randint(0, (WIDTH - CELL_SIZE) // CELL_SIZE) * CELL_SIZE,
            random.randint(0, (HEIGHT - CELL_SIZE) // CELL_SIZE) * CELL_SIZE
        )
        self.animation_time = 0
        print(f"[DEBUG] Food spawned at {self.position}")
        
    def draw(self, surface):
        self.animation_time += 1
        size = CELL_SIZE + math.sin(self.animation_time / 10) * 5
        center = (self.position[0] + CELL_SIZE // 2, self.position[1] + CELL_SIZE // 2)
        
        for i in range(5):
            alpha = 50 - i * 10
            radius = int(size + i * 3)
            gfxdraw.filled_circle(surface, center[0], center[1], radius, (*self.color, alpha))

        gfxdraw.filled_circle(surface, center[0], center[1], int(size / 2), self.color)
        gfxdraw.aacircle(surface, center[0], center[1], int(size / 2), self.color)

# ----------------------------------------------------------------------------------
# POWERUP
# ----------------------------------------------------------------------------------
class PowerUp:
    def __init__(self):
        self.position = (0, 0)
        self.type = random.choice([SPEED_BOOST, SLOW_DOWN, REVERSE_CONTROLS, EXTRA_POINTS, SHIELD])
        self.animation_time = 0
        self.spawn()
        self.timer = 600
        
    def spawn(self):
        self.position = (
            random.randint(0, (WIDTH - CELL_SIZE) // CELL_SIZE) * CELL_SIZE,
            random.randint(0, (HEIGHT - CELL_SIZE) // CELL_SIZE) * CELL_SIZE
        )
        
    def get_color(self):
        colors = {
            SPEED_BOOST: NEON_BLUE,
            SLOW_DOWN: (255, 50, 50),
            REVERSE_CONTROLS: NEON_PINK,
            EXTRA_POINTS: (255, 215, 0),
            SHIELD: (0, 255, 255)
        }
        return colors[self.type]
    
    def draw(self, surface):
        self.animation_time += 1
        center = (self.position[0] + CELL_SIZE // 2, self.position[1] + CELL_SIZE // 2)
        angle = math.radians(self.animation_time * 5)
        
        for i in range(3):
            radius = CELL_SIZE // 2 + math.sin(self.animation_time / 10 + i) * 5
            x = center[0] + math.cos(angle + i * 2) * radius
            y = center[1] + math.sin(angle + i * 2) * radius
            gfxdraw.filled_circle(surface, int(x), int(y), 3, self.get_color())

        gfxdraw.filled_circle(surface, center[0], center[1], CELL_SIZE // 3, self.get_color())

# ----------------------------------------------------------------------------------
# GAME
# ----------------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.snake = Snake()
        self.food = Food()
        self.power_ups = []
        self.high_scores = self.load_high_scores()
        self.particles = []
        self.screen_shake = 0
        
        self.coins = 300
        
        self.inventory = {
           "Shield": 0,
           "Speed Boost": 0,
           "Extra Life": 0
        }

    def load_high_scores(self):
        try:
            with open("high_scores.json", "r") as f:
                return json.load(f)
        except:
            return []
            
    def save_high_scores(self):
        with open("high_scores.json", "w") as f:
            json.dump(self.high_scores, f)
            
    def reset(self):
        self.snake.reset()
        self.food.spawn()
        self.power_ups = []
        self.particles = []
        
    def draw_inventory_hud(self):
        """Draw a small panel listing how many items we have: Shield, Speed, Extra Life."""
        panel_w = 220
        panel_h = 120
        x,y=20,90
        shape=pygame.Surface((panel_w,panel_h), pygame.SRCALPHA)
        pygame.draw.rect(shape,(255,255,255,15),(0,0,panel_w,panel_h), border_radius=15)
        pygame.draw.rect(shape,(255,255,255,30),(0,0,panel_w,panel_h),2, border_radius=15)
        screen.blit(shape,(x,y))

        # Lines of text
        # 1 => Shield, 2 => Speed, 3 => Extra Life
        lines = [
            f"1) Shield: {self.inventory['Shield']}",
            f"2) Speed : {self.inventory['Speed Boost']}",
            f"3) Ex. Life: {self.inventory['Extra Life']}",
        ]
        y_off= y+10
        for line in lines:
            txt_surf=font.render(line, True, (255,255,255))
            screen.blit(txt_surf, (x+10, y_off))
            y_off+=30
        
    def draw_background(self):
        screen.fill(DARK_BG)
        for x in range(0, WIDTH, 80):
            pygame.draw.line(screen, (25, 25, 35), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, 80):
            pygame.draw.line(screen, (25, 25, 35), (0, y), (WIDTH, y))
        global SCANLINE_Y
        SCANLINE_Y += 4
        if SCANLINE_Y > HEIGHT:
            SCANLINE_Y = 0
        pygame.draw.line(screen, (255, 255, 255, 25), (0, SCANLINE_Y), (WIDTH, SCANLINE_Y))
        
    def draw(self):
        self.draw_background()
        for p in self.particles:
            p.update()
            p.draw(screen)
        self.particles = [p for p in self.particles if p.age < p.lifespan]

        for p in self.snake.trail_particles:
            p.update()
            p.draw(screen)
        self.snake.trail_particles = [p for p in self.snake.trail_particles if p.age < p.lifespan]
        
        # Snake
        for (x, y) in self.snake.body:
            color = NEON_GREEN if not self.snake.shield else (0, 255, 255)
            for j in range(3):
                gfxdraw.filled_circle(
                    screen, x + CELL_SIZE // 2, y + CELL_SIZE // 2,
                    (CELL_SIZE // 2 + 2) + j * 2,
                    (*color, 50 - j * 15)
                )
            gfxdraw.filled_circle(
                screen, x + CELL_SIZE // 2, y + CELL_SIZE // 2,
                CELL_SIZE // 2 + 2, color
            )
            gfxdraw.aacircle(
                screen, x + CELL_SIZE // 2, y + CELL_SIZE // 2,
                CELL_SIZE // 2 + 2, color
            )

        # Food
        self.food.draw(screen)

        # Power-ups
        for pu in self.power_ups:
            pu.draw(screen)
            
        self.draw_glass_panel(20, 20, 200, 60, 20)
        score_text = font.render(f"SCORE: {self.snake.score}", True, NEON_BLUE)
        screen.blit(score_text, (40, 35))
        
        self.draw_inventory_hud()
        
        if self.screen_shake > 0:
            self.screen_shake -= 1

    def draw_glass_panel(self, x, y, w, h, radius):
        shape = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(shape, (255, 255, 255, 15), (0, 0, w, h), border_radius=radius)
        pygame.draw.rect(shape, (255, 255, 255, 30), (0, 0, w, h), 2, border_radius=radius)
        screen.blit(shape, (x, y))

    def check_food_collision_at(self, px, py):
        """Called every sub-step from snake.move. If (px,py) hits the food's cell, eat it."""
        cell_x = (px // CELL_SIZE) * CELL_SIZE
        cell_y = (py // CELL_SIZE) * CELL_SIZE

        if (cell_x, cell_y) == self.food.position:
            self.snake.length += 1
            self.snake.score += 10
            self.food.spawn()
            if eat_sound:
                eat_sound.play()
            self.screen_shake = 5

            center = (cell_x + CELL_SIZE // 2, cell_y + CELL_SIZE // 2)
            for _ in range(20):
                self.particles.append(
                    Particle(
                        center,
                        random.choice(PARTICLE_COLORS),
                        (random.uniform(-3, 3), random.uniform(-3, 3)),
                        random.randint(20, 30),
                        size=3,
                        glow=True
                    )
                )
            if random.random() < 0.3 and len(self.power_ups) < 2:
                self.power_ups.append(PowerUp())

    def check_power_up_collision(self):
        for pu in self.power_ups[:]:
            if self.snake.body[0] == pu.position:
                self.snake.apply_power_up(pu.type)
                if pu.type == EXTRA_POINTS:
                    self.snake.score += 50
                self.power_ups.remove(pu)
                if powerup_sound:
                    powerup_sound.play()

# ----------------------------------------------------------------------------------
# MICROTRANSACTIONS / SHOP
# ----------------------------------------------------------------------------------
POWERUP_ITEMS = [
    {
        "type": "item",
        "title": "Shield",
        "cost_coins": 100,
        "desc": "Protects you temporarily."
    },
    {
        "type": "item",
        "title": "Speed Boost",
        "cost_coins": 150,
        "desc": "Increases speed temporarily."
    },
    {
        "type": "item",
        "title": "Extra Life",
        "cost_coins": 200,
        "desc": "Survive one collision."
    },
]
COIN_PACKAGES = [
    {
        "type": "coins",
        "title": "$2.99 => +300 coins",
        "price": 2.99,
        "coins": 300
    },
    {
        "type": "coins",
        "title": "$9.99 => +1000 coins",
        "price": 9.99,
        "coins": 1000
    },
    {
        "type": "coins",
        "title": "$19.99 => +2500 coins",
        "price": 19.99,
        "coins": 2500
    },
    {
        "type": "coins",
        "title": "$49.99 => +7000 coins",
        "price": 49.99,
        "coins": 7000
    },
    {
        "type": "coins",
        "title": "$99.99 => +15000 coins",
        "price": 99.99,
        "coins": 15000
    },
]

def draw_heading(surface, text, x, y):
    heading_surf = font.render(text, True, NEON_BLUE)
    surface.blit(heading_surf, (x, y))

def draw_microtransactions_screen(game, scroll_offset, 
                                  pending_item, 
                                  purchase_confirm, 
                                  purchase_message):
    """
    Renders the shop in two separate sections: 
     - 'IN-GAME POWER-UPS'
     - 'COIN PACKAGES'
    Each is drawn in a 2-column layout, with a scrollbar.
    If `pending_item` is not None, a "confirmation popup" is drawn.
    If `purchase_message` is set, a "result popup" is drawn.
    Returns possibly updated scroll_offset.
    """
    # Matrix-rain background
    screen.fill(DARK_BG)
    for p in background_particles:
        p["pos"][1] += p["speed"]
        if p["pos"][1] > HEIGHT:
            p["pos"][1] = 0
            p["brightness"] = random.randint(50, 255)
        alpha = p["brightness"]
        pygame.draw.line(
            screen, (0, alpha, 0),
            (p["pos"][0], p["pos"][1]),
            (p["pos"][0], p["pos"][1] + 15),
            p["size"]
        )

    title_surf = title_font.render("SHOP", True, NEON_BLUE)
    screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 40))

    coin_text = font.render(f"Coins: {game.coins}", True, WHITE)
    screen.blit(coin_text, (50, 50))

    SCROLL_LEFT = 100
    SCROLL_TOP = 140
    SCROLL_WIDTH = 1000
    SCROLL_HEIGHT = HEIGHT - 250

    boundary_rect = pygame.Rect(SCROLL_LEFT, SCROLL_TOP, SCROLL_WIDTH, SCROLL_HEIGHT)
    pygame.draw.rect(screen, (30, 30, 50), boundary_rect, 2)

    scroll_surface = pygame.Surface((SCROLL_WIDTH, SCROLL_HEIGHT), pygame.SRCALPHA)
    scroll_surface.fill((0, 0, 0, 0))

    # Each item is 450 wide x 100 tall, 2 columns
    item_width = 450
    item_height = 100
    x_spacing = (SCROLL_WIDTH - (2 * item_width)) // 3
    columns = 2

    y_offset = 0

    # ---- Section 1: POWERUP ITEMS ----
    draw_heading(scroll_surface, "IN-GAME POWER-UPS", 10, 0 - scroll_offset)
    y_offset = 40

    total_powerups = len(POWERUP_ITEMS)
    rows_pu = (total_powerups + columns - 1) // columns
    powerup_height = rows_pu * item_height

    y_offset_pu_start = y_offset
    for i, item in enumerate(POWERUP_ITEMS):
        row = i // columns
        col = i % columns
        # Center items with proper spacing
        x_pos = x_spacing + col * (item_width + x_spacing)
        y_pos = y_offset + row * item_height
        
        item_rect = pygame.Rect(x_pos, y_pos - scroll_offset, item_width, item_height)

        if item_rect.bottom < 0 or item_rect.top > SCROLL_HEIGHT:
            continue

        pygame.draw.rect(scroll_surface, (30, 30, 50), item_rect, border_radius=8)
        pygame.draw.rect(scroll_surface, NEON_BLUE, item_rect, 2, border_radius=8)
        txt = f"{item['title']} - {item['cost_coins']} coins"
        desc = item["desc"]

        txt_surf = font.render(txt, True, NEON_GREEN)
        scroll_surface.blit(txt_surf, (item_rect.x + 15, item_rect.y + 10))

        if desc:
            desc_surf = font.render(desc, True, (200, 200, 200))
            scroll_surface.blit(desc_surf, (item_rect.x + 15, item_rect.y + 45))

        buy_w, buy_h = 80, 35
        buy_x = item_rect.right - buy_w - 15
        buy_y = item_rect.y + (item_height - buy_h)//2
        
        max_text_width = item_width - buy_w - 30  # 15px padding on both sides
        txt = f"{item['title']} - {item['cost_coins']} coins"
        txt_surf = font.render(txt, True, NEON_GREEN)
        if txt_surf.get_width() > max_text_width:
            # Shorten text with ellipsis
            txt = font.render(txt, True, NEON_GREEN)
            while txt_surf.get_width() > max_text_width and len(txt) > 3:
                txt = txt[:-4] + "..."
                txt_surf = font.render(txt, True, NEON_GREEN)
        scroll_surface.blit(txt_surf, (item_rect.x + 15, item_rect.y + 10))
        
        
        buy_rect = pygame.Rect(buy_x, buy_y, buy_w, buy_h)
        pygame.draw.rect(scroll_surface, NEON_BLUE, buy_rect, border_radius=8)
        buy_text_surf = font.render("BUY", True, WHITE)
        buy_text_rect = buy_text_surf.get_rect(center=buy_rect.center)
        scroll_surface.blit(buy_text_surf, buy_text_rect)

        # Store for click detection
        item["drawn_rect"] = item_rect.copy()
        item["buy_rect"] = buy_rect.copy()

    y_offset += powerup_height
    y_offset += 20  # a small gap between categories

    # Now draw "COIN PACKAGES" heading
    draw_heading(scroll_surface, "COIN PACKAGES", 10, y_offset - scroll_offset)
    y_offset += 40  # leave room for heading

    total_coins = len(COIN_PACKAGES)
    rows_cp = (total_coins + columns - 1) // columns
    coinpack_height = rows_cp * item_height

    y_offset_cp_start = y_offset
    for i, pack in enumerate(COIN_PACKAGES):
        row = i // columns
        col = i % columns
        # Center items with proper spacing
        x_pos = x_spacing + col * (item_width + x_spacing)
        y_pos = y_offset + row * item_height
        
        item_rect = pygame.Rect(x_pos, y_pos - scroll_offset, item_width, item_height)

        if item_rect.bottom < 0 or item_rect.top > SCROLL_HEIGHT:
            continue

        pygame.draw.rect(scroll_surface, (30, 30, 50), item_rect, border_radius=8)
        pygame.draw.rect(scroll_surface, NEON_BLUE, item_rect, 2, border_radius=8)

        txt_surf = font.render(pack["title"], True, NEON_GREEN)
        scroll_surface.blit(txt_surf, (item_rect.x + 15, item_rect.y + 10))

        # Entire item is clickable
        pack["drawn_rect"] = item_rect.copy()
        pack["buy_rect"] = item_rect.copy()

    y_offset += coinpack_height

    # total content height
    total_height = y_offset + coinpack_height

    # Blit scroll_surface
    screen.blit(scroll_surface, (SCROLL_LEFT, SCROLL_TOP))

    # Scrollbar
    if total_height > SCROLL_HEIGHT:
        track_height = SCROLL_HEIGHT
        thumb_height = max(int(track_height * (track_height / float(total_height))), 20)
        max_scroll = total_height - SCROLL_HEIGHT
        if scroll_offset > max_scroll:
            scroll_offset = max_scroll
        scroll_ratio = scroll_offset / float(max_scroll) if max_scroll > 0 else 0
        thumb_y = SCROLL_TOP + int((track_height - thumb_height) * scroll_ratio)
        scrollbar_rect = pygame.Rect(SCROLL_LEFT + SCROLL_WIDTH - 8, thumb_y, 8, thumb_height)
        pygame.draw.rect(screen, (80,80,80), scrollbar_rect, border_radius=4)

    # ESC to menu text
    esc_text_surf = font.render("Press ESC to return to menu", True, NEON_BLUE)
    screen.blit(esc_text_surf, (WIDTH // 2 - esc_text_surf.get_width() // 2, HEIGHT - 50))

    # -------------- Purchase Confirmation Popup --------------
    # If user clicked BUY, we ask "Are you sure you want to buy...?"
    if pending_item is not None and purchase_confirm:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,180))
        screen.blit(overlay, (0,0))

        # Popup box
        box_w, box_h = 600, 200
        box_rect = pygame.Rect(0,0, box_w, box_h)
        box_rect.center = (WIDTH//2, HEIGHT//2)
        pygame.draw.rect(screen, (30,30,50), box_rect, border_radius=12)
        pygame.draw.rect(screen, NEON_BLUE, box_rect, 3, border_radius=12)

        # Title
        confirm_txt = f"Are you sure you want to purchase?"
        confirm_surf = font.render(confirm_txt, True, WHITE)
        screen.blit(confirm_surf, (box_rect.centerx - confirm_surf.get_width()//2, box_rect.y+20))

        if pending_item["type"] == "item":
            cost_str = f"{pending_item['title']} for {pending_item['cost_coins']} coins?"
        else:
            cost_str = f"{pending_item['title']}?"  # coin package

        cost_surf = font.render(cost_str, True, NEON_GREEN)
        screen.blit(cost_surf, (box_rect.centerx - cost_surf.get_width()//2, box_rect.y+60))

        # Yes / No buttons
        btn_w, btn_h = 120, 50
        yes_rect = pygame.Rect(0,0, btn_w, btn_h)
        yes_rect.center = (box_rect.centerx - 80, box_rect.centery+40)
        no_rect = pygame.Rect(0,0, btn_w, btn_h)
        no_rect.center = (box_rect.centerx + 80, box_rect.centery+40)

        pygame.draw.rect(screen, NEON_BLUE, yes_rect, border_radius=8)
        pygame.draw.rect(screen, NEON_BLUE, no_rect, border_radius=8)

        yes_surf = font.render("YES", True, WHITE)
        no_surf = font.render("NO", True, WHITE)
        yes_rect_txt = yes_surf.get_rect(center=yes_rect.center)
        no_rect_txt = no_surf.get_rect(center=no_rect.center)
        screen.blit(yes_surf, yes_rect_txt)
        screen.blit(no_surf, no_rect_txt)

        return scroll_offset  # Return now, after drawing popup

    # -------------- Purchase Result Popup --------------
    # If there's a purchase message (e.g. "Not enough coins" or "Purchase successful")
    if purchase_message:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,180))
        screen.blit(overlay, (0,0))

        box_w, box_h = 500, 150
        box_rect = pygame.Rect(0,0, box_w, box_h)
        box_rect.center = (WIDTH//2, HEIGHT//2)
        pygame.draw.rect(screen, (30,30,50), box_rect, border_radius=12)
        pygame.draw.rect(screen, NEON_BLUE, box_rect, 3, border_radius=12)

        msg_surf = font.render(purchase_message, True, NEON_GREEN)
        screen.blit(msg_surf, (box_rect.centerx - msg_surf.get_width()//2, box_rect.y+40))

        # OK button
        ok_w, ok_h = 100, 40
        ok_rect = pygame.Rect(0,0, ok_w, ok_h)
        ok_rect.center = (box_rect.centerx, box_rect.centery+30)
        pygame.draw.rect(screen, NEON_BLUE, ok_rect, border_radius=8)
        ok_surf = font.render("OK", True, WHITE)
        ok_rect_txt = ok_surf.get_rect(center=ok_rect.center)
        screen.blit(ok_surf, ok_rect_txt)

    return scroll_offset

def draw_cyber_button(text, position, hover=False):
    x, y = position
    time = pygame.time.get_ticks() / 1000
    size_factor = 1 + 0.1 * math.sin(time * 5) if hover else 1

    btn_rect = pygame.Rect(0, 0, 300, 60)
    btn_rect.center = (x, y)
    
    border_color = NEON_BLUE
    pygame.draw.rect(screen, border_color, btn_rect, 3, border_radius=15)
    if hover:
        pygame.draw.rect(screen, (*border_color, 50), btn_rect, border_radius=15)

    text_surf = font.render(text, True, NEON_PINK)
    text_rect = text_surf.get_rect(center=(x,y))
    shadow_surf = font.render(text, True, (0,0,0))
    screen.blit(shadow_surf, text_rect.move(2,2))
    screen.blit(text_surf, text_rect)

def draw_menu():
    global SCANLINE_Y, TITLE_GLOW_PHASE, HOLOGRAM_ANGLE, MENU_PARTICLES

    screen.fill(DARK_BG)
    
    mouse_x, mouse_y = pygame.mouse.get_pos()
    for (gx, gy) in GRID_POINTS:
        dist = math.hypot(gx - mouse_x, gy - mouse_y)
        intensity = 50 - min(dist / 20, 50)
        if intensity < 0:
            intensity = 0
        pygame.draw.circle(screen, (25, 25, 35), (gx, gy), 1)

    for p in MENU_PARTICLES:
        p["pos"][0] += p["vel"][0]
        p["pos"][1] += p["vel"][1]
        p["pos"][0] %= WIDTH
        p["pos"][1] %= HEIGHT
        gfxdraw.filled_circle(screen, int(p["pos"][0]), int(p["pos"][1]),
                              p["size"], (*p["color"], p["alpha"]))
    
    TITLE_GLOW_PHASE += 0.05
    title_text = "NEON SNAKE"
    title_surf = title_font.render(title_text, True, NEON_BLUE)
    title_rect = title_surf.get_rect(center=(WIDTH//2, 150))

    for i in range(20, 0, -1):
        glow_color = (
            int(127 + 127 * math.sin(TITLE_GLOW_PHASE + i/5)),
            int(127 + 127 * math.sin(TITLE_GLOW_PHASE + i/3 + 2)),
            255
        )
        glow_surf = title_font.render(title_text, True, glow_color)
        offset = i * 2 * math.sin(TITLE_GLOW_PHASE + i / 3)
        screen.blit(glow_surf, title_rect.move(offset, -offset))

    screen.blit(title_surf, title_rect)

    buttons = [
        ("TERMINAL START", (WIDTH // 2, 300), NEON_GREEN),  
        ("DATA ARCHIVES", (WIDTH // 2, 380), NEON_BLUE),    
        ("CREDIT CHIP", (WIDTH // 2, 460), NEON_PINK),       
        ("SYSTEM EXIT", (WIDTH // 2, 540), (255, 50, 50))    
    ]
    mx, my = pygame.mouse.get_pos()
    for text, (bx, by), color in buttons:
        btn_rect = pygame.Rect(0, 0, 340, 70)
        btn_rect.center = (bx, by)
        hover = btn_rect.collidepoint(mx, my)
        draw_cyber_button(text, (bx, by), hover)

    HOLOGRAM_ANGLE += 0.02
    for i in range(3):
        size = 100 + i*50
        pos = (WIDTH//2 + math.cos(HOLOGRAM_ANGLE + i)*100,
               150 + math.sin(HOLOGRAM_ANGLE + i)*50)
        pygame.draw.ellipse(screen, NEON_PINK,
                            (pos[0]-size//2, pos[1]-size//4, size, size//2), 2)
                            
                            
def draw_intro_screen(alpha):
    black_surf= pygame.Surface((WIDTH, HEIGHT))
    black_surf.fill((0,0,0))
    screen.blit(black_surf, (0,0))

    text="Neon Snake 2 By Lunar"
    intro_font=pygame.font.SysFont("impact",60)
    color=(255,255,255)

    text_surf=intro_font.render(text, True, color)
    text_rect=text_surf.get_rect(center=(WIDTH//2, HEIGHT//2))

    fade_surface=pygame.Surface(text_surf.get_size(), SRCALPHA)
    fade_surface.blit(text_surf,(0,0))
    fade_surface.set_alpha(alpha)
    screen.blit(fade_surface, text_rect)

# ----------------------------------------------------------------------------------
# LORE SCREEN (NEW)
# ----------------------------------------------------------------------------------
lore_text_lines = [
    "The year is 2099. Neon floods every street corner,",
    "and the city pulses with electricity and data streams.",
    "In a hidden VR realm, you pilot the legendary Snake,",
    "collecting data orbs while evading your own trail,",
    "all to survive in this digital neon wasteland...",
    "",
    "Press ENTER to begin the mission."
]

def draw_lore_screen():
    global lore_timer, lore_alpha

    # (A) Increment the timer for fade
    lore_timer += 1
    if lore_timer < lore_fade_duration:
        lore_alpha = int((lore_timer / lore_fade_duration) * 255)
    else:
        lore_alpha = 255  # hold at full opacity

    # (B) Draw the background black first
    screen.fill((0, 0, 0))

    # (C) Update & draw the green “data rain” lines
    for p in lore_rain_particles:
        p["pos"][1] += p["speed"]  # move down
        if p["pos"][1] > HEIGHT:
            # reset to top
            p["pos"][1] = random.randint(-100, 0)
            p["pos"][0] = random.randint(0, WIDTH)
            p["speed"] = random.uniform(2, 5)
            p["brightness"] = random.randint(80, 255)
            p["size"] = random.randint(1,2)

        alpha = p["brightness"]
        # We'll draw them as vertical lines, e.g. 15 px long for a "vertical stream"
        line_length = 15
        line_color = (0, alpha, 0)  # bright green
        start_x = int(p["pos"][0])
        start_y = int(p["pos"][1])
        end_y = start_y + line_length
        pygame.draw.line(screen, line_color, (start_x, start_y), (start_x, end_y), p["size"])

    # (D) Now draw the LORE text lines as a single surface with fade alpha
    lore_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    
    lines = [
        "The year is 2099. Neon floods every street corner,",
        "and the city pulses with electricity and data streams.",
        "In a hidden VR realm, you pilot the legendary Snake,",
        "collecting data orbs while evading your own trail,",
        "all to survive in this digital neon wasteland...",
        "",
        "Press ENTER to begin the mission."
    ]
    
    y_start = 180
    line_spacing = 40
    for i, line in enumerate(lines):
        line_surf = font.render(line, True, NEON_BLUE)
        line_rect = line_surf.get_rect(center=(WIDTH//2, y_start + i*line_spacing))
        lore_surface.blit(line_surf, line_rect)

    lore_surface.set_alpha(lore_alpha)
    screen.blit(lore_surface, (0, 0))


# ----------------------------------------------------------------------------------
# CREDIT CARD FORM
# ----------------------------------------------------------------------------------
def validate_card_info(card_info):
    name, number, expiry, cvv = card_info
    if not name.strip():
        return False, "Name on card cannot be empty."
    if not number.isdigit() or len(number) != 16:
        return False, "Card number must be 16 digits."
    if not cvv.isdigit() or len(cvv) != 3:
        return False, "CVV must be 3 digits."

    parts = expiry.split("/")
    if len(parts) != 2:
        return False, "Expiry must be MM/YY."
    mm, yy = parts
    if not (mm.isdigit() and yy.isdigit()):
        return False, "Expiry must have numeric MM and YY."
    month = int(mm)
    year = 2000
    if len(yy) == 2:
        year = int("20"+yy)

    now = datetime.datetime.now()
    if month < 1 or month > 12:
        return False, "Invalid month."
    if year < now.year or (year == now.year and month <= now.month):
        return False, "Expiry is not after current month."
    return True, ""

def draw_credit_card_form(game, card_info, active_field, form_rects,
                          processing, processing_countdown, error_message,
                          success, selected_package):
    screen.fill(DARK_BG)
    for p in background_particles:
        p["pos"][1] += p["speed"]
        if p["pos"][1] > HEIGHT:
            p["pos"][1] = 0
            p["brightness"] = random.randint(50, 255)
        alpha = p["brightness"]
        pygame.draw.line(screen, (0, alpha, 0),
                         (p["pos"][0], p["pos"][1]),
                         (p["pos"][0], p["pos"][1]+15),
                         p["size"])

    back_btn_rect = pygame.Rect(20, 20, 80, 40)
    pygame.draw.rect(screen, (80,80,80), back_btn_rect, border_radius=8)
    back_text = font.render("BACK", True, WHITE)
    screen.blit(back_text, back_btn_rect.move(10,5))

    title_surf = title_font.render("ENTER CARD INFO", True, NEON_BLUE)
    screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 40))

    if selected_package and selected_package.get("type") == "coins":
        pkg_str = f"{selected_package['title']} ({selected_package['coins']} coins)"
        pkg_surf = font.render(f"Package: {pkg_str}", True, WHITE)
        screen.blit(pkg_surf, (WIDTH//2 - pkg_surf.get_width()//2, 120))

    if processing:
        proc_surf = font.render("PROCESSING TRANSACTION...", True, WHITE)
        proc_rect = proc_surf.get_rect(center=(WIDTH//2, HEIGHT//2))
        screen.blit(proc_surf, proc_rect)
        angle = (pygame.time.get_ticks() // 10) % 360
        radius = 40
        cx, cy = WIDTH//2, HEIGHT//2+80
        for i in range(12):
            a = math.radians(angle + i*30)
            dot_x = cx + math.cos(a)*radius
            dot_y = cy + math.sin(a)*radius
            color_factor = 255 - i*10
            pygame.draw.circle(screen, (color_factor,color_factor,color_factor), (int(dot_x),int(dot_y)), 5)
        return

    if success:
        success_surf = font.render("TRANSACTION SUCCESSFUL!", True, (0,255,0))
        screen.blit(success_surf, (WIDTH//2 - success_surf.get_width()//2, HEIGHT//2))
        note_surf = font.render("Press any key to continue...", True, WHITE)
        screen.blit(note_surf, (WIDTH//2 - note_surf.get_width()//2, HEIGHT//2+40))
        return

    labels = ["Name on Card:", "Card Number (16 digits):", "Expiry (MM/YY):", "CVV (3 digits):"]
    for i, label in enumerate(labels):
        y = form_rects[i].y
        lbl_surf = font.render(label, True, WHITE)
        screen.blit(lbl_surf, (form_rects[i].x - 300, y))

        pygame.draw.rect(screen, (50,50,80), form_rects[i], border_radius=8)
        if i == active_field:
            pygame.draw.rect(screen, NEON_BLUE, form_rects[i], 3, border_radius=8)
        else:
            pygame.draw.rect(screen, (150,150,150), form_rects[i], 3, border_radius=8)

        display_text = card_info[i]
        while True:
            text_surf = font.render(display_text, True, WHITE)
            if text_surf.get_width() <= (form_rects[i].width - 20):
                break
            display_text = display_text[1:]
        screen.blit(text_surf, (form_rects[i].x+10, form_rects[i].y+5))

    if error_message:
        err_surf = font.render(error_message, True, (255,0,0))
        screen.blit(err_surf, (WIDTH//2 - err_surf.get_width()//2, 500))

    inst_surf = font.render("Click a field to edit. Press Enter/Tab to next. ESC to cancel.",
                            True, NEON_BLUE)
    screen.blit(inst_surf, (WIDTH//2 - inst_surf.get_width()//2, HEIGHT-60))
    
def draw_intro_screen(alpha):
    """
    Renders a fancy introduction: "Neon Snake 2 By Lunar"
    We'll fade in from black to alpha=255, hold, fade out.
    alpha param is 0..255 controlling text opacity.
    The background also fades out/in with black overlay if you want.
    """
    # Fill black
    black_surface = pygame.Surface((WIDTH, HEIGHT))
    black_surface.fill((0,0,0))
    screen.blit(black_surface, (0,0))

    # The text
    text = "Neon Snake 2 By Lunar"
    intro_font=pygame.font.SysFont("impact",60)
    color=(255,255,255)

    text_surf=intro_font.render(text, True, color)
    text_rect=text_surf.get_rect(center=(WIDTH//2, HEIGHT//2))

    # We'll apply alpha
    fade_surface=pygame.Surface(text_surf.get_size(), SRCALPHA)
    fade_surface.blit(text_surf,(0,0))
    fade_surface.set_alpha(alpha)
    screen.blit(fade_surface, text_rect)

# ----------------------------------------------------------------------------------
# MAIN LOOP
# ----------------------------------------------------------------------------------
def main():
    global current_state
    game = Game()
    if pygame.mixer.music.get_busy() == 0:
        pygame.mixer.music.play(-1)
    
    name_input = ""
    snake_time_accumulator = 0.0
    TARGET_FPS = 60

    # For credit card form:
    card_info = ["","","",""]
    active_field = 0
    processing = False
    processing_countdown = 0
    error_message = ""
    success = False
    selected_package = None
    form_rects = [
        pygame.Rect(500, 200, 300, 40),
        pygame.Rect(500, 260, 300, 40),
        pygame.Rect(500, 320, 300, 40),
        pygame.Rect(500, 380, 300, 40),
    ]

    shop_scroll_offset = 0
    pending_item = None
    purchase_confirm = False
    purchase_message = ""
    
    # INTRO variables
    intro_timer=0   # total frames in intro
    intro_duration=3*60  # 3 seconds at 60 fps => 180 frames
    # We'll do: fade in (0->1s), hold (1->2s), fade out(2->3s)

    while True:
        dt = clock.tick(TARGET_FPS) / 1000.0
        snake_time_accumulator += dt

        # ========== EVENT HANDLING ==========
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()

            # If we are in INTRO, skip events except QUIT.
            if current_state == INTRO:
                continue
                
            if current_state==LORE:
                if event.type==KEYDOWN:
                    if event.key in (K_RETURN,K_SPACE):
                        current_state=PLAYING
                continue

            if current_state == MENU:
                if event.type == MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    menu_buttons = [
                        ("TERMINAL START", pygame.Rect(0,0,340,70), (WIDTH//2,300), LORE),
                        ("DATA ARCHIVES", pygame.Rect(0,0,340,70), (WIDTH//2,380), HIGH_SCORES),
                        ("CREDIT CHIP",    pygame.Rect(0,0,340,70), (WIDTH//2,460), MICROTRANSACTIONS),
                        ("SYSTEM EXIT",    pygame.Rect(0,0,340,70), (WIDTH//2,540), None)
                    ]
                    for text, rect, center_pos, next_state in menu_buttons:
                        rect.center = center_pos
                        if rect.collidepoint(mx,my):
                            if text == "SYSTEM EXIT":
                                pygame.quit()
                                sys.exit()
                            elif text == "TERMINAL START":
                                current_state = LORE
                                game.reset()
                            elif text == "DATA ARCHIVES":
                                current_state = HIGH_SCORES
                            elif text == "CREDIT CHIP":
                                current_state = MICROTRANSACTIONS

            elif current_state == PLAYING:
                if event.type == KEYDOWN:
                    if event.key == K_UP and game.snake.direction != (0,1):
                        game.snake.next_direction = (0,-1)
                    elif event.key == K_DOWN and game.snake.direction != (0,-1):
                        game.snake.next_direction = (0,1)
                    elif event.key == K_LEFT and game.snake.direction != (1,0):
                        game.snake.next_direction = (-1,0)
                    elif event.key == K_RIGHT and game.snake.direction != (-1,0):
                        game.snake.next_direction = (1,0)
                    elif event.key == K_1:
                        if game.inventory["Shield"] > 0:
                            game.inventory["Shield"] -= 1
                            game.snake.apply_power_up(SHIELD)  # SHIELD is constant 4
                    elif event.key == K_2:
                        if game.inventory["Speed Boost"] > 0:
                            game.inventory["Speed Boost"] -= 1
                            game.snake.apply_power_up(SPEED_BOOST)  # SPEED_BOOST is 0
                    elif event.key == K_3:
                        if game.inventory["Extra Life"] > 0:
                            game.inventory["Extra Life"] -= 1
                            game.snake.apply_power_up(-1)  # Extra Life uses -1

            elif current_state == GAME_OVER:
                if event.type == KEYDOWN:
                    if event.key == K_RETURN:
                        if game.snake.score>0:
                            game.high_scores.append({"name": name_input,"score":game.snake.score})
                            game.high_scores.sort(key=lambda x:x["score"], reverse=True)
                            game.save_high_scores()
                        current_state = MENU
                        name_input = ""
                    elif event.key == K_BACKSPACE:
                        name_input = name_input[:-1]
                    else:
                        if len(name_input)<12:
                            name_input += event.unicode

            elif current_state == HIGH_SCORES:
                if event.type == MOUSEBUTTONDOWN:
                    bx, by = (WIDTH//2, HEIGHT-100)
                    btn_rect = pygame.Rect(0,0,335,60)
                    btn_rect.center = (bx, by)
                    if btn_rect.collidepoint(event.pos):
                        current_state = MENU
                if event.type == KEYDOWN and event.key == K_ESCAPE:
                    current_state = MENU

            elif current_state == MICROTRANSACTIONS:
                # If in a pop-up
                if purchase_confirm and pending_item is not None:
                    if event.type == MOUSEBUTTONDOWN:
                        mx,my = event.pos
                        yes_rect = pygame.Rect(0,0,120,50)
                        yes_rect.center=(WIDTH//2-80,HEIGHT//2+40)
                        no_rect = pygame.Rect(0,0,120,50)
                        no_rect.center=(WIDTH//2+80,HEIGHT//2+40)
                        if yes_rect.collidepoint(mx,my):
                            if pending_item["type"]=="item":
                                cost=pending_item["cost_coins"]
                                if game.coins>=cost:
                                    game.coins-=cost
                                    game.inventory[pending_item["title"]] += 1
                                    purchase_message="Purchase Successful!"
                                else:
                                    purchase_message="Not Enough Coins"
                            else:
                                # coin package => card form
                                selected_package = pending_item
                                current_state=CREDIT_CARD_FORM
                                purchase_confirm=False
                                pending_item=None
                                break
                            purchase_confirm=False
                            pending_item=None
                        elif no_rect.collidepoint(mx,my):
                            purchase_confirm=False
                            pending_item=None

                elif purchase_message:
                    if event.type == MOUSEBUTTONDOWN:
                        mx,my=event.pos
                        ok_rect=pygame.Rect(0,0,100,40)
                        ok_rect.center=(WIDTH//2,HEIGHT//2+30)
                        if ok_rect.collidepoint(mx,my):
                            purchase_message=""

                else:
                    if event.type==KEYDOWN and event.key==K_ESCAPE:
                        current_state=MENU

                    if event.type==MOUSEWHEEL:
                        scroll_speed=40
                        if event.y>0:
                            shop_scroll_offset=max(0, shop_scroll_offset- scroll_speed)
                        else:
                            shop_scroll_offset+=scroll_speed

                    if event.type==MOUSEBUTTONDOWN and event.button==1:
                        mx,my=event.pos
                        SCROLL_LEFT, SCROLL_TOP=100,140
                        local_x=mx-SCROLL_LEFT
                        local_y=my-SCROLL_TOP
                        for item in POWERUP_ITEMS:
                            if "drawn_rect" in item:
                                if item["drawn_rect"].collidepoint(local_x,local_y):
                                    if "buy_rect" in item and item["buy_rect"].collidepoint(local_x,local_y):
                                        pending_item=item
                                        purchase_confirm=True
                                        break
                        for pack in COIN_PACKAGES:
                            if "drawn_rect" in pack:
                                if pack["drawn_rect"].collidepoint(local_x,local_y):
                                    pending_item=pack
                                    purchase_confirm=True
                                    break

            elif current_state==CREDIT_CARD_FORM:
                if processing:
                    if event.type==KEYDOWN and event.key==K_ESCAPE:
                        current_state=MICROTRANSACTIONS
                    continue
                if success:
                    if event.type==KEYDOWN:
                        current_state=MICROTRANSACTIONS
                    continue

                if event.type==KEYDOWN:
                    if event.key==K_ESCAPE:
                        current_state=MICROTRANSACTIONS
                    elif event.key in (K_RETURN,K_TAB):
                        if active_field<3:
                            active_field+=1
                        else:
                            valid, err=validate_card_info(card_info)
                            if valid:
                                processing=True
                                processing_countdown=120
                            else:
                                error_message=err
                    elif event.key==K_BACKSPACE:
                        if card_info[active_field]:
                            card_info[active_field]=card_info[active_field][:-1]
                    else:
                        card_info[active_field]+=event.unicode
                elif event.type==MOUSEBUTTONDOWN:
                    mx,my=event.pos
                    back_btn_rect=pygame.Rect(20,20,80,40)
                    if back_btn_rect.collidepoint(mx,my):
                        current_state=MICROTRANSACTIONS
                        continue
                    for i,r in enumerate(form_rects):
                        if r.collidepoint(mx,my):
                            active_field=i
                            break
        # ========== INTRO LOGIC ==========
        if current_state == INTRO:
            intro_timer += 1
            # After about 3 seconds, go to MENU (3 * 60 = 180 frames)
            if intro_timer >= 180:
                current_state = MENU

        # Processing credit card
        if current_state==CREDIT_CARD_FORM and processing:
            processing_countdown-=1
            if processing_countdown<=0:
                processing=False
                success=True
                if selected_package:
                    game.coins+=selected_package["coins"]

        # If playing, sub-step move
        if current_state==PLAYING:
            time_per_cell=1.0/game.snake.speed
            if snake_time_accumulator>=time_per_cell:
                snake_time_accumulator-=time_per_cell
                game.snake.move(game)
                # no single-step check
                game.check_power_up_collision()
                if game.snake.check_collision():
                    if game_over_sound:
                        game_over_sound.play()
                    current_state=GAME_OVER

        # DRAW
        screen.fill(DARK_BG)
        
        if current_state==INTRO:
            # fade in, hold, fade out
            # 0..60 => alpha 0->255
            # 60..120 => alpha=255
            # 120..180 => alpha 255->0
            if intro_timer<60:
                # fade in
                alpha_val = int((intro_timer/60)*255)
            elif intro_timer<120:
                # hold
                alpha_val=255
            else:
                # fade out (120->180)
                fade_out_t= intro_timer-120  # goes 0..60
                alpha_val= int(255 - (fade_out_t/60)*255)
            draw_intro_screen(alpha_val)
        elif current_state==LORE:
            lore_rain_particles = []
            for _ in range(150):
                lore_rain_particles.append({
                    "x": random.randint(0, WIDTH),
                    "y": random.randint(-HEIGHT, 0),
                    "speed": random.uniform(2, 6),
                    "char": random.choice(["0", "1"]),  # or pick from a set of ASCII
                    "alpha": random.randint(150, 255)
                })

            # 2) We'll have some variables to track fade:
            lore_timer = 0  # increments each frame
            lore_fade_duration = 60  # 60 frames ~1 second
            lore_alpha = 0  # 0..255
            draw_lore_screen()
        
        if current_state==MENU:
            draw_menu()
        elif current_state==PLAYING:
            game.draw()
        elif current_state==GAME_OVER:
            overlay=pygame.Surface((WIDTH,HEIGHT), pygame.SRCALPHA)
            overlay.fill((0,0,0,200))
            screen.blit(overlay,(0,0))
            
            text=font.render("GAME OVER",True,NEON_PINK)
            screen.blit(text,(WIDTH//2 - text.get_width()//2, HEIGHT//2 -80))

            score_text=font.render(f"FINAL SCORE: {game.snake.score}",True,WHITE)
            screen.blit(score_text,(WIDTH//2 - score_text.get_width()//2,HEIGHT//2 -30))

            # If maybe a new highscore
            if len(game.high_scores)<10 or (game.high_scores and game.snake.score>game.high_scores[-1]["score"]):
                input_text=font.render(f"ENTER NAME: {name_input}",True,NEON_BLUE)
                screen.blit(input_text,(WIDTH//2 - input_text.get_width()//2, HEIGHT//2+20))

        elif current_state==HIGH_SCORES:
            screen.fill(DARK_BG)
            for p in background_particles:
                p["pos"][1]+=p["speed"]
                if p["pos"][1]>HEIGHT:
                    p["pos"][1]=0
                    p["brightness"]=random.randint(50,255)
                alpha=p["brightness"]
                pygame.draw.line(screen,(0,alpha,0),
                                 (p["pos"][0],p["pos"][1]),
                                 (p["pos"][0],p["pos"][1]+15),
                                 p["size"])
            title_surf=title_font.render("HIGH SCORES",True,NEON_BLUE)
            screen.blit(title_surf,(WIDTH//2 - title_surf.get_width()//2,80))

            y_offset=200
            for i,entry in enumerate(game.high_scores[:10],start=1):
                score_line=f"{i}. {entry['name']} - {entry['score']}"
                line_surf=font.render(score_line,True,NEON_GREEN)
                screen.blit(line_surf,(200,y_offset))
                y_offset+=40

            bx,by=(WIDTH//2, HEIGHT-100)
            btn_rect=pygame.Rect(0,0,335,60)
            btn_rect.center=(bx,by)
            hover=btn_rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen,NEON_BLUE,btn_rect,3,border_radius=15)
            txt_surf=font.render("RETURN TO TERMINAL",True,NEON_PINK)
            txt_rect=txt_surf.get_rect(center=btn_rect.center)
            shadow_surf=font.render("RETURN TO TERMINAL",True,(0,0,0))
            screen.blit(shadow_surf, txt_rect.move(2,2))
            screen.blit(txt_surf, txt_rect)

        elif current_state==MICROTRANSACTIONS:
            shop_scroll_offset=draw_microtransactions_screen(game, shop_scroll_offset,
                                                             pending_item,purchase_confirm,purchase_message)
        elif current_state==CREDIT_CARD_FORM:
            draw_credit_card_form(game, card_info, active_field, form_rects,
                                  processing, processing_countdown, error_message,
                                  success, selected_package)

        pygame.display.flip()

if __name__=="__main__":
    main()
