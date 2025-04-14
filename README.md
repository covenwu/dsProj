# 历史课智能导师系统

## 数据库配置

本系统使用MySQL数据库，支持高并发访问。在部署前需进行以下配置：

### 1. 创建MySQL数据库

对于app1.py (练习系统):
```sql
CREATE DATABASE chat_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

对于app.py (问答系统):
```sql
CREATE DATABASE que_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 创建MySQL用户并授权

```sql
CREATE USER 'chat_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON chat_system.* TO 'chat_user'@'localhost';
GRANT ALL PRIVILEGES ON que_system.* TO 'chat_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. 修改数据库配置

编辑`app1.py`和`app.py`文件中的`DB_CONFIG`变量，设置正确的数据库连接信息：

对于app1.py:
```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'chat_user',  # 替换为您的用户名
    'password': 'your_secure_password',  # 替换为您的密码
    'database': 'chat_system',
    'charset': 'utf8mb4'
}
```

对于app.py:
```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'chat_user',  # 替换为您的用户名
    'password': 'your_secure_password',  # 替换为您的密码
    'database': 'que_system',
    'charset': 'utf8mb4'
}
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动应用

### 开发环境

练习系统:
```bash
python app1.py
```

问答系统:
```bash
python app.py
```

### 生产环境（使用Gunicorn）

练习系统:
```bash
gunicorn -w 4 -b 0.0.0.0:5001 --timeout 120 app1:app
```

问答系统:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 app:app
```

## 并发性能

当前配置支持：
- 最大50个并发数据库连接
- 初始缓存5个连接
- 最大空闲连接20个

可以根据服务器性能和负载情况调整这些参数。 