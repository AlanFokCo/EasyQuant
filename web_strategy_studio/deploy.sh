#!/bin/bash
# Web Strategy Studio 部署脚本
# 用法: ./deploy.sh

set -e

echo "========================================"
echo "Web Strategy Studio 部署脚本"
echo "========================================"
echo ""

# 配置
SERVER="39.106.214.78"
USER="root"
APP_DIR="/opt/easyquant-studio"
REPO_URL="https://github.com/AlanFokCo/EasyQuant.git"
BACKEND_PORT="8080"
FRONTEND_PORT="5173"

echo "目标服务器: $SERVER"
echo "部署目录: $APP_DIR"
echo ""

# 检查 SSH 连接
echo "[1/8] 检查 SSH 连接..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$USER@$SERVER" "echo 'SSH OK'" > /dev/null 2>&1; then
    echo "错误: 无法通过 SSH 连接到 $SERVER"
    echo "请确保:"
    echo "  1. SSH 密钥已添加到 ssh-agent: ssh-add ~/.ssh/id_rsa"
    echo "  2. 公钥已添加到服务器的 ~/.ssh/authorized_keys"
    echo "  3. 或者使用密码登录: ssh $USER@$SERVER"
    exit 1
fi
echo "SSH 连接正常"
echo ""

# 创建部署脚本（在服务器上执行）
echo "[2/8] 创建远程部署脚本..."

cat > /tmp/deploy-remote.sh << 'REMOTEEOF'
#!/bin/bash
set -e

APP_DIR="/opt/easyquant-studio"
REPO_URL="https://github.com/AlanFokCo/EasyQuant.git"

mkdir -p $APP_DIR
cd $APP_DIR

echo "========================================"
echo "在服务器上部署 Web Strategy Studio"
echo "========================================"

# 1. 安装系统依赖
echo "[1/6] 安装系统依赖..."
if command -v apt-get &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq git curl wget python3 python3-pip python3-venv nodejs npm nginx
elif command -v yum &> /dev/null; then
    # Remove conflicting Node.js packages first
    yum remove -y nodejs nodejs-full-i18n 2>/dev/null || true
    yum update -y -q --exclude=nodejs*,nodejs-full-i18n
    yum install -y -q git curl wget python3 python3-pip nginx
    # Check if Node.js >= 18 is already installed
    if ! command -v node &> /dev/null || [ "$(node -v | cut -d'v' -f2 | cut -d'.' -f1)" -lt 18 ]; then
        # Node.js 20
        curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
        yum install -y -q nodejs
    fi
else
    echo "不支持的包管理器"
    exit 1
fi

# 安装 Node.js 20 (如果当前版本 < 18)
if ! command -v node &> /dev/null || [ "$(node -v | cut -d'v' -f2 | cut -d'.' -f1)" -lt 18 ]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi

echo "Node.js 版本: $(node -v)"
echo "Python3 版本: $(python3 --version)"

# 2. 克隆或更新代码
echo "[2/6] 拉取代码..."
if [ -d ".git" ]; then
    git pull origin main
else
    git clone "$REPO_URL" .
fi

# Check Python version and install Python 3.9+ if needed
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
if [ "$(echo "$PYTHON_VERSION < 3.9" | bc -l)" -eq 1 ]; then
    echo "Python $PYTHON_VERSION 版本太低，安装 Python 3.11..."
    yum install -y -q python3.11 python3.11-pip
    ln -sf /usr/bin/python3.11 /usr/local/bin/python3
    ln -sf /usr/bin/pip3.11 /usr/local/bin/pip3
fi

# 3. 安装 Python 依赖
echo "[3/6] 安装 Python 依赖..."
pip3 install -q -e .
cd web_strategy_studio/backend
pip3 install -q -e .

# Check and add swap if needed
SWAP_SIZE=$(free -m | awk '/Swap:/{print $2}')
if [ -z "$SWAP_SIZE" ] || [ "$SWAP_SIZE" -lt 2048 ]; then
    echo "内存不足，添加 2GB 交换空间..."
    if [ ! -f /swapfile ]; then
        fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048
        chmod 600 /swapfile
        mkswap /swapfile
    fi
    swapon /swapfile 2>/dev/null || true
fi

# 4. 安装前端依赖并构建
echo "[4/6] 安装前端依赖并构建..."
cd ../frontend
npm install --silent --no-audit --no-fund
NODE_OPTIONS="--max-old-space-size=1024" npm run build

# 5. 配置 Nginx
echo "[5/6] 配置 Nginx..."
cd /opt/easyquant-studio

# CentOS/RHEL uses /etc/nginx/conf.d/ instead of sites-available
if [ -d /etc/nginx/sites-available ]; then
    # Debian/Ubuntu style
    cat > /etc/nginx/sites-available/easyquant-studio << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    location / {
        root /opt/easyquant-studio/web_strategy_studio/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:8080/static/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
NGINXEOF
    ln -sf /etc/nginx/sites-available/easyquant-studio /etc/nginx/sites-enabled/easyquant-studio
    rm -f /etc/nginx/sites-enabled/default
else
    # CentOS/RHEL style
    cat > /etc/nginx/conf.d/easyquant-studio.conf << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    location / {
        root /opt/easyquant-studio/web_strategy_studio/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        proxy_pass http://127.0.0.1:8080/static/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
NGINXEOF
fi
nginx -t && systemctl reload nginx

# 6. 创建 systemd 服务
echo "[6/6] 创建 systemd 服务..."

# Generate JWT secret before writing service file (systemd Environment= doesn't support shell expansion)
JWT_SECRET=$(openssl rand -hex 32)
cat > /etc/systemd/system/easyquant-backend.service << SERVICEEOF
[Unit]
Description=EasyQuant Studio Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/easyquant-studio/web_strategy_studio/backend
Environment="EQ_STUDIO_REPO_ROOT=/opt/easyquant-studio"
Environment="EQ_STUDIO_DATABASE_URL=sqlite+aiosqlite:////opt/easyquant-studio/data/studio.sqlite3"
Environment="EQ_STUDIO_ARTIFACT_DIR=/opt/easyquant-studio/artifacts"
Environment="EQ_STUDIO_PUBLIC_BASE_URL=http://39.106.214.78"
Environment="EQ_ADMIN_PASSWORD=demo123!Admin"
Environment="EQ_JWT_SECRET=${JWT_SECRET}"
ExecStart=/usr/local/bin/uvicorn studio_api.app:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable easyquant-backend
systemctl start easyquant-backend

echo ""
echo "========================================"
echo "部署完成！"
echo "========================================"
echo ""
echo "访问地址: http://39.106.214.78"
echo "API 地址: http://39.106.214.78/api/v1"
echo ""
echo "默认管理员账号:"
echo "  用户名: admin"
echo "  密码: demo123!Admin"
echo ""
echo "预设用户:"
echo "  用户名: demo"
echo "  密码: demo123"
echo ""
echo "查看服务状态:"
echo "  systemctl status easyquant-backend"
echo "  journalctl -u easyquant-backend -f"
echo ""

REMOTEEOF

chmod +x /tmp/deploy-remote.sh

echo "远程脚本已创建"
echo ""

# 3. 上传并执行部署脚本
echo "[3/8] 上传部署脚本到服务器..."
scp /tmp/deploy-remote.sh "$USER@$SERVER:/tmp/"

echo "[4/8] 执行远程部署..."
ssh "$USER@$SERVER" "bash /tmp/deploy-remote.sh"

echo ""
echo "========================================"
echo "部署脚本已执行完毕"
echo "========================================"
