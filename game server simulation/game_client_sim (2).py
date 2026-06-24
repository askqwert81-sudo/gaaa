"""
game_client_sim.py - محاكاة سلوك اللاعبين (عميل)
يدير أنواع اللاعبين المختلفة ويحاكي طلباتهم.
"""

import threading
import random
import time
import logging

logger = logging.getLogger("GameClient")

class GameClient:
    """يمثل لاعباً بسلوك معين (normal, aggressive, casual, afk)."""
    def __init__(self, client_id: int, behavior: str, server_core):
        self.client_id = client_id
        self.behavior = behavior  # normal, aggressive, casual, afk
        self.server = server_core
        self.active = True
        self.thread = None
        self.stop_event = threading.Event()

    def start(self):
        """بدء محاكاة سلوك اللاعب."""
        self.active = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.active = False
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)

    def _run(self):
        """الحلقة الرئيسية للاعب: يقوم بإجراءات عشوائية حسب السلوك."""
        # إضافة اللاعب إلى السيرفر
        self.server.add_player(self.client_id, f"{self.behavior}_{self.client_id}")
        
        while not self.stop_event.is_set() and self.active:
            # تحديد زمن الانتظار بين الإجراءات حسب السلوك
            if self.behavior == "aggressive":
                wait = random.uniform(8, 18)
                action_prob = 0.8
            elif self.behavior == "casual":
                wait = random.uniform(20, 45)
                action_prob = 0.3
            elif self.behavior == "afk":
                wait = random.uniform(60, 180)
                action_prob = 0.05
            else:  # normal
                wait = random.uniform(12, 30)
                action_prob = 0.6

            time.sleep(wait)
            if not self.active:
                break

            # تنفيذ إجراء عشوائي: مغادرة السيرفر أو طلب إعادة الماتشميكينغ
            if random.random() < action_prob:
                # احتمال المغادرة
                if random.random() < 0.2:
                    self.server.remove_player(self.client_id)
                    logger.info(f"Client {self.client_id} left the server.")
                    break  # انهاء هذا العميل
                else:
                    # طلب إعادة matchmaking (يضاف إلى قائمة الانتظار)
                    # يمكن إرسال طلب مباشر عبر وضع لاعب جديد؟ لكنه موجود بالفعل.
                    # في هذا المحاكاة، اللاعب بعد خروجه لا يعود. لذا نكتفي.
                    pass
        # عند الخروج، نتأكد من إزالة اللاعب
        self.server.remove_player(self.client_id)

class ClientManager:
    """يدير مجموعة من عملاء اللاعبين."""
    def __init__(self, server_core):
        self.server = server_core
        self.clients: dict[int, GameClient] = {}
        self.lock = threading.Lock()

    def add_client(self, behavior: str) -> int:
        """إضافة عميل جديد بسلوك معين، ويعيد معرف العميل."""
        with self.lock:
            new_id = len(self.clients) + 1
            client = GameClient(new_id, behavior, self.server)
            self.clients[new_id] = client
            client.start()
            return new_id

    def remove_client(self, client_id: int):
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id].stop()
                del self.clients[client_id]

    def get_client_count(self) -> int:
        with self.lock:
            return len(self.clients)

    def stop_all(self):
        with self.lock:
            for client in self.clients.values():
                client.stop()
            self.clients.clear()