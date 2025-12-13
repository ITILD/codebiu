from langchain_huggingface import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer
from pathlib import Path

# 设置模型ID和本地路径
model_id = "Qwen/Qwen3-0.6B"
local_model_path = Path("temp/models/Qwen3-0.6B")  # 使用Path对象

# 检查本地路径是否存在，不存在则下载
if not local_model_path.exists():
    print(f"模型未在本地找到，开始下载到 {local_model_path}...")
    # 下载tokenizer和模型
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id)
    
    # 保存到本地 - 使用mkdir代替os.makedirs
    local_model_path.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(local_model_path)
    model.save_pretrained(local_model_path)
    print("模型下载并保存完成！")
else:
    print(f"从本地路径 {local_model_path} 加载模型...")

# 从本地路径加载模型
llm = HuggingFacePipeline.from_model_id(
    model_id=str(local_model_path),  # 转换为字符串路径
    task="text-generation",
    pipeline_kwargs={"max_new_tokens": 512, "temperature": 0.7}
)
print("模型已加载！")

question = "1+1? 只输出结果"
result = llm.invoke(question)
print(result)