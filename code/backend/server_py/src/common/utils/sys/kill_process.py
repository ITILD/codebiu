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
        if not pids:
            log_info = f"port:{port} not used or cant check"
            logger.warning(log_info)
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
