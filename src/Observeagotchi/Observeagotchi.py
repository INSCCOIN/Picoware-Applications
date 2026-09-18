# PicoCalc Picoware — Observergotchi
# Copy to /picoware/apps/observergotchi.py
# INSCCOIN 2026
# Ported from SharkDeck Observergotchi.
# Inspired by Pwnagotchi, but 100% passive: scan / observe only.
# VERSION 1.4
# HOURS SPENT HERE: 15

from picoware.system.buttons import (
    BUTTON_A,
    BUTTON_BACK,
    BUTTON_CENTER,
    BUTTON_DOWN,
    BUTTON_ENTER,
    BUTTON_ESCAPE,
    BUTTON_H,
    BUTTON_L,
    BUTTON_LEFT,
    BUTTON_NONE,
    BUTTON_R,
    BUTTON_RIGHT,
    BUTTON_S,
    BUTTON_SPACE,
    BUTTON_START,
    BUTTON_UP,
)
from picoware.system.colors import (
    TFT_BLACK,
    TFT_CYAN,
    TFT_DARKGREY,
    TFT_GREEN,
    TFT_ORANGE,
    TFT_RED,
    TFT_WHITE,
    TFT_YELLOW,
)
from picoware.system.font import FONT_MEDIUM, FONT_SMALL, FONT_XTRA_SMALL
from picoware.system.vector import Vector

import json
import random
import time

Keyboard = None
try:
    from picoware.gui.keyboard import Keyboard as _Keyboard
    Keyboard = _Keyboard
except Exception:
    Keyboard = None

try:
    from picoware.system.boards import BOARD_HAS_WIFI
except ImportError:
    BOARD_HAS_WIFI = True

SAVE_CANDIDATES = (
    "/sd/observergotchi.json",
    "/sd/picoware/observergotchi.json",
    "observergotchi.json",
    "/picoware/observergotchi.json",
)

BG = TFT_BLACK
FG = TFT_WHITE
ACCENT = TFT_GREEN
DIM = TFT_DARKGREY
WARN = TFT_ORANGE
ALERT = TFT_RED
INFO = TFT_CYAN
GOLD = TFT_YELLOW

FACES = {
    "happy": "(^_^)",
    "excited": "(>v<)",
    "bored": "(-_-)",
    "curious": "(?_?)",
    "sleeping": "(-_-)z",
    "surprised": "(O_O)",
    "sad": "(T_T)",
    "cool": "(B-)",
    "thinking": "(._.)",
    "love": "(<3)",
    "neutral": "(._.)",
}

AUTH_NAME = {
    0: "OPEN",
    1: "WEP",
    2: "WPA",
    3: "WPA2",
    4: "WPA/WPA2",
    5: "WPA2-ENT",
    6: "WPA3",
    7: "WPA2/WPA3",
    8: "WPA3-ENT",
}

INTERVALS = (15, 30, 60, 120)

_state = {
    "pet": None,
    "mode": "face",
    "dirty": True,
    "auto": False,
    "interval": 30,
    "last_scan_ms": 0,
    "scanning": False,
    "status": "awake",
    "toast": "",
    "toast_ms": 0,
    "kb": None,
    "blink": 0,
    "last_new": (0, 0, 0),
    "has_wifi": True,
    "page": 0,
    "boot_ignore": 0,
    "paint_ok": True,
    "thought": "",
    "thought_ms": 0,
    "blink_shut": False,
}


def _now():
    try:
        t = time.time()
        if t and t > 1000:
            return t
    except Exception:
        pass
    try:
        return time.ticks_ms() / 1000.0
    except Exception:
        return 0.0


def _ticks():
    try:
        return time.ticks_ms()
    except Exception:
        return int(_now() * 1000)


def _ticks_diff(a, b):
    try:
        return time.ticks_diff(a, b)
    except Exception:
        return a - b


def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _rssi_pct(rssi):
    try:
        r = int(rssi)
    except Exception:
        return 0
    return _clamp(2 * (r + 100), 0, 100)


def _bssid_hex(raw):
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.upper()
    try:
        return ":".join("%02X" % b for b in raw)
    except Exception:
        return str(raw)


