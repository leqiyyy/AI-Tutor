import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '@/services/auth';

export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [codeCountdown, setCodeCountdown] = useState(0);
  const [codeSent, setCodeSent] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  const startCountdown = (seconds: number) => {
    setCodeCountdown(seconds);
    const timer = window.setInterval(() => {
      setCodeCountdown((prev) => {
        if (prev <= 1) {
          window.clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const handleSendCode = async () => {
    setError('');
    if (!emailValid) {
      setError('请输入正确的邮箱地址');
      return;
    }
    setSendingCode(true);
    try {
      const result = await authService.sendVerificationCode({
        role: 'student',
        channel: 'email',
        target: email.trim(),
        purpose: 'reset_password',
      });
      setCodeSent(true);
      startCountdown(result.cooldownSeconds);
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : '验证码发送失败，请稍后重试');
    } finally {
      setSendingCode(false);
    }
  };

  const validate = () => {
    if (!emailValid) return '请输入正确的邮箱地址';
    if (!verifyCode.trim()) return '请输入验证码';
    if (password.length < 8) return '密码不少于8位';
    if (!/[a-zA-Z]/.test(password) || !/\d/.test(password)) return '密码需包含字母和数字';
    if (password !== confirmPassword) return '两次输入的新密码不一致';
    return '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      await authService.resetPassword({
        email: email.trim(),
        verifyCode: verifyCode.trim(),
        password,
        confirmPassword,
      });
      setSuccess(true);
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : '密码重置失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-soft min-h-screen flex items-center justify-center bg-white px-6" style={{ fontFamily: "'Noto Sans SC', sans-serif" }}>
        <div className="w-full max-w-md text-center">
          <div className="w-20 h-20 rounded-full bg-teal-50 flex items-center justify-center mx-auto mb-6">
            <i className="ri-checkbox-circle-line text-4xl text-teal-600"></i>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">密码已重置</h1>
          <p className="text-sm text-gray-500 mb-8">请使用新密码重新登录珞樱学堂。</p>
          <button
            onClick={() => navigate('/login')}
            className="w-full py-2.5 text-sm font-semibold text-white rounded-lg bg-teal-600 hover:bg-teal-700 transition-all cursor-pointer"
          >
            返回登录
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-soft min-h-screen flex" style={{ fontFamily: "'Noto Sans SC', sans-serif" }}>
      <div className="hidden lg:flex lg:w-[52%] relative flex-col overflow-hidden">
        <img
          src="https://readdy.ai/api/search-image?query=quiet%20modern%20university%20library%20desk%20with%20laptop%20and%20soft%20morning%20light%2C%20clean%20academic%20environment%2C%20warm%20professional%20photography&width=900&height=1080&seq=forgot-password-bg&orientation=portrait"
          alt="珞樱学堂"
          className="absolute inset-0 w-full h-full object-cover object-top"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-teal-900/70 via-teal-800/45 to-teal-600/35"></div>
        <div className="relative z-10 p-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <i className="ri-plant-line text-white text-xl"></i>
            </div>
            <span className="text-2xl font-bold text-white tracking-wide">珞樱学堂</span>
          </div>
        </div>
        <div className="relative z-10 flex-1 flex items-center px-10 pb-16">
          <div className="max-w-xl">
            <h1 className="text-4xl font-bold text-white leading-tight mb-5">找回账号访问权限</h1>
            <p className="text-white text-base leading-relaxed">通过注册邮箱完成验证码校验后，即可设置新的登录密码。</p>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col justify-center items-center bg-white px-8 py-12">
        <div className="w-full max-w-md">
          <div className="mb-7">
            <button
              type="button"
              onClick={() => navigate('/login')}
              className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-teal-600 mb-5 cursor-pointer"
            >
              <i className="ri-arrow-left-line text-sm"></i>
              返回登录
            </button>
            <h2 className="text-2xl font-bold text-gray-900 mb-1">忘记密码</h2>
            <p className="text-sm text-gray-500">输入注册邮箱，完成验证后设置新密码</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">邮箱</label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-400">
                  <i className="ri-mail-line text-base"></i>
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="请输入注册邮箱"
                  className="w-full pl-9 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">邮箱验证码</label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <div className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-400">
                    <i className="ri-shield-keyhole-line text-base"></i>
                  </div>
                  <input
                    type="text"
                    value={verifyCode}
                    onChange={(e) => setVerifyCode(e.target.value)}
                    placeholder="6位验证码"
                    maxLength={6}
                    className="w-full pl-9 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleSendCode}
                  disabled={sendingCode || codeCountdown > 0}
                  className="px-3 py-2.5 text-xs font-medium rounded-lg whitespace-nowrap transition-all cursor-pointer border bg-teal-50 text-teal-600 border-teal-200 hover:bg-teal-100 disabled:bg-gray-100 disabled:text-gray-400 disabled:border-gray-200 disabled:cursor-not-allowed"
                >
                  {sendingCode ? '发送中...' : codeCountdown > 0 ? `${codeCountdown}s后重发` : codeSent ? '重新发送' : '发送验证码'}
                </button>
              </div>
              {codeSent && <p className="text-xs text-gray-400 mt-1">验证码已发送至 {email.trim()}，请注意查收</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">新密码</label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-400">
                  <i className="ri-lock-line text-base"></i>
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="至少8位，包含字母和数字"
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

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">确认新密码</label>
              <div className="relative">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-400">
                  <i className="ri-lock-2-line text-base"></i>
                </div>
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="请再次输入新密码"
                  className="w-full pl-9 pr-10 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                >
                  <i className={`${showConfirmPassword ? 'ri-eye-off-line' : 'ri-eye-line'} text-base`}></i>
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
              className="w-full py-2.5 text-sm font-semibold text-white rounded-lg bg-teal-600 hover:bg-teal-700 transition-all cursor-pointer disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <i className="ri-loader-4-line animate-spin text-base"></i>
                  提交中...
                </span>
              ) : '重置密码'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
