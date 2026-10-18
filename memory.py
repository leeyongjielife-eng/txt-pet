"""
memory.py — 松喵喵轻量记忆系统
存储路径: data/songnyang_memory.json
"""
import json
import os
import sys
from datetime import date

ROOT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = (
    os.path.join(os.path.expanduser("~"), "Library", "Application Support",
                 "TXT Desktop Pets", "Songnyang", "songnyang_memory.json")
    if getattr(sys, "frozen", False)
    else os.path.join(ROOT_DIR, "data", "songnyang_memory.json")
)

_DEFAULTS: dict = {
    "first_met_date":   None,
    "last_opened_date": None,
    "days_together":    0,
    "interaction_count": 0,
    "croissant_count":  0,
    "txt_song_count":   0,
    "stamina":          100,
}


class MemoryManager:

    def __init__(self):
        self._data: dict = {}
        self._load()
        self._on_startup()

    # ── 读写 ──────────────────────────────────────────────────────────────────

    def _load(self):
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Retired intimacy and one-time flower-gift fields are no longer
                # part of the active save format.
                for key in (
                    "hidden_closeness", "music_play_count", "workout_count", "flower_gift_count",
                    "bath_count", "play_count", "static_event_count",
                ):
                    saved.pop(key, None)
                self._data = {**_DEFAULTS, **saved}
            except (json.JSONDecodeError, OSError):
                print("[memory] 读取失败，使用默认值")
                self._data = dict(_DEFAULTS)
        else:
            self._data = dict(_DEFAULTS)

    def _save(self):
        try:
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"[memory] 保存失败: {e}")

    # ── 启动逻辑 ──────────────────────────────────────────────────────────────

    def _on_startup(self):
        today = date.today().isoformat()
        if not self._data["first_met_date"]:
            self._data["first_met_date"] = today
            print(f"[memory] 第一次见面：{today}")
        self._data["last_opened_date"] = today
        first = date.fromisoformat(self._data["first_met_date"])
        self._data["days_together"] = (date.today() - first).days + 1
        self._save()
        print(f"[memory] 已陪伴 {self._data['days_together']} 天，互动 {self._data['interaction_count']} 次")

    # ── 公开接口 ──────────────────────────────────────────────────────────────

    def increment(self, *keys: str) -> None:
        """将一个或多个计数字段各加 1 并保存。"""
        for key in keys:
            if key in self._data and isinstance(self._data[key], int):
                self._data[key] += 1
        self._save()

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value) -> None:
        """保存一个运行状态值。"""
        if key in self._data:
            self._data[key] = value
            self._save()
