# app.py

from flask import Flask, request, jsonify, render_template, Response, redirect, url_for, session, make_response
from openai import OpenAI
import os
import certifi
import json
import pymysql  # 替换sqlite3为pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB  # 导入连接池
from datetime import datetime
import time
from download_routes import download_bp  # Import the Blueprint from download_routes.py

app = Flask(__name__)
app.secret_key = '123456'  # Set a secret key for session management

# Register the download blueprint
app.register_blueprint(download_bp)

# MySQL配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'chat_user',  # 生产环境用户
    'password': '12345678',  # 生产环境密码
    'database': 'chat_system',  # 替换为你的数据库名
    'charset': 'utf8mb4'
}

# 创建数据库连接池
pool = PooledDB(
    creator=pymysql,
    maxconnections=50,  # 最大连接数
    mincached=5,        # 初始连接数
    maxcached=20,       # 最大空闲连接数
    blocking=True,      # 连接池满时是否阻塞等待
    **DB_CONFIG
)

def get_connection():
    """获取数据库连接"""
    return pool.connection()

def init_db():
    """初始化数据库"""
    conn = get_connection()
    cursor = conn.cursor()
    # 创建对话记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            problem_id INT NOT NULL,
            problem_state VARCHAR(20) NOT NULL,
            message_type VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id),
            INDEX idx_problem_id (problem_id)
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

def store_message(user_id, problem_id, problem_state, message_type, content):
    """存储消息到数据库"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO conversations (user_id, problem_id, problem_state, message_type, content)
        VALUES (%s, %s, %s, %s, %s)
    ''', (user_id, problem_id, problem_state, message_type, content))
    conn.commit()
    cursor.close()
    conn.close()

def fetch_user_history(user_id):
    """获取用户的对话历史"""
    conn = get_connection()
    cursor = conn.cursor(DictCursor)  # 使用字典游标
    cursor.execute('''
        SELECT message_type, content 
        FROM conversations 
        WHERE user_id = %s 
        ORDER BY timestamp
    ''', (user_id,))
    history = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{'role': msg['message_type'], 'content': msg['content']} for msg in history]

def get_recent_message(user_id):
    """获取用户最近的消息状态"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT problem_id, problem_state
        FROM conversations 
        WHERE user_id = %s 
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    # 如果用户没有历史记录，返回默认值
    if result is None:
        return (0, 'revise')  # 返回元组(problem_id, problem_state)
    
    return result  # 返回元组(problem_id, problem_state)

