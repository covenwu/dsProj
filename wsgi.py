from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from app import app as app1
from app1 import app as app2

# 创建应用分发器
application = DispatcherMiddleware(app1, {
    '/app1': app2  # app1.py 的应用将在 /app1 路径下访问
})

if __name__ == "__main__":
    # 开发环境下运行
    run_simple('localhost', 5000, application, use_reloader=True)