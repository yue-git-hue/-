"""
彩票分析 Agent 主程序
FastAPI + OpenAI + SQLite
"""

import os, json, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI

from database import init_db, get_or_create_user, save_pick, get_picks, update_prize, get_draws, get_latest_draw
from crawler  import crawl_history, crawl_latest
from analyzer import get_stats, generate_picks, check_prize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-api-key-here")
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """你是一个双色球数据分析助手。你帮助用户分析历史开奖数据、解读号码规律、生成选号建议。
重要提示：彩票是随机事件，你的分析是基于历史统计，不能预测未来，请在分析时提醒用户理性购彩。
回答要简洁清晰，数据准确，语气友好。用中文回答。"""


@asynccontextmanager
async def lifespan(app):
    init_db()
    draws = get_draws(1)
    if not draws:
        logger.info("首次启动，抓取历史数据...")
        crawl_history(pages=20)
    else:
        crawl_latest()
    yield


app = FastAPI(title="双色球分析助手", lifespan=lifespan)


# ── API 接口 ─────────────────────────────────────────────────

@app.get("/api/stats")
def api_stats():
    return get_stats(300) or {}


@app.get("/api/latest")
def api_latest():
    return get_latest_draw() or {}


@app.post("/api/generate")
def api_generate():
    stats = get_stats(300)
    picks = generate_picks(n=5, stats=stats)
    return {"picks": picks}


@app.post("/api/user/login")
async def api_login(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    if not username or len(username) > 20:
        return JSONResponse({"error": "用户名不合法"}, status_code=400)
    user = get_or_create_user(username)
    return {"user_id": user["id"], "username": user["username"]}


@app.post("/api/picks/save")
async def api_save_pick(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    reds    = data.get("reds", [])
    blue    = data.get("blue")
    note    = data.get("note", "")
    issue   = data.get("issue", "")
    if not user_id or len(reds) != 6 or not blue:
        return JSONResponse({"error": "参数错误"}, status_code=400)
    save_pick(user_id, reds, blue, note, issue)
    return {"ok": True}


@app.get("/api/picks/{user_id}")
def api_get_picks(user_id: int):
    picks = get_picks(user_id, limit=50)
    # 自动对奖
    latest = get_latest_draw()
    result = []
    for p in picks:
        my_reds  = [p["red1"],p["red2"],p["red3"],p["red4"],p["red5"],p["red6"]]
        my_blue  = p["blue"]
        item = dict(p)
        if latest and p["issue"] == latest["issue"] and not p["checked"]:
            draw_reds = [latest["red1"],latest["red2"],latest["red3"],
                         latest["red4"],latest["red5"],latest["red6"]]
            level, desc = check_prize(my_reds, my_blue, draw_reds, latest["blue"])
            update_prize(p["id"], level)
            item["prize_level"] = level
            item["prize_desc"]  = desc
        result.append(item)
    return result


@app.post("/api/chat")
async def api_chat(request: Request):
    data     = await request.json()
    messages = data.get("messages", [])
    stats    = get_stats(100)
    latest   = get_latest_draw()

    context = ""
    if stats:
        context = f"""
当前数据概况（近{stats['total']}期）：
- 最新一期：{latest['issue'] if latest else '无'}期，开奖号码：{latest['red1']},{latest['red2']},{latest['red3']},{latest['red4']},{latest['red5']},{latest['red6']} + {latest['blue']}
- 红球热号（出现最多）：{stats['hot_reds']}
- 红球冷号（出现最少）：{stats['cold_reds']}
- 蓝球热号：{stats['hot_blues']}
- 蓝球冷号：{stats['cold_blues']}
- 红球和值平均：{stats['avg_sum']}
- 最常见奇偶比：{stats['most_odd']}奇{6-stats['most_odd']}偶
"""

    full_messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context},
        *messages[-10:],  # 最近10条对话
    ]

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=full_messages,
            max_tokens=800,
            temperature=0.7,
        )
        reply = resp.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        logger.error(f"OpenAI 错误: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/refresh")
def api_refresh():
    n = crawl_latest()
    return {"updated": n}


# ── 前端页面 ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
