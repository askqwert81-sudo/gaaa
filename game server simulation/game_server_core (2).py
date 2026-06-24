"""
game_server_core.py - النواة الموسعة مع استخدام Semaphores و Mutexes
تم التعديل: إضافة لاعبين فعليين في simulate_batch_join، مع إمكانية استخدام قفل أو دونه.
تمت إضافة: إحصائيات مفصلة عن حالة التضارب، وتسجيل اللاعبين المطرودين والناجين.
"""

import threading
import time
import random
import queue
from collections import deque
from enum import Enum
from typing import Dict, List, Set, Optional, Tuple, Any
import logging

logger = logging.getLogger("GameServer")

class ResourceType(Enum):
    CPU_CORE = "CPU Core"
    MEMORY_SLOT = "Memory Slot"
    NETWORK_BANDWIDTH = "Network Bandwidth"
    DB_CONNECTION = "Database Connection"
    GAME_INSTANCE = "Game Instance"

class GameResource:
    """
    مورد مع حماية باستخدام Semaphore للحد من التزامن و Lock لتحديث الحالة.
    """
    def __init__(self, res_type: ResourceType, total_units: int):
        self.type = res_type
        self.total = total_units
        self.available = total_units
        self.lock = threading.Lock()
        self.semaphore = threading.Semaphore(total_units)
        self.history = deque(maxlen=100)

    def acquire(self, units: int = 1, timeout: float = None) -> bool:
        for _ in range(units):
            if not self.semaphore.acquire(blocking=True, timeout=timeout):
                for _ in range(_):
                    self.semaphore.release()
                return False
        with self.lock:
            self.available -= units
            self._record()
        return True

    def release(self, units: int = 1):
        with self.lock:
            self.available += units
            self._record()
        for _ in range(units):
            self.semaphore.release()

    def _record(self):
        self.history.append((time.time(), self.available))

    def get_usage(self) -> float:
        with self.lock:
            return (self.total - self.available) / self.total if self.total > 0 else 0

    def get_available(self) -> int:
        with self.lock:
            return self.available

class GameSession:
    _id_counter = 0
    _id_lock = threading.Lock()
    MAX_PLAYERS = 4

    def __init__(self, game_name: str, players: List[int] = None):
        with GameSession._id_lock:
            GameSession._id_counter += 1
            self.game_id = GameSession._id_counter
        self.game_name = game_name
        self.players = players[:] if players else []
        self.start_time = time.time()
        self.status = "active"
        self.resources_held = {}

    def add_player(self, player_id: int) -> bool:
        if len(self.players) >= GameSession.MAX_PLAYERS:
            return False
        if player_id in self.players:
            return False
        self.players.append(player_id)
        return True

    def remove_player(self, player_id: int):
        if player_id in self.players:
            self.players.remove(player_id)

    def is_full(self) -> bool:
        return len(self.players) >= GameSession.MAX_PLAYERS

    def duration(self) -> float:
        return time.time() - self.start_time

class DeadlockDetector:
    def __init__(self):
        self.lock = threading.Lock()
        self.allocation = {}
        self.request = {}
        self.processes = set()

    def update_allocation(self, process_id: int, resource_type: ResourceType):
        with self.lock:
            self.allocation[process_id] = resource_type
            self.processes.add(process_id)

    def update_request(self, process_id: int, resource_type: ResourceType):
        with self.lock:
            self.request[process_id] = resource_type
            self.processes.add(process_id)

    def release_allocation(self, process_id: int):
        with self.lock:
            if process_id in self.allocation:
                del self.allocation[process_id]

    def detect_deadlock(self) -> List[int]:
        with self.lock:
            graph = {p: set() for p in self.processes}
            for p, res in self.request.items():
                for owner, owned_res in self.allocation.items():
                    if owned_res == res and owner != p:
                        graph[p].add(owner)
            visited = set()
            rec_stack = set()
            deadlocked = []

            def dfs(node):
                visited.add(node)
                rec_stack.add(node)
                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        return True
                rec_stack.remove(node)
                return False

            for p in list(self.processes):
                if p not in visited:
                    if dfs(p):
                        deadlocked.append(p)
            return deadlocked

