"use client";

import Link from "next/link";
import { Button } from "antd";

export default function Home() {
  return (
    <div className="w-full p-10">
      <div className="hero-section">
        <h2 className="text-4xl font-bold mb-4">欢迎来到网站首页</h2>
        <p className="text-xl mb-8 max-w-2xl mx-auto">首页示例，您可以通过顶部导航栏切换到服务器管理页面。</p>
        <Link href="/_server">
          <Button type="primary" size="large" className="bg-blue-600 hover:bg-blue-700">
            前往服务器管理
          </Button>
        </Link>
      </div>
      
      <div className="features-section mt-12">
        <h3 className="text-3xl font-bold text-center mb-8">主要功能</h3>
        <div className="features-grid grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="feature-card bg-gray-100 p-6 rounded-lg text-center transition-transform duration-300 hover:translate-y-[-5px] hover:shadow-lg">
            <h4 className="text-xl font-semibold text-blue-700 mb-3">简单易用</h4>
            <p className="text-gray-600">直观的界面设计，让您轻松上手。</p>
          </div>
          <div className="feature-card bg-gray-100 p-6 rounded-lg text-center transition-transform duration-300 hover:translate-y-[-5px] hover:shadow-lg">
            <h4 className="text-xl font-semibold text-blue-700 mb-3">服务器管理</h4>
            <p className="text-gray-600">查看和管理您的服务器资源。</p>
          </div>
          <div className="feature-card bg-gray-100 p-6 rounded-lg text-center transition-transform duration-300 hover:translate-y-[-5px] hover:shadow-lg">
            <h4 className="text-xl font-semibold text-blue-700 mb-3">响应式设计</h4>
            <p className="text-gray-600">在各种设备上都能获得良好的体验。</p>
          </div>
        </div>
      </div>
      
      <style jsx global>{`
        .hero-section {
          text-align: center;
          padding: 3rem 0;
          margin-bottom: 2rem;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border-radius: 8px;
        }
        
        .hero-section h2 {
          font-size: 2.5rem;
          margin-bottom: 1rem;
        }
        
        .hero-section p {
          font-size: 1.2rem;
          margin-bottom: 2rem;
          max-width: 600px;
          margin-left: auto;
          margin-right: auto;
        }
        
        .features-section h3 {
          text-align: center;
          font-size: 1.8rem;
          margin-bottom: 2rem;
        }
      `}</style>
    </div>
  );
}
