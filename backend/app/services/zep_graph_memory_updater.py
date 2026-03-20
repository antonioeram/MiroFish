"""
ZepGrafMemorieActualizareServiciu
将SimulareAgent活动动态ActualizarelaZepGraf
"""

import os
import time
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.zep_graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent活动Înregistrare"""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str
    
    def to_episode_text(self) -> str:
        """
        将活动转换为可以Trimite给Zep文本Descriere
        
        采用自然语言DescriereFormat，让Zep能够de la提取EntitateșiRelație
        不添加Simulare相关前缀，避免误导GrafActualizare
        """
        # 根据不同AcțiuneTipGenerare不同Descriere
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }
        
        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()
        
        # 直接Returnare "agentNume: 活动Descriere" Format，不添加Simulare前缀
        return f"{self.agent_name}: {description}"
    
    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"Publicare一条帖子：「{content}」"
        return "Publicare一条帖子"
    
    def _describe_like_post(self) -> str:
        """点赞帖子 - 包含帖子原文șiAutorInformații"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"点赞{post_author}帖子：「{post_content}」"
        elif post_content:
            return f"点赞一条帖子：「{post_content}」"
        elif post_author:
            return f"点赞{post_author}一条帖子"
        return "点赞一条帖子"
    
    def _describe_dislike_post(self) -> str:
        """踩帖子 - 包含帖子原文șiAutorInformații"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"踩{post_author}帖子：「{post_content}」"
        elif post_content:
            return f"踩一条帖子：「{post_content}」"
        elif post_author:
            return f"踩{post_author}一条帖子"
        return "踩一条帖子"
    
    def _describe_repost(self) -> str:
        """转发帖子 - 包含原帖ConținutșiAutorInformații"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        
        if original_content and original_author:
            return f"转发{original_author}帖子：「{original_content}」"
        elif original_content:
            return f"转发一条帖子：「{original_content}」"
        elif original_author:
            return f"转发{original_author}一条帖子"
        return "转发一条帖子"
    
    def _describe_quote_post(self) -> str:
        """引用帖子 - 包含原帖Conținut、AutorInformațiiși引用评论"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        
        base = ""
        if original_content and original_author:
            base = f"引用{original_author}帖子「{original_content}」"
        elif original_content:
            base = f"引用一条帖子「{original_content}」"
        elif original_author:
            base = f"引用{original_author}一条帖子"
        else:
            base = "引用一条帖子"
        
        if quote_content:
            base += f"，并评论道：「{quote_content}」"
        return base
    
    def _describe_follow(self) -> str:
        """关注Utilizator - 包含被关注UtilizatorNume"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"关注Utilizator「{target_user_name}」"
        return "关注一个Utilizator"
    
    def _describe_create_comment(self) -> str:
        """发表评论 - 包含评论Conținutși所评论帖子Informații"""
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if content:
            if post_content and post_author:
                return f"în{post_author}帖子「{post_content}」评论道：「{content}」"
            elif post_content:
                return f"în帖子「{post_content}」评论道：「{content}」"
            elif post_author:
                return f"în{post_author}帖子评论道：「{content}」"
            return f"评论道：「{content}」"
        return "发表评论"
    
    def _describe_like_comment(self) -> str:
        """点赞评论 - 包含评论ConținutșiAutorInformații"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"点赞{comment_author}评论：「{comment_content}」"
        elif comment_content:
            return f"点赞一条评论：「{comment_content}」"
        elif comment_author:
            return f"点赞{comment_author}一条评论"
        return "点赞一条评论"
    
    def _describe_dislike_comment(self) -> str:
        """踩评论 - 包含评论ConținutșiAutorInformații"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"踩{comment_author}评论：「{comment_content}」"
        elif comment_content:
            return f"踩一条评论：「{comment_content}」"
        elif comment_author:
            return f"踩{comment_author}一条评论"
        return "踩一条评论"
    
    def _describe_search(self) -> str:
        """搜索帖子 - 包含搜索关Cheie词"""
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"搜索「{query}」" if query else "进行搜索"
    
    def _describe_search_user(self) -> str:
        """搜索Utilizator - 包含搜索关Cheie词"""
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"搜索Utilizator「{query}」" if query else "搜索Utilizator"
    
    def _describe_mute(self) -> str:
        """屏蔽Utilizator - 包含被屏蔽UtilizatorNume"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"屏蔽Utilizator「{target_user_name}」"
        return "屏蔽一个Utilizator"
    
    def _describe_generic(self) -> str:
        # pentruNecunoscutAcțiuneTip，Generare通用Descriere
        return f"执行{self.action_type}操作"


class ZepGraphMemoryUpdater:
    """
    ZepGrafMemorieActualizare器
    
    监控SimulareactionsJurnalFișier，将新agent活动实时ActualizarelaZepGraf。
    按Platformă分组，每累积BATCH_SIZE条活动后În lotTrimitelaZep。
    
    所有有意义Comportament都会被ActualizarelaZep，action_args会包含Complet文Informații：
    - 点赞/踩帖子原文
    - 转发/引用帖子原文
    - 关注/屏蔽Utilizator名
    - 点赞/踩评论原文
    """
    
    # În lotTrimite大小（每个Platformă累积多少条后Trimite）
    BATCH_SIZE = 5
    
    # PlatformăNume映射（用于Consolă显示）
    PLATFORM_DISPLAY_NAMES = {
        'twitter': '世界1',
        'reddit': '世界2',
    }
    
    # Trimite间隔（秒），避免Cerere过快
    SEND_INTERVAL = 0.5
    
    # ReîncercareConfigurare
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # 秒
    
    def __init__(self, graph_id: str, api_key: Optional[str] = None):
        """
        InițializareActualizare器
        
        Args:
            graph_id: ZepGrafID
            api_key: Zep API Key（可选，Implicitde laConfigurare读取）
        """
        self.graph_id = graph_id
        self.api_key = api_key or Config.ZEP_API_KEY
        
        if not self.api_key:
            raise ValueError("ZEP_API_KEY未Configurare")
        
        self.client = Zep(api_key=self.api_key)
        
        # 活动队列
        self._activity_queue: Queue = Queue()
        
        # 按Platformă分组活动缓冲区（每个Platformă各自累积laBATCH_SIZE后În lotTrimite）
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()
        
        # 控制标志
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # 统计
        self._total_activities = 0  # 实际添加la队列活动数
        self._total_sent = 0        # SuccesTrimitelaZep批次数
        self._total_items_sent = 0  # SuccesTrimitelaZep活动条数
        self._failed_count = 0      # TrimiteEșec批次数
        self._skipped_count = 0     # 被过滤跳过活动数（DO_NOTHING）
        
        logger.info(f"ZepGraphMemoryUpdater InițializareFinalizare: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")
    
    def _get_platform_display_name(self, platform: str) -> str:
        """ObținerePlatformă显示Nume"""
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)
    
    def start(self):
        """启动后台工作线程"""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"ZepMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"ZepGraphMemoryUpdater 已启动: graph_id={self.graph_id}")
    
    def stop(self):
        """Oprire后台工作线程"""
        self._running = False
        
        # Trimite剩余活动
        self._flush_remaining()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        
        logger.info(f"ZepGraphMemoryUpdater 已Oprire: graph_id={self.graph_id}, "
                   f"total_activities={self._total_activities}, "
                   f"batches_sent={self._total_sent}, "
                   f"items_sent={self._total_items_sent}, "
                   f"failed={self._failed_count}, "
                   f"skipped={self._skipped_count}")
    
    def add_activity(self, activity: AgentActivity):
        """
        添加一个agent活动la队列
        
        所有有意义Comportament都会被添加la队列，包括：
        - CREATE_POST（发帖）
        - CREATE_COMMENT（评论）
        - QUOTE_POST（引用帖子）
        - SEARCH_POSTS（搜索帖子）
        - SEARCH_USER（搜索Utilizator）
        - LIKE_POST/DISLIKE_POST（点赞/踩帖子）
        - REPOST（转发）
        - FOLLOW（关注）
        - MUTE（屏蔽）
        - LIKE_COMMENT/DISLIKE_COMMENT（点赞/踩评论）
        
        action_args会包含Complet文Informații（如帖子原文、Utilizator名等）。
        
        Args:
            activity: Agent活动Înregistrare
        """
        # 跳过DO_NOTHINGTip活动
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        
        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"添加活动laZep队列: {activity.agent_name} - {activity.action_type}")
    
    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """
        de laDicționarDate添加活动
        
        Args:
            data: de laactions.jsonl解析DicționarDate
            platform: PlatformăNume (twitter/reddit)
        """
        # 跳过EvenimentTip条目
        if "event_type" in data:
            return
        
        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        
        self.add_activity(activity)
    
    def _worker_loop(self):
        """后台工作循环 - 按PlatformăÎn lotTrimite活动laZep"""
        while self._running or not self._activity_queue.empty():
            try:
                # 尝试de la队列Obținere活动（超时1秒）
                try:
                    activity = self._activity_queue.get(timeout=1)
                    
                    # 将活动添加la对应Platformă缓冲区
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)
                        
                        # Verificare该PlatformăDaNu达laÎn lot大小
                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            # 释放锁后再Trimite
                            self._send_batch_activities(batch, platform)
                            # Trimite间隔，避免Cerere过快
                            time.sleep(self.SEND_INTERVAL)
                    
                except Empty:
                    pass
                    
            except Exception as e:
                logger.error(f"工作循环Excepție: {e}")
                time.sleep(1)
    
    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """
        În lotTrimite活动laZepGraf（合并为一条文本）
        
        Args:
            activities: Agent活动Listă
            platform: PlatformăNume
        """
        if not activities:
            return
        
        # 将多条活动合并为一条文本，用换行分隔
        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)
        
        # 带ReîncercareTrimite
        for attempt in range(self.MAX_RETRIES):
            try:
                self.client.graph.add(
                    graph_id=self.graph_id,
                    type="text",
                    data=combined_text
                )
                
                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(f"SuccesÎn lotTrimite {len(activities)} 条{display_name}活动laGraf {self.graph_id}")
                logger.debug(f"În lotConținut预览: {combined_text[:200]}...")
                return
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"În lotTrimitelaZepEșec (尝试 {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"În lotTrimitelaZepEșec，已Reîncercare{self.MAX_RETRIES}次: {e}")
                    self._failed_count += 1
    
    def _flush_remaining(self):
        """Trimite队列și缓冲区剩余活动"""
        # 首先Procesare队列剩余活动，添加la缓冲区
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break
        
        # 然后Trimite各Platformă缓冲区剩余活动（即使不足BATCH_SIZE条）
        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"Trimite{display_name}Platformă剩余 {len(buffer)} 条活动")
                    self._send_batch_activities(buffer, platform)
            # 清Gol所有缓冲区
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []
    
    def get_stats(self) -> Dict[str, Any]:
        """Obținere统计Informații"""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,  # 添加la队列活动总数
            "batches_sent": self._total_sent,            # SuccesTrimite批次数
            "items_sent": self._total_items_sent,        # SuccesTrimite活动条数
            "failed_count": self._failed_count,          # TrimiteEșec批次数
            "skipped_count": self._skipped_count,        # 被过滤跳过活动数（DO_NOTHING）
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,                # 各Platformă缓冲区大小
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """
    管理多个SimulareZepGrafMemorieActualizare器
    
    每个Simulare可以有自己Actualizare器实例
    """
    
    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()
    
    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        """
        为SimulareCreareGrafMemorieActualizare器
        
        Args:
            simulation_id: SimulareID
            graph_id: ZepGrafID
            
        Returns:
            ZepGraphMemoryUpdater实例
        """
        with cls._lock:
            # dacă已存în，先Oprire旧
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            
            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            
            logger.info(f"CreareGrafMemorieActualizare器: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater
    
    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[ZepGraphMemoryUpdater]:
        """ObținereSimulareActualizare器"""
        return cls._updaters.get(simulation_id)
    
    @classmethod
    def stop_updater(cls, simulation_id: str):
        """Oprire并移除SimulareActualizare器"""
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"已OprireGrafMemorieActualizare器: simulation_id={simulation_id}")
    
    # 防止 stop_all 重复调用标志
    _stop_all_done = False
    
    @classmethod
    def stop_all(cls):
        """Oprire所有Actualizare器"""
        # 防止重复调用
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        
        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"OprireActualizare器Eșec: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info("已Oprire所有GrafMemorieActualizare器")
    
    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Obținere所有Actualizare器统计Informații"""
        return {
            sim_id: updater.get_stats() 
            for sim_id, updater in cls._updaters.items()
        }
