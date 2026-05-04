import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote, urlparse, parse_qs

PORT = int(os.environ.get("PORT", 8765))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OVERLAY_FILE = os.path.join(BASE_DIR, "overlay.html")
LOGO_FILE = os.path.join(BASE_DIR, "breakstart-logo.png")
STATE_FILE = os.path.join(BASE_DIR, "state.json")
LISTS_DIR = os.path.join(BASE_DIR, "lists")

DEFAULT_LIST_ID = "nrl"

DEFAULT_NAMES = [
    "Broncos",
    "Bulldogs",
    "Cowboys",
    "Dolphins",
    "Dragons",
    "Eels",
    "Knights",
    "Panthers",
    "Rabbitohs",
    "Raiders",
    "Roosters",
    "Sea Eagles",
    "Sharks",
    "Storm",
    "Titans",
    "Warriors",
    "Wests Tigers"
]


def ensure_files():
    os.makedirs(LISTS_DIR, exist_ok=True)

    nrl_file = os.path.join(LISTS_DIR, "nrl.txt")

    if not os.path.exists(nrl_file):
        with open(nrl_file, "w", encoding="utf-8") as f:
            f.write("\n".join(DEFAULT_NAMES))

    if not os.path.exists(STATE_FILE):
        save_state(default_state())


def safe_list_id(list_id):
    list_id = list_id.strip().lower()
    list_id = list_id.replace(".txt", "")
    list_id = re.sub(r"[^a-z0-9_-]", "", list_id)

    if not list_id:
        list_id = DEFAULT_LIST_ID

    return list_id


def list_path(list_id):
    list_id = safe_list_id(list_id)
    return os.path.join(LISTS_DIR, list_id + ".txt")


def read_list_names(list_id):
    path = list_path(list_id)

    if not os.path.exists(path):
        return []

    names = []
    seen = set()

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()

            if not name:
                continue

            key = name.lower()

            if key not in seen:
                names.append(name)
                seen.add(key)

    return names


def blank_list_state(list_id):
    names = read_list_names(list_id)

    return {
        "active": sorted(names, key=lambda x: x.lower()),
        "removed": [],
        "last_removed": None,
        "history": [],
        "processed_spins": []
    }


def default_state():
    return {
        "current_list": DEFAULT_LIST_ID,
        "lists": {
            DEFAULT_LIST_ID: blank_list_state(DEFAULT_LIST_ID)
        }
    }


def load_state():
    if not os.path.exists(STATE_FILE):
        state = default_state()
        save_state(state)
        return state

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = default_state()
        save_state(state)
        return state

    if "current_list" not in state:
        state["current_list"] = DEFAULT_LIST_ID

    if "lists" not in state:
        state["lists"] = {}

    current = safe_list_id(state["current_list"])
    state["current_list"] = current

    if current not in state["lists"]:
        state["lists"][current] = blank_list_state(current)

    return state


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def current_wheel(state):
    current = safe_list_id(state["current_list"])

    if current not in state["lists"]:
        state["lists"][current] = blank_list_state(current)

    return state["lists"][current]


def sort_active(wheel):
    wheel["active"] = sorted(wheel["active"], key=lambda x: x.lower())


def record_winner(name, spin_id):
    state = load_state()
    wheel = current_wheel(state)

    name = name.strip()
    spin_id = spin_id.strip()

    if not name or not spin_id:
        return state

    if spin_id in wheel["processed_spins"]:
        return state

    wheel["processed_spins"].append(spin_id)

    if len(wheel["processed_spins"]) > 500:
        wheel["processed_spins"] = wheel["processed_spins"][-500:]

    wheel["history"].append(name)

    if name in wheel["active"]:
        wheel["active"].remove(name)

    if name not in wheel["removed"]:
        wheel["removed"].append(name)

    wheel["last_removed"] = name
    sort_active(wheel)

    save_state(state)
    return state


def manual_remove(name):
    state = load_state()
    wheel = current_wheel(state)

    name = name.strip()

    if name in wheel["active"]:
        wheel["active"].remove(name)

    if name and name not in wheel["removed"]:
        wheel["removed"].append(name)

    wheel["last_removed"] = name
    sort_active(wheel)

    save_state(state)
    return state


def restore_team(name):
    state = load_state()
    wheel = current_wheel(state)

    name = name.strip()

    if name in wheel["removed"]:
        wheel["removed"].remove(name)

    if name and name not in wheel["active"]:
        wheel["active"].append(name)

    sort_active(wheel)

    save_state(state)
    return state


def restore_last():
    state = load_state()
    wheel = current_wheel(state)

    name = wheel.get("last_removed")

    if name:
        if name in wheel["removed"]:
            wheel["removed"].remove(name)

        if name not in wheel["active"]:
            wheel["active"].append(name)

        wheel["last_removed"] = None
        sort_active(wheel)

    save_state(state)
    return state


