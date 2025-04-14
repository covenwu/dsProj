import os
import csv
from flask import Blueprint, send_file, make_response
from io import StringIO
import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

download_bp = Blueprint('download', __name__)

# MySQL配置 - que_system数据库
QUE_DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'chat_user',  # 生产环境用户
    'password': '12345678',  # 生产环境密码
    'database': 'que_system',  # 数据库名
    'charset': 'utf8mb4'
}

# MySQL配置 - chat_system数据库
CHAT_DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'chat_user',  # 生产环境用户
    'password': '12345678',  # 生产环境密码
    'database': 'chat_system',  # 数据库名
    'charset': 'utf8mb4'
}

# 创建数据库连接池 - que_system
que_pool = PooledDB(
    creator=pymysql,
    maxconnections=5,  # 最大连接数
    mincached=1,       # 初始连接数
    maxcached=5,       # 最大空闲连接数
    blocking=True,     # 连接池满时是否阻塞等待
    **QUE_DB_CONFIG
)

# 创建数据库连接池 - chat_system
chat_pool = PooledDB(
    creator=pymysql,
    maxconnections=5,  # 最大连接数
    mincached=1,       # 初始连接数
    maxcached=5,       # 最大空闲连接数
    blocking=True,     # 连接池满时是否阻塞等待
    **CHAT_DB_CONFIG
)

def get_que_connection():
    """获取que_system数据库连接"""
    return que_pool.connection()

def get_chat_connection():
    """获取chat_system数据库连接"""
    return chat_pool.connection()

@download_bp.route('/download/socrate')
def download_socrate():
    """Generate and download a CSV file from que_system database"""
    try:
        # Connect to the database
        conn = get_que_connection()
        cursor = conn.cursor(DictCursor)
        
        # Query all data from the database
        cursor.execute('''
            SELECT * FROM conversations
        ''')
        
        data = cursor.fetchall()
        
        # Create a string buffer and csv writer
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header if data exists
        if data:
            # Get column names from the first row
            column_names = list(data[0].keys())
            writer.writerow(column_names)
            
            # Write data rows
            for row in data:
                writer.writerow([row[col] for col in column_names])
        else:
            writer.writerow(["No data found"])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=socrate_chat_history.csv'
        response.headers['Content-type'] = 'text/csv'
        
        # Close connection
        cursor.close()
        conn.close()
        
        return response
    
    except Exception as e:
        return str(e), 500

@download_bp.route('/download/thinkaloud')
def download_thinkaloud():
    """Generate and download a CSV file from chat_system database"""
    try:
        # Connect to the database
        conn = get_chat_connection()
        cursor = conn.cursor(DictCursor)
        
        # Query all data from the database
        cursor.execute('''
            SELECT * FROM conversations
        ''')
        
        data = cursor.fetchall()
        
        # Create a string buffer and csv writer
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header if data exists
        if data:
            # Get column names from the first row
            column_names = list(data[0].keys())
            writer.writerow(column_names)
            
            # Write data rows
            for row in data:
                writer.writerow([row[col] for col in column_names])
        else:
            writer.writerow(["No data found"])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=thinkaloud_chat_history.csv'
        response.headers['Content-type'] = 'text/csv'
        
        # Close connection
        cursor.close()
        conn.close()
        
        return response
    
    except Exception as e:
        return str(e), 500 