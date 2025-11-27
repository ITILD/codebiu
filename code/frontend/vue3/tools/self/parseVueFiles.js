// nodejs
import fs from 'fs'
import path from 'path'
import { parse } from '@vue/compiler-sfc'

/**
 * 读取目录下的所有文件和子目录
 * @param {string} dirPath - 目录路径
 * @returns {Promise<Array>} - 包含文件和子目录信息的数组
 */
function readDirectory(dirPath) {
  return fs.promises.readdir(dirPath, { withFileTypes: true })
}

/**
 * 读取目录下的所有文件和子目录
 * @param {string} dirPath - 目录路径
 * @returns {Promise<Array>} - 递归包含文件和子目录信息的数组
 */
async function readDirectoryAll(dirPath) {
  const entries = await readDirectory(dirPath)
  const result = [...entries]
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name)
    if (entry.isDirectory()) {
      const subEntries = await readDirectoryAll(fullPath)
      result.push(...subEntries)
    }
  }
  return result
}

/**
 * 检查文件是否为 Vue 文件
 * @param {fs.Dirent} file - 文件信息对象
 * @returns {boolean} - 是否为 Vue 文件
 */
function isVueFile(file) {
  return file.isFile() && path.extname(file.name) === '.vue'
}

/**
 * 从代码中提取注释
 * @param {string} code - 文件内容
 * @returns {Array<string>} - 注释数组
 */
function extractComments(code) {
  const commentRegex = /\/\*[^*]*\*+([^/*][^*]*\*+)*\//g
  let comments = []
  let match
  while ((match = commentRegex.exec(code)) !== null) {
    comments.push(match[0])
  }
  return comments
}

function extractPath(fullPath) {
  // 使用 path 模块将路径转换为标准格式
  const normalizedPath = path.normalize(fullPath)

  // 使用正则表达式匹配 'pages' 和 '.vue' 之间的路径部分
  // const regex = /pages(.*?).vue/
  // const regex = /pages\\index\\(.*?).vue/;
  // 首位保留/  作为绝对路径
  // const regex = /pages\\index(.*?).vue/;
  const regex = /pages\\index(.*).vue/;
  const match = normalizedPath.match(regex)
  // console.log('match', match[1],match,normalizedPath)
  if (match && match[1]) return match[1].replace(/\\/g, '/')
  return '未识别!'
}

/**
 * 解析多行注释，提取描述和作者信息
 * @param {string} comment - 多行注释字符串
 * @param {Array} toFinds - 需要查找的注释关键词
 * @returns {Object} - 包含描述和作者的对象
 */
function parseComment(comment, toFinds) {
  const lines = comment.split('\n').map((line) => line.trim())
  const result = {}
  lines.forEach((line) => {
    // 每行注释查找关键词
    for (const key in toFinds) {
      const value = toFinds[key]
      if (line.startsWith(value)) {
        result[key] = line.replace(value, '').trim()
      }
    }
  })
  return result
}

/**
 * 解析目录下的所有 Vue 3 文件，并提取文件名和注释
 * @param {string} dirPath - 目录路径
 * @param {Array} toFinds - 需要查找的注释关键词
 * @returns {Promise<Array>} - 包含文件名和注释的数组 [{"key0": "value0",}]
 */
async function parseVue3Files(dirPath, toFinds) {
  // 获取dirPath和子文件夹的所有文件
  // const files = await readDirectory(dirPath)
  const files = await readDirectoryAll(dirPath)
  const vueFiles = files.filter(isVueFile)
  const results = []
  for (const file of vueFiles) {
    const properties = await parseVue3FileSingle(path.join(file.path, file.name), toFinds)
    properties && results.push(properties)
  }
  return results
}

/**
 * 解析单个 Vue 3 文件，并提取文件名和注释
 * @param {string} filePath - 文件路径
 * @param {Array} toFinds - 需要查找的注释关键词
 * @returns {Promise<Object>} - 包含文件名和注释的对象 {"key0": "value0",}
 * */
async function parseVue3FileSingle(filePath, toFinds) {
  const fileContent = await fs.promises.readFile(filePath, 'utf-8')
  //获取'pages'和'.vue'中间路径
  const pathFromPagesVue = extractPath(filePath)

  const parsed = parse(fileContent)
  // 文件名
  const fileName = path.basename(filePath)
  // 脚本内容
  const scriptContent = parsed.descriptor.scriptSetup ? parsed.descriptor.scriptSetup.content : ''
  // 注释
  const comments = extractComments(scriptContent)
  // 获取具体注释
  const commentResult = []
  for (const comment of comments) {
    commentResult.push(parseComment(comment, toFinds))
  }
  // 获取第一批注释属性  没有就{}
  const properties = commentResult[0]||{}
  properties.name = fileName.split('.')[0]
  properties.pathFromPagesVue = pathFromPagesVue
  // 每行注释查找关键词
  for (const key in toFinds) {
    properties[key] = properties[key]|| ''
  }
  return properties
}

export { parseVue3Files, parseVue3FileSingle }
