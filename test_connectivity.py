import socket

try:
    socket.create_connection(("api.telegram.org", 443), timeout=5)
    print("✅ اتصال به api.telegram.org برقرار است. مشکل چیز دیگری است.")
except OSError:
    print("❌ نمی‌توان به api.telegram.org وصل شد. اینترنت یا شبکه این آدرس را مسدود کرده.")