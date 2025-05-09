import os
import telebot
import yt_dlp
import socket
import urllib3
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

# تنظیمات پایه
TOKEN = "8043273209:AAHYz7Wiabbz-ARgUN6dfaUnwoibybradyo"
DOWNLOAD_DIR = "downloads"
MAX_RETRIES = 3
TIMEOUT = 30

# تنظیمات پروکسی (برای کاربران ایرانی)
PROXY = {
    'http': 'http://username:password@proxy_ip:port',  # اطلاعات پروکسی خود را وارد کنید
    'https': 'http://username:password@proxy_ip:port'
}

# ایجاد پوشه دانلود
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# تنظیمات پیشرفته yt-dlp
ydl_opts = {
    'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
    'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'socket_timeout': TIMEOUT,
    'retries': MAX_RETRIES,
    'proxy': PROXY['http'],
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/'
    },
    'extract_flat': True,
    'force_ipv4': True,
    'ratelimit': 1000000,  # محدودیت سرعت دانلود (1MB/s)
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'geo_bypass': True,
    'geo_bypass_country': 'US'
}

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
executor = ThreadPoolExecutor(max_workers=4)

# دکوراتور مدیریت خطاهای پیشرفته
def advanced_error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except yt_dlp.DownloadError as e:
            if "HTTP Error 403" in str(e):
                return "🔒 خطای دسترسی (403)\nلطفاً از VPN/پروکسی معتبر استفاده کنید"
            elif "HTTP Error 404" in str(e):
                return "❌ ویدیو یافت نشد (404)\nلینک را بررسی کنید"
            elif "Tunnel connection failed" in str(e):
                return "🔌 خطای اتصال به پروکسی\nاطلاعات پروکسی را بررسی کنید"
            return f"❌ خطای دانلود: {str(e)}"
        except (socket.timeout, urllib3.exceptions.TimeoutError):
            return "⏳ زمان اتصال به پایان رسید\nلطفاً دوباره تلاش کنید"
        except Exception as e:
            return f"⚠️ خطای سیستمی: {str(e)}"
    return wrapper

@advanced_error_handler
def download_video(url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # بررسی اولیه ویدیو
        info = ydl.extract_info(url, download=False)
        
        # بررسی محدودیت‌ها
        if info.get('age_limit', 0) >= 18:
            raise Exception("🔞 این ویدیو محدودیت سنی دارد")
        
        if info.get('is_live', False):
            raise Exception("📡 ویدیوی زنده قابل دانلود نیست")
        
        if info.get('duration', 0) > 3600:  # بیش از 1 ساعت
            raise Exception("⏱ ویدیوهای بلندتر از 1 ساعت پشتیبانی نمی‌شوند")
        
        # دانلود واقعی
        ydl.download([url])
        return info

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_msg = """
🎬 <b>ربات دانلود حرفه‌ای یوتیوب</b>

🔹 لینک ویدیوی یوتیوب را ارسال کنید
🔹 حداکثر کیفیت: 720p
🔹 حداکثر مدت: 60 دقیقه

⚙️ <i>پشتیبانی فنی: @dev00111</i>
"""
    bot.reply_to(message, welcome_msg)

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    url = message.text.strip()
    
    # اعتبارسنجی پیشرفته لینک
    if not is_valid_youtube_url(url):
        bot.reply_to(message, "⚠️ لطفاً یک لینک معتبر یوتیوب وارد کنید\nمثال: https://youtu.be/dQw4w9WgXcQ")
        return
    
    # ارسال پیام وضعیت
    status_msg = bot.reply_to(message, "🔍 در حال بررسی ویدیو... لطفاً صبر کنید")
    
    # اجرای دانلود در پس‌زمینه
    def background_download():
        try:
            result = download_video(url)
            
            if isinstance(result, str):  # اگر خطا باشد
                bot.edit_message_text(result, message.chat.id, status_msg.message_id)
            else:  # اگر موفق باشد
                file_path = os.path.join(DOWNLOAD_DIR, f"{result['title']}.{result['ext']}")
                
                # ارسال ویدیو با نمایش پیشرفت
                with open(file_path, 'rb') as video_file:
                    bot.send_video(
                        chat_id=message.chat.id,
                        video=video_file,
                        caption=f"🎬 {result['title']}\n🕒 مدت: {result.get('duration_string', '?')}",
                        reply_to_message_id=message.message_id,
                        timeout=100
                    )
                
                # حذف فایل موقت
                os.remove(file_path)
                
        except Exception as e:
            bot.edit_message_text(f"⚠️ خطای غیرمنتظره: {str(e)}", message.chat.id, status_msg.message_id)
    
    executor.submit(background_download)

def is_valid_youtube_url(url):
    try:
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return False
            
        domains = ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com']
        if not any(d in parsed.netloc for d in domains):
            return False
            
        if parsed.netloc == 'youtu.be':
            return True
            
        if parsed.path == '/watch':
            query = parse_qs(parsed.query)
            return 'v' in query
            
        return True
    except:
        return False

if __name__ == '__main__':
    print("✅ ربات با موفقیت راه‌اندازی شد...")
    bot.infinity_polling()
