"""
Pico Elite - A simplified 1980s Elite-inspired space trading & combat game
for PicoCalc / Picoware.

Classic wireframe 3D feel on a 320x320 display.
Controls (PicoCalc keyboard):
  Arrows / WASD  : Pitch / Yaw
  Q / E          : Roll
  SPACE / CENTER : Thrust (hold)
  F              : Fire laser (if implemented)
  H              : Hyperspace jump
  D              : Attempt dock / market
  M              : Market menu (when docked)
  BACK / ESC     : Exit / menu
"""

from picoware.system.vector import Vector
from picoware.system.colors import *
from picoware.system.buttons import *
import math
import random
import gc

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREEN_W = 320
SCREEN_H = 320
CX = 160
CY = 140          # slightly above center for cockpit feel
FOV = 180.0       # perspective scale
NEAR = 0.5

# Colors (RGB565)
COL_STAR = TFT_WHITE
COL_PLANET = TFT_CYAN
COL_STATION = TFT_YELLOW
COL_SHIP = TFT_GREEN
COL_HUD = TFT_GREEN
COL_ALERT = TFT_RED
COL_BG = TFT_BLACK
COL_COCKPIT = TFT_DARKGREY

# ---------------------------------------------------------------------------
# Global game state
# ---------------------------------------------------------------------------
draw = None
input_mgr = None

# Player ship state
player_pos = Vector(0.0, 0.0, 0.0)   # world position
# Orientation as Euler angles (radians) - simple but effective for this scale
pitch = 0.0
yaw = 0.0
roll = 0.0
speed = 0.0
max_speed = 4.0
thrust = 0.0

fuel = 70.0
credits = 1000
cargo = {}          # commodity -> qty
cargo_capacity = 20
current_system = 0
docked = True       # start docked
hyperspace_timer = 0

# Starfield (local space points, regenerated on jump)
stars = []
NUM_STARS = 80

# Simple "universe" - 8 systems like a tiny Elite galaxy
SYSTEMS = [
    {"name": "Lave",      "tech": 5, "gov": "Democracy", "prod": "Rich Industrial", "x": 0, "y": 0},
    {"name": "Diso",      "tech": 8, "gov": "Corporate",  "prod": "Rich Industrial", "x": 12, "y": 5},
    {"name": "Riedquat",  "tech": 2, "gov": "Anarchy",    "prod": "Poor Agricultural", "x": -8, "y": 10},
    {"name": "Leesti",    "tech": 7, "gov": "Democracy",  "prod": "Average Industrial", "x": 5, "y": -9},
    {"name": "Zaonce",    "tech": 9, "gov": "Corporate",  "prod": "Rich Industrial", "x": 18, "y": 2},
    {"name": "Tianve",    "tech": 4, "gov": "Dictatorship","prod": "Average Agricultural", "x": -15, "y": -6},
    {"name": "Orrere",    "tech": 3, "gov": "Feudal",     "prod": "Poor Agricultural", "x": 3, "y": 14},
    {"name": "Reorte",    "tech": 6, "gov": "Democracy",  "prod": "Average Industrial", "x": -4, "y": -12},
]

COMMODITIES = [
    "Food", "Textiles", "Radioactives", "Slaves", "Liquor",
    "Luxuries", "Narcotics", "Computers", "Machinery", "Alloys",
    "Firearms", "Furs", "Minerals", "Gold", "Platinum"
]

# Market prices (base, modified by system)
market = {}

# Simple planet / station in local space
planet_pos = Vector(0.0, 0.0, 80.0)
planet_radius = 25.0
station_angle = 0.0

game_mode = "title"   # title, flight, market, jump
message = ""
message_timer = 0

# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def rotate_point(x, y, z, p, y_, r):
    """Apply pitch, yaw, roll to a point (order: roll -> pitch -> yaw)"""
    # Roll
    cr, sr = math.cos(r), math.sin(r)
    x1 = x * cr - y * sr
    y1 = x * sr + y * cr
    z1 = z
    # Pitch
    cp, sp = math.cos(p), math.sin(p)
    y2 = y1 * cp - z1 * sp
    z2 = y1 * sp + z1 * cp
    x2 = x1
    # Yaw
    cy, sy = math.cos(y_), math.sin(y_)
    x3 = x2 * cy + z2 * sy
    z3 = -x2 * sy + z2 * cy
    y3 = y2
    return x3, y3, z3

