
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

from aiohttp import web
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
AUDD_TOKEN = os.getenv("AUDD_API_TOKEN")

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

AUDD_URL = "https://api.audd.io/"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Render Environment Variables ichida yo'q")

if not AUDD_TOKEN:
    raise RuntimeError("AUDD_API_TOKEN Render Environment Variables ichida yo'q")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Har bir yuborilgan video uchun alohida ma'lumot
video_data = {}


# ==============================
# INSTAGRAM HAVOLASI
# ==============================

def clean_instagram_url(raw_url):
    match = re.search(
        r'https?://(?:www\.)?instagram\.com/'
        r'(?:reel|reels|p|tv)/[A-Za-z0-9_-]+',
        raw_url
    )

    if not match:
        raise ValueError("Instagram havolasi noto'g'ri")

    return match.group(0)


# ==============================
# VIDEO YUKLASH VA AUDIO AJRATISH
# ==============================

def prepare_video(url, job_id):

    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": str(job_dir / "video.%(ext)s"),
        "format": "best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "socket_timeout": 30,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = Path(ydl.prepare_filename(info))

    if not video_path.exists():
        raise FileNotFoundError("Video fayli topilmadi")

    # AudD uchun 12 soniyalik audio namuna tayyorlash
    audio_path = job_dir / "sample.mp3"

    command = [
        FFMPEG_PATH,
        "-y",
        "-i", str(video_path),
        "-t", "12",
        "-vn",
        "-ac", "2",
        "-ar", "44100",
        "-b:a", "128k",
        str(audio_path)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=90
    )

    if result.returncode != 0 or not audio_path.exists():
        raise RuntimeError("Videodan audio ajratib bo'lmadi")

    return str(video_path), str(audio_path)


# ==============================
# AUDD ORQALI MUSIQANI ANIQLASH
# ==============================

def recognize_music(audio_path):

    with open(audio_path, "rb") as audio_file:

        response = requests.post(
            AUDD_URL,
            data={
                "api_token": AUDD_TOKEN,
                "return": "apple_music,spotify",
                "market": "UZ"
            },
            files={
                "file": (
                    "sample.mp3",
                    audio_file,
                    "audio/mpeg"
                )
            },
            timeout=60
        )

    response.raise_for_status()
    data = response.json()

    if data.get("status") != "success":
        raise RuntimeError(
            data.get("error", {}).get("error_message", "AudD xatosi")
        )

    return data.get("result")


# ==============================
# NATIJANI TAYYORLASH
# ==============================

def get_music_links(result):

    links = []

    spotify = result.get("spotify") or {}
    spotify_url = (
        spotify.get("external_urls", {}).get("spotify")
        or spotify.get("url")
    )

    apple = result.get("apple_music") or {}
    apple_url = apple.get("url")

    song_link = result.get("song_link")

    if spotify_url:
        links.append(
            InlineKeyboardButton(
                text="🎧 Spotify",
                url=spotify_url
            )
        )

    if apple_url:
        links.append(
            InlineKeyboardButton(
                text="🍎 Apple Music",
                url=apple_url
            )
        )

    if song_link:
        links.append(
            InlineKeyboardButton(
                text="🔎 Qo'shiqni ochish",
                url=song_link
            )
        )

    # Qo'shimcha qidiruv havolasi
    artist = result.get("artist", "")
    title = result.get("title", "")

    if artist and title:
        from urllib.parse import quote_plus

        search_url = (
            "https://www.youtube.com/results?search_query="
            + quote_plus(f"{artist} {title} official audio")
        )

        links.append(
            InlineKeyboardButton(
                text="▶️ YouTube orqali topish",
                url=search_url
            )
        )

    keyboard_rows = [[button] for button in links]

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard_rows
    ) if keyboard_rows else None


def format_music_info(result):

    artist = result.get("artist") or "Noma'lum"
    title = result.get("title") or "Noma'lum"
    album = result.get("album") or "Ma'lumot yo'q"
    release_date = result.get("release_date") or "Noma'lum"
    timecode = result.get("timecode") or "Noma'lum"

    text = (
        "🎵 MUSIQA ANIQLANDI!\n\n"
        f"🎤 Ijrochi: {artist}\n"
        f"🎶 Qo'shiq: {title}\n"
        f"💿 Albom: {album}\n"
        f"📅 Chiqqan sana: {release_date}\n"
        f"⏱ Audio qismi: {timecode}\n\n"
        "👇 To'liq qo'shiqni tinglash uchun:"
    )

    return text


# ==============================
# START
# ==============================

