"""
live_game_enhanced.py - نسخة محسنة ومستقلة من LiveGameCanvas
تقدم حركة طبيعية، رصاص متنوع، تأثيرات إصابة وموت، وارتباط مباشر بالسيرفر.
"""

import math
import random
import threading
import time
from tkinter import Canvas
import tkinter as tk

# استيراد الفئات الأساسية من game_gui (إذا كانت موجودة)
try:
    from game_gui import LiveGameCanvas, Bullet, LiveGamePlayer
except ImportError:
    # تعريف مبسط للفئات في حالة عدم وجود game_gui (للاستخدام المستقل)
    class LiveGamePlayer:
        def __init__(self, player_id, x, y, color, name, game_id):
            self.player_id = player_id
            self.x = x
            self.y = y
            self.color = color
            self.name = name
            self.game_id = game_id
            self.health = 100
            self.max_health = 100
            self.direction = random.choice([-1, 1])
            self.speed = random.uniform(1.5, 3.0)
            self.dy = random.uniform(-0.5, 0.5)
            self.alive = True
            self.hit_flash = 0
            self.shoot_timer = random.uniform(1, 3)
            self.radius = 18
            self.emoji = random.choice(["🧑", "👦", "👩", "🧔", "👱"])

    class Bullet:
        def __init__(self, x, y, dx, dy, owner_id, color):
            self.x = x
            self.y = y
            self.dx = dx
            self.dy = dy
            self.owner_id = owner_id
            self.color = color
            self.alive = True
            self.radius = 4


