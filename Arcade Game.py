import pygame
import math
import random
from enum import Enum
pygame.init()
# ==================== CONSTANTS ====================
# Screen / World
SCREEN_WIDTH = 1025
SCREEN_HEIGHT = 710
FPS = 60
GRAVITY = 0.5
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


# Game timing
TAG_COOLDOWN = 30
MATCH_DURATION = 60

# Colors
WHITE = (255,255,255) #(255,255,255) NORMAL VALUE
GREY_CLOUD = (60, 60, 70) #(60,60,70) NORMAL VALUE
BLACK = (0, 0, 0)
RED = (220, 50, 50)
BLUE = (50, 100, 220)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
PURPLE = (200, 50, 200)
ORANGE = (255, 165, 0)
SHIRT_RED = (220, 50, 50)
SHIRT_BLUE = (50, 100, 220)
SKY_TOP = (115, 156, 255) #(115, 156, 255) NORMAL VALUE
SKY_BOTTOM = (210, 230, 255) #(210, 230, 255) NORMAL VALUE
UPSIDE_DOWN_SKY_TOP = (40,8,48) #(40,8,48) NORMAL VALUE
UPSIDE_DOWN_SKY_BOTTOM = (140,23,35) #(140,23,35) NORMAL VALUE
MOUNTAIN_DARK = (80, 100, 80) #(80, 100, 80) NORMAL VALUE
MOUNTAIN_LIGHT = (120, 140, 100) #(120, 140, 100) NORMAL VALUE
UPSIDE_DOWN_MOUNTAIN_DARK = (20, 10, 20) #(20,10,20) NORMAL VALUE
UPSIDE_DOWN_MOUNTAIN_LIGHT = (45, 30, 45) #(45,30,45) NORMAL VALUE
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
        self.dash_cooldown = 0
        self.dash_speed = 20
        self.dash_duration = 10
        self.dash_timer = 0

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

        # Reset ground state before checking
        #self.on_ground = False

        # Check world floor
        if self.y + self.height >= MAP_HEIGHT:
            self.y = MAP_HEIGHT - self.height
            self.vy = 0
            self.on_ground = True
            self.jumps_remaining = 2

        # Resolve platform collisions
        player_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        for platform in platforms:
            if player_rect.colliderect(platform.rect):
                prev_y = self.y - self.vy
                prev_bottom = prev_y + self.height

                # Landing on top of platform
                if self.vy > 0 and prev_bottom <= platform.rect.top + 8:
                    self.y = platform.rect.top - self.height
                    self.vy = 0
                    self.on_ground = True
                    self.jumps_remaining = 2
                # Hitting head on bottom of platform
                elif self.vy < 0 and prev_y >= platform.rect.bottom - 4:
                    self.y = platform.rect.bottom
                    self.vy = 0
                # Side collision
                else:
                    prev_x = self.x - self.vx
                    if prev_x + self.width <= platform.rect.left:
                        # Hit from left
                        self.x = platform.rect.left - self.width
                        self.vx = 0
                    elif prev_x >= platform.rect.right:
                        # Hit from right
                        self.x = platform.rect.right
                        self.vx = 0

                player_rect.update(self.x, self.y, self.width, self.height)

        # Animation state
        grounded_still = self.on_ground and abs(self.vx) < 0.25 and abs(self.vy) < 0.2 and self.dash_timer == 0
        if grounded_still:
            self.current_animation = "idle"
            self.run_cycle = 0
            self.idle_phase += 0.04
            if self.idle_phase > math.tau:
                self.idle_phase -= math.tau
        elif self.on_ground:
            self.current_animation = "running"
            self.idle_phase = 0
            self.run_cycle += abs(self.vx) * 0.08
            if self.run_cycle > 4:
                self.run_cycle -= 4
        else:
            # in air: show running if moving sideways, else jumping
            if abs(self.vx) > RUN_THRESHOLD:
                self.current_animation = "running"
                self.run_cycle += abs(self.vx) * 0.08
                if self.run_cycle > 4:
                    self.run_cycle -= 4
            else:
                self.current_animation = "jumping"
        
        if self.is_tagged:
            self.glow_intensity = min(self.glow_intensity + 0.15, 1.0)
            self.tagged_timer = 0
        else:
            self.glow_intensity = max(self.glow_intensity - 0.1, 0.0)
            if self.tagged_timer > 0:
                self.tagged_timer -= 1

        if self.tagged_cooldown > 0:
            self.tagged_cooldown -= 1

        if self.dash_timer > 0:
            self.dash_timer -= 1
        elif self.dash_cooldown > 0:
            self.dash_cooldown -= 1

        if self.on_ground and abs(self.vx) < 0.08 and self.dash_timer == 0:
            self.vx = 0

    def dash(self):
        if self.dash_cooldown == 0 and self.dash_timer == 0:
            self.dash_timer = self.dash_duration
            self.dash_cooldown = FPS * 5  # 5 seconds cooldown
            self.vx = self.dash_speed * self.direction

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
        
        # Adjust the camera to show a bit more ground
        ground_offset = 50  # Pixels to lower the camera view
        dash_bar_height = 40  # Additional offset to ensure dash bars don't cover the ground
        if center_y + half_view_height > self.ground_top + ground_offset + dash_bar_height:
            center_y = self.ground_top - half_view_height + ground_offset + dash_bar_height
        
        # Don't let camera go above world top
        if center_y - half_view_height < 0:
            center_y = half_view_height
        
        # 6. Convert world center to camera position
        # Camera position is top-left corner in world space
        self.target_x = center_x * self.target_zoom - SCREEN_WIDTH / 2
        self.target_y = center_y * self.target_zoom - SCREEN_HEIGHT / 2
        
        # 7. Clamp camera to world boundaries
        max_cam_x = max(0, MAP_WIDTH * self.target_zoom - SCREEN_WIDTH)
        max_cam_y = max(0, self.ground_top * self.target_zoom - SCREEN_HEIGHT) #ADDED PLUS 10
        
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
        
        # Current sky and mountain colors (can be modified for special maps) - MUST be before create_background()
        self.current_sky_top = SKY_TOP
        self.current_sky_bottom = SKY_BOTTOM
        self.current_mountain_light = MOUNTAIN_LIGHT
        self.current_mountain_dark = MOUNTAIN_DARK
        self.current_cloud_color = WHITE
        
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
        self.font_huge = pygame.font.Font(None, 100)
        
        # Screen flags
        self.show_title_screen = True
        self.show_color_selection_screen = False
        self.show_start_screen = False

    def create_background(self):
        """
        Pre-render the background gradient once for performance.
        This eliminates 1024 draw calls per frame!
        """
        bg = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            ratio = y / SCREEN_HEIGHT
            r = int(self.current_sky_top[0] + (self.current_sky_bottom[0] - self.current_sky_top[0]) * ratio)
            g = int(self.current_sky_top[1] + (self.current_sky_bottom[1] - self.current_sky_top[1]) * ratio)
            b = int(self.current_sky_top[2] + (self.current_sky_bottom[2] - self.current_sky_top[2]) * ratio)
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
        pygame.draw.polygon(surface, self.current_mountain_light, points_far)
        
        points_near = [
            (0, 1050), (250, 580), (550, 680), (750, 550), 
            (1000, 680), (1200, 600), (1500, 650), (1800, 600), 
            (2100, 700), (2400, 600), (2400, 1050)
        ]
        pygame.draw.polygon(surface, self.current_mountain_dark, points_near)

    def draw_cloud(self, surface, x, y, size):
        """Draw a simple cloud."""
        pygame.draw.circle(surface, self.current_cloud_color, (x, y), size)
        pygame.draw.circle(surface, self.current_cloud_color, (x + size, y), size)
        pygame.draw.circle(surface, self.current_cloud_color, (x + size // 2, y - size // 2), size)

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

        # Movement - update direction even during dash
        if keys[pygame.K_a]:
            self.player1.direction = -1
            if self.player1.dash_timer == 0:
                self.player1.vx = -p1_speed
        elif keys[pygame.K_d]:
            self.player1.direction = 1
            if self.player1.dash_timer == 0:
                self.player1.vx = p1_speed
        else:
            if self.player1.dash_timer == 0:
                self.player1.vx *= FRICTION

        # Player 2 controls (Arrow keys)
        p2_speed = BASE_SPEED * (TAGGED_SPEED_BOOST if self.player2.is_tagged else 1.0)
        
        # Movement - update direction even during dash
        if keys[pygame.K_LEFT]:
            self.player2.direction = -1
            if self.player2.dash_timer == 0:
                self.player2.vx = -p2_speed
        elif keys[pygame.K_RIGHT]:
            self.player2.direction = 1
            if self.player2.dash_timer == 0:
                self.player2.vx = p2_speed
        else:
            if self.player2.dash_timer == 0:
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

        # Update camera
        self.camera.update(self.player1, self.player2)

        # Update game timer
        if self.state == GameState.PLAYING:
            self.frame_counter += 1
            if self.frame_counter >= FPS:
                self.frame_counter = 0
                self.match_seconds -= 1

                if self.match_seconds <= 0:
                    if self.player1.is_tagged and not self.player2.is_tagged:
                        self.state = GameState.GAME_OVER_P2
                    elif self.player2.is_tagged and not self.player1.is_tagged:
                        self.state = GameState.GAME_OVER_P1
                    else:
                        self.state = GameState.GAME_OVER_P2

    def draw_ui(self):
        """Draw HUD elements during gameplay."""
        # Tag status banner (show which player is 'it' using their selected color)
        if self.player1.is_tagged:
            tagged_text = "PLAYER 1 IS IT!"
            color = self.player1.color_shirt
        else:
            tagged_text = "PLAYER 2 IS IT!"
            color = self.player2.color_shirt

        text_surface = self.font_main.render(tagged_text, True, color)
        # place banner just under the top UI (dash bars)
        self.screen.blit(text_surface, 
                        (SCREEN_WIDTH // 2 - text_surface.get_width() // 2, 10 + 15 + 4))
        
        # Controls guide
        p1_text = self.font_small.render("P1: A / D move, W jump, R dash", True, BLACK)
        p2_text = self.font_small.render("P2: LEFT / RIGHT move, UP jump, U dash", True, BLACK)
        self.screen.blit(p1_text, (10, 50))
        self.screen.blit(p2_text, (10, 75))
        
        # Match timer (moved slightly lower so it doesn't overlap with top dash bars)
        timer_surface = self.font_main.render(f"Time: {self.match_seconds}s", True, BLACK)
        timer_x = SCREEN_WIDTH - timer_surface.get_width() - 10
        # place timer beneath the top dash bars (dash bars at y=10, height=15)
        timer_y = 10 + 15 + 8
        self.screen.blit(timer_surface, (timer_x, timer_y))

    def draw_dash_cooldown(self):
        """Draw dash cooldown bars for both players at the top of the screen."""
        # Player 1 Dash Cooldown Bar (Top Left)
        p1_bar_width = 200
        p1_bar_height = 15
        p1_bar_x = 10
        p1_bar_y = 10
        p1_cooldown_ratio = 1 - (self.player1.dash_cooldown / (FPS * 5))
        p1_fill_width = int(p1_bar_width * p1_cooldown_ratio)

        pygame.draw.rect(self.screen, BLACK, (p1_bar_x, p1_bar_y, p1_bar_width, p1_bar_height), 2)
        pygame.draw.rect(self.screen, self.player1.color_shirt, (p1_bar_x, p1_bar_y, p1_fill_width, p1_bar_height))

        # Player 2 Dash Cooldown Bar (Top Right)
        p2_bar_width = 200
        p2_bar_height = 15
        p2_bar_x = SCREEN_WIDTH - p2_bar_width - 10
        p2_bar_y = 10
        p2_cooldown_ratio = 1 - (self.player2.dash_cooldown / (FPS * 5))
        p2_fill_width = int(p2_bar_width * p2_cooldown_ratio)

        pygame.draw.rect(self.screen, BLACK, (p2_bar_x, p2_bar_y, p2_bar_width, p2_bar_height), 2)
        pygame.draw.rect(self.screen, self.player2.color_shirt, (p2_bar_x, p2_bar_y, p2_fill_width, p2_bar_height))

    def draw_game_over(self):
        """Draw game over screen with winner announcement."""
        if self.state == GameState.GAME_OVER_P1:
            title = "PLAYER 1 WINS!"
            color = self.player1.color_shirt
        else:
            title = "PLAYER 2 WINS!"
            color = self.player2.color_shirt
        
        # Title
        title_surface = self.font_big.render(title, True, color)
        self.screen.blit(title_surface, 
                        (SCREEN_WIDTH // 2 - title_surface.get_width() // 2,
                         SCREEN_HEIGHT // 2 - 60))
        
        # Instructions
        info1 = self.font_main.render("Press 6 to restart", True, BLACK)
        info2 = self.font_main.render("Press 5 to quit", True, BLACK)
        self.screen.blit(info1, 
                        (SCREEN_WIDTH // 2 - info1.get_width() // 2,
                         SCREEN_HEIGHT // 2 + 20))
        self.screen.blit(info2, 
                        (SCREEN_WIDTH // 2 - info2.get_width() // 2,
                         SCREEN_HEIGHT // 2 + 50))

    def draw_title_screen(self):
        """Draw the title screen."""
        self.screen.fill(UPSIDE_DOWN_SKY_BOTTOM)
        
        # Main title
        title_surface = self.font_huge.render("DANGER THINGS", True, BLACK)
        self.screen.blit(title_surface,
                         (SCREEN_WIDTH // 2 - title_surface.get_width() // 2,
                          SCREEN_HEIGHT // 2 - 150))
        
        # Subtitle
        subtitle_surface = self.font_big.render("Two Player Tag Game", True, BLACK)
        self.screen.blit(subtitle_surface,
                         (SCREEN_WIDTH // 2 - subtitle_surface.get_width() // 2,
                          SCREEN_HEIGHT // 2 + 50))
        
        # Instructions
        instructions_surface = self.font_main.render("Press SPACE to continue", True, BLACK)
        self.screen.blit(instructions_surface,
                         (SCREEN_WIDTH // 2 - instructions_surface.get_width() // 2,SCREEN_HEIGHT - 100))
        
        pygame.display.flip()
    
    def handle_title_screen_event(self, event):
        """Handle events on the title screen."""
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.show_title_screen = False
                self.show_color_selection_screen = True

    def draw_start_screen(self):
        """Draw the start screen with map selection options and previews."""
        self.screen.fill(UPSIDE_DOWN_SKY_BOTTOM)
        title_surface = self.font_big.render("Two Player Tag Game", True, BLACK)
        self.screen.blit(title_surface, 
                         (SCREEN_WIDTH // 2 - title_surface.get_width() // 2, 
                          SCREEN_HEIGHT // 2 - 280))

        instructions = [
            "Player 1: A/D to move, W to jump, R to dash",
            "Player 2: LEFT/RIGHT to move, UP to jump, U to dash",
        ]

        for i, text in enumerate(instructions):
            text_surface = self.font_main.render(text, True, BLACK)
            self.screen.blit(text_surface, 
                             (SCREEN_WIDTH // 2 - text_surface.get_width() // 2, 
                              SCREEN_HEIGHT // 2 - 200 + i * 30))
        
        # Draw map previews
        self.draw_map_preview_default(100, 300)
        self.draw_map_preview_floating(400, 300)
        self.draw_map_preview_narrow(700, 300)
        
        # Map selection labels
        label1 = self.font_main.render("1: Default", True, BLACK)
        self.screen.blit(label1, (100, 475))
        
        label2 = self.font_main.render("6: Floating", True, BLACK)
        self.screen.blit(label2, (400, 475))
        
        label3 = self.font_main.render("2: Narrow", True, BLACK)
        self.screen.blit(label3, (700, 475))
        
        # Start instruction
        space_text = self.font_main.render("Press 1, 2, or 6 to select a map and start", True, BLACK)
        self.screen.blit(space_text,
                         (SCREEN_WIDTH // 2 - space_text.get_width() // 2,
                          SCREEN_HEIGHT - 100))

        pygame.display.flip()
    
    def draw_map_preview_default(self, x, y):
        """Draw a small preview of the default map."""
        preview_width, preview_height = 250, 150
        pygame.draw.rect(self.screen, BLACK, (x, y, preview_width, preview_height), 2)
        
        # Draw sky gradient
        for iy in range(preview_height):
            ratio = iy / preview_height
            r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * ratio)
            g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * ratio)
            b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * ratio)
            pygame.draw.line(self.screen, (r, g, b), (x, y + iy), (x + preview_width, y + iy))
        
        # Draw mountains at consistent positions (same across all previews)
        # Mountain 1 (left) - darker shade
        mountain_points1 = [(x + 10, y + 115), (x + 45, y + 50), (x + 80, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_DARK, mountain_points1)
        # Mountain 2 (center) - lighter shade
        mountain_points2 = [(x + 85, y + 115), (x + 130, y + 40), (x + 175, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_LIGHT, mountain_points2)
        # Mountain 3 (right) - darker shade
        mountain_points3 = [(x + 180, y + 115), (x + 215, y + 55), (x + 250, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_DARK, mountain_points3)
        
        # Draw connected clouds (different spot from floating platforms preview)
        pygame.draw.circle(self.screen, WHITE, (x + 25, y + 20), 7)
        pygame.draw.circle(self.screen, WHITE, (x + 40, y + 20), 6)
        pygame.draw.circle(self.screen, WHITE, (x + 52, y + 22), 5)
        pygame.draw.circle(self.screen, WHITE, (x + 205, y + 25), 7)
        pygame.draw.circle(self.screen, WHITE, (x + 220, y + 25), 6)
        
        # Draw ground/base platform
        ground_y = y + preview_height - 20
        pygame.draw.line(self.screen, PLATFORM_BROWN, (x + 10, ground_y), (x + preview_width - 10, ground_y), 3)
        
        # Draw some floating platforms
        platform_positions = [(30, 100), (100, 80), (170, 120), (210, 70)]
        for px, py in platform_positions:
            pygame.draw.rect(self.screen, PLATFORM_BROWN, (x + px, y + py, 40, 8))
    
    def draw_map_preview_floating(self, x, y):
        """Draw a small preview of the floating platforms map."""
        preview_width, preview_height = 250, 150
        pygame.draw.rect(self.screen, BLACK, (x, y, preview_width, preview_height), 2)
        
        # Draw with upside down colors to distinguish
        for iy in range(preview_height):
            ratio = iy / preview_height
            r = int(UPSIDE_DOWN_SKY_TOP[0] + (UPSIDE_DOWN_SKY_BOTTOM[0] - UPSIDE_DOWN_SKY_TOP[0]) * ratio)
            g = int(UPSIDE_DOWN_SKY_TOP[1] + (UPSIDE_DOWN_SKY_BOTTOM[1] - UPSIDE_DOWN_SKY_TOP[1]) * ratio)
            b = int(UPSIDE_DOWN_SKY_TOP[2] + (UPSIDE_DOWN_SKY_BOTTOM[2] - UPSIDE_DOWN_SKY_TOP[2]) * ratio)
            pygame.draw.line(self.screen, (r, g, b), (x, y + iy), (x + preview_width, y + iy))
        
        # Draw mountains at consistent positions (same as other previews)
        # Mountain 1 (left) - upside-down darker shade
        mountain_points1 = [(x + 10, y + 115), (x + 45, y + 50), (x + 80, y + 115)]
        pygame.draw.polygon(self.screen, UPSIDE_DOWN_MOUNTAIN_DARK, mountain_points1)
        # Mountain 2 (center) - upside-down lighter shade
        mountain_points2 = [(x + 85, y + 115), (x + 130, y + 40), (x + 175, y + 115)]
        pygame.draw.polygon(self.screen, UPSIDE_DOWN_MOUNTAIN_LIGHT, mountain_points2)
        # Mountain 3 (right) - upside-down darker shade
        mountain_points3 = [(x + 180, y + 115), (x + 215, y + 55), (x + 250, y + 115)]
        pygame.draw.polygon(self.screen, UPSIDE_DOWN_MOUNTAIN_DARK, mountain_points3)
        
        # Draw connected dark grey clouds (different spot from default map preview)
        pygame.draw.circle(self.screen, GREY_CLOUD, (x + 35, y + 20), 6)
        pygame.draw.circle(self.screen, GREY_CLOUD, (x + 48, y + 20), 5)
        pygame.draw.circle(self.screen, GREY_CLOUD, (x + 60, y + 22), 5)
        pygame.draw.circle(self.screen, GREY_CLOUD, (x + 190, y + 25), 6)
        pygame.draw.circle(self.screen, GREY_CLOUD, (x + 205, y + 25), 5)
        
        # Draw floating platforms scattered
        floating_platforms = [(20, 30), (80, 70), (160, 40), (200, 100), (70, 120), (180, 80)]
        for px, py in floating_platforms:
            pygame.draw.rect(self.screen, PLATFORM_BROWN, (x + px, y + py, 35, 6))
    
    def draw_map_preview_narrow(self, x, y):
        """Draw a small preview of the narrow platforms map."""
        preview_width, preview_height = 250, 150
        pygame.draw.rect(self.screen, BLACK, (x, y, preview_width, preview_height), 2)
        
        # Draw sky gradient
        for iy in range(preview_height):
            ratio = iy / preview_height
            r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * ratio)
            g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * ratio)
            b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * ratio)
            pygame.draw.line(self.screen, (r, g, b), (x, y + iy), (x + preview_width, y + iy))
        
        # Draw mountains at consistent positions (same as other previews)
        # Mountain 1 (left) - darker shade
        mountain_points1 = [(x + 10, y + 115), (x + 45, y + 50), (x + 80, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_DARK, mountain_points1)
        # Mountain 2 (center) - lighter shade
        mountain_points2 = [(x + 85, y + 115), (x + 130, y + 40), (x + 175, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_LIGHT, mountain_points2)
        # Mountain 3 (right) - darker shade
        mountain_points3 = [(x + 180, y + 115), (x + 215, y + 55), (x + 250, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_DARK, mountain_points3)
        
        # Draw connected clouds (different spot from both other previews)
        pygame.draw.circle(self.screen, WHITE, (x + 60, y + 18), 7)
        pygame.draw.circle(self.screen, WHITE, (x + 75, y + 18), 6)
        pygame.draw.circle(self.screen, WHITE, (x + 88, y + 20), 5)
        pygame.draw.circle(self.screen, WHITE, (x + 165, y + 22), 7)
        pygame.draw.circle(self.screen, WHITE, (x + 180, y + 22), 5)
        
        # Draw ground/base platform
        ground_y = y + preview_height - 20
        pygame.draw.line(self.screen, PLATFORM_BROWN, (x + 10, ground_y), (x + preview_width - 10, ground_y), 3)
        
        # Draw narrow platforms in a vertical pattern
        narrow_platforms = [(50, 100), (120, 80), (190, 110), (70, 60), (150, 90), (210, 50)]
        for px, py in narrow_platforms:
            pygame.draw.rect(self.screen, PLATFORM_BROWN, (x + px, y + py, 25, 7))

    def draw_color_selection_screen(self):
        """Draw the color selection screen with player previews and 6 color options."""
        self.screen.fill(UPSIDE_DOWN_SKY_BOTTOM)
        title_surface = self.font_big.render("Select Player Colors", True, BLACK)
        self.screen.blit(title_surface, 
                         (SCREEN_WIDTH // 2 - title_surface.get_width() // 2, 
                          SCREEN_HEIGHT // 2 - 250))

        # All available colors
        all_colors = [
            ("Red", RED),
            ("Blue", BLUE),
            ("Green", GREEN),
            ("Yellow", YELLOW),
            ("Purple", PURPLE),
            ("Orange", ORANGE),
        ]

        # Create a smaller font for color options
        tiny_font = pygame.font.Font(None, 20)
        
        # Player 1 Section (centered on left half)
        p1_preview_x = SCREEN_WIDTH // 4 - 100
        p1_preview_y = 200
        p1_label = self.font_big.render("Player 1", True, BLACK)
        self.screen.blit(p1_label, (p1_preview_x - p1_label.get_width() // 2, 60))
        p1_inst = tiny_font.render("(A/D to cycle)", True, BLACK)
        self.screen.blit(p1_inst, (p1_preview_x - p1_inst.get_width() // 2, 120))

        # Draw player 1 preview (slightly larger)
        self.draw_player_preview(self.screen, p1_preview_x, p1_preview_y, self.player1.color_shirt, 2.4)

        # Color options for player 1 (centered under preview)
        for i, (name, color) in enumerate(all_colors):
            is_selected = self.player1.color_shirt == color
            is_taken = color == self.player2.color_shirt

            if is_selected:
                color_text = f"> {name} <"
                text_color = color
            elif is_taken:
                color_text = f"{name} (X)"
                text_color = (150, 150, 150)
            else:
                color_text = f"{name}"
                text_color = BLACK

            color_surface = tiny_font.render(color_text, True, text_color)
            cx = p1_preview_x - color_surface.get_width() // 2
            self.screen.blit(color_surface, (cx, 350 + i * 22))

        # Player 2 Section (centered on right half)
        p2_preview_x = (SCREEN_WIDTH * 3) // 4 + 100
        p2_preview_y = 200
        p2_label = self.font_big.render("Player 2", True, BLACK)
        self.screen.blit(p2_label, (p2_preview_x - p2_label.get_width() // 2, 60))
        p2_inst = tiny_font.render("(LEFT / RIGHT to cycle)", True, BLACK)
        self.screen.blit(p2_inst, (p2_preview_x - p2_inst.get_width() // 2, 120))

        # Draw player 2 preview (slightly larger)
        self.draw_player_preview(self.screen, p2_preview_x, p2_preview_y, self.player2.color_shirt, 2.4)

        # Color options for player 2 (centered under preview)
        for i, (name, color) in enumerate(all_colors):
            is_selected = self.player2.color_shirt == color
            is_taken = color == self.player1.color_shirt

            if is_selected:
                color_text = f"> {name} <"
                text_color = color
            elif is_taken:
                color_text = f"{name} (X)"
                text_color = (150, 150, 150)
            else:
                color_text = f"{name}"
                text_color = BLACK

            color_surface = tiny_font.render(color_text, True, text_color)
            cx = p2_preview_x - color_surface.get_width() // 2
            self.screen.blit(color_surface, (cx, 350 + i * 22))
        
        # (duplicate color list removed)

        # Confirmation instruction
        space_text = self.font_main.render("Press SPACE to confirm and continue to map selection", True, BLACK)
        self.screen.blit(space_text,
                         (SCREEN_WIDTH // 2 - space_text.get_width() // 2, SCREEN_HEIGHT - 60))

        pygame.display.flip()
    
    def draw_player_preview(self, surface, x, y, color, zoom):
        """Draw a simple player preview at the given position."""
        # Body
        body_radius = int(18 * zoom)
        pygame.draw.circle(surface, color, (x, y), body_radius)
        
        # Face
        eye_offset = int(6 * zoom)
        eye_r = int(4 * zoom)
        pupil_r = int(2 * zoom)
        pygame.draw.circle(surface, WHITE, (x - eye_offset, y - int(4 * zoom)), eye_r)
        pygame.draw.circle(surface, WHITE, (x + eye_offset, y - int(4 * zoom)), eye_r)
        pygame.draw.circle(surface, BLACK, (x - eye_offset, y - int(4 * zoom)), pupil_r)
        pygame.draw.circle(surface, BLACK, (x + eye_offset, y - int(4 * zoom)), pupil_r)
        
        # Simple smile
        mouth_rect = pygame.Rect(x - int(6 * zoom), y + int(2 * zoom), int(12 * zoom), int(6 * zoom))
        pygame.draw.arc(surface, BLACK, mouth_rect, math.pi, 2 * math.pi, int(2 * zoom))
        
        # Arms
        lx0, ly0 = x - int(18 * zoom), y + int(2 * zoom)
        lx1, ly1 = x - int(20 * zoom), y + int(16 * zoom)
        pygame.draw.line(surface, color, (lx0, ly0), (lx1, ly1), int(5 * zoom))
        pygame.draw.circle(surface, color, (lx1, ly1), int(4 * zoom))
        
        rx0, ry0 = x + int(18 * zoom), y + int(2 * zoom)
        rx1, ry1 = x + int(20 * zoom), y + int(16 * zoom)
        pygame.draw.line(surface, color, (rx0, ry0), (rx1, ry1), int(5 * zoom))
        pygame.draw.circle(surface, color, (rx1, ry1), int(4 * zoom))
        
        # Legs
        leg_y = y + int(18 * zoom)
        llx0, lly0 = x - int(6 * zoom), leg_y
        llx1, lly1 = x - int(6 * zoom), leg_y + int(14 * zoom)
        pygame.draw.line(surface, color, (llx0, lly0), (llx1, lly1), int(5 * zoom))
        pygame.draw.circle(surface, color, (llx1, lly1), int(3 * zoom))
        
        rlx0, rly0 = x + int(6 * zoom), leg_y
        rlx1, rly1 = x + int(6 * zoom), leg_y + int(14 * zoom)
        pygame.draw.line(surface, color, (rlx0, rly0), (rlx1, rly1), int(5 * zoom))
        pygame.draw.circle(surface, color, (rlx1, rly1), int(3 * zoom))

    def handle_color_selection_event(self, event):
        """Handle events during the color selection screen."""
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            # All available colors
            all_colors = [RED, BLUE, GREEN, YELLOW, PURPLE, ORANGE]
            
            # Player 1 color cycling with A/D keys (skip any colors taken by player 2)
            if event.key == pygame.K_a or event.key == pygame.K_d:
                current_index = all_colors.index(self.player1.color_shirt)
                step = -1 if event.key == pygame.K_a else 1
                # try up to len(all_colors) steps to find a color not taken
                for _ in range(len(all_colors)):
                    current_index = (current_index + step) % len(all_colors)
                    candidate = all_colors[current_index]
                    if candidate != self.player2.color_shirt:
                        self.player1.color_primary = candidate
                        self.player1.color_shirt = candidate
                        break
            
            # Player 2 color cycling with arrow keys (skip any colors taken by player 1)
            if event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                current_index = all_colors.index(self.player2.color_shirt)
                step = -1 if event.key == pygame.K_LEFT else 1
                for _ in range(len(all_colors)):
                    current_index = (current_index + step) % len(all_colors)
                    candidate = all_colors[current_index]
                    if candidate != self.player1.color_shirt:
                        self.player2.color_primary = candidate
                        self.player2.color_shirt = candidate
                        break
            
            if event.key == pygame.K_SPACE:
                self.show_color_selection_screen = False
                self.show_start_screen = True

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
            self.draw_dash_cooldown()
        else:
            self.draw_game_over()
        
        pygame.display.flip()

    def handle_event(self, event):
        """Handle pygame events."""
        global GRAVITY
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if self.show_start_screen:
                if event.key == pygame.K_1:
                    # Reset colors and gravity to defaults for normal map
                    GRAVITY = 0.5
                    self.current_sky_top = SKY_TOP
                    self.current_sky_bottom = SKY_BOTTOM
                    self.current_mountain_light = MOUNTAIN_LIGHT
                    self.current_mountain_dark = MOUNTAIN_DARK
                    self.current_cloud_color = WHITE
                    self.background_surface = self.create_background()
                    
                    self.platforms = self.generate_platforms()
                    self.show_start_screen = False
                elif event.key == pygame.K_6:
                    # Floating map uses upside-down sky and mountain colors and grey clouds
                    GRAVITY = 0.5
                    self.current_sky_top = UPSIDE_DOWN_SKY_TOP
                    self.current_sky_bottom = UPSIDE_DOWN_SKY_BOTTOM
                    self.current_mountain_light = UPSIDE_DOWN_MOUNTAIN_LIGHT
                    self.current_mountain_dark = UPSIDE_DOWN_MOUNTAIN_DARK
                    self.current_cloud_color = GREY_CLOUD
                    self.background_surface = self.create_background()

                    self.platforms = self.generate_floating_platforms()
                    self.show_start_screen = False
                elif event.key == pygame.K_2:
                    # Reset colors and gravity to defaults for narrow platforms
                    GRAVITY = 0.5
                    self.current_sky_top = SKY_TOP
                    self.current_sky_bottom = SKY_BOTTOM
                    self.current_mountain_light = MOUNTAIN_LIGHT
                    self.current_mountain_dark = MOUNTAIN_DARK
                    self.current_cloud_color = WHITE
                    self.background_surface = self.create_background()
                    
                    self.platforms = self.generate_narrow_platforms()
                    self.show_start_screen = False
            else:
                if event.key == pygame.K_5:
                    self.running = False
                
                if self.state == GameState.PLAYING:
                    if event.key == pygame.K_w:
                        self.player1.jump()
                    if event.key == pygame.K_UP:
                        self.player2.jump()
                    if event.key == pygame.K_r:
                        self.player1.dash()
                    if event.key == pygame.K_u:
                        self.player2.dash()
                else:
                    # Game over - restart on W
                    if event.key == pygame.K_6:
                        self.reset()

    def reset(self):
        """Reset game state for a new match."""
        global GRAVITY
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
        
        # Reset colors and gravity to defaults
        GRAVITY = 0.5
        self.current_sky_top = SKY_TOP
        self.current_sky_bottom = SKY_BOTTOM
        self.current_mountain_light = MOUNTAIN_LIGHT
        self.current_mountain_dark = MOUNTAIN_DARK
        self.current_cloud_color = WHITE
        
        # Regenerate platforms for variety
        self.platforms = self.generate_platforms()
        
        # Regenerate background with reset colors
        self.background_surface = self.create_background()
        
        # Reset camera
        self.camera = Camera(self.ground_top)

    def _is_too_close(self, platforms, candidate, pad_x, pad_y):
        """Reject platform placement when padded candidate bounds collide with any existing platform."""
        padded = candidate.rect.inflate(pad_x * 2, pad_y * 2)
        for existing in platforms:
            if padded.colliderect(existing.rect):
                return True
        return False

    def generate_platforms(self):
        """Generate the default map with evenly spaced common platforms (no overlaps)."""
        platforms = []
        platforms.append(Platform(0, MAP_HEIGHT - GROUND_HEIGHT, MAP_WIDTH, GROUND_HEIGHT))

        attempts = 0
        target = 26
        while len(platforms) - 1 < target and attempts < target * 30:
            attempts += 1
            w = random.randint(150, 320)
            x = random.randint(60, MAP_WIDTH - w - 60)
            y = random.randint(140, MAP_HEIGHT - GROUND_HEIGHT - 260)
            candidate = Platform(x, y, w, 44)
            if not self._is_too_close(platforms, candidate, 50, 120):
                platforms.append(candidate)
        return platforms

    def generate_floating_platforms(self):
        """Generate a map with mostly floating platforms (no overlaps)."""
        platforms = []
        platforms.append(Platform(0, MAP_HEIGHT - GROUND_HEIGHT, MAP_WIDTH, GROUND_HEIGHT))
        attempts = 0
        target = 20
        while len(platforms) - 1 < target and attempts < target * 25:
            attempts += 1
            fw = random.randint(120, 280)
            fx = random.randint(70, MAP_WIDTH - fw - 70)
            fy = random.randint(120, MAP_HEIGHT - 340)
            candidate = Platform(fx, fy, fw, 40)
            if not self._is_too_close(platforms, candidate, 60, 140):
                platforms.append(candidate)
        
        # Set low gravity for this map
        global GRAVITY
        GRAVITY = 0.2
        
        # Switch to upside down sky and mountains
        self.current_sky_top = UPSIDE_DOWN_SKY_TOP
        self.current_sky_bottom = UPSIDE_DOWN_SKY_BOTTOM
        self.current_mountain_light = UPSIDE_DOWN_MOUNTAIN_LIGHT
        self.current_mountain_dark = UPSIDE_DOWN_MOUNTAIN_DARK
        self.current_cloud_color = GREY_CLOUD
        
        # Regenerate background with new colors
        self.background_surface = self.create_background()
        
        return platforms

    def generate_narrow_platforms(self):
        """Generate a map with narrow and challenging platforms (no overlaps)."""
        platforms = []
        platforms.append(Platform(0, MAP_HEIGHT - GROUND_HEIGHT, MAP_WIDTH, GROUND_HEIGHT))
        attempts = 0
        target = 15
        while len(platforms) - 1 < target and attempts < target * 25:
            attempts += 1
            nw = random.randint(90, 160)
            nx = random.randint(60, MAP_WIDTH - nw - 60)
            ny = random.randint(120, MAP_HEIGHT - 340)
            candidate = Platform(nx, ny, nw, 30)
            if not self._is_too_close(platforms, candidate, 50, 120):
                platforms.append(candidate)
        return platforms

    def run(self):
        """Main game loop."""
        while self.running:
            for event in pygame.event.get():
                if self.show_title_screen:
                    self.handle_title_screen_event(event)
                elif self.show_color_selection_screen:
                    self.handle_color_selection_event(event)
                else:
                    self.handle_event(event)

            if self.show_title_screen:
                self.draw_title_screen()
            elif self.show_color_selection_screen:
                self.draw_color_selection_screen()
            elif self.show_start_screen:
                self.draw_start_screen()
            elif self.state == GameState.PLAYING:
                self.update()
                self.draw()
            elif self.state != GameState.PLAYING:
                self.draw()

            self.clock.tick(FPS)
        pygame.quit()


# Main entry point
if __name__ == "__main__":
    game = Game()
    game.run()