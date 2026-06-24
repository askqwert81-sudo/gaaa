"""
game_gui.py - الواجهة الرسومية المتطورة - Pro Edition v4.0
مع: نظام تسجيل الدخول، البث المباشر، تحسينات شاملة
تم التعديل لاستخدام نسخة محسنة من البث المباشر (live_game_enhanced.py) إذا كانت متوفرة.
جميع الأزرار العائمة تعمل بشكل صحيح.
تم إضافة محاكاة التضارب التلقائية واليدوية مع تسجيل مفصل في السجلات.
"""

import sys
import threading
import time
import random
import math
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

try:
    import customtkinter as ctk
    from tkinter import Canvas
    import tkinter as tk
except ImportError:
    print("❌ customtkinter غير مثبت. قم بتشغيل: pip install customtkinter")
    sys.exit(1)

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️ matplotlib غير مثبت. سيتم تعطيل الرسوم البيانية.")

try:
    from game_server_core import GameServerCore
    from game_client_sim import ClientManager
except ImportError as e:
    print(f"❌ فشل استيراد ملفات المشروع: {e}")
    sys.exit(1)

# ===================================================================
# محاولة استيراد النسخة المحسنة من البث المباشر
# ===================================================================
try:
    from live_game_enhanced import LiveGameCanvasEnhanced
    LIVE_ENHANCED_AVAILABLE = True
except ImportError:
    LIVE_ENHANCED_AVAILABLE = False
    # سيتم استخدام النسخة الأصلية من game_gui (معرفة لاحقاً)

# ===================================================================
# بيانات المستخدمين (محاكاة قاعدة بيانات)
# ===================================================================
USERS_DB = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "display_name": "System Administrator",
        "avatar": "👑",
        "permissions": ["all"]
    },
    "operator1": {
        "password": "op1pass",
        "role": "operator",
        "display_name": "Operator Ahmed",
        "avatar": "🎮",
        "permissions": ["view", "add_player", "kick_player"]
    },
    "operator2": {
        "password": "op2pass",
        "role": "operator",
        "display_name": "Operator Sara",
        "avatar": "🎯",
        "permissions": ["view", "add_player"]
    },
    "monitor1": {
        "password": "mon1pass",
        "role": "monitor",
        "display_name": "Monitor Ali",
        "avatar": "📊",
        "permissions": ["view"]
    },
    "monitor2": {
        "password": "mon2pass",
        "role": "monitor",
        "display_name": "Monitor Nora",
        "avatar": "👁️",
        "permissions": ["view"]
    },
}

ROLE_COLORS = {
    "admin": "#ff6b35",
    "operator": "#4caf50",
    "monitor": "#2196f3"
}

ROLE_LABELS = {
    "admin": "Admin",
    "operator": "Operator",
    "monitor": "Monitor"
}

# ===================================================================
# إعدادات المظهر
# ===================================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

THEMES = {
    "dark": {
        "bg_primary": "#0d1117",
        "bg_secondary": "#161b22",
        "bg_card": "#1f2937",
        "accent": "#00ff88",
        "accent2": "#0ea5e9",
        "text": "#e6edf3",
        "text_dim": "#8b949e",
        "border": "#30363d",
        "danger": "#f85149",
        "warning": "#d29922",
        "success": "#3fb950",
    },
    "light": {
        "bg_primary": "#f0f4f8",
        "bg_secondary": "#ffffff",
        "bg_card": "#e8edf2",
        "accent": "#0ea5e9",
        "accent2": "#7c3aed",
        "text": "#1c2938",
        "text_dim": "#6b7280",
        "border": "#d1d5db",
        "danger": "#dc2626",
        "warning": "#d97706",
        "success": "#16a34a",
    }
}


# ===================================================================
# نظام الإشعارات المحسّن
# ===================================================================
class ToastNotification:
    def __init__(self, master):
        self.master = master
        self.toasts = []

    def show(self, message, duration=3, type="info"):
        toast = ctk.CTkToplevel(self.master)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        colors = {
            "info": ("#0ea5e9", "#0c4a6e"),
            "success": ("#3fb950", "#14532d"),
            "warning": ("#d29922", "#78350f"),
            "error": ("#f85149", "#7f1d1d")
        }
        icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        fg, bg = colors.get(type, colors["info"])
        toast.configure(fg_color=bg)

        # حساب الموضع
        offset_y = 70 + len([t for t in self.toasts if t.winfo_exists()]) * 70
        x = self.master.winfo_x() + self.master.winfo_width() - 370
        y = self.master.winfo_y() + offset_y
        toast.geometry(f"350x55+{x}+{y}")

        frame = ctk.CTkFrame(toast, fg_color=fg, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=3, pady=3)
        ctk.CTkLabel(frame, text=f"{icons.get(type, '')} {message}",
                     font=("Arial", 12, "bold"), text_color="white",
                     wraplength=310).pack(pady=12, padx=15)

        self.toasts.append(toast)
        self.master.after(duration * 1000, lambda: self._remove_toast(toast))

    def _remove_toast(self, toast):
        try:
            toast.destroy()
            if toast in self.toasts:
                self.toasts.remove(toast)
        except Exception:
            pass


# ===================================================================
# زر عائم محسّن مع تأثير نبض
# ===================================================================
class FloatingButton(ctk.CTkButton):
    def __init__(self, master, text="", command=None, tooltip="", **kwargs):
        fg_color = kwargs.pop('fg_color', '#00ff88')
        hover_color = kwargs.pop('hover_color', '#00cc6a')
        super().__init__(
            master,
            text=text,
            command=command,
            width=56,
            height=56,
            corner_radius=28,
            fg_color=fg_color,
            hover_color=hover_color,
            font=("Arial", 22, "bold"),
            border_width=2,
            border_color="#ffffff",
            **kwargs
        )
        self.tooltip_text = tooltip
        self._text = text
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        if self.tooltip_text:
            self.configure(text=self.tooltip_text if len(self.tooltip_text) < 5 else self._text)

    def _on_leave(self, e):
        pass


# ===================================================================
# محرك اللعبة المرئية البسيطة (Live Game View) - النسخة الأصلية
# ===================================================================
class LiveGamePlayer:
    """لاعب في البث المباشر"""
    def __init__(self, player_id: int, x: float, y: float, color: str, name: str, game_id: int):
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
        self.bullets = []
        self.shoot_timer = random.uniform(1, 3)
        self.radius = 18
        self.emoji = random.choice(["🧑", "👦", "👩", "🧔", "👱"])


class Bullet:
    """رصاصة في اللعبة"""
    def __init__(self, x, y, dx, dy, owner_id, color):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.owner_id = owner_id
        self.color = color
        self.alive = True
        self.radius = 4


