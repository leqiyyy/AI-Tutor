import { useState } from 'react';
import { Link } from 'react-router-dom';

export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 固定导航栏 */}
      <nav className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-50">
        <div className="px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2">
                <img src="https://public.readdy.ai/ai/img_res/2625f127-2f4f-41ee-82d8-6c2fa4dee4ac.png" alt="珞樱学堂" className="h-9 w-9" />
                <span className="text-lg font-semibold text-gray-900">珞樱学堂 · 管理端</span>
              </Link>
              <div className="flex items-center gap-1">
                <button onClick={() => setActiveTab('overview')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'overview' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>系统概览</button>
                <button onClick={() => setActiveTab('users')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'users' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>用户管理</button>
                <button onClick={() => setActiveTab('courses')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'courses' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>课程管理</button>
                <button onClick={() => setActiveTab('audit')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors relative ${activeTab === 'audit' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>
                  内容审核
                  <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                </button>
                <button onClick={() => setActiveTab('settings')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'settings' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>系统设置</button>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-gray-900 cursor-pointer">
                <i className="ri-notification-3-line text-lg"></i>
              </button>
              <div className="w-8 h-8 rounded-full bg-purple-500 flex items-center justify-center text-white text-sm font-medium cursor-pointer">管</div>
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容区 */}
      <div className="pt-16 px-6 py-6">
        {activeTab === 'overview' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">系统概览</h1>
            
            {/* 基础数据 */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">注册教师</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-blue-50">
                    <i className="ri-user-star-line text-blue-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">156</div>
                <div className="text-xs text-green-600 mt-1">+8 本月</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">注册学生</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-green-50">
                    <i className="ri-group-line text-green-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">3,842</div>
                <div className="text-xs text-green-600 mt-1">+127 本月</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">开设课程</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-purple-50">
                    <i className="ri-book-open-line text-purple-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">284</div>
                <div className="text-xs text-gray-500 mt-1">本学期</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">活跃班级</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-orange-50">
                    <i className="ri-team-line text-orange-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">218</div>
                <div className="text-xs text-gray-500 mt-1">近7天活跃</div>
              </div>
            </div>

            {/* 待办提醒 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200 mb-6">
              <h2 className="text-base font-semibold text-gray-900 mb-4">待办提醒</h2>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-red-50 border border-red-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">待审核注册</span>
                    <div className="w-7 h-7 flex items-center justify-center rounded-full bg-red-500 text-white text-xs font-bold">12</div>
                  </div>
                  <div className="text-xs text-gray-600">教师资质审核 8 人 · 学生学籍核验 4 人</div>
                  <button className="mt-3 w-full px-3 py-1.5 text-xs font-medium text-red-600 bg-red-100 rounded-md hover:bg-red-200 cursor-pointer whitespace-nowrap">立即处理</button>
                </div>
                <div className="p-4 rounded-lg bg-orange-50 border border-orange-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">知识库异常</span>
                    <div className="w-7 h-7 flex items-center justify-center rounded-full bg-orange-500 text-white text-xs font-bold">5</div>
                  </div>
                  <div className="text-xs text-gray-600">索引构建失败 3 个 · 资料解析错误 2 个</div>
                  <button className="mt-3 w-full px-3 py-1.5 text-xs font-medium text-orange-600 bg-orange-100 rounded-md hover:bg-orange-200 cursor-pointer whitespace-nowrap">查看详情</button>
                </div>
                <div className="p-4 rounded-lg bg-blue-50 border border-blue-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">待处理举报</span>
                    <div className="w-7 h-7 flex items-center justify-center rounded-full bg-blue-500 text-white text-xs font-bold">3</div>
                  </div>
                  <div className="text-xs text-gray-600">内容举报 2 条 · AI回答错误 1 条</div>
                  <button className="mt-3 w-full px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-100 rounded-md hover:bg-blue-200 cursor-pointer whitespace-nowrap">前往审核</button>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              {/* 近期动态 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">近期动态</h2>
                <div className="space-y-3">
                  {[
                    { type: 'user', title: '新用户注册', content: '计算机学院 8 名教师完成注册', time: '10分钟前', color: 'green' },
                    { type: 'course', title: '课程创建', content: '王教授创建了"深度学习基础"课程', time: '1小时前', color: 'blue' },
                    { type: 'announcement', title: '系统公告', content: '发布了"期末考试安排"全校公告', time: '3小时前', color: 'purple' },
                    { type: 'backup', title: '数据备份', content: '系统自动备份已完成', time: '5小时前', color: 'teal' },
                    { type: 'user', title: '学生注册', content: '软件学院 23 名学生完成学籍核验', time: '1天前', color: 'green' }
                  ].map((activity, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50">
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg bg-${activity.color}-50 flex-shrink-0`}>
                        <i className={`text-base ${
                          activity.type === 'user' ? `ri-user-add-line text-${activity.color}-600` :
                          activity.type === 'course' ? `ri-book-line text-${activity.color}-600` :
                          activity.type === 'announcement' ? `ri-megaphone-line text-${activity.color}-600` :
                          `ri-save-line text-${activity.color}-600`
                        }`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">{activity.title}</div>
                        <div className="text-xs text-gray-600 mt-1">{activity.content}</div>
                        <div className="text-xs text-gray-400 mt-1">{activity.time}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 系统状态 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">系统状态</h2>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">服务器负载</span>
                      <span className="text-sm font-semibold text-green-600">正常</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-green-500 rounded-full" style={{ width: '35%' }}></div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">CPU: 35% · 内存: 42%</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">数据库状态</span>
                      <span className="text-sm font-semibold text-green-600">运行中</span>
                    </div>
                    <div className="text-xs text-gray-500">连接数: 156/500 · 响应时间: 12ms</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">AI服务状态</span>
                      <span className="text-sm font-semibold text-green-600">正常</span>
                    </div>
                    <div className="text-xs text-gray-500">今日调用: 8,234 次 · 平均响应: 1.2s</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">存储空间</span>
                      <span className="text-sm font-semibold text-orange-600">68%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-orange-500 rounded-full" style={{ width: '68%' }}></div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">已用 680GB / 总计 1TB</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">最近备份</span>
                      <span className="text-sm font-semibold text-gray-900">5小时前</span>
                    </div>
                    <div className="text-xs text-gray-500">下次自动备份: 今天 23:00</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'users' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">用户管理</h1>
            
            {/* 注册审核 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900">注册审核</h2>
                <div className="flex items-center gap-2">
                  <button className="px-3 py-1.5 text-sm font-medium text-green-600 border border-green-600 rounded-lg hover:bg-green-50 cursor-pointer whitespace-nowrap">批量通过</button>
                  <button className="px-3 py-1.5 text-sm font-medium text-red-600 border border-red-600 rounded-lg hover:bg-red-50 cursor-pointer whitespace-nowrap">批量拒绝</button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">
                        <input type="checkbox" className="w-4 h-4 text-teal-600 border-gray-300 rounded" />
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">姓名</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">角色</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">院系</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">工号/学号</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">申请时间</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {[
                      { name: '张伟', role: '教师', dept: '计算机学院', id: 'T2024001', time: '2小时前' },
                      { name: '李娜', role: '教师', dept: '软件学院', id: 'T2024002', time: '3小时前' },
                      { name: '王强', role: '学生', dept: '计算机学院', id: '2024301001', time: '5小时前' },
                      { name: '刘芳', role: '学生', dept: '软件学院', id: '2024302001', time: '1天前' }
                    ].map((user, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <input type="checkbox" className="w-4 h-4 text-teal-600 border-gray-300 rounded" />
                        </td>
                        <td className="px-4 py-3 font-medium text-gray-900">{user.name}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${user.role === '教师' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600'}`}>
                            {user.role}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{user.dept}</td>
                        <td className="px-4 py-3 text-gray-600 font-mono text-xs">{user.id}</td>
                        <td className="px-4 py-3 text-gray-500">{user.time}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button className="px-3 py-1 text-xs font-medium text-green-600 bg-green-50 rounded-md hover:bg-green-100 cursor-pointer whitespace-nowrap">通过</button>
                            <button className="px-3 py-1 text-xs font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 cursor-pointer whitespace-nowrap">拒绝</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 用户列表 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900">用户列表</h2>
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <input type="text" placeholder="搜索用户..." className="w-64 pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
                    <i className="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
                  </div>
                  <select className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                    <option>全部角色</option>
                    <option>教师</option>
                    <option>学生</option>
                    <option>管理员</option>
                  </select>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">姓名</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">角色</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">院系</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">注册时间</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">登录状态</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {[
                      { name: '王教授', role: '教师', dept: '计算机学院', date: '2023-09-01', status: '在线' },
                      { name: '李教授', role: '教师', dept: '软件学院', date: '2023-09-01', status: '离线' },
                      { name: '李明', role: '学生', dept: '计算机学院', date: '2023-09-15', status: '在线' },
                      { name: '张华', role: '学生', dept: '软件学院', date: '2023-09-15', status: '在线' },
                      { name: '刘洋', role: '学生', dept: '计算机学院', date: '2023-09-16', status: '离线' }
                    ].map((user, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{user.name}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${user.role === '教师' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600'}`}>
                            {user.role}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{user.dept}</td>
                        <td className="px-4 py-3 text-gray-600">{user.date}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 text-xs ${user.status === '在线' ? 'text-green-600' : 'text-gray-500'}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${user.status === '在线' ? 'bg-green-500' : 'bg-gray-400'}`}></span>
                            {user.status}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">查看</button>
                            <button className="text-xs text-gray-600 hover:text-gray-700 cursor-pointer whitespace-nowrap">重置密码</button>
                            <button className="text-xs text-red-600 hover:text-red-700 cursor-pointer whitespace-nowrap">禁用</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'courses' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">课程管理</h1>
            
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900">课程总览</h2>
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <input type="text" placeholder="搜索课程..." className="w-64 pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
                    <i className="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
                  </div>
                  <select className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                    <option>全部学院</option>
                    <option>计算机学院</option>
                    <option>软件学院</option>
                    <option>信息学院</option>
                  </select>
                  <select className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                    <option>本学期</option>
                    <option>上学期</option>
                    <option>全部学期</option>
                  </select>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">课程名称</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">授课教师</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">学生人数</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">知识库状态</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">最后活跃</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {[
                      { name: '计算机网络', teacher: '王教授', students: 68, kb: '正常', docs: 45, active: '2小时前' },
                      { name: '数据结构与算法', teacher: '李教授', students: 82, kb: '正常', docs: 62, active: '1小时前' },
                      { name: '操作系统原理', teacher: '张教授', students: 56, kb: '异常', docs: 28, active: '5小时前' },
                      { name: '数据库系统', teacher: '刘教授', students: 74, kb: '正常', docs: 51, active: '3小时前' },
                      { name: '软件工程', teacher: '陈教授', students: 91, kb: '正常', docs: 38, active: '1天前' },
                      { name: '人工智能基础', teacher: '赵教授', students: 63, kb: '正常', docs: 72, active: '4小时前' }
                    ].map((course, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{course.name}</td>
                        <td className="px-4 py-3 text-gray-600">{course.teacher}</td>
                        <td className="px-4 py-3 text-gray-600">{course.students} 人</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${course.kb === '正常' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                              {course.kb}
                            </span>
                            <span className="text-xs text-gray-500">{course.docs} 份资料</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-500">{course.active}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">查看详情</button>
                            <button className="text-xs text-gray-600 hover:text-gray-700 cursor-pointer whitespace-nowrap">转移负责人</button>
                            <button className="text-xs text-orange-600 hover:text-orange-700 cursor-pointer whitespace-nowrap">归档</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">内容审核</h1>
            
            <div className="grid grid-cols-2 gap-6">
              {/* AI回答抽检 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">AI回答抽检</h2>
                <div className="space-y-3">
                  {[
                    { question: 'TCP三次握手的第三次可以携带数据吗?', answer: '可以。第三次握手时,客户端已经处于ESTABLISHED状态...', dislike: 3, course: '计算机网络' },
                    { question: '红黑树的旋转操作有哪些?', answer: '红黑树有四种旋转操作:左旋、右旋、左右旋、右左旋...', dislike: 2, course: '数据结构' },
                    { question: '进程和线程的区别是什么?', answer: '进程是资源分配的基本单位,线程是CPU调度的基本单位...', dislike: 5, course: '操作系统' }
                  ].map((item, index) => (
                    <div key={index} className="p-4 rounded-lg border border-gray-200 hover:border-gray-300">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900 mb-1">{item.question}</div>
                          <div className="text-xs text-gray-600 line-clamp-2">{item.answer}</div>
                        </div>
                        <span className="ml-3 px-2 py-1 text-xs font-medium bg-red-50 text-red-600 rounded-full flex-shrink-0">
                          {item.dislike} 次点踩
                        </span>
                      </div>
                      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                        <span className="text-xs text-gray-500">{item.course}</span>
                        <div className="flex items-center gap-2">
                          <button className="px-3 py-1 text-xs font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 cursor-pointer whitespace-nowrap">查看完整</button>
                          <button className="px-3 py-1 text-xs font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 cursor-pointer whitespace-nowrap">标记错误</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 举报处理 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">举报处理</h2>
                <div className="space-y-3">
                  {[
                    { type: '版权侵权', content: '课程资料"深度学习PPT"疑似侵权', reporter: '学生A', time: '2小时前' },
                    { type: '知识错误', content: 'AI回答关于"快速排序时间复杂度"存在错误', reporter: '教师B', time: '5小时前' },
                    { type: '不当内容', content: '讨论区存在不当言论', reporter: '学生C', time: '1天前' }
                  ].map((report, index) => (
                    <div key={index} className="p-4 rounded-lg border border-gray-200 hover:border-gray-300">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="px-2 py-0.5 text-xs font-medium bg-orange-50 text-orange-600 rounded-full">{report.type}</span>
                            <span className="text-xs text-gray-500">{report.time}</span>
                          </div>
                          <div className="text-sm text-gray-900 mb-1">{report.content}</div>
                          <div className="text-xs text-gray-500">举报人: {report.reporter}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
                        <button className="flex-1 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 cursor-pointer whitespace-nowrap">查看详情</button>
                        <button className="flex-1 px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 cursor-pointer whitespace-nowrap">删除内容</button>
                        <button className="flex-1 px-3 py-1.5 text-xs font-medium text-green-600 bg-green-50 rounded-md hover:bg-green-100 cursor-pointer whitespace-nowrap">驳回举报</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 敏感词配置 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200 mt-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900">敏感词配置</h2>
                <button className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap">
                  <i className="ri-add-line mr-1"></i>添加敏感词
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {['病毒编写', '系统攻击', '密码破解', '数据窃取', '恶意代码', '黑客工具', '漏洞利用', 'SQL注入'].map((word, index) => (
                  <div key={index} className="flex items-center gap-2 px-3 py-1.5 bg-red-50 border border-red-100 rounded-lg">
                    <span className="text-sm text-red-600">{word}</span>
                    <button className="w-4 h-4 flex items-center justify-center text-red-600 hover:text-red-700 cursor-pointer">
                      <i className="ri-close-line text-xs"></i>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">系统设置</h1>
            
            <div className="space-y-5">
              {/* 维护模式 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">维护模式</h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 rounded-lg bg-gray-50">
                    <div>
                      <div className="text-sm font-medium text-gray-900">系统维护模式</div>
                      <div className="text-xs text-gray-600 mt-1">开启后将暂停服务并显示维护公告</div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-teal-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-lg bg-gray-50">
                    <div>
                      <div className="text-sm font-medium text-gray-900">考试周限流</div>
                      <div className="text-xs text-gray-600 mt-1">限制AI调用频次,防止服务器卡顿</div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" checked className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-teal-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
                    </label>
                  </div>
                </div>
              </div>

              {/* 数据备份 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">数据备份</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">自动备份周期</label>
                    <select className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                      <option>每天 23:00</option>
                      <option>每周日 23:00</option>
                      <option>每月1日 23:00</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-3">
                    <button className="flex-1 px-4 py-2 text-sm font-medium text-teal-600 border border-teal-600 rounded-lg hover:bg-teal-50 transition-colors cursor-pointer whitespace-nowrap">立即备份</button>
                    <button className="flex-1 px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap">查看备份历史</button>
                  </div>
                  <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                    <div className="flex items-start gap-2">
                      <i className="ri-information-line text-blue-600 text-base mt-0.5"></i>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-blue-900">最近备份</div>
                        <div className="text-xs text-blue-700 mt-1">2024-01-15 23:00 · 数据库 + 知识库 · 大小: 2.3GB</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 全局公告 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">全局公告</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">公告标题</label>
                    <input type="text" placeholder="输入公告标题..." className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">公告内容</label>
                    <textarea rows={4} placeholder="输入公告内容..." className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"></textarea>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">发送范围</label>
                    <select className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                      <option>全校师生</option>
                      <option>全体教师</option>
                      <option>全体学生</option>
                      <option>指定学院</option>
                    </select>
                  </div>
                  <button className="w-full px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap">发布公告</button>
                </div>
              </div>

              {/* 基础配置 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">基础配置</h2>
                <div className="space-y-3">
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900">学科专业结构</div>
                      <div className="text-xs text-gray-500 mt-1">维护院系和专业信息</div>
                    </div>
                    <button className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap">管理</button>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900">统一认证配置</div>
                      <div className="text-xs text-gray-500 mt-1">对接校园CAS认证系统</div>
                    </div>
                    <button className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap">配置</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}