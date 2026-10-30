import os
import re
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

user_links = {}

def clean_instagram_url(raw_url: str) -> str:
    match = re.search(r'(https?://(?:www\.)?instagram\.com/(?:reel|p|tv)/[A-Za-z0-9_-]+)', raw_url)
    return match.group(1) if match else raw_url

def download_video(url: str):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def download_audio(url: str):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s_audio.%(ext)s',
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info.get('title', 'Audio')

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    text = (
        "Assalomu alaykum!\n\n"
        "Menga Instagram post yoki reel havolasini yuboring, videoni yuklab beraman."
    )
    await message.answer(text)

@dp.message(F.text.regexp(r'https?://(?:www\.)?instagram\.com/(?:reel|p|tv)/[A-Za-z0-9_-]+'))
async def handle_instagram_link(message: types.Message):
    url = clean_instagram_url(message.text.strip())
    status_msg = await message.answer("Video yuklanmoqda, kuting...")

    try:
        loop = asyncio.get_running_loop()
        video_path = await loop.run_in_executor(None, download_video, url)

        user_links[message.from_user.id] = url

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Musiqani yuklab olish", callback_data="get_audio")],
            [InlineKeyboardButton(text="Guruhga qo'shish", url="https://t.me/Instavideodowland_bot?startgroup=true")]
        ])

        caption = "Videongiz tayyor! Ibojonga raxmat ayting! @Instavideodowland_bot"
        video_file = FSInputFile(video_path)
        await message.answer_video(video=video_file, caption=caption, reply_markup=keyboard)

        if os.path.exists(video_path):
            os.remove(video_path)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_msg.edit_text("Yuklab bo'lmadi. Havola noto'g'ri yoki profil yopiq bo'lishi mumkin.")

@dp.callback_query(F.data == "get_audio")
async def send_audio_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    url = user_links.get(user_id)

    if not url:
        await callback.answer("Havola topilmadi. Videoni qaytadan yuboring.", show_alert=True)
        return

    await callback.answer("Musiqa yuklanmoqda...")
    status_audio = await callback.message.reply("Musiqa ajratib olinmoqda, kuting...")

    try:
        loop = asyncio.get_running_loop()
        audio_path, title = await loop.run_in_executor(None, download_audio, url)

        if os.path.exists(audio_path):
            audio_file = FSInputFile(audio_path)
            await callback.message.reply_audio(
                audio=audio_file,
                caption="Ibojonga raxmat ayting! @Instavideodowland_bot",
                title=title[:40],
                performer="Ibojon"
            )
            os.remove(audio_path)

        await status_audio.delete()

    except Exception as e:
        logging.error(f"Audio xatolik: {e}")
        await status_audio.edit_text("Musiqani yuklab bo'lmadi.")

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
