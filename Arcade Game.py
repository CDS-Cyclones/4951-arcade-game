import pygame
import math
import random
from enum import Enum

pygame.init()

# ==================== CONSTANTS ====================
# Screen / World
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 1024
FPS = 120
GRAVITY = 0.6
MAP_WIDTH = 2400
MAP_HEIGHT = 1600

# Movement
RUN_THRESHOLD = 1.2
BASE_SPEED = 7
TAGGED_SPEED_BOOST = 1.15
JUMP_VELOCITY = -15
FRICTION = 0.80

# Player dimensions
PLAYER_WIDTH = 30
PLAYER_HEIGHT = 60

# Camera
CAMERA_MARGIN_X = 220
CAMERA_MARGIN_Y = 140
CAMERA_EASE = 0.14
ZOOM_MIN = 0.4
ZOOM_MAX = 1.9

# Platform generation
GROUND_HEIGHT = 140
PLATFORM_SEGMENTS = 12
PLATFORM_TIERS = 3
FLOATING_PLATFORMS = 16

# Game timing
TAG_COOLDOWN = 30
MATCH_DURATION = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 50, 50)
BLUE = (50, 100, 220)
SKIN = (255, 200, 150)
DARK_SKIN = (200, 100, 60)
SHIRT_RED = (220, 50, 50)
SHIRT_BLUE = (50, 100, 220)
GREEN = (100, 200, 100)
SKY_TOP = (135, 206, 235)
SKY_BOTTOM = (200, 220, 255)
MOUNTAIN_DARK = (80, 100, 80)
MOUNTAIN_LIGHT = (120, 140, 100)
PLATFORM_BROWN = (139, 89, 19)
PLATFORM_DARK = (101, 60, 14)


class PlayerState(Enum):
    NORMAL = 1
    TAGGED = 2


class Platform:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = PLATFORM_BROWN
        self.edge_color = PLATFORM_DARK

    def draw(self, surface, zoom, cam_x, cam_y):
        sx = int(self.rect.x * zoom - cam_x)
        sy = int(self.rect.y * zoom - cam_y)
        sw = max(1, int(self.rect.width * zoom))
        sh = max(1, int(self.rect.height * zoom))
        draw_rect = pygame.Rect(sx, sy, sw, sh)
        
        # Frustum culling
        if (draw_rect.right < 0 or draw_rect.left > SCREEN_WIDTH or 
            draw_rect.bottom < 0 or draw_rect.top > SCREEN_HEIGHT):
            return
            
        pygame.draw.rect(surface, self.color, draw_rect)
        pygame.draw.rect(surface, self.edge_color, draw_rect, max(1, int(3 * zoom)))
        pygame.draw.line(surface, (100, 150, 50),
                        (draw_rect.left, draw_rect.top),
                        (draw_rect.right, draw_rect.top), max(1, int(4 * zoom)))

