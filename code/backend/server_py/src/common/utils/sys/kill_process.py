import re
import sys
import platform
import subprocess
import logging

logger = logging.getLogger(__name__)


def find_and_kill_process(port, os_type=platform.system()):
    """
    查找并杀死占用指定端口的进程
    :param port: 要检查的端口号
    :param os_type: 操作系统类型，默认为当前系统
    :raises RuntimeError: 当端口未被占用或操作系统不支持时
    """
    pids =[]
    if os_type == "Windows":
        try:
            output = subprocess.check_output(
                f"netstat -aon | findstr :{port}", shell=True
            ).decode()
            pids = [
                line.split()[-1] for line in output.splitlines() if "LISTENING" in line
            ]
        except subprocess.CalledProcessError:
            pass
        if not pids:
            log_info = f"port:{port} not used or cant check"
            logger.warning(log_info)
            return
        for pid in pids:
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, check=True)
        logger.info(f"kill port [{port}] success")

    elif os_type in ["Darwin", "Linux"]:
        try:
            output = subprocess.check_output(
                f"lsof -i tcp:{port} -sTCP:LISTEN", shell=True
            ).decode()
            pids = [line.split()[1] for line in output.splitlines()[1:]]
        except subprocess.CalledProcessError:
            pass
        # lsof 查不到时用 ss 兜底(lsof 未安装 / 无权限时看不到占用进程)
        if not pids and os_type == "Linux":
            try:
                output = subprocess.check_output(
                    f"ss -ltnp sport = :{port}", shell=True
                ).decode()
                pids = re.findall(r"pid=(\d+)", output)
            except subprocess.CalledProcessError:
                pass
        if not pids:
            # 区分"端口确实空闲"和"端口被占用但当前用户无权查看/终止(属主非当前用户)"
            occupied = subprocess.run(
                f"ss -ltn sport = :{port}", shell=True, capture_output=True
            ).stdout.decode().count("LISTEN")
            if occupied:
                logger.error(
                    f"port:{port} 被占用, 但占用进程属主不是当前用户(root/容器等), 无权终止, "
                    f"请用 root 执行: sudo kill $(sudo lsof -ti tcp:{port}) 或停止对应服务"
                )
            else:
                logger.warning(f"port:{port} not used or cant check")
            return
        for pid in pids:
            subprocess.run(f"kill -9 {pid}", shell=True, check=True)
        logger.info(f"kill port [{port}] success")
    else:
        raise RuntimeError("不支持的操作系统")


if __name__ == "__main__":
    try:
        os_type = platform.system()
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 2666
        find_and_kill_process(port, os_type)
    except Exception as e:
        sys.stderr.write(f"错误: {str(e)}\n")
        sys.exit(1)
