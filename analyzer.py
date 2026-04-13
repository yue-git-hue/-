"""
分析模块：统计频率、冷热号、生成推荐号码
"""
import random
import numpy as np
from collections import Counter
from database import get_draws


def get_stats(limit=300):
    """统计历史数据"""
    draws = get_draws(limit)
    if not draws:
        return None

    red_all  = []
    blue_all = []
    for d in draws:
        reds = [d["red1"],d["red2"],d["red3"],d["red4"],d["red5"],d["red6"]]
        red_all.extend(reds)
        blue_all.append(d["blue"])

    total = len(draws)

    # 红球频率
    red_freq  = Counter(red_all)
    blue_freq = Counter(blue_all)

    # 红球遗漏期数（上次出现距今多少期）
    red_miss  = {}
    blue_miss = {}
    for n in range(1, 34):
        for i, d in enumerate(draws):
            reds = [d["red1"],d["red2"],d["red3"],d["red4"],d["red5"],d["red6"]]
            if n in reds:
                red_miss[n] = i
                break
        else:
            red_miss[n] = total
    for n in range(1, 17):
        for i, d in enumerate(draws):
            if d["blue"] == n:
                blue_miss[n] = i
                break
        else:
            blue_miss[n] = total

    # 热号（出现频率前10）/ 冷号（出现频率后10）
    sorted_red = sorted(red_freq.items(), key=lambda x: x[1], reverse=True)
    hot_reds   = [x[0] for x in sorted_red[:10]]
    cold_reds  = [x[0] for x in sorted_red[-10:]]

    sorted_blue = sorted(blue_freq.items(), key=lambda x: x[1], reverse=True)
    hot_blues   = [x[0] for x in sorted_blue[:5]]
    cold_blues  = [x[0] for x in sorted_blue[-5:]]

    # 和值分布
    sum_vals = []
    for d in draws:
        reds = [d["red1"],d["red2"],d["red3"],d["red4"],d["red5"],d["red6"]]
        sum_vals.append(sum(reds))
    avg_sum = round(np.mean(sum_vals), 1)

    # 奇偶比分布
    odd_ratios = []
    for d in draws:
        reds = [d["red1"],d["red2"],d["red3"],d["red4"],d["red5"],d["red6"]]
        odds = sum(1 for r in reds if r % 2 == 1)
        odd_ratios.append(odds)
    most_odd = Counter(odd_ratios).most_common(1)[0][0]

    return {
        "total":       total,
        "red_freq":    {str(k): v for k, v in sorted(red_freq.items())},
        "blue_freq":   {str(k): v for k, v in sorted(blue_freq.items())},
        "red_miss":    {str(k): v for k, v in sorted(red_miss.items())},
        "blue_miss":   {str(k): v for k, v in sorted(blue_miss.items())},
        "hot_reds":    hot_reds,
        "cold_reds":   cold_reds,
        "hot_blues":   hot_blues,
        "cold_blues":  cold_blues,
        "avg_sum":     avg_sum,
        "most_odd":    most_odd,
        "latest":      draws[:5],
    }


def generate_picks(n=5, stats=None):
    """
    生成n注推荐号码
    策略：基于历史频率加权随机，兼顾冷热平衡
    """
    if stats is None:
        stats = get_stats()
    if stats is None:
        return []

    red_freq  = {int(k): v for k, v in stats["red_freq"].items()}
    blue_freq = {int(k): v for k, v in stats["blue_freq"].items()}
    red_miss  = {int(k): v for k, v in stats["red_miss"].items()}

    picks = []
    for _ in range(n):
        # 红球加权：频率权重 × 遗漏期数权重（遗漏越久稍微加权）
        red_weights = {}
        for num in range(1, 34):
            freq_w = red_freq.get(num, 1)
            miss_w = 1 + red_miss.get(num, 0) * 0.05
            red_weights[num] = freq_w * miss_w

        total_w = sum(red_weights.values())
        probs   = [red_weights[i] / total_w for i in range(1, 34)]

        reds = sorted(np.random.choice(range(1, 34), size=6,
                                       replace=False, p=probs).tolist())

        # 蓝球加权：纯频率
        blue_nums = list(range(1, 17))
        bw = [blue_freq.get(n, 1) for n in blue_nums]
        bw_sum = sum(bw)
        bprobs = [w / bw_sum for w in bw]
        blue = int(np.random.choice(blue_nums, p=bprobs))

        picks.append({
            "reds": reds,
            "blue": blue,
            "note": _pick_note(reds, blue, stats),
        })

    return picks


def _pick_note(reds, blue, stats):
    """给每注号码生成简短说明"""
    hot_reds  = stats.get("hot_reds", [])
    cold_reds = stats.get("cold_reds", [])
    hot_blues = stats.get("hot_blues", [])

    hot_cnt  = sum(1 for r in reds if r in hot_reds)
    cold_cnt = sum(1 for r in reds if r in cold_reds)
    odd_cnt  = sum(1 for r in reds if r % 2 == 1)
    total    = sum(reds)
    blue_tag = "热蓝" if blue in hot_blues else "冷蓝"

    return f"和值{total} 奇{odd_cnt}偶{6-odd_cnt} 热{hot_cnt}冷{cold_cnt} {blue_tag}"


def check_prize(my_reds, my_blue, draw_reds, draw_blue):
    """
    对奖：计算中奖等级
    返回 (等级, 说明)
    """
    red_match  = len(set(my_reds) & set(draw_reds))
    blue_match = my_blue == draw_blue

    if red_match == 6 and blue_match:  return 1, "一等奖🎉"
    if red_match == 6:                 return 2, "二等奖🎊"
    if red_match == 5 and blue_match:  return 3, "三等奖🥳"
    if red_match == 5 or (red_match == 4 and blue_match): return 4, "四等奖"
    if red_match == 4 or (red_match == 3 and blue_match): return 5, "五等奖"
    if blue_match:                     return 6, "六等奖"
    return 0, "未中奖"