def project(x, y, z):
    """Simple perspective projection. Returns (sx, sy) or None if behind."""
    if z < NEAR:
        return None
    scale = FOV / z
    sx = CX + int(x * scale)
    sy = CY - int(y * scale)   # Y flipped for screen
    if sx < -50 or sx > SCREEN_W + 50 or sy < -50 or sy > SCREEN_H + 50:
        return None
    return sx, sy

# ---------------------------------------------------------------------------
# Starfield
# ---------------------------------------------------------------------------
def generate_stars():
    global stars
    stars = []
    for _ in range(NUM_STARS):
        # Random points in a large sphere around origin
        x = random.uniform(-200, 200)
        y = random.uniform(-150, 150)
        z = random.uniform(20, 300)
        stars.append(Vector(x, y, z))

def update_stars(dx, dy, dz):
    """Move stars opposite to player motion for relative motion feel."""
    for s in stars:
        s.x -= dx
        s.y -= dy
        s.z -= dz
        # Wrap / respawn if too close or behind
        if s.z < 5:
            s.x = random.uniform(-200, 200)
            s.y = random.uniform(-150, 150)
            s.z = random.uniform(150, 300)

# ---------------------------------------------------------------------------
# Market / Economy (very simplified Elite style)
# ---------------------------------------------------------------------------
def generate_market(sys_idx):
    global market
    sys = SYSTEMS[sys_idx]
    market = {}
    for i, name in enumerate(COMMODITIES):
        # Base price influenced by tech level and random
        base = 10 + i * 8 + random.randint(-5, 15)
        if "Agricultural" in sys["prod"] and name in ("Food", "Textiles", "Furs"):
            base = int(base * 0.6)
        if "Industrial" in sys["prod"] and name in ("Computers", "Machinery", "Alloys"):
            base = int(base * 0.7)
        if sys["gov"] == "Anarchy" and name in ("Slaves", "Narcotics", "Firearms"):
            base = int(base * 1.4)
        market[name] = max(2, base)

def buy(name, qty=1):
    global credits, cargo
    if name not in market:
        return False
    price = market[name] * qty
    current = sum(cargo.values())
    if current + qty > cargo_capacity:
        return False
    if credits < price:
        return False
    credits -= price
    cargo[name] = cargo.get(name, 0) + qty
    return True

def sell(name, qty=1):
    global credits, cargo
    if cargo.get(name, 0) < qty:
        return False
    price = market[name] * qty
    credits += price
    cargo[name] -= qty
    if cargo[name] <= 0:
        del cargo[name]
    return True

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def draw_stars(d):
    for s in stars:
        # Rotate star into view space using inverse player orientation
        # For simplicity we treat stars as local and move them
        px, py, pz = s.x, s.y, s.z
        # Apply inverse rotation roughly
        rx, ry, rz = rotate_point(px, py, pz, -pitch, -yaw, -roll)
        p = project(rx, ry, rz)
        if p:
            sx, sy = p
            # Brighter closer
            if rz < 60:
                d.pixel(Vector(sx, sy), TFT_WHITE)
            else:
                d.pixel(Vector(sx, sy), TFT_LIGHTGREY)

def draw_planet(d):
    # Planet is fixed relative for this simple version; transform relative to player
    # For demo: planet always ahead-ish, simple circle for performance
    # Relative position
    rel = Vector(planet_pos.x - player_pos.x,
                 planet_pos.y - player_pos.y,
                 planet_pos.z - player_pos.z)
    rx, ry, rz = rotate_point(rel.x, rel.y, rel.z, -pitch, -yaw, -roll)
    if rz < 5:
        return
    p = project(rx, ry, rz)
    if not p:
        return
    sx, sy = p
    # Apparent radius
    rad = max(3, int(planet_radius * FOV / rz))
    if rad > 120:
        rad = 120
    # Wireframe-ish circle (several arcs)
    d.circle(Vector(sx, sy), rad, COL_PLANET)
    # Simple latitude lines
    for i in range(1, 4):
        r2 = int(rad * math.sin(i * math.pi / 4))
        if r2 > 2:
            d.circle(Vector(sx, sy), r2, COL_PLANET)