class LiveGameCanvasEnhanced:
    """
    نسخة مطورة من LiveGameCanvas مع:
    - حركة لاعبين طبيعية (تغيير اتجاه عشوائي، سرعات مختلفة).
    - إطلاق رصاص أكثر دقة مع ألوان متنوعة.
    - تأثير إصابة (وميض) وتأثير موت (انفجار متدرج).
    - الموت يؤدي إلى إزالة اللاعب من السيرفر بعد 0.5 ثانية.
    - إدارة أفضل للرصاص (إزالة الرصاص خارج الحدود).
    """

    def __init__(self, parent, server):
        self.parent = parent
        self.server = server
        self.canvas_width = 900
        self.canvas_height = 480
        self.players = {}
        self.bullets = []
        self.running = False
        self.lock = threading.Lock()
        self.death_effects = []  # تأثيرات الموت (انفجارات)
        self.death_effect_lock = threading.Lock()
        self.kill_callbacks = []
        self.event_log = []
        self.player_colors = [
            "#ff6b6b", "#ffa94d", "#ffd43b", "#69db7c",
            "#74c0fc", "#e599f7", "#f783ac", "#a9e34b",
            "#63e6be", "#74b0ff"
        ]
        self.bullet_colors = ["#ff4444", "#ffaa00", "#44ff88", "#4488ff", "#ff44ff", "#ffffff"]
        self.color_index = 0
        self._build()

    def _build(self):
        # بناء الواجهة (مطابق لـ game_gui الأصلي)
        self.frame = tk.Frame(self.parent, bg="#0a0a1a")
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)

        header = tk.Frame(self.frame, bg="#111128", height=45)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🔴 LIVE", font=("Arial", 14, "bold"),
                 fg="#ff4444", bg="#111128").pack(side="left", padx=15, pady=10)
        tk.Label(header, text="Game Server Battle Arena",
                 font=("Arial", 14, "bold"), fg="#00ff88", bg="#111128").pack(side="left")

        self.live_players_label = tk.Label(header, text="👥 0 Players",
                                           font=("Arial", 12), fg="#8b949e", bg="#111128")
        self.live_players_label.pack(side="right", padx=15)

        self.live_games_label = tk.Label(header, text="🎮 0 Games",
                                         font=("Arial", 12), fg="#8b949e", bg="#111128")
        self.live_games_label.pack(side="right", padx=15)

        canvas_container = tk.Frame(self.frame, bg="#0a0a1a")
        canvas_container.pack(fill="both", expand=True, padx=5, pady=5)

        self.canvas = Canvas(
            canvas_container,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#0a0a1a",
            highlightthickness=1,
            highlightbackground="#00ff88"
        )
        self.canvas.pack(fill="both", expand=True)

        event_frame = tk.Frame(self.frame, bg="#111128", height=80)
        event_frame.pack(fill="x")
        event_frame.pack_propagate(False)

        tk.Label(event_frame, text="⚡ Events:", font=("Arial", 11, "bold"),
                 fg="#ffd43b", bg="#111128").pack(side="left", padx=10, pady=5)
        self.event_display = tk.Label(event_frame, text="Waiting for players to join...",
                                      font=("Consolas", 11), fg="#8b949e", bg="#111128",
                                      wraplength=800, justify="left")
        self.event_display.pack(side="left", padx=5, pady=5, fill="x", expand=True)

    def start(self):
        self.running = True
        threading.Thread(target=self._game_loop, daemon=True).start()
        threading.Thread(target=self._sync_with_server, daemon=True).start()

    def stop(self):
        self.running = False

    def _get_next_color(self):
        color = self.player_colors[self.color_index % len(self.player_colors)]
        self.color_index += 1
        return color

    def _add_event(self, text):
        from datetime import datetime
        self.event_log.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
        self.event_log = self.event_log[:5]

    def _sync_with_server(self):
        """مزامنة اللاعبين مع السيرفر الحقيقي."""
        while self.running:
            try:
                server_players = self.server.get_all_players()
                server_ids = set(server_players.keys())
                with self.lock:
                    live_ids = set(self.players.keys())
                    # إضافة لاعبين جدد
                    for pid in server_ids - live_ids:
                        game_id = self.server.get_player_game(pid) or 0
                        color = self._get_next_color()
                        zone_x = ((game_id % 3) * 300 + 50) if game_id else 50
                        zone_x = min(zone_x, self.canvas_width - 100)
                        x = zone_x + random.uniform(20, 250)
                        y = random.uniform(80, self.canvas_height - 80)
                        x = max(30, min(self.canvas_width - 30, x))
                        y = max(50, min(self.canvas_height - 50, y))
                        pdata = server_players[pid]
                        name = pdata.get('name', f'P{pid}')[:8]
                        self.players[pid] = LiveGamePlayer(pid, x, y, color, name, game_id)
                        self._add_event(f"👤 {name} joined the arena")
                    # إزالة اللاعبين الذين غادروا
                    for pid in live_ids - server_ids:
                        if pid in self.players:
                            p = self.players[pid]
                            if p.alive:
                                self._add_event(f"💨 {p.name} left the server")
                            del self.players[pid]
                    # تحديث معلومات اللعبة
                    for pid in server_ids & live_ids:
                        game_id = self.server.get_player_game(pid) or 0
                        if pid in self.players:
                            self.players[pid].game_id = game_id
            except Exception:
                pass
            time.sleep(0.8)

    def _game_loop(self):
        """حلقة اللعبة الرئيسية."""
        last_draw = time.time()
        while self.running:
            now = time.time()
            dt = now - last_draw
            last_draw = now
            with self.lock:
                try:
                    self._update_physics(dt)
                    self._update_bullets(dt)
                    self._check_collisions()
                    self._draw_frame()
                except Exception:
                    pass
            time.sleep(0.033)  # ~30 FPS

    def _update_physics(self, dt):
        """تحديث حركة اللاعبين وإطلاق النار."""
        for pid, p in list(self.players.items()):
            if not p.alive:
                continue

            # تغيير عشوائي في الاتجاه والسرعة
            if random.random() < 0.01:
                p.direction *= -1
            if random.random() < 0.005:
                p.dy += random.uniform(-0.5, 0.5)
                p.dy = max(-2, min(2, p.dy))
            if random.random() < 0.01:
                p.speed = random.uniform(1.0, 4.0)

            # حركة
            p.x += p.direction * p.speed
            p.y += p.dy

            # ارتداد من الحواف
            if p.x <= p.radius or p.x >= self.canvas_width - p.radius:
                p.direction *= -1
                p.x = max(p.radius, min(self.canvas_width - p.radius, p.x))
            if p.y <= 50 or p.y >= self.canvas_height - 50:
                p.dy *= -1
                p.y = max(50, min(self.canvas_height - 50, p.y))

            # إطلاق النار
            p.shoot_timer -= dt
            if p.shoot_timer <= 0 and len(self.players) > 1:
                p.shoot_timer = random.uniform(0.8, 3.0)
                targets = [op for oid, op in self.players.items()
                           if oid != pid and op.alive and op.game_id == p.game_id]
                if not targets:
                    targets = [op for oid, op in self.players.items()
                               if oid != pid and op.alive]
                if targets:
                    target = random.choice(targets)
                    dx = target.x - p.x
                    dy = target.y - p.y
                    dist = math.sqrt(dx*dx + dy*dy) or 1
                    speed = random.uniform(5, 8)
                    scatter = random.uniform(-0.1, 0.1)
                    bx = (dx / dist + scatter) * speed
                    by = (dy / dist + scatter) * speed
                    color = random.choice(self.bullet_colors)
                    self.bullets.append(Bullet(p.x, p.y, bx, by, pid, color))

            if p.hit_flash > 0:
                p.hit_flash -= dt * 3
                if p.hit_flash < 0:
                    p.hit_flash = 0

    def _update_bullets(self, dt):
        """تحديث الرصاص."""
        for b in self.bullets[:]:
            b.x += b.dx
            b.y += b.dy
            margin = 20
            if (b.x < -margin or b.x > self.canvas_width + margin or
                    b.y < -margin or b.y > self.canvas_height + margin):
                b.alive = False
        self.bullets = [b for b in self.bullets if b.alive]

    def _check_collisions(self):
        """فحص التصادم مع تأثيرات محسنة."""
        for b in self.bullets[:]:
            if not b.alive:
                continue
            for pid, p in list(self.players.items()):
                if pid == b.owner_id or not p.alive:
                    continue
                dist = math.sqrt((b.x - p.x)**2 + (b.y - p.y)**2)
                if dist < p.radius + b.radius:
                    dmg = random.randint(5, 25)
                    p.health -= dmg
                    p.hit_flash = 0.8
                    b.alive = False

                    attacker = self.players.get(b.owner_id)
                    attacker_name = attacker.name if attacker else f"P{b.owner_id}"

                    if p.health <= 0:
                        p.health = 0
                        p.alive = False
                        # تأثير الموت
                        with self.death_effect_lock:
                            self.death_effects.append({
                                'x': p.x,
                                'y': p.y,
                                'radius': 5,
                                'max_radius': 40,
                                'alpha': 1.0,
                                'life': 0.8,
                                'color': p.color
                            })
                        self._add_event(f"💀 {attacker_name} eliminated {p.name}!")
                        # إزالة من السيرفر بعد 0.5 ثانية
                        threading.Thread(
                            target=self._delayed_remove_player,
                            args=(pid, 0.5),
                            daemon=True
                        ).start()
                    else:
                        self._add_event(f"🔫 {attacker_name} hit {p.name} (-{dmg}hp)")

    def _delayed_remove_player(self, player_id, delay=0.5):
        """إزالة اللاعب من السيرفر بعد تأخير."""
        time.sleep(delay)
        try:
            self.server.remove_player(player_id)
        except Exception:
            pass

    def _draw_frame(self):
        """جدولة الرسم."""
        self.canvas.after(0, self._render)

    def _render(self):
        """الرسم الفعلي."""
        if not self.running:
            return

        self.canvas.delete("all")
        w = self.canvas_width
        h = self.canvas_height

        # خلفية
        self.canvas.create_rectangle(0, 0, w, h, fill="#0a0a1a", outline="")

        # تأثيرات الموت
        with self.death_effect_lock:
            for effect in self.death_effects[:]:
                effect['radius'] += (effect['max_radius'] - effect['radius']) * 0.15
                effect['alpha'] -= 0.02
                effect['life'] -= 0.03
                if effect['life'] <= 0 or effect['alpha'] <= 0:
                    self.death_effects.remove(effect)
                    continue
                alpha = int(255 * effect['alpha'])
                color = effect['color']
                r = effect['radius']
                for i in range(3):
                    r2 = r * (1 + i * 0.3)
                    self.canvas.create_oval(
                        effect['x'] - r2, effect['y'] - r2,
                        effect['x'] + r2, effect['y'] + r2,
                        outline=color,
                        width=2,
                        stipple="gray50" if alpha < 128 else "",
                        fill=""
                    )
                self.canvas.create_oval(
                    effect['x'] - r * 0.4, effect['y'] - r * 0.4,
                    effect['x'] + r * 0.4, effect['y'] + r * 0.4,
                    fill=color, outline=""
                )

        # شبكة خلفية
        for gx in range(0, w, 60):
            self.canvas.create_line(gx, 0, gx, h, fill="#111130", width=1)
        for gy in range(0, h, 60):
            self.canvas.create_line(0, gy, w, gy, fill="#111130", width=1)

        # مناطق الألعاب
        games = self.server.get_all_games()
        zone_colors = ["#00ff8808", "#0ea5e908", "#ffd43b08", "#ff6b6b08"]
        for i, (gid, game) in enumerate(games.items()):
            if i >= 3:
                break
            zx = i * (w // 3)
            zy = 0
            zw = w // 3
            zh = h
            color = zone_colors[i % len(zone_colors)]
            self.canvas.create_rectangle(zx, zy, zx + zw, zy + zh,
                                         fill=color, outline=zone_colors[i % len(zone_colors)].replace("08", "33"))
            self.canvas.create_text(zx + zw // 2, 20,
                                    text=f"🎮 {game.game_name} ({len(game.players)} players)",
                                    fill="#ffffff44", font=("Arial", 9))

        # رسم الرصاص
        for b in self.bullets:
            if b.alive:
                glow_r = b.radius + 5
                self.canvas.create_oval(b.x - glow_r, b.y - glow_r,
                                        b.x + glow_r, b.y + glow_r,
                                        fill=b.color + "44", outline="")
                self.canvas.create_oval(b.x - b.radius, b.y - b.radius,
                                        b.x + b.radius, b.y + b.radius,
                                        fill=b.color, outline="white", width=1)

        # رسم اللاعبين
        for pid, p in list(self.players.items()):
            if not p.alive:
                continue

            body_color = "#ff4444" if p.hit_flash > 0.4 else p.color
            glow_alpha = "66" if p.hit_flash > 0 else "22"
            glow_r = p.radius + 8

            self.canvas.create_oval(
                p.x - glow_r, p.y - glow_r,
                p.x + glow_r, p.y + glow_r,
                fill=p.color + glow_alpha, outline=""
            )
            r = p.radius
            self.canvas.create_oval(
                p.x - r, p.y - r,
                p.x + r, p.y + r,
                fill=body_color, outline=p.color, width=2
            )
            self.canvas.create_text(p.x, p.y, text=p.emoji, font=("Arial", 14))
            self.canvas.create_text(p.x, p.y - r - 18,
                                    text=p.name, fill="white",
                                    font=("Consolas", 8, "bold"))
            # شريط الصحة
            bar_w = 36
            bar_h = 5
            bar_x = p.x - bar_w // 2
            bar_y = p.y - r - 10
            hp_ratio = p.health / p.max_health
            hp_color = "#3fb950" if hp_ratio > 0.5 else ("#d29922" if hp_ratio > 0.25 else "#f85149")
            self.canvas.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
                                         fill="#333", outline="")
            self.canvas.create_rectangle(bar_x, bar_y, bar_x + int(bar_w * hp_ratio),
                                         bar_y + bar_h, fill=hp_color, outline="")
            self.canvas.create_text(p.x, bar_y + 2,
                                    text=f"{int(p.health)}",
                                    fill="white", font=("Arial", 7, "bold"))

        if not self.players and not self.death_effects:
            self.canvas.create_text(w // 2, h // 2,
                                    text="🕹️ No players online\nAdd players to start the show!",
                                    fill="#334455", font=("Arial", 18), justify="center")

        # تحديث معلومات الرأس
        try:
            self.live_players_label.config(text=f"👥 {self.server.get_player_count()} Players")
            self.live_games_label.config(text=f"🎮 {self.server.get_active_games_count()} Games")
            if self.event_log:
                self.event_display.config(text=" | ".join(self.event_log[:3]))
        except Exception:
            pass