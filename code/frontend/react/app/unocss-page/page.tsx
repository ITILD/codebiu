"use client";

export default function UnoCSSPage() {
  return (
    <div className="min-h-screen bg-gradient-to-r from-blue-500 to-purple-600 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-8 text-center">
          UnoCSS 展示页面
        </h1>
        
        <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800">
            UnoCSS 功能演示
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-blue-100 p-4 rounded-lg">
              <h3 className="text-lg font-medium mb-2 text-blue-800">
                颜色工具类
              </h3>
              <div className="space-y-2">
                <div className="text-red-500">红色文字</div>
                <div className="text-green-500">绿色文字</div>
                <div className="text-blue-500">蓝色文字</div>
              </div>
            </div>
            
            <div className="bg-green-100 p-4 rounded-lg">
              <h3 className="text-lg font-medium mb-2 text-green-800">
                布局工具类
              </h3>
              <div className="flex items-center justify-between">
                <div className="bg-red-200 px-3 py-1 rounded">左</div>
                <div className="bg-blue-200 px-3 py-1 rounded">中</div>
                <div className="bg-green-200 px-3 py-1 rounded">右</div>
              </div>
            </div>
            
            <div className="bg-yellow-100 p-4 rounded-lg">
              <h3 className="text-lg font-medium mb-2 text-yellow-800">
                间距工具类
              </h3>
              <div className="space-y-3">
                <div className="bg-gray-200 p-2 rounded">小间距</div>
                <div className="bg-gray-300 p-4 rounded">中间距</div>
                <div className="bg-gray-400 p-6 rounded">大间距</div>
              </div>
            </div>
            
            <div className="bg-purple-100 p-4 rounded-lg">
              <h3 className="text-lg font-medium mb-2 text-purple-800">
                响应式设计
              </h3>
              <div className="text-sm md:text-lg lg:text-xl text-purple-600">
                不同屏幕尺寸的文字大小
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800">
            UnoCSS 与 Tailwind CSS 对比
          </h2>
          <p className="text-gray-600 mb-4">
            UnoCSS 是一个即时、按需的原子化 CSS 引擎，相比 Tailwind CSS 具有更好的性能：
          </p>
          <ul className="list-disc list-inside text-gray-600 space-y-2">
            <li>更快的构建速度</li>
            <li>更小的包体积</li>
            <li>更灵活的自定义规则</li>
            <li>更好的 TypeScript 支持</li>
          </ul>
        </div>
      </div>
    </div>
  );
}