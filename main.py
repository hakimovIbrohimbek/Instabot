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

def download_audio_and_meta(url: str):
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
        file_path = ydl.prepare_filename(info)
        
        # Instagram ichidagi metadata ma'lumotlarini qidirish
        track_name = info.get('track') or info.get('alt_title')
        artist_name = info.get('artist') or info.get('creator') or info.get('uploader')
        description = info.get('description', '')

        return file_path, artist_name, track_name, description

def download_youtube_track(video_id: str):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        'outtmpl': f'downloads/{video_id}.%(ext)s',
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    track_url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(track_url, download=True)
        return ydl.prepare_filename(info)

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "Assalomu alaykum!\n\n"
        "Menga Instagram reels yoki video havolasini yuboring. Videoni va undagi qo'shiqni to'liq varianti bilan topib beraman."
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
            [InlineKeyboardButton(text="Musiqani yuklab olish", callback_data="find_music")],
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
        await status_msg.edit_text("Yuklab bo'lmadi. Profil yopiq yoki havola xato bo'lishi mumkin.")

@dp.callback_query(F.data == "find_music")
async def find_music_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    url = user_links.get(user_id)

    if not url:
        await callback.answer("Havola topilmadi. Videoni qaytadan yuboring.", show_alert=True)
        return

    await callback.answer("Musiqa aniqlanmoqda...")
    status_msg = await callback.message.reply("🔍 Musiqa barcha manbalardan qidirilmoqda...")

    try:
        loop = asyncio.get_running_loop()
        audio_path, insta_artist, insta_track, description = await loop.run_in_executor(None, download_audio_and_meta, url)

        found_title = None
        found_artist = None

        # 1-usul: Instagram rasmiy ma'lumotlarini tekshirish
        if insta_track and not str(insta_track).lower().startswith("original"):
            found_title = insta_track
            found_artist = insta_artist if insta_artist else ""

        # 2-usul: Agar Instagram nomini bermagan bo'lsa, Shazam orqali tekshirish
        if not found_title:
            try:
                out = await shazam.recognize(audio_path)
                track = out.get('track', {})
                if track:
                    found_title = track.get('title')
                    found_artist = track.get('subtitle')
            except Exception as sh_err:
                logging.error(f"Shazam xatosi: {sh_err}")

        # 3-usul: Agar umuman topilmasa, toza audio faylni o'zini yuboramiz
        if not found_title:
            if os.path.exists(audio_path):
                audio_file = FSInputFile(audio_path)
                await callback.message.reply_audio(
                    audio=audio_file,
                    caption="Ibojonga raxmat ayting! @Instavideodowland_bot",
                    title="Audio",
                    performer="Ibojon"
                )
                os.remove(audio_path)
            await status_msg.delete()
            return

        if os.path.exists(audio_path):
            os.remove(audio_path)

        # 4-usul: YouTube Music orqali 5 xil variantini qidirib topish
        search_query = f"{found_artist} {found_title}".strip()
        search_res = await loop.run_in_executor(None, ytmusic.search, search_query, "songs")
        songs = [s for s in search_res if s.get('videoId')][:5]

        if not songs:
            search_res = await loop.run_in_executor(None, ytmusic.search, search_query)
            songs = [s for s in search_res if s.get('videoId')][:5]

        user_search_results[user_id] = {str(i+1): s for i, s in enumerate(songs)}

        # Xabarni chiroyli formatda shakllantirish
        text = f"🎧 **{found_artist} - {found_title}**\n\n🔍 **{found_artist} - {found_title}**\n\n"
        for i, s in enumerate(songs, 1):
            dur = s.get('duration', '')
            dur_str = f" {dur}" if dur else ""
            text += f"{i}. {s.get('title', 'Noma\'lum')}{dur_str}\n"

        buttons = [
            InlineKeyboardButton(text=str(i), callback_data=f"sel_song_{i}")
            for i in range(1, len(songs) + 1)
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])

        await callback.message.reply(text, reply_markup=keyboard, parse_mode="Markdown")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Umumiy xatolik: {e}")
        await status_msg.edit_text("Musiqani yuklashda xatolik yuz berdi.")

@dp.callback_query(F.data.startswith("sel_song_"))
async def download_selected_song(callback: types.CallbackQuery):
    num = callback.data.replace("sel_song_", "")
    user_id = callback.from_user.id
    user_songs = user_search_results.get(user_id, {})
    song_info = user_songs.get(num)

    if not song_info:
        await callback.answer("Qidiruv muddati tugagan, qaytadan urinib ko'ring.", show_alert=True)
        return

    await callback.answer(f"{num}-musiqa yuklanmoqda...")
    status = await callback.message.reply(f"⏳ **{song_info.get('title')}** yuklab olinmoqda...", parse_mode="Markdown")

    try:
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(None, download_youtube_track, song_info['videoId'])

        if os.path.exists(file_path):
            audio_file = FSInputFile(file_path)
            await callback.message.reply_audio(
                audio=audio_file,
                caption="Ibojonga raxmat ayting! @Instavideodowland_bot",
                title=song_info.get('title', 'Audio'),
                performer=song_info.get('artists', [{}])[0].get('name', 'Ibojon')
            )
            os.remove(file_path)

        await status.delete()
    except Exception as e:
        logging.error(f"Yuklash xatosi: {e}")
        await status.edit_text("Ushbu musiqa variantini yuklab bo'lmadi.")

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
