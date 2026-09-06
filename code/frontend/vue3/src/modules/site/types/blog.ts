// src/modules/site/types/blog.ts —— 博客文章类型

/** 发布来源: markdown 在线编辑 / url 关联外链 */
export type PostSource = 'markdown' | 'url'

/** 发布状态: 草稿 / 已发布 */
export type PostStatus = 'draft' | 'published'

/** 博客文章实体 */
export interface BlogPost {
  id: string
  /** 作者用户ID */
  user_id: string
  title: string
  source_type: PostSource
  /** markdown 正文(source_type=url 时可空) */
  content: string
  /** 关联外链地址(source_type=url 时使用) */
  url: string | null
  category: string | null
  status: PostStatus
  created_at: string
  updated_at: string
}

/** 创建博客文章参数 */
export interface BlogPostCreate {
  title: string
  source_type?: PostSource
  content?: string
  url?: string | null
  category?: string | null
  status?: PostStatus
}

/** 更新博客文章参数(全部可选, 仅更新传入字段) */
export type BlogPostUpdate = Partial<BlogPostCreate>
