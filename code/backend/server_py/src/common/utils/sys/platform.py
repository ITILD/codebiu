import platform
import uuid
from common.utils.enum.platform import PlatformId
from common.utils.sys.do.platform import PlatformInfo

class PlatformUtils:
    """平台工具类，提供平台检测和识别功能"""

    @staticmethod
    def get_platform_id() -> PlatformId:
        """
        获取当前系统的平台ID
        
        返回:
            PlatformId: 平台枚举值
            
        异常:
            Exception: 当平台无法识别时抛出
        """
        # 收集平台信息
        platform_info = PlatformInfo(
            system=platform.system(),
            machine=platform.machine(),
            bitness=platform.architecture()[0]
        )
        
        system_map: dict[str, str] = {
            "Windows": "win",
            "Darwin": "osx",
            "Linux": "linux"
        }
        
        machine_map: dict[str, str] = {
            "AMD64": "x64",
            "x86_64": "x64",
            "i386": "x86",
            "i686": "x86",
            "aarch64": "arm64",
            "arm64": "arm64"
        }
        
        if platform_info.system in system_map and platform_info.machine in machine_map:
            platform_id: str = f"{system_map[platform_info.system]}-{machine_map[platform_info.machine]}"
            
            if platform_info.system == "Linux" and platform_info.bitness == "64bit":
                platform_info.libc = platform.libc_ver()[0]
                if platform_info.libc != "glibc":
                    platform_id += f"-{platform_info.libc}"
                    
            return PlatformId(platform_id)
        
        raise Exception(f"未知平台: {platform_info.system} {platform_info.machine} {platform_info.bitness}")
    def get_mac_address():
        """mac 硬件地址"""
        mac = uuid.getnode()
        return ":".join(["{:02x}".format((mac >> i) & 0xff) for i in range(0, 8 * 6, 8)][::-1])

if __name__ == "__main__":
    print(PlatformUtils.get_platform_id())