import os
import sys

# 调试信息：打印当前环境
print("=== Python Environment Debug Info ===")
print(f"Current Working Directory: {os.getcwd()}")
print(f"Python Version: {sys.version}")
print("sys.path:")
for p in sys.path:
    print(f"  - {p}")

print("Directory listing of current dir:")
try:
    print(os.listdir('.'))
except Exception as e:
    print(f"Error listing dir: {e}")

# Add the current directory to sys.path so that 'backend' can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

print(f"Added root_dir to sys.path: {root_dir}")
print("Directory listing of root_dir:")
try:
    print(os.listdir(root_dir))
except Exception as e:
    print(f"Error listing root_dir: {e}")
print("=====================================")

from backend.app import create_app

app = create_app()
