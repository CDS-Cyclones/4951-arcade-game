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
MAP_WIDTH = 2000
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
WHITE = (255, 255, 255)
GREY_CLOUD = (60, 60, 70)
BLACK = (0, 0, 0)
RED = (220, 50, 50)
BLUE = (50, 100, 220)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
PURPLE = (200, 50, 200)
ORANGE = (255, 165, 0)
SKY_TOP = (115, 156, 255)
SKY_BOTTOM = (210, 230, 255)
UPSIDE_DOWN_SKY_TOP = (40, 8, 48)
UPSIDE_DOWN_SKY_BOTTOM = (140, 23, 35)
MOUNTAIN_DARK = (80, 100, 80)
MOUNTAIN_LIGHT = (120, 140, 100)
UPSIDE_DOWN_MOUNTAIN_DARK = (20, 10, 20)
UPSIDE_DOWN_MOUNTAIN_LIGHT = (45, 30, 45)
PLATFORM_BROWN = (139, 89, 19)
PLATFORM_DARK = (101, 60, 14)
GRASS_COLOR = (100, 150, 50)
UPSIDE_DOWN_PLATFORM_BROWN = (84, 75, 67)
UPSIDE_DOWN_PLATFORM_DARK = (41, 38, 35)
UPSIDE_DOWN_GRASS_COLOR = (50, 67, 33)
UI_LIGHT = (230, 230, 230)
PLATFORM_Y_OFFSET = 80

class PlayerState(Enum):
    NORMAL = 1
    TAGGED = 2

class Platform:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)

    def draw(self, surface, zoom, cam_x, cam_y, platform_color, edge_color, grass_color):
        sx = int(self.rect.x * zoom - cam_x)
        sy = int(self.rect.y * zoom - cam_y)
        sw = max(1, int(self.rect.width * zoom))
        sh = max(1, int(self.rect.height * zoom))
        draw_rect = pygame.Rect(sx, sy, sw, sh)
        # Frustum culling
        if (draw_rect.right < 0 or draw_rect.left > SCREEN_WIDTH or 
            draw_rect.bottom < 0 or draw_rect.top > SCREEN_HEIGHT):
            return
        pygame.draw.rect(surface, platform_color, draw_rect)
        pygame.draw.rect(surface, edge_color, draw_rect, max(1, int(3 * zoom)))
        pygame.draw.line(surface, grass_color,
                        (draw_rect.left, draw_rect.top),
                        (draw_rect.right, draw_rect.top), max(1, int(4 * zoom)))

