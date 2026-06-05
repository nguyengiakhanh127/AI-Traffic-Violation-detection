import os

def generate_tree(startpath: str, exclude_dirs: list[str]) -> None:
    """
    Duyệt và in cấu trúc cây thư mục, bỏ qua các thư mục không cần thiết.
    Chỉ hiển thị các tệp mã nguồn hoặc cấu hình.
    """
    for root, dirs, files in os.walk(startpath):
        # Lọc bỏ các thư mục trong danh sách loại trừ
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = '│   ' * level
        
        # In tên thư mục
        folder_name = os.path.basename(root) if root != startpath else "Project_Root"
        print(f'{indent}├── {folder_name}/')
        
        subindent = '│   ' * (level + 1)
        for f in files:
            # Lọc chỉ hiển thị các tệp quan trọng (bỏ qua ảnh, video, v.v.)
            if f.endswith(('.py', '.ui', '.json', '.yaml', '.txt', '.md')):
                print(f'{subindent}├── {f}')

if __name__ == "__main__":
    # Các thư mục cần loại bỏ (bao gồm môi trường ảo)
    EXCLUDE_DIRS = ['.git', '__pycache__', 'venv', '.venv', 'env', '.idea', '.vscode', 'models', 'weights', 'configs', 'data', 'demo_data', 'Evidence']
    
    current_path = os.getcwd()
    generate_tree(current_path, EXCLUDE_DIRS)