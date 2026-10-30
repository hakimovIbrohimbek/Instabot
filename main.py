import os
import re
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from shazamio import Shazam
from ytmusicapi import YTMusic

TOKEN = "7622123900:AAFdOgczhmAZ8S5ZFDcqhalvBH2uD6FpKfg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()
shazam = Shazam()
ytmusic = YTMusic()

user_links = {}
user_search_results = {}

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

def download_raw_audio(url: str):
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
        return ydl.prepare_filename(info)

def download_full_track(video_id: str):
    os.makedirs("downloads", exist_ok=True)
    out_path = f"downloads/{video_id}.mp3"
    ydl_opts = {
        'outtmpl': f'downloads/{video_id}.%(ext)s',
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    track_url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([track_url])
    
    # Ba'zi hollarda kengaytmasi avtomatik o'zgarishi mumkin
    for f in os.listdir("downloads"):
        if f.startswith(video_id):
            return os.path.join("downloads", f)
    return out_path

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "Assalomu alaykum!\n\n"
        "Instagram Reels yoki Post havolasini yuboring. Men videoni yuklab, ichidagi qo'shiqni to'liq varianti bilan topib beraman."
    )

@dp.message(F.text.regexp(r'https?://(?:www\.)?instagram\.com/(?:reel|p|tv)/[A-Za-z0-9_-]+'))
async def handle_instagram_link(message: types.Message):
    url = clean_instagram_url(message.text.strip())
    status_msg = await message.answer("Video yuklanmoqda, kuting...")

    try:
        loop = asyncio.get_running_loop()
        video_path = await loop.run_in_executor(None, download_video, url)

        user_links[message.from_user.id] = url

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Musiqani qidirish (Shazam)", callback_data="find_music")],
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

@dp.callback_query(F.data == "find_music")
async def find_music_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    url = user_links.get(user_id)

    if not url:
        await callback.answer("Havola topilmadi. Videoni qaytadan yuboring.", show_alert=True)
        return

    await callback.answer("Musiqa aniqlanmoqda...")
    status_msg = await callback.message.reply("🔍 Shazam orqali musiqa qidirilmoqda...")

    try:
        loop = asyncio.get_running_loop()
        audio_path = await loop.run_in_executor(None, download_raw_audio, url)

        # 1. Shazam orqali aniqlash
        track_artist = None
        track_title = None
        cover_image = None

        try:
            with open(audio_path, 'rb') as f:
                data = f.read()
            out = await shazam.recognize(data)
            track = out.get('track', {})
            if track:
                track_title = track.get('title')
                track_artist = track.get('subtitle')
                images = track.get('images', {})
                cover_image = images.get('coverart') or images.get('background')
        except Exception as sh_err:
            logging.error(f"Shazam xatosi: {sh_err}")

        # 2. Agar Shazam topmasa, to'g'ridan-to'g'ri videodagi audioni beramiz
        if not track_title or not track_artist:
            if os.path.exists(audio_path):
                audio_file = FSInputFile(audio_path)
                await callback.message.reply_audio(
                    audio=audio_file,
                    caption="Musiqa Shazam'dan topilmadi, videodagi audio yuklab berildi.\n@Instavideodowland_bot"
                )
                os.remove(audio_path)
            await status_msg.delete()
            return

        if os.path.exists(audio_path):
            os.remove(audio_path)

        # 3. YouTube Music'dan to'liq variantlarini qidirish
        search_query = f"{track_artist} {track_title}"
        results = await loop.run_in_executor(None, ytmusic.search, search_query, "songs")
        songs = [r for r in results if r.get('videoId')][:5]

        if not songs:
            # Qo'shiqlar chiqmasa oddiy qidiruv qilib ko'ramiz
            results = await loop.run_in_executor(None, ytmusic.search, search_query)
            songs = [r for r in results if r.get('videoId')][:5]

        # Foydalanuvchi tanlashi uchun xotirada saqlash
        user_search_results[user_id] = {str(i+1): s for i, s in enumerate(songs)}

        # Matn tayyorlash (xuddi skrinshotdagi uslubda)
        text = f"Ижрочи: **{track_artist}**\nҚўшиқ номи: **{track_title}**\n\n"
        for i, song in enumerate(songs, 1):
            dur = song.get('duration', '')
            dur_str = f" {dur}" if dur else ""
            text += f"{i}. {song.get('title', 'Noma\'lum')}{dur_str}\n"

        # Tugmalar: [1] [2] [3] [4] [5]
        buttons_row = [
            InlineKeyboardButton(text=str(i), callback_data=f"dl_song_{i}") 
            for i in range(1, len(songs) + 1)
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons_row])

        if cover_image:
            await callback.message.reply_photo(photo=cover_image, caption=text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await callback.message.reply(text, reply_markup=keyboard, parse_mode="Markdown")

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_msg.edit_text("Qo'shiqni aniqlashda xatolik yuz berdi.")

@dp.callback_query(F.data.startswith("dl_song_"))
async def download_selected_song(callback: types.CallbackQuery):
    num = callback.data.replace("dl_song_", "")
    user_id = callback.from_user.id
    user_songs = user_search_results.get(user_id, {})
    selected_song = user_songs.get(num)

    if not selected_song:
        await callback.answer("Qo'shiq muddati tugagan, qayta qidiring.", show_alert=True)
        return

    await callback.answer(f"{num}-musiqa yuklanmoqda...")
    status = await callback.message.reply(f"⏳ **{selected_song.get('title')}** yuklab olinmoqda...", parse_mode="Markdown")

    try:
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(None, download_full_track, selected_song['videoId'])

        if os.path.exists(file_path):
            audio_file = FSInputFile(file_path)
            await callback.message.reply_audio(
                audio=audio_file,
                caption="Ibojonga raxmat ayting! @Instavideodowland_bot",
                title=selected_song.get('title', 'Audio'),
                performer=selected_song.get('artists', [{}])[0].get('name', 'Ibojon')
            )
            os.remove(file_path)

        await status.delete()

    except Exception as e:
        logging.error(f"Musiqa yuklashda xato: {e}")
        await status.edit_text("Ushbu variantni yuklab bo'lmadi.")

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