class Portal:
    """A bright red portal that switches the world colors."""
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)

    def draw(self, surface, zoom, cam_x, cam_y, alpha=1.0):
        # Transform to screen space
        sx = int(self.rect.x * zoom - cam_x)
        sy = int(self.rect.y * zoom - cam_y)
        sw = max(1, int(self.rect.width * zoom))
        sh = max(1, int(self.rect.height * zoom))
        draw_rect = pygame.Rect(sx, sy, sw, sh)

        # Frustum culling
        if (draw_rect.right < 0 or draw_rect.left > SCREEN_WIDTH or
            draw_rect.bottom < 0 or draw_rect.top > SCREEN_HEIGHT):
            return

        # Pulsating glow effect
        t = pygame.time.get_ticks() * 0.005
        glow_phase = (math.sin(t) + 1) * 0.5  # 0..1
        base_color = (255, 40, 40)
        glow_color = (255, 90 + int(100 * glow_phase), 90 + int(80 * glow_phase))

        radius = max(4, int(8 * zoom))
        a = max(0, min(1.0, alpha))

        # Draw on an alpha surface
        portal_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        def with_alpha(col):
            return (col[0], col[1], col[2], int(255 * a))

        pygame.draw.rect(portal_surf, with_alpha(base_color), portal_surf.get_rect(), border_radius=radius)
        pygame.draw.rect(portal_surf, with_alpha(glow_color), portal_surf.get_rect(), max(2, int(4 * zoom)), border_radius=radius)
        inner = portal_surf.get_rect().inflate(-max(3, int(6 * zoom)), -max(3, int(6 * zoom)))
        if inner.width > 0 and inner.height > 0:
            pygame.draw.rect(portal_surf, with_alpha(glow_color), inner, max(1, int(3 * zoom)), border_radius=radius)

        surface.blit(portal_surf, (draw_rect.x, draw_rect.y))

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
            self.vy = JUMP_VELOCITY
            self.jumps_remaining -= 1
            self.on_ground = False

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

        # Apply friction to stop small movements
        if self.on_ground and abs(self.vx) < 0.08 and self.dash_timer == 0:
            self.vx = 0
        
        # Animation state - set AFTER friction is applied
        # Trust on_ground flag completely - it's set properly by collision detection
        if self.on_ground:
            # On ground: idle when still, running when moving
            if abs(self.vx) == 0 and self.dash_timer == 0:
                self.current_animation = "idle"
                self.run_cycle = 0
                self.idle_phase += 0.04
                if self.idle_phase > math.tau:
                    self.idle_phase -= math.tau
            else:
                self.current_animation = "running"
                self.idle_phase = 0
                self.run_cycle += abs(self.vx) * 0.08
                if self.run_cycle > 4:
                    self.run_cycle -= 4
        else:
            # In air: jumping when not moving horizontally much, running when moving sideways
            if abs(self.vx) > 2.0:
                self.current_animation = "running"
                self.run_cycle += abs(self.vx) * 0.08
                if self.run_cycle > 4:
                    self.run_cycle -= 4
            else:
                self.current_animation = "jumping"
                self.run_cycle = 0

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
        margin_x = 160
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
        
        # Clamp zoom to reasonable limits and never show outside world bounds
        min_zoom_world = max(
            ZOOM_MIN,
            SCREEN_WIDTH / MAP_WIDTH,
            SCREEN_HEIGHT / max(self.ground_top, 1),
        )
        self.target_zoom = max(min_zoom_world, min(self.target_zoom, ZOOM_MAX))
        
        # 4. Calculate center point between players
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        
        # 5. Apply vertical constraints to keep ground visible but allow a lower view
        half_view_height = (SCREEN_HEIGHT / self.target_zoom) / 2

        # Allow the camera bottom to sit lower so part of the ground platform stays visible
        visible_ground = GROUND_HEIGHT + 60  # ensure full ground is visible even at wide zooms
        if center_y + half_view_height > self.ground_top + visible_ground:
            center_y = self.ground_top - half_view_height + visible_ground
        
        # Don't let camera go above world top
        if center_y - half_view_height < 0:
            center_y = half_view_height
        
        # 6. Convert world center to camera position
        # Camera position is top-left corner in world space
        self.target_x = center_x * self.target_zoom - SCREEN_WIDTH / 2
        self.target_y = center_y * self.target_zoom - SCREEN_HEIGHT / 2
        # Shift camera view downward to reveal more ground
        self.target_y += 24
        
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
        self.current_platform_brown = PLATFORM_BROWN
        self.current_platform_dark = PLATFORM_DARK
        self.current_grass_color = GRASS_COLOR
        
        # Initialize world
        self.platforms = self.generate_platforms()
        self.ground_top = MAP_HEIGHT - GROUND_HEIGHT
        
        # Pre-render background for performance
        self.background_surface = self.create_background()

        # Theme state
        self.is_upside_down = False
        self.transition_active = False
        self.transition_elapsed = 0.0
        self.transition_duration = 0.0
        self.transition_from = None
        self.transition_to = None
        self.ui_t = 0.0
        self.ui_from = 0.0
        self.ui_to = 0.0
        
        # Initialize players at spawn positions
        ground_spawn_y = self.ground_top - PLAYER_HEIGHT
        self.player1 = Player(200, ground_spawn_y, 1, RED, RED)
        self.player2 = Player(MAP_WIDTH - 200, ground_spawn_y, 2, BLUE, BLUE)
        
        # Initialize camera with new simplified class
        self.camera = Camera(self.ground_top)

        # Portal spawns on a platform and toggles world colors
        self.portal = None
        self.portal_cooldown = 0
        self.portal_spawn_delay = 0
        self.portal_needs_platform_fix = True  # spawn initial fallback then fix onto a platform
        self.portal_fade_timer = 0.0
        self.portal_fade_duration = 0.6
        # First portal: intentionally place with fallback (may float), then corrected next update
        self._spawn_portal_on_random_platform(40, 80, force_ground_fallback=True)
        
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

    def _ui_color(self):
        """Return a blended UI color based on transition progress (fades black->light)."""
        def lerp_color(c1, c2, t):
            return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        return lerp_color(BLACK, UI_LIGHT, max(0.0, min(1.0, self.ui_t)))

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

        # Color transition step
        if self.transition_active:
            self.transition_elapsed += 1.0 / FPS
            t = min(1.0, self.transition_elapsed / self.transition_duration)
            def lerp(c1, c2):
                return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
            (f_top, f_bot, f_light, f_dark, f_cloud, f_pbrown, f_pdark, f_grass) = self.transition_from
            (t_top, t_bot, t_light, t_dark, t_cloud, t_pbrown, t_pdark, t_grass) = self.transition_to
            self.current_sky_top = lerp(f_top, t_top)
            self.current_sky_bottom = lerp(f_bot, t_bot)
            self.current_mountain_light = lerp(f_light, t_light)
            self.current_mountain_dark = lerp(f_dark, t_dark)
            self.current_cloud_color = lerp(f_cloud, t_cloud)
            self.current_platform_brown = lerp(f_pbrown, t_pbrown)
            self.current_platform_dark = lerp(f_pdark, t_pdark)
            self.current_grass_color = lerp(f_grass, t_grass)
            self.ui_t = self.ui_from + (self.ui_to - self.ui_from) * t
            self.background_surface = self.create_background()
            if t >= 1.0:
                self.transition_active = False
                self.ui_t = self.ui_to

        # First-frame fix to move initial portal onto a platform
        if self.portal_needs_platform_fix and self.portal_spawn_delay == 0:
            if self.platforms:
                w, h = (self.portal.rect.size if self.portal else (40, 80))
                self._spawn_portal_on_random_platform(w, h)
                self.portal_needs_platform_fix = False

        # Handle portal spawn delay
        if self.portal_spawn_delay > 0:
            self.portal_spawn_delay -= 1
            if self.portal_spawn_delay == 0:
                # Spawn after delay if portal is absent
                if self.portal is None:
                    self._spawn_portal_on_random_platform(40, 80)

        # Fade-in timer for newly spawned portals
        if self.portal and self.portal_fade_timer < self.portal_fade_duration:
            self.portal_fade_timer = min(self.portal_fade_duration, self.portal_fade_timer + 1.0 / FPS)

        # Portal collision: toggle colors and start respawn delay
        if self.portal_cooldown > 0:
            self.portal_cooldown -= 1
        portal_ready = (
            self.portal
            and self.portal_cooldown == 0
            and self.portal_fade_timer >= self.portal_fade_duration
        )
        if portal_ready:
            if (self.player1.get_bounds().colliderect(self.portal.rect) or
                self.player2.get_bounds().colliderect(self.portal.rect)):
                if not self.is_upside_down:
                    self._start_transition_to_upside_down()
                    self.is_upside_down = True
                else:
                    self._start_transition_to_light()
                    self.is_upside_down = False
                # Despawn portal and schedule a delayed respawn (5-10s)
                self.portal = None
                self.portal_spawn_delay = random.randint(5 * FPS, 10 * FPS)
                self.portal_cooldown = max(10, FPS // 4)

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
        ui_color = self._ui_color()
        p1_text = self.font_small.render("P1: A / D move, W jump, R dash", True, ui_color)
        p2_text = self.font_small.render("P2: LEFT / RIGHT move, UP jump, U dash", True, ui_color)
        self.screen.blit(p1_text, (10, 50))
        self.screen.blit(p2_text, (10, 75))
        
        # Match timer (moved slightly lower so it doesn't overlap with top dash bars)
        timer_surface = self.font_main.render(f"Time: {self.match_seconds}s", True, ui_color)
        timer_x = SCREEN_WIDTH - timer_surface.get_width() - 10
        # place timer beneath the top dash bars (dash bars at y=10, height=15)
        timer_y = 10 + 15 + 8
        self.screen.blit(timer_surface, (timer_x, timer_y))

    def draw_dash_cooldown(self):
        """Draw dash cooldown bars for both players at the top of the screen."""
        ui_color = self._ui_color()
        # Player 1 Dash Cooldown Bar (Top Left)
        p1_bar_width = 200
        p1_bar_height = 15
        p1_bar_x = 10
        p1_bar_y = 10
        p1_cooldown_ratio = 1 - (self.player1.dash_cooldown / (FPS * 5))
        p1_fill_width = int(p1_bar_width * p1_cooldown_ratio)

        pygame.draw.rect(self.screen, ui_color, (p1_bar_x, p1_bar_y, p1_bar_width, p1_bar_height), 2)
        pygame.draw.rect(self.screen, self.player1.color_shirt, (p1_bar_x, p1_bar_y, p1_fill_width, p1_bar_height))

        # Player 2 Dash Cooldown Bar (Top Right)
        p2_bar_width = 200
        p2_bar_height = 15
        p2_bar_x = SCREEN_WIDTH - p2_bar_width - 10
        p2_bar_y = 10
        p2_cooldown_ratio = 1 - (self.player2.dash_cooldown / (FPS * 5))
        p2_fill_width = int(p2_bar_width * p2_cooldown_ratio)

        pygame.draw.rect(self.screen, ui_color, (p2_bar_x, p2_bar_y, p2_bar_width, p2_bar_height), 2)
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
        info1 = self.font_main.render("Press 6 for Title Screen", True, BLACK)
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
        """Draw a small preview of the floating platforms map (light colors)."""
        preview_width, preview_height = 250, 150
        pygame.draw.rect(self.screen, BLACK, (x, y, preview_width, preview_height), 2)
        
        # Draw sky gradient (light)
        for iy in range(preview_height):
            ratio = iy / preview_height
            r = int(SKY_TOP[0] + (SKY_BOTTOM[0] - SKY_TOP[0]) * ratio)
            g = int(SKY_TOP[1] + (SKY_BOTTOM[1] - SKY_TOP[1]) * ratio)
            b = int(SKY_TOP[2] + (SKY_BOTTOM[2] - SKY_TOP[2]) * ratio)
            pygame.draw.line(self.screen, (r, g, b), (x, y + iy), (x + preview_width, y + iy))
        
        # Mountains (light theme)
        mountain_points1 = [(x + 10, y + 115), (x + 45, y + 50), (x + 80, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_DARK, mountain_points1)
        mountain_points2 = [(x + 85, y + 115), (x + 130, y + 40), (x + 175, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_LIGHT, mountain_points2)
        mountain_points3 = [(x + 180, y + 115), (x + 215, y + 55), (x + 250, y + 115)]
        pygame.draw.polygon(self.screen, MOUNTAIN_DARK, mountain_points3)
        
        # Light clouds
        pygame.draw.circle(self.screen, WHITE, (x + 35, y + 20), 6)
        pygame.draw.circle(self.screen, WHITE, (x + 48, y + 20), 5)
        pygame.draw.circle(self.screen, WHITE, (x + 60, y + 22), 5)
        pygame.draw.circle(self.screen, WHITE, (x + 190, y + 25), 6)
        pygame.draw.circle(self.screen, WHITE, (x + 205, y + 25), 5)
        
        # Floating platforms scattered
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

    def _get_available_colors(self):
        """Return list of all available color options."""
        return [
            ("Red", RED),
            ("Blue", BLUE),
            ("Green", GREEN),
            ("Yellow", YELLOW),
            ("Purple", PURPLE),
            ("Orange", ORANGE),
        ]

    def draw_color_selection_screen(self):
        """Draw the color selection screen with player previews and 6 color options."""
        self.screen.fill(UPSIDE_DOWN_SKY_BOTTOM)
        title_surface = self.font_big.render("Select Player Colors", True, BLACK)
        self.screen.blit(title_surface, 
                         (SCREEN_WIDTH // 2 - title_surface.get_width() // 2, 
                          SCREEN_HEIGHT // 2 - 250))

        # All available colors
        all_colors = self._get_available_colors()

        # Create a smaller font for color options
        tiny_font = pygame.font.Font(None, 20)
        
        # Player 1 Section (centered on left half)
        p1_preview_x = SCREEN_WIDTH // 4 - 100
        p1_preview_y = 200
        p1_label = self.font_big.render("Player 1", True, BLACK)
        self.screen.blit(p1_label, (p1_preview_x - p1_label.get_width() // 2, 60))
        p1_inst = tiny_font.render("(Use joystick to cycle)", True, BLACK)
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
        p2_inst = tiny_font.render("(Use joystick to cycle)", True, BLACK)
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
            all_colors = [color for _, color in self._get_available_colors()]
            
            # Player 1 color cycling with Q/S, A/D keys (skip any colors taken by player 2)
            if event.key == pygame.K_q or event.key == pygame.K_s or event.key == pygame.K_a or event.key == pygame.K_d:
                current_index = all_colors.index(self.player1.color_shirt)
                step = -1 if (event.key == pygame.K_q or event.key == pygame.K_a) else 1
                # try up to len(all_colors) steps to find a color not taken
                for _ in range(len(all_colors)):
                    current_index = (current_index + step) % len(all_colors)
                    candidate = all_colors[current_index]
                    if candidate != self.player2.color_shirt:
                        self.player1.color_primary = candidate
                        self.player1.color_shirt = candidate
                        break
            
            # Player 2 color cycling with P/DOWN, LEFT/RIGHT keys (skip any colors taken by player 1)
            if event.key == pygame.K_p or event.key == pygame.K_DOWN or event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                current_index = all_colors.index(self.player2.color_shirt)
                step = -1 if (event.key == pygame.K_p or event.key == pygame.K_LEFT) else 1
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
            platform.draw(self.screen, zoom, cam_x, cam_y, 
                         self.current_platform_brown, 
                         self.current_platform_dark, 
                         self.current_grass_color)

        # Draw portal on top of platforms but behind players
        if self.portal:
            if self.portal_fade_duration <= 0:
                alpha = 1.0
            else:
                alpha = min(1.0, self.portal_fade_timer / self.portal_fade_duration)
            self.portal.draw(self.screen, zoom, cam_x, cam_y, alpha)
        
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
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if self.show_start_screen:
                if event.key == pygame.K_1:
                    # Default map: light colors + normal gravity
                    self._reset_to_default_theme()
                    self._set_normal_gravity()
                    self.platforms = self.generate_platforms()
                    self.show_start_screen = False
                elif event.key == pygame.K_6:
                    # Floating map gameplay: light colors + low gravity
                    self._reset_to_default_theme()
                    self._set_low_gravity()
                    self.platforms = self.generate_floating_platforms()
                    self.show_start_screen = False
                elif event.key == pygame.K_2:
                    # Narrow map: light colors + normal gravity
                    self._reset_to_default_theme()
                    self._set_normal_gravity()
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
                    # Game over - go to title screen on 6
                    if event.key == pygame.K_6:
                        self.go_to_title_screen()

    def _reset_to_default_theme(self):
        """Reset all theme settings to default normal map colors and gravity."""
        global GRAVITY
        GRAVITY = 0.5
        self.current_sky_top = SKY_TOP
        self.current_sky_bottom = SKY_BOTTOM
        self.current_mountain_light = MOUNTAIN_LIGHT
        self.current_mountain_dark = MOUNTAIN_DARK
        self.current_cloud_color = WHITE
        self.background_surface = self.create_background()
        self.is_upside_down = False
    
    def _set_floating_theme(self):
        """Set theme for floating platforms map with upside-down colors."""
        global GRAVITY
        GRAVITY = 0.2
        self.current_sky_top = UPSIDE_DOWN_SKY_TOP
        self.current_sky_bottom = UPSIDE_DOWN_SKY_BOTTOM
        self.current_mountain_light = UPSIDE_DOWN_MOUNTAIN_LIGHT
        self.current_mountain_dark = UPSIDE_DOWN_MOUNTAIN_DARK
        self.current_cloud_color = GREY_CLOUD
        self.background_surface = self.create_background()

    def _start_color_transition(self, target_palette, target_ui_t, duration=0.6):
        """Begin a smooth transition to the target palette over duration seconds."""
        self.transition_active = True
        self.transition_elapsed = 0.0
        self.transition_duration = max(0.05, duration)
        self.transition_from = (
            self.current_sky_top,
            self.current_sky_bottom,
            self.current_mountain_light,
            self.current_mountain_dark,
            self.current_cloud_color,
            self.current_platform_brown,
            self.current_platform_dark,
            self.current_grass_color,
        )
        self.transition_to = target_palette
        self.ui_from = self.ui_t
        self.ui_to = target_ui_t

    def _apply_upside_down_colors(self):
        """Apply upside-down color palette without changing gravity (instant)."""
        self.current_sky_top = UPSIDE_DOWN_SKY_TOP
        self.current_sky_bottom = UPSIDE_DOWN_SKY_BOTTOM
        self.current_mountain_light = UPSIDE_DOWN_MOUNTAIN_LIGHT
        self.current_mountain_dark = UPSIDE_DOWN_MOUNTAIN_DARK
        self.current_cloud_color = GREY_CLOUD
        self.current_platform_brown = UPSIDE_DOWN_PLATFORM_BROWN
        self.current_platform_dark = UPSIDE_DOWN_PLATFORM_DARK
        self.current_grass_color = UPSIDE_DOWN_GRASS_COLOR
        self.background_surface = self.create_background()

    def _apply_light_colors(self):
        """Apply light color palette without changing gravity (instant)."""
        self.current_sky_top = SKY_TOP
        self.current_sky_bottom = SKY_BOTTOM
        self.current_mountain_light = MOUNTAIN_LIGHT
        self.current_mountain_dark = MOUNTAIN_DARK
        self.current_cloud_color = WHITE
        self.current_platform_brown = PLATFORM_BROWN
        self.current_platform_dark = PLATFORM_DARK
        self.current_grass_color = GRASS_COLOR
        self.background_surface = self.create_background()

    def _start_transition_to_upside_down(self):
        target = (
            UPSIDE_DOWN_SKY_TOP,
            UPSIDE_DOWN_SKY_BOTTOM,
            UPSIDE_DOWN_MOUNTAIN_LIGHT,
            UPSIDE_DOWN_MOUNTAIN_DARK,
            GREY_CLOUD,
            UPSIDE_DOWN_PLATFORM_BROWN,
            UPSIDE_DOWN_PLATFORM_DARK,
            UPSIDE_DOWN_GRASS_COLOR,
        )
        self._start_color_transition(target, 1.0)

    def _start_transition_to_light(self):
        target = (
            SKY_TOP,
            SKY_BOTTOM,
            MOUNTAIN_LIGHT,
            MOUNTAIN_DARK,
            WHITE,
            PLATFORM_BROWN,
            PLATFORM_DARK,
            GRASS_COLOR,
        )
        self._start_color_transition(target, 0.0)

    def _spawn_portal_on_random_platform(self, portal_w=40, portal_h=80, force_ground_fallback=False):
        """Place the portal on top of a random non-ground platform.
        If platforms missing or forced, use a ground fallback near center.
        """
        if not self.platforms or force_ground_fallback:
            x = MAP_WIDTH // 2 - portal_w // 2
            y = max(0, self.ground_top - portal_h)
            if self.portal is None:
                self.portal = Portal(x, y, portal_w, portal_h)
            else:
                self.portal.rect.update(x, y, portal_w, portal_h)
            self.portal_fade_timer = 0.0
            return

        # Exclude ground platform (assumed first in list) and require enough width
        candidates = [p for p in self.platforms[1:] if p.rect.width >= portal_w + 10]

        # If no suitable non-ground platforms, fall back to widest non-ground or ground
        if not candidates:
            non_ground = self.platforms[1:] if len(self.platforms) > 1 else []
            if non_ground:
                platform = max(non_ground, key=lambda p: p.rect.width)
            else:
                platform = self.platforms[0]
        else:
            platform = random.choice(candidates)

        # Center the portal on the chosen platform and keep inside bounds
        x = platform.rect.centerx - portal_w // 2
        x = max(platform.rect.left, min(x, platform.rect.right - portal_w))
        y = platform.rect.top - portal_h
        y = max(0, y)

        if self.portal is None:
            self.portal = Portal(x, y, portal_w, portal_h)
        else:
            self.portal.rect.update(x, y, portal_w, portal_h)
        self.portal_fade_timer = 0.0

    def _set_normal_gravity(self):
        global GRAVITY
        GRAVITY = 0.5

    def _set_low_gravity(self):
        global GRAVITY
        GRAVITY = 0.2

    def reset(self):
        """Reset game state for a new match."""
        ground_spawn_y = self.ground_top - PLAYER_HEIGHT
        self.player1 = Player(200, ground_spawn_y, 1, RED, RED)
        self.player2 = Player(MAP_WIDTH - 200, ground_spawn_y, 2, BLUE, BLUE)
        
        self.player1.is_tagged = True
        self.player2.is_tagged = False
        self.tag_timer = 0
        
        self.p1_tag_time = 0
        self.p2_tag_time = 0
        self.match_seconds = MATCH_DURATION
        self.frame_counter = 0
        self.state = GameState.PLAYING
        
        # Reset to default theme
        self._reset_to_default_theme()
        self._set_normal_gravity()
        
        # Regenerate platforms for variety
        self.platforms = self.generate_platforms()
        
        # Reset camera
        self.camera = Camera(self.ground_top)

        # Recreate portal: spawn fallback then fix onto platform next update
        self.portal_cooldown = 0
        self.portal_spawn_delay = 0
        self.portal_needs_platform_fix = True
        self.portal_fade_timer = 0.0
        self.portal = None
        self._spawn_portal_on_random_platform(40, 80, force_ground_fallback=True)

    def go_to_title_screen(self):
        """Reset gameplay state, then show the DANGER THINGS title screen."""
        # Ensure a fresh gameplay state when players return from the title flow
        self.reset()
        # Show title flow
        self.show_title_screen = True
        self.show_color_selection_screen = False
        self.show_start_screen = False

    def _is_too_close(self, platforms, candidate, pad_x, pad_y):
        """Reject platform placement when padded candidate bounds collide with any existing platform."""
        padded = candidate.rect.inflate(pad_x * 2, pad_y * 2)
        return any(padded.colliderect(existing.rect) for existing in platforms)

    def generate_platforms(self):
        """Generate the default map with evenly spaced common platforms (no overlaps)."""
        platforms = []
        platforms.append(Platform(0, MAP_HEIGHT - GROUND_HEIGHT, MAP_WIDTH, GROUND_HEIGHT))

        attempts = 0
        target = 26
        while len(platforms) - 1 < target and attempts < target * 30:
            attempts += 1
            w = random.randint(150, 320)
            x = random.randint(10, MAP_WIDTH - w - 10)
            y = random.randint(140 + PLATFORM_Y_OFFSET, MAP_HEIGHT - GROUND_HEIGHT - 260 + PLATFORM_Y_OFFSET)
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
            fx = random.randint(10, MAP_WIDTH - fw - 10)
            fy = random.randint(120 + PLATFORM_Y_OFFSET, MAP_HEIGHT - 340 + PLATFORM_Y_OFFSET)
            candidate = Platform(fx, fy, fw, 40)
            if not self._is_too_close(platforms, candidate, 60, 140):
                platforms.append(candidate)
        
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
            nx = random.randint(10, MAP_WIDTH - nw - 10)
            ny = random.randint(120 + PLATFORM_Y_OFFSET, MAP_HEIGHT - 340 + PLATFORM_Y_OFFSET)
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