import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
import yt_dlp

TOKEN = "7622123900:AAFdOgczhmAZ8S5ZFDcqhalvBH2uD6FpKfg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

def download_instagram_video(url: str, output_path: str = "downloads/%(id)s.%(ext)s"):
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'mp4/bestvideo+bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Assalomu alaykum! Menga Instagram post yoki reel havolasini yuboring, videoni yuklab beraman.")

@dp.message(F.text.regexp(r'https?://(?:www\.)?instagram\.com/(?:reel|p|tv)/[A-Za-z0-9_-]+'))
async def handle_instagram_link(message: types.Message):
    url = message.text.strip()
    status_msg = await message.answer("⏳ Videoni Ibojonni shaxsan o'zi yuklamoqda, kuting...")

    try:
        os.makedirs("downloads", exist_ok=True)
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(None, download_instagram_video, url)

        video = FSInputFile(file_path)
        await message.answer_video(video=video, caption="Videongiz tayyor! Ibojonga raxmat ayting! @Instavideodowland_bot")

        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_msg.edit_text("❌ Videoni yuklab bo'lmadi. Havola noto'g'ri yoki profil yopiq bo'lishi mumkin.")

# Render Web Service uchun port eshituvchi server
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

