import mimetypes

# 添加 Office Open XML 类型
mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx")

# 添加其他常见类型
mimetypes.add_type("text/x-java-source", ".java")
mimetypes.add_type("text/x-python", ".py")
# mimetypes.add_type("application/json", ".json")  # 通常已有，但确保

# 示例
# print(mimetypes.guess_extension("image/jpeg", strict=False))      # → ".jpe" 或 ".jpeg"（取决于系统）
# print(mimetypes.guess_type("photo.jpg"))   # → ("image/jpeg", None) 
# 确定文件的 MIME 类型
# content_type, _ = mimetypes.guess_type(path, strict=False)