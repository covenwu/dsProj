# app.py

from flask import Flask, request, jsonify, render_template, Response, redirect, url_for, session, make_response
from openai import OpenAI
import os
import certifi
import json
import sqlite3
from datetime import datetime
import time
from download_routes import download_bp  # Import the Blueprint from download_routes.py

app = Flask(__name__)
app.secret_key = '123456'  # Set a secret key for session management

# Register the download blueprint
app.register_blueprint(download_bp)

# 数据库配置
DATABASE = 'chat_history1.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # 创建对话记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            problem_id INTEGER NOT NULL,
            problem_state TEXT NOT NULL,
            message_type TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def store_message(user_id, problem_id, problem_state, message_type, content):
    """存储消息到数据库"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO conversations (user_id, problem_id, problem_state, message_type, content)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, problem_id, problem_state, message_type, content))
    conn.commit()
    conn.close()

def fetch_user_history(user_id):
    """Fetch conversation history for a specific user"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT message_type, content 
        FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp
    ''', (user_id,))
    history = c.fetchall()
    conn.close()
    return [{'role': msg[0], 'content': msg[1]} for msg in history]

def get_recent_message(user_id):
    """Get the most recent problem state for a user"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT problem_id, problem_state
        FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (user_id,))
    result = c.fetchone()
    conn.close()
    
    # If user has no history, return default values
    if result is None:
        return (0, 'revise')  # Return a tuple with default values
    
    return result  # Return the entire tuple (problem_id, problem_state)

def get_recent_user_content(user_id):
    """Get the most recent user message content for a given user"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT content
        FROM conversations 
        WHERE user_id = ? AND message_type = 'user' AND problem_state = 'answer'
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (user_id,))
    result = c.fetchone()
    conn.close()
    
    # If user has no history, return empty string
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
                    try:
                        # 第一次 API 调用获取 reasoning
                        response = client.chat.completions.create(
                            model="deepseek-r1-250120", 
                            messages=messages,
                            stream=True
                        )
                        
                        for chunk in response:
                            try:
                                # Check if choices exist and are not empty
                                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                                    delta = None
                                    if hasattr(chunk.choices[0].delta, 'reasoning_content'):
                                        delta = chunk.choices[0].delta.reasoning_content
                                    if delta:
                                        reasoning_content += delta
                                        yield f"event: responding\ndata: {json.dumps({'content': delta, 'user_id': user_id})}\n\n"
                            except Exception as chunk_err:
                                print(f"Error processing chunk: {str(chunk_err)}")
                                # 继续处理，不中断流
                    except Exception as api_err:
                        print(f"API error: {str(api_err)}")
                        yield f"event: error\ndata: {json.dumps({'content': str(api_err), 'user_id': user_id})}\n\n"
                        yield f"event: done\ndata: {json.dumps({'user_id': user_id})}\n\n"
                        return
                        
                    # 发送额外消息
                    yield f"event: responding\ndata: {json.dumps({'content': '\n\n请根据老师的分析过程,对照你之前写的答案，写出你之前答案中的错误是什么，说明错误的原因是什么,有什么学习收获。', 'user_id': user_id})}\n\n"
                    
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
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            SELECT message_type, content, timestamp 
            FROM conversations 
            WHERE user_id = ? 
            ORDER BY timestamp
        ''', (user_id,))
        history = c.fetchall()
        conn.close()
       
        return jsonify([{
            'type': msg[0],
            'content': msg[1],
            'timestamp': msg[2]
        } for msg in history])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
    