class PriorityScheduler:
    def __init__(self):
        self.lock = threading.Lock()
        self.queues = {prio: deque() for prio in range(11)}

    def add_request(self, request, priority: int):
        with self.lock:
            priority = max(0, min(10, priority))
            self.queues[priority].append(request)

    def get_next_request(self):
        with self.lock:
            for prio in range(11):
                if self.queues[prio]:
                    return self.queues[prio].popleft()
        return None

    def size(self) -> int:
        with self.lock:
            return sum(len(q) for q in self.queues.values())

    def get_queue_sizes(self) -> Dict[int, int]:
        with self.lock:
            return {prio: len(q) for prio, q in self.queues.items()}

class PerformanceMonitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.response_times = deque(maxlen=1000)
        self.requests_processed = 0
        self.start_time = time.time()

    def record_response(self, response_time: float):
        with self.lock:
            self.response_times.append(response_time)
            self.requests_processed += 1

    def get_avg_response_time(self) -> float:
        with self.lock:
            if not self.response_times:
                return 0.0
            return sum(self.response_times) / len(self.response_times)

    def get_throughput(self) -> float:
        with self.lock:
            elapsed = time.time() - self.start_time
            if elapsed == 0:
                return 0
            return self.requests_processed / elapsed

    def get_response_times_list(self) -> List[float]:
        with self.lock:
            return list(self.response_times)

    def reset(self):
        with self.lock:
            self.response_times.clear()
            self.requests_processed = 0
            self.start_time = time.time()

