# app.py

from flask import Flask, request, jsonify, render_template, Response
from openai import OpenAI
import os
import certifi
import json
import sqlite3
from datetime import datetime
import time

app = Flask(__name__)

# 数据库配置
DATABASE = 'chat_history.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # 创建对话记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            message_type TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def store_message(session_id, message_type, content):
    """存储消息到数据库"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO conversations (session_id, message_type, content)
        VALUES (?, ?, ?)
    ''', (session_id, message_type, content))
    conn.commit()
    conn.close()

# 确保在应用启动时初始化数据库
init_db()

# Set SSL certificate environment variable
os.environ['SSL_CERT_FILE'] = certifi.where()

# Initialize OpenAI client with DeepSeek base URL
#https://www.ohmygpt.com/settings
client = OpenAI(
    #火山引擎， https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%22PageSize%22%3A100%2C%22PageNumber%22%3A1%2C%22Filter%22%3A%7B%7D%7D&OpenTokenDrawer=false&projectName=undefined
    api_key="sk-RD1EZ9gA0dde3eF262f0T3BLbkFJ6fabd1439bA74A159497",#"sk-UXCWFj2Md7688d70e7deT3BLbkFJ6696f0FAb26746E78Dd2",#e4aa2de7-78a9-4793-b132-ddf79269a35e",#"sk-eb1a5dee66374fb7bac030255fcd07f2",
    base_url="https://www.ohmygpt.com/v1"#"https://api.deepseek.com/"
)

conversation_history = []

@app.route('/')
def index():
    try:

        global conversation_history
        #conversation_history = []
        #return render_template('index.html')
        # 生成新的会话ID
        session_id = datetime.now().strftime("%Y%m%d%H%M%S")
        #return render_template('index.html')
        return render_template('index.html', session_id=session_id)
    except Exception as e:
        print(f"Error rendering template: {str(e)}")
        return str(e), 500

def format_sse(event, data):
    """Helper function to format SSE data"""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

@app.route('/api/stream')
def stream():
    try:
        user_prompt = request.args.get('prompt')
        session_id = request.args.get('session_id')
        
        # 添加调试日志
        print(f"Received request - prompt: {user_prompt}, session_id: {session_id}")

        # 修改验证逻辑
        if not user_prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        # session_id 可以为空，使用默认值
        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d%H%M%S")
            print(f"Generated new session_id: {session_id}")
        
        # 存储对话历史
        global conversation_history

        def generate():
            try:

                # 存储用户消息
                #store_message(session_id, 'user', user_prompt)
                
                # 构建包含历史对话的消息列表
                messages = []
                #print(f"conversation_history: {conversation_history}")
                if conversation_history:
                    # 添加历史对话
                    messages.extend(conversation_history)
                    # 添加当前用户输入
                    messages.append({"role": "user", "content": user_prompt})
                    
                    #print(f"messages: {messages}")
                    
                    #调用获取 reasoning
                    response = client.chat.completions.create(
                        model="chatgpt-4o-latest",
                        messages=messages,
                        stream=True
                    )
                    
                    assistant_response = ""
                    for chunk in response:
                        # Check if choices exist and are not empty
                        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                            if hasattr(chunk.choices[0].delta, 'content'):
                                delta = chunk.choices[0].delta.content
                                if delta:
                                    assistant_response += delta
                                    yield format_sse("responding", {"content": delta})
                        else:
                            print("No choices found in the response.")  # Debugging output
                            yield format_sse("error", {"content": "No choices found in the response."})
                
                    # 更新对话历史
                    conversation_history.append({"role": "user", "content": user_prompt})
                    conversation_history.append({"role": "assistant", "content": assistant_response})
                    # 存储 conversation_history 内容
                    store_message(session_id, 'user', user_prompt)
                    store_message(session_id, 'assistant', assistant_response)

                else:
                    # 添加当前用户输入
                    system_prompt = """
                    ##角色
                    你是一位历史老师,与你交互的用户是中学生。请你根据用户提供的历史史料题,其中包括若干史料和若干题目(problem),为每个题目分别设计苏格拉底式引导问题链,确保每个问题链的核心问题(question)数量控制在 2 - 3 个。

                    ##技能
                    ###技能 1: 与学生互动答题
                    1. 清晰展示第一个题目，展示后即等待用户输入答案，不进行任何提前模拟回答或跳过用户输入的操作。

                    2. 当收到用户答案后，判断答案正确性：

                        2.1 若答案正确：直接展示下一个题目，展示后继续等待用户输入。

                        2.2 若答案错误：从该题目对应的苏格拉底式引导问题链中取出第一个核心问题，直接显示问题内容，不附加任何假设性回答或解释，展示后等待用户输入。

                    3. 收到针对引导问题的用户答案后，判断答案正确性：

                        3.1 若答案正确：继续展示同一问题链的下一个核心问题，展示后等待用户输入。

                        3.2 若答案错误：先提示线索（如 “注意朝代时间顺序”），然后等待用户再次回答；若用户再次回答仍错误，直接给出正确答案并展示下一问题，展示后等待用户输入。

                    4. 当完成当前问题链的所有核心问题后，自动进入下一个题目。

                    5. 所有题目结束后，用一句话总结学习成果并鼓励用户。

                    ##限制
                    1. 严禁提前模拟回答任何问题，必须严格等待用户输入。

                    2. 仅围绕用户提供的历史史料题展开互动，不回答与题目无关的话题。

                    3. 回答需按照上述技能要求的流程进行，不可偏离流程框架。
                    """
                    messages = [{'role': 'system', 'content': system_prompt}]
                    messages.append({"role": "user", "content": user_prompt})
                    
                    # 第一次 API 调用获取 reasoning
                    response = client.chat.completions.create(
                        model="chatgpt-4o-latest",
                        messages=messages,
                        stream=True
                    )
                    
                    content = ""
                    for chunk in response:
                        # Check if choices exist and are not empty
                        if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                            if hasattr(chunk.choices[0].delta, 'content'):
                                delta = chunk.choices[0].delta.content
                                if delta:
                                    content += delta
                                    yield format_sse("responding", {"content": delta})
                        else:
                            print("No choices found in the response.")  # Debugging output
                            yield format_sse("error", {"content": "No choices found in the response."})
                    
                    print(f"Responding: {content}")
                    
                    # 更新对话历史
                    conversation_history.append({"role": "system", "content": system_prompt})
                    #每次一个问题
                    conversation_history.append({"role": "user", "content": user_prompt})
                    #苏格拉底问题1
                    conversation_history.append({"role": "assistant", "content": content})
                    
                    print(f"conversation_history: {conversation_history}")
                    
                    # 存储 conversation_history 内容
                    store_message(session_id, 'system', system_prompt)
                    store_message(session_id, 'user', user_prompt)
                    store_message(session_id, 'assistant', content)
                    
                    # 第二次 API 调用获取 response
                    #system_prompt = """
                    #你是一位历史老师,和你交互的用户是中学生,请你根据[user_prompt]中的问题,结合[reasoning_content]的内容,设计苏格拉底式问题链.
                    #"""
                    
                    # 构建第二次调用的消息列表
                    #messages = [{'role': 'system', 'content': system_prompt}]
                    
                    # 添加当前用户输入和reasoning
                    #messages.append({"role": "user", "content": user_prompt})
                    #messages.append({"role": "user", "content": "[user_prompt]:"+user_prompt+"[reasoning_content]:"+reasoning_content})
                    
                    #response = client.chat.completions.create(
                    #    model="gpt-4o-mini",
                    #    messages=messages,
                    #    stream=True
                    #)
                    
                    #assistant_response = ""
                    #for chunk in response:
                    #    if hasattr(chunk.choices[0].delta, 'content'):
                    #        delta = chunk.choices[0].delta.content
                    #        if delta:
                    #            assistant_response += delta
                    #            #yield format_sse("responding", {"content": delta})

                    #print(f"Question Chain: {assistant_response}")
                    
                    #系统提示
                    #conversation_history.append({"role": "system", "content": system_prompt})
                    #问题
                    #conversation_history.append({"role": "user", "content": user_prompt})
                    #思维+问题链
                    #conversation_history.append({"role": "assistant", "content": reasoning_content+assistant_response})
                    
                    #messages = [{'role': 'assistant', 'content': assistant_response }]
                    
                    #system1_prompt = "请按照问题链中的问题次序，依次显示每个问题，但不要直接给出答案，也不要一次性列出多个问题。等待用户回答后，判断用户回答是否正确。如果回答正确，就再显示下一个问题，如果回答错误就先给出正确答案，再显示下一个问题。直接显示问题，前面不需要显示任何其它信息。"
                    #messages.append({'role': 'user', 'content': system1_prompt})
                    
                    #response = client.chat.completions.create(
                    #    model="gpt-4o-mini",
                    #    messages=messages,
                    #    stream=True
                    #)
                    
                    #assistant_response = ""
                    #for chunk in response:
                    #    if hasattr(chunk.choices[0].delta, 'content'):
                    #        delta = chunk.choices[0].delta.content
                    #        if delta:
                    #            assistant_response += delta
                    #            yield format_sse("responding", {"content": delta})
                    
                    # 更新对话历史
                    #每次一个问题
                    #conversation_history.append({"role": "user", "content": system1_prompt})
                    #苏格拉底问题1
                    #conversation_history.append({"role": "assistant", "content": assistant_response})
                
                    # 存储 conversation_history 内容
                    #store_message(session_id, 'user', system1_prompt)
                    #store_message(session_id, 'assistant', assistant_response)
                
                yield format_sse("done", {})
                
            except Exception as e:
                print(f"Error in generate: {str(e)}")
                yield format_sse("error", {"content": str(e)})

        return Response(generate(), mimetype='text/event-stream')
    
    except Exception as e:
        print(f"Error in stream: {str(e)}")
        return jsonify({"error": str(e)}), 500

# 添加获取历史记录的路由
@app.route('/api/history/<session_id>')
def get_history(session_id):
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            SELECT message_type, content, timestamp 
            FROM conversations 
            WHERE session_id = ? 
            ORDER BY timestamp
        ''', (session_id,))
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
    app.run(debug=True, port=5000)
    