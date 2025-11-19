import fs from 'fs'
import { parseVue3Files } from './parseVueFiles.js'


/**
 * 数组转化为树
 * 按parent分类,没有parent放入default
 * @param {*} results  
 * @returns 
 */
function formatList2Tree(results) {
  // 格式化成树状结构
  const fileMap = new Map()
  for (let index = 0; index < results.length; index++) {
    const result = results[index]
    if (result.name == 'index') continue
    // 默认 default
    const parent = result.parent || 'default'
    const arr = fileMap.get(parent)
    arr ? arr.push(result) : fileMap.set(parent, [result])
  }
  const resultsOut = []
  for (const [key, value] of fileMap) {
    resultsOut.push({ label: key, child: value })
  }

  return resultsOut
}

// 读取目录测试
const fileDealFlow = async (dirPath, toFinds) => {
  // 读取读取目录测试
  const results = await parseVue3Files(dirPath, toFinds)
  const resultsOut = formatList2Tree(results)
  const resultsStr = JSON.stringify(resultsOut, null, 2)
  const result = `const fileList = ${resultsStr}
    
export{fileList}
    `
  // 新建或覆盖文件并写入内容
  await fs.promises.writeFile(dirPath + '/index.ts', result, 'utf-8')
}

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
  fileDealFlow('./src/pages/index/component_mini', toFinds)
  fileDealFlow('./src/pages/index/component_lib', toFinds)
}

main()