class GameServerCore:
    def __init__(self):
        # الموارد مع Semaphores
        self.resources = {
            ResourceType.CPU_CORE: GameResource(ResourceType.CPU_CORE, 8),
            ResourceType.MEMORY_SLOT: GameResource(ResourceType.MEMORY_SLOT, 16),
            ResourceType.NETWORK_BANDWIDTH: GameResource(ResourceType.NETWORK_BANDWIDTH, 100),
            ResourceType.DB_CONNECTION: GameResource(ResourceType.DB_CONNECTION, 10),
            ResourceType.GAME_INSTANCE: GameResource(ResourceType.GAME_INSTANCE, 20),
        }
        
        self.processing_semaphore = threading.Semaphore(5)
        
        self.players: Dict[int, Dict] = {}
        self.games: Dict[int, GameSession] = {}
        self.player_game_map: Dict[int, int] = {}
        self.pending_requests = PriorityScheduler()
        self.deadlock_detector = DeadlockDetector()
        self.performance_monitor = PerformanceMonitor()
        
        self.players_lock = threading.RLock()
        self.games_lock = threading.RLock()
        self.map_lock = threading.RLock()
        self.stats_lock = threading.Lock()
        
        self.running = False
        self.stop_event = threading.Event()
        self.matchmaking_queue = queue.Queue(maxsize=100)
        self.consumer_threads = []
        self.deadlock_monitor_thread = None

        # إحصائيات عامة
        self.total_players_joined = 0
        self.total_players_left = 0
        self.total_games_created = 0
        self.total_games_finished = 0
        self.matchmaking_attempts = 0
        self.matchmaking_success = 0

        # متغيرات محاكاة التضارب - مع تفاصيل إضافية للتسجيل
        self.race_lock = threading.Lock()
        self.race_active_players = []
        self.race_killed_players = []   # المطرودين بسبب التضارب
        self.race_lost_players = 0
        self.race_games_created = 0
        self.race_expected_games = 0
        self.race_total_added = 0

    def start(self):
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        for _ in range(3):
            t = threading.Thread(target=self._consumer_worker, daemon=True)
            t.start()
            self.consumer_threads.append(t)
        self.deadlock_monitor_thread = threading.Thread(target=self._deadlock_monitor, daemon=True)
        self.deadlock_monitor_thread.start()
        logger.info("Game server started.")

    def stop(self):
        self.running = False
        self.stop_event.set()
        with self.players_lock:
            self.players.clear()
        with self.games_lock:
            self.games.clear()
        with self.map_lock:
            self.player_game_map.clear()
        self.pending_requests = PriorityScheduler()
        self.performance_monitor.reset()
        for res in self.resources.values():
            held = res.total - res.available
            for _ in range(held):
                res.semaphore.release()
            with res.lock:
                res.available = res.total
                res.history.clear()
        logger.info("Game server stopped.")

    def reset(self):
        self.stop()
        with self.stats_lock:
            self.total_players_joined = 0
            self.total_players_left = 0
            self.total_games_created = 0
            self.total_games_finished = 0
            self.matchmaking_attempts = 0
            self.matchmaking_success = 0
        # إعادة تعيين متغيرات السباق
        with self.race_lock:
            self.race_active_players = []
            self.race_killed_players = []
            self.race_lost_players = 0
            self.race_games_created = 0
            self.race_expected_games = 0
            self.race_total_added = 0
        self.start()

    def add_player(self, player_id: int, name: str = None, behavior: str = 'normal') -> bool:
        with self.players_lock:
            if player_id in self.players:
                return False
            self.players[player_id] = {
                'name': name or f"Player_{player_id}",
                'status': 'idle',
                'join_time': time.time(),
                'behavior': behavior
            }
            with self.stats_lock:
                self.total_players_joined += 1
        try:
            self.matchmaking_queue.put(('matchmake', player_id), block=False)
        except queue.Full:
            logger.warning(f"Matchmaking queue full, player {player_id} will be retried later")
            return False
        return True

    def remove_player(self, player_id: int) -> bool:
        with self.players_lock:
            if player_id not in self.players:
                return False
            del self.players[player_id]
            with self.stats_lock:
                self.total_players_left += 1
        with self.map_lock:
            game_id = self.player_game_map.get(player_id)
            if game_id:
                with self.games_lock:
                    if game_id in self.games:
                        game = self.games[game_id]
                        game.remove_player(player_id)
                        if len(game.players) == 0:
                            for res_type, units in game.resources_held.items():
                                if res_type in self.resources:
                                    self.resources[res_type].release(units)
                            del self.games[game_id]
                            with self.stats_lock:
                                self.total_games_finished += 1
                del self.player_game_map[player_id]
        return True

    def get_player_count(self) -> int:
        with self.players_lock:
            return len(self.players)

    def get_active_games_count(self) -> int:
        with self.games_lock:
            return len(self.games)

    def get_all_players(self) -> Dict[int, Dict]:
        with self.players_lock:
            return self.players.copy()

    def get_all_games(self) -> Dict[int, GameSession]:
        with self.games_lock:
            return self.games.copy()

    def get_player_game(self, player_id: int) -> Optional[int]:
        with self.map_lock:
            return self.player_game_map.get(player_id)

    def _consumer_worker(self):
        while not self.stop_event.is_set():
            try:
                item = self.matchmaking_queue.get(timeout=1)
                if item[0] == 'matchmake':
                    player_id = item[1]
                    if not self.processing_semaphore.acquire(blocking=False):
                        self.matchmaking_queue.put(item)
                        time.sleep(0.1)
                        continue
                    try:
                        self._process_matchmaking(player_id)
                    finally:
                        self.processing_semaphore.release()
                self.matchmaking_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Consumer error: {e}")

    def _process_matchmaking(self, player_id: int):
        with self.players_lock:
            if player_id not in self.players:
                return
        with self.map_lock:
            if player_id in self.player_game_map:
                return
        with self.stats_lock:
            self.matchmaking_attempts += 1

        target_game = None
        with self.games_lock:
            for game in self.games.values():
                if len(game.players) < GameSession.MAX_PLAYERS and game.status == "active":
                    target_game = game
                    break

        cpu_needed = 1
        mem_needed = 2
        net_needed = 5
        db_needed = 1
        game_instance_needed = 1 if target_game is None else 0

        acquired_resources = []
        try:
            if game_instance_needed:
                if not self.resources[ResourceType.GAME_INSTANCE].acquire(game_instance_needed, timeout=2):
                    raise RuntimeError("Failed to acquire Game Instance")
                acquired_resources.append((ResourceType.GAME_INSTANCE, game_instance_needed))
            if not self.resources[ResourceType.CPU_CORE].acquire(cpu_needed, timeout=2):
                raise RuntimeError("Failed to acquire CPU")
            acquired_resources.append((ResourceType.CPU_CORE, cpu_needed))
            if not self.resources[ResourceType.MEMORY_SLOT].acquire(mem_needed, timeout=2):
                raise RuntimeError("Failed to acquire Memory")
            acquired_resources.append((ResourceType.MEMORY_SLOT, mem_needed))
            if not self.resources[ResourceType.NETWORK_BANDWIDTH].acquire(net_needed, timeout=2):
                raise RuntimeError("Failed to acquire Network")
            acquired_resources.append((ResourceType.NETWORK_BANDWIDTH, net_needed))
            if not self.resources[ResourceType.DB_CONNECTION].acquire(db_needed, timeout=2):
                raise RuntimeError("Failed to acquire DB Connection")
            acquired_resources.append((ResourceType.DB_CONNECTION, db_needed))

        except RuntimeError as e:
            for res_type, units in acquired_resources:
                self.resources[res_type].release(units)
            self.pending_requests.add_request((player_id,), priority=5)
            logger.warning(f"Matchmaking for player {player_id} failed: {e}")
            return

        with self.games_lock:
            if target_game:
                if target_game.add_player(player_id):
                    with self.map_lock:
                        self.player_game_map[player_id] = target_game.game_id
                    for res_type, units in acquired_resources:
                        target_game.resources_held[res_type] = target_game.resources_held.get(res_type, 0) + units
                    self.performance_monitor.record_response(random.uniform(0.1, 0.5))
                    with self.stats_lock:
                        self.matchmaking_success += 1
                else:
                    for res_type, units in acquired_resources:
                        self.resources[res_type].release(units)
                    self.pending_requests.add_request((player_id,), priority=3)
            else:
                new_game = GameSession(f"Game_{len(self.games)+1}", [player_id])
                for res_type, units in acquired_resources:
                    new_game.resources_held[res_type] = new_game.resources_held.get(res_type, 0) + units
                self.games[new_game.game_id] = new_game
                with self.map_lock:
                    self.player_game_map[player_id] = new_game.game_id
                with self.stats_lock:
                    self.total_games_created += 1
                    self.matchmaking_success += 1
                self.performance_monitor.record_response(random.uniform(0.5, 1.0))
                logger.info(f"New game {new_game.game_id} created for player {player_id}")

    def _deadlock_monitor(self):
        while not self.stop_event.is_set():
            deadlocked = self.deadlock_detector.detect_deadlock()
            if deadlocked:
                logger.warning(f"Deadlock detected: {deadlocked}")
                with self.games_lock:
                    for pid in deadlocked:
                        for game in list(self.games.values()):
                            if pid in game.players:
                                for res_type, units in game.resources_held.items():
                                    if res_type in self.resources:
                                        self.resources[res_type].release(units)
                                game.status = "finished"
                                for player in game.players:
                                    with self.map_lock:
                                        if player in self.player_game_map:
                                            del self.player_game_map[player]
                                del self.games[game.game_id]
                                with self.stats_lock:
                                    self.total_games_finished += 1
                                break
            time.sleep(3)

    # ===================== محاكاة التضارب مع وبدون قفل =====================

    def simulate_batch_join(self, count: int, use_lock: bool) -> Dict:
        """
        محاكاة إضافة لاعبين مع أو بدون مزامنة.
        use_lock=True: استخدام قفل (Mutex) لمزامنة آمنة.
        use_lock=False: بدون قفل (Race Condition) - يضيف لاعبين بسرعة عالية بدون مزامنة.
        هذه الدالة تضيف لاعبين فعليين إلى السيرفر ثم تعيد النتائج مع تفاصيل إضافية للتسجيل.
        """
        with self.players_lock:
            existing_ids = set(self.players.keys())
        start_count = len(existing_ids)
        
        new_player_ids = list(range(start_count + 1, start_count + count + 1))
        
        # إعادة تعيين متغيرات السباق
        with self.race_lock:
            self.race_active_players = []
            self.race_killed_players = []
            self.race_lost_players = 0
            self.race_games_created = 0
            self.race_total_added = count
            self.race_expected_games = (start_count + count) // 4
            if (start_count + count) % 4 > 0:
                self.race_expected_games += 1

        if use_lock:
            with self.race_lock:  # نستخدم قفل خاص لمزامنة الإضافة
                for pid in new_player_ids:
                    self.add_player(pid, f"Race_{pid}", behavior='race_locked')
                    time.sleep(0.01)
        else:
            # بدون قفل: نضيفهم في خيوط متعددة بدون مزامنة
            threads = []
            def add_without_lock(pid):
                time.sleep(random.uniform(0.001, 0.005))
                self.add_player(pid, f"Race_{pid}", behavior='race_unlocked')
            
            for pid in new_player_ids:
                t = threading.Thread(target=add_without_lock, args=(pid,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        
        # ننتظر حتى تتم معالجة جميع اللاعبين
        time.sleep(1.5)
        
        # نحسب النتائج
        with self.games_lock:
            games_created = len(self.games)
        with self.players_lock:
            players_now = len(self.players)
        
        added = count
        actual_added = players_now - start_count
        lost = added - actual_added

        # تحديث متغيرات السباق
        with self.race_lock:
            self.race_games_created = games_created
            self.race_lost_players = lost
            # تحديد اللاعبين الناجين والمطرودين
            with self.players_lock:
                current_players = set(self.players.keys())
            # اللاعبين المطرودين هم أولئك الذين لم يتمكنوا من الانضمام (محاكاة)
            # في هذه المحاكاة، نفترض أن المطرودين هم الذين لم يتم إضافتهم
            killed = list(set(new_player_ids) - current_players)
            self.race_killed_players = killed
            self.race_active_players = list(current_players.intersection(set(new_player_ids)))
        
        expected_games = (start_count + count) // 4
        if (start_count + count) % 4 > 0:
            expected_games += 1
        
        return {
            'total_players': count,
            'games_created': games_created,
            'lost_players': lost,
            'expected_games': expected_games,
            'players_in_last_game': (start_count + count) % 4,
            'active_players': self.race_active_players,
            'killed_players': self.race_killed_players
        }

    def generate_random_race(self, use_lock: bool) -> Dict:
        if use_lock:
            count = random.randint(2, 10)   # مع القفل: بين 2 و 10
        else:
            count = random.randint(10, 20)  # بدون قفل: بين 10 و 20
        result = self.simulate_batch_join(count, use_lock)
        result['random_count'] = count
        return result

    # دوال للحصول على تفاصيل السباق للتسجيل
    def get_race_details(self) -> Dict:
        with self.race_lock:
            return {
                'total_added': self.race_total_added,
                'games_created': self.race_games_created,
                'lost_players': self.race_lost_players,
                'expected_games': self.race_expected_games,
                'active_players': self.race_active_players,
                'killed_players': self.race_killed_players
            }

    # دوال الإحصائيات
    def get_resource_usage(self) -> Dict[str, float]:
        return {res.type.value: res.get_usage() for res in self.resources.values()}

    def get_resource_details(self) -> Dict[str, Dict]:
        return {
            res.type.value: {
                'total': res.total,
                'available': res.get_available(),
                'usage_percent': res.get_usage() * 100
            } for res in self.resources.values()
        }

    def get_performance_stats(self) -> dict:
        return {
            'avg_response_time': self.performance_monitor.get_avg_response_time(),
            'throughput': self.performance_monitor.get_throughput(),
            'total_requests': self.performance_monitor.requests_processed,
            'response_times': self.performance_monitor.get_response_times_list()
        }

    def get_pending_requests_count(self) -> int:
        return self.pending_requests.size()

    def get_queue_sizes(self) -> Dict[int, int]:
        return self.pending_requests.get_queue_sizes()

    def get_game_stats(self) -> dict:
        with self.stats_lock:
            return {
                'total_players_joined': self.total_players_joined,
                'total_players_left': self.total_players_left,
                'total_games_created': self.total_games_created,
                'total_games_finished': self.total_games_finished,
                'matchmaking_attempts': self.matchmaking_attempts,
                'matchmaking_success': self.matchmaking_success,
                'matchmaking_success_rate': (self.matchmaking_success / self.matchmaking_attempts * 100)
                                            if self.matchmaking_attempts > 0 else 0
            }