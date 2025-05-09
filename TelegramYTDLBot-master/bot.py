import os
import telebot
import yt_dlp
from urllib.parse import urlparse

# تنظیمات پایه
TOKEN = "8043273209:AAHYz7Wiabbz-ARgUN6dfaUnwoibybradyo"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# تنظیمات پروکسی با احراز هویت
PROXY = {
    'http': 'http://username:password@proxy_ip:port',  # اطلاعات واقعی خود را وارد کنید
    'https': 'http://username:password@proxy_ip:port'
}

# تنظیمات yt-dlp
ydl_opts = {
    'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'proxy': PROXY['http'],
    'socket_timeout': 30,
    'retries': 5,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept-Language': 'en-US,en;q=0.9'
    },
    'extract_flat': True
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and \
               any(d in result.netloc for d in ['youtube.com', 'youtu.be'])
    except:
        return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🎬 ربات دانلود یوتیوب آماده خدمت!\nلینک ویدیو را ارسال کنید")

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    if not is_valid_url(message.text):
        bot.reply_to(message, "⚠️ لینک معتبر یوتیوب وارد کنید")
        return
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(message.text, download=False)
            file_path = ydl.prepare_filename(info)
            
            # دانلود با نمایش پیشرفت
            @ydl.add_progress_hook
            def progress_hook(d):
                if d['status'] == 'downloading':
                    print(f"Downloading: {d['_percent_str']}")
            
            ydl.download([message.text])
            
            # ارسال ویدیو
            with open(file_path, 'rb') as f:
                bot.send_video(message.chat.id, f, caption=f"✅ {info['title']}")
            
            # حذف فایل موقت
            os.remove(file_path)
            
    except Exception as e:
        error_msg = str(e)
        if "407 Proxy Authentication Required" in error_msg:
            error_msg = "❌ خطای احراز هویت پروکسی\nلطفاً اطلاعات پروکسی را بررسی کنید"
        elif "403 Forbidden" in error_msg:
            error_msg = "🔒 خطای دسترسی\nاز VPN استفاده کنید"
        bot.reply_to(message, error_msg)

if __name__ == '__main__':
    print("✅ ربات آماده به کار است...")
    bot.infinity_polling()