def _ssid_text(raw):
    if raw is None:
        return "<Hidden>"
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except Exception:
            raw = raw.decode("latin-1", "ignore")
    s = str(raw).strip()
    return s if s else "<Hidden>"


def _sec_name(sec):
    if sec is None:
        return "OPEN"
    if isinstance(sec, str):
        s = sec.strip()
        return s if s else "OPEN"
    try:
        n = int(sec)
    except Exception:
        return str(sec)
    return AUTH_NAME.get(n, "SEC%d" % n)


class Observergotchi:
    def __init__(self):
        self.name = "Observer"
        self.born = _now()
        self.last_active = _now()
        self.age_hours = 0.0
        self.mood = "curious"
        self.boredom = 20
        self.excitement = 40
        self.energy = 80
        self.networks_seen = 0
        self.unique_ssids = []
        self.unique_bssids = []
        self._ssid_set = {}
        self._bssid_set = {}
        self.open_networks = 0
        self.wpa3_networks = 0
        self.interesting_found = 0
        self.scans_done = 0
        self.total_uptime_minutes = 0
        self.recent = []
        self.last_scan_count = 0

    def remember_sets(self):
        self._ssid_set = {}
        for s in self.unique_ssids:
            self._ssid_set[s] = 1
        self._bssid_set = {}
        for b in self.unique_bssids:
            self._bssid_set[b] = 1

    def to_dict(self):
        return {
            "name": self.name,
            "born": self.born,
            "last_active": self.last_active,
            "age_hours": self.age_hours,
            "mood": self.mood,
            "boredom": self.boredom,
            "excitement": self.excitement,
            "energy": self.energy,
            "networks_seen": self.networks_seen,
            "unique_ssids": list(self.unique_ssids),
            "unique_bssids": list(self.unique_bssids),
            "open_networks": self.open_networks,
            "wpa3_networks": self.wpa3_networks,
            "interesting_found": self.interesting_found,
            "scans_done": self.scans_done,
            "total_uptime_minutes": self.total_uptime_minutes,
            "recent": self.recent[:8],
            "last_scan_count": self.last_scan_count,
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        if not isinstance(data, dict):
            return obj
        for k, v in data.items():
            if k.startswith("_"):
                continue
            if hasattr(obj, k):
                setattr(obj, k, v)
        if not isinstance(obj.unique_ssids, list):
            obj.unique_ssids = list(obj.unique_ssids) if obj.unique_ssids else []
        if not isinstance(obj.unique_bssids, list):
            obj.unique_bssids = list(obj.unique_bssids) if obj.unique_bssids else []
        if not isinstance(obj.recent, list):
            obj.recent = []
        obj.remember_sets()
        return obj

    def update_time(self):
        current = _now()
        last = self.last_active
        try:
            last = float(last)
        except Exception:
            last = current
        if last > current + 60:
            last = current
        delta = (current - last) / 3600.0
        if delta < 0:
            delta = 0
        if delta > 24 * 30:
            delta = 0
        self.age_hours = float(self.age_hours) + delta
        self.total_uptime_minutes = float(self.total_uptime_minutes) + delta * 60
        self.last_active = current
        self.boredom = _clamp(float(self.boredom) + delta * 8, 0, 100)
        self.excitement = _clamp(float(self.excitement) - delta * 5, 0, 100)
        self.energy = _clamp(float(self.energy) - delta * 2, 10, 100)

    def get_face(self):
        if self.energy < 20:
            return FACES["sleeping"]
        if self.excitement > 75:
            return FACES["excited"]
        if self.boredom > 70:
            return FACES["bored"]
        return FACES.get(self.mood, FACES["neutral"])

    def speak(self):
        lines = {
            "happy": (
                "The airwaves feel friendly today.",
                "So many networks... I like this place.",
                "I'm in a good mood. Keep exploring!",
            ),
            "excited": (
                "New signals! New signals everywhere!",
                "This is the best day ever!",
                "I can feel the packets flowing!",
            ),
            "bored": (
                "Same old networks... nothing new.",
                "Is this all there is?",
                "I'm getting bored... take me somewhere else.",
            ),
            "curious": (
                "I wonder what's hiding in that SSID...",
                "Hmm... interesting encryption choices.",
                "The spectrum is full of secrets.",
            ),
            "cool": (
                "Just another day observing the wild.",
                "I've seen things you wouldn't believe.",
                "Stay curious, human.",
            ),
            "surprised": (
                "Whoa! Did you see that open network?!",
                "Unexpected signal detected!",
                "That was new...",
            ),
            "sleeping": (
                "zzZ... just a few more packets...",
                "Wake me if something interesting shows up.",
                "Low energy. Soft scan only.",
            ),
        }
        mood = self.mood
        if self.energy < 20:
            mood = "sleeping"
        pool = lines.get(mood, lines["curious"])
        return pool[random.randrange(len(pool))]


def _storage(vm):
    try:
        return vm.storage
    except Exception:
        return None


def _load_pet(vm):
    st = _storage(vm)
    for path in SAVE_CANDIDATES:
        raw = None
        try:
            if st is not None and hasattr(st, "exists"):
                if not st.exists(path):
                    continue
            if st is not None and hasattr(st, "read"):
                raw = st.read(path)
            else:
                with open(path, "r") as f:
                    raw = f.read()
        except Exception:
            raw = None
        if not raw:
            continue
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            data = json.loads(raw)
            return Observergotchi.from_dict(data)
        except Exception:
            continue
    return None


def _save_pet(vm, pet):
    if pet is None:
        return False
    blob = json.dumps(pet.to_dict())
    st = _storage(vm)
    last_err = None
    for path in SAVE_CANDIDATES:
        try:
            if st is not None and hasattr(st, "write"):
                if st.write(path, blob, mode="w"):
                    return True
            else:
                with open(path, "w") as f:
                    f.write(blob)
                return True
        except Exception as e:
            last_err = e
    return last_err is None


def _parse_scan_row(row):
    ssid = "<Hidden>"
    bssid = ""
    signal = 0
    security = "OPEN"
    ch = 0
    if row is None:
        return None
    if isinstance(row, dict):
        ssid = _ssid_text(row.get("ssid") or row.get("SSID"))
        bssid = _bssid_hex(row.get("bssid") or row.get("BSSID"))
        rssi = row.get("rssi", row.get("RSSI", row.get("signal", 0)))
        signal = _rssi_pct(rssi) if not isinstance(rssi, str) else _rssi_pct(0)
        if isinstance(rssi, int) and 0 <= rssi <= 100 and "rssi" not in row:
            signal = rssi
        security = _sec_name(row.get("security") or row.get("auth") or row.get("authmode"))
        ch = int(row.get("channel") or row.get("ch") or 0)
    else:
        try:
            n = len(row)
        except Exception:
            return None
        if n >= 1:
            ssid = _ssid_text(row[0])
        if n >= 2:
            bssid = _bssid_hex(row[1])
        if n >= 3:
            try:
                ch = int(row[2])
            except Exception:
                ch = 0
        if n >= 4:
            signal = _rssi_pct(row[3])
        if n >= 5:
            security = _sec_name(row[4])
    return {"ssid": ssid, "bssid": bssid, "signal": signal, "security": security, "ch": ch}


def _passive_scan(vm):
    nets = []
    wifi = None
    try:
        wifi = vm.wifi
    except Exception:
        wifi = None
    raw = None
    if wifi is not None:
        try:
            raw = wifi.scan()
        except Exception:
            raw = None
        if raw is None:
            try:
                if hasattr(wifi, "wlan") and wifi.wlan is not None:
                    try:
                        wifi.wlan.active(True)
                    except Exception:
                        pass
                    raw = wifi.wlan.scan()
            except Exception:
                raw = None
    if raw is None:
        try:
            import network

            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
            raw = wlan.scan()
        except Exception:
            raw = None
    if not raw:
        return nets
    seen = {}
    for row in raw:
        net = _parse_scan_row(row)
        if net is None:
            continue
        key = net["bssid"] or net["ssid"]
        if key in seen:
            continue
        seen[key] = 1
        nets.append(net)
    return nets


def _observe(pet, networks):
    pet.scans_done += 1
    pet.last_scan_count = len(networks)
    new_ssids = 0
    new_bssids = 0
    open_count = 0
    wpa3_count = 0
    recent = []
    for net in networks:
        ssid = net["ssid"]
        bssid = net["bssid"]
        if ssid not in pet._ssid_set:
            pet._ssid_set[ssid] = 1
            pet.unique_ssids.append(ssid)
            new_ssids += 1
        if bssid and bssid not in pet._bssid_set:
            pet._bssid_set[bssid] = 1
            pet.unique_bssids.append(bssid)
            new_bssids += 1
        sec = str(net["security"]).upper()
        if "OPEN" in sec or sec in ("", "--", "NONE", "0"):
            open_count += 1
        if "WPA3" in sec:
            wpa3_count += 1
        recent.append(net)
    pet.networks_seen += len(networks)
    pet.open_networks += open_count
    pet.wpa3_networks += wpa3_count
    pet.recent = recent[:12]
    if new_ssids > 3 or new_bssids > 5:
        pet.mood = "excited"
        pet.excitement = _clamp(pet.excitement + 25, 0, 100)
        pet.boredom = _clamp(pet.boredom - 20, 0, 100)
        pet.interesting_found += 1
    elif open_count > 0:
        pet.mood = "surprised"
        pet.excitement = _clamp(pet.excitement + 15, 0, 100)
    elif new_ssids > 0:
        pet.mood = "curious"
        pet.boredom = _clamp(pet.boredom - 10, 0, 100)
    elif pet.boredom > 60:
        pet.mood = "bored"
    else:
        pet.mood = random.choice(("happy", "curious", "cool"))
    pet.energy = _clamp(pet.energy - 1, 10, 100)
    _set_thought(pet, True)
    return new_ssids, new_bssids, open_count


def _do_scan(vm):
    pet = _state["pet"]
    if pet is None:
        return
    _state["scanning"] = True
    _state["status"] = "scanning..."
    _state["dirty"] = True
    _paint(vm)
    try:
        networks = _passive_scan(vm)
        new_s, new_b, opens = _observe(pet, networks)
        _state["last_new"] = (new_s, new_b, opens)
        _state["status"] = "%d nets  +%d ssid  %d open" % (len(networks), new_s, opens)
        _toast("%d seen  +%d SSID  %d open" % (len(networks), new_s, opens))
        _save_pet(vm, pet)
    except Exception as e:
        _state["status"] = "scan failed"
        _toast("scan failed")
        try:
            vm.log("observergotchi scan: %s" % e)
        except Exception:
            pass
    _state["last_scan_ms"] = _ticks()
    _state["scanning"] = False
    _state["dirty"] = True


def _toast(msg):
    _state["toast"] = msg
    _state["toast_ms"] = _ticks()
    _state["dirty"] = True


def _set_thought(pet, force=False):
    if not force and _state.get("thought"):
        return _state["thought"]
    try:
        _state["thought"] = pet.speak()
    except Exception:
        _state["thought"] = "watching the airwaves..."
    _state["thought_ms"] = _ticks()
    return _state["thought"]


def _text_w(draw, text, font):
    try:
        n = draw.len(text, font)
        if n:
            return int(n)
    except Exception:
        pass
    if font == FONT_XTRA_SMALL:
        return 6 * len(text)
    return 10 * len(text)


def _bar(draw, x, y, w, h, pct, fill, back=DIM):
    draw.rect(Vector(x, y), Vector(w, h), FG)
    inner = int((w - 2) * _clamp(pct, 0, 100) / 100.0)
    if inner > 0:
        draw.fill_rectangle(Vector(x + 1, y + 1), Vector(inner, h - 2), fill)
    if inner < w - 2:
        draw.fill_rectangle(Vector(x + 1 + inner, y + 1), Vector((w - 2) - inner, h - 2), back)


def _blob(draw, x, y, w, h, color):
    draw.fill_rectangle(Vector(x, y), Vector(w, h), color)


def _draw_creature(draw, cx, cy, pet, blink):
    mood = pet.mood
    if pet.energy < 20:
        mood = "sleeping"
    elif pet.excitement > 75:
        mood = "excited"
    elif pet.boredom > 70:
        mood = "bored"
    body = ACCENT
    if mood == "surprised":
        body = GOLD
    elif mood == "excited":
        body = INFO
    elif mood == "bored" or mood == "sleeping":
        body = DIM
    elif mood == "sad":
        body = ALERT
    _blob(draw, cx - 28, cy - 24, 56, 48, body)
    draw.rect(Vector(cx - 28, cy - 24), Vector(56, 48), FG)
    _blob(draw, cx - 22, cy - 32, 12, 12, body)
    _blob(draw, cx + 10, cy - 32, 12, 12, body)
    draw.rect(Vector(cx - 22, cy - 32), Vector(12, 12), FG)
    draw.rect(Vector(cx + 10, cy - 32), Vector(12, 12), FG)
    closed = blink or mood == "sleeping"
    ey = cy - 8
    if closed:
        _blob(draw, cx - 16, ey, 10, 2, TFT_BLACK)
        _blob(draw, cx + 6, ey, 10, 2, TFT_BLACK)
    else:
        _blob(draw, cx - 16, ey - 4, 10, 10, TFT_BLACK)
        _blob(draw, cx + 6, ey - 4, 10, 10, TFT_BLACK)
        _blob(draw, cx - 14, ey - 3, 3, 3, TFT_WHITE)
        _blob(draw, cx + 8, ey - 3, 3, 3, TFT_WHITE)
    my = cy + 12
    if mood == "happy" or mood == "excited" or mood == "love":
        _blob(draw, cx - 10, my, 20, 2, TFT_BLACK)
        _blob(draw, cx - 4, my + 2, 8, 4, TFT_BLACK)
    elif mood == "sad" or mood == "bored":
        _blob(draw, cx - 10, my + 4, 20, 2, TFT_BLACK)
    elif mood == "sleeping":
        _blob(draw, cx - 8, my, 16, 2, TFT_BLACK)
        draw.text(Vector(cx + 30, cy - 28), "z", DIM, FONT_SMALL)
    elif mood == "surprised":
        _blob(draw, cx - 4, my, 8, 8, TFT_BLACK)
    else:
        _blob(draw, cx - 8, my + 2, 16, 2, TFT_BLACK)


def _hdr(draw, title, right):
    draw.fill_rectangle(Vector(0, 0), Vector(320, 22), ACCENT)
    draw.text(Vector(6, 4), title, TFT_BLACK, FONT_XTRA_SMALL)
    if right:
        tw = _text_w(draw, right, FONT_XTRA_SMALL)
        x = 320 - tw - 8
        if x < 160:
            x = 160
        draw.text(Vector(x, 4), right, TFT_BLACK, FONT_XTRA_SMALL)


def _ftr(draw, line):
    draw.fill_rectangle(Vector(0, 302), Vector(320, 18), ACCENT)
    draw.text(Vector(6, 306), line, TFT_BLACK, FONT_XTRA_SMALL)


def _paint_face(vm):
    draw = vm.draw
    pet = _state["pet"]
    draw.fill_screen(BG)
    auto = "auto %ds" % _state["interval"] if _state["auto"] else "manual"
    _hdr(draw, "OBSERVERGOTCHI", auto)
    blink = bool(_state.get("blink_shut"))
    _draw_creature(draw, 160, 82, pet, blink)
    face = pet.get_face()
    fw = _text_w(draw, face, FONT_SMALL)
    draw.text(Vector(max(8, (320 - fw) // 2), 122), face, FG, FONT_SMALL)
    age_days = float(pet.age_hours) / 24.0
    draw.text(Vector(10, 144), pet.name, GOLD, FONT_SMALL)
    draw.text(Vector(10, 162), "age %.1fd  %s" % (age_days, pet.mood), FG, FONT_XTRA_SMALL)
    y = 182
    for label, val, col in (
        ("BRD", pet.boredom, WARN),
        ("XCT", pet.excitement, INFO),
        ("NRG", pet.energy, ACCENT),
    ):
        draw.text(Vector(10, y), label, DIM, FONT_XTRA_SMALL)
        _bar(draw, 40, y + 1, 270, 10, val, col)
        y += 16
    draw.text(
        Vector(10, y + 2),
        "scans %d   ssid %d   bssid %d"
        % (pet.scans_done, len(pet.unique_ssids), len(pet.unique_bssids)),
        FG,
        FONT_XTRA_SMALL,
    )
    draw.text(
        Vector(10, y + 16),
        "open %d   wpa3 %d   wow %d   last %d"
        % (pet.open_networks, pet.wpa3_networks, pet.interesting_found, pet.last_scan_count),
        FG,
        FONT_XTRA_SMALL,
    )
    if _state["toast"]:
        thought = _state["toast"]
    else:
        thought = _state.get("thought") or ""
    if len(thought) > 38:
        thought = thought[:37] + ".."
    draw.rect(Vector(8, 248), Vector(304, 48), DIM)
    draw.text(Vector(14, 254), '"' + thought + '"', INFO, FONT_XTRA_SMALL)
    status = _state["status"] or ""
    if len(status) > 38:
        status = status[:37] + ".."
    draw.text(Vector(14, 272), status, DIM, FONT_XTRA_SMALL)
    if not _state["has_wifi"]:
        draw.text(Vector(14, 286), "no wifi radio", WARN, FONT_XTRA_SMALL)
    _ftr(draw, "S scan  A auto  L list  R name  H help")
    draw.swap()


def _paint_list(vm):
    draw = vm.draw
    pet = _state["pet"]
    draw.fill_screen(BG)
    _hdr(draw, "AIRWAVES", "%d seen" % pet.last_scan_count)
    rows = pet.recent or []
    if not rows:
        draw.text(Vector(12, 40), "No scan yet.", FG, FONT_SMALL)
        draw.text(Vector(12, 60), "Press S to observe.", DIM, FONT_SMALL)
    else:
        page = _state["page"]
        per = 12
        start = page * per
        chunk = rows[start : start + per]
        y = 24
        draw.text(Vector(8, y), "SSID                 SIG  SEC", DIM, FONT_XTRA_SMALL)
        y = 38
        for net in chunk:
            ssid = net.get("ssid", "")
            if len(ssid) > 18:
                ssid = ssid[:17] + "+"
            sig = int(net.get("signal", 0))
            sec = str(net.get("security", ""))
            if len(sec) > 9:
                sec = sec[:9]
            col = ACCENT if sig >= 60 else (GOLD if sig >= 35 else DIM)
            if "OPEN" in sec.upper():
                col = WARN
            line = "%-18s %3d  %s" % (ssid, sig, sec)
            draw.text(Vector(8, y), line, col, FONT_XTRA_SMALL)
            y += 20
        if start + per < len(rows):
            draw.text(Vector(8, 288), "DOWN more", DIM, FONT_XTRA_SMALL)
    _ftr(draw, "UP/DN page  S rescan  BACK face")
    draw.swap()


def _paint_help(vm):
    draw = vm.draw
    draw.fill_screen(BG)
    _hdr(draw, "HELP", "passive")
    lines = (
        "Observergotchi watches WiFi.",
        "It never associates, never attacks.",
        "",
        "S / SPACE   scan now",
        "A           auto scan on/off",
        "LEFT/RIGHT  auto interval",
        "L           last airwave list",
        "R           rename the pet",
        "UP          pet it (mood boost)",
        "H           this screen",
        "BACK        save and exit",
        "",
        "Save: /sd/observergotchi.json",
        "Needs Pico W / Pico 2W to scan.",
    )
    y = 24
    for line in lines:
        draw.text(Vector(10, y), line, FG if line else DIM, FONT_XTRA_SMALL)
        y += 18
    _ftr(draw, "BACK return")
    draw.swap()


def _paint_safe_face(vm, err=None):
    draw = vm.draw
    pet = _state["pet"]
    draw.fill_screen(BG)
    name = pet.name if pet else "Observer"
    mood = pet.mood if pet else "curious"
    face = pet.get_face() if pet else "(._.)"
    draw.text(Vector(8, 8), "OBSERVERGOTCHI", ACCENT, FONT_SMALL)
    draw.text(Vector(8, 40), face, FG, FONT_SMALL)
    draw.text(Vector(8, 64), name, GOLD, FONT_SMALL)
    draw.text(Vector(8, 84), mood, FG, FONT_SMALL)
    draw.text(Vector(8, 108), _state.get("status") or "ready", DIM, FONT_SMALL)
    if err:
        msg = str(err)
        if len(msg) > 40:
            msg = msg[:40]
        draw.text(Vector(8, 140), msg, WARN, FONT_XTRA_SMALL)
    draw.text(Vector(8, 300), "S scan  A auto  BACK quit", FG, FONT_XTRA_SMALL)
    draw.swap()


def _paint(vm):
    mode = _state["mode"]
    if mode == "rename":
        return
    try:
        if mode == "list":
            _paint_list(vm)
        elif mode == "help":
            _paint_help(vm)
        else:
            _paint_face(vm)
        _state["paint_ok"] = True
        _state["dirty"] = False
    except Exception as e:
        _state["paint_ok"] = False
        try:
            _paint_safe_face(vm, e)
        except Exception:
            pass
        _state["dirty"] = False


def _reset_input(vm):
    try:
        vm.input_manager.reset()
    except Exception:
        pass


def _begin_rename(vm):
    pet = _state["pet"]
    draw = vm.draw
    if Keyboard is None:
        _toast("keyboard unavailable")
        return
    try:
        kb = Keyboard(draw, vm.input_manager, FG, BG, ACCENT)
        kb.title = "Name your Observergotchi"
        kb.response = pet.name
        kb.show_keyboard = True

        def _saved(_=None):
            name = kb.response
            if name:
                pet.name = str(name).strip()[:16] or pet.name
                _save_pet(vm, pet)
            _state["kb"] = None
            _state["mode"] = "face"
            _state["dirty"] = True
            _toast("hello, %s" % pet.name)

        try:
            kb.set_save_callback(_saved)
        except Exception:
            kb.callback = _saved
        _state["kb"] = kb
        _state["mode"] = "rename"
    except Exception:
        _state["mode"] = "face"
        _toast("keyboard unavailable")


def _pet_it(pet):
    pet.boredom = _clamp(pet.boredom - 12, 0, 100)
    pet.energy = _clamp(pet.energy + 6, 10, 100)
    pet.excitement = _clamp(pet.excitement + 4, 0, 100)
    if pet.energy >= 20:
        pet.mood = "happy"
    _set_thought(pet, True)
    _toast("%s purrs at the spectrum." % pet.name)


def start(view_manager):
    vm = view_manager
    _reset_input(vm)
    has_wifi = True
    try:
        has_wifi = bool(BOARD_HAS_WIFI)
    except Exception:
        has_wifi = True
    try:
        if hasattr(vm, "has_wifi"):
            has_wifi = bool(vm.has_wifi) and has_wifi
    except Exception:
        pass
    pet = None
    try:
        pet = _load_pet(vm)
    except Exception:
        pet = None
    if pet is None:
        pet = Observergotchi()
        _toast("A new Observergotchi woke up.")
    else:
        try:
            pet.update_time()
        except Exception:
            pass
        _toast("%s is back online." % pet.name)
    try:
        pet.remember_sets()
    except Exception:
        pet._ssid_set = {}
        pet._bssid_set = {}
    _state["pet"] = pet
    _state["mode"] = "face"
    _state["dirty"] = True
    _state["auto"] = False
    _state["interval"] = 30
    _state["last_scan_ms"] = 0
    _state["scanning"] = False
    _state["status"] = "press S to observe"
    _state["kb"] = None
    _state["blink"] = 0
    _state["page"] = 0
    _state["has_wifi"] = has_wifi
    _state["boot_ignore"] = 18
    _state["thought"] = ""
    _state["thought_ms"] = 0
    _state["blink_shut"] = False
    _set_thought(pet, True)
    try:
        _save_pet(vm, pet)
    except Exception:
        pass
    try:
        _paint(vm)
    except Exception:
        pass
    _reset_input(vm)
    return True


def stop(view_manager):
    pet = _state["pet"]
    if pet is not None:
        try:
            pet.update_time()
            _save_pet(view_manager, pet)
        except Exception:
            pass
    _state["pet"] = None
    _state["kb"] = None
    try:
        from gc import collect
        collect()
    except Exception:
        pass


def run(view_manager):
    vm = view_manager
    pet = _state["pet"]
    if pet is None:
        return
    try:
        btn = vm.input_manager.button
    except Exception:
        btn = BUTTON_NONE
    now = _ticks()

    ignore = int(_state.get("boot_ignore") or 0)
    if ignore > 0:
        _state["boot_ignore"] = ignore - 1
        if btn != BUTTON_NONE:
            _reset_input(vm)
        _state["blink"] += 1
        shut = (_state["blink"] % 80) > 74
        if shut != _state.get("blink_shut"):
            _state["blink_shut"] = shut
            _state["dirty"] = True
        if _state["dirty"]:
            _paint(vm)
        return

    if _state["mode"] == "rename":
        kb = _state["kb"]
        if kb is None:
            _state["mode"] = "face"
            _state["dirty"] = True
            return
        try:
            cont = kb.run()
        except Exception:
            cont = False
        if cont is False or kb.is_finished:
            name = ""
            try:
                name = kb.response
            except Exception:
                name = ""
            if name:
                pet.name = str(name).strip()[:16] or pet.name
                _save_pet(vm, pet)
            _state["kb"] = None
            _state["mode"] = "face"
            _state["dirty"] = True
            _toast("hello, %s" % pet.name)
            _paint(vm)
        return

    if _state["toast"] and _ticks_diff(now, _state["toast_ms"]) > 2500:
        _state["toast"] = ""
        _state["dirty"] = True

    _state["blink"] += 1
    if _state["mode"] == "face":
        shut = (_state["blink"] % 80) > 74
        if shut != _state.get("blink_shut"):
            _state["blink_shut"] = shut
            _state["dirty"] = True

    if _state["auto"] and not _state["scanning"] and _state["mode"] == "face":
        gap = _state["interval"] * 1000
        if _state["last_scan_ms"] == 0 or _ticks_diff(now, _state["last_scan_ms"]) >= gap:
            _do_scan(vm)
            return

    if (_state["blink"] % 200) == 0:
        pet.update_time()

    if btn == BUTTON_NONE:
        if _state["dirty"]:
            _paint(vm)
        return

    if btn in (BUTTON_BACK, BUTTON_ESCAPE):
        if _state["mode"] != "face":
            _state["mode"] = "face"
            _state["dirty"] = True
            _paint(vm)
            return
        pet.update_time()
        _save_pet(vm, pet)
        try:
            vm.back()
        except Exception:
            pass
        return

    if _state["mode"] == "help":
        _state["mode"] = "face"
        _state["dirty"] = True
        _paint(vm)
        return

    if _state["mode"] == "list":
        if btn == BUTTON_DOWN:
            if pet.recent and (_state["page"] + 1) * 12 < len(pet.recent):
                _state["page"] += 1
            _state["dirty"] = True
        elif btn == BUTTON_UP:
            _state["page"] = max(0, _state["page"] - 1)
            _state["dirty"] = True
        elif btn in (BUTTON_S, BUTTON_SPACE):
            _do_scan(vm)
        _paint(vm)
        return

    if btn in (BUTTON_S, BUTTON_SPACE):
        _do_scan(vm)
        _paint(vm)
        return
    if btn == BUTTON_A:
        _state["auto"] = not _state["auto"]
        if _state["auto"]:
            _toast("auto every %ds" % _state["interval"])
            _state["status"] = "auto %ds" % _state["interval"]
        else:
            _toast("manual")
            _state["status"] = "manual"
        _state["dirty"] = True
    elif btn == BUTTON_LEFT:
        i = INTERVALS.index(_state["interval"]) if _state["interval"] in INTERVALS else 1
        _state["interval"] = INTERVALS[(i - 1) % len(INTERVALS)]
        _toast("interval %ds" % _state["interval"])
    elif btn == BUTTON_RIGHT:
        i = INTERVALS.index(_state["interval"]) if _state["interval"] in INTERVALS else 1
        _state["interval"] = INTERVALS[(i + 1) % len(INTERVALS)]
        _toast("interval %ds" % _state["interval"])
    elif btn in (BUTTON_L, BUTTON_DOWN):
        _state["mode"] = "list"
        _state["page"] = 0
        _state["dirty"] = True
    elif btn == BUTTON_R:
        _begin_rename(vm)
        return
    elif btn == BUTTON_H or btn == BUTTON_START:
        _state["mode"] = "help"
        _state["dirty"] = True
    elif btn == BUTTON_UP:
        _pet_it(pet)
        _save_pet(vm, pet)

    if _state["dirty"]:
        _paint(vm)
