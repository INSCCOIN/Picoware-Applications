from picoware.system.vector import Vector
from picoware.system.colors import (
    TFT_ORANGE, TFT_YELLOW, TFT_WHITE, TFT_GREEN, TFT_RED, TFT_CYAN
)
from picoware.system.buttons import (
    BUTTON_UP, BUTTON_DOWN, BUTTON_CENTER, BUTTON_OK, BUTTON_BACK, BUTTON_BACKSPACE,
    BUTTON_A, BUTTON_S, BUTTON_D, BUTTON_T,
    BUTTON_0, BUTTON_1, BUTTON_2, BUTTON_3, BUTTON_4,
    BUTTON_5, BUTTON_6, BUTTON_7, BUTTON_8, BUTTON_9,
    BUTTON_PERIOD
)

DATA_PATH = "/picoware/data/fuellog.json"

DIGITS = {
    BUTTON_0: "0", BUTTON_1: "1", BUTTON_2: "2", BUTTON_3: "3", BUTTON_4: "4",
    BUTTON_5: "5", BUTTON_6: "6", BUTTON_7: "7", BUTTON_8: "8", BUTTON_9: "9",
    BUTTON_PERIOD: ".",
}

_storage = None
_mode = "main"
_idx = 0
_msg = "Type numbers on keyboard"
_entries = []
_field = 0
_buf = ""
_draft = {"odo": "0", "gal": "0", "cost": "0"}
_trip = {"miles": "100", "mpg": "25", "ppg": "3.50"}

MAIN = ["History", "Add fill", "Summary", "Trip calc", "Save", "Load", "Exit"]
ADD_FIELDS = ["odo", "gal", "cost"]
ADD_LABELS = ["Odometer", "Gallons", "Total $"]
TRIP_FIELDS = ["miles", "mpg", "ppg"]
TRIP_LABELS = ["Trip miles", "MPG", "Price/gal"]


def _load():
    global _entries
    _entries = []
    try:
        import ujson as js
    except Exception:
        try:
            import json as js
        except Exception:
            return
    try:
        if _storage and _storage.exists(DATA_PATH):
            raw = _storage.read(DATA_PATH)
            if isinstance(raw, bytes):
                raw = raw.decode()
            data = js.loads(raw)
            if isinstance(data, list):
                _entries = data
    except Exception:
        _entries = []


def _save():
    global _msg
    try:
        import ujson as js
    except Exception:
        try:
            import json as js
        except Exception:
            _msg = "No JSON"
            return
    try:
        if not _storage.exists("/picoware/data"):
            _storage.mkdir("/picoware/data")
        _storage.write(DATA_PATH, js.dumps(_entries))
        _msg = "Saved %d entries" % len(_entries)
    except Exception:
        _msg = "Save failed"


def _f(s):
    try:
        return float(s)
    except Exception:
        return 0.0


def _i(s):
    try:
        return int(float(s))
    except Exception:
        return 0


def _mpg_for(i):
    if i <= 0 or i >= len(_entries):
        return 0.0
    cur = _entries[i]
    prev = _entries[i - 1]
    miles = int(cur.get("odo", 0)) - int(prev.get("odo", 0))
    gal = float(cur.get("gal", 0))
    if miles <= 0 or gal <= 0:
        return 0.0
    return miles / gal


def _avg_mpg():
    total_m = 0
    total_g = 0.0
    for i in range(1, len(_entries)):
        cur = _entries[i]
        prev = _entries[i - 1]
        miles = int(cur.get("odo", 0)) - int(prev.get("odo", 0))
        gal = float(cur.get("gal", 0))
        if miles > 0 and gal > 0:
            total_m += miles
            total_g += gal
    if total_g <= 0:
        return 0.0
    return total_m / total_g


def _totals():
    spend = 0.0
    gal = 0.0
    for e in _entries:
        spend += float(e.get("cost", 0))
        gal += float(e.get("gal", 0))
    miles = 0
    if len(_entries) >= 2:
        miles = int(_entries[-1].get("odo", 0)) - int(_entries[0].get("odo", 0))
        if miles < 0:
            miles = 0
    return spend, gal, miles


def _sync_buf_from_field():
    global _buf
    if _mode == "add":
        _buf = str(_draft[ADD_FIELDS[_field]])
    elif _mode == "trip":
        _buf = str(_trip[TRIP_FIELDS[_field]])
    else:
        _buf = ""


