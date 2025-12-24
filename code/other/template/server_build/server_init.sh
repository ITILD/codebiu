# uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# docker
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release

# 创建目录
sudo install -m 0755 -d /etc/apt/keyrings

# 下载阿里云提供的 Docker GPG 密钥（国内可访问）
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 添加阿里云 Docker 仓库
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update 
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
