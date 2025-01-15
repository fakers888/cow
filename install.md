# 安装指南

本指南将帮助你完整地安装和配置 chatgpt-on-wechat-ipad。

## 1. 前提条件

在开始安装之前，请确保满足以下条件：

- Ubuntu 22.04 操作系统（推荐）
- Python 3.10 
- 已获取 ipad 协议的 token
- 有公网 IP 或内网穿透服务（用于接收消息回调）

## 2. 安装步骤

### 2.1 克隆项目

```bash
git clone https://github.com/fakers888/cow
cd cow
```

### 2.2 创建并激活虚拟环境

```bash
# 安装虚拟环境工具
sudo apt update
sudo apt install python3-venv

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate
```

### 2.3 安装依赖

```bash
# 安装核心依赖
pip install -r requirements.txt

# 安装可选依赖（建议安装）
pip install -r requirements-optional.txt
```

### 2.4 配置项目

1. 复制配置模板：
```bash
cp config-template.json config.json
```

2. 编辑 config.json，填入必要参数：
```json
{
  "auth_account": "开通后的手机号",
  "auth_password": "开通后加密后的密码",
  "token": "login接口获取的token",
  "auth": "login接口获取的auth",
  "http_hook": "http://你的服务器IP:端口/chat",
  "base_url": "远端IPAD服务器地址",
  "wechatipad_port":"你的端口号",
  "channel_type": "wx",
  "AI_reply": true,
  "group_name_white_list": ["测试群1", "测试群2"],
  "group_chat_prefix": [">", "bot"],
  "single_chat_prefix": ["bot", "@bot"]
}
```

## 3. 运行与测试

### 3.1 使用 Screen 调试运行

1. 安装 screen：
```bash
sudo apt install screen
```

2. 创建新的 screen 会话：
```bash
screen -S chatbot
```

3. 启动程序：
```bash
python3 app.py
```

要退出 screen 会话，按 `Ctrl+A` 然后按 `D`。要恢复会话，使用 `screen -r chatbot`。

### 3.2 使用 Supervisor 部署（推荐）

1. 安装 1Panel：
```bash
# Ubuntu
wget -O quick_start.sh https://resource.fit2cloud.com/1panel/package/quick_start.sh && bash quick_start.sh
```

2. 在 1Panel 中安装：
   - Supervisor

3. 安装 gunicorn：
```bash
```

4. 创建 Supervisor 配置：
```ini
[program:chatbot]
directory=/path/to/chatgpt-on-wechat-ipad
command=/path/to/venv/bin/gunicorn app:quart_app -w 1 -b 0.0.0.0:5731
autostart=true
autorestart=true
stderr_logfile=/var/log/chatbot.err.log
stdout_logfile=/var/log/chatbot.out.log
environment=PATH="/path/to/venv/bin:%(ENV_PATH)s"
```

5. 配置 Nginx 反向代理 （可选）：
```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://127.0.0.1:5731;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

6. 启动服务：
```bash
supervisorctl reread
supervisorctl update
supervisorctl start chatbot
```

### 3.3 配置微信号

1. 访问后台管理界面：`http://你的服务器IP:你的端口/login`  注意防火墙放开端口！！
   - 默认用户名：admin
   - 默认密码：123456

2. 添加微信号：
   - 点击"新增"按钮
   - 填写获取的用户名和密码
   - 填写省份和城市信息（按实际微信注册地填写），直辖市填写省份，城市留空。例如 山西省 太原市
   - 填写回调地址（确保可以从外网访问）
   - 添加后提示你用新账号登录
3. 使用你的手机号和密码123456登录！！
4. 初始化和登录：
   - 选中刚添加的账号
   - 点击"初始化"按钮
   - 点击"扫码"按钮
   - 使用微信扫描二维码完成登录。注意看省份是否正确，确保同省
   - 点击"开启"按钮设置回调地址
   - 点击 "编辑" 可以修改

5. 重启程序：
   - 如果使用 Supervisor：
     ```bash
     supervisorctl restart chatbot
     ```
   - 如果使用 Screen：
     ```bash
     screen -r chatbot
     # Ctrl+C 停止当前程序
     python3 app.py
     ```
检查是否获取到微信信息，并初始化完成。
### 3.4 测试
0. 设置私聊和群聊的触发词
1. 私聊测试：
   - 用另一个微信号私聊机器人
   - 发送 "bot 你好" 测试回复

2. 群聊测试：
   - 将机器人拉入群聊。
   - 群聊保存到通讯录！！！！
   - 将群名称保存到配置中的白名单！！！！
   - 再次重启机器人
   - 在群里 @机器人 测试回复
### 3.5 二次登录
   - 第二天微信会掉线一次，打开网页，点击登录，手机再确认登录，这样以后就不会掉线了
## 常见问题

1. 如果遇到依赖安装失败，可以尝试：
   - 用上面的方法进入cd cow目录
   - 使用 source venv/bin/activate 激活虚拟环境
   - 更新 pip3：`pip install --upgrade pip`
   - 单独安装失败的依赖
     pip3 install 缺少的库文件

2. 如果遇到缺少库文件错误：
   ```bash
   # Ubuntu/Debian 系统
   sudo apt-get update
   sudo apt-get install -y \
       build-essential \
       python3-dev \
       libffi-dev \
       libssl-dev \
       libjpeg-dev \
       zlib1g-dev \
       libpng-dev
   
   # CentOS/RHEL 系统
   sudo yum groupinstall -y "Development Tools"
   sudo yum install -y \
       python3-devel \
       libffi-devel \
       openssl-devel \
       libjpeg-devel \
       zlib-devel \
       libpng-devel
   ```

3. 如果无法接收消息：
   - 检查回调地址是否可以从外网访问
   - 确认防火墙是否开放对应端口：
     ```bash
     # 开放端口
    
     
     # 检查端口状态
     sudo netstat -tulpn | grep -E '80|5731'
     ```
   - 查看程序日志是否有错误信息

     ```

4. 如果扫码登录失败：
   - 确认 token 和auth 是否正确
   - 检查省份和城市是否正确 省 和 市 不能省略
   - 确认微信号是否被限制登录
   - 检查日志文件：
     ```bash
     tail -f /var/log/chatbot.err.log
     ```

5. 内存占用过高：
   - 调整 gunicorn 工作进程数
   - 修改 supervisor 配置中的 `-w` 参数
   - 监控内存使用：
     ```bash
     # 查看内存使用
     free -h
     
     # 查看进程资源占用
     top -u chatbot
     ```

## 4. 运维管理

### 4.1 使用 Supervisor 管理服务

常用命令：
```bash
# 查看服务状态
supervisorctl status chatbot

# 停止服务
supervisorctl stop chatbot

# 启动服务
supervisorctl start chatbot

# 重启服务
supervisorctl restart chatbot

# 查看日志
tail -f /var/log/chatbot.out.log
tail -f /var/log/chatbot.err.log
```

### 4.2 使用 1Panel 管理服务

1. 通过 1Panel 网页界面可以方便地：
   - 监控服务状态
   - 查看日志
   - 启动/停止服务

2. 建议定期通过 1Panel：
   - 检查系统资源使用情况
   - 备份配置文件
   - 更新系统安全补丁 