def restore_all():
    state = load_state()
    list_id = state["current_list"]

    wheel = current_wheel(state)
    names = read_list_names(list_id)

    wheel["active"] = sorted(names, key=lambda x: x.lower())
    wheel["removed"] = []
    wheel["last_removed"] = None

    save_state(state)
    return state


def clear_history():
    state = load_state()
    wheel = current_wheel(state)

    wheel["history"] = []
    wheel["processed_spins"] = []

    save_state(state)
    return state


def reset_current_list():
    state = load_state()
    current = safe_list_id(state["current_list"])

    state["lists"][current] = blank_list_state(current)

    save_state(state)
    return state


def switch_list(list_id):
    state = load_state()
    list_id = safe_list_id(list_id)

    if not os.path.exists(list_path(list_id)):
        with open(list_path(list_id), "w", encoding="utf-8") as f:
            f.write("")

    state["current_list"] = list_id

    if list_id not in state["lists"]:
        state["lists"][list_id] = blank_list_state(list_id)

    save_state(state)
    return state


def reload_list_from_file(list_id):
    state = load_state()
    list_id = safe_list_id(list_id)

    if not os.path.exists(list_path(list_id)):
        with open(list_path(list_id), "w", encoding="utf-8") as f:
            f.write("")

    state["current_list"] = list_id
    state["lists"][list_id] = blank_list_state(list_id)

    save_state(state)
    return state


def available_lists():
    os.makedirs(LISTS_DIR, exist_ok=True)

    files = []

    for name in os.listdir(LISTS_DIR):
        if name.lower().endswith(".txt"):
            files.append(name[:-4])

    return sorted(files)


def render_history_page():
    state = load_state()
    wheel = current_wheel(state)
    current = state["current_list"]

    if not wheel["history"]:
        rows = '<tr><td colspan="2">No names spun yet</td></tr>'
    else:
        rows = ""

        for i, name in enumerate(wheel["history"], start=1):
            rows += f"<tr><td>{i}</td><td>{name}</td></tr>"

    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Breakstart Spin History</title>
<style>
body {{
    margin: 0;
    background: #081018;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
    padding: 30px;
}}
h1 {{
    color: #1d8cff;
    margin: 0 0 8px 0;
}}
.sub {{
    color: #ff2d55;
    font-weight: bold;
    margin-bottom: 24px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    background: rgba(0,0,0,0.35);
    border: 1px solid rgba(29,140,255,0.4);
}}
th {{
    background: #1d8cff;
    padding: 14px;
    text-align: left;
    font-size: 20px;
}}
td {{
    padding: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.12);
    font-size: 22px;
    font-weight: bold;
}}
td:first-child {{
    width: 80px;
    color: #ff2d55;
}}
tr:last-child td {{
    background: rgba(255,45,85,0.12);
}}
button, a {{
    display: inline-block;
    margin-top: 20px;
    margin-right: 10px;
    padding: 12px 18px;
    border: none;
    border-radius: 10px;
    background: #ff2d55;
    color: white;
    font-weight: bold;
    text-decoration: none;
    cursor: pointer;
}}
</style>
</head>
<body>
<h1>BREAKSTART SPIN HISTORY</h1>
<div class="sub">Current list: {current}</div>

<table>
<thead>
<tr><th>#</th><th>Name</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>

<button onclick="fetch('/clear-history').then(()=>location.reload())">Clear History</button>
<a href="/control">Control Panel</a>
<a href="/lists">Lists</a>

<script>
setInterval(function() {{
    location.reload();
}}, 3000);
</script>
</body>
</html>
"""


def render_lists_page():
    state = load_state()
    current = state["current_list"]
    lists = available_lists()

    items = ""

    for list_id in lists:
        active = "CURRENT" if list_id == current else ""

        items += f"""
        <div class="row">
            <strong>{list_id}</strong>
            <span>{active}</span>
            <a href="/load-list/{list_id}">Load</a>
            <a href="/reload-list/{list_id}">Reload From File</a>
        </div>
        """

    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Breakstart Lists</title>
<style>
body {{
    margin: 0;
    background: #081018;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
    padding: 30px;
}}
h1 {{
    color: #1d8cff;
}}
.row {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.15);
}}
a {{
    padding: 8px 12px;
    background: #ff2d55;
    color: white;
    border-radius: 8px;
    text-decoration: none;
    font-weight: bold;
}}
span {{
    color: #1d8cff;
    font-weight: bold;
}}
</style>
</head>
<body>
<h1>BREAKSTART LISTS</h1>
<p>Put list files inside the <strong>lists</strong> folder. One name per line.</p>

{items}

<br>
<a href="/control">Control Panel</a>
<a href="/history">History</a>
<a href="/">Wheel</a>
</body>
</html>
"""


