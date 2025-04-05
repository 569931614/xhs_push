from flask import Flask, request, jsonify
import mysql.connector
import requests
import time
import os
import traceback
from datetime import datetime

print("开始初始化Flask应用...")
app = Flask(__name__)

# MySQL数据库配置
db_config = {
    'host': '47.238.216.176',
    'user': 'xhs_push',
    'password': 'CYh3xjbFf4MDA3cd',
    'database': 'xhs_push',
    'ssl_disabled': True
}

# 获取数据库连接
def get_db_connection():
    try:
        print("尝试连接数据库...")
        conn = mysql.connector.connect(**db_config)
        print("数据库连接成功!")
        return conn
    except Exception as e:
        print(f"数据库连接失败: {str(e)}")
        traceback.print_exc()
        return None

# 获取密钥API
@app.route('/api/signature', methods=['GET'])
def get_signature():
    try:
        print("请求 /api/signature API")
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "无法连接到数据库"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # 查询最新的签名
        cursor.execute("SELECT * FROM signature ORDER BY created_at DESC LIMIT 1")
        result = cursor.fetchone()
        
        # 如果存在签名且未过期（小于19分钟）
        current_time = int(time.time() * 1000)
        if result and current_time - int(result['timestamp']) < 19 * 60 * 1000:
            cursor.close()
            conn.close()
            return jsonify(result)
        
        # 否则请求新的签名
        try:
            print("请求新的签名...")
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post('https://red-sever-pnfbxjccci.cn-hangzhou.fcapp.run/signature', headers=headers)
            print(f"签名API响应: 状态码 {response.status_code}, 内容 {response.text}")
            data = response.json()
            
            # 保存到数据库
            query = """
            INSERT INTO signature (app_key, signature, timestamp, nonce, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """
            values = (
                data['appKey'],
                data['signature'],
                data['timestamp'],
                data['nonce'],
                datetime.now()
            )
            cursor.execute(query, values)
            conn.commit()
            
            cursor.close()
            conn.close()
            return jsonify(data)
        except Exception as e:
            print(f"获取签名失败: {str(e)}")
            traceback.print_exc()
            cursor.close()
            conn.close()
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"获取签名API错误: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# 保存小红书数据API
@app.route('/api/posts', methods=['POST'])
def save_post():
    try:
        print("请求 /api/posts POST API")
        data = request.json
        print(f"接收到数据: {data}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "无法连接到数据库"}), 500
            
        cursor = conn.cursor()
        
        # 插入帖子信息
        post_query = """
        INSERT INTO posts (type, title, content, video, cover)
        VALUES (%s, %s, %s, %s, %s)
        """
        post_values = (
            data.get('type', 'normal'),
            data.get('title', ''),
            data.get('content', ''),
            data.get('video', ''),
            data.get('cover', '')
        )
        
        cursor.execute(post_query, post_values)
        conn.commit()
        post_id = cursor.lastrowid
        
        # 插入图片信息
        if 'images' in data and isinstance(data['images'], list):
            for image_url in data['images']:
                image_query = "INSERT INTO images (post_id, image_url) VALUES (%s, %s)"
                cursor.execute(image_query, (post_id, image_url))
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "id": post_id})
    except Exception as e:
        print(f"保存帖子失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# 获取小红书数据API
@app.route('/api/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    try:
        print(f"请求 /api/posts/{post_id} GET API")
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "无法连接到数据库"}), 500
            
        cursor = conn.cursor(dictionary=True)
        
        # 获取帖子信息
        cursor.execute("SELECT * FROM posts WHERE id = %s", (post_id,))
        post = cursor.fetchone()
        
        if not post:
            cursor.close()
            conn.close()
            return jsonify({"error": "Post not found"}), 404
        
        # 获取图片信息
        cursor.execute("SELECT image_url FROM images WHERE post_id = %s", (post_id,))
        images = [row['image_url'] for row in cursor.fetchall()]
        
        post['images'] = images
        
        cursor.close()
        conn.close()
        
        return jsonify(post)
    except Exception as e:
        print(f"获取帖子失败: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# 前端页面路由
@app.route('/<int:post_id>', methods=['GET'])
def share_page(post_id):
    try:
        print(f"请求 /{post_id} 分享页面")
        conn = get_db_connection()
        if not conn:
            return "数据库连接失败", 500
            
        cursor = conn.cursor(dictionary=True)
        
        # 获取帖子信息
        cursor.execute("SELECT * FROM posts WHERE id = %s", (post_id,))
        post = cursor.fetchone()
        
        if not post:
            cursor.close()
            conn.close()
            return "帖子不存在", 404
        
        # 获取图片信息
        cursor.execute("SELECT image_url FROM images WHERE post_id = %s", (post_id,))
        images = [row['image_url'] for row in cursor.fetchall()]
        
        # 获取最新的签名
        cursor.execute("SELECT * FROM signature ORDER BY created_at DESC LIMIT 1")
        signature = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # 构建HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="zh">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{post['title'] if post['title'] else '小红书分享'}</title>
            <script src="https://fe-static.xhscdn.com/biz-static/goten/xhs-1.0.1.js"></script>
        </head>
        <body>
            <script>
                window.onload = function() {{
                    xhsFn();
                }};
                
                function xhsFn() {{
                    console.log('分享数据:', {{"type": "{post['type']}", "title": "{post['title']}", "content": "{post['content']}", "images": {images}, "video": "{post['video']}", "cover": "{post['cover']}"}});
                    xhs.share({{
                        shareInfo: {{
                            type: '{post['type']}',
                            title: '{post['title']}',
                            content: '{post['content']}',
                            images: {images},
                            video: '{post['video']}',
                            cover: '{post['cover']}'
                        }},
                        verifyConfig: {{
                            appKey: '{signature['app_key']}',
                            signature: '{signature['signature']}',
                            timestamp: '{signature['timestamp']}',
                            nonce: '{signature['nonce']}'
                        }},
                        fail: (e) => {{
                            console.log('分享失败:', e);
                        }}
                    }});
                }}
            </script>
            <div style="text-align: center; margin-top: 50px;">
                <h1>正在打开小红书...</h1>
                <p>如果没有自动打开，请点击"打开小红书"按钮</p>
                <button onclick="xhsFn()" style="padding: 10px 20px; background-color: #fe2c55; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer;">打开小红书</button>
            </div>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        print(f"生成分享页面失败: {str(e)}")
        traceback.print_exc()
        return str(e), 500

if __name__ == '__main__':
    try:
        print("开始运行Flask应用...")
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Flask应用启动失败: {str(e)}")
        traceback.print_exc() 