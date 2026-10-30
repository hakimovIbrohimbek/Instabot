import os
import re
import asyncio
import logging
import static_ffmpeg
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

static_ffmpeg.add_paths()

TOKEN = "7622123900:AAFdOgczhmAZ8S5ZFDcqhalvBH2uD6FpKfg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

user_video_data = {}

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
        filename = ydl.prepare_filename(info)
        
        artist = info.get('artist') or info.get('creator') or info.get('uploader') or "Ibojon"
        track = info.get('track') or info.get('alt_title')
        title = info.get('title', '')
        
        if not track:
            if " - " in title and not title.lower().startswith("video by"):
                parts = title.split(" - ", 1)
                artist, track = parts[0].strip(), parts[1].strip()
            else:
                track = "Musiqa"
        
        return filename, str(artist), str(track)

def extract_direct_audio(url: str, user_id: int):
    os.makedirs("downloads", exist_ok=True)
    out_base = f"downloads/{user_id}_audio"
    
    ydl_opts = {
        'outtmpl': f'{out_base}.%(ext)s',
        'format': 'best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    target_path = f"{out_base}.mp3"
    if os.path.exists(target_path):
        return target_path
        
    for f in os.listdir("downloads"):
        if f.startswith(f"{user_id}_audio"):
            return os.path.join("downloads", f)
    return None

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "Assalomu alaykum!\n\n"
        "Menga Instagram reels yoki video havolasini yuboring. Videoni va undagi qo'shiqni yuklab beraman."
    )

@dp.message(F.text.regexp(r'https?://(?:www\.)?instagram\.com/(?:reel|p|tv)/[A-Za-z0-9_-]+'))
async def handle_instagram_link(message: types.Message):
    url = clean_instagram_url(message.text.strip())
    status_msg = await message.answer("Video yuklanmoqda, kuting...")

    try:
        loop = asyncio.get_running_loop()
        video_path, artist, track = await loop.run_in_executor(None, download_video, url)

        user_video_data[message.from_user.id] = {
            'url': url,
            'artist': artist,
            'track': track
        }

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Musiqani yuklab olish", callback_data="get_music")],
            [InlineKeyboardButton(text="Guruhga qo'shish", url="https://t.me/Instavideodowland_bot?startgroup=true")]
        ])

        caption = "Videongiz tayyor! Ibojonga raxmat ayting! @Instavideodowland_bot"
        video_file = FSInputFile(video_path)
        await message.answer_video(video=video_file, caption=caption, reply_markup=keyboard)

        if os.path.exists(video_path):
            os.remove(video_path)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Video xatosi: {e}")
        await status_msg.edit_text("Yuklab bo'lmadi. Havola noto'g'ri yoki profil yopiq bo'lishi mumkin.")

@dp.callback_query(F.data == "get_music")
async def send_music_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = user_video_data.get(user_id)

    if not data:
        await callback.answer("Havola topilmadi. Videoni qaytadan yuboring.", show_alert=True)
        return

    await callback.answer("Musiqa tayyorlanmoqda...")
    status_music = await callback.message.reply("⏳ Musiqa yuklab olinmoqda...")

    try:
        loop = asyncio.get_running_loop()
        audio_file_path = await loop.run_in_executor(None, extract_direct_audio, data['url'], user_id)

        if audio_file_path and os.path.exists(audio_file_path):
            audio_file = FSInputFile(audio_file_path)
            track_name = data['track']
            artist_name = data['artist']

            # Markdown o'rniga oddiy matn (xatolik bermasligi uchun)
            caption = f"🎧 {artist_name} - {track_name}\n\nIbojonga raxmat ayting! @Instavideodowland_bot"
            
            await callback.message.reply_audio(
                audio=audio_file,
                caption=caption,
                title=track_name[:40],
                performer=artist_name[:30]
            )
            os.remove(audio_file_path)
            await status_music.delete()
        else:
            await status_music.edit_text("Musiqani yuklab bo'lmadi.")

    except Exception as e:
        logging.error(f"Audio xatosi: {e}")
        await status_music.edit_text("Musiqani ajratishda xatolik yuz berdi.")

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
