import os
import re
import uuid
import asyncio
import logging
import subprocess
from pathlib import Path

import requests
import yt_dlp
import imageio_ffmpeg

from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# ==============================
# SOZLAMALAR
# ==============================

TOKEN = "7622123900:AAFdOgczhmAZ8S5ZFDcqhalvBH2uD6FpKfg"
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

video_data = {}

# ==============================
# INSTAGRAM HAVOLASI
# ==============================

def clean_instagram_url(raw_url: str) -> str:
    match = re.search(
        r'https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[A-Za-z0-9_-]+',
        raw_url
    )
    if not match:
        raise ValueError("Instagram havolasi noto'g'ri")
    return match.group(0)

# ==============================
# VIDEO VA METAMA'LUMOTLAR
# ==============================

def download_video_and_meta(url: str, job_id: str):
    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": str(job_dir / "video.%(ext)s"),
        "format": "best",
        "quiet": True,
        "no_warnings": True,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = Path(ydl.prepare_filename(info))

        artist = info.get('artist') or info.get('creator') or info.get('uploader') or "Ibojon"
        track = info.get('track') or info.get('alt_title')
        title = info.get('title', '')

        if not track:
            if " - " in title and not title.lower().startswith("video by"):
                parts = title.split(" - ", 1)
                artist, track = parts[0].strip(), parts[1].strip()
            else:
                track = "Musiqa"

        return str(video_path), str(artist), str(track)

def extract_clean_mp3(video_path: str, job_id: str):
    job_dir = DOWNLOAD_DIR / job_id
    audio_path = job_dir / "audio.mp3"

    command = [
        FFMPEG_PATH,
        "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", "192k",
        str(audio_path)
    ]

    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if result.returncode == 0 and audio_path.exists():
        return str(audio_path)
    return None

# ==============================
# START
# ==============================

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "Assalomu alaykum!\n\n"
        "Instagram Reels havolasini yuboring. Videoni va undagi musiqani toza MP3 formatda yuklab beraman."
    )

# ==============================
# VIDEO QABUL QILISH
# ==============================

@dp.message(F.text.regexp(r'https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/'))
async def handle_instagram(message: types.Message):
    status = await message.answer("Video yuklanmoqda, kuting...")
    job_id = uuid.uuid4().hex[:12]

    try:
        url = clean_instagram_url(message.text.strip())
        loop = asyncio.get_running_loop()

        video_path, artist, track = await loop.run_in_executor(
            None, download_video_and_meta, url, job_id
        )

        video_data[job_id] = {
            "video_path": video_path,
            "artist": artist,
            "track": track
        }

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎵 Musiqani yuklab olish", callback_data=f"music:{job_id}")],
                [InlineKeyboardButton(text="➕ Guruhga qo'shish", url="https://t.me/Instavideodowland_bot?startgroup=true")]
            ]
        )

        caption = "Videongiz tayyor! Ibojonga raxmat ayting! @Instavideodowland_bot"
        await message.answer_video(
            video=FSInputFile(video_path),
            caption=caption,
            reply_markup=keyboard
        )

        await status.delete()

    except Exception as e:
        logger.exception("Instagram yuklash xatosi")
        await status.edit_text("Yuklab bo'lmadi. Havola noto'g'ri yoki profil yopiq bo'lishi mumkin.")

# ==============================
# MUSIQANI YUKLASH TUGMASI
# ==============================

@dp.callback_query(F.data.startswith("music:"))
async def music_callback(callback: types.CallbackQuery):
    job_id = callback.data.split(":", 1)[1]
    data = video_data.get(job_id)

    if not data:
        await callback.answer("Muddati tugagan. Videoni qayta yuboring.", show_alert=True)
        return

    await callback.answer("Musiqa tayyorlanmoqda...")
    status_music = await callback.message.reply("⏳ MP3 tayyorlanmoqda...")

    try:
        loop = asyncio.get_running_loop()
        audio_path = await loop.run_in_executor(
            None, extract_clean_mp3, data["video_path"], job_id
        )

        if audio_path and os.path.exists(audio_path):
            clean_track = re.sub(r'[_*`\[\]]', '', data["track"])
            clean_artist = re.sub(r'[_*`\[\]]', '', data["artist"])

            caption = f"🎧 {clean_artist} - {clean_track}\n\nIbojonga raxmat ayting! @Instavideodowland_bot"

            await callback.message.reply_audio(
                audio=FSInputFile(audio_path),
                caption=caption,
                title=clean_track[:40],
                performer=clean_artist[:30]
            )
            await status_music.delete()
        else:
            await status_music.edit_text("Musiqani ajratish imkoni bo'lmadi.")

    except Exception:
        logger.exception("Audio yuborish xatosi")
        await status_music.edit_text("Musiqani yuklashda xatolik yuz berdi.")
    finally:
        # Fayllarni tozalash
        job_dir = DOWNLOAD_DIR / job_id
        if job_dir.exists():
            for f in job_dir.iterdir():
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                job_dir.rmdir()
            except OSError:
                pass
        video_data.pop(job_id, None)

# ==============================
# WEB SERVER (RENDER)
# ==============================

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

# ==============================
# ISHGA TUSHIRISH
# ==============================

async def main():
    await start_web_server()
    logger.info("Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
