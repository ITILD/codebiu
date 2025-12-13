import asyncio
import psutil
from datetime import datetime
from common.utils.sys.do.status import (
    TopProcessInfo,
    GPUInfo,
    CPUInfo,
    HardwareStatus,
    DiskInfo,
    MemoryInfo,
    ProcessInfo,
)


class SystemMonitor:
    """异步系统监控工具类，支持 NVIDIA 和 AMD GPU 检测"""

    @staticmethod
    def b2gb(b):
        """将字节转换为GB"""
        return round(b / (1024**3), 2)

    async def get_hardware_status(self) -> HardwareStatus:
        """
        获取系统硬件状态信息

        返回:
            dict: 包含磁盘、内存、CPU、GPU状态信息的字典
        """
        # 使用 gather 并行获取各项指标
        disk_info, mem_info, cpu_info, gpu_info = await asyncio.gather(
            self._get_disk_info(),
            self._get_memory_info(),
            self._get_cpu_info(),
            self._get_gpu_info(),
        )

        return HardwareStatus(
            disk=disk_info,
            memory=mem_info,
            cpu=cpu_info,
            gpu=gpu_info,
            timestamp=datetime.now(),
        )

    async def _get_disk_info(self) -> DiskInfo:
        """获取磁盘信息"""
        disk = psutil.disk_usage("/")
        return DiskInfo(
            total=self.b2gb(disk.total), used=self.b2gb(disk.used), percent=disk.percent
        )

    async def _get_memory_info(self) -> MemoryInfo:
        """获取内存信息"""
        mem = psutil.virtual_memory()
        return MemoryInfo(
            total=self.b2gb(mem.total), used=self.b2gb(mem.used), percent=mem.percent
        )

    async def _get_cpu_info(self) -> CPUInfo:
        """获取CPU信息"""
        # 等待1秒获取准确的CPU使用率
        await asyncio.sleep(1)
        return CPUInfo(
            percent=psutil.cpu_percent(interval=0),
            cores=psutil.cpu_count(logical=False),
            threads=psutil.cpu_count(logical=True),
        )

    async def _get_gpu_info(self) -> list[GPUInfo]:
        """
        获取 GPU 信息(自动检测 NVIDIA 或 AMD)

        返回:
            list: GPU 信息列表，若未检测到 GPU 则返回空列表
        """
        # 并行尝试获取NVIDIA和AMD GPU信息
        nvidia_gpus, amd_gpus = await asyncio.gather(
            self._get_nvidia_gpu_info(), self._get_amd_gpu_info()
        )

        return nvidia_gpus if nvidia_gpus else amd_gpus

    async def _get_nvidia_gpu_info(self) -> list[GPUInfo]:
        """使用 nvidia-smi 获取 NVIDIA GPU 信息"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()
            output = stdout.decode("utf-8")

            gpu_info = []
            for line in output.strip().split("\n"):
                values = [x.strip() for x in line.split(",")]
                gpu_info.append(
                    GPUInfo(
                        vendor="NVIDIA",
                        id=int(values[0]),
                        name=values[1],
                        total=float(values[2]),
                        used=float(values[3]),
                        percent=float(values[4]),
                        temp=float(values[5]),
                    )
                )
            return gpu_info
        except Exception:
            return []

    async def _get_amd_gpu_info(self) -> list[GPUInfo]:
        """使用 rocm-smi 获取 AMD GPU 信息"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi",
                "--showmeminfo",
                "vram",
                "--showtemp",
                "--showuse",
                "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()
            data = stdout.decode("utf-8")

            import json

            data = json.loads(data)

            gpu_info = []
            for gpu_id, gpu_data in data.items():
                if not gpu_id.startswith("card"):
                    continue

                gpu_info.append(
                    GPUInfo(
                        vendor="AMD",
                        id=gpu_data["Device Number"],
                        name=gpu_data["Device Name"],
                        total=self.b2gb(gpu_data["vram"]["Total Memory (B)"]),
                        used=self.b2gb(gpu_data["vram"]["Used Memory (B)"]),
                        percent=float(gpu_data["GPU use (%)"]),
                        temp=float(gpu_data["Temperature (C)"]),
                    )
                )
            return gpu_info
        except Exception:
            return []

    async def get_process_info(self, pid, interval=0.2) -> ProcessInfo | None:
        """获取指定进程的详细信息(更精确的CPU使用率计算)"""
        try:
            p = psutil.Process(pid)

            # 第一次采样
            cpu_times1 = p.cpu_times()
            await asyncio.sleep(interval)  # 异步等待

            with p.oneshot():
                # 第二次采样并计算CPU使用率
                cpu_times2 = p.cpu_times()
                total_time = sum(cpu_times2) - sum(cpu_times1)
                return ProcessInfo(
                    pid=pid,
                    name=p.name(),
                    status=p.status(),
                    cpu_percent=(total_time / interval) * 100 / psutil.cpu_count(),
                    memory_percent=p.memory_percent(),
                    memory_rss=self.b2gb(p.memory_info().rss),
                    create_time=datetime.fromtimestamp(p.create_time()).isoformat(),
                    exe=p.exe(),
                    cmdline=p.cmdline(),
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    async def get_top_processes(self, count=5, interval=1.0) -> list[TopProcessInfo]:
        """获取资源占用最高的进程列表(改进版)"""
        # 第一次采样
        first_sample = {}
        for p in psutil.process_iter(["pid", "cpu_times"]):
            try:
                with p.oneshot():
                    first_sample[p.pid] = p.info["cpu_times"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 异步等待间隔
        await asyncio.sleep(interval)

        # 第二次采样并计算CPU使用率
        processes = []
        for p in psutil.process_iter(
            ["pid", "name", "username", "cpu_times", "memory_percent", "memory_info"]
        ):
            try:
                with p.oneshot():
                    pid = p.info["pid"]
                    if pid not in first_sample:
                        continue

                    # 计算CPU使用率
                    old_times = first_sample[pid]
                    new_times = p.info["cpu_times"]
                    total_time = sum(new_times) - sum(old_times)
                    if total_time <= 0:
                        continue

                    cpu_percent = (total_time / interval) * 100 / psutil.cpu_count()

                    # 获取内存信息
                    mem_percent = p.info["memory_percent"]
                    rss_mb = self.b2gb(p.info["memory_info"].rss)

                    processes.append(
                        TopProcessInfo(
                            pid=pid,
                            user=p.info.get("username", "N/A"),
                            name=p.info["name"],
                            cpu=cpu_percent,
                            memory=mem_percent,
                            rss_mb=rss_mb,
                        )
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 按 CPU 降序，然后按内存降序
        return sorted(processes, key=lambda x: (x.cpu, x.memory), reverse=True)[:count]


if __name__ == "__main__":

    async def main():
        monitor = SystemMonitor()
        # 获取硬件状态
        hardware = await monitor.get_hardware_status()
        print("硬件状态:")
        print(f"CPU使用率: {hardware.cpu.percent}%")
        print(f"内存使用: {hardware.memory.used}GB/{hardware.memory.total}GB")

        # 打印 GPU 信息
        if hardware.gpu:
            print("\nGPU 信息:")
            for gpu in hardware.gpu:
                print(f"{gpu.vendor} GPU {gpu.id}: {gpu.name}")
                print(
                    f"显存: {gpu.used}MB/{gpu.total}MB, 使用率: {gpu.percent}%, 温度: {gpu.temp}°C"
                )
        else:
            print("\n未检测到 GPU 信息")

        # 获取当前进程信息
        pid = psutil.Process().pid
        process_info = await monitor.get_process_info(pid)
        if process_info:
            print(f"\n当前进程信息: {process_info}")
        else:
            print("\n无法获取当前进程信息")

        # 获取占用最高的5个进程
        top_processes = await monitor.get_top_processes(5)
        print("\n资源占用最高的5个进程:")
        for p in top_processes:
            print(
                f"PID: {p.pid}, 用户: {p.user}, 名称: {p.name}, CPU: {p.cpu:.1f}%, 内存: {p.memory:.1f}% (RSS: {p.rss_mb}MB)"
            )

    asyncio.run(main())