class Player:
    def __init__(self, x, y, player_id, color_primary, color_shirt):
        self.x = x
        self.y = y
        self.player_id = player_id
        self.color_primary = color_primary
        self.color_shirt = color_shirt
        self.vx = 0
        self.vy = 0
        self.width = 30
        self.height = 60
        self.on_ground = False
        self.jumps_remaining = 2
        self.is_tagged = False
        self.tagged_cooldown = 0
        self.tagged_timer = 0
        self.state = PlayerState.NORMAL
        self.glow_intensity = 0
        self.direction = 1
        self.run_cycle = 0.0
        self.current_animation = "idle"
        self.idle_phase = 0.0

    def get_bounds(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def jump(self):
        if self.jumps_remaining > 0:
            self.vy = -15
            self.jumps_remaining -= 1

    def update(self, platforms):
        self.vy += GRAVITY
        self.x += self.vx
        self.y += self.vy

        # World bounds
        if self.x < 0:
            self.x = 0
            self.vx = 0
        elif self.x + self.width > MAP_WIDTH:
            self.x = MAP_WIDTH - self.width
            self.vx = 0

        if self.y + self.height >= MAP_HEIGHT:
            self.y = MAP_HEIGHT - self.height
            self.vy = 0
            self.on_ground = True
            self.jumps_remaining = 2

        # Reset ground, then resolve collisions
        #self.on_ground = False COMMENTED OUT
        player_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        for platform in platforms:
            if player_rect.colliderect(platform.rect):
                prev_y = self.y - self.vy
                if self.vy >= 0 and prev_y + self.height <= platform.rect.top + 6:
                    if (self.x + self.width) > platform.rect.left and self.x < (platform.rect.right):
                        self.y = platform.rect.top - self.height
                        self.vy = 0
                        self.on_ground = True
                        self.jumps_remaining = 2
                elif self.vy < 0 and prev_y >= platform.rect.bottom - 2:
                    if (self.x + self.width) > platform.rect.left and self.x < (platform.rect.right):
                        self.y = platform.rect.bottom
                        self.on_ground = False #COMMENTED IN
                        self.vy = 0
                else:
                    if (self.x + self.width) > platform.rect.left and self.x < (platform.rect.right):
                        plat_center = platform.rect.centerx
                        player_center = self.x + self.width / 2
                        self.on_ground = False #COMMENTED IN
                        if player_center < plat_center:
                            self.x = platform.rect.left - self.width - 1
                        else:
                            self.x = platform.rect.right + 1
                player_rect.update(self.x, self.y, self.width, self.height)

        # Animation state
        if not self.on_ground:
            self.current_animation = "jumping"
        elif abs(self.vx) > RUN_THRESHOLD:
            self.current_animation = "running"
            self.run_cycle += abs(self.vx) * 0.08
            if self.run_cycle > 4:
                self.run_cycle -= 4
        else:
            self.current_animation = "idle"
            self.run_cycle = 0
            self.idle_phase += 0.04  # breathing speed
            if self.idle_phase > math.tau:
                self.idle_phase -= math.tau

        # Glow for tagged
        if self.is_tagged:
            self.glow_intensity = min(self.glow_intensity + 0.15, 1.0)
            self.tagged_timer = 0
        else:
            self.glow_intensity = max(self.glow_intensity - 0.1, 0.0)
            if self.tagged_timer > 0:
                self.tagged_timer -= 1

        if self.tagged_cooldown > 0:
            self.tagged_cooldown -= 1

        # Friction and clamp to stop sliding
        if self.on_ground and abs(self.vx) < 0.08:
            self.vx = 0

    def draw(self, surface, zoom, cam_x, cam_y):
        # Slight smoothing in idle only
        used_zoom = zoom
        if self.current_animation == "idle":
            used_zoom = round(zoom, 3)

        # Breathing bob in idle
        bob = 0
        if self.current_animation == "idle":
            bob = int(math.sin(self.idle_phase) * 2 * used_zoom)

        draw_x = int(self.x * used_zoom - cam_x)
        draw_y = int(self.y * used_zoom - cam_y) + bob
        w = max(1, int(self.width * used_zoom))
        h = max(1, int(self.height * used_zoom))
        center_x = draw_x + w // 2
        center_y = draw_y + h // 2

        # Tagged glow
        if self.is_tagged:
            glow_radius = int((25 + self.glow_intensity * 15) * used_zoom)
            for i in range(3):
                glow_color = (255,
                              int(100 + self.glow_intensity * 155 - i * 30),
                              int(100 + self.glow_intensity * 155 - i * 30))
                pygame.draw.circle(surface, glow_color, (center_x, center_y),
                                   glow_radius + i * max(2, int(4 * used_zoom)),
                                   max(1, int(3 * used_zoom)))

        # Body (shirt-colored)
        body_radius = max(1, int(18 * used_zoom))
        pygame.draw.circle(surface, self.color_shirt, (center_x, center_y), body_radius)

        # Face
        eye_offset = max(1, int(6 * used_zoom))
        eye_r = max(1, int(4 * used_zoom))
        pupil_r = max(1, int(2 * used_zoom))
        pygame.draw.circle(surface, WHITE, (center_x - eye_offset, center_y - max(1, int(4 * used_zoom))), eye_r)
        pygame.draw.circle(surface, WHITE, (center_x + eye_offset, center_y - max(1, int(4 * used_zoom))), eye_r)
        pygame.draw.circle(surface, BLACK, (center_x - eye_offset, center_y - max(1, int(4 * used_zoom))), pupil_r)
        pygame.draw.circle(surface, BLACK, (center_x + eye_offset, center_y - max(1, int(4 * used_zoom))), pupil_r)
        mouth_rect = pygame.Rect(center_x - max(1, int(6 * used_zoom)), center_y + max(1, int(2 * used_zoom)), max(1, int(12 * used_zoom)), max(1, int(6 * used_zoom)))
        pygame.draw.arc(surface, BLACK, mouth_rect, math.pi, 2 * math.pi, max(1, int(2 * used_zoom)))
        # Poses
        if self.current_animation == "jumping":
            self.draw_jumping_pose(surface, center_x, center_y, used_zoom)
        elif self.current_animation == "running":
            self.draw_running_pose(surface, center_x, center_y, used_zoom)
        else:
            self.draw_idle_pose(surface, center_x, center_y, used_zoom)

    def draw_idle_pose(self, surface, center_x, center_y, zoom):
        # Arms slightly relaxed
        lx0 = center_x - int(18 * zoom)
        ly0 = center_y + int(2 * zoom)
        lx1 = center_x - int(20 * zoom)
        ly1 = center_y + int(16 * zoom)
        pygame.draw.line(surface, self.color_shirt, (lx0, ly0), (lx1, ly1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (lx1, ly1), max(1, int(4 * zoom)))

        rx0 = center_x + int(18 * zoom)
        ry0 = center_y + int(2 * zoom)
        rx1 = center_x + int(20 * zoom)
        ry1 = center_y + int(16 * zoom)
        pygame.draw.line(surface, self.color_shirt, (rx0, ry0), (rx1, ry1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (rx1, ry1), max(1, int(4 * zoom)))

        # Legs straight under body
        leg_y = center_y + int(18 * zoom)
        llx0 = center_x - int(6 * zoom)
        lly0 = leg_y
        llx1 = center_x - int(6 * zoom)
        lly1 = leg_y + int(14 * zoom)
        pygame.draw.line(surface, self.color_shirt, (llx0, lly0), (llx1, lly1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (llx1, lly1), max(1, int(3 * zoom)))

        rlx0 = center_x + int(6 * zoom)
        rly0 = leg_y
        rlx1 = center_x + int(6 * zoom)
        rly1 = leg_y + int(14 * zoom)
        pygame.draw.line(surface, self.color_shirt, (rlx0, rly0), (rlx1, rly1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (rlx1, rly1), max(1, int(3 * zoom)))

    def draw_running_pose(self, surface, center_x, center_y, zoom):
        arm_swing = math.sin(self.run_cycle * math.pi / 2) * 6
        arm_swing_px = int(arm_swing * zoom)
        arm_y = center_y + int(2 * zoom)
        leg_y = center_y + int(18 * zoom)
        arm_back_x = int(24 * zoom)
        arm_forward_x = int(24 * zoom)

        # Arms with facing direction
        if self.direction > 0:
            lx0 = center_x - int(18 * zoom)
            ly0 = arm_y
            lx1 = center_x - arm_back_x - arm_swing_px
            ly1 = arm_y + int(8 * zoom)
            pygame.draw.line(surface, self.color_shirt, (lx0, ly0), (lx1, ly1), max(1, int(5 * zoom)))
            pygame.draw.circle(surface, self.color_shirt, (lx1, ly1), max(1, int(4 * zoom)))

            rx0 = center_x + int(18 * zoom)
            ry0 = arm_y
            rx1 = center_x + arm_forward_x + arm_swing_px
            ry1 = arm_y + int(8 * zoom)
            pygame.draw.line(surface, self.color_shirt, (rx0, ry0), (rx1, ry1), max(1, int(5 * zoom)))
            pygame.draw.circle(surface, self.color_shirt, (rx1, ry1), max(1, int(4 * zoom)))
        else:
            rx0 = center_x + int(18 * zoom)
            ry0 = arm_y
            rx1 = center_x + int(24 * zoom) + arm_swing_px
            ry1 = arm_y + int(8 * zoom)
            pygame.draw.line(surface, self.color_shirt, (rx0, ry0), (rx1, ry1), max(1, int(5 * zoom)))
            pygame.draw.circle(surface, self.color_shirt, (rx1, ry1), max(1, int(4 * zoom)))

            lx0 = center_x - int(18 * zoom)
            ly0 = arm_y
            lx1 = center_x - int(24 * zoom) - arm_swing_px
            ly1 = arm_y + int(8 * zoom)
            pygame.draw.line(surface, self.color_shirt, (lx0, ly0), (lx1, ly1), max(1, int(5 * zoom)))
            pygame.draw.circle(surface, self.color_shirt, (lx1, ly1), max(1, int(4 * zoom)))

        # Legs with phase offset so they alternate vs arms
        leg_swing = math.sin(self.run_cycle * math.pi / 2 + math.pi / 2) * 4
        leg_swing_px = int(leg_swing * zoom)

        llx0 = center_x - int(6 * zoom)
        lly0 = leg_y
        llx1 = center_x - int(10 * zoom) - leg_swing_px
        lly1 = leg_y + int(14 * zoom)
        pygame.draw.line(surface, self.color_shirt, (llx0, lly0), (llx1, lly1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (llx1, lly1), max(1, int(3 * zoom)))

        rlx0 = center_x + int(6 * zoom)
        rly0 = leg_y
        rlx1 = center_x + int(10 * zoom) + leg_swing_px
        rly1 = leg_y + int(14 * zoom)
        pygame.draw.line(surface, self.color_shirt, (rlx0, rly0), (rlx1, rly1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (rlx1, rly1), max(1, int(3 * zoom)))

    def draw_jumping_pose(self, surface, center_x, center_y, zoom):
        # Arms up
        lx0 = center_x - int(18 * zoom)
        ly0 = center_y - int(5 * zoom)
        lx1 = center_x - int(25 * zoom)
        ly1 = center_y - int(15 * zoom)
        pygame.draw.line(surface, self.color_shirt, (lx0, ly0), (lx1, ly1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (lx1, ly1), max(1, int(4 * zoom)))

        rx0 = center_x + int(18 * zoom)
        ry0 = center_y - int(5 * zoom)
        rx1 = center_x + int(25 * zoom)
        ry1 = center_y - int(15 * zoom)
        pygame.draw.line(surface, self.color_shirt, (rx0, ry0), (rx1, ry1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (rx1, ry1), max(1, int(4 * zoom)))

        # Legs slightly tucked
        leg_y = center_y + int(18 * zoom)
        llx0 = center_x - int(6 * zoom)
        lly0 = leg_y
        llx1 = center_x - int(8 * zoom)
        lly1 = leg_y + int(8 * zoom)
        pygame.draw.line(surface, self.color_shirt, (llx0, lly0), (llx1, lly1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (llx1, lly1), max(1, int(3 * zoom)))

        rlx0 = center_x + int(6 * zoom)
        rly0 = leg_y
        rlx1 = center_x + int(8 * zoom)
        rly1 = leg_y + int(8 * zoom)
        pygame.draw.line(surface, self.color_shirt, (rlx0, rly0), (rlx1, rly1), max(1, int(5 * zoom)))
        pygame.draw.circle(surface, self.color_shirt, (rlx1, rly1), max(1, int(3 * zoom)))

class Camera:
    """
    Improved camera system with simplified logic and smoother behavior.
    Automatically frames both players while respecting world boundaries.
    """
    def __init__(self, ground_top):
        self.x = 0
        self.y = 0
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.ground_top = ground_top  # y-coordinate of the top of the ground platform
        
        # Smoothing parameters
        self.zoom_ease = 0.14
        self.position_ease = 0.12
        
        # Target position (for smooth interpolation)
        self.target_x = 0
        self.target_y = 0

    def update(self, player1, player2):
        """
        Update camera to frame both players smoothly.
        
        Args:
            player1: First player object
            player2: Second player object
        """
        # 1. Calculate bounding box containing both players
        left = min(player1.x, player2.x)
        right = max(player1.x + player1.width, player2.x + player2.width)
        top = min(player1.y, player2.y)
        bottom = max(player1.y + player1.height, player2.y + player2.height)
        
        # 2. Add comfortable margins around players
        margin_x = 220
        margin_y = 140
        
        required_width = (right - left) + margin_x
        required_height = (bottom - top) + margin_y
        
        # Ensure minimum size (prevent extreme zoom-in)
        required_width = max(required_width, 400)
        required_height = max(required_height, 300)
        
        # 3. Calculate zoom level to fit both dimensions
        zoom_x = SCREEN_WIDTH / required_width
        zoom_y = SCREEN_HEIGHT / required_height
        
        # Use the smaller zoom to ensure everything fits
        self.target_zoom = min(zoom_x, zoom_y)
        
        # Clamp zoom to reasonable limits
        self.target_zoom = max(ZOOM_MIN, min(self.target_zoom, ZOOM_MAX))
        
        # 4. Calculate center point between players
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        
        # 5. Apply vertical constraints to keep ground visible
        half_view_height = (SCREEN_HEIGHT / self.target_zoom) / 2
        
        # Don't let camera go below ground line
        if center_y + half_view_height > self.ground_top:
            center_y = self.ground_top - half_view_height
        
        # Don't let camera go above world top
        if center_y - half_view_height < 0:
            center_y = half_view_height
        
        # 6. Convert world center to camera position
        # Camera position is top-left corner in world space
        self.target_x = center_x * self.target_zoom - SCREEN_WIDTH / 2
        self.target_y = center_y * self.target_zoom - SCREEN_HEIGHT / 2
        
        # 7. Clamp camera to world boundaries
        max_cam_x = max(0, MAP_WIDTH * self.target_zoom - SCREEN_WIDTH)
        max_cam_y = max(0, self.ground_top * self.target_zoom - SCREEN_HEIGHT)
        
        self.target_x = max(0, min(self.target_x, max_cam_x))
        self.target_y = max(0, min(self.target_y, max_cam_y))
        
        # 8. Smooth interpolation for camera movement
        self.zoom += (self.target_zoom - self.zoom) * self.zoom_ease
        self.x += (self.target_x - self.x) * self.position_ease
        self.y += (self.target_y - self.y) * self.position_ease

    def get_transform(self):
        """Returns (zoom, camera_x, camera_y) for rendering."""
        return self.zoom, self.x, self.y
    
    def world_to_screen(self, world_x, world_y):
        """Convert world coordinates to screen coordinates."""
        screen_x = world_x * self.zoom - self.x
        screen_y = world_y * self.zoom - self.y
        return screen_x, screen_y
    
    def screen_to_world(self, screen_x, screen_y):
        """Convert screen coordinates to world coordinates."""
        world_x = (screen_x + self.x) / self.zoom
        world_y = (screen_y + self.y) / self.zoom
        return world_x, world_y


# Usage example in your Game class:
# Replace the camera.update() call with:
# self.camera.update(self.player1, self.player2)

class GameState(Enum):
    PLAYING = 1
    GAME_OVER_P1 = 2
    GAME_OVER_P2 = 3

class Game:
    """
    Main game class with improved initialization and update logic.
    """
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Two Player Tag Game")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Initialize world
        self.platforms = self.generate_platforms()
        self.ground_top = MAP_HEIGHT - GROUND_HEIGHT
        
        # Pre-render background for performance
        self.background_surface = self.create_background()
        
        # Initialize players at spawn positions
        ground_spawn_y = self.ground_top - PLAYER_HEIGHT
        self.player1 = Player(200, ground_spawn_y, 1, RED, RED)
        self.player2 = Player(2100, ground_spawn_y, 2, BLUE, BLUE)
        
        # Initialize camera with new simplified class
        self.camera = Camera(self.ground_top)
        
        # Game state
        self.player1.is_tagged = True
        self.player2.is_tagged = False
        self.tag_timer = 0
        self.state = GameState.PLAYING
        
        # Timing and scoring
        self.match_seconds = MATCH_DURATION
        self.frame_counter = 0
        self.p1_tag_time = 0
        self.p2_tag_time = 0
        
        # Fonts
        self.font_main = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 20)
        self.font_big = pygame.font.Font(None, 64)

    def create_background(self):
        """
        Pre-render the background gradient once for performance.
        This eliminates 1024 draw calls per frame!
        """
        bg = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            ratio = y / SCREEN_HEIGHT
            r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * ratio)
            g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * ratio)
            b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * ratio)
            pygame.draw.line(bg, (r, g, b), (0, y), (SCREEN_WIDTH, y))
        
        # Draw mountains on the background
        self.draw_mountains(bg)
        return bg

    def draw_mountains(self, surface):
        """Draw mountain layers on the given surface."""
        points_far = [
            (0, 650), (300, 520), (600, 600), (900, 500), 
            (1200, 580), (1500, 550), (1800, 580), (2100, 500), 
            (2400, 650), (2400, 1050), (0, 1050)
        ]
        pygame.draw.polygon(surface, MOUNTAIN_LIGHT, points_far)
        
        points_near = [
            (0, 1050), (250, 580), (550, 680), (750, 550), 
            (1000, 680), (1200, 600), (1500, 650), (1800, 600), 
            (2100, 700), (2400, 600), (2400, 1050)
        ]
        pygame.draw.polygon(surface, MOUNTAIN_DARK, points_near)

    def draw_cloud(self, surface, x, y, size):
        """Draw a simple cloud."""
        pygame.draw.circle(surface, WHITE, (x, y), size)
        pygame.draw.circle(surface, WHITE, (x + size, y), size)
        pygame.draw.circle(surface, WHITE, (x + size // 2, y - size // 2), size)

    def check_tag(self):
        """Check if players collide and handle tag switching."""
        bounds1 = self.player1.get_bounds()
        bounds2 = self.player2.get_bounds()
        
        if bounds1.colliderect(bounds2) and self.tag_timer <= 0:
            # Switch who is tagged
            self.player1.is_tagged = not self.player1.is_tagged
            self.player2.is_tagged = not self.player2.is_tagged
            self.tag_timer = TAG_COOLDOWN

    def update(self):
        """Update game state - called every frame during gameplay."""
        keys = pygame.key.get_pressed()
        
        # Player 1 controls (WASD)
        p1_speed = BASE_SPEED * (TAGGED_SPEED_BOOST if self.player1.is_tagged else 1.0)
        if keys[pygame.K_a]:
            self.player1.vx = -p1_speed
            self.player1.direction = -1
        elif keys[pygame.K_d]:
            self.player1.vx = p1_speed
            self.player1.direction = 1
        else:
            self.player1.vx *= FRICTION
        
        # Player 2 controls (Arrow keys)
        p2_speed = BASE_SPEED * (TAGGED_SPEED_BOOST if self.player2.is_tagged else 1.0)
        if keys[pygame.K_LEFT]:
            self.player2.vx = -p2_speed
            self.player2.direction = -1
        elif keys[pygame.K_RIGHT]:
            self.player2.vx = p2_speed
            self.player2.direction = 1
        else:
            self.player2.vx *= FRICTION
        
        # Update physics
        self.player1.update(self.platforms)
        self.player2.update(self.platforms)
        
        # Check for tagging
        self.check_tag()
        if self.tag_timer > 0:
            self.tag_timer -= 1
        
        # Accumulate tagged time for scoring
        if self.state == GameState.PLAYING:
            if self.player1.is_tagged:
                self.p1_tag_time += 1
            if self.player2.is_tagged:
                self.p2_tag_time += 1
        
        # Update camera (NEW SIMPLIFIED CALL)
        self.camera.update(self.player1, self.player2)
        
        # Update game timer
        if self.state == GameState.PLAYING:
            self.frame_counter += 1
            if self.frame_counter >= FPS:
                self.frame_counter = 0
                self.match_seconds -= 1
                
                if self.match_seconds <= 0:
                    # Determine winner (whoever is NOT tagged wins)
                    if self.player1.is_tagged and not self.player2.is_tagged:
                        self.state = GameState.GAME_OVER_P2
                    elif self.player2.is_tagged and not self.player1.is_tagged:
                        self.state = GameState.GAME_OVER_P1
                    else:
                        # Tie - default to P2 win
                        self.state = GameState.GAME_OVER_P2

    def draw_ui(self):
        """Draw HUD elements during gameplay."""
        # Tag status banner
        if self.player1.is_tagged:
            tagged_text = "PLAYER 1 IS IT!"
            color = SHIRT_RED
        else:
            tagged_text = "PLAYER 2 IS IT!"
            color = SHIRT_BLUE
        
        text_surface = self.font_main.render(tagged_text, True, color)
        self.screen.blit(text_surface, 
                        (SCREEN_WIDTH // 2 - text_surface.get_width() // 2, 10))
        
        # Controls guide
        p1_text = self.font_small.render("P1: A/D move, W jump", True, BLACK)
        p2_text = self.font_small.render("P2: ← → move, ↑ jump", True, BLACK)
        self.screen.blit(p1_text, (10, 50))
        self.screen.blit(p2_text, (10, 75))
        
        # Match timer
        timer_surface = self.font_main.render(f"Time: {self.match_seconds}s", True, BLACK)
        self.screen.blit(timer_surface, 
                        (SCREEN_WIDTH - timer_surface.get_width() - 10, 10))

    def draw_game_over(self):
        """Draw game over screen with winner announcement."""
        if self.state == GameState.GAME_OVER_P1:
            title = "PLAYER 1 WINS!"
            color = SHIRT_RED
        else:
            title = "PLAYER 2 WINS!"
            color = SHIRT_BLUE
        
        # Title
        title_surface = self.font_big.render(title, True, color)
        self.screen.blit(title_surface, 
                        (SCREEN_WIDTH // 2 - title_surface.get_width() // 2,
                         SCREEN_HEIGHT // 2 - 60))
        
        # Instructions
        info1 = self.font_main.render("Press W to restart", True, BLACK)
        info2 = self.font_main.render("Press 5 to quit", True, BLACK)
        self.screen.blit(info1, 
                        (SCREEN_WIDTH // 2 - info1.get_width() // 2,
                         SCREEN_HEIGHT // 2 + 20))
        self.screen.blit(info2, 
                        (SCREEN_WIDTH // 2 - info2.get_width() // 2,
                         SCREEN_HEIGHT // 2 + 50))

    def draw(self):
        """Main draw method - renders everything."""
        # Draw pre-rendered background (HUGE performance boost!)
        self.screen.blit(self.background_surface, (0, 0))
        
        # Draw animated clouds
        cloud_time = pygame.time.get_ticks() // 100
        for i in range(4):
            cloud_x = (i * 350 + cloud_time) % (SCREEN_WIDTH + 200) - 100
            cloud_y = 40 + (i % 2) * 60
            self.draw_cloud(self.screen, cloud_x, cloud_y, 50)
        
        # Get camera transform
        zoom, cam_x, cam_y = self.camera.get_transform()
        
        # Draw world objects
        for platform in self.platforms:
            platform.draw(self.screen, zoom, cam_x, cam_y)
        
        self.player1.draw(self.screen, zoom, cam_x, cam_y)
        self.player2.draw(self.screen, zoom, cam_x, cam_y)
        
        # Draw UI overlay
        if self.state == GameState.PLAYING:
            self.draw_ui()
        else:
            self.draw_game_over()
        
        pygame.display.flip()

    def handle_event(self, event):
        """Handle pygame events."""
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_5:
                self.running = False
            
            if self.state == GameState.PLAYING:
                if event.key == pygame.K_w:
                    self.player1.jump()
                if event.key == pygame.K_UP:
                    self.player2.jump()
            else:
                # Game over - restart on W
                if event.key == pygame.K_w:
                    self.reset()

    def reset(self):
        """Reset game state for a new match."""
        ground_spawn_y = self.ground_top - PLAYER_HEIGHT
        self.player1 = Player(200, ground_spawn_y, 1, RED, RED)
        self.player2 = Player(2100, ground_spawn_y, 2, BLUE, BLUE)
        
        self.player1.is_tagged = True
        self.player2.is_tagged = False
        self.tag_timer = 0
        
        self.p1_tag_time = 0
        self.p2_tag_time = 0
        self.match_seconds = MATCH_DURATION
        self.frame_counter = 0
        self.state = GameState.PLAYING
        
        # Regenerate platforms for variety
        self.platforms = self.generate_platforms()
        
        # Reset camera
        self.camera = Camera(self.ground_top)

    def generate_platforms(self):
        """Generate platforms for the level."""
        platforms = []
        
        # Ground platform
        platforms.append(Platform(0, MAP_HEIGHT - GROUND_HEIGHT, MAP_WIDTH, GROUND_HEIGHT))

        segments = 12
        tiers = 3
        for i in range(segments):
            seg_w = MAP_WIDTH / segments
            x_min = int(i * seg_w) + 40
            x_max = int((i + 1) * seg_w) - 40
            width = random.randint(140, 360)
            x = random.randint(x_min, max(x_min, x_max - width))

            # Base height curve
            t = i / max(1, (segments - 1))
            base_y = MAP_HEIGHT - 220 - int(math.sin(t * math.pi) * (MAP_HEIGHT * 0.18))
            y = base_y + random.randint(-140, 140)
            y = max(60, min(y, MAP_HEIGHT - GROUND_HEIGHT - 60))

            # Main platform
            platforms.append(Platform(x, y, width, 40))

            # Tiered platforms
            for tier in range(1, tiers + 1):
                if random.random() < 0.72:
                    tw = random.randint(100, 220)
                    tx = x + random.randint(-260, 260)
                    tx = max(20, min(MAP_WIDTH - tw - 20, tx))
                    tier_frac = tier / (tiers + 1)
                    ty_base = base_y - int(tier_frac * (220 + MAP_HEIGHT * 0.06)) - int(math.cos(t * math.pi) * 80)
                    ty = ty_base + random.randint(-150, 150)
                    ty = max(60, min(ty, MAP_HEIGHT - GROUND_HEIGHT - 80))
                    newp = Platform(tx, ty, tw, 36)
                    
                    # Overlap correction
                    for existing in platforms:
                        vert_gap = abs(existing.rect.y - newp.rect.y)
                        if vert_gap < 180:
                            hor_overlap = max(0, min(existing.rect.right, newp.rect.right) - max(existing.rect.left, newp.rect.left))
                            minw = min(existing.rect.width, newp.rect.width)
                            if hor_overlap > 0.65 * minw:
                                shift = int((hor_overlap - 0.55 * minw) + 60)
                                if newp.rect.centerx < existing.rect.centerx:
                                    newp.rect.x = max(20, newp.rect.x - shift)
                                else:
                                    newp.rect.x = min(MAP_WIDTH - newp.rect.width - 20, newp.rect.x + shift)
                    platforms.append(newp)

        # Floating platforms
        for _ in range(16):
            fw = random.randint(80, 220)
            fx = random.randint(60, MAP_WIDTH - fw - 60)
            fy = random.randint(100, MAP_HEIGHT - 420)
            fp = Platform(fx, fy, fw, 36)
            platforms.append(fp)

        return platforms

    def run(self):
        """Main game loop."""
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            
            if self.state == GameState.PLAYING:
                self.update()
            
            self.draw()
            self.clock.tick(FPS)
        
        pygame.quit()


# Main entry point
if __name__ == "__main__":
    game = Game()
    game.run()
