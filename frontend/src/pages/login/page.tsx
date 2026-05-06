import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getDefaultRouteForRole } from '@/lib/role-routes';
import { authService } from '@/services/auth';
import type { AppRole } from '@/types/auth';

type Role = AppRole;

const roles = [
  {
    key: 'student' as Role,
    label: '学生',
    desc: '加入课程、完成作业、AI答疑',
    icon: 'ri-graduation-cap-line',
    color: 'teal',
    bg: 'bg-teal-50',
    border: 'border-teal-400',
    iconBg: 'bg-teal-100',
    iconColor: 'text-teal-600',
    badge: 'bg-teal-500',
    path: '/student-dashboard',
  },
  {
    key: 'teacher' as Role,
    label: '教师',
    desc: '创建课程、发布任务、管理学生',
    icon: 'ri-user-star-line',
    color: 'orange',
    bg: 'bg-orange-50',
    border: 'border-orange-400',
    iconBg: 'bg-orange-100',
    iconColor: 'text-orange-600',
    badge: 'bg-orange-500',
    path: '/teacher-dashboard',
  },
  {
    key: 'admin' as Role,
    label: '管理员',
    desc: '用户审核、系统管理、内容监管',
    icon: 'ri-shield-user-line',
    color: 'slate',
    bg: 'bg-slate-50',
    border: 'border-slate-400',
    iconBg: 'bg-slate-100',
    iconColor: 'text-slate-600',
    badge: 'bg-slate-500',
    path: '/admin-dashboard',
  },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const [selectedRole, setSelectedRole] = useState<Role>('student');
  const [account, setAccount] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const currentRole = roles.find((r) => r.key === selectedRole)!;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!account.trim()) {
      setError('请输入账号');
      return;
    }
    if (!password.trim()) {
      setError('请输入密码');
      return;
    }
    setLoading(true);
    try {
      const result = await authService.login({
        role: selectedRole,
        account: account.trim(),
        password,
      });
      navigate(result.redirectTo || getDefaultRouteForRole(result.user.role));
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : '登录失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-soft min-h-screen flex" style={{ fontFamily: "'Noto Sans SC', sans-serif" }}>
      {/* 左侧品牌区 */}
      <div className="hidden lg:flex lg:w-[52%] relative flex-col overflow-hidden">
        <img
          src="https://readdy.ai/api/search-image?query=Beautiful%20Chinese%20university%20campus%20cherry%20blossom%20trees%20in%20full%20bloom%20along%20a%20serene%20pathway%20with%20modern%20academic%20buildings%20in%20the%20background%2C%20soft%20warm%20spring%20light%20filtering%20through%20pink%20petals%2C%20elegant%20and%20peaceful%20atmosphere%2C%20high%20quality%20photography%20style%20with%20shallow%20depth%20of%20field%2C%20pastel%20pink%20and%20white%20tones%2C%20professional%20educational%20institution%20aesthetic&width=900&height=1080&seq=login-bg-1&orientation=portrait"
          alt="珞樱学堂"
          className="absolute inset-0 w-full h-full object-cover object-top"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-teal-900/70 via-teal-800/50 to-teal-600/40"></div>

        {/* Logo */}
        <div className="relative z-10 p-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <i className="ri-plant-line text-white text-xl"></i>
            </div>
            <span className="text-2xl font-bold text-white tracking-wide">珞樱学堂</span>
          </div>
        </div>

        {/* 中间文案 */}
        <div className="relative z-10 flex-1 flex items-center px-10 pb-16">
          <div className="max-w-xl">
            <h1 className="text-4xl font-bold text-white leading-tight mb-5">
              基于大语言模型和检索增强生成的AI助教平台
            </h1>
            <p className="text-white text-base leading-relaxed mb-8">
              面向课程知识库构建、智能问答与教学辅助场景，提供面向师生的学习支持服务。
            </p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: 'ri-database-2-line', title: '课程知识库', desc: '支持课程资料解析与索引构建' },
                { icon: 'ri-node-tree', title: '知识图谱', desc: '组织课程概念与知识关系' },
                { icon: 'ri-chat-3-line', title: '检索增强问答', desc: '结合课程证据生成回答' },
                { icon: 'ri-user-settings-line', title: '教师审核回流', desc: '支持问答质量审核与知识沉淀' },
              ].map((item) => (
                <div key={item.title} className="rounded-xl bg-white/18 backdrop-blur-sm border border-white/25 p-4">
                  <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/25 mb-3">
                    <i className={`${item.icon} text-white text-lg`}></i>
                  </div>
                  <div className="text-white text-sm font-semibold">{item.title}</div>
                  <div className="text-white text-xs leading-relaxed mt-1">{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 右侧登录区 */}
      <div className="flex-1 flex flex-col justify-center items-center bg-white px-8 py-12">
        <div className="w-full max-w-md">
          {/* 移动端 Logo */}
          <div className="flex lg:hidden items-center gap-2 mb-8 justify-center">
            <div className="w-9 h-9 rounded-xl bg-teal-500 flex items-center justify-center">
              <i className="ri-plant-line text-white text-lg"></i>
            </div>
            <span className="text-xl font-bold text-gray-900">珞樱学堂</span>
          </div>

          <div className="mb-7">
            <h2 className="text-2xl font-bold text-gray-900 mb-1">欢迎登录</h2>
            <p className="text-sm text-gray-500">请选择您的身份并登录账号</p>
          </div>

          {/* 角色选择 */}
          <div className="mb-6">
            <div className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wider">选择登录身份</div>
            <div className="grid grid-cols-3 gap-3">
              {roles.map((role) => (
                <button
                  key={role.key}
                  onClick={() => { setSelectedRole(role.key); setError(''); }}
                  className={`relative flex flex-col items-center gap-2 p-3 rounded-xl border-2 transition-all cursor-pointer ${
                    selectedRole === role.key
                      ? `${role.bg} ${role.border} shadow-sm`
                      : 'bg-gray-50 border-gray-200 hover:border-gray-300 hover:bg-gray-100'
                  }`}
                >
                  {selectedRole === role.key && (
                    <span className={`absolute top-2 right-2 w-2 h-2 rounded-full ${role.badge}`}></span>
                  )}
                  <div className={`w-10 h-10 flex items-center justify-center rounded-xl ${
                    selectedRole === role.key ? role.iconBg : 'bg-white'
                  }`}>
                    <i className={`${role.icon} text-xl ${
                      selectedRole === role.key ? role.iconColor : 'text-gray-400'
                    }`}></i>
                  </div>
                  <div className="text-center">
                    <div className={`text-sm font-semibold ${
                      selectedRole === role.key ? 'text-gray-900' : 'text-gray-600'
                    }`}>{role.label}</div>
                    <div className="text-xs text-gray-400 mt-0.5 leading-tight">{role.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 登录表单 */}
          <form onSubmit={handleLogin} className="space-y-4" data-readdy-form>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                {selectedRole === 'student' ? '学号 / 邮箱' : selectedRole === 'teacher' ? '工号 / 邮箱' : '管理员账号'}
              </label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-400">
                  <i className="ri-user-line text-base"></i>
                </div>
                <input
                  type="text"
                  name="account"
                  value={account}
                  onChange={(e) => setAccount(e.target.value)}
                  placeholder={selectedRole === 'student' ? '请输入学号或邮箱' : selectedRole === 'teacher' ? '请输入工号或邮箱' : '请输入管理员账号'}
                  className="w-full pl-9 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-gray-700">密码</label>
                <button type="button" className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">忘记密码？</button>
              </div>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-400">
                  <i className="ri-lock-line text-base"></i>
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  className="w-full pl-9 pr-10 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className={`${showPassword ? 'ri-eye-off-line' : 'ri-eye-line'} text-base`}></i>
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
                <i className="ri-error-warning-line text-red-500 text-sm"></i>
                <span className="text-xs text-red-600">{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className={`w-full py-2.5 text-sm font-semibold text-white rounded-lg transition-all cursor-pointer whitespace-nowrap ${
                loading ? 'opacity-70 cursor-not-allowed' : 'hover:opacity-90 active:scale-[0.99]'
              } ${
                selectedRole === 'student' ? 'bg-teal-600 hover:bg-teal-700' :
                selectedRole === 'teacher' ? 'bg-orange-500 hover:bg-orange-600' :
                'bg-slate-600 hover:bg-slate-700'
              }`}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <i className="ri-loader-4-line animate-spin text-base"></i>
                  登录中...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  <i className={`${currentRole.icon} text-base`}></i>
                  以{currentRole.label}身份登录
                </span>
              )}
            </button>
          </form>

          {/* 注册提示 */}
          <p className="text-center text-xs text-gray-400 mt-6">
            还没有账号？
            <button onClick={() => navigate('/register')} className="text-teal-600 hover:text-teal-700 font-medium ml-1 cursor-pointer whitespace-nowrap">立即注册</button>
            <span className="mx-2 text-gray-300">|</span>
            <button className="text-gray-500 hover:text-gray-700 cursor-pointer whitespace-nowrap">使用帮助</button>
          </p>

          <p className="text-center text-xs text-gray-300 mt-4">
            © 2026 武汉大学网络空间安全学院
          </p>
        </div>
      </div>
    </div>
  );
}
