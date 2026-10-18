"""Soobin letter quotes. The letter UI intentionally shows only the short line."""

import random


LETTER_QUOTES = (
    "现在，我想绽放真我的光芒。",
    "爱真的能改变一切。",
    "因为成员们的幸福就是我的目标。",
    "我的信条是在想做的时候就要享受乐趣。",
    "因为我被好好地爱着，所以我也能够好好地去爱别人。",
    "一个瞬间的决心，就可能彻底改变你的人生，让你实现梦想。",
    "我很喜欢现实中的崔秀彬和偶像崔秀彬之间没有界限这一点。",
    "与其因为放弃而后悔，不如努力过后再后悔。",
    "我认为有一种爱，只存在于歌手和粉丝之间。",
    "即使偶尔偏离了方向，也希望你能继续相信自己。",
)


def random_letter_quote() -> str:
    return random.choice(LETTER_QUOTES)
