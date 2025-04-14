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
    'database': 'que_system',  # 数据库名
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
            message_type VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_id (user_id)
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

def store_message(user_id, message_type, content):
    """存储消息到数据库"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO conversations (user_id, message_type, content)
        VALUES (%s, %s, %s)
    ''', (user_id, message_type, content))
    conn.commit()
    cursor.close()
    conn.close()

def fetch_user_history(user_id):
    """Fetch conversation history for a specific user"""
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

# 确保在应用启动时初始化数据库
init_db()

# Set SSL certificate environment variable
os.environ['SSL_CERT_FILE'] = certifi.where()

# Initialize OpenAI client with DeepSeek base URL
#https://www.ohmygpt.com/settings
client = OpenAI(
    #火山引擎， https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%22PageSize%22%3A100%2C%22PageNumber%22%3A1%2C%22Filter%22%3A%7B%7D%7D&OpenTokenDrawer=false&projectName=undefined
    api_key="sk-RD1EZ9gA0dde3eF262f0T3BLbkFJ6fabd1439bA74A159497",#"sk-UXCWFj2Md7688d70e7deT3BLbkFJ6696f0FAb26746E78Dd2",#e4aa2de7-78a9-4793-b132-ddf79269a35e",#"sk-eb1a5dee66374fb7bac030255fcd07f2",
    base_url="https://aigptx.top/v1"#"https://www.ohmygpt.com/v1"#"https://api.deepseek.com/"
)

# Dictionary to hold conversation history for each user
conversation_history = {}

# Route for the welcome page
@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

# Route for the index page
@app.route('/index')
def index():
    user_id = session.get('userID')  # Get userID from the session
    return render_template('index.html', user_id=user_id)

# Route for the root URL
@app.route('/')
def home():
    return redirect(url_for('welcome'))  # Redirect to the welcome page

@app.route('/set_user', methods=['POST'])
def set_user():
    user_id = request.form.get('userID')
    session['userID'] = user_id  # Store userID in session

    # Initialize conversation history for the new user
    conversation_history[user_id] = []

    return redirect(url_for('index'))  # Redirect to index page

@app.route('/logout')
def logout():
    user_id = session.get('userID')
    if user_id in conversation_history:
        del conversation_history[user_id]  # Remove user's conversation history
    session.pop('userID', None)  # Remove userID from session
    return redirect(url_for('welcome'))  # Redirect to welcome page

def format_sse(event, data):
    """Helper function to format SSE data"""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

@app.route('/api/stream')
def stream():
    try:
        user_prompt = request.args.get('prompt')
        user_id = request.args.get('userID')  # Get userID from request parameters
        
        # Debug log
        print(f"Received request - user prompt, user_id: {user_id}")

        if not user_prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        if user_id not in conversation_history:
            conversation_history[user_id] = []  # Initialize if not present

        # Fetch user's conversation history
        user_history = fetch_user_history(user_id)
        conversation_history[user_id].extend(user_history)

        def generate():
            try:
                messages = []
                
                if conversation_history[user_id]:
                    messages.extend(conversation_history[user_id])
                    messages.append({"role": "user", "content": user_prompt})
                    
                    response = client.chat.completions.create(
                        model="chatgpt-4o-latest",
                        messages=messages,
                        stream=True
                    )
                    
                    assistant_response = ""
                    for chunk in response:
                        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                            if hasattr(chunk.choices[0].delta, 'content'):
                                delta = chunk.choices[0].delta.content
                                if delta:
                                    assistant_response += delta
                                    yield format_sse("responding", {"content": delta})
                        else:
                            print("No choices found in the response.")
                            yield format_sse("error", {"content": "No choices found in the response."})
                
                    # Update conversation history for the user
                    conversation_history[user_id].append({"role": "user", "content": user_prompt})
                    conversation_history[user_id].append({"role": "assistant", "content": assistant_response})
                    store_message(user_id, 'user', user_prompt)
                    store_message(user_id, 'assistant', assistant_response)

                else:
                    # Handle the case where there is no conversation history
                    system_prompt = """
                    ##角色
                    你是一位历史老师,与你交互的用户是中学生。请你根据用户提供的练习题,其中包括若干史料和若干题目(problem),为每个题目分别设计苏格拉底式引导问题链,确保每个问题链的核心问题(core question)数量控制在 2 - 3 个。

                    ##技能
                    ###技能 1: 与学生互动答题
                    1. 清晰展示第一个题目，展示后即等待用户输入答案，不进行任何提前模拟回答或跳过用户输入的操作，直接显示问题内容，也不附加任何假设性回答或解释，展示后等待用户输入。

                    2. 当收到用户答案后，判断答案正确性：

                        2.1 若答案完全正确：直接展示下一个题目，展示后继续等待用户输入。

                        2.2 若答案不完全正确，或者错误：不直接显示正确答案，而是从该题目对应的苏格拉底式引导问题链中取出第一个核心问题，直接显示问题内容，也不附加任何假设性回答或解释，展示后等待用户输入。

                    3. 收到针对引导核心问题的用户答案后，判断答案正确性：

                        3.1 若答案正确：继续展示同一问题链的下一个核心问题，展示后等待用户输入。

                        3.2 若答案错误：先提示线索（如 "注意朝代时间顺序"），然后等待用户再次回答；若用户再次回答仍错误，直接给出正确答案并展示下一核心问题，展示后等待用户输入。

                    4. 当完成当前问题链的所有核心问题(core question)后，自动进入下一个题目(problem)。

                    5. 每个练习题的所有题目完成学习后，用一句话总结学习成果并鼓励用户，然后告知用户可以继续下一个练习题的学习或者退出系统。

                    ##限制
                    1. 严禁提前模拟回答任何问题，必须严格等待用户输入。

                    2. 仅围绕用户提供的历史史料题展开互动，不回答与题目无关的话题。

                    3. 回答需按照上述技能要求的流程进行，不可偏离流程框架。
                    
                    ##注意
                    1. 北魏在唐朝之前
                    """
                    messages = [{'role': 'system', 'content': system_prompt}]
                    messages.append({"role": "user", "content": user_prompt})
                    
                    response = client.chat.completions.create(
                        model="chatgpt-4o-latest",
                        messages=messages,
                        stream=True
                    )
                    
                    content = ""
                    for chunk in response:
                        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                            if hasattr(chunk.choices[0].delta, 'content'):
                                delta = chunk.choices[0].delta.content
                                if delta:
                                    content += delta
                                    yield format_sse("responding", {"content": delta})
                        else:
                            print("No choices found in the response.")
                            yield format_sse("error", {"content": "No choices found in the response."})
                    
                    # Update conversation history
                    conversation_history[user_id].append({"role": "system", "content": system_prompt})
                    conversation_history[user_id].append({"role": "user", "content": user_prompt})
                    conversation_history[user_id].append({"role": "assistant", "content": content})
                    
                    store_message(user_id, 'system', system_prompt)
                    store_message(user_id, 'user', user_prompt)
                    store_message(user_id, 'assistant', content)
                
                yield format_sse("done", {})
                
            except Exception as e:
                print(f"Error in generate: {str(e)}")
                yield format_sse("error", {"content": str(e)})

        return Response(generate(), mimetype='text/event-stream')
    
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
            'role': msg['message_type'],
            'content': msg['content'],
            'timestamp': str(msg['timestamp'])
        } for msg in history])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route for the download page
@app.route('/download')
def download_page():
    user_id = session.get('userID')  # Get userID from the session
    if not user_id:
        return redirect(url_for('welcome'))  # Redirect to welcome if not logged in
    return render_template('download.html', user_id=user_id)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    