def _apply_buf():
    global _buf
    if _mode == "add":
        key = ADD_FIELDS[_field]
        if _buf == "" or _buf == ".":
            _buf = "0"
        _draft[key] = _buf
    elif _mode == "trip":
        key = TRIP_FIELDS[_field]
        if _buf == "" or _buf == ".":
            _buf = "0"
        _trip[key] = _buf


def start(view_manager) -> bool:
    global _storage, _mode, _idx, _msg, _field, _buf
    _storage = view_manager.storage
    _mode = "main"
    _idx = 0
    _field = 0
    _buf = ""
    _msg = "Type digits for amounts"
    _load()
    if _entries:
        _draft["odo"] = str(int(_entries[-1].get("odo", 0)))
    _draw(view_manager)
    return True


def _draw(vm):
    d = vm.draw
    d.erase()
    d.text(Vector(4, 2), "FUEL LOG", TFT_ORANGE, 1)
    d.text(Vector(4, 14), str(_msg)[:38], TFT_YELLOW, 1)

    if _mode == "main":
        y = 32
        for i, name in enumerate(MAIN):
            mark = ">" if i == _idx else " "
            col = TFT_CYAN if i == _idx else TFT_WHITE
            d.text(Vector(8, y), mark + " " + name, col, 1)
            y += 14

    elif _mode == "history":
        if not _entries:
            d.text(Vector(8, 40), "(no fill-ups)", TFT_WHITE, 1)
        else:
            start = max(0, len(_entries) - 1 - _idx - 3)
            end = min(len(_entries), start + 8)
            y = 30
            for i in range(end - 1, start - 1, -1):
                e = _entries[i]
                mpg = _mpg_for(i)
                mark = ">" if i == len(_entries) - 1 - _idx else " "
                col = TFT_CYAN if mark == ">" else TFT_WHITE
                line = "%s%d %.1fg $%.2f" % (
                    mark,
                    int(e.get("odo", 0)),
                    float(e.get("gal", 0)),
                    float(e.get("cost", 0)),
                )
                if mpg > 0:
                    line += " %.1f" % mpg
                d.text(Vector(4, y), line[:38], col, 1)
                y += 14
        d.text(Vector(4, 200), "U/D  D=del  Back", TFT_GREEN, 1)

    elif _mode == "add":
        y = 34
        for i in range(3):
            key = ADD_FIELDS[i]
            mark = ">" if i == _field else " "
            col = TFT_CYAN if i == _field else TFT_WHITE
            val = _buf if i == _field else str(_draft[key])
            d.text(Vector(6, y), "%s%s: %s" % (mark, ADD_LABELS[i], val), col, 1)
            y += 16
        d.text(Vector(4, 120), "Type number  BS=erase", TFT_GREEN, 1)
        d.text(Vector(4, 136), "U/D field  OK=save fill", TFT_GREEN, 1)
        d.text(Vector(4, 152), "Back=cancel", TFT_WHITE, 1)

    elif _mode == "summary":
        avg = _avg_mpg()
        spend, gal, miles = _totals()
        cpm = (spend / miles) if miles > 0 else 0
        d.text(Vector(8, 36), "Entries: %d" % len(_entries), TFT_WHITE, 1)
        d.text(Vector(8, 52), "Avg MPG: %.1f" % avg, TFT_GREEN, 1)
        d.text(Vector(8, 68), "Miles:   %d" % miles, TFT_WHITE, 1)
        d.text(Vector(8, 84), "Gallons: %.1f" % gal, TFT_WHITE, 1)
        d.text(Vector(8, 100), "Spent:   $%.2f" % spend, TFT_YELLOW, 1)
        d.text(Vector(8, 116), "$/mile:  %.2f" % cpm, TFT_CYAN, 1)
        d.text(Vector(4, 200), "Back=menu", TFT_WHITE, 1)

    elif _mode == "trip":
        y = 32
        for i in range(3):
            key = TRIP_FIELDS[i]
            mark = ">" if i == _field else " "
            col = TFT_CYAN if i == _field else TFT_WHITE
            val = _buf if i == _field else str(_trip[key])
            d.text(Vector(6, y), "%s%s: %s" % (mark, TRIP_LABELS[i], val), col, 1)
            y += 14
        miles = _f(_trip["miles"])
        mpg = _f(_trip["mpg"])
        ppg = _f(_trip["ppg"])
        gal_need = (miles / mpg) if mpg > 0 else 0
        cost = gal_need * ppg
        d.text(Vector(8, 90), "Fuel need: %.1f gal" % gal_need, TFT_GREEN, 1)
        d.text(Vector(8, 106), "Est cost:  $%.2f" % cost, TFT_YELLOW, 1)
        avg = _avg_mpg()
        if avg > 0:
            d.text(Vector(8, 128), "Log avg MPG %.1f" % avg, TFT_CYAN, 1)
        d.text(Vector(4, 170), "Type number  T=use avg MPG", TFT_GREEN, 1)
        d.text(Vector(4, 186), "U/D field  Back=menu", TFT_GREEN, 1)

    d.swap()


