import os

# --- 配置区域 (更严格的过滤) ---

# 1. 只允许最核心的代码格式 (去掉了 .txt 和 .json，防止抓取大量数据)
ALLOWED_EXTENSIONS = {'.py', '.m', '.cpp', '.h', }

# 2. 强力忽略名单 (包含常见的虚拟环境、Git、编译目录)
IGNORE_DIRS = {
    '__pycache__', '.git', '.idea', '.vscode', 
    'venv', 'env', '.env', 'Lib', 'site-packages', 'Scripts', # Python环境
    'build', 'dist', 'bin', 'obj', # 编译产物
    'node_modules', # 如果有前端
    'data', 'results', 'mesh', 'figures' # 常见的力学/数据文件夹
}

# 3. 单个文件大小上限 (关键！设置为 50KB)
# 源代码文件很少超过 50KB (约 1000-2000 行)。超过的大概率是生成的垃圾或数据。
MAX_FILE_SIZE_KB = 100 

def is_text_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)
        return True
    except Exception:
        return False

def pack_project(output_file='project_context_lite.txt'):
    project_root = os.getcwd()
    total_lines = 0
    skipped_files = []
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(f"# Project Context (Lite Version)\n")
        out.write(f"# Root: {os.path.basename(project_root)}\n\n")
        
        # 1. 文件树 (依然保留，方便我看结构)
        out.write("## Project Structure\n```text\n")
        for root, dirs, files in os.walk(project_root):
            # 过滤文件夹
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            level = root.replace(project_root, '').count(os.sep)
            indent = '    ' * level
            out.write(f"{indent}{os.path.basename(root)}/\n")
            subindent = '    ' * (level + 1)
            for f in files:
                if os.path.splitext(f)[1] in ALLOWED_EXTENSIONS:
                    out.write(f"{subindent}{f}\n")
        out.write("```\n\n")
        
        # 2. 文件内容
        out.write("## File Contents\n")
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                file_ext = os.path.splitext(file)[1]
                if file_ext in ALLOWED_EXTENSIONS:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, project_root)
                    
                    # 检查文件大小
                    file_size_kb = os.path.getsize(file_path) / 1024
                    if file_size_kb > MAX_FILE_SIZE_KB:
                        skipped_files.append(f"{rel_path} ({file_size_kb:.1f} KB)")
                        out.write(f"\n<file path=\"{rel_path}\">\n# [SKIPPED] File too large ({file_size_kb:.1f} KB)\n</file>\n")
                        continue

                    if is_text_file(file_path):
                        out.write(f"\n<file path=\"{rel_path}\">\n")
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                lines = content.count('\n')
                                total_lines += lines
                                out.write(content)
                        except Exception as e:
                            out.write(f"# Error reading file: {e}")
                        out.write(f"\n</file>\n")
                        print(f"Packed: {rel_path}")

    print(f"\n{'='*30}")
    print(f"完成！生成文件: {output_file}")
    print(f"当前总行数: {total_lines} (这下应该正常了)")
    if skipped_files:
        print(f"\n已跳过的大文件 (>{MAX_FILE_SIZE_KB}KB):")
        for f in skipped_files:
            print(f" - {f}")
    print(f"{'='*30}")

if __name__ == '__main__':
    pack_project()