@dp.message(CommandStart())
async def start_handler(message: types.Message):

    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Men Instagram video yuklovchi va "
        "musiqani aniqlovchi botman.\n\n"
        "📥 Instagram Reels havolasini yuboring.\n\n"
        "Men sizga:\n"
        "🎬 Videoni yuklab beraman.\n"
        "🎵 Fon musiqasini aniqlayman.\n"
        "🎤 Qo'shiq nomi va ijrochisini ko'rsataman.\n"
        "🔗 To'liq qo'shiq uchun havolalar beraman."
    )


# ==============================
# INSTAGRAM VIDEO QABUL QILISH
# ==============================

@dp.message(F.text.regexp(
    r'https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/'
))
async def handle_instagram(message: types.Message):

    status = await message.answer(
        "⏳ Video yuklanmoqda, kuting..."
    )

    job_id = uuid.uuid4().hex[:16]

    try:

        url = clean_instagram_url(message.text.strip())

        loop = asyncio.get_running_loop()

        video_path, audio_path = await loop.run_in_executor(
            None,
            prepare_video,
            url,
            job_id
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎵 Qo'shiqni aniqlash",
                        callback_data=f"recognize:{job_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="➕ Guruhga qo'shish",
                        url="https://t.me/Instavideodowland_bot?startgroup=true"
                    )
                ]
            ]
        )

        sent = await message.answer_video(
            video=FSInputFile(video_path),
            caption=(
                "✅ Video tayyor!\n\n"
                "🎵 Fon musiqasini bilish uchun "
                "pastdagi tugmani bosing.\n\n"
                "@Instavideodowland_bot"
            ),
            reply_markup=keyboard
        )

        # Callback uchun fayllarni saqlab qolamiz
        video_data[job_id] = {
            "video_path": video_path,
            "audio_path": audio_path,
            "user_id": message.from_user.id,
            "chat_id": message.chat.id
        }

        await status.delete()

    except Exception as e:

        logger.exception("Instagram yuklash xatosi")

        await status.edit_text(
            "❌ Video yuklab bo'lmadi.\n"
            "Havola noto'g'ri, profil yopiq yoki "
            "Instagram yuklashni cheklagan bo'lishi mumkin."
        )


# ==============================
# MUSIQANI ANIQLASH TUGMASI
# ==============================

@dp.callback_query(F.data.startswith("recognize:"))
async def recognize_callback(callback: types.CallbackQuery):

    job_id = callback.data.split(":", 1)[1]

    data = video_data.get(job_id)

    if not data:
        await callback.answer(
            "Video ma'lumotlari topilmadi. Qaytadan yuboring.",
            show_alert=True
        )
        return

    if (
        callback.from_user.id != data["user_id"]
        or callback.message.chat.id != data["chat_id"]
    ):
        await callback.answer(
            "Bu tugma videoni yuborgan foydalanuvchi uchun.",
            show_alert=True
        )
        return

    await callback.answer("Musiqa aniqlanmoqda...")

    status = await callback.message.reply(
        "🔍 Videodagi qo'shiq qidirilmoqda..."
    )

    try:

        loop = asyncio.get_running_loop()

        result = await loop.run_in_executor(
            None,
            recognize_music,
            data["audio_path"]
        )

        if not result:

            await status.edit_text(
                "😔 Qo'shiq aniqlanmadi.\n\n"
                "Boshqa videoni yuborib ko'ring. "
                "Musiqa aniq eshitilishi kerak."
            )

        else:

            text = format_music_info(result)
            keyboard = get_music_links(result)

            await status.edit_text(
                text,
                reply_markup=keyboard
            )

    except requests.exceptions.Timeout:

        await status.edit_text(
            "⏳ Musiqa aniqlash xizmati javob bermadi. "
            "Keyinroq urinib ko'ring."
        )

    except Exception:

        logger.exception("Musiqa aniqlash xatosi")

        await status.edit_text(
            "❌ Musiqani aniqlashda xatolik yuz berdi.\n"
            "AudD API tokenini va internet aloqasini tekshiring."
        )

    finally:

        # Ish tugagach vaqtinchalik fayllarni o'chirish
        for key in ("video_path", "audio_path"):
            path = data.get(key)

            if path and os.path.exists(path):
                os.remove(path)

        job_dir = DOWNLOAD_DIR / job_id

        try:
            if job_dir.exists():
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

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()


# ==============================
# BOTNI ISHGA TUSHIRISH
# ==============================

async def main():

    await start_web_server()

    logger.info("Bot ishga tushdi!")

    await dp.start_polling(bot)


if __name__ == "__main__":

    try:
        asyncio.run(main())

    finally:
        pass
