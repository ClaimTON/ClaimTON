import asyncio
import random
import logging
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest

BOT_TOKEN  = "BOT_TOKEN"
CHANNEL_ID = "@channel"
ADMIN_IDS  = [123456789]

GIFT_IDS = [
    "gift_id_1",
    "gift_id_2",
    "gift_id_3",
    "gift_id_4",
    "gift_id_5",
]

DB_PATH = "claimton.db"

START_TEXT = """<b>🐸 ClaimTON - Get Free Gift!</b>

ClaimTON is a community movement built on the TON blockchain. We're on a mission to reward every early member with a free Telegram gift simply for believing in us before everyone else.

<b>🌐 Why ClaimTON?</b>
<blockquote>The future of Web3 is being built on TON, and we want you in it from day one. Fast transactions, near-zero fees, deep Telegram integration this is where it all happens.

🎁 <b>You</b> claim a free Telegram gift
🚀 <b>We</b> build something great together</blockquote>

<b>🪂 What's an AirDrop?</b>
<blockquote>Think of it as your founding member reward. We drop exclusive Telegram digital assets straight to your account assets with <b>real market value</b> you can hold, show off, or trade. Rare ones exist. Early ones get the best shot at them.</blockquote>

<b>💡 The logic behind it</b>
<blockquote>Your presence fuels this project. A blockchain community is only as strong as the people in it. So instead of spending on ads, we invest directly in you the people who show up first and help us grow.</blockquote>

<b>🚀 Grab your AirDrop</b>
<blockquote>🔹 <b>Hit the button below</b> to get started
🔹 <b>Claim your gift</b> in under a minute
🔹 <b>Spread the word</b> and grow with us</blockquote>

<b><a href="https://t.me">🐸 The channel for the news - big things coming!</a></b>

<b><a href="https://github.com/claimton/claimton">👾 GitHub Page</a></b>"""

NOT_MEMBER_TEXT = """❌ <b>To use the bot, you need to connect it to your business account!</b>"""

ALREADY_CLAIMED_TEXT = """<b>🎁 You've already claimed your AirDrop!</b>

You can only claim once per account. Thank you for being part of the ClaimTON community! 🚀

<i>Share the bot with your friends so they can claim theirs too 👇</i>"""

SUCCESS_TEXT = """<b>🎉 Your AirDrop is on its way!</b>

Your free Telegram gift has been sent to your account. Check your Telegram gifts to find it!

<i>Enjoy, and don't forget to share ClaimTON with your network. The more we grow, the more we can give. 🚀</i>

<b><a href="https://t.me/claimton">🐸 Stay tuned on the channel!</a></b>"""

ERROR_TEXT = """❌ <b>To use it, you need to give the bot permission to interact with the gift airdrop!</b>"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                gift_id     TEXT,
                claimed_at  TEXT
            )
        """)
        await db.commit()


async def has_claimed(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM claims WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def save_claim(user_id: int, username: str, first_name: str, gift_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO claims (user_id, username, first_name, gift_id, claimed_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, gift_id, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM claims") as cursor:
            total = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM claims WHERE claimed_at >= date('now', '-1 day')"
        ) as cursor:
            today = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM claims WHERE claimed_at >= date('now', '-7 days')"
        ) as cursor:
            week = (await cursor.fetchone())[0]
    return {"total": total, "today": today, "week": week}


def kb_join() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join ClaimTON", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton(text="✅ I've joined — Claim my AirDrop!", callback_data="check_membership")]
    ])


def kb_claim() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪂 Claim my free AirDrop!", callback_data="claim_airdrop")]
    ])


def kb_share(bot_username: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}&text=🐸 Claim your free Telegram AirDrop on ClaimTON!"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Share with friends", url=share_url)],
    ])


async def is_member(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ("left", "kicked")
    except TelegramBadRequest:
        return False


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    logger.info(f"Start | user_id={user.id} username={user.username}")
    if await is_member(user.id):
        await message.answer(START_TEXT, parse_mode="HTML", reply_markup=kb_claim())
    else:
        await message.answer(START_TEXT, parse_mode="HTML", reply_markup=kb_join())


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    stats = await get_stats()
    text = (
        f"<b>📊 ClaimTON Stats</b>\n\n"
        f"🪂 Total claims: <b>{stats['total']}</b>\n"
        f"📅 Last 24h: <b>{stats['today']}</b>\n"
        f"📆 Last 7 days: <b>{stats['week']}</b>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.callback_query(F.data == "check_membership")
async def check_membership(callback: CallbackQuery) -> None:
    await callback.answer()
    if await is_member(callback.from_user.id):
        await callback.message.edit_reply_markup(reply_markup=kb_claim())
        await callback.message.answer(
            "✅ <b>You're in!</b> Now claim your free AirDrop below 🎁",
            parse_mode="HTML",
            reply_markup=kb_claim()
        )
    else:
        await callback.answer("❌ You haven't joined the channel yet!", show_alert=True)


@dp.callback_query(F.data == "claim_airdrop")
async def claim_airdrop(callback: CallbackQuery) -> None:
    await callback.answer()
    user = callback.from_user

    if await has_claimed(user.id):
        await callback.message.answer(ALREADY_CLAIMED_TEXT, parse_mode="HTML")
        return

    if not await is_member(user.id):
        await callback.message.answer(NOT_MEMBER_TEXT, parse_mode="HTML", reply_markup=kb_join())
        return

    gift_id = random.choice(GIFT_IDS)
    try:
        await bot.send_gift(user_id=user.id, gift_id=gift_id)
        await save_claim(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            gift_id=gift_id
        )
        me = await bot.get_me()
        await callback.message.answer(SUCCESS_TEXT, parse_mode="HTML", reply_markup=kb_share(me.username))
        logger.info(f"Gift sent | user_id={user.id} username={user.username} gift_id={gift_id}")
    except TelegramBadRequest as e:
        logger.error(f"Gift failed | user_id={user.id} error={e}")
        await callback.message.answer(ERROR_TEXT, parse_mode="HTML")


async def main() -> None:
    await init_db()
    logger.info("ClaimTON bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