class LiveGameCanvas:
    """كانفاس البث المباشر للعبة - النسخة الأصلية"""
    def __init__(self, parent, server):
        self.parent = parent
        self.server = server
        self.canvas_width = 900
        self.canvas_height = 480
        self.players: Dict[int, LiveGamePlayer] = {}
        self.bullets: List[Bullet] = []
        self.running = False
        self.lock = threading.Lock()
        self.kill_callbacks = []
        self.event_log = []

        # الألوان
        self.player_colors = [
            "#ff6b6b", "#ffa94d", "#ffd43b", "#69db7c",
            "#74c0fc", "#e599f7", "#f783ac", "#a9e34b",
            "#63e6be", "#74b0ff"
        ]
        self.color_index = 0

        # بناء الكانفاس
        self._build()

    def _build(self):
        self.frame = ctk.CTkFrame(self.parent, fg_color="#0a0a1a", corner_radius=12)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)

        # رأس البث
        header = ctk.CTkFrame(self.frame, fg_color="#111128", height=45, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="🔴 LIVE", font=("Arial", 14, "bold"),
                     text_color="#ff4444").pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(header, text="Game Server Battle Arena",
                     font=("Arial", 14, "bold"), text_color="#00ff88").pack(side="left")

        self.live_players_label = ctk.CTkLabel(header, text="👥 0 Players",
                                               font=("Arial", 12), text_color="#8b949e")
        self.live_players_label.pack(side="right", padx=15)

        self.live_games_label = ctk.CTkLabel(header, text="🎮 0 Games",
                                              font=("Arial", 12), text_color="#8b949e")
        self.live_games_label.pack(side="right", padx=15)

        # الكانفاس الرئيسي
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

        # سجل الأحداث
        event_frame = ctk.CTkFrame(self.frame, fg_color="#111128", height=80, corner_radius=0)
        event_frame.pack(fill="x")
        event_frame.pack_propagate(False)

        ctk.CTkLabel(event_frame, text="⚡ Events:", font=("Arial", 11, "bold"),
                     text_color="#ffd43b").pack(side="left", padx=10, pady=5)
        self.event_display = ctk.CTkLabel(event_frame, text="Waiting for players to join...",
                                          font=("Consolas", 11), text_color="#8b949e",
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

    def _sync_with_server(self):
        """مزامنة اللاعبين مع السيرفر الحقيقي"""
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
                        # توزيع اللاعبين حسب اللعبة
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

    def _add_event(self, text):
        self.event_log.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
        self.event_log = self.event_log[:5]

    def _game_loop(self):
        """حلقة اللعبة الرئيسية"""
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
        """تحديث حركة اللاعبين"""
        for pid, p in list(self.players.items()):
            if not p.alive:
                continue

            # حركة ذهاباً وإياباً
            p.x += p.direction * p.speed
            p.y += p.dy

            # ارتداد من الحواف
            if p.x <= p.radius or p.x >= self.canvas_width - p.radius:
                p.direction *= -1
                p.x = max(p.radius, min(self.canvas_width - p.radius, p.x))

            if p.y <= 50 or p.y >= self.canvas_height - 50:
                p.dy *= -1
                p.y = max(50, min(self.canvas_height - 50, p.y))

            # تغيير طفيف عشوائي
            if random.random() < 0.02:
                p.dy += random.uniform(-0.3, 0.3)
                p.dy = max(-2, min(2, p.dy))

            if random.random() < 0.005:
                p.speed = random.uniform(1.5, 3.5)

            # إطلاق النار
            p.shoot_timer -= dt
            if p.shoot_timer <= 0 and len(self.players) > 1:
                p.shoot_timer = random.uniform(1.5, 4.0)
                # استهداف لاعب عشوائي في نفس اللعبة أو أقرب لاعب
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
                    # سرعة الرصاصة مع انحراف طفيف
                    speed = 6
                    scatter = random.uniform(-0.15, 0.15)
                    bx = (dx / dist + scatter) * speed
                    by = (dy / dist + scatter) * speed
                    self.bullets.append(Bullet(p.x, p.y, bx, by, pid, p.color))

            # تناقص تأثير الضربة
            if p.hit_flash > 0:
                p.hit_flash -= dt * 3

    def _update_bullets(self, dt):
        """تحريك الرصاص"""
        for b in self.bullets[:]:
            b.x += b.dx
            b.y += b.dy
            if (b.x < 0 or b.x > self.canvas_width or
                    b.y < 0 or b.y > self.canvas_height):
                b.alive = False
        self.bullets = [b for b in self.bullets if b.alive]

    def _check_collisions(self):
        """فحص تصادم الرصاص مع اللاعبين"""
        for b in self.bullets[:]:
            if not b.alive:
                continue
            for pid, p in list(self.players.items()):
                if pid == b.owner_id or not p.alive:
                    continue
                dist = math.sqrt((b.x - p.x)**2 + (b.y - p.y)**2)
                if dist < p.radius + b.radius:
                    # إصابة!
                    dmg = random.randint(8, 20)
                    p.health -= dmg
                    p.hit_flash = 1.0
                    b.alive = False

                    # الحصول على اسم المهاجم
                    attacker = self.players.get(b.owner_id)
                    attacker_name = attacker.name if attacker else f"P{b.owner_id}"

                    if p.health <= 0:
                        p.health = 0
                        p.alive = False
                        self._add_event(f"💀 {attacker_name} eliminated {p.name}!")
                        # إخراج اللاعب من السيرفر عند الموت
                        threading.Thread(
                            target=self._remove_player_from_server,
                            args=(pid,), daemon=True
                        ).start()
                    else:
                        self._add_event(f"🔫 {attacker_name} hit {p.name} (-{dmg}hp)")
                    break

    def _remove_player_from_server(self, player_id):
        """إخراج اللاعب من السيرفر"""
        try:
            time.sleep(0.5)
            self.server.remove_player(player_id)
        except Exception:
            pass

    def _draw_frame(self):
        """رسم الإطار الكامل"""
        self.canvas.after(0, self._render)

    def _render(self):
        """الرسم الفعلي على الكانفاس"""
        if not self.running:
            return

        self.canvas.delete("all")
        w = self.canvas_width
        h = self.canvas_height

        # خلفية الملعب
        self.canvas.create_rectangle(0, 0, w, h, fill="#0a0a1a", outline="")

        # خطوط الشبكة
        for gx in range(0, w, 60):
            self.canvas.create_line(gx, 0, gx, h, fill="#111130", width=1)
        for gy in range(0, h, 60):
            self.canvas.create_line(0, gy, w, gy, fill="#111130", width=1)

        # مناطق الألعاب (إذا وجدت)
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
                glow_r = b.radius + 3
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

            # تأثير الضربة
            body_color = "#ff4444" if p.hit_flash > 0.5 else p.color
            glow_alpha = "66" if p.hit_flash > 0 else "22"
            glow_r = p.radius + 8

            # توهج
            self.canvas.create_oval(
                p.x - glow_r, p.y - glow_r,
                p.x + glow_r, p.y + glow_r,
                fill=p.color + glow_alpha, outline=""
            )

            # جسم اللاعب
            r = p.radius
            self.canvas.create_oval(
                p.x - r, p.y - r,
                p.x + r, p.y + r,
                fill=body_color, outline=p.color, width=2
            )

            # الإيموجي
            self.canvas.create_text(p.x, p.y, text=p.emoji,
                                    font=("Arial", 14))

            # اسم اللاعب
            self.canvas.create_text(p.x, p.y - r - 18,
                                    text=p.name,
                                    fill="white",
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

        # إذا لا يوجد لاعبين
        if not self.players:
            self.canvas.create_text(w // 2, h // 2,
                                    text="🕹️ No players online\nAdd players to start the show!",
                                    fill="#334455", font=("Arial", 18), justify="center")

        # تحديث معلومات الرأس
        try:
            self.live_players_label.configure(text=f"👥 {self.server.get_player_count()} Players")
            self.live_games_label.configure(text=f"🎮 {self.server.get_active_games_count()} Games")

            # تحديث سجل الأحداث
            if self.event_log:
                self.event_display.configure(text=" | ".join(self.event_log[:3]))
        except Exception:
            pass


# ===================================================================
# شاشة تسجيل الدخول
# ===================================================================
class LoginScreen:
    def __init__(self, on_login_success):
        self.on_login_success = on_login_success
        self.root = ctk.CTk()
        self.root.title("Game Server Pro - Login")
        self.root.geometry("520x700")
        self.root.resizable(False, False)
        self._center_window()
        self._build_ui()

    def _center_window(self):
        self.root.update_idletasks()
        w = 520
        h = 700
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        self.root.configure(fg_color="#0d1117")

        # الخلفية المزخرفة
        main_frame = ctk.CTkFrame(self.root, fg_color="#0d1117", corner_radius=0)
        main_frame.pack(fill="both", expand=True)

        # الشعار والعنوان
        logo_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        logo_frame.pack(pady=(40, 20))

        ctk.CTkLabel(logo_frame, text="🎮",
                     font=("Arial", 64)).pack()
        ctk.CTkLabel(logo_frame, text="Game Server Pro",
                     font=("Arial", 28, "bold"),
                     text_color="#00ff88").pack()
        ctk.CTkLabel(logo_frame, text="Operating Systems 2 • Simulation Engine",
                     font=("Arial", 12),
                     text_color="#8b949e").pack(pady=5)

        # خط فاصل
        sep = ctk.CTkFrame(main_frame, height=1, fg_color="#30363d")
        sep.pack(fill="x", padx=40, pady=15)

        # بطاقة تسجيل الدخول
        card = ctk.CTkFrame(main_frame, fg_color="#161b22", corner_radius=16,
                             border_width=1, border_color="#30363d")
        card.pack(padx=40, fill="x")

        ctk.CTkLabel(card, text="Sign In",
                     font=("Arial", 22, "bold"),
                     text_color="#e6edf3").pack(pady=(25, 5))
        ctk.CTkLabel(card, text="Enter your credentials to continue",
                     font=("Arial", 12), text_color="#8b949e").pack(pady=(0, 20))

        # حقل اسم المستخدم
        ctk.CTkLabel(card, text="Username", font=("Arial", 13, "bold"),
                     text_color="#8b949e", anchor="w").pack(fill="x", padx=25)
        self.username_entry = ctk.CTkEntry(
            card, placeholder_text="Enter username",
            height=45, font=("Arial", 14),
            fg_color="#0d1117", border_color="#30363d",
            corner_radius=8
        )
        self.username_entry.pack(fill="x", padx=25, pady=(5, 15))

        # حقل كلمة المرور
        ctk.CTkLabel(card, text="Password", font=("Arial", 13, "bold"),
                     text_color="#8b949e", anchor="w").pack(fill="x", padx=25)
        self.password_entry = ctk.CTkEntry(
            card, placeholder_text="Enter password",
            show="*", height=45, font=("Arial", 14),
            fg_color="#0d1117", border_color="#30363d",
            corner_radius=8
        )
        self.password_entry.pack(fill="x", padx=25, pady=(5, 5))

        # رسالة الخطأ
        self.error_label = ctk.CTkLabel(card, text="",
                                        font=("Arial", 12),
                                        text_color="#f85149")
        self.error_label.pack(pady=5)

        # زر تسجيل الدخول
        self.login_btn = ctk.CTkButton(
            card, text="Sign In →",
            height=48, font=("Arial", 15, "bold"),
            fg_color="#00ff88", hover_color="#00cc6a",
            text_color="#0d1117", corner_radius=10,
            command=self._attempt_login
        )
        self.login_btn.pack(fill="x", padx=25, pady=(10, 25))

        # ربط Enter بتسجيل الدخول
        self.root.bind("<Return>", lambda e: self._attempt_login())

        # قائمة الحسابات المتاحة
        hint_frame = ctk.CTkFrame(main_frame, fg_color="#161b22", corner_radius=12,
                                  border_width=1, border_color="#30363d")
        hint_frame.pack(padx=40, pady=15, fill="x")

        ctk.CTkLabel(hint_frame, text="👤 Available Accounts",
                     font=("Arial", 13, "bold"), text_color="#8b949e").pack(pady=(15, 8))

        accounts_data = [
            ("admin", "admin123", "admin"),
            ("operator1", "op1pass", "operator"),
            ("operator2", "op2pass", "operator"),
            ("monitor1", "mon1pass", "monitor"),
            ("monitor2", "mon2pass", "monitor"),
        ]

        for uname, pwd, role in accounts_data:
            row = ctk.CTkFrame(hint_frame, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            role_color = ROLE_COLORS.get(role, "#8b949e")
            ctk.CTkLabel(row, text=f"{USERS_DB[uname]['avatar']} {uname}",
                         font=("Consolas", 11), text_color="#c9d1d9",
                         width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"pass: {pwd}",
                         font=("Consolas", 11), text_color="#8b949e",
                         width=100, anchor="w").pack(side="left")
            role_lbl = ctk.CTkLabel(row, text=ROLE_LABELS.get(role, role),
                                    font=("Arial", 10, "bold"),
                                    text_color="white",
                                    fg_color=role_color,
                                    corner_radius=5, width=65)
            role_lbl.pack(side="right", padx=5)
            # زر سريع للنقر
            quick_btn = ctk.CTkButton(row, text="Use",
                                      width=40, height=22,
                                      font=("Arial", 9),
                                      fg_color="#30363d",
                                      hover_color="#484f58",
                                      corner_radius=5,
                                      command=lambda u=uname, p=pwd: self._quick_fill(u, p))
            quick_btn.pack(side="right", padx=3)

        ctk.CTkLabel(hint_frame, text="", height=5).pack()

    def _quick_fill(self, username, password):
        self.username_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
        self.username_entry.insert(0, username)
        self.password_entry.insert(0, password)

    def _attempt_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.error_label.configure(text="⚠️ Please enter username and password")
            return

        if username in USERS_DB and USERS_DB[username]["password"] == password:
            user_data = USERS_DB[username]
            self.login_btn.configure(text="✅ Logging in...", state="disabled")
            self.root.after(600, lambda: self._success(user_data, username))
        else:
            self.error_label.configure(text="❌ Invalid username or password")
            self.password_entry.delete(0, "end")
            # تأثير اهتزاز بصري
            self.login_btn.configure(fg_color="#f85149")
            self.root.after(500, lambda: self.login_btn.configure(fg_color="#00ff88"))

    def _success(self, user_data, username):
        self.root.destroy()
        self.on_login_success(user_data, username)

    def run(self):
        self.root.mainloop()


# ===================================================================
# الواجهة الرئيسية المطورة
# ===================================================================
class GameServerGUI:
    def __init__(self, user_data: dict, username: str):
        self.user_data = user_data
        self.username = username
        self.current_role = user_data["role"]

        self.server = GameServerCore()
        self.client_manager = ClientManager(self.server)

        self.root = ctk.CTk()
        self.root.title(f"🎮 Game Server Pro v4.0 — {user_data['display_name']}")
        self.root.geometry("1450x950")
        self.root.minsize(1280, 800)

        # المظهر
        self.current_theme = "dark"

        # الإشعارات
        self.toast = ToastNotification(self.root)

        # بيانات الرسم البياني
        self.history_times = []
        self.history_players = []
        self.history_games = []

        self.update_id = None

        # البث المباشر
        self.live_game = None

        # متغير لتتبع حالة المحاكاة التلقائية
        self.auto_race_running = False

        self._build_ui()
        self._start_periodic_updates()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _has_permission(self, perm: str) -> bool:
        perms = self.user_data.get("permissions", [])
        return "all" in perms or perm in perms

    # =================================================================
    # بناء الواجهة
    # =================================================================
    def _build_ui(self):
        # ===== شريط العنوان =====
        self.title_bar = ctk.CTkFrame(self.root, height=65, fg_color="#0d1117", corner_radius=0)
        self.title_bar.pack(fill="x")
        self.title_bar.pack_propagate(False)

        # زر تبديل المظهر
        self.theme_btn = ctk.CTkButton(
            self.title_bar, text="🌙", width=44, height=44,
            corner_radius=22, fg_color="#161b22",
            hover_color="#30363d", font=("Arial", 20),
            command=self.toggle_theme, border_width=1, border_color="#30363d"
        )
        self.theme_btn.pack(side="left", padx=12, pady=10)

        # العنوان
        ctk.CTkLabel(
            self.title_bar,
            text="⚡ Game Server Simulation",
            font=("Arial", 22, "bold"), text_color="#00ff88"
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            self.title_bar,
            text="Pro Edition v4.0 | OS2",
            font=("Arial", 12), text_color="#8b949e"
        ).pack(side="left", padx=8)

        # معلومات المستخدم (يمين)
        user_frame = ctk.CTkFrame(self.title_bar, fg_color="#161b22",
                                   corner_radius=22, border_width=1,
                                   border_color="#30363d")
        user_frame.pack(side="right", padx=15, pady=10)

        role_color = ROLE_COLORS.get(self.current_role, "#8b949e")
        ctk.CTkLabel(user_frame,
                     text=f"{self.user_data['avatar']} {self.user_data['display_name']}",
                     font=("Arial", 13, "bold"), text_color="#e6edf3").pack(
            side="left", padx=(15, 5), pady=8)
        role_badge = ctk.CTkLabel(user_frame,
                                   text=f" {ROLE_LABELS.get(self.current_role, self.current_role).upper()} ",
                                   font=("Arial", 10, "bold"),
                                   text_color="white",
                                   fg_color=role_color,
                                   corner_radius=8)
        role_badge.pack(side="left", padx=(0, 15), pady=8)

        # زر تسجيل الخروج
        ctk.CTkButton(
            self.title_bar, text="🚪 Logout",
            width=80, height=34, corner_radius=8,
            fg_color="#21262d", hover_color="#30363d",
            font=("Arial", 11), command=self._logout,
            border_width=1, border_color="#30363d"
        ).pack(side="right", padx=8, pady=15)

        # ===== التبويبات =====
        self.tabview = ctk.CTkTabview(
            self.root, width=1400, height=820,
            segmented_button_selected_color="#00ff88",
            segmented_button_unselected_color="#21262d",
            segmented_button_fg_color="#161b22",
            fg_color="#0d1117",
        )
        self.tabview.pack(padx=15, pady=10, fill="both", expand=True)

        tabs = [
            "🎛️ Control", "📊 Dashboard", "👥 Players",
            "🎮 Games", "⚙️ Resources", "📋 Scheduling",
            "🔒 Deadlock", "📈 Statistics", "🎬 Live View", "📝 Logs"
        ]
        for tab in tabs:
            self.tabview.add(tab)

        self._build_control_tab()
        self._build_dashboard_tab()
        self._build_players_tab()
        self._build_games_tab()
        self._build_resources_tab()
        self._build_scheduling_tab()
        self._build_deadlock_tab()
        self._build_statistics_tab()
        self._build_live_view_tab()
        self._build_logs_tab()

        # ===== شريط الحالة =====
        self.status_bar = ctk.CTkFrame(self.root, height=38, fg_color="#0d1117",
                                        border_width=1, border_color="#30363d",
                                        corner_radius=0)
        self.status_bar.pack(side="bottom", fill="x")

        self.status_label = ctk.CTkLabel(
            self.status_bar, text="🔴 Status: Stopped",
            font=("Consolas", 12), anchor="w", text_color="#8b949e"
        )
        self.status_label.pack(side="left", padx=20)

        self.clock_label = ctk.CTkLabel(
            self.status_bar, text="", font=("Consolas", 12), text_color="#8b949e"
        )
        self.clock_label.pack(side="right", padx=20)
        self._update_clock()

        # نبض الخادم
        self.pulse_label = ctk.CTkLabel(
            self.status_bar, text="●", font=("Arial", 14), text_color="#333"
        )
        self.pulse_label.pack(side="right", padx=5)
        self._animate_pulse()

        # ===== أزرار عائمة =====
        self.fab_add = FloatingButton(
            self.root, text="➕", command=self.fab_add_player,
            fg_color="#0ea5e9", hover_color="#0284c7", tooltip="Add Player"
        )
        self.fab_add.place(relx=0.03, rely=0.93, anchor="sw")

        self.fab_start = FloatingButton(
            self.root, text="▶", command=self.fab_toggle_server,
            fg_color="#3fb950", hover_color="#2ea043"
        )
        self.fab_start.place(relx=0.97, rely=0.93, anchor="se")

        self.fab_reset = FloatingButton(
            self.root, text="↺", command=self.fab_reset_server,
            fg_color="#d29922", hover_color="#bb8a00"
        )
        self.fab_reset.place(relx=0.50, rely=0.93, anchor="s")

        # زر اللعبة المباشرة
        self.fab_live = FloatingButton(
            self.root, text="🎬", command=self._go_to_live_view,
            fg_color="#7c3aed", hover_color="#6d28d9"
        )
        self.fab_live.place(relx=0.12, rely=0.93, anchor="sw")

        # زر المحاكاة التلقائية للتضارب
        self.fab_auto_race = FloatingButton(
            self.root, text="⚡", command=self.fab_toggle_auto_race,
            fg_color="#ff6b6b", hover_color="#ee5a24", tooltip="Auto Race"
        )
        self.fab_auto_race.place(relx=0.20, rely=0.93, anchor="sw")

    def _animate_pulse(self):
        """تأثير نبض لمؤشر الحالة"""
        if self.server.running:
            current = self.pulse_label.cget("text_color")
            color = "#00ff88" if current == "#333" else "#333"
            self.pulse_label.configure(text_color=color)
        else:
            self.pulse_label.configure(text_color="#333")
        self.root.after(600, self._animate_pulse)

    def _go_to_live_view(self):
        self.tabview.set("🎬 Live View")

    def _logout(self):
        self.on_closing()
        # إعادة تشغيل شاشة الدخول
        import subprocess
        import sys
        subprocess.Popen([sys.executable, __file__])

    # =================================================================
    # تبديل المظهر المحسّن
    # =================================================================
    def toggle_theme(self):
        if self.current_theme == "dark":
            ctk.set_appearance_mode("light")
            self.current_theme = "light"
            self.theme_btn.configure(text="☀️")
            self.title_bar.configure(fg_color="#f0f4f8")
            self.status_bar.configure(fg_color="#f0f4f8")
            self.toast.show("☀️ Light mode", type="info", duration=2)
        else:
            ctk.set_appearance_mode("dark")
            self.current_theme = "dark"
            self.theme_btn.configure(text="🌙")
            self.title_bar.configure(fg_color="#0d1117")
            self.status_bar.configure(fg_color="#0d1117")
            self.toast.show("🌙 Dark mode", type="info", duration=2)

    # =================================================================
    # أزرار عائمة
    # =================================================================
    def fab_add_player(self):
        if not self._has_permission("add_player"):
            self.toast.show("⛔ No permission to add players", type="error")
            return
        if not self.server.running:
            self.toast.show("⚠️ Start the server first!", type="warning")
            return
        behavior = random.choice(["normal", "aggressive", "casual"])
        self.client_manager.add_client(behavior)
        self.toast.show(f"👤 Player added ({behavior})", duration=2, type="success")
        self.add_log(f"➕ Player added via FAB (behavior: {behavior})")

    def fab_toggle_server(self):
        if self.server.running:
            self.stop_server()
            self.fab_start.configure(text="▶", fg_color="#3fb950")
        else:
            self.start_server()
            self.fab_start.configure(text="⏹", fg_color="#f85149")

    def fab_reset_server(self):
        self.reset_server()
        self.fab_start.configure(text="▶", fg_color="#3fb950")
        self.toast.show("🔄 Server reset", type="warning")

    def fab_toggle_auto_race(self):
        """تشغيل/إيقاف المحاكاة التلقائية للتضارب"""
        if not self._has_permission("all"):
            self.toast.show("⛔ Admin only", type="error")
            return
        if not self.server.running:
            self.toast.show("⚠️ Start the server first!", type="warning")
            return
        self.auto_race_running = not self.auto_race_running
        if self.auto_race_running:
            self.fab_auto_race.configure(fg_color="#ff0000")
            self.toast.show("⚡ Auto Race started", type="info", duration=2)
            self.add_log("⚡ Auto Race mode activated")
            threading.Thread(target=self._auto_race_loop, daemon=True).start()
        else:
            self.fab_auto_race.configure(fg_color="#ff6b6b")
            self.toast.show("⏹ Auto Race stopped", type="warning", duration=2)
            self.add_log("⏹ Auto Race mode deactivated")

    # =================================================================
    # تبويب التحكم
    # =================================================================
    def _build_control_tab(self):
        frame = self.tabview.tab("🎛️ Control")
        frame.grid_columnconfigure((0, 1, 2), weight=1)

        # بطاقة التحكم الرئيسية
        control_card = self._make_card(frame, "🎛️ Server Controls")
        control_card.grid(row=0, column=0, columnspan=3, padx=12, pady=10, sticky="ew")
        control_card.grid_columnconfigure((0, 1, 2), weight=1)

        self.btn_start = self._make_btn(control_card, "▶️  Start Server", self.start_server,
                                         "#3fb950", "#2ea043", height=50, row=1, col=0)
        self.btn_stop = self._make_btn(control_card, "⏹️  Stop Server", self.stop_server,
                                        "#f85149", "#da3633", height=50, row=1, col=1)
        self.btn_reset = self._make_btn(control_card, "↺  Reset Server", self.reset_server,
                                         "#d29922", "#bb8a00", height=50, row=1, col=2)

        # إضافة لاعبين
        players_card = self._make_card(frame, "👤 Add Players")
        players_card.grid(row=2, column=0, columnspan=3, padx=12, pady=8, sticky="ew")
        players_card.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        ctk.CTkLabel(players_card, text="Count:", font=("Arial", 13),
                     text_color="#8b949e").grid(row=1, column=0, padx=10, pady=12)
        self.manual_count_slider = ctk.CTkSlider(
            players_card, from_=1, to=20, number_of_steps=19,
            width=200, button_color="#00ff88", progress_color="#00ff88"
        )
        self.manual_count_slider.set(4)
        self.manual_count_slider.grid(row=1, column=1, padx=10, pady=12)
        self.manual_count_label = ctk.CTkLabel(players_card, text="4",
                                                font=("Arial", 16, "bold"),
                                                text_color="#00ff88")
        self.manual_count_label.grid(row=1, column=2, padx=5)
        self.manual_count_slider.configure(
            command=lambda v: self.manual_count_label.configure(text=str(int(v)))
        )

        ctk.CTkLabel(players_card, text="Behavior:", font=("Arial", 13),
                     text_color="#8b949e").grid(row=1, column=3, padx=5)
        self.behavior_option = ctk.CTkOptionMenu(
            players_card, values=["normal", "aggressive", "casual", "afk"],
            fg_color="#21262d", button_color="#00ff88",
            button_hover_color="#00cc6a", width=130
        )
        self.behavior_option.set("normal")
        self.behavior_option.grid(row=1, column=4, padx=5)

        self._make_btn(players_card, "➕ Add Players", self.add_manual_players,
                       "#0ea5e9", "#0284c7", height=42, row=1, col=5)

        # Race Simulation
        race_card = self._make_card(frame, "⚡ Race Condition Simulation")
        race_card.grid(row=3, column=0, columnspan=3, padx=12, pady=8, sticky="ew")
        race_card.grid_columnconfigure((0, 1, 2), weight=1)

        self.race_lock_switch = ctk.CTkSwitch(
            race_card, text="🔒 Use Lock/Semaphore",
            font=("Arial", 13), progress_color="#00ff88"
        )
        self.race_lock_switch.grid(row=1, column=0, padx=20, pady=10)
        self.race_lock_switch.select()

        self._make_btn(race_card, "🏃 Without Lock (Race)", self.run_race_no_lock,
                       "#f85149", "#da3633", height=42, row=1, col=1)
        self._make_btn(race_card, "🔒 With Lock (Safe)", self.run_race_with_lock,
                       "#3fb950", "#2ea043", height=42, row=1, col=2)

        # إحصائيات سريعة
        stats_card = self._make_card(frame, "📊 Quick Stats")
        stats_card.grid(row=4, column=0, columnspan=3, padx=12, pady=8, sticky="ew")
        stats_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.quick_kpis = {}
        kpi_data = [
            ("👥", "Players", "#0ea5e9"),
            ("🎮", "Games", "#d29922"),
            ("⏳", "Pending", "#7c3aed"),
            ("📡", "Throughput", "#3fb950"),
        ]
        for i, (icon, label, color) in enumerate(kpi_data):
            sub = ctk.CTkFrame(stats_card, fg_color="#0d1117", corner_radius=10)
            sub.grid(row=1, column=i, padx=10, pady=12, sticky="nsew")
            ctk.CTkLabel(sub, text=icon, font=("Arial", 24)).pack(pady=(8, 0))
            val_lbl = ctk.CTkLabel(sub, text="0", font=("Arial", 26, "bold"),
                                   text_color=color)
            val_lbl.pack()
            ctk.CTkLabel(sub, text=label, font=("Arial", 11),
                         text_color="#8b949e").pack(pady=(0, 8))
            self.quick_kpis[label] = val_lbl

        # شريط تقدم الموارد
        res_bar_card = self._make_card(frame, "⚙️ Resource Overview")
        res_bar_card.grid(row=5, column=0, columnspan=3, padx=12, pady=8, sticky="ew")
        res_bar_card.grid_columnconfigure(list(range(len(self.server.resources))), weight=1)

        self.res_compact_bars = {}
        for i, (res_type, res_obj) in enumerate(self.server.resources.items()):
            sub = ctk.CTkFrame(res_bar_card, fg_color="transparent")
            sub.grid(row=1, column=i, padx=8, pady=8, sticky="ew")
            ctk.CTkLabel(sub, text=res_type.value[:8],
                         font=("Arial", 10), text_color="#8b949e").pack()
            pb = ctk.CTkProgressBar(sub, height=12, progress_color="#00ff88",
                                     fg_color="#30363d", corner_radius=6)
            pb.set(0)
            pb.pack(fill="x", pady=3)
            lbl = ctk.CTkLabel(sub, text="0%", font=("Arial", 10, "bold"),
                                text_color="#00ff88")
            lbl.pack()
            self.res_compact_bars[res_type] = (pb, lbl, res_obj)

    # Helper: بطاقة قسم
    def _make_card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color="#161b22", corner_radius=12,
                             border_width=1, border_color="#30363d")
        ctk.CTkLabel(card, text=title, font=("Arial", 15, "bold"),
                     text_color="#e6edf3").grid(row=0, column=0, columnspan=10,
                                                 padx=15, pady=(12, 5), sticky="w")
        return card

    # Helper: زر
    def _make_btn(self, parent, text, cmd, fg, hover, height=40, row=0, col=0) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            parent, text=text, command=cmd,
            fg_color=fg, hover_color=hover,
            height=height, font=("Arial", 13, "bold"),
            corner_radius=10, border_width=1, border_color="#ffffff"
        )
        btn.grid(row=row, column=col, padx=10, pady=8, sticky="ew")
        return btn

    # =================================================================
    # تبويب الداشبورد
    # =================================================================
    def _build_dashboard_tab(self):
        frame = self.tabview.tab("📊 Dashboard")
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # KPI cards (4 cards at top)
        kpi_frame = ctk.CTkFrame(frame, fg_color="transparent")
        kpi_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        for i in range(4):
            kpi_frame.grid_columnconfigure(i, weight=1)

        self.dash_kpi = {}
        kpi_items = [
            ("👥 Online Players", "#0ea5e9", "0"),
            ("🎮 Active Games", "#d29922", "0"),
            ("✅ Success Rate", "#3fb950", "0%"),
            ("⚡ Throughput", "#7c3aed", "0/s"),
        ]
        for i, (name, color, default) in enumerate(kpi_items):
            c = ctk.CTkFrame(kpi_frame, fg_color="#161b22", corner_radius=12,
                              border_width=1, border_color="#30363d")
            c.grid(row=0, column=i, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(c, text=name, font=("Arial", 12), text_color="#8b949e").pack(pady=(14, 2))
            v = ctk.CTkLabel(c, text=default, font=("Arial", 30, "bold"), text_color=color)
            v.pack(pady=(2, 14))
            self.dash_kpi[name] = v

        # رسوم بيانية
        if MATPLOTLIB_AVAILABLE:
            chart_frame = ctk.CTkFrame(frame, fg_color="#161b22", corner_radius=12,
                                        border_width=1, border_color="#30363d")
            chart_frame.grid(row=1, column=0, columnspan=2, padx=12, pady=8, sticky="nsew")
            self.fig_main = Figure(figsize=(10, 4), dpi=90, facecolor="#161b22")
            self.ax_main = self.fig_main.add_subplot(111)
            self.ax_main.set_facecolor("#0d1117")
            self.ax_main.tick_params(colors="#8b949e")
            self.ax_main.spines[:].set_color("#30363d")
            self.ax_main.set_xlabel("Time (s)", color="#8b949e")
            self.ax_main.set_ylabel("Count", color="#8b949e")
            self.ax_main.grid(alpha=0.15, color="#30363d")
            self.canvas_main = FigureCanvasTkAgg(self.fig_main, master=chart_frame)
            self.canvas_main.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    # =================================================================
    # تبويب اللاعبين
    # =================================================================
    def _build_players_tab(self):
        frame = self.tabview.tab("👥 Players")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # شريط أعلى
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=8)

        self.players_count_label = ctk.CTkLabel(
            top, text="Total: 0 Players",
            font=("Arial", 15, "bold"), text_color="#0ea5e9"
        )
        self.players_count_label.pack(side="left", padx=10)

        if self._has_permission("kick_player"):
            ctk.CTkButton(top, text="🗑️ Kick All", width=100, height=32,
                          fg_color="#f85149", hover_color="#da3633",
                          font=("Arial", 11), corner_radius=8,
                          command=self._kick_all_players).pack(side="right", padx=10)

        self.players_table_frame = ctk.CTkScrollableFrame(
            frame, fg_color="#161b22", corner_radius=12,
            border_width=1, border_color="#30363d"
        )
        self.players_table_frame.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")
        self._refresh_players_table()

    def _refresh_players_table(self):
        for w in self.players_table_frame.winfo_children():
            w.destroy()
        headers = ["#", "Name", "Behavior", "Status", "Game", "Health", "Action"]
        header_colors = ["#8b949e"] * 7
        col_widths = [50, 140, 100, 80, 70, 80, 70]
        for j, (h, c, w) in enumerate(zip(headers, header_colors, col_widths)):
            lbl = ctk.CTkLabel(self.players_table_frame, text=h,
                                font=("Arial", 12, "bold"), width=w,
                                text_color=c)
            lbl.grid(row=0, column=j, padx=4, pady=6, sticky="w")

        # separator
        sep = ctk.CTkFrame(self.players_table_frame, height=1, fg_color="#30363d")
        sep.grid(row=1, column=0, columnspan=7, sticky="ew", padx=5, pady=2)

        players = self.server.get_all_players()
        behavior_colors = {
            "normal": "#3fb950", "aggressive": "#f85149",
            "casual": "#d29922", "afk": "#8b949e"
        }
        for row_i, (pid, data) in enumerate(players.items(), start=2):
            game_id = self.server.get_player_game(pid) or "-"
            behavior = data.get('behavior', 'normal')
            bg = "#0d1117" if row_i % 2 == 0 else "#161b22"

            ctk.CTkLabel(self.players_table_frame, text=str(pid), width=50,
                         font=("Consolas", 11), text_color="#8b949e",
                         fg_color=bg, corner_radius=0).grid(row=row_i, column=0, padx=4, pady=2)
            ctk.CTkLabel(self.players_table_frame, text=data.get('name', 'N/A'), width=140,
                         font=("Arial", 11), text_color="#e6edf3",
                         fg_color=bg, anchor="w").grid(row=row_i, column=1, padx=4, pady=2)

            beh_lbl = ctk.CTkLabel(self.players_table_frame, text=behavior, width=100,
                                    font=("Arial", 10, "bold"),
                                    text_color="white",
                                    fg_color=behavior_colors.get(behavior, "#8b949e"),
                                    corner_radius=6)
            beh_lbl.grid(row=row_i, column=2, padx=4, pady=2)

            ctk.CTkLabel(self.players_table_frame, text="🟢 online", width=80,
                         font=("Arial", 10), text_color="#3fb950",
                         fg_color=bg).grid(row=row_i, column=3, padx=4, pady=2)
            ctk.CTkLabel(self.players_table_frame, text=str(game_id), width=70,
                         font=("Consolas", 11), text_color="#0ea5e9",
                         fg_color=bg).grid(row=row_i, column=4, padx=4, pady=2)

            # شريط صحة اللاعب في اللعبة المباشرة
            live_hp = 100
            if self.live_game and pid in self.live_game.players:
                live_hp = max(0, self.live_game.players[pid].health)
            hp_color = "#3fb950" if live_hp > 50 else ("#d29922" if live_hp > 25 else "#f85149")
            hp_lbl = ctk.CTkLabel(self.players_table_frame, text=f"❤️ {live_hp}",
                                   width=80, font=("Arial", 10, "bold"),
                                   text_color=hp_color, fg_color=bg)
            hp_lbl.grid(row=row_i, column=5, padx=4, pady=2)

            if self._has_permission("kick_player"):
                btn_kick = ctk.CTkButton(
                    self.players_table_frame, text="Kick", width=60, height=26,
                    fg_color="#21262d", hover_color="#f85149",
                    font=("Arial", 10), corner_radius=6,
                    command=lambda p=pid: self._kick_player(p)
                )
                btn_kick.grid(row=row_i, column=6, padx=4, pady=2)

        self.players_count_label.configure(text=f"Total: {len(players)} Players")

    def _kick_player(self, player_id):
        self.client_manager.remove_client(player_id)
        self._refresh_players_table()
        self.add_log(f"⚡ Player {player_id} kicked.")
        self.toast.show(f"Player {player_id} kicked", type="warning", duration=2)

    def _kick_all_players(self):
        self.client_manager.stop_all()
        self._refresh_players_table()
        self.add_log("⚡ All players kicked.")
        self.toast.show("All players removed", type="warning")

    # =================================================================
    # تبويب الألعاب
    # =================================================================
    def _build_games_tab(self):
        frame = self.tabview.tab("🎮 Games")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        self.games_count_label = ctk.CTkLabel(
            top, text="Active Games: 0",
            font=("Arial", 15, "bold"), text_color="#d29922"
        )
        self.games_count_label.pack(side="left", padx=10)

        self.games_table_frame = ctk.CTkScrollableFrame(
            frame, fg_color="#161b22", corner_radius=12,
            border_width=1, border_color="#30363d"
        )
        self.games_table_frame.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")
        self._refresh_games_table()

    def _refresh_games_table(self):
        for w in self.games_table_frame.winfo_children():
            w.destroy()
        headers = ["Game ID", "Name", "Players", "Capacity", "Duration", "Status", "Action"]
        for j, h in enumerate(headers):
            ctk.CTkLabel(self.games_table_frame, text=h,
                         font=("Arial", 12, "bold"), width=110,
                         text_color="#8b949e").grid(row=0, column=j, padx=4, pady=6)
        sep = ctk.CTkFrame(self.games_table_frame, height=1, fg_color="#30363d")
        sep.grid(row=1, column=0, columnspan=7, sticky="ew", padx=5, pady=2)

        games = self.server.get_all_games()
        for row_i, (gid, game) in enumerate(games.items(), start=2):
            bg = "#0d1117" if row_i % 2 == 0 else "#161b22"
            capacity_pct = len(game.players) / game.MAX_PLAYERS
            cap_color = "#3fb950" if capacity_pct < 0.5 else ("#d29922" if capacity_pct < 1.0 else "#f85149")

            ctk.CTkLabel(self.games_table_frame, text=f"#{gid}", width=80,
                         font=("Consolas", 11, "bold"), text_color="#7c3aed",
                         fg_color=bg).grid(row=row_i, column=0, padx=4, pady=3)
            ctk.CTkLabel(self.games_table_frame, text=game.game_name, width=110,
                         font=("Arial", 11), text_color="#e6edf3",
                         fg_color=bg).grid(row=row_i, column=1, padx=4, pady=3)
            ctk.CTkLabel(self.games_table_frame, text=str(len(game.players)), width=80,
                         font=("Arial", 13, "bold"), text_color=cap_color,
                         fg_color=bg).grid(row=row_i, column=2, padx=4, pady=3)
            ctk.CTkLabel(self.games_table_frame,
                         text=f"{len(game.players)}/{game.MAX_PLAYERS}", width=80,
                         font=("Arial", 11), text_color="#8b949e",
                         fg_color=bg).grid(row=row_i, column=3, padx=4, pady=3)
            ctk.CTkLabel(self.games_table_frame, text=f"{game.duration():.0f}s", width=80,
                         font=("Arial", 11), text_color="#8b949e",
                         fg_color=bg).grid(row=row_i, column=4, padx=4, pady=3)
            ctk.CTkLabel(self.games_table_frame, text="🟢 active", width=80,
                         font=("Arial", 10), text_color="#3fb950",
                         fg_color=bg).grid(row=row_i, column=5, padx=4, pady=3)

            if self._has_permission("all"):
                ctk.CTkButton(
                    self.games_table_frame, text="End", width=65, height=26,
                    fg_color="#21262d", hover_color="#f85149",
                    font=("Arial", 10), corner_radius=6,
                    command=lambda g=gid: self._end_game(g)
                ).grid(row=row_i, column=6, padx=4, pady=3)

        self.games_count_label.configure(text=f"Active Games: {len(games)}")

    def _end_game(self, game_id):
        with self.server.games_lock:
            if game_id in self.server.games:
                del self.server.games[game_id]
        self._refresh_games_table()
        self.add_log(f"🎮 Game {game_id} ended manually.")
        self.toast.show(f"Game #{game_id} ended", type="info", duration=2)

    # =================================================================
    # تبويب الموارد
    # =================================================================
    def _build_resources_tab(self):
        frame = self.tabview.tab("⚙️ Resources")
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure(1, weight=1)

        self.resource_bars = {}
        res_frame = ctk.CTkFrame(frame, fg_color="transparent")
        res_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        for i in range(3):
            res_frame.grid_columnconfigure(i, weight=1)

        res_colors = ["#0ea5e9", "#3fb950", "#d29922", "#7c3aed", "#f85149"]
        for idx, (res_type, res_obj) in enumerate(self.server.resources.items()):
            color = res_colors[idx % len(res_colors)]
            card = ctk.CTkFrame(res_frame, fg_color="#161b22", corner_radius=12,
                                 border_width=1, border_color="#30363d")
            card.grid(row=idx // 3, column=idx % 3, padx=8, pady=8, sticky="nsew")

            ctk.CTkLabel(card, text=res_type.value,
                         font=("Arial", 13, "bold"), text_color=color).pack(pady=(12, 5), padx=15, anchor="w")
            pb = ctk.CTkProgressBar(card, height=16, progress_color=color,
                                     fg_color="#30363d", corner_radius=8)
            pb.set(0)
            pb.pack(fill="x", padx=15, pady=5)
            lbl = ctk.CTkLabel(card, text="0 / 0 (0% used)",
                                font=("Arial", 11), text_color="#8b949e")
            lbl.pack(pady=(0, 12))
            self.resource_bars[res_type] = (pb, lbl, res_obj, color)

        if MATPLOTLIB_AVAILABLE:
            chart_frame = ctk.CTkFrame(frame, fg_color="#161b22", corner_radius=12,
                                        border_width=1, border_color="#30363d")
            chart_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=8, sticky="nsew")
            self.fig_res = Figure(figsize=(9, 3), dpi=90, facecolor="#161b22")
            self.ax_res = self.fig_res.add_subplot(111)
            self.ax_res.set_facecolor("#0d1117")
            self.ax_res.tick_params(colors="#8b949e")
            self.ax_res.spines[:].set_color("#30363d")
            self.ax_res.grid(alpha=0.15, color="#30363d")
            self.canvas_res = FigureCanvasTkAgg(self.fig_res, master=chart_frame)
            self.canvas_res.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    # =================================================================
    # تبويب الجدولة
    # =================================================================
    def _build_scheduling_tab(self):
        frame = self.tabview.tab("📋 Scheduling")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="📋 Priority Scheduling Queues (0=High → 10=Low)",
                     font=("Arial", 16, "bold"), text_color="#e6edf3").grid(
            row=0, column=0, pady=12, padx=12, sticky="w")

        self.queue_frame = ctk.CTkScrollableFrame(frame, fg_color="#161b22",
                                                   corner_radius=12,
                                                   border_width=1, border_color="#30363d")
        self.queue_frame.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")
        self._refresh_queue_display()

    def _refresh_queue_display(self):
        for w in self.queue_frame.winfo_children():
            w.destroy()
        sizes = self.server.get_queue_sizes()
        max_val = max(sizes.values()) if sizes and any(sizes.values()) else 1
        priority_colors = ["#f85149", "#f97316", "#fb923c", "#fbbf24",
                           "#a3e635", "#3fb950", "#2dd4bf", "#0ea5e9",
                           "#818cf8", "#a855f7", "#ec4899"]
        for prio in range(11):
            row = ctk.CTkFrame(self.queue_frame, fg_color="#0d1117", corner_radius=8)
            row.pack(fill="x", pady=3, padx=8)
            row.grid_columnconfigure(2, weight=1)

            color = priority_colors[prio]
            badge = ctk.CTkLabel(row, text=f"P{prio}", width=45,
                                  font=("Arial", 11, "bold"),
                                  text_color=color, fg_color=color,
                                  corner_radius=6)
            badge.grid(row=0, column=0, padx=8, pady=8)

            count = sizes.get(prio, 0)
            ctk.CTkLabel(row, text=f"{count} requests",
                         font=("Consolas", 11), text_color="#e6edf3", width=100).grid(
                row=0, column=1, padx=8)

            pb = ctk.CTkProgressBar(row, height=10, progress_color=color,
                                     fg_color="#30363d", corner_radius=5)
            pb.grid(row=0, column=2, padx=10, sticky="ew", pady=8)
            pb.set(count / max_val if max_val > 0 else 0)

    # =================================================================
    # تبويب الجمود
    # =================================================================
    def _build_deadlock_tab(self):
        frame = self.tabview.tab("🔒 Deadlock")
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(frame, text="🔒 Deadlock Detection & Prevention (DFS Algorithm)",
                     font=("Arial", 16, "bold"), text_color="#e6edf3").grid(
            row=0, column=0, columnspan=2, padx=12, pady=12, sticky="w")

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=1, column=0, columnspan=2, padx=10, sticky="ew")

        self._make_btn(btn_frame, "🔍 Detect Deadlock", self.detect_deadlock,
                       "#d29922", "#bb8a00", height=44, row=0, col=0)
        self._make_btn(btn_frame, "⚠️ Simulate Deadlock", self.simulate_deadlock,
                       "#f85149", "#da3633", height=44, row=0, col=1)
        self._make_btn(btn_frame, "✅ Resolve & Clear", self._resolve_deadlock,
                       "#3fb950", "#2ea043", height=44, row=0, col=2)
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.deadlock_display = ctk.CTkTextbox(
            frame, fg_color="#0d1117", font=("Consolas", 12),
            border_width=1, border_color="#30363d", corner_radius=10
        )
        self.deadlock_display.grid(row=2, column=0, columnspan=2,
                                    padx=10, pady=10, sticky="nsew")
        self.deadlock_display.insert("1.0",
            "🔒 Deadlock Monitor Ready\n\n"
            "Click 'Simulate Deadlock' to create a deadlock scenario,\n"
            "then 'Detect Deadlock' to run the DFS cycle-detection algorithm.\n\n"
            "Algorithm Details:\n"
            "• Builds a Resource Allocation Graph (RAG)\n"
            "• Runs DFS to find cycles in the graph\n"
            "• Reports all processes involved in deadlock\n"
            "• 'Resolve & Clear' releases stuck resources"
        )

    def _resolve_deadlock(self):
        self.server.deadlock_detector.allocation.clear()
        self.server.deadlock_detector.request.clear()
        self.server.deadlock_detector.processes.clear()
        self.deadlock_display.delete("1.0", "end")
        self.deadlock_display.insert("1.0",
            "✅ Deadlock resolved!\nAll resource allocations cleared. System is safe.")
        self.add_log("✅ Deadlock resolved and cleared.")
        self.toast.show("✅ Deadlock resolved", type="success")

    # =================================================================
    # تبويب الإحصائيات
    # =================================================================
    def _build_statistics_tab(self):
        frame = self.tabview.tab("📈 Statistics")
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure(1, weight=1)

        self.stats_text = ctk.CTkTextbox(
            frame, height=180, fg_color="#0d1117",
            font=("Consolas", 12), border_width=1, border_color="#30363d",
            corner_radius=10
        )
        self.stats_text.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        if MATPLOTLIB_AVAILABLE:
            fig_frame = ctk.CTkFrame(frame, fg_color="#161b22", corner_radius=12,
                                      border_width=1, border_color="#30363d")
            fig_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=8, sticky="nsew")
            self.fig_stats = Figure(figsize=(11, 4), dpi=90, facecolor="#161b22")
            self.ax_resp = self.fig_stats.add_subplot(121)
            self.ax_through = self.fig_stats.add_subplot(122)
            for ax in [self.ax_resp, self.ax_through]:
                ax.set_facecolor("#0d1117")
                ax.tick_params(colors="#8b949e")
                ax.spines[:].set_color("#30363d")
                ax.grid(alpha=0.15, color="#30363d")
            self.ax_resp.set_title("Response Times (ms)", color="#8b949e", fontsize=11)
            self.ax_through.set_title("Throughput (req/s)", color="#8b949e", fontsize=11)
            self.canvas_stats = FigureCanvasTkAgg(self.fig_stats, master=fig_frame)
            self.canvas_stats.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    # =================================================================
    # تبويب البث المباشر - معدل لاستخدام النسخة المحسنة
    # =================================================================
    def _build_live_view_tab(self):
        frame = self.tabview.tab("🎬 Live View")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # رأس البث المباشر
        header = ctk.CTkFrame(frame, fg_color="#161b22", corner_radius=10,
                               border_width=1, border_color="#30363d")
        header.grid(row=0, column=0, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(header, text="🎬 Real-Time Game Battle Arena",
                     font=("Arial", 18, "bold"), text_color="#00ff88").pack(side="left", padx=20, pady=12)
        ctk.CTkLabel(header,
                     text="Players move autonomously • Bullets fire automatically • Eliminated players leave the server",
                     font=("Arial", 11), text_color="#8b949e").pack(side="left", padx=5)

        hint = ctk.CTkLabel(header,
                             text="🟢 Start server → Add players → Watch the action!",
                             font=("Arial", 11, "bold"), text_color="#d29922")
        hint.pack(side="right", padx=20)

        # كانفاس اللعبة
        game_frame = ctk.CTkFrame(frame, fg_color="#0d1117", corner_radius=12,
                                   border_width=1, border_color="#30363d")
        game_frame.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")

        # اختيار النسخة المناسبة من البث المباشر
        if LIVE_ENHANCED_AVAILABLE:
            self.live_game = LiveGameCanvasEnhanced(game_frame, self.server)
        else:
            self.live_game = LiveGameCanvas(game_frame, self.server)
        self.live_game.start()

    # =================================================================
    # تبويب السجلات
    # =================================================================
    def _build_logs_tab(self):
        frame = self.tabview.tab("📝 Logs")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(
            frame, fg_color="#0d1117", font=("Consolas", 11),
            border_width=1, border_color="#30363d", corner_radius=10,
            text_color="#c9d1d9"
        )
        self.log_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=1, column=0, pady=8, sticky="ew", padx=10)

        ctk.CTkButton(btn_frame, text="🗑️ Clear", command=self.clear_logs,
                      fg_color="#21262d", hover_color="#30363d",
                      width=90, height=34, font=("Arial", 11), corner_radius=8).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="💾 Export", command=self.export_logs,
                      fg_color="#0ea5e9", hover_color="#0284c7",
                      width=90, height=34, font=("Arial", 11), corner_radius=8).pack(side="left", padx=5)

        self.log_count_label = ctk.CTkLabel(btn_frame, text="0 entries",
                                             font=("Arial", 11), text_color="#8b949e")
        self.log_count_label.pack(side="right", padx=10)

        self._redirect_logging()
        self.log_count = 0

    # =================================================================
    # التحديثات الدورية
    # =================================================================
    def _start_periodic_updates(self):
        self._update_all()

    def _update_all(self):
        players = self.server.get_player_count()
        games = self.server.get_active_games_count()
        pending = self.server.get_pending_requests_count()
        perf = self.server.get_performance_stats()
        game_stats = self.server.get_game_stats()

        # تحديث الحالة
        status = "🟢 Running" if self.server.running else "🔴 Stopped"
        self.status_label.configure(
            text=f"{status}  |  Players: {players}  |  Games: {games}  |  Pending: {pending}"
        )

        # Quick KPIs
        success_rate = game_stats.get("matchmaking_success_rate", 0)
        self.quick_kpis["Players"].configure(text=str(players))
        self.quick_kpis["Games"].configure(text=str(games))
        self.quick_kpis["Pending"].configure(text=str(pending))
        self.quick_kpis["Throughput"].configure(text=f"{perf['throughput']:.1f}/s")

        # Dashboard KPIs
        self.dash_kpi["👥 Online Players"].configure(text=str(players))
        self.dash_kpi["🎮 Active Games"].configure(text=str(games))
        self.dash_kpi["✅ Success Rate"].configure(text=f"{success_rate:.0f}%")
        self.dash_kpi["⚡ Throughput"].configure(text=f"{perf['throughput']:.1f}/s")

        # موارد
        usage = self.server.get_resource_usage()
        for res_type, (pb, lbl, res_obj, color) in self.resource_bars.items():
            avail = res_obj.get_available()
            total = res_obj.total
            used_pct = (total - avail) / total if total > 0 else 0
            pb.set(used_pct)
            lbl.configure(text=f"{avail}/{total} ({int(used_pct*100)}% used)")

        # Resource compact bars (control tab)
        for res_type, (pb, lbl, res_obj) in self.res_compact_bars.items():
            avail = res_obj.get_available()
            total = res_obj.total
            used_pct = (total - avail) / total if total > 0 else 0
            pb.set(used_pct)
            lbl.configure(text=f"{int(used_pct*100)}%")

        # تحديثات كل 2 ثانية
        t = int(time.time())
        if t % 2 == 0:
            self._refresh_players_table()
            self._refresh_games_table()
            self._refresh_queue_display()

        if t % 3 == 0:
            self._update_stats_text()

        # الرسم البياني
        self._update_main_chart(players, games)
        self._update_resources_chart()

        self.update_id = self.root.after(1000, self._update_all)

    def _update_main_chart(self, players, games):
        if not MATPLOTLIB_AVAILABLE:
            return
        t = time.time()
        self.history_times.append(t)
        self.history_players.append(players)
        self.history_games.append(games)
        if len(self.history_times) > 60:
            self.history_times.pop(0)
            self.history_players.pop(0)
            self.history_games.pop(0)
        if len(self.history_times) > 1:
            self.ax_main.clear()
            self.ax_main.set_facecolor("#0d1117")
            base = self.history_times[0]
            times = [x - base for x in self.history_times]
            self.ax_main.fill_between(times, self.history_players,
                                       alpha=0.15, color="#0ea5e9")
            self.ax_main.plot(times, self.history_players, label="Players",
                               color="#0ea5e9", linewidth=2.5)
            self.ax_main.fill_between(times, self.history_games,
                                       alpha=0.15, color="#d29922")
            self.ax_main.plot(times, self.history_games, label="Games",
                               color="#d29922", linewidth=2.5)
            self.ax_main.legend(loc="upper left", facecolor="#161b22",
                                 labelcolor="#e6edf3", framealpha=0.8)
            self.ax_main.set_xlabel("Time (s)", color="#8b949e")
            self.ax_main.set_ylabel("Count", color="#8b949e")
            self.ax_main.tick_params(colors="#8b949e")
            self.ax_main.spines[:].set_color("#30363d")
            self.ax_main.grid(alpha=0.12, color="#30363d")
            self.canvas_main.draw()

    def _update_resources_chart(self):
        if not MATPLOTLIB_AVAILABLE:
            return
        colors = ["#0ea5e9", "#3fb950", "#d29922", "#7c3aed", "#f85149"]
        self.ax_res.clear()
        self.ax_res.set_facecolor("#0d1117")
        for idx, (res_type, res_obj) in enumerate(self.server.resources.items()):
            hist = list(res_obj.history)[-40:]
            if hist:
                times = [h[0] for h in hist]
                vals = [h[1] for h in hist]
                if times:
                    base = times[0]
                    self.ax_res.plot([t - base for t in times], vals,
                                     label=res_type.value[:6],
                                     color=colors[idx % len(colors)], linewidth=1.8)
        self.ax_res.legend(loc="upper right", facecolor="#161b22",
                           labelcolor="#e6edf3", fontsize=8, framealpha=0.8)
        self.ax_res.tick_params(colors="#8b949e")
        self.ax_res.spines[:].set_color("#30363d")
        self.ax_res.grid(alpha=0.12, color="#30363d")
        self.canvas_res.draw()

    def _update_stats_text(self):
        stats = self.server.get_performance_stats()
        game_stats = self.server.get_game_stats()
        txt = (
            f"📊 PERFORMANCE\n"
            f"  Avg Response Time : {stats['avg_response_time']*1000:.1f} ms\n"
            f"  Throughput        : {stats['throughput']:.2f} req/s\n"
            f"  Total Requests    : {stats['total_requests']}\n\n"
            f"🎮 MATCHMAKING\n"
            f"  Players Joined    : {game_stats['total_players_joined']}\n"
            f"  Players Left      : {game_stats['total_players_left']}\n"
            f"  Games Created     : {game_stats['total_games_created']}\n"
            f"  Games Finished    : {game_stats['total_games_finished']}\n"
            f"  MM Attempts       : {game_stats['matchmaking_attempts']}\n"
            f"  MM Success        : {game_stats['matchmaking_success']}\n"
            f"  MM Success Rate   : {game_stats['matchmaking_success_rate']:.1f}%"
        )
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("1.0", txt)

        if MATPLOTLIB_AVAILABLE and len(stats['response_times']) > 1:
            self.ax_resp.clear()
            self.ax_resp.set_facecolor("#0d1117")
            rt = [v * 1000 for v in stats['response_times'][-50:]]
            self.ax_resp.fill_between(range(len(rt)), rt, alpha=0.2, color="#0ea5e9")
            self.ax_resp.plot(rt, color="#0ea5e9", linewidth=1.8)
            self.ax_resp.set_title("Response Times (ms)", color="#8b949e")
            self.ax_resp.tick_params(colors="#8b949e")
            self.ax_resp.spines[:].set_color("#30363d")
            self.ax_resp.grid(alpha=0.12, color="#30363d")

            self.ax_through.clear()
            self.ax_through.set_facecolor("#0d1117")
            tp = stats['throughput']
            bars = self.ax_through.bar(["Current"], [tp], color="#3fb950", width=0.3)
            self.ax_through.set_title("Throughput (req/s)", color="#8b949e")
            self.ax_through.set_ylim(0, max(tp * 1.5, 1))
            self.ax_through.tick_params(colors="#8b949e")
            self.ax_through.spines[:].set_color("#30363d")
            self.ax_through.grid(alpha=0.12, color="#30363d", axis="y")
            self.canvas_stats.draw()

    # =================================================================
    # دوال التحكم
    # =================================================================
    def add_manual_players(self):
        if not self._has_permission("add_player"):
            self.toast.show("⛔ No permission", type="error")
            return
        if not self.server.running:
            self.toast.show("⚠️ Start the server first!", type="warning")
            return
        count = int(self.manual_count_slider.get())
        behavior = self.behavior_option.get()
        for _ in range(count):
            self.client_manager.add_client(behavior)
        self.add_log(f"➕ Added {count} player(s) (behavior: {behavior})")
        self.toast.show(f"✅ Added {count} player(s)", type="success", duration=2)
        self.root.after(800, self._log_games_created)

    def _log_games_created(self):
        games = self.server.get_active_games_count()
        if games > 0:
            self.add_log(f"🏠 {games} active game room(s) on server")

    def run_race_no_lock(self):
        self._run_race(use_lock=False)

    def run_race_with_lock(self):
        self._run_race(use_lock=True)

    def run_race_simulation(self):
        use_lock = self.race_lock_switch.get() == 1
        self._run_race(use_lock=use_lock)

    def _run_race(self, use_lock: bool):
        if not self._has_permission("all") and not self._has_permission("add_player"):
            self.toast.show("⛔ No permission", type="error")
            return
        if not self.server.running:
            self.toast.show("⚠️ Start the server first!", type="warning")
            return
        
        def task():
            # اختيار عدد عشوائي حسب الحالة
            if use_lock:
                count = random.randint(2, 10)   # مع القفل: عدد قليل (2-10)
                mode = "🔒 WITH Lock"
            else:
                count = random.randint(10, 20)  # بدون قفل: عدد كبير (10-20)
                mode = "⚡ WITHOUT Lock"
            
            self.add_log(f"🏃 Race Simulation {mode} — adding {count} players randomly")
            self.toast.show(f"🏃 Running race simulation ({count} players)...", type="info", duration=2)
            
            # استدعاء المحاكاة في السيرفر
            result = self.server.simulate_batch_join(count, use_lock=use_lock)
            
            # تسجيل النتائج المفصلة
            self.add_log(f"📊 Players added: {count}")
            self.add_log(f"🎮 Games created: {result['games_created']}")
            
            # تسجيل اللاعبين المطرودين (killed) والذين بقوا (life)
            killed = result.get('killed_players', [])
            active = result.get('active_players', [])
            
            if killed:
                self.add_log(f"💀 Killed players: {', '.join(map(str, killed))}")
            else:
                self.add_log(f"💀 Killed players: None")
            
            if active:
                self.add_log(f"✅ Alive players: {', '.join(map(str, active))}")
            else:
                self.add_log(f"✅ Alive players: None")
            
            if result['lost_players'] > 0:
                self.add_log(f"❌ Lost {result['lost_players']} players due to race condition!")
            else:
                self.add_log(f"✅ All players assigned correctly (with lock)")
            
            # عرض رسالة للمستخدم
            msg = f"Race done: {result['games_created']} games, {result['lost_players']} lost"
            if result['lost_players'] > 0:
                self.toast.show(f"⚠️ Race condition: {result['lost_players']} players lost!", type="warning", duration=3)
            else:
                self.toast.show(f"✅ Safe: {result['games_created']} games created", type="success", duration=3)
            
            # تحديث الواجهة لعرض النتائج
            self.root.after(0, self._refresh_players_table)
            self.root.after(0, self._refresh_games_table)
            
        threading.Thread(target=task, daemon=True).start()

    def _auto_race_loop(self):
        """حلقة المحاكاة التلقائية للتضارب"""
        while self.auto_race_running and self.server.running:
            # اختيار عشوائي بين use_lock True/False
            use_lock = random.choice([True, False])
            # اختيار عدد عشوائي حسب الحالة
            if use_lock:
                count = random.randint(2, 10)
                mode = "🔒 WITH Lock (Auto)"
            else:
                count = random.randint(10, 20)
                mode = "⚡ WITHOUT Lock (Auto)"
            
            self.add_log(f"🏃 Auto Race {mode} — adding {count} players")
            
            # تنفيذ المحاكاة
            result = self.server.simulate_batch_join(count, use_lock=use_lock)
            
            # تسجيل النتائج
            self.add_log(f"📊 Auto Race: {count} players added, {result['games_created']} games created")
            killed = result.get('killed_players', [])
            active = result.get('active_players', [])
            if killed:
                self.add_log(f"💀 Killed: {', '.join(map(str, killed))}")
            if active:
                self.add_log(f"✅ Alive: {', '.join(map(str, active))}")
            if result['lost_players'] > 0:
                self.add_log(f"❌ Lost {result['lost_players']} players")
            
            # انتظار قبل التكرار (بين 5 و 10 ثواني)
            time.sleep(random.uniform(5, 10))

    def start_server(self):
        if not self._has_permission("all"):
            self.toast.show("⛔ Admin only", type="error")
            return
        if not self.server.running:
            self.server.start()
            self.status_label.configure(text="🟢 Status: Running")
            self.fab_start.configure(text="⏹", fg_color="#f85149")
            self.add_log("🚀 Server started.")
            self.toast.show("🚀 Server started", type="success")

    def stop_server(self):
        if not self._has_permission("all"):
            self.toast.show("⛔ Admin only", type="error")
            return
        if self.server.running:
            self.server.stop()
            self.client_manager.stop_all()
            self.status_label.configure(text="🔴 Status: Stopped")
            self.fab_start.configure(text="▶", fg_color="#3fb950")
            self.add_log("⏹ Server stopped.")
            self.toast.show("⏹ Server stopped", type="warning")

    def reset_server(self):
        if not self._has_permission("all"):
            self.toast.show("⛔ Admin only", type="error")
            return
        self.stop_server()
        self.server.reset()
        self.client_manager = ClientManager(self.server)
        self.history_times.clear()
        self.history_players.clear()
        self.history_games.clear()
        if self.live_game:
            with self.live_game.lock:
                self.live_game.players.clear()
                self.live_game.bullets.clear()
        self.add_log("🔄 Server reset.")

    def detect_deadlock(self):
        deadlocked = self.server.deadlock_detector.detect_deadlock()
        self.deadlock_display.delete("1.0", "end")
        if deadlocked:
            msg = (f"⚠️ DEADLOCK DETECTED!\n\n"
                   f"Involved Processes: {deadlocked}\n\n"
                   f"Algorithm: DFS Cycle Detection\n"
                   f"Status: Cycle found in Resource Allocation Graph\n\n"
                   f"Recommended Action: Click 'Resolve & Clear' to release resources")
            self.deadlock_display.insert("1.0", msg)
            self.add_log(f"⚠️ Deadlock detected: {deadlocked}")
            self.toast.show("⚠️ Deadlock detected!", type="error")
        else:
            self.deadlock_display.insert("1.0",
                "✅ NO DEADLOCK DETECTED\n\n"
                "System is in a safe state.\n"
                "No cycles found in the Resource Allocation Graph.")
            self.toast.show("✅ System safe — no deadlock", type="success")

    def simulate_deadlock(self):
        from game_server_core import ResourceType
        self.server.deadlock_detector.update_allocation(1, ResourceType.CPU_CORE)
        self.server.deadlock_detector.update_allocation(2, ResourceType.MEMORY_SLOT)
        self.server.deadlock_detector.update_request(1, ResourceType.MEMORY_SLOT)
        self.server.deadlock_detector.update_request(2, ResourceType.CPU_CORE)
        self.deadlock_display.delete("1.0", "end")
        self.deadlock_display.insert("1.0",
            "⚠️ DEADLOCK SIMULATED\n\n"
            "Scenario Created:\n"
            "  Process 1: HOLDS CPU_CORE → WAITING for MEMORY_SLOT\n"
            "  Process 2: HOLDS MEMORY_SLOT → WAITING for CPU_CORE\n\n"
            "This is a classic circular wait (Condition 4 of Deadlock).\n\n"
            "Click 'Detect Deadlock Now' to run DFS detection algorithm.")
        self.add_log("⚠️ Deadlock scenario simulated.")
        self.toast.show("⚠️ Deadlock simulated — click Detect", type="warning")

    # =================================================================
    # السجلات
    # =================================================================
    def _redirect_logging(self):
        import logging
        class TextHandler(logging.Handler):
            def __init__(self, gui):
                super().__init__()
                self.gui = gui
            def emit(self, record):
                self.gui.add_log(self.format(record))
        handler = TextHandler(self)
        handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def add_log(self, message: str):
        def _update():
            ts = datetime.now().strftime('%H:%M:%S')
            self.log_text.insert("end", f"[{ts}] {message}\n")
            self.log_text.see("end")
            self.log_count += 1
            try:
                self.log_count_label.configure(text=f"{self.log_count} entries")
            except Exception:
                pass
        self.root.after(0, _update)

    def clear_logs(self):
        self.log_text.delete("1.0", "end")
        self.log_count = 0
        self.log_count_label.configure(text="0 entries")
        self.add_log("🗑️ Logs cleared.")

    def export_logs(self):
        from tkinter import filedialog
        fn = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"server_logs_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if fn:
            with open(fn, "w", encoding="utf-8") as f:
                f.write(self.log_text.get("1.0", "end"))
            self.add_log(f"💾 Exported → {fn}")
            self.toast.show("💾 Logs exported", type="success")

    # =================================================================
    # الساعة والإغلاق
    # =================================================================
    def _update_clock(self):
        self.clock_label.configure(text=datetime.now().strftime("⏰ %H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def on_closing(self):
        if self.live_game:
            self.live_game.stop()
        if self.server.running:
            self.server.stop()
            self.client_manager.stop_all()
        if self.update_id:
            self.root.after_cancel(self.update_id)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ===================================================================
# نقطة الدخول
# ===================================================================
def main():
    def on_login(user_data, username):
        app = GameServerGUI(user_data, username)
        app.add_log(f"🔐 Logged in as: {user_data['display_name']} ({user_data['role']})")
        app.toast.show(f"Welcome, {user_data['display_name']}! 👋", type="success", duration=3)
        app.run()

    login = LoginScreen(on_login_success=on_login)
    login.run()

     
if __name__ == "__main__":
    main()