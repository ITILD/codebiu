// src/modules/site/api/blog.ts —— 博客文章接口(/site/blog/posts)
import { http_base_server } from '@/common/api/http'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type { BlogPost, BlogPostCreate, BlogPostUpdate } from '../types/blog'

/** 我的文章列表查询参数(分页 + 过滤) */
export interface ListMyPostsParams extends PaginationParams {
  /** 标题模糊搜索 */
  title?: string
  /** 状态过滤(draft/published) */
  status?: string
  /** 来源过滤(markdown/url) */
  source_type?: string
}

/** 发布博客文章(markdown 在线编辑 或 关联 URL) */
export const createBlogPost = (post: BlogPostCreate) => {
  return http_base_server.post<string>('/site/blog/posts', post)
}

/** 删除博客文章(仅作者可删) */
export const deleteBlogPost = (postId: string) => {
  return http_base_server.delete<void>(`/site/blog/posts/${postId}`)
}

/** 更新博客文章(改标题/正文/外链/状态等) */
export const updateBlogPost = (postId: string, post: BlogPostUpdate) => {
  return http_base_server.put<void>(`/site/blog/posts/${postId}`, post)
}

/** 获取文章详情(草稿仅作者可见, 已发布对持有读权限用户可见) */
export const getBlogPost = (postId: string) => {
  return http_base_server.get<BlogPost>(`/site/blog/posts/${postId}`)
}

/** 分页查询我的文章列表(管理页) */
export const listMyPosts = (params: ListMyPostsParams) => {
  return http_base_server.get<PaginationResponse<BlogPost>>('/site/blog/posts/list', { params })
}

/** 分页查询已发布文章(展示页) */
export const listPublishedPosts = (params: PaginationParams & { keyword?: string }) => {
  return http_base_server.get<PaginationResponse<BlogPost>>('/site/blog/posts/view/list', { params })
}