def get_recent_user_content(user_id):
    """获取用户最近的用户消息内容"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT content
        FROM conversations 
        WHERE user_id = %s AND message_type = 'user' AND problem_state = 'answer'
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    # 如果用户没有历史记录，返回空字符串
    if result is None:
        return ""
    
    return result[0]

# 确保在应用启动时初始化数据库
init_db()

# Set SSL certificate environment variable
os.environ['SSL_CERT_FILE'] = certifi.where()

# Initialize OpenAI client with DeepSeek base URL
#https://www.ohmygpt.com/settings
client = OpenAI(
    #火山引擎， https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%22PageSize%22%3A100%2C%22PageNumber%22%3A1%2C%22Filter%22%3A%7B%7D%7D&OpenTokenDrawer=false&projectName=undefined
    api_key="e4aa2de7-78a9-4793-b132-ddf79269a35e",
    base_url="https://ark.cn-beijing.volces.com/api/v3"
)

conversation_history = {}
# Remove global variables since we're using the database
# reasoning_content = ""
# user_problem = ""


# Route for the welcome page
@app.route('/welcome1')
def welcome1():
    return render_template('welcome1.html')

# Route for the index page
@app.route('/index1')
def index1():
    user_id = session.get('userID')  # Get userID from the session
    return render_template('index1.html', user_id=user_id)

# Route for the root URL
@app.route('/')
def home():
    #revise
    return redirect('/welcome1') 
    #return redirect(url_for('welcome1'))  # Redirect to the welcome page

@app.route('/set_user', methods=['POST'])
def set_user():
    user_id = request.form.get('userID')
    session['userID'] = user_id  # Store userID in session

    # Initialize conversation history for the new user
    conversation_history[user_id] = []
    #revise
    #return redirect('/index1') 
    return redirect(url_for('index1'))  # Redirect to index page

@app.route('/logout')
def logout():
    user_id = session.get('userID')
    if user_id in conversation_history:
        del conversation_history[user_id]  # Remove user's conversation history
    session.pop('userID', None)  # Remove userID from session
    #revise
    #return redirect('/welcome1') 
    return redirect(url_for('welcome1'))  # Redirect to welcome page

def format_sse(event, data, user_id):
    """Helper function to format SSE data with user_id"""
    data['user_id'] = user_id  # Add user_id to the data
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

@app.route('/api/stream')
def stream():
    try:
        user_prompt = request.args.get('prompt')
        user_id = request.args.get('userID')  # Get userID from request parameters
        
        # 添加调试日志
        print(f"Received request - user prompt, user_id: {user_id}")

        # 修改验证逻辑
        if not user_prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        if user_id not in conversation_history:
            conversation_history[user_id] = []  # Initialize if not present
        
        # Fetch user's conversation history
        user_history = fetch_user_history(user_id)
        conversation_history[user_id].extend(user_history)

        def generate():
            try:
                # Get current problem state from database
                problem_state = get_recent_message(user_id)[1]
                problem_id = get_recent_message(user_id)[0]
                    
                if problem_state == "revise":
                    problem_state = "answer"
                    problem_id = problem_id + 1
                                            
                    yield f"event: responding\ndata: {json.dumps({'content': '请先写下你对这道练习中每一问的答案，完成所有回答后，再点击发送按钮。', 'user_id': user_id})}\n\n"
                    
                    # 更新对话历史
                    conversation_history[user_id].append({"role": "user", "content": user_prompt})
                    conversation_history[user_id].append({"role": "assistant", "content": "请先写下你的答案"})
                    
                    store_message(user_id, problem_id, problem_state, 'user', user_prompt)
                    store_message(user_id, problem_id, problem_state, 'assistant', "请先写下你的答案")
                    
                elif problem_state == "answer":
                    problem_state = "thinking"
                
                    # Get the user's problem from their most recent message
                    user_problem = get_recent_user_content(user_id)
                    
                    print(f"get user problem: {user_problem}")
                    
                    messages = [{"role": "user", "content": user_problem}]
                        
                    # 安全包装 API 调用
                    reasoning_content = ""
                    stream_completed = False
                    try:
                        # 第一次 API 调用获取 reasoning
                        response = client.chat.completions.create(
                            model="deepseek-r1-250120", 
                            messages=messages,
                            stream=True
                        )
                        
                        for chunk in response:
                            try:
                                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                                    delta = None
                                    if hasattr(chunk.choices[0].delta, 'reasoning_content'):
                                        delta = chunk.choices[0].delta.reasoning_content
                                        
                                    # Check for finish_reason
                                    if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason is not None:
                                        print(f"Stream finished with reason: {chunk.choices[0].finish_reason}")
                                        stream_completed = True
                                    
                                    if delta:
                                        reasoning_content += delta
                                        message_data = json.dumps({'content': delta, 'user_id': user_id})
                                        yield f"event: responding\ndata: {message_data}\n\n"
                            except Exception as chunk_err:
                                print(f"Error processing chunk: {str(chunk_err)}")
                        
                        # Mark as completed if we processed all chunks without error
                        stream_completed = True
                        print("Stream processing completed successfully")
                        
                    except Exception as api_err:
                        print(f"API error: {str(api_err)}")
                        error_data = json.dumps({'content': str(api_err), 'user_id': user_id})
                        yield f"event: error\ndata: {error_data}\n\n"
                    
                    finally:
                        # Always mark as completed in the finally block
                        if not stream_completed:
                            print("Stream ended without explicit finish_reason, marking as completed")
                        
                        # 确保在流处理后执行，无论流如何结束
                        print("准备发送额外消息")
                        # 发送额外消息
                        message_data = json.dumps({'content': '\n\n请根据老师的分析过程,对照你之前写的答案，写出你之前答案中的错误是什么，说明错误的原因是什么,有什么学习收获。', 'user_id': user_id})
                        yield f"event: responding\ndata: {message_data}\n\n"
                        
                        conversation_history[user_id].append({"role": "user", "content": user_prompt})
                        conversation_history[user_id].append({"role": "assistant", "content": reasoning_content})
                        
                        # Update conversation history
                        store_message(user_id, problem_id, problem_state, 'user', user_prompt)
                        store_message(user_id, problem_id, problem_state, 'assistant', reasoning_content)
                        
                elif problem_state == "thinking":
                    problem_state = "revise"
                    
                    yield f"event: responding\ndata: {json.dumps({'content': '恭喜你完成本题的学习，你可以进入下一练习题的学习，或者退出本系统。', 'user_id': user_id})}\n\n"
                    
                    conversation_history[user_id].append({"role": "user", "content": user_prompt})
                    conversation_history[user_id].append({"role": "assistant", "content": "恭喜你完成本题的学习，你可以进入下一练习题的学习，或者退出本系统。"})
                    
                    store_message(user_id, problem_id, problem_state, 'user', user_prompt)
                    store_message(user_id, problem_id, problem_state, 'assistant', "恭喜你完成本题的学习，你可以进入下一练习题的学习，或者退出本系统。")
                
                # 确保发送完成事件
                yield f"event: done\ndata: {json.dumps({'user_id': user_id})}\n\n"
                
            except Exception as e:
                print(f"Error in generate: {str(e)}")
                yield f"event: error\ndata: {json.dumps({'content': str(e), 'user_id': user_id})}\n\n"
                yield f"event: done\ndata: {json.dumps({'user_id': user_id})}\n\n"

        # 返回响应并添加必要的头部
        response = Response(generate(), mimetype='text/event-stream')
        response.headers.add('Cache-Control', 'no-cache')
        response.headers.add('X-Accel-Buffering', 'no')  # 告诉 Nginx 不要缓冲
        return response
    
    except Exception as e:
        print(f"Error in stream: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 添加获取历史记录的路由
@app.route('/api/history/<user_id>')
def get_history(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor(DictCursor)  # 使用字典游标
        cursor.execute('''
            SELECT message_type, content, timestamp 
            FROM conversations 
            WHERE user_id = %s 
            ORDER BY timestamp
        ''', (user_id,))
        history = cursor.fetchall()
        cursor.close()
        conn.close()
       
        return jsonify([{
            'type': msg['message_type'],
            'content': msg['content'],
            'timestamp': msg['timestamp']
        } for msg in history])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 添加状态检查路由
@app.route('/api/check-status')
def check_status():
    try:
        user_id = request.args.get('userID')
        if not user_id:
            return jsonify({"error": "No user ID provided"}), 400
            
        # 获取用户当前状态
        problem_state = get_recent_message(user_id)[1]
        problem_id = get_recent_message(user_id)[0]
        
        return jsonify({
            "user_id": user_id,
            "problem_id": problem_id,
            "problem_state": problem_state,
            "status": "ok"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 添加确认更新路由 - 如果客户端连接断开，可以调用此路由确保状态更新
@app.route('/api/confirm-update')
def confirm_update():
    try:
        user_id = request.args.get('userID')
        if not user_id:
            return jsonify({"error": "No user ID provided"}), 400
            
        # 获取用户当前状态
        problem_state = get_recent_message(user_id)[1]
        problem_id = get_recent_message(user_id)[0]
        
        # 如果当前状态是 answer，尝试移动到 thinking
        if problem_state == "answer":
            problem_state = "thinking"
            # 确保之前的消息已存储
            store_message(user_id, problem_id, problem_state, 'system', "Stream ended but status updated")
            print(f"通过 confirm-update 为用户 {user_id} 更新状态: {problem_state}")
            
        return jsonify({
            "user_id": user_id,
            "problem_id": problem_id,
            "problem_state": problem_state,
            "status": "updated"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
    