def draw_cockpit(d):
    # Simple classic Elite style cockpit frame
    # Bottom panel
    d.fill_rectangle(Vector(0, 260), Vector(320, 60), TFT_BLACK)
    d.rect(Vector(0, 260), Vector(320, 60), COL_HUD)
    # Side frames
    d.line_custom(Vector(0, 0), Vector(40, 260), COL_COCKPIT)
    d.line_custom(Vector(320, 0), Vector(280, 260), COL_COCKPIT)
    # Crosshair
    d.line_custom(Vector(CX - 8, CY), Vector(CX + 8, CY), COL_HUD)
    d.line_custom(Vector(CX, CY - 8), Vector(CX, CY + 8), COL_HUD)

def draw_hud(d):
    sys = SYSTEMS[current_system]
    # Status line
    d.text(Vector(8, 268), f"{sys['name']}", COL_HUD, 1)
    d.text(Vector(8, 282), f"Cr:{credits}  Fuel:{int(fuel)}", COL_HUD, 1)
    d.text(Vector(8, 296), f"Spd:{speed:.1f}  Cargo:{sum(cargo.values())}/{cargo_capacity}", COL_HUD, 1)
    if docked:
        d.text(Vector(200, 268), "DOCKED", COL_ALERT, 1)
    if message_timer > 0:
        d.text(Vector(80, 120), message, COL_ALERT, 1)

def draw_title(d):
    d.fill_screen(COL_BG)
    d.text(Vector(70, 60), "PICO ELITE", TFT_YELLOW, 3)
    d.text(Vector(40, 110), "A tribute to the 1984 classic", COL_HUD, 1)
    d.text(Vector(50, 140), "by Braben & Bell", COL_HUD, 1)
    d.text(Vector(30, 190), "CENTER / SPACE  -  Launch", TFT_WHITE, 1)
    d.text(Vector(30, 210), "Arrows / WASD   -  Fly", TFT_WHITE, 1)
    d.text(Vector(30, 230), "H = Hyperspace   D = Dock", TFT_WHITE, 1)
    d.text(Vector(30, 250), "BACK            -  Quit", TFT_WHITE, 1)
    d.text(Vector(80, 290), "Commander, welcome.", COL_HUD, 1)

def draw_market(d):
    d.fill_screen(COL_BG)
    sys = SYSTEMS[current_system]
    d.text(Vector(10, 8), f"MARKET - {sys['name']}", TFT_YELLOW, 2)
    d.text(Vector(10, 30), f"Credits: {credits}   Cargo: {sum(cargo.values())}/{cargo_capacity}", COL_HUD, 1)
    y = 50
    d.text(Vector(10, y), "Commodity      Price  Own", COL_HUD, 1)
    y += 14
    for i, name in enumerate(COMMODITIES[:12]):  # limited for screen
        price = market.get(name, 0)
        own = cargo.get(name, 0)
        col = TFT_WHITE if own == 0 else TFT_GREEN
        d.text(Vector(10, y), f"{name[:12]:12} {price:4}  {own:2}", col, 1)
        y += 12
    d.text(Vector(10, 290), "1-9 Buy   SHIFT+1-9 Sell   BACK Exit", COL_HUD, 1)

# ---------------------------------------------------------------------------
# Game logic
# ---------------------------------------------------------------------------
def launch():
    global docked, game_mode, speed, message, message_timer
    if not docked:
        return
    docked = False
    game_mode = "flight"
    speed = 0.5
    message = "Launching..."
    message_timer = 40
    generate_stars()

def attempt_dock():
    global docked, game_mode, speed, message, message_timer
    if docked:
        game_mode = "market"
        return
    # Simple distance check
    dist = math.sqrt((player_pos.x - planet_pos.x)**2 +
                     (player_pos.y - planet_pos.y)**2 +
                     (player_pos.z - planet_pos.z)**2)
    if dist < planet_radius + 15 and speed < 1.5:
        docked = True
        speed = 0
        game_mode = "market"
        message = "Docked successfully"
        message_timer = 60
        generate_market(current_system)
    else:
        message = "Too far or too fast"
        message_timer = 40

