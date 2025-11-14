### markdown常用格式

- 标题
```markdown
# 一级标题
## 二级标题
### 三级标题
#### 四级标题
##### 五级标题
###### 六级标题
```
- 表格
```markdown
| 表头1 | 表头2 | 表头3 |
| :---: | :---: | :---: |
| 表格1 | 表格2 | 表格3 |
| 表格1 | 表格2 | 表格3 |
```
- 代码块
```markdown
`单行代码`
```

- 列表
```markdown
- 无序列表
- 无序列表
- 无序列表

1. 有序列表
2. 有序列表
3. 有序列表
```

- 引用
```markdown
> 引用
```

- 链接
```markdown
[链接名称](链接地址)
```

- 图片
```markdown
![图片描述](图片地址)
```
代码
```python
@router.post(
    "", summary="创建模板", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_template(
    template: TemplateCreate, service: TemplateService = Depends(get_template_service)
) -> str:
    """
    创建新模板
    :param template: 模板数据
    :param service: 模板服务依赖注入
    :return: 创建的模板ID
    """
    try:
        return await service.add(template)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

```