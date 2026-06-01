import os
import platform
import shutil

try:
    import psutil
except ImportError:
    psutil = None


class SystemMonitorService:

    @staticmethod
    def get_system_info():

        return {
            "os": platform.system(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu": SystemMonitorService.get_cpu_usage(),
            "memory": SystemMonitorService.get_memory_usage(),
            "disk": SystemMonitorService.get_disk_usage(),
            "termux": SystemMonitorService.is_termux(),
            "psutil_available": psutil is not None
        }

    @staticmethod
    def is_termux():
        return (
            'com.termux' in os.environ.get('PREFIX', '')
            or os.path.exists('/data/data/com.termux')
        )

    # =========================
    # CPU
    # =========================

    @staticmethod
    def get_cpu_usage():

        if psutil:
            return {
                "percent": psutil.cpu_percent(interval=1),
                "cores": psutil.cpu_count()
            }

        # fallback Linux/Android
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()

            values = line.split()[1:]

            total = sum(map(int, values))
            idle = int(values[3])

            usage = round((1 - idle / total) * 100, 2)

            return {
                "percent": usage,
                "cores": os.cpu_count()
            }

        except Exception as e:
            return {
                "error": str(e)
            }

    # =========================
    # MEMÓRIA
    # =========================

    @staticmethod
    def get_memory_usage():

        if psutil:

            mem = psutil.virtual_memory()

            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent": mem.percent
            }

        # fallback Linux/Android
        try:

            meminfo = {}

            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    key, value = line.split(':')
                    meminfo[key] = int(value.strip().split()[0])

            total = meminfo['MemTotal']
            available = meminfo['MemAvailable']

            used = total - available

            percent = round((used / total) * 100, 2)

            return {
                "total_gb": round(total / 1024 / 1024, 2),
                "used_gb": round(used / 1024 / 1024, 2),
                "percent": percent
            }

        except Exception as e:
            return {
                "error": str(e)
            }

    # =========================
    # DISCO
    # =========================

    @staticmethod
    def get_disk_usage():

        try:

            disk = shutil.disk_usage("/")

            total = round(disk.total / (1024**3), 2)
            used = round(disk.used / (1024**3), 2)
            free = round(disk.free / (1024**3), 2)

            percent = round((used / disk.total) * 100, 2)

            return {
                "total_gb": total,
                "used_gb": used,
                "free_gb": free,
                "percent": percent
            }

        except Exception as e:
            return {
                "error": str(e)
            }