def do_hyperspace():
    global current_system, player_pos, pitch, yaw, roll, speed, fuel
    global message, message_timer, hyperspace_timer, game_mode
    if fuel < 5:
        message = "Insufficient fuel"
        message_timer = 40
        return
    fuel -= 5 + random.randint(0, 5)
    # Jump to random other system
    old = current_system
    while current_system == old:
        current_system = random.randint(0, len(SYSTEMS) - 1)
    player_pos = Vector(0, 0, 0)
    pitch = yaw = roll = 0
    speed = 0
    generate_stars()
    generate_market(current_system)
    message = f"Arrived: {SYSTEMS[current_system]['name']}"
    message_timer = 80
    game_mode = "flight"
    docked = False

def update_flight(button):
    global pitch, yaw, roll, speed, thrust, player_pos, message_timer, message

    # Controls - arrows preferred, letters as alternatives
    if button == BUTTON_UP or button == BUTTON_W:
        pitch -= 0.05
    elif button == BUTTON_DOWN or button == BUTTON_S:
        pitch += 0.05
    if button == BUTTON_LEFT or button == BUTTON_A:
        yaw -= 0.05
    elif button == BUTTON_RIGHT or button == BUTTON_D:
        yaw += 0.05
    # Roll
    if button == BUTTON_Q:
        roll -= 0.06
    elif button == BUTTON_E:
        roll += 0.06

    # Thrust (hold space / center)
    if button in (BUTTON_SPACE, BUTTON_CENTER, BUTTON_OK, BUTTON_ENTER):
        thrust = 0.10
    else:
        thrust = -0.03  # natural drag

    speed = clamp(speed + thrust, 0.0, max_speed)

    # Move forward in facing direction
    fx, fy, fz = rotate_point(0.0, 0.0, 1.0, pitch, yaw, roll)
    dx = fx * speed * 0.7
    dy = fy * speed * 0.7
    dz = fz * speed * 0.7
    player_pos.x += dx
    player_pos.y += dy
    player_pos.z += dz

    update_stars(dx * 0.4, dy * 0.4, dz * 0.4)

    if message_timer > 0:
        message_timer -= 1

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
def start(view_manager):
    global draw, input_mgr, game_mode, credits, fuel, cargo, current_system
    global player_pos, pitch, yaw, roll, speed, docked

    draw = view_manager.draw
    input_mgr = view_manager.input_manager

    # Reset state
    game_mode = "title"
    credits = 1000
    fuel = 70
    cargo = {}
    current_system = 0
    player_pos = Vector(0, 0, 0)
    pitch = yaw = roll = 0.0
    speed = 0.0
    docked = True
    generate_market(0)
    generate_stars()

    draw.fill_screen(COL_BG)
    draw.swap()
    return True

def run(view_manager):
    global game_mode, message_timer

    button = input_mgr.button
    input_mgr.reset()

    if button == BUTTON_BACK or button == BUTTON_ESCAPE:
        if game_mode == "market":
            game_mode = "flight" if not docked else "title"
        elif game_mode == "flight":
            game_mode = "title"
        else:
            view_manager.back()
            return

    if game_mode == "title":
        if button in (BUTTON_CENTER, BUTTON_SPACE, BUTTON_OK, BUTTON_ENTER):
            launch()
        draw_title(draw)
        draw.swap()
        return

    if game_mode == "market":
        # Simple buy/sell with number keys
        if button >= BUTTON_1 and button <= BUTTON_9:
            idx = button - BUTTON_1
            if idx < len(COMMODITIES):
                name = COMMODITIES[idx]
                if buy(name):
                    message = f"Bought {name}"
                    message_timer = 30
                else:
                    message = "Cannot buy"
                    message_timer = 30
        # Note: SHIFT detection is limited; for full sell we can add later
        if button == BUTTON_0:
            # Sell first owned
            if cargo:
                name = next(iter(cargo))
                if sell(name):
                    message = f"Sold {name}"
                    message_timer = 30
        draw_market(draw)
        if message_timer > 0:
            draw.text(Vector(80, 270), message, COL_ALERT, 1)
            message_timer -= 1
        draw.swap()
        return

    # Flight mode
    if button == BUTTON_H:
        do_hyperspace()
    elif button == BUTTON_D or button == BUTTON_M:
        attempt_dock()

    update_flight(button)

    # Render
    draw.fill_screen(COL_BG)
    draw_stars(draw)
    draw_planet(draw)
    draw_cockpit(draw)
    draw_hud(draw)
    draw.swap()

def stop(view_manager):
    global draw, input_mgr, stars, cargo, market
    draw = None
    input_mgr = None
    stars = []
    cargo = {}
    market = {}
    gc.collect()