def _type_digit(ch):
    global _buf, _msg
    if ch == "." and "." in _buf:
        return
    if len(_buf) >= 10:
        return
    if _buf == "0" and ch != ".":
        _buf = ch
    else:
        _buf += ch
    _apply_buf()


def run(vm) -> None:
    global _mode, _idx, _msg, _field, _buf
    button = vm.button

    if _mode in ("add", "trip") and button in DIGITS:
        _type_digit(DIGITS[button])
        _draw(vm)
        return

    if _mode in ("add", "trip") and button == BUTTON_BACKSPACE:
        if len(_buf) > 0:
            _buf = _buf[:-1]
            _apply_buf()
        _draw(vm)
        return

    if _mode == "main":
        if button == BUTTON_UP:
            _idx = (_idx - 1) % len(MAIN)
        elif button == BUTTON_DOWN:
            _idx = (_idx + 1) % len(MAIN)
        elif button == BUTTON_CENTER or button == BUTTON_OK:
            item = MAIN[_idx]
            if item == "History":
                _mode = "history"
                _idx = 0
            elif item == "Add fill":
                _mode = "add"
                _field = 0
                if _entries:
                    _draft["odo"] = str(int(_entries[-1].get("odo", 0)))
                _sync_buf_from_field()
            elif item == "Summary":
                _mode = "summary"
            elif item == "Trip calc":
                _mode = "trip"
                _field = 0
                avg = _avg_mpg()
                if avg > 0:
                    _trip["mpg"] = "%.1f" % avg
                _sync_buf_from_field()
            elif item == "Save":
                _save()
            elif item == "Load":
                _load()
                _msg = "Loaded %d" % len(_entries)
            elif item == "Exit":
                vm.back()
                return
        elif button == BUTTON_BACK:
            vm.back()
            return

    elif _mode == "history":
        n = len(_entries)
        if button == BUTTON_UP and n:
            _idx = (_idx + 1) % n
        elif button == BUTTON_DOWN and n:
            _idx = (_idx - 1) % n
        elif button == BUTTON_D and n:
            real = n - 1 - _idx
            if 0 <= real < n:
                _entries.pop(real)
                if _idx >= len(_entries):
                    _idx = max(0, len(_entries) - 1)
                _msg = "Deleted"
                _save()
        elif button == BUTTON_BACK:
            _mode = "main"
            _idx = 0

    elif _mode == "add":
        if button == BUTTON_UP:
            _apply_buf()
            _field = (_field - 1) % 3
            _sync_buf_from_field()
        elif button == BUTTON_DOWN:
            _apply_buf()
            _field = (_field + 1) % 3
            _sync_buf_from_field()
        elif button == BUTTON_CENTER or button == BUTTON_OK:
            _apply_buf()
            odo = _i(_draft["odo"])
            gal = _f(_draft["gal"])
            cost = _f(_draft["cost"])
            if gal <= 0:
                _msg = "Enter gallons"
            else:
                _entries.append({"odo": odo, "gal": round(gal, 3), "cost": round(cost, 2)})
                _msg = "Fill saved"
                _save()
                _mode = "main"
                _idx = 0
        elif button == BUTTON_BACK:
            _mode = "main"
            _idx = 0

    elif _mode == "summary":
        if button == BUTTON_BACK:
            _mode = "main"
            _idx = 0

    elif _mode == "trip":
        if button == BUTTON_UP:
            _apply_buf()
            _field = (_field - 1) % 3
            _sync_buf_from_field()
        elif button == BUTTON_DOWN:
            _apply_buf()
            _field = (_field + 1) % 3
            _sync_buf_from_field()
        elif button == BUTTON_T:
            avg = _avg_mpg()
            if avg > 0:
                _trip["mpg"] = "%.1f" % avg
                if _field == 1:
                    _buf = _trip["mpg"]
                _msg = "Using log avg MPG"
        elif button == BUTTON_BACK:
            _apply_buf()
            _mode = "main"
            _idx = 0

    _draw(vm)


def stop(vm) -> None:
    global _storage, _entries
    try:
        _save()
    except Exception:
        pass
    _storage = None
    _entries = []