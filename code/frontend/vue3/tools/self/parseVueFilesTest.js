import { parseVue3Files, parseVue3FileSingle } from './parseVueFiles.js'
/**
 * 主函数，读取目录并解析 Vue 3 文件
 * @returns {Promise<void>}
 */
async function main() {
  //   const dirPath = './path/to/your/vue3/files' // 替换为你的 Vue 3 文件目录

  const toFinds = {
    parent: '* @parent       :',
    summary: '* @summary      :',
    description: '* @description  :'
  }
  // 读取读取目录测试
  const dirPath = 'D:/github/codebiu/miniUI-example/src/pages/index/test' // 替换为你的 Vue 3 文件目录
  const results = await parseVue3Files(dirPath, toFinds)
  console.log('读取读取目录测试', JSON.stringify(results, null, 2))
  // 读取单个文件测试
  const filePath = 'D:/github/codebiu/miniUI-example/src/pages/index/test/todo.vue'
  const result = await parseVue3FileSingle(filePath, toFinds)
  console.log('读取单个文件测试', JSON.stringify(result, null, 2))
}

main()
