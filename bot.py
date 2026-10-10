import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import aiohttp

# --- SOZLAMALAR ---
BOT_TOKEN = '8867807680:AAF3nSCl3N-LxFXuvH7QfJKIxx2g8bvxGRA'
ADMIN_ID = 1696886169  # O'zingizning Telegram ID'angizni yozing (@userinfobot orqali bilsangiz bo'ladi)
CHANNELS = [
    {"username": "@kanal_username", "name": "Asosiy Kanal"} # @ belgi bilan yozing, bot kanalda admin bo'lishi shart!
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect("saveoff_base.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT
)
""")
conn.commit()

def register_user(user_id, username):
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
    except Exception as e:
        logging.error(f"Baza xatosi: {e}")

def get_users_count():
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]

def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]

# --- MAJBURIY OBUNA TEKSHIRISH ---
async def check_subscription(user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["username"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            # Agar bot kanalda admin bo'lmasa yoki kanal topilmasa false qaytaradi
            return False
    return True

def get_subscription_keyboard():
    keyboard = []
    for channel in CHANNELS:
        keyboard.append([InlineKeyboardButton(text=channel["name"], url=f"https://t.me{channel['username'].replace('@', '')}")])
    keyboard.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- TIKTOK API ---
async def download_tiktok(tiktok_url: str):
    api_url = "https://tikwm.com"
    payload = {'url': tiktok_url}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(api_url, data=payload) as response:
                if response.status == 200:
                    res_json = await response.json()
                    if res_json.get('code') == 0:
                        video_url = "https://tikwm.com" + res_json['data']['play']
                        music_url = "https://tikwm.com" + res_json['data']['music']
                        title = res_json['data'].get('title', 'SaveOFF Downloader')
                        return video_url, music_url, title
        except Exception as e:
            logging.error(f"API xatolik: {e}")
    return None, None, None

# --- HANDLERLAR ---

@dp.message(CommandStart())
async def start_cmd(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    
    if not await check_subscription(message.from_user.id):
        await message.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=get_subscription_keyboard())
        return

    await message.answer(
        "👋 **SaveOFF TikTok Downloader-ga xush kelibsiz!**\n\n"
        "Menga TikTok video havolasini yuboring. Men uni sizga video va audio formatda yuklab beraman!"
    )

@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(call: CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Obuna tasdiqlandi. Endi menga TikTok linkini yuborishingiz mumkin.")
    else:
        await call.answer("❌ Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "👨‍💻 **Admin panelga xush kelibsiz!**\n\n"
        "📊 /stat - Bot a'zolari statistikasini ko'rish\n"
        "📢 /send [xabar] - Barcha foydalanuvchilarga reklama tarqatish"
    )

@dp.message(Command("stat"))
async def admin_stat(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    count = get_users_count()
    await message.answer(f"📊 **Bot foydalanuvchilari soni:** {count} ta")

@dp.message(Command("send"))
async def admin_send(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text_to_send = message.text.replace("/send", "").strip()
    if not text_to_send:
        await message.answer("⚠️ Foydalanish: `/send Reklama matni`")
        return
    
    users = get_all_users()
    success = 0
    await message.answer("📢 Reklama tarqatish boshlandi...")
    
    for user_id in users:
        try:
            await bot.send_message(chat_id=user_id, text=text_to_send)
            success += 1
            await asyncio.sleep(0.05) # Telegram bloklab qo'ymasligi uchun kichik pauza
        except Exception:
            pass
            
    await message.answer(f"✅ Reklama yakunlandi.\nUzatildi: {success}/{len(users)}")

# --- LINKLARNI QABUL QILISH ---
@dp.message(F.text)
async def handle_tiktok_link(message: Message):
    register_user(message.from_user.id, message.from_user.username)
    
    if not await check_subscription(message.from_user.id):
        await message.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=get_subscription_keyboard())
        return

    url = message.text.strip()
    if "tiktok.com" in url:
        status_msg = await message.answer("🔄 Video tahlil qilinmoqda...")
        video_url, music_url, title = await download_tiktok(url)
        
        if video_url:
            await status_msg.edit_text("⚡️ Video yuklanmoqda...")
            try:
                # Audio yuklash uchun inline tugma qo'shamiz
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎵 MP3 formatda yuklash", callback_data=f"audio_{url}")]
                ])
                
                await message.reply_video(
                    video=video_url,
                    caption=f"🎬 **{title}**\n\n✨ @SaveOFF_bot orqali yuklab olindi.",
                    reply_markup=kb
                )
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit_text("❌ Videoni yuborishda xatolik yuz berdi.")
                logging.error(f"Telegram yuborish xatosi: {e}")
        else:
            await status_msg.edit_text("❌ Videoni yuklab bo'lmadi. Linkni tekshiring.")
    else:
        await message.answer("⚠️ Iltimos, faqat to'g'ri TikTok linkini yuboring!")

# --- AUDIO YUKLAB BERISH (CALLBACK) ---
@dp.callback_query(F.data.startswith("audio_"))
async def callback_download_audio(call: CallbackQuery):
    url = call.data.replace("audio_", "")
    await call.answer("🎵 Audio tayyorlanmoqda...")
    
    _, music_url, title = await download_tiktok(url)
    if music_url:
        try:
            await call.message.reply_audio(
                audio=music_url,
                caption=f"🎵 **{title} (Audio)**\n\n✨ @SaveOFF_bot"
            )
        except Exception:
            await call.message.answer("❌ Audioni yuborib bo'lmadi.")
    else:
        await call.message.answer("❌ Audio havolasi topilmadi.")

async def main():
    print("🚀 SaveOFF Pro Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
