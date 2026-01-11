from enum import Enum


# class syntax
class CodeType(str, Enum):
    python = "python"
    java = "java"
    cpp = "cpp"
    javascript = "javascript"
    rust = "rust"
    html = "html"
    markdown = "markdown"
    dart = "dart"
    ruby = "ruby"
    c_sharp = "c-sharp"
    
    
    def __str__(self) -> str:
        return self.value