def render_control_page():
    state = load_state()
    wheel = current_wheel(state)
    current = state["current_list"]

    active_buttons = ""
    removed_buttons = ""

    for name in wheel["active"]:
        active_buttons += f"""
        <button class="remove" onclick="fetch('/remove/{name}').then(()=>location.reload())">{name}</button>
        """

    for name in wheel["removed"]:
        removed_buttons += f"""
        <button class="restore" onclick="fetch('/restore/{name}').then(()=>location.reload())">{name}</button>
        """

    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Breakstart Control</title>
<style>
body {{
    margin: 0;
    background: #081018;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
    padding: 30px;
}}
h1 {{
    color: #1d8cff;
}}
h2 {{
    color: #ff2d55;
}}
button, a {{
    display: inline-block;
    margin: 6px;
    padding: 10px 14px;
    border: none;
    border-radius: 8px;
    color: white;
    font-weight: bold;
    text-decoration: none;
    cursor: pointer;
}}
.remove {{
    background: #ff2d55;
}}
.restore {{
    background: #1d8cff;
}}
.utility {{
    background: #333;
}}
.section {{
    margin-bottom: 28px;
}}
</style>
</head>
<body>
<h1>BREAKSTART CONTROL PANEL</h1>
<p>Current list: <strong>{current}</strong></p>

<div class="section">
<h2>Active Names - click to remove</h2>
{active_buttons if active_buttons else "<p>No active names.</p>"}
</div>

<div class="section">
<h2>Removed Names - click to restore</h2>
{removed_buttons if removed_buttons else "<p>No removed names.</p>"}
</div>

<div class="section">
<button class="utility" onclick="fetch('/restore-all').then(()=>location.reload())">Restore All</button>
<button class="utility" onclick="fetch('/restore-last').then(()=>location.reload())">Restore Last</button>
<button class="utility" onclick="fetch('/clear-history').then(()=>location.reload())">Clear History</button>
<button class="utility" onclick="fetch('/reset-current').then(()=>location.reload())">Reset Current List</button>
</div>

<a class="utility" href="/history">History</a>
<a class="utility" href="/lists">Lists</a>
<a class="utility" href="/">Wheel</a>
</body>
</html>
"""


def render_keepalive_page():
    return """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Breakstart Keep Alive</title>
<style>
body {
    background: #081018;
    color: white;
    font-family: Arial, Helvetica, sans-serif;
    padding: 30px;
}
h1 { color: #1d8cff; }
#status { color: #ff2d55; font-weight: bold; }
</style>
</head>
<body>
<h1>Breakstart Keep Alive</h1>
<p>Leave this tab open during stream.</p>
<p>Status: <span id="status">Running</span></p>
<p>Last ping: <span id="last">Never</span></p>

<script>
function ping() {
    fetch('/state')
        .then(function() {
            document.getElementById('last').textContent = new Date().toLocaleTimeString();
            document.getElementById('status').textContent = 'Running';
        })
        .catch(function() {
            document.getElementById('status').textContent = 'Error';
        });
}

ping();
setInterval(ping, 5 * 60 * 1000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        return

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == "/":
                with open(OVERLAY_FILE, "rb") as f:
                    content = f.read()

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
                return

            if path == "/breakstart-logo.png":
                with open(LOGO_FILE, "rb") as f:
                    content = f.read()

                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                self.wfile.write(content)
                return

            if path == "/state":
                self.send_json(load_state())
                return

            if path == "/history":
                self.send_html(render_history_page())
                return

            if path == "/lists":
                self.send_html(render_lists_page())
                return

            if path == "/control":
                self.send_html(render_control_page())
                return

            if path == "/keepalive":
                self.send_html(render_keepalive_page())
                return

            if path.startswith("/load-list/"):
                list_id = unquote(path.replace("/load-list/", ""))
                self.send_json(switch_list(list_id))
                return

            if path.startswith("/reload-list/"):
                list_id = unquote(path.replace("/reload-list/", ""))
                self.send_json(reload_list_from_file(list_id))
                return

            if path == "/reset-current":
                self.send_json(reset_current_list())
                return

            if path.startswith("/record/"):
                name = unquote(path.replace("/record/", ""))
                spin_id = query.get("spin_id", [""])[0]
                self.send_json(record_winner(name, spin_id))
                return

            if path.startswith("/remove/"):
                name = unquote(path.replace("/remove/", ""))
                self.send_json(manual_remove(name))
                return

            if path.startswith("/restore/"):
                name = unquote(path.replace("/restore/", ""))
                self.send_json(restore_team(name))
                return

            if path == "/restore-last":
                self.send_json(restore_last())
                return

            if path == "/restore-all":
                self.send_json(restore_all())
                return

            if path == "/clear-history":
                self.send_json(clear_history())
                return

            self.send_json({"error": "Unknown endpoint"})

        except Exception as e:
            self.send_json({"error": str(e)})


ensure_files()

print(f"Breakstart server running on port {PORT}")
print("Local Wheel:   http://127.0.0.1:8765/")
print("Local Control: http://127.0.0.1:8765/control")
print("Local History: http://127.0.0.1:8765/history")
print("Local Lists:   http://127.0.0.1:8765/lists")

HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
