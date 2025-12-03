import os
import sys

# Add packages directory to sys.path
# 在 Vercel 环境中，依赖被安装到了 packages 目录
packages_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'packages')
if os.path.exists(packages_dir):
    sys.path.insert(0, packages_dir)

# Add the current directory to sys.path so that 'backend' can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

# 调试信息：打印当前环境
print("=== Python Environment Debug Info ===")
print(f"Current Working Directory: {os.getcwd()}")
print("sys.path:")
for p in sys.path:
    print(f"  - {p}")

print("Directory listing of packages dir:")
try:
    if os.path.exists(packages_dir):
        print(os.listdir(packages_dir)[:20]) # 只打印前20个
    else:
        print("packages dir not found!")
except Exception as e:
    print(f"Error listing packages dir: {e}")
print("=====================================")

from backend.app import create_app

app = create_app()
