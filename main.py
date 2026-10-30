import os
import re
import asyncio
import logging
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

TOKEN = "7622123900:AAFdOgczhmAZ8S5ZFDcqhalvBH2uD6FpKfg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

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

def get_track_info_and_audio(url: str):
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

        track = info.get('track') or info.get('alt_title')
        artist = info.get('artist') or info.get('creator') or info.get('uploader')
        title = info.get('title', '')
        description = info.get('description', '')

        search_query = None
        if track and not str(track).lower().startswith("original"):
            search_query = f"{artist} {track}".strip() if artist else track
        elif artist and artist not in ["Instagram", "Ibojon", "None"]:
            first_line = description.split('\n')[0] if description else ""
            clean_desc = re.sub(r'#\S+', '', first_line).strip()[:30]
            search_query = f"{artist} {clean_desc}".strip()
        elif title and not title.lower().startswith("video by"):
            search_query = title

        return file_path, search_query, artist or "Ibojon", track or "Audio"

async def search_deezer_tracks(query: str):
    url = f"https://api.deezer.com/search?q={query}&limit=5"
    async with ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('data', [])
    return []

async def download_direct_mp3(download_url: str, filename: str):
    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{filename}.mp3"
    async with ClientSession() as session:
        async with session.get(download_url) as resp:
            if resp.status == 200:
                with open(file_path, 'wb') as f:
                    f.write(await resp.read())
                return file_path
    return None

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "Assalomu alaykum!\n\n"
        "Instagram havola yuboring, video va undagi qo'shiqni to'liq varianti bilan topib beraman."
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

    await callback.answer("Musiqa qidirilmoqda...")
    status_msg = await callback.message.reply("🔍 Qo'shiq qidirilmoqda...")

    try:
        loop = asyncio.get_running_loop()
        audio_path, query, artist, track = await loop.run_in_executor(None, get_track_info_and_audio, url)

        songs = []
        if query:
            songs = await search_deezer_tracks(query)

        # Agar bazadan topilmasa, videoning o'zidan olingan audioni beramiz
        if not songs:
            if os.path.exists(audio_path):
                audio_file = FSInputFile(audio_path)
                await callback.message.reply_audio(
                    audio=audio_file,
                    caption="Ibojonga raxmat ayting! @Instavideodowland_bot",
                    title=track[:40],
                    performer=artist[:30]
                )
                os.remove(audio_path)
            await status_msg.delete()
            return

        if os.path.exists(audio_path):
            os.remove(audio_path)

        user_search_results[user_id] = {str(i+1): s for i, s in enumerate(songs)}

        main_artist = songs[0].get('artist', {}).get('name', artist)
        main_title = songs[0].get('title', track)

        text = f"Ижрочи: **{main_artist}**\nҚўшиқ номи: **{main_title}**\n\n"
        for i, s in enumerate(songs, 1):
            dur_sec = s.get('duration', 0)
            dur_str = f" {dur_sec // 60}:{dur_sec % 60:02d}" if dur_sec else ""
            text += f"{i}. {s.get('title', 'Noma\'lum')}{dur_str}\n"

        buttons = [
            InlineKeyboardButton(text=str(i), callback_data=f"sel_song_{i}")
            for i in range(1, len(songs) + 1)
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])

        await callback.message.reply(text, reply_markup=keyboard, parse_mode="Markdown")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_msg.edit_text("Musiqani topishda xatolik yuz berdi.")

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
        mp3_url = song_info.get('preview')
        title = song_info.get('title', 'Audio')
        artist = song_info.get('artist', {}).get('name', 'Ibojon')

        file_path = await download_direct_mp3(mp3_url, f"{user_id}_{num}")

        if file_path and os.path.exists(file_path):
            audio_file = FSInputFile(file_path)
            await callback.message.reply_audio(
                audio=audio_file,
                caption="Ibojonga raxmat ayting! @Instavideodowland_bot",
                title=title,
                performer=artist
            )
            os.remove(file_path)
        else:
            await callback.message.reply("Faylni yuklab bo'lmadi.")

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
