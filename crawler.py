"""
爬虫模块：抓取福彩双色球历史数据
数据源：福彩官方API
"""
import requests
import json
import time
import logging
from database import save_draw, get_latest_draw

logger = logging.getLogger("crawler")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.cwl.gov.cn/",
}


def fetch_page(page=1, pagesize=30):
    """抓取一页开奖数据"""
    url = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
    params = {
        "name":     "ssq",
        "issueCount": "",
        "issueStart": "",
        "issueEnd":   "",
        "dayStart":   "",
        "dayEnd":     "",
        "pageNo":   page,
        "pageSize": pagesize,
        "week":     "",
        "systemType": "PC",
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()
        return data.get("result", [])
    except Exception as e:
        logger.error(f"抓取失败 page={page}: {e}")
        return []


def parse_and_save(records):
    """解析并保存开奖记录"""
    saved = 0
    for rec in records:
        try:
            issue = rec.get("code", "")
            date  = rec.get("date", "")[:10]
            reds_str = rec.get("red", "")
            blue  = int(rec.get("blue", 0))
            sales = rec.get("sales", "")
            pool  = rec.get("poolmoney", "")

            reds = [int(x) for x in reds_str.split(",") if x.strip()]
            if len(reds) != 6:
                continue

            save_draw(issue, date, reds, blue, sales, pool)
            saved += 1
        except Exception as e:
            logger.warning(f"解析失败: {e} | {rec}")
    return saved


def crawl_history(pages=20):
    """抓取历史数据（默认20页×30条=600期）"""
    total = 0
    for page in range(1, pages + 1):
        records = fetch_page(page=page, pagesize=30)
        if not records:
            break
        n = parse_and_save(records)
        total += n
        logger.info(f"第{page}页 保存{n}条，累计{total}条")
        time.sleep(0.5)
    logger.info(f"历史数据抓取完成，共{total}条")
    return total


def crawl_latest():
    """只抓最新1页，用于定时更新"""
    records = fetch_page(page=1, pagesize=5)
    n = parse_and_save(records)
    logger.info(f"更新最新数据 {n}条")
    return n
