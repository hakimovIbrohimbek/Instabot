import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

TOKEN = "7622123900:AAFdOgczhmAZ8S5ZFDcqhalvBH2uD6FpKfg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Foydalanuvchi havolalarini eslab qolish uchun oddiy xotira
user_links = {}

def download_video_only(url: str):
    os.makedirs("downloads", exist_ok=True)
    video_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'format': 'mp4/bestvideo+bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(video_opts) as ydl:
        v_info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(v_info)

def download_audio_only(url: str):
    os.makedirs("downloads", exist_ok=True)
    audio_opts = {
        'outtmpl': 'downloads/%(id)s_audio.%(ext)s',
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(audio_opts) as ydl:
        a_info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(a_info), a_info.get('title', 'Musiqa')

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    text = (
        "👋 **Assalomu alaykum!**\n\n"
        "✨ **Ibojon InstaSaver** botiga xush kelibsiz!\n"
        "📥 Instagram **Reels** yoki **Post** havolasini yuboring.\n\n"
        "👑 **Muallif:** Ibrohimbek (Ibojon)"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.regexp(r'https?://(?:www\.)?instagram\.com/(?:reel|p|tv)/[A-Za-z0-9_-]+'))
async def handle_instagram_link(message: types.Message):
    url = message.text.strip()
    status_msg = await message.answer("⚡️ **Video yuklanmoqda...**", parse_mode="Markdown")

    try:
        loop = asyncio.get_running_loop()
        video_path = await loop.run_in_executor(None, download_video_only, url)

        # Video ID sini tugmaga biriktiramiz
        user_id = message.from_user.id
        user_links[user_id] = url

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 Qo'shiqni yuklab olish", callback_data="get_audio")],
            [InlineKeyboardButton(text="➕ Guruhga qo'shish", url=f"https://t.me/{(await bot.get_me()).username}?startgroup=true")]
        ])

        caption = (
            "🎬 **Videongiz tayyor!**\n\n"
            "❤️ **Ibojonga raxmat aytib qo'ying!** 😉\n"
            "🤖 @Instavideodowland_bot"
        )
        video_file = FSInputFile(video_path)
        await message.answer_video(video=video_file, caption=caption, reply_markup=keyboard, parse_mode="Markdown")

        if os.path.exists(video_path):
            os.remove(video_path)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_msg.edit_text("❌ Yuklab bo'lmadi. Havola noto'g'ri yoki profil yopiq bo'lishi mumkin.")

@dp.callback_query(F.data == "get_audio")
async def send_audio_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    url = user_links.get(user_id)

    if not url:
        await callback.answer("Havola topilmadi. Qaytadan video havolasini yuboring.", show_alert=True)
        return

    await callback.answer("🎵 Qo'shiq yuklanmoqda...")
    status_audio = await callback.message.reply("⏳ Musiqa ajratib olinmoqda, kuting...")

    try:
        loop = asyncio.get_running_loop()
        audio_path, title = await loop.run_in_executor(None, download_audio_only, url)

        if os.path.exists(audio_path):
            audio_file = FSInputFile(audio_path)
            await callback.message.reply_audio(
                audio=audio_file,
                caption="🎵 **Videodagi musiqa**\n👑 *Ibojon InstaSaver*",
                title=title[:40],
                performer="Ibojon InstaSaver",
                parse_mode="Markdown"
            )
            os.remove(audio_path)

        await status_audio.delete()

    except Exception as e:
        logging.error(f"Audio xatolik: {e}")
        await status_audio.edit_text("❌ Musiqani yuklab bo'lmadi.")

# Render uchun web server
async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
